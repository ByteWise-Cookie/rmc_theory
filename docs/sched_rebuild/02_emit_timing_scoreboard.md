# Command Emit Stage + Timing Scoreboard — legality engine

**Phase 1, block 2.** Sits directly behind the exchange fabric (block 1). Takes the
arbiter's winning command, proves it **JEDEC-legal this cycle**, drives it into the CA
out FIFO, and advances the timing state so the *next* pick is judged correctly.

This is the block that turns "the arbiter wants to do X" into "X is allowed at cycle N."
Two parts: the **scoreboard** (state = when each command type becomes legal) and the
**emit FSM** (pick → prove → drive → advance).

Grounded in the golden model `legal()`/`readyAt()` and verified **DDR5-4800B (40-40-40)**
timings. All counts in `tCK` unless noted.

---

## 0. Verified timing params (DDR5-4800B, the reference speed bin)

| Param | tCK | Meaning |
|-------|-----|---------|
| `tRCD` | 40 | ACT → CAS (row open → column) |
| `tRP`  | 40 | PRE → ACT (row close → open) |
| `tRAS` | 77 | ACT → PRE (row must stay open) |
| `tRC`  | 117 | ACT → ACT same bank (= tRAS+tRP) |
| `tRTP` | 18 | RD → PRE (read-to-precharge) |
| `tWR`  | 72 | last-write → PRE (write recovery, 30 ns) |
| `tCCD_S` | 8 | CAS → CAS, different bank group |
| `tCCD_L` | 12 | CAS → CAS, same bank group (read) |
| `tCCD_L_WR` | 48 | WR → WR same BG (= max(32 nCK, 20 ns)) |
| `tCCD_L_WR2` | 24 | WR → WR same BG, 2nd-tier |
| `tRRD_S` | 8 | ACT → ACT, different BG |
| `tRRD_L` | 12 | ACT → ACT, same BG |
| `tFAW` | 32 (1KB) / 40 (2KB) | 4-activate rolling window |
| `tWTR_S` | 6 | WR→RD, different BG (after WL+burst) |
| `tWTR_L` | 24 | WR→RD, same BG |
| `tRTP` | 18 | (see above) |
| `tPPD` | 2 | PRE → PRE (min precharge spacing) |
| `CL / RL` | 40 | read latency (CAS → data) |
| `CWL / WL` | 38 | write latency (CAS → data) |
| `tRFC1/2/sb` | density-dep | refresh occupancy (16Gb: 295/160/130 ns) |
| `tREFI` | 3.9 µs | avg refresh interval (32ms/8192) |

> All these are **programmable** — scoreboard reads them from block-1 §2B timing CSRs +
> a small local param bank. The values above are the bin defaults, not hard-coded.

---

## 1. Scoreboard — state, by hierarchy level

The scoreboard is a set of "next-legal cycle" counters (event times, compared against the
global cycle `gc`). Command legal iff `gc >= counter`. Four levels: global, rank, bank
group, bank.

### 1A. Global

| Field | Set by | Gates |
|-------|--------|-------|
| `caFree` | every emit | next cycle CA bus free (command cadence: +2 in 2N, +1 in 1N per command slot) |
| `dqFree` | every CAS | next cycle DQ bus free (+burst_len/2 after each CAS launch window) |
| `gc` | free-run | global cycle counter (reference clock) |

### 1B. Per-rank  (index: rank)

| Field | Set by | Gates |
|-------|--------|-------|
| `nActAny` | ACT | any-bank ACT spacing on the rank |
| `nPreAny` | PRE | any-bank PRE spacing (`tPPD`) |
| `nCasAny` | CAS | any-bank CAS spacing floor |
| `faw[]`   | ACT | rolling list of last activate times → `tFAW` (4-in-window) |
| `nWrRd` | WR | write→read turnaround ready time (WL + burst + `tWTR`) |
| `nRdWr` | RD | read→write turnaround ready time (RL + burst + `tRTRW`) |
| `nRef`  | REF | refresh-busy until (`tRFC` after REFab / `tRFCsb` after REFsb) |

### 1C. Per-bank-group  (index: rank × BG)

| Field | Set by | Gates |
|-------|--------|-------|
| `nActBg` | ACT | ACT→ACT same BG (`tRRD_L`) |
| `nCasBg` | CAS | CAS→CAS same BG (`tCCD_L` read / `tCCD_L_WR` write) |

### 1D. Per-bank  (index: rank × BG × bank)

| Field | Set by | Gates |
|-------|--------|-------|
| `nAct` | ACT | ACT→ACT same bank (`tRC`) |
| `nRas` | ACT | earliest PRE (`tRAS` after ACT) |
| `nPre` | PRE | PRE→ACT (`tRP`) i.e. when row can reopen |
| `nCas` | CAS | CAS→CAS same bank, + `tRCD` after ACT (first CAS) |
| `nRtp` | RD | PRE-after-read ready (`tRTP`) |
| `nWtp` | WR | PRE-after-write ready (`tWR` after last write) |
| `open_row` | ACT/PRE | currently open row, or CLOSED |
| `state` | FSM | IDLE / ACTIVATING / OPEN / PRECHARGING |

> **Emit does not own** which row is open as *policy* — that's the arbiter/row-lock
> (block 3). The scoreboard only records the *fact* of the open row and the timing
> consequences.

---

## 2. `legal(cmd)` — earliest legal cycle (mirrors golden model)

For a candidate command `c` on bank `b` / BG `g` / rank `rk`, the earliest legal cycle:

```
legal(c):
  x = caFree                                  # CA bus must be free
  if c == ACT:
      x = max(x, b.nAct, g.nActBg, rk.nActAny)
      if rk.faw has >=3 prior acts in window:  # 4th activate
          x = max(x, faw[len-3] + tFAW)
      x = max(x, b.nPre)                       # row must be precharged (tRP)
  elif c == PRE:
      x = max(x, b.nRas, rk.nPreAny)           # tRAS met, tPPD spacing
      x = max(x, (b.lastRD ? b.nRtp : 0))      # tRTP after read
      x = max(x, (b.lastWR ? b.nWtp : 0))      # tWR after write
  else:                                        # RD / WR (CAS)
      lat = (c.dir == R) ? RL : WL
      x = max(x, b.nCas, g.nCasBg, rk.nCasAny)
      x = max(x, b.nRcd)                        # tRCD after ACT (first CAS)
      x = max(x, dqFree - lat)                  # DQ bus free at data time
      x = max(x, (c.dir==R) ? rk.nWrRd : rk.nRdWr)  # turnaround
  return x
```

`readyAt()` (used by the timing-wheel probe, block-3 note) is the same function without
the `caFree` term — "when would the DRAM allow it, ignoring CA contention."

**Legal now** ⇔ `legal(c) <= gc`.

---

## 3. Emit FSM — pick → prove → drive → advance

Per emit cycle:

1. **Receive winner** from arbiter (block 3): `{cmd, bank, bg, rank, row, col, dir, tag}`.
   Arbiter guarantees the winner already passed `readyAt <= gc` at nomination; emit
   re-checks `legal()` against the *live* `caFree` (the arbiter may have picked assuming
   this slot).
2. **CA credit check** — fabric `caFree`/`ca_credit` says the CA out FIFO can take a
   command this cycle. In 2N a 2-cycle command consumes the slot for 2 `tCK`.
3. **Drive** — push `{opcode, addr fields, cs, rank}` into fabric CA out FIFO (block-1
   §3A). For CAS, also arm the data path: WR → notify WR buffer to launch at
   `t_phy_wrlat`; RD → register outstanding-read tracker entry.
4. **Advance scoreboard** — set forward counters for the emitted command:

| Emitted | Updates |
|---------|---------|
| ACT | `b.nAct=gc+tRC`, `b.nRas=gc+tRAS`, `b.nRcd=gc+tRCD`, `g.nActBg=gc+tRRD_L`, `rk.nActAny=gc+tRRD_S`, push `gc` to `rk.faw`, `b.open_row=row`, `caFree=gc+cadence` |
| PRE | `b.nPre=gc+tRP`, `rk.nPreAny=gc+tPPD`, `b.open_row=CLOSED`, `caFree+=cadence` |
| RD  | `b.nCas=gc+tCCD_L`, `g.nCasBg=gc+tCCD_L`, `rk.nCasAny=gc+tCCD_S`, `dqFree=gc+RL+BL/2`, `b.nRtp=gc+tRTP`, `rk.nRdWr=gc+RL+BL/2+tRTRW`, `caFree+=cadence` |
| WR  | `b.nCas=gc+tCCD_L_WR`, `g.nCasBg=gc+tCCD_L_WR`, `rk.nCasAny=gc+tCCD_S`, `dqFree=gc+WL+BL/2`, `b.nWtp=gc+WL+BL/2+tWR`, `rk.nWrRd=gc+WL+BL/2+tWTR`, `caFree+=cadence` |
| REF | `rk.nRef=gc+tRFC`, block `sts_ca_quiesced` for the window, `caFree+=cadence` |

5. **Idle path** — if no legal winner this cycle, `caFree`/`gc` advance; the DQ guardrail
   (below) flags if `dqFree` is drifting past `gc` with demand pending.

---

## 4. Guardrails living at the emit boundary

- **Never-idle-DQ** — track `dqFree - gc`. If it goes positive (DQ idle ahead) while any
  bank has a ready CAS, that's a scheduling miss; raise a perf-counter, and the arbiter's
  servo term (block 3) reacts. Emit *reports*; arbiter *fixes*.
- **RAW pause** — emit must not launch a RD to a bank/addr with an in-flight WR not yet
  drained (block-4 RAW gate). Emit trusts the arbiter's RAW-cleared winner but asserts a
  final same-cycle check against `wr_occupied`.
- **Maintenance quiesce** — `sts_ca_quiesced` (block-1 §2D) high → emit stalls the CA
  path; refresh/update owns the bus.
- **2N cadence** — the CA budget is 1 command / 2 `tCK` in 2N. `caFree += 2` per command
  (in 1N `+=1`). This is the single knob that makes the whole legality math gear-aware.

---

## 5. Interfaces

**Up (from arbiter, block 3):**
`win_cmd`, `win_bank/bg/rank`, `win_row/col`, `win_dir`, `win_tag`, `win_valid`.
Back: `emit_ack` (winner consumed), `emit_stall` (CA busy / quiesced).

**Down (to fabric, block 1):**
`ca_push` + `ca_fields`, reads `caFree`/`ca_credit`, `sts_ca_quiesced`.
`wr_launch` (arm WR buffer), `rd_track_push` (outstanding-read tracker).

**Sideways (scoreboard read, to arbiter):**
The arbiter reads `readyAt(c)` for its candidates — the scoreboard exposes a combinational
`readyAt` port per candidate lane so the arbiter scores only DRAM-ready commands.

---

## Open items (emit / scoreboard)

- **OE-1** `tRTRW` (read-to-write bus turnaround) exact value — pull from spec AC table.
- **OE-2** `readyAt` port count = arbiter candidate lanes — pin when arbiter width fixed
  (block 3).
- **OE-3** REF granularity — per-rank REFab vs per-bank REFsb changes which counter the
  window blocks; refresh block (later) resolves.
- **OE-4** first-CAS `tRCD` vs subsequent-CAS `tCCD` merge — `b.nCas` carries both; verify
  no double-count when ACT and first CAS are back-to-back legal.
- **OE-5** cadence in 1:1 vs 1:4 gear — `caFree += cadence` where cadence = 2·(tCK per
  dfi_clk)? Reconcile with block-1 phase packer so CA budget is counted in one domain.
