# RMC — Reconfigurable DDR5 Memory Controller
## Version Control Log
### For continuation in a new session — read this first

---

## HOW TO USE THIS DOCUMENT

This file tracks every architectural decision, field change, and design
evolution of the RMC project. Each version = one meaningful decision or
design milestone. When continuing in a new session:

1. Read the CURRENT VERSION section
2. Read all OPEN QUESTIONS at the bottom
3. Check NEXT STEPS for what was planned
4. Reference RMC_Knowledge_Base_v3.md for full field definitions
5. Reference RMC_IO_Map.md for all block I/O ports
6. Reference RMC_Maintenance_Engine.md for 4 sub-FSM specs

All LaTeX docs are in outputs/.

---

## CURRENT VERSION: v1.9.8

---

## VERSION HISTORY

---

### v1.0.1 — Project Bootstrap
**Status:** Closed

**What was decided:**
- Target: DDR5 memory controller, JESD79-5
- Host interface: AXI4
- PHY interface: DFI 5.2
- Scope: MC block only (not PHY, not CPU)
- DDR5 hierarchy: Channel → Subchannel → Rank → BG → Bank → Row → Column

---

### v1.1.0 — AXI Feature Lock
**Status:** Closed

- Burst type: INCR only (WRAP/FIXED rejected)
- Data bus: 64-bit
- Outstanding IDs: multiple supported
- Narrow/unaligned/exclusive/QoS: NOT supported

---

### v1.1.1 — Burst Model Lock
**Status:** Closed

- BL16 ONLY — no BL8, no BC8
- 64B request = exactly one BL16 burst on 32-bit subchannel
- BL/2 = 8 MC clock cycles bus occupancy

---

### v1.2.0 — CIF Block Definition
**Status:** Closed

- Burst Splitter Stage 1: row boundary check
- Burst Splitter Stage 2: BL alignment
- Address Translator: byte_addr → {rank, BG, bank, row, col}
- Merge Logic: fragment reassembly
- ROB: {AXID, seqnum} composite tag, per-AXID HEAD pointer

---

### v1.2.1 — Single CDC Crossing Lock
**Status:** Closed

- ONE Async FIFO CDC bar = sole crossing point
- TWO unidirectional FIFOs (req + resp)
- Everything upstream = AXI clock, downstream = MC clock

---

### v1.3.0 — Request/Response FIFO Packet Format
**Status:** Closed

**Request FIFO (CIF → MC):**
```
req_type  1b
tag       AXI_ID_WIDTH
addr      ADDR_WIDTH
data      DATA_WIDTH   WR only
mask      STRB_WIDTH   WR only
```

**Response FIFO (MC → CIF):**
```
resp_type  RESP_TYPE_WIDTH
tag        AXI_ID_WIDTH
data       DATA_WIDTH   RD only
status     STATUS_EXT_WIDTH
```

**Key:** valid-only resp FIFO, no ready from CIF.
gate_resp_fifo_avail checked before every RD issue.

---

### v1.3.1 — Global Cycle Counter Width
**Status:** Closed

- GC_WIDTH parameterized (baseline reasoning: 20b)
- half-range = 524,288 cycles, worst-case gap ~12,480 cycles → 42× margin
- comparison: modular subtract, bit[GC_WIDTH-1] sign check
- same as TCP sequence number wraparound

---

### v1.4.0 — Buffer Architecture Lock
**Status:** Closed (updated in v1.9.2)

- Write Data Buffer: SRAM, index-addressed, not FIFO
- Write Request Buffer: CAM-searched
- Read Request Buffer: CAM-searched
- CAM/RAM split: compare array on search-key bits only

---

### v1.4.1 — Bank FSM Table Architecture
**Status:** Closed (pending bits deprecated in v1.8.2, can_* added in v1.9.1)

- 16 × N_RANKS rows
- Timing fields: next_act, next_pre, next_cas, next_ref (absolute deadlines)
- Global cross-bank fields: next_act_bg, faw_window, next_cas_bg, etc.

---

### v1.5.0 — Timing Model Lock
**Status:** Closed (can_* extension in v1.9.1)

**Key principle:** absolute deadline fields, NOT countdown counters.
```
issue time (rare): next_legal = gc + delay
check every cycle: eligible = (gc - next_legal)[GC_WIDTH-1] == 0
```
Eliminates ~200 decrementers → ~100 static comparators against one shared counter.

---

### v1.5.1 — Worked Example Parameters Lock
**Status:** Closed

All widths now parameterized. Example values for documentation only.

---

### v1.6.0 — RAW Redirect Architecture
**Status:** Closed

- Stage A: exact match {BG, bank, row, col} via WR_TCAM
- Stage B: mask coverage check
- CRITICAL: RAW hit completes READ ONLY, write untouched

---

### v1.6.1 — Partial Hit Correction
**Status:** Closed

- Partial hit with gaps → STALL read until conflicting write retires
- NOT degrade to DRAM fetch (stale data bug)

---

### v1.6.2 — Hold-and-Forward: 1x → 2x
**Status:** Closed

- 2-deep hold slots (hold_slot[1:0], hold_valid[1:0])
- RAW hit + DRAM-return can fire same cycle

---

### v1.6.3 — CAM vs Comparator Distinction
**Status:** Closed

- RAW Stage A = XOR-based exact-match (true CAM cells)
- Scheduler Stage 2 = subtractor-based magnitude comparator
- Different primitives, must not be conflated in RTL

---

### v1.7.0 — Scheduler Stage 1 (RD/WR Mode)
**Status:** Closed

```
RD→WR: wr_count >= WR_HIGH_WM OR RD empty
WR→RD: wr_count <= WR_LOW_WM  OR WR empty OR AGE_THR2 escalation
```
WR_HIGH_WM=16, WR_LOW_WM=4. AGE_THR2 → force-interrupt (locked v1.9.0).

---

### v1.7.1 — Scheduler Five-Stage Structure
**Status:** Closed (fully defined in v1.9.0)

```
Stage 0: Maintenance override (REF/ZQ/RFM)
Stage 1: TCAM search → hit_bitmap + metadata
Stage 2: can_* gate check + cost classification
Stage 3: SJF winner selection
Stage 4: command emission + table writebacks
```

---

### v1.7.2 — Maintenance Engine Placement Lock
**Status:** Closed (fully specced in v1.9.0)

- Model A: peer block to Scheduler
- Writes into Bank FSM Table + Per-Rank FSM Table
- 4 sub-FSMs: Refresh, ZQcal, RFM, Power Management

---

### v1.7.3 — Pipeline Latency and ROB Sizing
**Status:** Closed

- Full round-trip worst case: ~37 cycles
- ROB_WATERMARK = 37
- Timeout Option A (wait for CAS): 76 cycles → LOCKED

---

### v1.8.0 — Address Mapping Lock
**Status:** Closed

- 32b baseline, parameterized expansion to 46b (3DS)
- Channel select = A[7] always (128B interleave)
- BG/Bank bits fixed (BG_BITS+BANK_BITS) across all configs

---

### v1.8.1 — Multi-Config Address Map
**Status:** Closed

- Desktop-S through 3DS-Max profiles defined
- No channel manager or rank manager block needed

---

### v1.8.2 — Pending Bits Removal + TCAM Decision
**Status:** Closed

**Removed from Bank FSM Table:**
```
open_pending → tcam_out[bank].hit
pre_pending  → Stage 2: tcam_out[b].row != row_open[b]
act_pending  → Stage 2: state[b] == IDLE
wr_pending   → tcam_out[b].req_type == WR
rd_pending   → tcam_out[b].req_type == RD
```
**Kept:** ref_pending (no TCAM equivalent for REF)

---

### v1.9.0 — Multi-Rank + Scheduler Full Definition
**Status:** Closed

- Bank FSM Table: [N_RANKS][16]
- Per-Rank FSM Table: N_RANKS instances, 5 states
- Global Timing Table: 1 instance, all cross-bank fields
- Scheduler fully defined: all 5 stages, SJF policy, bank pipelining
- Maintenance Engine: all 4 sub-FSMs fully specced
- Stage 0: ref_urgent > ref_due > rfm_req > zq_due
- Stage 3 tie-break: locked → round-robin BG, oldest entry within BG
- AGE_THR2 escalation: locked → force-interrupt
- Starvation: starved[i] = age[i] >= STARVATION_THR + entry_idx[i]
- Bank pipelining: consecutive ACTs prefer diff BG (tRRD_S < tRRD_L)

---

### v1.9.1 — can_* Registered Flag Extension
**Status:** Closed

**Decision:** timestamps stored, can_* flags registered separately.

```
every cycle (background, not critical path):
  can_act <= (gc - next_act)[GC_WIDTH-1] == 0
  can_pre <= (gc - next_pre)[GC_WIDTH-1] == 0
  can_cas <= (gc - next_cas)[GC_WIDTH-1] == 0
  can_ref <= (gc - next_ref)[GC_WIDTH-1] == 0
```

**Per-bank FSM Table final fields:**
```
state        BANK_STATE_WIDTH
row_open     ROW_BITS
next_cas     GC_WIDTH
next_pre     GC_WIDTH
next_act     GC_WIDTH
next_ref     GC_WIDTH
can_cas      1b
can_pre      1b
can_act      1b
can_ref      1b
ref_pending  1b
```

**Global Timing Table:** same pattern, can_* for all cross-bank fields.
**Per-Rank FSM Table:** can_rfc, can_zq, can_xp, can_xs added.

**Stage 2 reads only can_* flags. No subtractor in critical path.**

---

### v1.9.2 — TCAM Split + Status Reg + Buffer Sizing + Interface Protocol
**Status:** Closed

#### TCAM Split: RD_TCAM + WR_TCAM

**WR_TCAM** (full address search, for RAW):
```
bg           BG_BITS
bank         BANK_BITS
row          ROW_BITS
col          COL_BITS
req_type     1b = WR
axi_id       AXI_ID_WIDTH
entry_idx    $clog2(N_WR_ENTRIES)
data_buf_idx optional → Write Data Buffer
```

**RD_TCAM** (BG/bank ternary, for Scheduler Stage 1):
```
bg           BG_BITS
bank         BANK_BITS
row          ROW_BITS   carried, not matched
col          COL_BITS   carried, not matched
req_type     1b = RD
axi_id       AXI_ID_WIDTH
entry_idx    $clog2(N_RD_ENTRIES)
```

**No valid/ts in TCAM entries.**
Valid gating: TCAM match[i] AND status_reg[i].valid
Multi-hit: argmax(status_reg[age]) via entry_idx lookup

**Power benefit:** invalid rows dark → dynamic power reduction at low occupancy.

#### Status Register Fields (final, minimal)
```
valid    1b
status   STATUS_WIDTH   00=PENDING 01=ISSUED 10=DONE 11=ERROR
age      GC_WIDTH
```
Owner: watermark managers (R/W). Scheduler: READ ONLY.
age = single source of truth for: multi-hit newest-wins, starvation, SJF cost.

#### Buffer Sizing
```
N_WR_ENTRIES = 2-3× N_RD_ENTRIES (v1: 64 WR, 32 RD)
rationale: larger WR buffer → scheduler drains WR in background
           RD sees less blocking → lower read latency
           bandwidth unchanged
```

#### RAW Hit Valid Condition
```
hit valid iff: wr_status_reg[hit_idx].age <= rd_age
write arrived same cycle or earlier → valid hit
write arrived after read → NOT a hit → normal mem_read
overshoot bytes → DROP
```

#### Interface Protocol Lock
```
AXI4 ports:              valid-ready (spec mandated)
Async req FIFO write:    credit-based push (N credits = FIFO depth)
Async req FIFO read:     valid-credit receive + credit_return
Async resp FIFO write:   credit-based push (gate_resp_fifo_avail)
Async resp FIFO read:    valid-credit receive + credit_return
Credit return (MC→CIF):  registered 1b, pulse sync
Credit return (CIF→MC):  registered 1b, pulse sync
All intra-MC:            valid-credit
DFI:                     DFI 5.2 protocol
PHY→MC rddata:           valid-only
```

#### All Widths Parameterized
No hardcoded bit-widths anywhere. All lengths expressed as parameters
(GC_WIDTH, DATA_WIDTH, AXI_ID_WIDTH, AWLEN_WIDTH, etc.).
See parameter definitions table in RMC_IO_Map.md §0.

---

## OPEN QUESTIONS (as of v1.9.2)

| ID | Topic | Question | Status |
|---|---|---|---|
| OQ-05 | 3rd collision Hold-Forward | hold_slot[1:0] full + new collision same cycle | CLOSED — impossible by construction, 2 sources max |
| OQ-10 | STARVATION_THR | RD=12480 WR=37440 (3:1 ratio), both CSR | CLOSED |
| OQ-11 | RAW Stage A latency | Combinational parallel with alloc, zero miss penalty | CLOSED |
| OQ-12 | Req FIFO credit depth | 16 entries both FIFOs | CLOSED |
| OQ-13 | ZQcal per-rank vs shared | Per-rank instances locked | CLOSED |
| OQ-14 | MR4 TUF polling path | Needs MRR command path spec | OPEN |
| OQ-15 | REFsb coverage counter | 5b per-rank bank cycle counter needed | OPEN |
| OQ-16 | TCAM area budget | Not estimated for target process node | OPEN |
| OQ-17 | PD_IDLE_THRESHOLD | 64 cycles default, CSR | CLOSED |
| OQ-18 | tZQCS_interval default | 128ms→cycles at runtime, CSR | CLOSED |
| OQ-19 | XOR address hashing | ADR-0002, split-column mapping | Deferred |
| OQ-20 | Runtime DIMM discovery | Out of scope | CLOSED |

---

## KNOWN BUGS / INCONSISTENCIES

| ID | Location | Issue | Status |
|---|---|---|---|
| BUG-01 | mc_v0_1.png | global_counter shown 32b | GC_WIDTH now param, diagram needs redraw |
| BUG-02 | rmc_mc_core_blocks.tex | pending bits still in field table | Deprecated v1.8.2, doc not patched |
| BUG-03 | rmc_mc_core_blocks.tex | buffer depth hardcoded 32 | Parameterized v1.9.2, doc not patched |
| BUG-04 | rmc_raw_redirect_cam.tex | partial-hit says "degrade to DRAM" | Corrected to stall v1.6.1, doc not patched |
| BUG-05 | mc_v0_1.png | TCAM not shown | Needs RD_TCAM + WR_TCAM added |
| BUG-06 | mc_v0_1.png | pending bits shown in Bank FSM | Removed in v1.8.2 |
| BUG-07 | all LaTeX docs | hardcoded bit-widths | All to be parameterized in next doc pass |

---

## NEXT STEPS (priority order)

1. **Excalidraw diagram** — full updated block diagram with:
   - RD_TCAM + WR_TCAM blocks
   - Per-Rank FSM Table
   - Bank Activity Counter Table
   - Maintenance Engine (4 sub-FSMs)
   - can_* flag annotation on FSM tables
   - valid-credit interface labels
   - credit return paths on async FIFOs

2. **Patch LaTeX docs** — fix all BUG-02 through BUG-07

3. **OQ-05 resolution** — verify 3rd collision rate-limited by construction

4. **OQ-11 resolution** — lock RAW Stage A latency (combinational vs registered)

5. **ADR-0002** — XOR address hashing, split-column mapping formalization

6. **Python address-map hash optimizer** — parameterized config tool

7. **RTL skeleton** — top-level module hierarchy, parameter propagation

---

## DOCUMENTS (current)

| File | Version | Description |
|---|---|---|
| DDR5_Command_Timing.csv | v1.1.1 | 198-row DDR5 timing table |
| DDR4_Command_Timing.csv | v1.1.1 | 197-row DDR4 equivalent |
| RMC_Design_Specification.pdf | v1.2.0 | Full system spec |
| rmc_pipeline_walkthrough.pdf | v1.5.1 | Read/write worked example |
| rmc_mc_core_blocks.pdf | v1.4.1 | Internal block field definitions (STALE — see BUG-02/03) |
| rmc_raw_redirect_cam.pdf | v1.6.0 | RAW redirect + CAM + Hold-Forward (STALE — see BUG-04) |
| rmc_design_optimizations.pdf | v1.5.0 | 35 named techniques |
| RMC_Knowledge_Base_v3.md | v1.9.2 | Complete field definitions + all decisions |
| RMC_IO_Map.md | v1.9.2 | All block I/O ports + parameter definitions |
| RMC_Maintenance_Engine.md | v1.9.0 | 4 sub-FSM full spec |
| rmc_version_control.md | v1.9.2 | This file |

---

## COMPILE-TIME PARAMETERS (current baseline)

```systemverilog
// all widths parameterized — no hardcoded values
// baseline: 4GB single-channel single-rank

parameter GC_WIDTH       = /* target-dependent */;
parameter ADDR_WIDTH     = /* config-dependent */;
parameter AXI_ID_WIDTH   = /* system-dependent */;
parameter DATA_WIDTH     = /* system-dependent */;
parameter CH_BITS        = /* config-dependent */;
parameter RANK_BITS      = /* config-dependent */;
parameter N_RANKS        = /* config-dependent */;
parameter BG_BITS        = /* config-dependent */;
parameter BANK_BITS      = /* config-dependent */;
parameter ROW_BITS       = /* config-dependent */;
parameter COL_BITS       = /* config-dependent */;
parameter N_WR_ENTRIES   = /* 2-3x N_RD_ENTRIES */;
parameter N_RD_ENTRIES   = /* config-dependent */;
parameter WR_BUF_DEPTH   = /* config-dependent */;
parameter FIFO_DEPTH     = /* area/latency tradeoff */;
parameter N_CLIENTS      = /* system-dependent */;
parameter WR_HIGH_WM     = /* runtime CSR */;
parameter WR_LOW_WM      = /* runtime CSR */;
parameter AGE_THR1       = /* runtime CSR */;
parameter AGE_THR2       = /* runtime CSR */;
parameter STARVATION_THR = /* runtime CSR */;
```

---

## ARCHITECTURE RATING (as of v1.9.2)

| Scope | Rating |
|---|---|
| What's built (buffers, timing model, RAW, scheduler) | 9/10 |
| Full architecture vs industry standard | 8/10 |
| vs typical capstone | Significantly above |

TCAM split, registered can_* flags, credit-based CDC interfaces,
SJF scheduling, bank pipelining, staggered starvation all match or
exceed real DDRC design patterns (Synopsys DDRC, ARM DMC-620).

---

### v1.9.3 — OQ-05 Resolution: Hold-Forward 3rd Collision
**Status:** Closed

**Question:** can hold_slot[0] and hold_slot[1] both be full AND a
third response arrive same cycle?

**Analysis:**
```
Response sources:
  src0: RAW Bypass Manager  → max 1/cycle (one req FIFO output/cycle)
  src1: Read Data Path      → max 1/cycle (one dfi_rddata_valid/cycle)
  total sources = 2
  max simultaneous = 2
```

**Resolution:** 3rd collision impossible by construction.
Rate-limited by:
- Single req FIFO output port (one RD alloc/cycle, valid-credit)
- Single dfi_rddata_valid (one DRAM return/cycle)

**Locked:** 2-deep Hold-Forward is exact minimum AND maximum required.
No 3rd slot ever needed.

**OQ-05 → CLOSED**

---

### v1.9.4 — Speculative Prefetch ACT (Stage 2 Extension)
**Status:** Closed

**What was added:**
NOP-cycle-only speculative ACT to next sequential bank.
Confirmed by RD_TCAM + bank_act_count. Not blind prediction.

**Trigger:** winner_valid==0 (true NOP cycle only)

**Prediction:**
```
active bank approaching col boundary (COL_MAX - cur_col <= BL_BYTES)
→ pred = {same_rank, same_bg, bank+1, same_row}
→ confirmed by RD_TCAM hit + row match + bank_act_count > 0
→ gated by can_act + can_faw (same as real ACT)
```

**No mispredict path:**
TCAM confirms real request exists before ACT fires.
Worst case: wasted FAW slot if row later conflicts.

**bank_act_count dual use (locked):**
```
count == 0     → no speculate + closed page policy
count 1-3      → speculate if boundary imminent + adaptive page
count >= 4     → speculate aggressively + open page
```

**New hardware:** one comparator per active bank + 1 mux.
Zero new tables, FSMs, or buffers.

**New invariants:** 17-20 added to scheduler invariants.

---

### v1.9.5 — OQ-11 Closed: RAW Stage A Latency + Merge Unit
**Status:** Closed

**RAW timing locked:**
```
cycle 0: WR_TCAM search combinational parallel with RD alloc
         zero penalty on miss path
cycle 1: coverage check + case decision
cycle 2: data on resp FIFO (full hit path)
```

**Search key:** exact {BG,bank,row,col}, no col LSB masking (BL16 aligned)

**Partial overlap — no stall (locked):**
```
issue DRAM fetch immediately, tag merge_pending in RD status reg
merge unit combines WDB + DRAM at return time (1 cycle)
partial hit costs same as normal DRAM fetch — zero penalty
```

**New blocks:** Merge Unit (64×2:1 mux, trivial)

**RD status reg updated:**
```
+ merge_pending  1b
+ wdb_entry_idx  $clog2(WR_BUF_DEPTH)
```

**OQ-11 → CLOSED**

---

### v1.9.6 — OQ-10,12,13,17,18,20 Closed
**Status:** Closed

**OQ-10 — STARVATION_THR (locked):**
```
RD_STARVATION_THR = 12480 cycles   (9×tREFI, CSR tunable)
WR_STARVATION_THR = 37440 cycles   (3× RD, CSR tunable)
WR served preferentially on NOP windows + watermark drain
WR starvation threshold = safety net only
ratio: 3:1 WR:RD starvation tolerance
```

**OQ-12 — FIFO depth (locked):**
```
REQ FIFO depth  = 16 entries (16 credits to CIF)
RESP FIFO depth = 16 entries (16 credits to MC)
2× headroom over CDC+pipeline latency
```

**OQ-13 — ZQcal (locked):** per-rank instances

**OQ-13 extension — rank-associative timing (locked):**
```
Global Timing Table additions:
  next_act_rank[N_RANKS]   GC_WIDTH × N_RANKS
  next_cas_rank[N_RANKS]   GC_WIDTH × N_RANKS
  can_act_rank[N_RANKS]    1b × N_RANKS   registered
  can_cas_rank[N_RANKS]    1b × N_RANKS   registered
```

**OQ-17 — PD_IDLE_THRESHOLD (locked):** 64 cycles default (CSR)

**OQ-18 — tZQCS_interval (locked):** 128ms converted to cycles at runtime (CSR)

**OQ-20 — runtime DIMM discovery:** OUT OF SCOPE, closed

**Open remaining: OQ-14, OQ-15, OQ-16, OQ-19**

---

### v1.9.7 — OQ-15 Closed: REFsb Coverage + Opportunity Refresh
**Status:** Closed

**REFsb coverage (locked):**
```
per-rank field added:
  last_refsb_gc[32]   GC_WIDTH × 32
  timestamp of last REFsb issued per bank
  one field → solves both coverage tracking + opportunity targeting
```

**Targeting (option B locked):**
```
normal:   argmin(bank_act_count) — least-loaded bank first
watchdog: if gc - last_refsb_gc[b] > tREFI×32 → force bank b next
          overdue bank overrides argmin selection
```

**Opportunity Refresh (new, locked):**
```
fires on NOP cycle (winner_valid==0):
  AND bank_act_count[r][bg][b]==0   bank idle, no traffic
  AND argmax(gc - last_refsb_gc[b]) most overdue bank
  AND can_ref[b]==1

→ REFsb issued with zero traffic disruption
→ spreads refresh load, reduces future forced stalls
```

**NOP cycle priority (locked):**
```
1. opportunity REFsb   (correctness > speculation)
2. speculative ACT     (only if no opportunity REF pending)
```

**Stage 4 writeback on REFsb:**
```
last_refsb_gc[r][bank_idx] ← gc
```

**OQ-15 → CLOSED**

---

### v1.9.8 — Major Batch Update
**Status:** Closed

**OQ-14 closed — MR_Poll FSM (ME sub-FSM 6):**
```
6 states: IDLE→WAIT_INTERVAL→REQUEST_MRR→WAIT_RDDATA→PARSE_TUF→UPDATE_TREFI
Stage 0 bypass for MRR issue
sideband: Read Data Path → MR_Poll FSM (not resp FIFO)
TUF=1 → tREFI halved, Refresh FSM updated
new Per-Rank fields: last_TUF, next_poll_gc, mrr_data
new CSR: MRR_POLL_INTERVAL (default 32×tREFI)
```

**OQ-16 closed — TCAM cell counts:**
```
WR_TCAM:  24,576T
RD_TCAM:   1,920T
RAW BCAM: 12,288T
total:    38,784T ≈ 6,464 SRAM bits
```

**OQ-19 partially closed — AMU (OQ-19b open):**
```
AMU replaces Address Translator in CIF
field_desc: src_msb/lsb_a/b, split_en, hash_en, xor_shift
rank=MSB locked, hash_en per-field
bg/bank/row/col hash_en=0 (preserve locality)
ch/rank hash_en=1 (spread traffic)
split-column support for channel interleave
OQ-19b: ch interleave granularity TBD (needs script)
```

**Init FSM → ME (locked):**
```
Init FSM now ME sub-FSM 1
ME owns DFI mux (init_done gates Scheduler vs Init FSM)
ME total: 6 sub-FSMs
```

**Bank Partition RD/WR scheme (locked):**
```
N_BANKS split into RD/WR halves
rotate every WINDOW_SIZE (CSR, default 2×tREFI)
no tRTW/tWTR within window
penalty only at rotation boundary (amortized)
overrides: WR_HIGH_WM, RD starvation, opportunity REFsb unaffected
new block: Bank Partition Controller
new fields: partition_reg, window_ctr, rd/wr_partition_mask
```

**NOP cycle priority (final, locked):**
```
1. opportunity REFsb
2. speculative ACT
3. WR partition drain
4. true NOP
```

**ME sub-FSMs (final list):**
```
1. Init FSM
2. Refresh FSM
3. ZQcal FSM (per-rank)
4. RFM FSM
5. Power Management FSM
6. MR_Poll FSM
```

**Open remaining:**
```
OQ-19b: ch interleave granularity (needs Python script)
BUG-02 through BUG-07: LaTeX docs stale
```
