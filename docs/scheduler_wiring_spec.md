# RMC Scheduler — Visio Wiring Spec (buffer-level blueprint)

Draw-it-yourself blueprint for the scheduler datapath: every **block** (buffer level),
its **ports**, the **net list** (what wires to what, with widths), a **placement plan**
for the Visio canvas, and **gate-level insets** for the handful of combinational clusters
that need them. Names are the real RTL (`rmc/rtl/mc_core/*.sv`, `rmc_pkg.sv`) and the
`RMC_IO_Map.md §19` stage ports — not invented.

Companion views: [[scheduler_bank_fsm]] (FSM + arbiter + `sched_gate_hw` datapath) ·
[[scheduler_staged_logic]] (S0–S4 port lists). This doc is the **connectivity + layout**
sheet those two describe behaviourally.

> Phase: doc-only, pkg **frozen**. Widths below are the frozen x16 instance
> (`N_BANKS=16`, `N_RD_ENTRIES=32`); design intent is `N_BANKS=32` / `N_RD=64` (RTL phase).
> `scoreboard` = new thin regs holding the `bank_fsm_t` rows (replaces
> `per_bank_fsm_table`); `work_state` is an added 2-bit field on `*_status_reg`.

---

## A. Block inventory (buffer level)

| # | instance | RTL module | role | Visio zone |
|---|---|---|---|---|
| — | *CIF boundary (context)* | `axi_rd/wr_port`, `burst_splitter`, `merge_logic`, `amu`, `rob`, `wdb` | request in / data out | A |
| 1 | `gc_ctr` | `gc_counter` | free-running `gc` [32] | C |
| 2 | `rd_tcam` / `wr_tcam` | `rd_tcam` / `wr_tcam` | row-match search (classify) | B |
| 3 | `rd_stat` / `wr_stat` | `rd_status_reg` / `wr_status_reg` | outstanding table: valid/status/age/**work_state** | B |
| 4 | `rd_wm` / `wr_wm` | `rd_watermark_mgr` / `wr_watermark_mgr` | slot alloc / retire, full flags | B |
| 5 | `timing_rf` | `timing_reg_file` | nCK per param [16], multi-port comb read | C |
| 6 | `scoreboard` | *(new thin regs)* → `bank_fsm_t[N_BANKS]` | `next_cas/pre/act`, `row_open`, `state`, **row-lock** (`lock_row/demand_count/oldest_miss_age`), **`age[lane]`**, globals (`dqFree/next_cas_any/next_cas_bg[bg]`, tFAW ring) | C |
| 7 | `bank_act` | `bank_activity_ctr` | per-bank demand `bank_act_count` | C |
| 8 | `maint_eng` | `maintenance_engine` | S0: REF/RFM/ZQ/PD-SR, override + gates | E-top |
| 9 | `classify` | *(inside `scheduler`)* | TCAM-vec → hit/empty/miss → `work_state`, `s1_hit_meta` | D |
| 10 | `gate_gen` | *(inside `scheduler`)* | comparators + AND → `can_cas/act/pre[N_BANKS]` | D |
| 11 | `cand_gen` | *(inside `scheduler`)* | per-bank head candidate `{cmd,idx,bank,bg,row,col}` | D |
| 12 | `arbiter` | *(inside `scheduler`)* | weight priority-encoder + aging + **servo** | E |
| 13 | `s4_mux` | *(inside `scheduler`)* | winner vs `s0_override` → final cmd | E |
| 14 | `dfi_drv` | *(inside `scheduler`)* | DFI 5.2 encode → `dfi_*` | F |
| 15 | `writeback` | *(inside `scheduler`)* | commit scoreboard / status / watermark / RAA (feedback) | E→C rail |
| — | *data plane (context)* | `read_data_path`, `write_data_path`, `raw_bypass_mgr` | RL/WL data move | A |

Blocks 9–15 are the combinational innards of `scheduler.sv` — draw them as separate
Visio shapes even though they are one RTL module; that is the whole point of the sheet.

---

## B. Placement plan (Visio canvas, left → right dataflow)

```
 ┌ZONE A┐   ┌───ZONE B────┐  ┌───ZONE C────┐   ┌──────ZONE D──────┐  ┌───ZONE E───┐  ┌ZONE F┐
 │ CIF  │   │ outstanding │  │  STATE (FF) │   │  COMBINATIONAL   │  │  ARBITER   │  │ DFI  │
 │ (ctx)│   │  tables     │  │ scoreboard  │   │ classify→gate_gen│  │ +servo     │  │ drv  │
 │ rob  │   │ tcam+stat+wm│  │ timing_rf   │   │ →cand_gen        │  │ +s4_mux    │  │ →PHY │
 │ wdb  │   │ (rd top /   │  │ gc, bank_act│   │ can_cas/act/pre  │  │            │  │      │
 │      │   │  wr bottom) │  │             │   │ [N_BANKS] bitmaps│  │            │  │      │
 └──────┘   └─────────────┘  └─────────────┘   └──────────────────┘  └────────────┘  └──────┘
                                    ▲                                   │  ▲ maint_eng (E-top)
                                    └──────── WRITEBACK feedback bus ◄───┘     override + gate_rfc/zq
                                              (bottom rail, distinct colour)   drops down onto D+E
```

Zone rules for the drawing:
- **Two horizontal planes in B & D:** reads on top, writes on the bottom; they **merge at
  `cand_gen`** (batch-mode picks R or W head per bank). Keep them separate until there.
- **Zone C = registers (flip-flops).** Draw as record/list shapes (fields from
  `bank_fsm_t`). Everything here is clocked.
- **Zone D = combinational.** Wrap in a dashed container labelled "comb, 1 cmd decode".
- **Bottom rail = the feedback** (writeback → scoreboard/status/watermark). Colour it
  distinctly (orange). It is what makes `can_*` deassert after an issue — see
  [[scheduler_bank_fsm]] §7.
- **Top rail = S0** (`maint_eng`) override + `gate_rfc/gate_zq`, dropping onto `gate_gen`
  (blocks a rank) and `s4_mux` (wins the cmd).

---

## C. Net list — the connections (SIGNAL [width] : SRC.port → DST.port)

Widths are the frozen x16 instance. `[N_BANKS]=16`, `[N_RD]=32`, `[N_WR]=64`.

### C.1 Broadcast
```
clk, rst_n                → all sequential blocks (1,3,4,6,7,8, writeback)
gc            [32]        : gc_ctr           → gate_gen, arbiter(aging), writeback, maint_eng
```

### C.2 Into classify (Zone B → D)
```
rd_tcam_hit_bitmap [32]   : rd_tcam  → classify
wr_tcam_hit_bitmap [64]   : wr_tcam  → classify
rd/wr_tcam_hit_meta       : rd/wr_tcam → classify, cand_gen   {row[17],col[10],req_type,entry_idx,axi_id}
rd_status_valid    [32]   : rd_stat  → classify
wr_status_valid    [64]   : wr_stat  → classify
status.age, work_state    : rd/wr_stat → classify, arbiter(age tie-break)
new_rd_bank/row/col/id/age : burst_splitter → classify   (newest-arrival fast path)
batch_policy_reg          : (adaptive batch) → classify, cand_gen   (R/W mode + QoS)
```

### C.3 State → gate comparators (Zone C → D)   *— the heart*
```
next_cas[b] [32], next_act[b] [32], next_pre[b] [32]  : scoreboard → gate_gen
row_open[b] [17], state[b] [3]                        : scoreboard → gate_gen (row match / !open)
dqFree [32], next_cas_any [32], next_cas_bg[bg] [32]  : scoreboard → gate_gen (CAS lane)
tFAW ring, turnaround win (tRTW/tWTR)                 : scoreboard → gate_gen
lock_row[b][17], demand_count[b], oldest_miss_age[b]  : scoreboard → gate_gen (can_pre row-lock)
age[lane] (PRE/ACT/CAS)                               : scoreboard → arbiter (aging term)
timing vals {tRCD,tRP,tRAS,tCCD_L/S,tRTP,tWR,tRRD_L/S,tFAW,RL,WL} [16 ea] : timing_rf → gate_gen(cmp), writeback(adders)
bank_act_count[b]                                    : bank_act → gate_gen (can_act demand, can_pre lock), servo
```

### C.4 Gate + candidate outputs (Zone D → E)
```
can_cas [N_BANKS], can_act [N_BANKS], can_pre [N_BANKS]  : gate_gen → arbiter
candidate[b] {cmd_type[3], entry_idx, bank[2], bg[2], row[17], col[10], req_type} : cand_gen → arbiter
```

### C.5 Servo (Zone D → E, the CAS↔ACT balance)
```
ready_cas = popcount(can_cas) [5]   : gate_gen → servo
dq_free_in = dqFree − gc     [32]   : scoreboard/writeback → servo
faw_budget                          : tFAW ring → servo
act_wmod (+/−)                      : servo → arbiter (ACT lane weight only)
```

### C.6 S0 maintenance (Zone E-top → D, E)
```
ref_urgent, ref_due, rfm_req, zq_due   : scheduler top-in → maint_eng
s0_override [1]                        : maint_eng → s4_mux (wins)
s0_cmd_type [3], s0_rank, s0_bg [2], s0_bank [2] : maint_eng → s4_mux
set/clr gate_rfc[rank], set/clr gate_zq[rank]    : maint_eng → gate_gen (block a rank), s4_mux
```

### C.7 Arbiter → emit (Zone E → F)
```
winner {cmd_type[3], rank, bg[2], bank[2], row[17], col[10], entry_idx, req_type} : arbiter → s4_mux
final_cmd (winner OR s0_override)      : s4_mux → dfi_drv
dfi_cmd_valid [1]                      : dfi_drv → PHY / ME mux   (scheduler top-out)
dfi_cmd [3]                            : dfi_drv → PHY
dfi_addr_row [17], dfi_addr_col [10]   : dfi_drv → PHY
dfi_bank [2], dfi_bg [2]               : dfi_drv → PHY
```

### C.8 Writeback feedback (Zone E → C, the bottom rail)
```
bank_fsm_update_en + {state, next_cas, next_pre, next_act, row_open}  : writeback → scoreboard
global_timing_update {next_cas_any, next_act_any, faw ring, bg arrays}: writeback → scoreboard (globals)
                     on CAS: dqFree=gc+lat+BL2 ; next_cas_bg=gc+tCCD_L ; next_cas_any=gc+tCCD_S
                     next_pre[b] = MAX(next_pre, gc+tRTP | gc+WL+BL2+tWR)   ← the MAX bug
status_update_en/idx/val (work_state advance NEED_PRE→ACT→CAS→DONE, retire) : writeback → rd/wr_stat
retire_en/idx                          : writeback → rd/wr_wm  (free slot)
raa_inc_en                             : writeback → maint_eng (RAA++ per ACT, for RFM)
inc/dec_ref_credits                    : writeback → maint_eng (leaky bucket)
sched_ack                              : writeback → maint_eng (S0 handshake)
rd data → rob @ RL ; wr drain ← wdb @ WL : dfi_drv/writeback → data plane
```

---

## D. Gate-level insets (draw on a 2nd Visio page, hyperlink from the block)

Only these five clusters need gate detail; everything else stays buffer-level.

**D.1 Timing comparator** (×`N_BANKS`×3 — the `can_*` legality bit)
```
   next_x[b][32] ─┐
                  ├─►  [ ≥ ]  ─► ge_x[b]      (gc ≥ next_x ⇒ legal).  Magnitude compare,
   gc[32] ────────┘                            or subtract + sign bit. 1 per class per bank.
```

**D.2 `can_cas[b]` AND cluster**
```
 row_open[b] ─────────────┐
 (open_row[b]==req_row) ──┤   row-match comparator [17]
 ge_cas[b]  (gc≥next_cas) ┤
 ge_cas_bg  (tCCD_L)  ────┤──► AND ─► can_cas[b]
 ge_cas_any (tCCD_S)  ────┤
 ge_dqFree  (gc≥dqFree) ──┤
 turnaround (tRTW/tWTR) ──┤
 NOT(age-cap gate) ───────┘
 (can_act[b] / can_pre[b] = same pattern, fewer terms — see bank_fsm §7)
```

**D.3 Weight arbiter — priority encoder + aging** (the pick)
```
 per lane L, per bank b:  w[L][b] = K·control[L] + age[L][b] + (L==ACT ? act_wmod : 0)
 class order CAS > ACT > PRE  (control constants)
   argmax over eligible {can_*} of w  → winner_bank, winner_class
   ties: oldest status.age, then BG-rotate (bg != last_cas_bg)
   GUARDRAIL: (dq_free_in==0 & ready_cas≥1) ⇒ force class=CAS   (never idle DQ)
   s0_override ⇒ s4_mux bypasses arbiter entirely
```

**D.4 Writeback update arithmetic**
```
 dqFree'      = gc + lat + BL2            (lat = RL rd / WL wr; adder)
 next_cas_bg' = gc + tCCD_L               next_cas_any' = gc + tCCD_S
 next_pre'    = MAX( next_pre,            ← mux-of-adders, the golden-model MAX
                     gc + tRTP,            (read path)
                     gc + WL + BL2 + tWR ) (write path)
 next_act'    = gc + tRP  (on PRE) ;  next_cas' = gc + tRCD (on ACT)
 faw_ring    << push gc on ACT, pop at gc−tFAW
```

**D.5 Servo datapath**
```
 ready_cas   = popcount(can_cas[N_BANKS])           (ones-counter → 5b)
 dq_free_in  = dqFree − gc                           (subtractor, clamp ≥0)
 act_wmod    = (ready_cas<POOL_LOW  & dq_free_in≤LOOKAHEAD) ?  +boost·(POOL_LOW−ready_cas)
             : (ready_cas>POOL_HIGH | faw_low)       ?  −damp·(ready_cas−POOL_HIGH)
             : 0
```

---

## E. Width quick-reference (from `rmc_pkg.sv`, frozen x16)

| signal | width | note |
|---|---|---|
| `GC_WIDTH` / gc, all `next_*`, `age` | 32 | |
| `ROW_BITS` / row, `lock_row` | 17 | |
| `COL_BITS` / col | 10 | |
| `BG_BITS` / bg | 2 | intent 3 (x8, 8 BG) |
| `BANK_BITS` / bank | 2 | |
| `N_BANKS` (bitmap width) | 16 | **intent 32** |
| `N_RD_ENTRIES` | 32 | **intent 64** |
| `N_WR_ENTRIES` | 64 | |
| `TIMING_WIDTH` (each nCK) | 16 | |
| `dfi_cmd` | 3 | |
| `STATUS_WIDTH` | 2 | `work_state` reuses 2b |
| `FAW_DEPTH` | 4 | tFAW ring |
| `AGE_THR2` | 256 | **= `AGE_MAX` candidate** (row-lock age cap) |

`bank_fsm_t` (pkg line 88) is the ready-made **scoreboard record** shape for Visio —
list its fields in the Zone-C box: `state, row_open, next_cas, next_pre, next_act,
next_ref, can_cas, can_pre, can_act, can_ref, ref_pending` (+ add `lock_row,
demand_count, oldest_miss_age, age[lane]` for the new logic).

---

## F. Visio drawing tips

1. **Three containers = the abstraction bands:** Zone C "REGISTERED (FF)", Zone D
   "COMBINATIONAL", Zone E "ARBITER". Matches `sched_gate_hw.excalidraw`.
2. **One line = one net.** Label the **width** on the wire (e.g. `/32`, `/N_BANKS`).
   Bundle same-source buses into one fat line + a breakout near the destination.
3. **Feedback bus = its own colour** (orange). It is the only thing that closes the loop
   C→D→E→C; keep it visually separate so the "gate = feedback" story reads.
4. **Reads vs writes = two planes** through Zones B/D, merging at `cand_gen`.
5. **Gate insets on page 2**, one shape per D.1–D.5, hyperlinked from the buffer-level
   block on page 1.
6. **Trace against** `sched_gate_hw.excalidraw` (datapath + servo) and
   `bank_fsm.excalidraw` (behaviour) so the Visio sheet stays consistent with the model.

---

## G. Consistency

- Blocks = `rmc/rtl/mc_core/*.sv`; ports = `RMC_IO_Map.md §19` + `scheduler.sv` top +
  `bank_fsm_t`. Widths = `rmc_pkg.sv` (frozen).
- Behaviour = golden model `tools/sched_model/sched_test.js`.
- pkg **frozen**; `N_BANKS=32` / `N_RD=64` are intent (RTL phase). No RTL this phase.
