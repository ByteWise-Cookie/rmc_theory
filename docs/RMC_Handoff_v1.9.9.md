# RMC — Reconfigurable DDR5 Memory Controller
## Session Handoff Document — v1.9.9
### Complete architecture, all locked decisions, all block definitions

---

## 0.0 Changes Since v1.9.8

v1.9.9 supersedes v1.9.8 (frozen snapshot). Scheduler / MC-core buffering path only;
CIF, AMU, maintenance engine, DFI boundary unchanged. Authoritative detail: the scheduler
doc set (`scheduler_queue_arch.md`, `short_notes/scheduler_deep.md`, `scheduler_bank_fsm.md`,
`scheduler_staged_logic.md`, `scheduler_adaptive_batching.md`) and the golden model
`tools/sched_model/sched_test.js`. Sections below carry a **[v1.9.9]** tag where revised.

1. **Residency split** — TCAM is a short admission/classify station; requests evict into
   per-bank in-flight FIFOs. TCAM not removed, residency shortened. (§6, §8)
2. **RAW = pause, not bypass** — younger read to a pending write's address held at
   admission until the write drains; RAW Bypass Manager forward/merge path superseded.
   (§7, §11)
3. **Per-bank in-flight queues** — 16 FIFOs, head-only active, one ready-bit/class to the
   arbiter (relocated watermark = queue depth counters). (§8, §9)
4. **`status` relocated** — command-progress into the queue entry; occupancy → queue
   depth counters. (§7)
5. **Weight arbiter** replaces pure-SJF Stage 3: `K·control + age + servo_mod(ACT)` with a
   never-idle-DQ guardrail. (§8 Stage 3)
6. **Adaptive batching** supersedes the fixed Bank Partition RD/WR scheme. (§13)
7. **Golden model** is the cycle-accurate RTL reference, DDR5-4800B timing; queue-arch
   opt-gated, 0 violations / ±2pt DQ-busy vs window. (§18, §22)
8. **Deferred sweep** — queue depth, ready-bank count, R/W org, `K`, control weights,
   `AGE_MAX`, servo pools. (§22)

---

## 0. How to Use This Document

This is the single source of truth for continuing the RMC project in a new session.
Read sections 0–3 first (identity, decisions, interfaces, block list).
Then load specific sections as needed.
All widths are compile-time parameters — no hardcoded values anywhere.

**Current version:** v1.9.8
**RTL status:** architecture complete, skeleton not started
**Open items:** OQ-19b (ch interleave granularity — needs Python script)

---

## 1. Project Identity

| Item | Value |
|---|---|
| Project | Reconfigurable Memory Controller (RMC) — DDR5 capstone |
| Standard | JEDEC JESD79-5 (DDR5), DFI 5.2, AXI4 |
| Target | 4GB, single-channel, single-rank (anchor config) |
| Future ceiling | 46b address, 8ch, 8rank, 64Gb×3DS-8H = 64TB |
| RTL style | SystemVerilog, fully parameterized, no hardcoded widths |

---

## 2. Parameter Definitions

All bit-widths expressed as compile-time parameters:

| Parameter | Meaning |
|---|---|
| `GC_WIDTH` | Global cycle counter width |
| `ADDR_WIDTH` | Byte address width |
| `AXI_ID_WIDTH` | AXI transaction ID width |
| `DATA_WIDTH` | Data bus width (payload) |
| `STRB_WIDTH` | Byte strobe width = DATA_WIDTH/8 |
| `CH_BITS` | Channel select bits |
| `RANK_BITS` | Rank select bits |
| `BG_BITS` | Bank group bits |
| `BANK_BITS` | Bank bits |
| `ROW_BITS` | Row address bits |
| `COL_BITS` | Column address bits |
| `N_RANKS` | Number of ranks |
| `N_BG` | Number of bank groups = 2^BG_BITS |
| `N_BANKS` | Banks per rank = N_BG × 2^BANK_BITS |
| `N_WR_ENTRIES` | Write buffer depth (2–3× N_RD_ENTRIES) |
| `N_RD_ENTRIES` | Read buffer depth |
| `WR_BUF_DEPTH` | Write data buffer depth |
| `STATUS_WIDTH` | Request status field width (2b min) |
| `TIMING_WIDTH` | Timing parameter register width |
| `PARAM_ID_WIDTH` | Timing param address bits |
| `FAW_DEPTH` | Four-activate window depth (= 4, JEDEC fixed) |
| `FIFO_DEPTH` | Async FIFO depth = initial credit count (default 16) |

---

## 3. Locked Architecture Decisions

| Decision | Value | Rationale |
|---|---|---|
| BL | BL16 only | AXI 64B-aligned INCR = one BL16 burst on 32b subchannel |
| AXI burst type | INCR only | WRAP/FIXED not useful for DRAM |
| AXI data width | 64-bit | Sufficient for target |
| Narrow/unaligned | Not supported | Too complex, low benefit |
| Exclusive access | Not supported | Out of scope |
| QoS | Not supported | Not justified |
| N_WR_ENTRIES | 64 (v1), 96 (v2) | 2–3× N_RD_ENTRIES |
| N_RD_ENTRIES | 32 | Lower latency priority |
| CDC crossing | Single async FIFO at AXI↔MC boundary only | One verification target |
| Intra-MC interfaces | Valid-credit | No combinational ready, better timing closure |
| AXI interfaces | Valid-ready | AXI4 spec mandated |
| Resp FIFO→CIF | Valid-only, MC self-throttles | No ready from CIF |
| Scheduler | 5-stage pipeline, TCAM-assisted, SJF | Industry standard pattern |
| TCAM split | WR_TCAM (full addr) + RD_TCAM (BG/bank ternary) | Different search semantics |
| Page policy | Open default, closed/adaptive configurable | Open best for sequential |
| Maintenance Engine | Model A — peer block to Scheduler | Writes into FSM tables, never issues CAS |
| Timing go/no-go | Registered can_* flags, timestamps stored | No subtractor in scheduling critical path |
| Bank pipelining | ACT→diff BG→ACT→CAS interleave | tRRD_S < tRRD_L |
| Starvation | Staggered: age >= THR + entry_idx | At most one starved miss fires per cycle |
| WR buffer larger | N_WR = 2–3× N_RD | Better RD latency, same bandwidth |
| RAW hit valid | wr_age <= rd_age (write same cycle or earlier) | Prevents stale data forwarding |
| TCAM valid gating | status_reg[i].valid gates TCAM match[i] | Power saving, single source of truth |
| RD/WR partition | Banks split into RD half / WR half, rotate WINDOW_SIZE | Eliminates tRTW/tWTR within window |
| Speculative ACT | NOP-cycle only, TCAM-confirmed, bank+1 same row | Zero mispredict path |
| Opportunity REFsb | NOP-cycle, idle bank, most overdue | Zero traffic disruption |
| ME sub-FSMs | 6 total (Init, Refresh, ZQcal, RFM, PwrMgmt, MR_Poll) | Init FSM moved into ME |
| DFI mux | Inside ME, init_done one-way latch | Scheduler inherits DFI after boot |
| AMU | Replaces Address Translator in CIF | XOR hash + split-field extract, setup-time configurable |

---

## 4. Interface Protocol Summary

| Interface | Protocol | Notes |
|---|---|---|
| AXI4 ports | Valid-ready | Spec mandated |
| Async REQ FIFO write (CIF side) | Credit-based push | N credits = FIFO_DEPTH, no combinational wr_full |
| Async REQ FIFO read (MC side) | Valid-credit receive | rd_valid registered, credit_return after consume |
| Async RESP FIFO write (MC side) | Credit-based push | gate_resp_fifo_avail guards sends |
| Async RESP FIFO read (CIF side) | Valid-credit receive | rd_valid registered, credit_return after consume |
| Credit return REQ (MC→CIF) | Registered 1b sync | Crosses CDC safely |
| Credit return RESP (CIF→MC) | Registered 1b sync | Crosses CDC safely |
| All intra-MC paths | Valid-credit | No combinational back-pressure |
| DFI 5.2 | DFI protocol | Spec mandated |
| PHY→MC rddata | Valid-only | No back-pressure on read return |

---

## 5. Complete Block List

### CIF Domain (AXI clock)
1. **AXI Write Port** — valid-ready AXI4 slave
2. **AXI Read Port** — valid-ready AXI4 slave
3. **AMU** (Address Map Unit) — replaces Address Translator; XOR hash + split-field extract; setup-time configurable via CSR
4. **Burst Splitter** — Stage 1: row boundary check; Stage 2: BL16 alignment
5. **ROB** — {AXID, seqnum} composite tag; per-AXID HEAD pointer
6. **Merge Logic** — fragment reassembly
7. **Async REQ FIFO** — credit-based push (CIF side), valid-credit read (MC side); FIFO_DEPTH=16
8. **Async RESP FIFO** — credit-based push (MC side), valid-credit read (CIF side); FIFO_DEPTH=16

### MC Core (MC clock, all intra-MC = valid-credit)
9. **Write Data Buffer** — SRAM, index-addressed (not FIFO), WR_BUF_DEPTH entries
10. **WR_TCAM** — full address search {BG,bank,row,col}; N_WR_ENTRIES; no valid/ts in entry; gated by WR_status.valid
11. **RD_TCAM** — ternary search {BG,bank}; N_RD_ENTRIES; row/col carried not matched; gated by RD_status.valid
12. **WR Status Reg** — fields: valid, status, age; owner: WR Watermark Mgr; scheduler READ ONLY
13. **RD Status Reg** — fields: valid, status, age, merge_pending, wdb_entry_idx; owner: RD Watermark Mgr; scheduler READ ONLY
14. **WR Watermark Buffer Manager** — owns WR_TCAM + WR_status_reg; manages alloc/retire/watermarks
15. **RD Watermark Buffer Manager** — owns RD_TCAM + RD_status_reg; manages alloc/retire
16. **RAW Bypass Manager** — Stage A: WR_TCAM exact match; Stage B: mask coverage; hit valid iff wr_age <= rd_age
17. **Merge Unit** — 64×2:1 mux per byte; WDB + DRAM at return time; combinational
18. **Hold-Forward 2-deep** — src0=RAW bypass, src1=DRAM return; 3rd collision impossible by construction
19. **Bank Activity Counter Table** — [N_RANKS][16]: count, dirty; used by ME for REFsb targeting and PD entry
20. **Global Cycle Counter** — GC_WIDTH free-running; resets only on SOFT_RESET
21. **timing_reg_file** — param_id → nCK value; multi-port read; CSR write only; cmd→timing_update_vector
22. **Scheduler** — 5-stage pipeline (see §8)
23. **Bank Partition Controller** — partition_reg, window_ctr, rd/wr_partition_mask; owned by Scheduler
24. **Per-Bank FSM Table** — [N_RANKS × 16] rows (see §9A)
25. **Per-Rank FSM Table** — [N_RANKS] rows (see §9B)
26. **Global Timing Table** — 1 instance (see §9C)
27. **Maintenance Engine** — 6 sub-FSMs + DFI mux (see §10)
28. **Write Data Path** — WL align, CRC, DFI write timing
29. **Read Data Path** — latency counter, capture FIFO, ECC/CRC, MRR sideband output
30. **Error Handler** — scheduler_error + dfi_alert_n monitoring
31. **Config Registers** — CSR via AXI4-Lite (see §13)

### DFI / PHY
32. **DDR PHY** — DFI 5.2
33. **DDR5 DRAM**

---

## 6. TCAM Split

**[v1.9.9] Residency.** Both TCAMs are now **short-residency admission/classify stations**,
not lifetime homes. An entry is searched/classified (and RAW-compared, §11) on admission,
then **evicted into its per-bank in-flight FIFO** (§9E), freeing the slot. The search keys,
fields, and valid-gating below are unchanged; only the dwell time drops (burst+classify
window, not the full ~118 tCK latency window). The read path still owns RD_TCAM as its
classify engine — TCAM is not removed.

### WR_TCAM (N_WR_ENTRIES entries)
```
purpose:    RAW hazard detection — full address exact match
search key: {BG, bank, row, col}
entry fields:
  bg           [BG_BITS]
  bank         [BANK_BITS]
  row          [ROW_BITS]
  col          [COL_BITS]
  req_type     1b = WR
  axi_id       [AXI_ID_WIDTH]
  entry_idx    [$clog2(N_WR_ENTRIES)]   → WR status reg
  data_buf_idx [$clog2(WR_BUF_DEPTH)]  optional → Write Data Buffer

valid gating:  match[i] AND wr_status_reg[i].valid
multi-hit:     winner = argmax(age[i]) via status reg lookup
cell count:    N_WR_ENTRIES × 32b × 12T = 24,576T baseline
```

### RD_TCAM (N_RD_ENTRIES entries)
```
purpose:    Scheduler Stage 1 bank pre-filter
search key: {BG, bank}  ternary, don't-care on row/col
entry fields:
  bg           [BG_BITS]
  bank         [BANK_BITS]
  row          [ROW_BITS]   carried, not matched
  col          [COL_BITS]   carried, not matched
  req_type     1b = RD
  axi_id       [AXI_ID_WIDTH]
  entry_idx    [$clog2(N_RD_ENTRIES)]   → RD status reg

valid gating:  match[i] AND rd_status_reg[i].valid
multi-hit:     winner = argmax(age[i]) via status reg lookup
cell count:    N_RD_ENTRIES × 5b × 12T = 1,920T baseline
```

### RAW BCAM (WR_TCAM used in Stage A)
```
search primitive: XOR-based exact match (BCAM cells, ~6T/bit)
cell count:       N_WR_ENTRIES × 32b × 6T = 12,288T baseline
total TCAM+CAM:   38,784T ≈ 6,464 SRAM bits equivalent
```

---

## 7. Status Register Fields

### WR Status Reg
```
valid          1b
status         STATUS_WIDTH    00=PENDING 01=ISSUED 10=DONE 11=ERROR
age            GC_WIDTH        allocation timestamp (gc at alloc)
```

### RD Status Reg
```
valid          1b
status         STATUS_WIDTH    00=PENDING 01=ISSUED 10=DONE 11=ERROR
age            GC_WIDTH        allocation timestamp
merge_pending  1b              RAW partial overlap: DRAM fetch pending
wdb_entry_idx  $clog2(WR_BUF_DEPTH)   valid when merge_pending=1
```

**Key properties:**
- `valid` = single source of truth for occupancy; gates TCAM match output
- `age` = used for multi-hit newest-wins, starvation check, SJF cost
- Owner: respective watermark manager (R/W). Scheduler: READ ONLY.

**[v1.9.9] Relocation.** The `status` field is split by role. **Command-progress**
(`NEED_PRE/ACT/CAS/DONE`, the old `PENDING/ISSUED/DONE`) moves into the **per-bank queue
entry** (§9E), where it self-advances as commands issue. **Occupancy/valid** stays with the
allocator but is now counted as **per-bank queue depth** — this is where the watermark
logic (inv-LSB priority encoder + `wr_count` popcount) relocates, counting queue slots
instead of TCAM rows and feeding admission backpressure. `merge_pending`/`wdb_entry_idx`
are retired with the RAW bypass (§11): the pause model has no partial-merge state.

---

## 8. Scheduler Pipeline (5 Stages)

### Stage 0 — Maintenance Override
```
priority: ref_urgent > ref_due > rfm_req > zq_due
if any asserted → bypass Stages 1–3 → Stage 4 directly
REFsb target: argmin(bank_act_count[rank][*])
REFab: gate_rfc[rank]=1, all banks blocked tRFC1
REFsb: gate_rfcpb[rank][bank]=1, one bank blocked tRFCsb
```

### Stage 1 — TCAM Search / Admission [v1.9.9]
```
search RD_TCAM + WR_TCAM simultaneously (multi-port)
outputs per bank: hit, row, col, req_type, entry_idx, axi_id
valid gating: hit[i] AND status_reg[i].valid
multi-hit same bank: winner = argmax(age[i])

[v1.9.9] this stage now also ADMITS + CLASSIFIES + EVICTS:
  classify: {bg,bank}→bank hit ; row vs open_row → NEED_CAS/NEED_PRE ; empty → NEED_ACT
  RAW: full-addr compare vs pending writes → set entry.blocked (§11), hold (no evict)
  evict: classified + RAW-clear + bank queue has room → move entry to per-bank FIFO (§9E)
         else stay in TCAM → backpressure (TCAM-full stalls admission)
candidate set feeding Stage 2/3 = HEADS of the 16 per-bank queues (one per bank),
  not a flat TCAM window. legality gates + Stage-4 writeback are identical either way.
```

### Stage 2 — can_* Gate Check + SJF Cost Classification
```
reads only registered can_* flags — no subtractor in critical path

per-bank gates:   can_cas, can_pre, can_act, can_ref
global gates:     can_act_any, can_cas_any, can_faw
per-BG gates:     can_act_bg[N_BG], can_cas_bg[N_BG], can_wtr_bg[N_BG]
per-rank gates:   can_act_rank[N_RANKS], can_cas_rank[N_RANKS]
rank blocking:    gate_rfc[rank], gate_zq[rank]
partition gate:   rd/wr_partition_mask from Bank Partition Ctrl

SJF cost per bank:
  ACTIVE + row hit      → HIT_SET,  cost = 0
  ACTIVATING            → PENDING,  cost = next_cas - gc
  IDLE                  → MISS_SET, cost = tRCD
  ACTIVE + row miss     → MISS_SET, cost = (next_pre - gc) + tRP + tRCD
  PRECHARGING           → MISS_SET, cost = (next_act - gc) + tRCD

speculative ACT detect (NOP cycle only):
  ACTIVE bank approaching col boundary (COL_MAX - cur_col <= BL_BYTES)
  pred = {same_rank, same_bg, bank+1, same_row}
  gates: RD_TCAM hit AND row match AND bank_act_count>0
         AND state==IDLE AND can_act AND can_faw
```

### Stage 3 — Weight-Arbiter Winner Selection [v1.9.9, replaces pure SJF]
```
winner = argmax over legal candidates of:
  weight(lane) = K·control[lane] + age[lane] + (lane==ACT ? servo_mod : 0)
    control : CAS > ACT > PRE   (SJF baseline, fixed)
    age     : +1 per waiting cycle, 0 on win  (breaks real starvation)
    servo_mod (DQ-occupancy balance):
       ready_cas = popcount(can_cas) ; dq_free_in = dqFree - gc
       pool thin & DQ freeing → +boost ACT ; pool deep / tFAW tight → −damp ACT
  GUARDRAIL: dq_free_in==0 & ready_cas>=1  ⇒ CAS wins absolutely (never idle DQ)
  ties → oldest age → BG-rotate (bg != last_act_bg : tCCD_S 8 < tCCD_L 12)

row-lock (per bank, at queue head):
  hold while demand[bank][open_row] > 0 ; release on drain OR oldest_miss_age >= AGE_MAX
  two-sided cap: when locked & aged out, can_cas ALSO deasserts so the burst finishes,
  tRTP/tWR clears, and the starved miss's PRE force-breaks in

RD/WR direction: adaptive batching (§13), not fixed watermark crossings
  flip batch on gateLoss >= BL2 (skipped opposite CAS on free DQ) OR stall >= tRAS+tRP

NOP cycle priority (winner_valid==0):
  1. Opportunity REFsb (correctness first)
  2. Speculative prefetch ACT
  3. opposite-batch drain
  4. True NOP

K, control values, AGE_MAX, servo POOL_LOW/HIGH/LOOKAHEAD = deferred sweep (§22).
Golden model currently runs the busy-first + oldest-tie baseline of this arbiter.
```

*Superseded (v1.9.8 pure SJF):* priority `Stage-0 > STARVED_MISS (age ≥
STARVATION_THR + entry_idx, staggered) > HIT_SET (cost 0, prefer bg ≠ last_act_bg) >
MISS_SET (lowest remaining_cost)`; RD/WR mode by watermark crossings
(`wr_count ≥ WR_HIGH_WM(16)` / `≤ WR_LOW_WM(4)`, `AGE_THR2(256)` force-flip).
`RD_STARVATION_THR=12480`, `WR_STARVATION_THR=37440` remain the hard backstops; the
weighted `age` term is the primary fairness mechanism now.

### Stage 4 — Command Emission + Writebacks
```
DFI output via ME DFI mux (init_done gates Init FSM vs Scheduler)

Per-bank FSM writebacks:
  ACT:    state→ACTIVATING, next_cas=gc+tRCD, next_pre=gc+tRAS, row_open=req.row
  CAS_RD: state→ACTIVE, next_pre=gc+tRTP
  CAS_WR: state→ACTIVE, next_pre=gc+CWL+BL/2+tWR
  PRE:    state→PRECHARGING, next_act=gc+tRP
  REFsb:  state→REFRESHING_SB, next_ref=gc+tRFCsb, last_refsb_gc updated

Global timing writebacks:
  ACT:    next_act_bg[bg]=gc+tRRD_L, next_act_any=gc+tRRD_S
          next_act_rank[r]=gc+tRRD_L, faw_window shift in gc
          last_act_bg[bg]=gc
  CAS_RD: next_cas_bg[bg]=gc+tCCD_L, next_cas_any=gc+tCCD_S
          next_cas_rank[r]=gc+tCCD_L, next_wr_rd=gc+tRTW
  CAS_WR: next_cas_bg[bg]=gc+tCCD_L_WR, next_cas_any=gc+tCCD_S
          next_cas_rank[r]=gc+tCCD_L_WR, next_rd_wr=gc+WL+BL/2+tWTR_L

Status: entry_idx → ISSUED
sched_ack → Maintenance Engine
raa_inc_en → Per-Rank FSM (RAA++)

can_* update (every cycle, background, not critical path):
  can_act <= (gc - next_act)[GC_WIDTH-1] == 0
  can_pre <= (gc - next_pre)[GC_WIDTH-1] == 0
  can_cas <= (gc - next_cas)[GC_WIDTH-1] == 0
  can_ref <= (gc - next_ref)[GC_WIDTH-1] == 0
```

---

## 9. FSM State Tables

### 9A. Per-Bank FSM Table — [N_RANKS × 16]

| Field | Width | Description |
|---|---|---|
| state | BANK_STATE_WIDTH | Bank FSM state |
| row_open | ROW_BITS | Currently open row |
| next_cas | GC_WIDTH | Deadline: ACT→CAS |
| next_pre | GC_WIDTH | Deadline: CAS→PRE |
| next_act | GC_WIDTH | Deadline: PRE→ACT |
| next_ref | GC_WIDTH | Deadline: REFsb recovery |
| can_cas | 1b | Registered flag |
| can_pre | 1b | Registered flag |
| can_act | 1b | Registered flag |
| can_ref | 1b | Registered flag |
| ref_pending | 1b | Set by Maintenance Engine (no TCAM equivalent for REF) |

**States:**

| Encoding | State |
|---|---|
| 000 | IDLE |
| 001 | ACTIVATING |
| 010 | ACTIVE |
| 011 | PRECHARGING |
| 100 | REFRESHING_SB |
| 101 | RFM_ACTIVE |
| 110 | POWER_DOWN |
| 111 | SELF_REFRESH |

**Removed fields** (replaced by TCAM output):
`open_pending`, `pre_pending`, `act_pending`, `wr_pending`, `rd_pending`

**Key transitions:**

| From | To | Trigger | Writeback |
|---|---|---|---|
| IDLE | ACTIVATING | ACT issued | next_cas=gc+tRCD, next_pre=gc+tRAS |
| ACTIVATING | ACTIVE | can_cas==1 | row_open=req.row |
| ACTIVE | PRECHARGING | row miss, no hits | next_act=gc+tRP |
| ACTIVE | ACTIVE | CAS row hit | next_pre updated |
| PRECHARGING | IDLE | can_act==1 | — |
| IDLE | REFRESHING_SB | ref_pending AND can_ref | next_ref=gc+tRFCsb |
| REFRESHING_SB | IDLE | can_ref==1 | ref_pending=0 |
| ACTIVE | RFM_ACTIVE | raa[b]<=RAAIMT | — |
| RFM_ACTIVE | IDLE | tRFM elapsed | raa[b] reset |

---

### 9B. Per-Rank FSM Table — [N_RANKS]

| Field | Width | Description |
|---|---|---|
| state | RANK_STATE_WIDTH | Rank FSM state |
| next_rfc | GC_WIDTH | REFab recovery deadline |
| next_zq | GC_WIDTH | ZQcal recovery deadline |
| next_xp | GC_WIDTH | PDX recovery deadline |
| next_xs | GC_WIDTH | SRX recovery deadline |
| next_trefi | GC_WIDTH | Next tREFI expiry |
| next_zqcs | GC_WIDTH | Next ZQcal deadline |
| can_rfc | 1b | Registered flag |
| can_zq | 1b | Registered flag |
| can_xp | 1b | Registered flag |
| can_xs | 1b | Registered flag |
| gate_rfc | 1b | Blocks ALL per-bank cmds this rank |
| gate_zq | 1b | Blocks ALL per-bank cmds this rank |
| ref_credits | CREDIT_WIDTH | Leaky bucket (0..15) |
| raa[16] | RAA_WIDTH×16 | Per-bank RAA counters |
| last_TUF | 1b | Last MR4 TUF bit read |
| next_poll_gc | GC_WIDTH | Next MRR poll deadline |
| mrr_data | 8b | Last MR4 response |
| last_refsb_gc[32] | GC_WIDTH×32 | Timestamp of last REFsb per bank |

**States:** NORMAL(000), REFab_ACTIVE(001), ZQCAL_ACTIVE(010), POWER_DOWN(011), SELF_REFRESH(100)

---

### 9C. Global Timing Table — [1 instance]

| Field | Width | Description |
|---|---|---|
| global_state | GLOBAL_STATE_WIDTH | INIT/NORMAL/SOFT_RESET/REF_STALL/ZQ_STALL |
| next_act_any | GC_WIDTH | tRRD_S from last ACT anywhere |
| next_cas_any | GC_WIDTH | tCCD_S from last CAS anywhere |
| next_rd_wr | GC_WIDTH | tWTR_S from last WR data-end |
| next_wr_rd | GC_WIDTH | tRTW from last RD |
| faw_window[FAW_DEPTH] | GC_WIDTH×FAW_DEPTH | Ring buffer of recent ACT timestamps |
| next_act_bg[N_BG] | GC_WIDTH×N_BG | tRRD_L per BG |
| next_cas_bg[N_BG] | GC_WIDTH×N_BG | tCCD_L/tCCD_L_WR per BG |
| next_wtr_bg[N_BG] | GC_WIDTH×N_BG | tWTR_L per BG |
| last_act_bg[N_BG] | GC_WIDTH×N_BG | gc at last ACT per BG |
| next_act_rank[N_RANKS] | GC_WIDTH×N_RANKS | tRRD within same rank |
| next_cas_rank[N_RANKS] | GC_WIDTH×N_RANKS | tCCD within same rank |
| can_act_any | 1b | Registered |
| can_cas_any | 1b | Registered |
| can_rd_wr | 1b | Registered |
| can_wr_rd | 1b | Registered |
| can_faw | 1b | Registered |
| can_act_bg[N_BG] | N_BG bits | Registered per BG |
| can_cas_bg[N_BG] | N_BG bits | Registered per BG |
| can_wtr_bg[N_BG] | N_BG bits | Registered per BG |
| can_act_rank[N_RANKS] | N_RANKS bits | Registered per rank |
| can_cas_rank[N_RANKS] | N_RANKS bits | Registered per rank |

---

### 9D. Bank Activity Counter Table — [N_RANKS × 16]

| Field | Width | Description |
|---|---|---|
| count | $clog2(BUF_DEPTH+1) | Outstanding requests to this bank |
| dirty | 1b | 1 = pending WR entry exists |

Updates: count++ on alloc, count-- on retire. dirty=1 on WR alloc, dirty=0 when last WR retires.

Usage: ME REFsb→argmin(count); PD entry→count==0 all banks; Scheduler S3→prefer high-count banks.

---

### 9E. Per-Bank In-Flight Queue — [N_RANKS × 16 FIFOs] [v1.9.9]

Holds requests after admission/classify (§6, §8 Stage 1). One FIFO per bank, arrival
order preserved (natural row-locality). Only the **head** is active in the command pipe.

| Field | Width | Description |
|---|---|---|
| valid | 1b | slot occupied |
| rw | 1b | R / W (unified queue + tag; split-queue variant is a sweep option) |
| seqnum | [SEQ_BITS] | ROB program order (RAW / retirement) |
| bg, bank | [BG_BITS],[BANK_BITS] | target bank (redundant with FIFO index, carried for emit) |
| row, col | [ROW_BITS],[COL_BITS] | target address |
| state | 2b | NEED_PRE / NEED_ACT / NEED_CAS / DONE (command-progress, relocated from status) |
| blocked | 1b | RAW-held (read waiting on a write drain, §11); set at admission |

```
depth per bank : ~4–8 (deferred sweep §22) ; total in-flight = N_BANKS × depth
head-only      : head asserts one ready-bit per class → can_pre/act/cas[16] to arbiter
                 timers (next_cas/pre/act) are PER-BANK scoreboard props, NOT per-entry —
                 the head reads them; deeper entries just wait
advance        : head self-advances state locally as ACT/PRE/CAS issue (thread model);
                 on CAS done → retire, pop, next entry becomes head next cycle
occupancy      : depth counter + full flag = relocated watermark → admission backpressure
owner          : allocator/watermark manager (R/W). Scheduler + arbiter: READ head only.
```

---

## 10. Maintenance Engine (6 Sub-FSMs)

Peer block to Scheduler. Writes into FSM tables. Never issues CAS.
Internal priority: `ref_urgent > ref_due > rfm_req > zq_due`

### DFI Output Mux (inside ME)
```
init_done = 0  →  Init FSM drives all DFI outputs   (boot)
init_done = 1  →  Scheduler Stage 4 drives DFI       (normal)
init_done: one-way latch, never de-asserted
MRR: MR_Poll FSM → Stage 0 bypass → Stage 4 → DFI (no 3rd mux input)
```

### Sub-FSM 1: Init FSM (16 states)
```
IDLE → ASSERT_RESET → CS_PRE_DEASSERT → CS_POST_DEASSERT → ODT_SETTLE →
NOP_BURST → WAIT_XPR → MPC_DLL_DIVIDER → MPC_DLL_RESET →
ZQCAL_START → WAIT_tZQCAL → ZQCAL_LATCH → WAIT_tZQLAT →
MRW_BURST → TRAINING → DONE

DONE: asserts init_done, releases Scheduler, hands DFI mux to Scheduler
```

### Sub-FSM 2: Refresh FSM (6 states)
```
IDLE → REF_DUE → WAIT_BANKS_IDLE → ISSUE_REF → WAIT_tRFC → DONE → IDLE

leaky-bucket: credits++ per tREFI, credits-- per REF issued
ref_urgent:   credits >= 8 → Stage 0 override
ref_due:      gc >= next_trefi → normal trigger

REFab: gate_rfc[rank]=1, all banks blocked, tRFC1 recovery
REFsb: gate_rfcpb[rank][bank]=1, one bank blocked, tRFCsb recovery

REFsb targeting (option B):
  normal:   argmin(bank_act_count[rank][*])
  watchdog: if gc - last_refsb_gc[r][b] > tREFI×32 → force that bank

Opportunity REFsb (NOP cycle):
  winner_valid==0 AND can_ref[b]==1 AND bank_act_count==0
  AND argmax(gc - last_refsb_gc) → fire REFsb, zero traffic cost

FGR-2x: tRFC2, refresh rate doubled, credit threshold halved
FGR-4x: tRFC4, refresh rate quadrupled, credit threshold quartered
Temperature: MR4 TUF=1 (>85°C) → tREFI_adjusted = tREFI/2
```

### Sub-FSM 3: ZQcal FSM (7 states, per-rank instances)
```
IDLE → WAIT_IDLE → ISSUE_START → WAIT_tZQCAL →
ISSUE_LATCH → WAIT_tZQLAT → DONE → IDLE

gate_zq[rank]=1 during entire sequence (all banks blocked)
trigger: gc >= next_zqcs
interval: tZQCS_interval CSR, default 128ms converted to cycles
```

### Sub-FSM 4: RFM FSM (6 states)
```
IDLE → MONITOR_RAA → RFM_REQUEST → WAIT_ISSUE → WAIT_tRFM → UPDATE_RAA → MONITOR_RAA

raa[rank][bank]: +1 per ACT to that bank, -RAADec per REF
trigger: raa[b] <= RAAIMT
priority: below REF, above ZQcal
```

### Sub-FSM 5: Power Management FSM (10 states)
```
PD branch:
  NORMAL → PD_ENTRY_CHECK → PRECHARGE_PD → ACTIVE_PD → PDX_WAIT → NORMAL
  entry: all bank_act_count[rank][*]==0 AND pd_en AND no pending maintenance

SR branch:
  NORMAL → SR_ENTRY → WAIT_tCKSRE → SELF_REFRESHING →
  SR_EXIT → WAIT_tXS_tDLLK → NORMAL
```

### Sub-FSM 6: MR_Poll FSM (6 states)
```
IDLE → WAIT_INTERVAL → REQUEST_MRR → WAIT_RDDATA → PARSE_TUF → UPDATE_TREFI → IDLE

trigger:  gc >= next_poll_gc  (interval: MRR_POLL_INTERVAL CSR = 32×tREFI)
command:  MRR to MR4, via Stage 0 bypass
response: Read Data Path sideband (mrr_data_valid, mrr_data, mrr_rank)
          NOT through resp FIFO

TUF=0: tREFI_adjusted = tREFI
TUF=1: tREFI_adjusted = tREFI/2  (>85°C)
UPDATE_TREFI: Refresh FSM next_trefi ← gc + tREFI_adjusted
```

---

## 11. RAW Hazard Handling — Pause [v1.9.9] (was RAW Bypass Manager)

**[v1.9.9] RAW is now a pause, not a bypass** (mentor review). The forward/partial-merge
scheme below is **superseded**.

```
Detect at admission (§8 Stage 1): the read's full-addr search hits a pending, older,
  not-yet-emitted write to the same address (seqnum gives program order).
On hit:  set entry.blocked=1 (pin bit, now on the read side) — do NOT evict to bank queue.
Hold:    keep the read in TCAM until the blocking write retires; then clear blocked, evict.
Result:  the read proceeds through the normal DRAM path after the write drains.
Cost:    the rare RAW read eats the write's latency serially — no forward, no reorder.
Effect:  per-bank queues stay CAM-free (RAW never re-checked downstream);
         raw_hit gates EVICTION, not a bypass mux;
         only one response source remains (DRAM) → the 2nd hold slot + Merge Unit + the
         merge_pending/wdb_entry_idx status fields (§7) are retired.
Proxy in the golden model: {rank,bank,row} (no column) — conservative.
```

*Superseded (v1.9.8 bypass model, retained for provenance):*

### Timing
```
cycle 0: new RD arrives → WR_TCAM searched simultaneously (combinational, multi-port)
         zero penalty on miss path (scheduler receives RD immediately)
cycle 1: mask coverage check + case decision
cycle 2: data on resp FIFO (full hit path)
```

### Hit Cases
```
FULL HIT (wdb_mask == all-1):
  forward WDB data directly → resp FIFO, no DRAM

PARTIAL OVERLAP (gaps in coverage):
  issue RD to scheduler immediately (NO STALL)
  set merge_pending=1, wdb_entry_idx in RD status reg
  DRAM fetch runs in background
  at DRAM return: Merge Unit → merged[b] = wdb[b] if mask[b] else dram[b]
  cost = normal DRAM latency (zero penalty vs pure miss)

OVERSHOOT (write covers more than read needs):
  mask to read's required bytes → forward

MISS or write arrived after read (wr_age > rd_age):
  pass RD to scheduler normally → zero added latency
```

### Merge Unit
```
64×2:1 mux array, combinational, one cycle
merged[byte] = wdb_data[byte] if wdb_mask[byte] else dram_data[byte]
```

### 2-Deep Hold-Forward
```
src0 = RAW bypass path
src1 = DRAM return (Read Data Path)
3rd collision impossible: each source rate-limited to 1 response/cycle
```

---

## 12. AMU — Address Map Unit

Replaces Address Translator in CIF. Setup-time configurable, locked before init_done.

### Pipeline (combinational)
```
Stage 1: per-field XOR hash (opt-in)
  hashed_addr[field] = raw_addr XOR (raw_addr >> xor_shift[field])

Stage 2: field extract from hashed_addr
  supports split fields (non-contiguous bit ranges)
```

### Field Descriptor (6 fields: ch, rank, bg, bank, row, col)
| Sub-field | Width | Description |
|---|---|---|
| src_msb_a | 5b | Upper segment MSB |
| src_lsb_a | 5b | Upper segment LSB |
| src_msb_b | 5b | Lower segment MSB (split only) |
| src_lsb_b | 5b | Lower segment LSB (split only) |
| split_en | 1b | 1=use both segments |
| hash_en | 1b | Per-field XOR hash enable |
| xor_shift | 5b | Per-field shift amount |

### Field Assignment (locked)
| Field | hash_en | Rationale |
|---|---|---|
| rank | 1 (MSB position) | Spread across ranks; rank switch penalty → push to MSB |
| ch | 1 | Spread across channels; same locality impact as rank |
| bg | 0 | Preserve locality; row hit rate critical |
| bank | 0 | Preserve locality |
| row | 0 | Preserve locality |
| col | 0 | Preserve locality; split_en used for ch interleave |

### Open Item (OQ-19b)
Ch interleave granularity TBD. Options: 4KB (A[12]), 8KB (A[13]), 16KB (A[14]).
Needs Python script + traffic trace analysis. CSR configurable at runtime.

---

## 13. Bank Partition RD/WR Scheme — Superseded by Adaptive Batching [v1.9.9]

**[v1.9.9] Superseded.** Turnaround is now amortized by **adaptive R/W batching** at the
arbiter, not by statically partitioning banks. The scheduler runs a batch direction and
flips it on accumulated **gate-loss** (a free DQ slot wasted skipping an opposite-direction
CAS, threshold `BL2`) or on **stall** (`≥ tRAS+tRP` with opposite work waiting). This pays
`tRTW`/`tWTR` once per batch, demand-driven, and adapts batch length to the live R/W mix.
Detail: `scheduler_adaptive_batching.md`, `scheduler_deep.md §5`. The fixed-window scheme
below is retained for provenance.

```
split N_BANKS into two halves:
  RD partition → serve reads only this window
  WR partition → serve writes only this window
rotate every WINDOW_SIZE cycles (CSR, default 2×tREFI)

no tRTW or tWTR within window (RD and WR never share a bank)
penalty at rotation boundary: max(tRTW, tWTR_L) once, amortized

partition state:
  partition_reg     1b
  window_ctr        GC_WIDTH
  rd_partition_mask N_BANKS
  wr_partition_mask N_BANKS

overrides:
  WR_HIGH_WM hit → expand WR partition temporarily
  RD starvation  → force starved RD bank into RD partition
  opportunity REFsb → unaffected, fires regardless of partition
```

---

## 14. Speculative Prefetch ACT

Fires on NOP cycles only (`winner_valid==0`). TCAM-confirmed — not blind prediction.

```
for each ACTIVE bank[r][bg][b]:
  col_remaining = COL_MAX - cur_col_being_served
  if col_remaining <= BL_BYTES:            ← page boundary imminent
    pred = {rank=r, bg=bg, bank=b+1, row=row_open[r][bg][b]}
    gates (ALL must pass):
      RD_TCAM hit for {bg, b+1}
      AND tcam_out[b+1].row == pred.row    ← same row confirmed
      AND bank_act_count[r][bg][b+1] > 0   ← real work exists
      AND state[r][bg][b+1] == IDLE
      AND can_act[r][bg][b+1] == 1
      AND can_faw == 1
    → emit speculative ACT to pred bank
    → tRCD elapses during NOP, real request arrives → row hit
```

bank_act_count dual use:
- count=0 → no speculate + closed page policy
- count 1–3 → speculate if boundary imminent + adaptive page
- count≥4 → speculate aggressively + open page

---

## 15. Scheduler Invariants (25 total)

```
1.  Row hit always beats row miss (unless starved)
2.  Max one ACT per cycle (faw_window enforces 4-ACT limit)
3.  Max one CAS per cycle
4.  REF/ZQ/RFM override Stages 1–3 via Stage 0
5.  Starved miss: at most one fires per cycle (stagger guarantee)
6.  RD never issues without gate_resp_fifo_avail
7.  WR never issues without valid data_buf_idx
8.  No cmd while gate_rfc[rank] or gate_zq[rank] asserted
9.  Consecutive ACTs prefer different BG (tRRD_S < tRRD_L)
10. CAS issued only when can_cas[b]==1
11. REFab: rank already idle, no bank-to-bank delay needed
12. REFsb: PRE required if target bank ACTIVE
13. SJF: lowest remaining_cost wins in MISS_SET
14. Stage 2 reads only registered can_* flags — no subtractor in critical path
15. WR_TCAM RAW hit valid only if wr_age <= rd_age
16. TCAM match suppressed when status_reg[i].valid==0 (power gating)
17. Speculative ACT fires ONLY on true NOP cycles (winner_valid==0)
18. Speculative ACT requires RD_TCAM confirmation (not blind)
19. Speculative ACT requires bank_act_count[next_bank] > 0
20. Speculative ACT subject to same can_faw gate as real ACT
21. Opportunity REFsb fires before speculative ACT on NOP cycles
22. last_refsb_gc updated on every REFsb regardless of trigger source
23. Watchdog overrides argmin if any bank overdue by tREFI×32
24. RD and WR never share same bank in same partition window
25. Partition rotation penalty (tRTW or tWTR_L) occurs once per window, amortized
```

---

## 16. Legal Check Matrix (Stage 2)

| Gate | Source | Constraint |
|---|---|---|
| can_cas[b] | Per-bank registered | tRCD elapsed since ACT |
| can_pre[b] | Per-bank registered | tRAS/tRTP/tWR elapsed |
| can_act[b] | Per-bank registered | tRP elapsed since PRE |
| can_ref[b] | Per-bank registered | tRFCsb elapsed |
| can_act_bg[bg] | Global registered | tRRD_L since last ACT in BG |
| can_act_any | Global registered | tRRD_S since last ACT anywhere |
| can_faw | Global registered | ≤4 ACTs in tFAW window |
| can_cas_bg[bg] | Global registered | tCCD_L/tCCD_L_WR |
| can_cas_any | Global registered | tCCD_S |
| can_rd_wr | Global registered | tWTR_S |
| can_wr_rd | Global registered | tRTW |
| can_act_rank[r] | Global registered | tRRD within same rank |
| can_cas_rank[r] | Global registered | tCCD within same rank |
| gate_rfc[r] | Per-rank | REFab in progress |
| gate_zq[r] | Per-rank | ZQcal in progress |
| gate_resp_fifo_avail | Resp FIFO | Free unreserved slot before RD issues |

---

## 17. Config Registers (Key)

| Register | Default | Description |
|---|---|---|
| WR_HIGH_WM | 16 | WR drain entry watermark |
| WR_LOW_WM | 4 | WR drain exit watermark |
| AGE_THR1 | 64 | Intra-class HOL bypass |
| AGE_THR2 | 256 | Cross-class mode flip |
| RD_STARVATION_THR | 12480 | RD miss forced service (9×tREFI) |
| WR_STARVATION_THR | 37440 | WR miss forced service (3× RD) |
| WINDOW_SIZE | 2×tREFI | RD/WR partition rotation window |
| PAGE_POLICY | 00=Open | 01=Closed, 10=Adaptive |
| REF_MODE | 00=REFab | 01=REFsb, 10=FGR-2x, 11=FGR-4x |
| MRR_POLL_INTERVAL | 32×tREFI | MR4 TUF polling interval |
| PD_IDLE_THRESHOLD | 64 cycles | Cycles idle before PD entry attempt |
| FIFO_DEPTH | 16 | Async FIFO depth = initial credit count |
| INIT_KICK | 0 | Trigger Init FSM |
| SOFT_RESET | 0 | Synchronous soft-reset all FSMs |

---

## 18. Pipeline Latency Reference

### Worked Example (@200MHz, tCK=5ns)
| Param | Value |
|---|---|
| CL / RL | 3 nCK |
| CWL / WL | 1 nCK |
| BL/2 | 8 cycles |
| tRCD | 4 nCK |
| tRP | 4 nCK |
| tRAS | 7 nCK |
| tCCD_L_WR | 32 nCK |
| tRFC1 | 39 nCK |

### Read Latency
| Path | Cycles |
|---|---|
| Row hit | RL + BL/2 = 11 |
| Row empty (IDLE→CAS) | tRCD + RL + BL/2 = 15 |
| Row miss (ACTIVE wrong row) | tRP + tRCD + RL + BL/2 = 19 |

### Full Round-Trip (worst case, row miss, no REF)
| Stage | Cycles |
|---|---|
| CIF pipeline | ~2 |
| REQ FIFO CDC | ~4 |
| RAW check | ~1 |
| Scheduler S1–S4 | ~4 |
| DRAM row miss | 19 |
| Read capture FIFO | 1 |
| RESP FIFO CDC | ~4 |
| ROB retirement | 1 |
| **Total** | **~37** |

ROB watermark: 37. REF stall timeout: 76 (Option A — let in-flight CAS complete).

---

## 19. Address Mapping (Baseline 32b, 4GB)

```
A[31:17] = Row   (ROW_BITS)
A[16:14] = BG    (BG_BITS=3, 8 bank groups)
A[13:12] = Bank  (BANK_BITS=2, 4 banks/BG)
A[11:2]  = Col   (COL_BITS=10)
A[1:0]   = Offset

Channel select = A[7] (128B interleave baseline)
BG/Bank bits fixed across all configs
JEDEC ceiling: 41b (8ch×8rank×64Gb). 46b with 3DS 8H.
AMU handles split-column and XOR hashing — see §12
```

### Multi-Config Profiles
| Config | Total | Addr | Ch | Rank | Row | Col |
|---|---|---|---|---|---|---|
| Desktop-S | 8GB | 33b | 0 | 0 | 16 | 10 |
| Desktop-D | 16GB | 34b | 1(A[7]) | 0 | 16 | 10 |
| Desktop-Q | 32GB | 35b | 1(A[7]) | 1(A[8]) | 16 | 10 |
| Workstation-D | 64GB | 36b | 1 | 1 | 17 | 10 |
| Enterprise-8C | 1TB | 40b | 3(A[9:7]) | 3 | 18 | 11 |
| JEDEC Max | 2TB | 41b | 3 | 3 | 18 | 11 |
| 3DS-Max | 64TB | 46b | 3 | 3+3(CID) | 18 | 11 |

---

## 20. FSM Count Summary

| FSM | States | Instances | Owner |
|---|---|---|---|
| Init FSM | 16 | 1 | ME sub-FSM 1 |
| Refresh FSM | 6 | 1 | ME sub-FSM 2 |
| ZQcal FSM | 7 | N_RANKS | ME sub-FSM 3 |
| RFM FSM | 6 | 1 | ME sub-FSM 4 |
| Power Mgmt FSM | 10 | 1 | ME sub-FSM 5 |
| MR_Poll FSM | 6 | 1 | ME sub-FSM 6 |
| Per-Bank FSM | 8 | 16×N_RANKS | Scheduler |
| Per-Rank FSM | 5 | N_RANKS | ME |
| Global FSM | 5 | 1 | Global |
| ~~Bank Partition FSM~~ (superseded v1.9.9, §13) | 2 | 1 | Scheduler |
| Write CRC FSM | 4 | 1 | Write Data Path |
| ECS FSM | 4 | 1 | Read Data Path |

**[v1.9.9]** New scheduler structures (not FSMs): 16 per-bank in-flight queues (§9E) +
their relocated watermark depth counters; the weight arbiter (§8 Stage 3). The per-bank
queues are FIFOs, not state machines — the head's command-progress lives in the entry's
2-bit `state`, driven by Stage 4.

---

## 21. Block Ownership

| Block | R/W Owner | Scheduler Access |
|---|---|---|
| WR Status Reg | WR Watermark Mgr | READ ONLY |
| RD Status Reg | RD Watermark Mgr | READ ONLY |
| WR_TCAM | WR Watermark Mgr | READ ONLY (search) |
| RD_TCAM | RD Watermark Mgr | READ ONLY (search) |
| Write Data Buffer | WR Watermark Mgr | READ ONLY (emit) |
| Per-Bank FSM Table | Scheduler S4 + ME | WRITE S4, READ S2 |
| Per-Rank FSM Table | ME | READ S0 |
| Global Timing Table | Scheduler S4 | READ S2 |
| Bank Activity Counter | WR/RD WM Mgrs | READ (ME, Power Mgmt) |
| timing_reg_file | CSR (init only) | READ ONLY |
| Global Cycle Counter | Free-running | READ all blocks |
| ~~Bank Partition Ctrl~~ (superseded v1.9.9) | Scheduler | — |
| Per-Bank In-Flight Queues (§9E) [v1.9.9] | R/D Watermark Mgr (alloc/evict/retire) | READ head only |
| Queue depth counters / relocated watermark [v1.9.9] | R/D Watermark Mgr | READ (admission backpressure) |

---

## 22. Open Items

| ID | Item | Status |
|---|---|---|
| OQ-19b | Ch interleave granularity | Needs Python script + traffic trace; CSR configurable |
| OQ-20 | **Scheduler weights/sizing sweep [v1.9.9]** | One joint pass vs the golden model: `K`, control-weight values, `AGE_MAX`, DQ-servo `POOL_LOW/POOL_HIGH/LOOKAHEAD`, per-bank queue **depth** + total in-flight, ready-bank count for CA-slot fill, R/W queue **organization** (unified+tag vs split). Blocks RTL; pkg frozen until done. |
| OQ-21 | **Golden-model debt [v1.9.9]** | Weighted arbiter + DQ servo/aging counter not yet in `sched_test.js` (still busy-first + oldest tie-break); add with OQ-20. |

**[v1.9.9]** Retired by the RAW-pause rework: the old RAW hold-forward collision-limit
question (only one response source remains).

---

## 23. Documents Produced

| File | Description |
|---|---|
| `RMC_Knowledge_Base_v3.md` | Full field definitions, all decisions |
| `RMC_IO_Map.md` | All block I/O ports, parameter definitions |
| `RMC_Maintenance_Engine.md` | 4 original sub-FSM spec (pre v1.9.8) |
| `rmc_version_control.md` | Full version history v1.0.1–v1.9.8 |
| `rmc_mc_core_blocks_v2.pdf/.tex` | LaTeX spec document, 16 pages |
| `RMC_Architecture_v4.excalidraw` | Full block diagram |
| `RMC_Diagram_README.md` | Arrow reference for excalidraw diagram |
| `DDR5_Command_Timing.csv` | 198-row DDR5 timing table |
