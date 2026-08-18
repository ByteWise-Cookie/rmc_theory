# Command Emit Stage + Timing Scoreboard — legality engine

**Phase 1, block 02.** Sits directly behind the exchange fabric (block 01). Takes the
arbiter's winning command, proves it **JEDEC-legal this cycle**, drives it into the CA out
FIFO, and advances the timing state so the *next* pick is judged correctly.

Turns "the arbiter wants X" into "X is allowed at cycle N." Two parts: the **scoreboard**
(registered `can_*` legal flags + `next_*` deadlines) and the **emit FSM** (pick → prove →
drive → advance).

Grounded in the golden model `legal()`/`readyAt()`, verified **DDR5-4800B** timings, and
the KB naming convention (block 00). All counts in `tCK`.

> **Reconciled with prior work (block 00 ledger):** this block adopts the KB's registered
> `can_*` flags (I1), `next_*`+sign-bit compare (I2), the **3-table** scoreboard (I3), the
> slack vector `A` (I25), and the ≥2-live-BG invariant + CA lookahead budget (I20/I23).
> `caFree`/`dqFree` are kept (new, no KB equivalent).

---

## 0. Verified timing params (DDR5-4800B) → `timing_reg_file`

All held in `timing_reg_file` as `T_<PARAM>` (`param_id → nCK`), CSR-written at init,
combinational multi-port read (I10). Values below are bin defaults, **not hard-coded**.

| Param | tCK | Meaning |
|-------|-----|---------|
| `T_RCD` | 40 | ACT → CAS |
| `T_RP`  | 40 | PRE → ACT |
| `T_RAS` | 77 | ACT → PRE (min row-open) |
| `T_RC`  | 117 | ACT → ACT same bank (tRAS+tRP) |
| `T_RTP` | 18 | RD → PRE |
| `T_WR`  | 72 | last-write → PRE (30 ns) |
| `T_CCD_S` | 8 | CAS→CAS diff BG (= BL/2, the heartbeat) |
| `T_CCD_L` | 12 | CAS→CAS same BG (read) |
| `T_CCD_L_WR` | 48 | WR→WR same BG (max(32nCK,20ns)) |
| `T_CCD_L_WR2` | 24 | WR→WR same BG, 2nd-tier |
| `T_RRD_S` | 8 | ACT→ACT diff BG |
| `T_RRD_L` | 12 | ACT→ACT same BG |
| `T_FAW` | 32 (1KB)/40 (2KB) | 4-activate window |
| `T_WTR_S` | 6 | WR→RD diff BG (after WL+burst) |
| `T_WTR_L` | 24 | WR→RD same BG |
| `T_PPD` | 2 | PRE→PRE |
| `T_RTW` | ~14 | RD→WR bus turnaround (OE-1) |
| `RL`/`WL` | 40/38 | read/write latency |
| `T_RFC1/2/sb` | density-dep | refresh occupancy (16Gb: 295/160/130 ns) |
| `T_REFI` | 3.9 µs | avg refresh interval |

---

## 1. Scoreboard — 3 tables + timing_reg_file (KB §9A–C)

State = registered `can_*` legal flags backed by `next_*` deadline timestamps. **A command
is legal when `can_x==1`; `can_x = (gc - next_x)[MSB]==0`, precomputed every cycle out of
the scheduling critical path** (I1/I2 — no subtractor in the pick path). Three tables:

### 1A. Per-Bank FSM Table — `[N_RANKS][16]`
| Field | Set by | Meaning |
|-------|--------|---------|
| `state` | FSM | IDLE / ACTIVATING / ACTIVE / PRECHARGING / REFRESHING_SB |
| `row_open` | ACT/PRE | currently open row, or CLOSED |
| `next_cas` | ACT/CAS | tRCD after ACT (first CAS); CAS→CAS same bank |
| `next_pre` | RD/WR/ACT | earliest PRE (tRAS from ACT; tRTP after RD; WL+BL/2+tWR after WR) |
| `next_act` | PRE | tRP after PRE (row can reopen) |
| `next_ref` | REFsb | tRFCsb recovery |
| `can_cas/pre/act/ref` | gc cmp | registered legal flags |
| `ref_pending` | ME | refresh queued (no CAM equivalent for REF) |

### 1B. Per-Rank FSM Table — `[N_RANKS]`
| Field | Set by | Meaning |
|-------|--------|---------|
| `next_act_any` | ACT | any-bank ACT spacing (tRRD_S) |
| `next_pre_any` | PRE | any-bank PRE spacing (tPPD) |
| `next_cas_any` | CAS | any-bank CAS spacing floor (tCCD_S) |
| `next_rd_wr` | RD | read→write turnaround (RL+BL/2+tRTW) |
| `next_wr_rd` | WR | write→read turnaround (WL+BL/2+tWTR) |
| `next_rfc` | REFab | tRFC1 recovery |
| `faw_window[4]` | ACT | ring of last-4 ACT timestamps → tFAW |
| `can_act_any/cas_any/faw/rd_wr/wr_rd` | gc cmp | registered flags |
| `gate_rfc/gate_zq` | ME | blocks all per-bank cmds this rank |

> **A10 (pkg intent):** `N_RANKS 1→2` — cross-rank W→R skips tWTR (~22 tCK cheaper). The
> per-rank table is already indexed `[N_RANKS]`; the bump is a param change, deferred to
> RTL-go.

### 1C. Global Timing Table — `[1]` (BG-level lives here per KB)
| Field | Set by | Meaning |
|-------|--------|---------|
| `next_act_bg[N_BG]` | ACT | ACT→ACT same BG (tRRD_L) |
| `next_cas_bg[N_BG]` | CAS | CAS→CAS same BG (tCCD_L / tCCD_L_WR) |
| `next_wtr_bg[N_BG]` | WR | same-BG write→read (tWTR_L) |
| `last_act_bg[N_BG]` | ACT | gc at last ACT per BG (BG-rotate tie-break) |
| `can_act_bg[N_BG]/can_cas_bg[N_BG]` | gc cmp | registered per-BG flags |
| `global_state` | FSM | INIT/NORMAL/SOFT_RESET/REF_STALL/ZQ_STALL |

Plus **`caFree`** (next cycle CA bus free) and **`dqFree`** (next cycle DQ bus free) — new,
no KB equivalent; they track the two shared buses directly.

> **Emit does not own** which row is open as *policy* — that's the arbiter/row-lock
> (block 03). The scoreboard records the *fact* + timing consequence only.

---

## 2. `legal(cmd)` — the reference the `can_*` flags precompute

`legal()` is the *specification*; in hardware the `can_*` flags are its registered result.
For candidate `c` on bank `b` / BG `g` / rank `rk`, earliest legal cycle:

```
legal(c):
  x = caFree                                      # CA bus free (+ credit)
  if c == ACT:
      x = max(x, b.next_act, g.next_act_bg, rk.next_act_any, b.next_pre)
      if rk.faw_window has >=3 acts in window:     # 4th activate
          x = max(x, faw_window[len-3] + T_FAW)
  elif c == PRE:
      x = max(x, b.next_pre, rk.next_pre_any)       # tRAS/tRTP/tWR folded into next_pre; tPPD
  else:                                             # RD / WR (CAS)
      lat = (c.dir==R) ? RL : WL
      x = max(x, b.next_cas, g.next_cas_bg, rk.next_cas_any)
      x = max(x, dqFree - lat)                       # DQ bus free at data time
      x = max(x, (c.dir==R) ? rk.next_wr_rd : rk.next_rd_wr)  # turnaround
  return x
```

`readyAt()` = `legal()` minus the `caFree` term ("when would the DRAM allow it, ignoring
CA contention") — the arbiter (block 03) reads it to score only DRAM-ready candidates.
**Legal now** ⇔ `can_<c>==1` ⇔ `legal(c) <= gc`.

### 2b. Slack vector `A` — schedule as windows, not points (I25/I26)

Each prep command has not one deadline but a **legal window**. Working **backward** from
the DQ slot `N` it wants to fill:
```
D_RD  = N                       D_ACT = N − T_RCD        D_PRE = N − T_RCD − T_RP
window_i = [ E_i , D_i ]        E_i = max(D_i − A_i , resource_ready_i)
```
`A = {A_PRE, A_ACT, A_CAS, A_REF}` is a **CSR-tunable** slack vector. `A_i=0` → one legal
cycle (zero freedom); `A_i>0` → a window, so commands for many in-flight requests
**bin-pack** into the free CA slots (§4). Cost of larger `A_i`: row opens earlier, stays
open longer (more tRAS exposure). Ideal = **smallest `A_i` that keeps the CA lane
feasible**. This is what lets the emitter hide prep ~10 bursts ahead (I24).

---

## 3. Emit FSM — pick → prove → drive → advance

Per emit cycle:

1. **Receive winner** from arbiter (block 03): `{cmd, bank, bg, rank, row, col, dir, tag}`.
   Arbiter guarantees `readyAt<=gc` at nomination; emit re-checks `can_<cmd>` against the
   *live* `caFree`.
2. **CA credit check** — fabric `caFree`/`ca_credit`: CA out FIFO can take a command. In
   2N a 2-cycle command holds the slot 2 `tCK`.
3. **Drive** — push `{opcode, addr fields, cs, rank}` into fabric CA out FIFO (block-01
   §3A). For CAS, arm the data path: WR → `wr_launch` (WR buffer launches at `T_PHY_WRLAT`);
   RD → register the outstanding-read tracker entry.
4. **Advance scoreboard** — set forward `next_*` (KB §8 S4 writeback):

| Emitted | Updates |
|---------|---------|
| ACT | `b.next_cas=gc+T_RCD`, `b.next_pre=gc+T_RAS`, `b.next_act=gc+T_RC`, `g.next_act_bg=gc+T_RRD_L`, `rk.next_act_any=gc+T_RRD_S`, shift `gc`→`rk.faw_window`, `g.last_act_bg=gc`, `b.row_open=row`, `caFree+=cadence` |
| PRE | `b.next_act=gc+T_RP`, `rk.next_pre_any=gc+T_PPD`, `b.row_open=CLOSED`, `caFree+=cadence` |
| RD  | `b.next_cas=gc+T_CCD_L`, `g.next_cas_bg=gc+T_CCD_L`, `rk.next_cas_any=gc+T_CCD_S`, `dqFree=gc+RL+BL/2`, `b.next_pre=gc+T_RTP`, `rk.next_rd_wr=gc+RL+BL/2+T_RTW`, `caFree+=cadence` |
| WR  | `b.next_cas=gc+T_CCD_L_WR`, `g.next_cas_bg=gc+T_CCD_L_WR`, `g.next_wtr_bg=gc+T_WTR_L`, `rk.next_cas_any=gc+T_CCD_S`, `dqFree=gc+WL+BL/2`, `b.next_pre=gc+WL+BL/2+T_WR`, `rk.next_wr_rd=gc+WL+BL/2+T_WTR`, `caFree+=cadence` |
| REF | `rk.next_rfc=gc+T_RFC1` (REFab) / `b.next_ref=gc+T_RFCsb` (REFsb), assert `sts_ca_quiesced`, `caFree+=cadence` |

5. **Idle path** — no legal winner: `caFree`/`gc` advance; the DQ guardrail flags if
   `dqFree` drifts past `gc` with demand pending.

---

## 4. Guardrails + datapath invariants at the emit boundary

- **≥2-live-BG invariant (I20) — hard.** Same-BG CAS pays `T_CCD_L`(rd,4-tCK bubble) or
  `T_CCD_L_WR`(wr,24-tCK bubble); diff-BG pays `T_CCD_S=8=`gapless. The arbiter (block 03)
  **must** keep ≥2 bank-groups holding a ready same-direction CAS so it can ping-pong BGs.
  Emit exposes `last_act_bg`/`next_cas_bg` so the arbiter can steer. **This is the #1
  datapath-busy job.**
- **CA lookahead budget (I23).** Under one 8-tCK burst there are 4 CA slots (2-cyc
  commands); 1 = the next CAS, **3 free** to prep future ACT/PRE. `caFree` accounting must
  expose those 3 slots so the slack-window bin-packing (§2b) fills them.
- **Never-idle-DQ.** Track `dqFree - gc`; if positive while a ready CAS exists → scheduling
  miss → perf-counter; arbiter's servo term reacts. Emit *reports*, arbiter *fixes*.
- **RAW pause.** Emit asserts a final same-cycle `wr_occupied` check on the RAW-cleared
  winner (block 03 HZU owns detection).
- **Maintenance quiesce.** `sts_ca_quiesced` (block-01 §2D) → emit stalls CA; refresh/update
  owns the bus.
- **2N cadence.** CA budget = 1 command / 2 `tCK` in 2N: `caFree += 2` (1N: `+=1`). The one
  gear-aware knob (reconcile with block-01 phase packer, OE-5).

---

## 5. Interfaces (valid-credit, I15)

**Up (from arbiter, block 03):** `win_cmd`, `win_bank/bg/rank`, `win_row/col`, `win_dir`,
`win_tag`, `win_valid`. Back: `emit_ack` (consumed), `emit_stall` (CA busy/quiesced).
Inter-block handshake = **valid-credit** (no combinational ready).

**Down (to fabric, block 01):** `ca_push` + `ca_fields`, reads `caFree`/`ca_credit`,
`sts_ca_quiesced`; `wr_launch`; `rd_track_push`.

**Sideways (to arbiter):** combinational `readyAt(c)` per candidate lane + `can_*`,
`last_act_bg`, `next_cas_bg` (for BG-rotate scoring).

---

## Open items (emit / scoreboard)

- **OE-1** `T_RTW` exact value — pull from spec AC table (currently ~14).
- **OE-2** `readyAt`/`can_*` port fan = arbiter candidate lanes — pin at arbiter width.
- **OE-3** REF granularity — REFab (per-rank `next_rfc`) vs REFsb (per-bank `next_ref`);
  refresh/ME block resolves.
- **OE-4** first-CAS `T_RCD` vs subsequent-CAS `T_CCD` — `next_cas` carries both; verify no
  double-count when ACT + first CAS are back-to-back legal.
- **OE-5** cadence across 1:1…1:4 gear — count the CA budget in **one** domain; reconcile
  with block-01 phase packer.
- **OE-6** slack `A` defaults — start small (`A_PRE=A_ACT=3`), tune in the sizing sweep.
