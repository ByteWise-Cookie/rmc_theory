# RMC — Reconfigurable DDR5 Memory Controller
## Complete Project Knowledge Base
### All key decisions, architecture, mappings, open questions

---

## 0. Project Identity

| Item | Value |
|---|---|
| Project | Reconfigurable Memory Controller (RMC) — DDR5 capstone |
| Standard | JEDEC JESD79-5 (DDR5), DFI 5.2, AXI4 |
| Target | 4GB, single-channel, single-rank (current anchor) |
| Future ceiling | 46b address, 8ch, 8rank, 64Gb×3DS-8H = 64TB |
| RTL style | SystemVerilog, parameterized, no hardcoded widths |
| Docs produced | 7 LaTeX/PDF documents (listed in §10) |

---

## 1. Locked Architecture Decisions

| Decision | Value | Rationale |
|---|---|---|
| BL | BL16 only, no BL8/BC8 | AXI contract is 64B-aligned INCR-only = exactly one BL16 burst on 32b subchannel |
| AXI burst type | INCR only | WRAP/FIXED not useful for DRAM |
| AXI data width | 64-bit | Sufficient for target |
| Narrow/unaligned transfers | Not supported | Too complex, low benefit |
| Exclusive access | Not supported | Out of scope |
| QoS | Not supported | Not justified at this stage |
| Outstanding IDs | 32 shared pool (not per-client) | Matches CAM-based transparent-buffer pattern |
| CDC crossing | Single async FIFO bar, sole crossing point | One crossing point = one verification target |
| Scheduler type | Common scheduler + cmd_type encoding | Industry standard (Synopsys, ARM, Cadence all do this) |
| ACT/PRE in scheduler | Scheduler-generated inline, not pool entries | ACT/PRE have no AXI-side originator |
| Page policy | Open page default, closed/adaptive configurable | Open page best for sequential/localised |
| Prefetch | Not owned by MC — CPU side | MC responds to requests, does not predict |
| Address mapping | Runtime configurable, no hardcoded widths | DIMM count, rank, density all vary |
| Cache-line interleave | 64B granularity | Odd/even address split rejected — destroys locality |
| Maintenance Engine | Model A — peer block to Scheduler | Writes into existing Bank FSM Table ref_pending bits |
| 1 MC core per channel | Yes | Symmetric replication, no cross-channel coordination needed |

---

## 2. System Block Diagram (Text)

```
AXI Masters (up to 32 clients)
    ↓ [AXI4, INCR only, 64b, 512b/256beat max per client]
AXI Interconnect
    ↓
CIF (AXI clock domain)
  ├── AXI Write Port / AXI Read Port
  ├── Burst Splitter (Stage1: row boundary, Stage2: BL alignment)
  ├── Address Translator (byte_addr → {ch,rank,BG,bank,row,col})
  ├── Write Cmd Pool / Read Cmd Pool
  ├── Reorder Buffer (ROB) — per-AXID HEAD pointer, {AXID,seqnum} tag
  └── Merge Logic (fragment reassembly)
    ↓ [Async FIFO CDC — SOLE crossing point]
MC Core (MC clock domain)
  ├── Config Registers (all timing knobs, CSR via AXI4-Lite)
  ├── Init FSM (16 states, DDR5 power-up sequence)
  ├── Write Data Buffer (32-entry SRAM, 576b/entry, index-addressed)
  ├── Write Request Buffer (32 entries, CAM-searched)
  ├── Read Request Buffer (32 entries, CAM-searched)
  ├── RAW Redirect (CAM-based hazard detect, every clock)
  ├── Hold-and-Forward (2-deep, response path collision)
  ├── Bank FSM Table (16×N_RANKS rows, go/no-go + next_* fields)
  ├── Global Cycle Counter (20b, free-running)
  ├── Arbitration Logic (5-level priority, watermark, age counters)
  ├── Command Selector (page policy, BG-aware reorder, legal check matrix)
  ├── Maintenance Engine
  │     ├── Refresh Scheduler FSM (leaky-bucket, REFab/REFsb/FGR)
  │     ├── ZQcal FSM (MPC ZQCAL Start/Latch)
  │     ├── RFM FSM (per-bank RAA counters)
  │     └── Power Management FSM (PD/SR/MPSM)
  ├── Write Data Path (WL align, CRC, DFI write timing)
  └── Read Data Path (latency counter, capture FIFO, ECC/CRC)
    ↓ [DFI 5.2]
DDR PHY
    ↓
DDR5 DRAM
```

---

## 3. Address Mapping (Locked: 32b, 4GB, Single Ch/Rank)

```
A[31:17] = Row      (15b, 32768 rows)
A[16:14] = BG       (3b,  8 bank groups)
A[13:12] = Bank     (2b,  4 banks/BG)
A[11:2]  = Column   (10b, 1024 columns)
A[1:0]   = Offset   (2b,  byte within 4B beat)
```

**Capacity check:** 2^15 × 2^10 × 2^2 × 2^5 bytes = 2^32 = 4GB ✓

### Multi-Config Address Map (parameterized)

| Config | Total | Addr | Ch bits | Rank bits | BG | Bank | Row | Col |
|---|---|---|---|---|---|---|---|---|
| Desktop-S | 8GB | 33b | 0 | 0 | 3 | 2 | 16 | 10 |
| Desktop-D | 16GB | 34b | 1 (A[7]) | 0 | 3 | 2 | 16 | 10 |
| Desktop-Q | 32GB | 35b | 1 (A[7]) | 1 (A[8]) | 3 | 2 | 16 | 10 |
| Workstation-D | 64GB | 36b | 1 | 1 | 3 | 2 | 17 | 10 |
| Workstation-Q | 128GB | 37b | 1 | 2 | 3 | 2 | 17 | 10 |
| Enterprise-4C | 256GB | 38b | 2 (A[8:7]) | 2 | 3 | 2 | 17 | 10 |
| Enterprise-8C | 1TB | 40b | 3 (A[9:7]) | 3 | 3 | 2 | 18 | 11 |
| Enterprise-Max | 2TB | 41b | 3 | 3 | 3 | 2 | 18 | 11 |
| 3DS-Max | 64TB | 46b | 3 | 3+3(CID) | 3 | 2 | 18 | 11 |

**128B interleave:** channel select bit = A[7] always (128 = 2^7). Column field splits around channel bits — NOT a simple contiguous slice. Address Translator bit-field extractor must handle split-column.

**Dual-channel always clean:** symmetric 2^N channel count, perfectly divisible.

**BG/Bank bits never change** (3b+2b) for x4/x8 across all configs. Only row/col/ch/rank grow.

**JEDEC hard ceiling:** 41b (8ch×8rank×64Gb, no stacking). 46b with 3DS 8H stacking.

---

## 4. Async FIFO Packet Formats

### Request FIFO (CIF → MC Core)

| Field | Width | Notes |
|---|---|---|
| req_type | 1b | 0=req_read, 1=req_write |
| tag (AWID/ARID) | varies | AXI ID, carried through |
| addr | 32b | Byte address |
| data | 512b | Write only |
| mask | 64b | Write only, byte-level |

### Response FIFO (MC Core → CIF)

| Field | Width | Notes |
|---|---|---|
| resp_type | 2b | 00=RD_DATA, 01=WR_ACK, 10=ERR |
| tag | varies | AXI ID for routing |
| data | 512b | RD_DATA only |
| status | 4b | 0=OK, else error code |

**Response FIFO is valid-only — NO ready from CIF.** MC must self-throttle via `gate_resp_fifo_avail` checked before any RD issue. CIF must always be able to accept a response instantly.

---

## 5. Internal Buffer Field Definitions

### Global Cycle Counter

| Field | Width | Notes |
|---|---|---|
| global_cycle | **20b** | Free-running, never resets (except SOFT_RESET) |

**20b rationale:** half-range = 524,288 cycles. Worst-case gap = 8×tREFI postponement ≈ 12,480 cycles. Margin = 42×. 15b rejected (only 1.3× margin — too tight). Comparison via modular subtract: `diff = global_cycle - next_legal_cycle (20b unsigned sub); eligible = (diff[19]==0)` — bit-19 sign check, same as TCP sequence number wraparound.

### Write Data Buffer (SRAM, separate from Write Request Buffer)

| Field | Width | Notes |
|---|---|---|
| data[511:0] | 512b | 64B write payload |
| mask[63:0] | 64b | Byte-level mask |

- 32 entries, index-addressed by data_buf_idx
- 576b/entry → 32×576 = 18,432b ≈ 2.25KB SRAM macro
- **NOT a FIFO** — random access buffer

### Write Request Buffer (CAM-searched, 32 entries)

| Field | Width | Notes |
|---|---|---|
| valid | 1b | Entry occupied |
| axi_tag | varies | AWID for WR_ACK routing |
| bank_group | 3b | From Address Translator |
| bank | 2b | From Address Translator |
| row | 17b | From Address Translator |
| column | 10b | From Address Translator |
| data_buf_idx | 5b | Index into Write Data Buffer |
| wr_partial | 1b | 1 if mask ≠ all-1 (triggers DRAM RMW) |
| status | 2b | 00=PENDING, 01=ISSUED, 10=DONE, 11=ERROR |
| issue_cycle | 20b | global_cycle at WR issue time |

### Read Request Buffer (CAM-searched, 32 entries)

| Field | Width | Notes |
|---|---|---|
| valid | 1b | Entry occupied |
| axi_tag | varies | ARID for RD_DATA routing |
| bank_group | 3b | From Address Translator |
| bank | 2b | From Address Translator |
| row | 17b | From Address Translator |
| column | 10b | From Address Translator |
| resp_slot | 5b | Reserved slot in Resp FIFO (pre-issue reservation) |
| status | 2b | 00=PENDING, 01=ISSUED, 10=DONE, 11=ERROR |
| issue_cycle | 20b | global_cycle at RD issue time |

### Bank FSM Table (16 × N_RANKS rows)

#### Per-Bank State Fields

| Field | Width | Notes |
|---|---|---|
| state | 4b | 0000=IDLE, 0001=ACTIVATING, 0010=ACTIVE, 0011=READING, 0100=WRITING, 0101=PRECHARGING, 0110=REFRESHING_AB, 0111=REFRESHING_SB, 1000=POWER_DOWN, 1001=SELF_REFRESH, 1010=RFM_ACTIVE |
| row_open | 17b | Currently open row address (valid in ACTIVE/READING/WRITING) |
| open_pending | 1b | GO/NO-GO: has a request targeting this bank |
| pre_pending | 1b | GO/NO-GO: PRE needed (row miss — open_row ≠ req.row) |
| act_pending | 1b | GO/NO-GO: ACT needed (bank IDLE or after PRE) |
| wr_pending | 1b | GO/NO-GO: pending request is a write |
| rd_pending | 1b | GO/NO-GO: pending request is a read |
| ref_pending | 1b | GO/NO-GO: Refresh Scheduler has marked this bank for REF |

#### Per-Bank Timing Eligibility Fields (all 20b, absolute deadlines)

| Field | Loaded on | Formula |
|---|---|---|
| next_act | PRE issued / cross-bank checks | global_cycle + tRP (and max w/ cross-bank) |
| next_pre | ACT issued / RD issued / WR issued | ACT: gc+tRAS. RD: gc+tRTP. WR: gc+CWL+BL/2+tWR |
| next_cas | ACT issued | global_cycle + tRCD |
| next_ref | REFsb issued | global_cycle + tRFCsb |

#### Global (Cross-Bank) Timing Fields

| Field | Width | Notes |
|---|---|---|
| next_act_same_bg[BG] | 20b × #BG | tRRD_L from last ACT in same BG |
| next_act_any | 20b | tRRD_S from last ACT anywhere |
| faw_window[3:0] | 20b × 4 | Ring buffer of 4 most recent ACT timestamps |
| next_cas_same_bg[BG] | 20b × #BG | tCCD_L/tCCD_L_WR/tCCD_L_WR2 from last CAS in BG |
| next_cas_any | 20b | tCCD_S from last CAS anywhere |
| next_rd_after_wr[BG] | 20b × #BG | tWTR_L from last WR data-end in BG |
| next_rd_after_wr_any | 20b | tWTR_S from last WR data-end anywhere |
| next_wr_after_rd | 20b | tRTW = RL+BL/2-WL+2+tWPRE from last RD |
| gate_resp_fifo_avail | 1b | Combinational: Resp FIFO has a free unreserved slot |

---

## 6. RAW Redirect

**Position:** between Read Request Buffer allocation and Bank FSM Table scan. Runs every clock cycle.

**Has read-only access to:** Write Request Buffer (all valid entries), Write Data Buffer (mask field via data_buf_idx).

### Stage A — Binary CAM (row-level exact match)

Compare `{BG, bank, row, column}` of incoming read against ALL 32 write entries in parallel. Output: `row_match_vector[31:0]`. Cost: 32×22b×~12 transistors ≈ 8,448 transistors.

### Stage B — Mask coverage check (post-match, single entry)

`coverable = (read_required_mask & write_valid_mask) == read_required_mask`

### Hit Classification

| Case | Action |
|---|---|
| Full hit (mask=all-1) | Route data directly from Write Data Buffer → response path |
| Masked/coverable hit | Route covered bytes from Write Data Buffer → response path |
| Partial hit with gaps (holes in needed bytes) | **STALL read, do NOT degrade to DRAM fetch** — wait until conflicting write entry retires (status=DONE), then re-run check |
| No match | Proceed to Bank FSM Table scan normally |

**CRITICAL CORRECTNESS RULE:** RAW hit completes the READ ONLY. The matched write entry is UNTOUCHED — it proceeds through its full normal lifecycle (PENDING→ISSUED→DONE→WR_ACK). Write is never retired early by a RAW hit.

**Partial-hit-with-gaps stall rule (corrected from earlier "degrade to miss"):** fetching from DRAM on a partial hit would return stale data for the covered bytes (write not yet committed). Must stall read until write retires.

### CAM vs Comparator array distinction (CRITICAL for RTL)

- **RAW Redirect Stage A** = XOR-based exact-match (true CAM cells)
- **Scheduler Stage 2 bank scan** = subtractor-based magnitude comparator (`global_cycle - next_legal_cycle`, sign-bit check) — NOT a CAM. Different primitive, must not be conflated in RTL synthesis.

### Timestamp-based winner selection (multi-hit)

Timestamp stored in watermark manager's `ts_reg[N-1:0]` (one per slot, written at allocation = `global_cycle`). On multi-hit: `winner = argmax(ts_reg[i] for i in hit_set)` — log2(N)-deep comparator tree. Newest write wins.

### 2-Deep Hold-and-Forward

Two independent response sources can fire same cycle: RAW hit + DRAM-return. Single Resp FIFO write port. Need 2-deep hold buffer, not 1-deep.

| Field | Width |
|---|---|
| hold_slot[1:0] | 2 × full resp packet |
| hold_valid[1:0] | 2b |

---

## 7. Scheduler Structure (5 Stages)

### Stage 0 — Priority Pre-Check (REF/ZQ override)

Checks `ref_urgent`, `ref_due`, `zq_due`. If any true → bypasses stages 1-3, drives Stage 4 output directly with REF/ZQ command. **Blocked by Maintenance Engine open items.**

### Stage 1 — RD/WR Mode Arbitration (DEFINED)

```
wr_count = popcount(write_req_buf[i].valid)  // 0..32

RD→WR: wr_count >= WR_HIGH_WM (16) OR RD pool empty
WR→RD: wr_count <= WR_LOW_WM  (4)  OR WR pool empty OR urgent RD (age escalation)
```

**Watermark values:** WR_HIGH_WM=16 (half buffer, 0.75 cycles/write amortized overhead), WR_LOW_WM=4 (gap=12, prevents thrashing).

**Open question (UNRESOLVED):** does AGE_THR2 escalation FORCE immediate mode flip (interrupts mid-burst same-BG write sequence before tCCD_L_WR completes) or only RAISE PRIORITY for next natural flip? Recommendation: force-interrupt → WR→RD if RD age ≥ AGE_THR2, accept the tCCD_L_WR waste (bounded 1 instance).

### Stage 2 — Per-Bank Go/No-Go Scan

For each of 16×N_RANKS banks: check `open_pending`, `pre/act/rd/wr_pending` flags AND all timing deadline fields vs `global_cycle` (20b subtract + bit-19 check). Produces `go_mask[N_RANKS×16-1:0]`.

### Stage 3 — Bank-Group Aware Reordering

Among `go_mask` bits set, prefer `bank_group != last_issued_bg` to avoid tCCD_L_WR=32nCK penalty. **Tie-break rule when multiple go-banks in different BGs: UNRESOLVED.** 

### Stage 4 — Command Emission + Writeback

Build `{cmd, rank, BG, bank, row, col}` → DFI. Update Bank FSM Table `next_*` fields per issue event. Update request buffer `status` → ISSUED.

### Command Priority Order

1. REF urgent (credits ≥ 8)
2. REF nominal (tREFI countdown = 0)
3. ZQcal (tZQCS interval)
4. Write drain (wr_count near WR_HIGH_WM)
5. Row-hit reads
6. Row-hit writes
7. Row-miss reads (ACT → tRCD → RD)
8. Row-miss writes
9. PRE (close idle banks, closed-page policy)

---

## 8. Maintenance Engine (4 Sub-FSMs, Peer to Scheduler)

All sub-FSMs write into EXISTING Bank FSM Table fields (Model A). Scheduler's Stage 0 reads flags — does not own refresh logic internally.

### Refresh Scheduler FSM

States: IDLE → REF_DUE → WAIT_BANKS_IDLE → ISSUE_REF → WAIT_tRFC → DONE → IDLE

**Leaky-bucket:** credits += 1 every tREFI. Credits -= 1 per REF issued. ref_urgent at credits = 8. FGR: tRFC2 or tRFC4 used, budget threshold halved/quartered. Temperature: MR4 TUF polling → tREFI halved at >85°C.

REFsb path: bank address cycles BA[1:0] in order 00→01→10→11.

### ZQcal FSM

States: IDLE → WAIT_IDLE → ISSUE_ZQCAL_START → WAIT_tZQCAL → ISSUE_ZQCAL_LATCH → WAIT_tZQLAT → DONE → IDLE

### RFM FSM

States: IDLE → MONITOR_RAA → RFM_REQUEST → WAIT_ISSUE → WAIT_tRFM → UPDATE_RAA → MONITOR_RAA

RAA[b] += 1 per ACT to bank b. RAA[b] -= RAADec per REF. RFM triggered when RAA[b] ≤ RAAIMT. Priority: above ZQcal, below REF.

### Power Management FSM

PD branch: NORMAL → PD_ENTRY_CHECK → PRECHARGE_PD or ACTIVE_PD → PDX_WAIT_tXP → NORMAL

SR branch: NORMAL → SR_ENTRY → WAIT_tCKSRE → SELF_REFRESHING → SR_EXIT → WAIT_tCKSRX → WAIT_tXS → WAIT_tDLLK → NORMAL

---

## 9. Pipeline Latency and ROB Sizing

### Worked example parameters (@200MHz)

| Param | Value |
|---|---|
| tCK | 5ns |
| CL | 3 nCK (RL=3) |
| CWL | 1 nCK (WL=1) |
| BL/2 | 8 cycles |
| tRCD | 4 nCK |
| tRP | 4 nCK |
| tRAS | 7 nCK |
| tCCD_L | 8 nCK |
| tCCD_L_WR | 32 nCK |
| tWTR_L | 4 nCK |
| tRTW | RL+BL/2-WL+2 = 12 nCK |
| tRFC1 | 39 nCK |
| PHY_RDLAT | 2 nCK |
| PHY_WRLAT | 2 nCK |

### Read Path Cycle Counts (CAS to last data)

| Path | Cycles | Breakdown |
|---|---|---|
| Row Hit | 11 | RL(3)+BL/2(8) |
| Row Empty | 15 | tRCD(4)+RL(3)+BL/2(8) |
| Row Miss | 19 | tRP(4)+tRCD(4)+RL(3)+BL/2(8) |

### Write Path Cycle Counts (WR to bank-available-for-PRE)

| Path | Cycles |
|---|---|
| Row Hit | CWL+BL/2+tWR = 15 |
| Row Empty | tRCD+CWL+BL/2+tWR = 19 |
| Row Miss | tRP+tRCD+CWL+BL/2+tWR = 23 |

### Full Round-Trip (AXI to AXI, worst case row-miss)

| Stage | Cycles |
|---|---|
| CIF pipeline | ~2 |
| Req FIFO CDC | ~4 |
| RAW Redirect check | ~1-2 (OPEN) |
| Scheduler stages 1-4 | ~4 |
| DRAM row-miss | 19 |
| Read Data FIFO capture | 1 |
| Resp FIFO CDC | ~4 |
| ROB retirement | 1 |
| **Total** | **~37 cycles** |

### ROB and Timeout Values

| Value | Cycles | Use |
|---|---|---|
| ROB_WATERMARK | 37 | Normal operation, ROB depth sizing |
| Timeout threshold | 76 | REF-stalled (REFab precondition, option A: let in-flight CAS complete) |
| Worst-case timeout | 84 | REF mid-sequence interrupt (option B: abandon and restart) |

**Recommendation (locked):** implement option A — let in-flight ACT's CAS complete, then honor REF. Costs max tRCD (4 cycles) extra vs REF-immediately, saves PRE+ACT+tRCD restart.

---

## 10. Init FSM (16 States, DDR5 Sequence)

| State | Action | Exit |
|---|---|---|
| IDLE | Assert RESET_n=0, CKE=0 | INIT_KICK=1 |
| ASSERT_RESET | Hold RESET_n LOW | tINIT1 (200μs) |
| CS_PRE_DEASSERT | CS_n LOW | tINIT2 (10ns) |
| CS_POST_DEASSERT | RESET_n HIGH, CS_n LOW | tINIT3 (4ms) |
| ODT_SETTLE | Raise CKE | tINIT4 (2μs) |
| NOP_BURST | Issue ≥3 NOP/DES | tINIT5 (3 nCK) |
| WAIT_XPR | Count tXPR = max(5nCK, tRFC1+10ns) | timer |
| MPC_DLL_DIVIDER | Issue MPC DLL Divider | issued |
| MPC_DLL_RESET | Issue MPC DLL Reset | issued |
| ZQCAL_START | Issue MPC ZQCAL Start | issued |
| WAIT_tZQCAL | Wait 1μs | timer |
| ZQCAL_LATCH | Issue MPC ZQCAL Latch | issued |
| WAIT_tZQLAT | Wait 30 nCK | timer |
| MRW_BURST | MR0,MR2,MR4,MR5,MR6,MR8,MR32-35,MR58 — one per tMRD | all done |
| TRAINING | CA/CS/WL/RD training, optional | TRAIN_EN bits |
| DONE | Assert init_done, release Scheduler | permanent |

---

## 11. DFI 5.2 Key Signals

| Signal | Dir | Description |
|---|---|---|
| dfi_address[13:0] | MC→PHY | CA bus, 2-cycle for DDR5 ACT |
| dfi_cs_n[1:0] | MC→PHY | Chip select per rank |
| dfi_bg[2:0] | MC→PHY | Bank group |
| dfi_bank[1:0] | MC→PHY | Bank (BA1 unused/tied-0 for 8Gb) |
| dfi_act_n | MC→PHY | Activate indicator |
| dfi_wrdata[127:0] | MC→PHY | Write data |
| dfi_wrdata_en | MC→PHY | Assert PHY_WRLAT cycles before data |
| dfi_wrdata_mask[15:0] | MC→PHY | Write byte mask |
| dfi_rddata[127:0] | PHY→MC | Read data |
| dfi_rddata_valid | PHY→MC | Data valid (no backpressure from MC) |
| dfi_alert_n | PHY→MC | CRC error / CA parity |
| dfi_freq_ratio[1:0] | MC→PHY | 1:1/1:2/1:4 |

**BA1 (MSB of dfi_bank) is unused/tied-0 for 8Gb devices (2 banks/BG). Live for 16Gb+ (4 banks/BG).**

---

## 12. Multi-Rank Architecture

**1 MC core per channel. One channel can have multiple ranks.**

- Bank FSM Table expands to `[N_RANKS][16]` — compile-time parameter `N_RANKS`
- 8 ranks → 128 rows in table. Stage 2 scans all 128.
- Rank selection: `rank` field in CMD packet drives `dfi_cs_n[rank]`
- No rank manager or rank distributor block
- Scheduler emits one command per cycle with rank field set

Additional global fields for cross-rank timing:
- `next_act_same_rank[r]` — tRRD within same rank
- `next_cas_same_rank[r]` — tCCD within same rank
- `gate_rfc[r]` — already specced in legal check matrix

---

## 13. Outstanding ID and Buffer Sizing

**Round-trip latency:** ~37 cycles (row-miss, no REF)
**Freq ratio AXI:MC = 2:1** → ~74 AXI cycles to saturate
**Synopsys standard:** 64 read CAM + 64 write CAM

**Current design:** 32 shared entries (floor/v1)

**AXI client capacity:** 512b/256beats = 16KB max per client. 16KB / 64B = 256 sub-requests per burst. 32 clients × 256 = 8192 potential outstanding — cannot size buffer for this.

**Solution:** throttled burst splitter (Technique 22 from optimizations doc). Burst Splitter holds per-client burst context, meters sub-requests into 64-entry shared pool one at a time as slots free. AXI ARREADY/AWREADY used for natural backpressure.

**64 entries** is the recommended v2 target (matches Synopsys floor).

---

## 14. Config Registers (Key Fields)

| Register | Width | Description |
|---|---|---|
| CL | 7b | CAS Latency |
| CWL | 7b | = CL-2 (DDR5 fixed) |
| tRCD | 8b | RAS-to-CAS delay |
| tRP | 8b | Row Precharge Time |
| tRAS | 9b | Row Active Time min |
| tWR | 8b | Write Recovery |
| tRTP | 6b | Read-to-Precharge |
| tCCD_L | 5b | CAS-to-CAS same BG |
| tCCD_L_WR | 6b | WR-to-WR same BG |
| tCCD_L_WR2 | 6b | WR-to-WR same BG (2nd not RMW) |
| tWTR_L | 6b | WR-to-RD same BG |
| tWTR_S | 5b | WR-to-RD diff BG |
| tRRD_L | 5b | ACT-to-ACT same BG |
| tRRD_S | 4b | ACT-to-ACT diff BG |
| tFAW | 6b | Four-Activate Window |
| tRFC1 | 12b | REFab recovery |
| tRFCsb | 11b | REFsb per-bank recovery |
| tREFI | 14b | Average refresh interval |
| tMRD | 5b | MRW-to-MRW |
| tXP | 5b | PDX-to-command |
| tXS | 12b | SRX-to-command |
| tDLLK | 11b | DLL lock time |
| RAAIMT | 8b | RFM RAA Initial Management Threshold |
| RAAMMT | 8b | RFM RAA Maximum Management Threshold |
| RAADec | 4b | RAA decrement per REF |
| REF_MODE | 2b | 00=REFab, 01=REFsb, 10=FGR-2x, 11=FGR-4x |
| PAGE_POLICY | 2b | 00=Open, 01=Closed, 10=Adaptive |
| AGE_THR1 | 8b | Intra-class HOL bypass threshold (64 cycles default) |
| AGE_THR2 | 8b | Cross-class escalation threshold (256 cycles default) |
| WR_HIGH_WM | 6b | WR mode entry watermark (16 default) |
| WR_LOW_WM | 6b | WR mode exit watermark (4 default) |
| PHY_WRLAT | 6b | dfi_t_phy_wrlat |
| PHY_RDLAT | 6b | dfi_t_rddata_en |
| FREQ_RATIO | 2b | DFI freq ratio 1:1/1:2/1:4 |
| INIT_KICK | 1b | Trigger Init FSM |
| SOFT_RESET | 1b | Synchronous soft-reset all FSMs |

---

## 15. Legal Check Matrix (Stage 2 Gates)

All must be true simultaneously before any command issues:

| Gate | Source | Constraint |
|---|---|---|
| bank_avail[b] | BSM state | Bank not ACTIVATING or PRECHARGING |
| gate_rcd[b] | ACT issue | tRCD: ACT→first CAS |
| gate_rp[b] | PRE issue | tRP: PRE→ACT |
| gate_ras[b] | ACT issue | tRAS: ACT→PRE min |
| gate_ccd_l | Same BG CAS | tCCD_L or tCCD_L_WR or tCCD_L_WR2 |
| gate_ccd_s | Diff BG CAS | tCCD_S = BL/2 = 8nCK |
| gate_rrd_l | Same BG ACT | tRRD_L |
| gate_rrd_s | Diff BG ACT | tRRD_S |
| gate_faw | Sliding window | ≤4 ACTs in tFAW window |
| gate_wtr_l | WR data end, same BG | WL+BL/2+tWTR_L |
| gate_wtr_s | WR data end, diff BG | WL+BL/2+tWTR_S |
| gate_rtw | Last RD cmd | RL+BL/2-WL+2+tWPRE |
| gate_rfc[r] | REF issue per rank | tRFC1: all cmds blocked |
| gate_rfcpb[r][b] | REFsb per bank | tRFCsb: same bank only |
| gate_zqcs | ZQCS issue | All cmds blocked |
| gate_mrd | MRW issue | tMRD: MRW→MRW |
| gate_resp_fifo_avail | Resp FIFO fill | Must have free slot before RD issues |

---

## 16. Open Questions / Unresolved

| Topic | Question |
|---|---|
| Stage 1 age-escalation | Force mid-burst mode flip (interrupt tCCD_L_WR sequence) or priority-only? Recommendation: force-interrupt. |
| Stage 3 tie-break | Exact rule when multiple go-banks in different BGs — unresolved, red-boxed in scheduler diagram |
| RAW Redirect Stage A latency | Adds a cycle to every read (even misses) or combinational parallel with alloc? |
| Duplicate-address write tiebreak | Two valid entries with same {BG,bank,row,col} — need "newest wins" not "lowest idx wins" |
| Column granularity confirmation | Stage A includes column in exact match key — confirms different columns = no match |
| 3rd collision in Hold-Forward | hold_slot[1:0] full + new collision same cycle — 3rd slot needed or rate-limited by construction? |
| REF mid-sequence behavior | Does ref_urgent interrupt bank mid-RCD-wait (→ 84-cycle worst case) or wait for in-flight CAS (→ 76-cycle)? Recommend option A (wait). |
| Req FIFO valid/ready vs credit | Not decided — affects AXI AWREADY/ARREADY backpressure semantics |
| XOR address hashing | ADR-0002 open — BG0=A14 XOR A18, etc. — deferred |
| Runtime DIMM discovery | SPD I²C reader integration — out of scope current phase |
| ROB=32 vs 256 outstanding/client | Mismatch noted — throttled burst splitter resolves it but ROB itself still 32 |

---

## 17. Compile-Time Config Profiles (SystemVerilog)

```systemverilog
// Desktop (35b, 32GB, 2ch, 2rank)
parameter ADDR_WIDTH  = 35;
parameter CH_BITS     = 1;
parameter RANK_BITS   = 1;
parameter N_RANKS     = 2;
parameter BG_BITS     = 3;
parameter BANK_BITS   = 2;
parameter ROW_BITS    = 16;
parameter COL_BITS    = 10;
parameter SUBCH_BITS  = 1;
parameter OFFSET_BITS = 2;
parameter BUF_DEPTH   = 32;
parameter GC_WIDTH    = 20;

// Enterprise (40b, 1TB, 4ch, 8rank)
parameter ADDR_WIDTH  = 40;
parameter CH_BITS     = 2;
parameter RANK_BITS   = 3;
parameter N_RANKS     = 8;
parameter BG_BITS     = 3;
parameter BANK_BITS   = 2;
parameter ROW_BITS    = 18;
parameter COL_BITS    = 11;
parameter SUBCH_BITS  = 1;
parameter OFFSET_BITS = 2;
parameter BUF_DEPTH   = 64;
parameter GC_WIDTH    = 20;

// JEDEC Max (41b, 2TB, 8ch, 8rank)
parameter ADDR_WIDTH  = 41;
parameter CH_BITS     = 3;
parameter RANK_BITS   = 3;
parameter N_RANKS     = 8;
parameter BG_BITS     = 3;
parameter BANK_BITS   = 2;
parameter ROW_BITS    = 18;
parameter COL_BITS    = 11;
parameter SUBCH_BITS  = 1;
parameter OFFSET_BITS = 2;
parameter BUF_DEPTH   = 64;
parameter GC_WIDTH    = 20;
```

---

## 18. FSM Count Summary

| FSM | States | Instances |
|---|---|---|
| Init FSM | 16 | 1 |
| Bank State Machine | 11 | 16 × N_RANKS |
| Arbitration Logic (mode FSM) | 6 | 1 |
| Command Selector | 4 | 1 |
| Refresh Scheduler | 7 | 1 |
| ZQcal FSM | 7 | 1 |
| RFM FSM | 6 | 1 |
| Power Management FSM | 10 | 1 |
| Write CRC Error FSM | 4 | 1 |
| ECS FSM | 4 | 1 |
| **Total (single rank)** | **~75** | **23** |

---

## 19. Documents Produced (all in outputs/)

| File | Description | Pages |
|---|---|---|
| DDR5_Command_Timing.csv | 198-row DDR5 command-to-command timing table | — |
| DDR4_Command_Timing.csv | 197-row DDR4 equivalent | — |
| RMC_Design_Specification.pdf | Full system spec — CIF, MC Core, DRAM Domain, DFI | 18 |
| rmc_pipeline_walkthrough.pdf | Read path + Write path worked example (CL=3,CWL=1,BL16) | 14 |
| rmc_mc_core_blocks.pdf | Internal block field definitions (post-CDC) | 13 |
| rmc_raw_redirect_cam.pdf | RAW Redirect, CAM theory, Hold-Forward spec | 9 |
| rmc_design_optimizations.pdf | 35 named design techniques (15 block-level + 20 scalability) | 40 |

---

## 20. Architecture Rating

| Scope | Rating |
|---|---|
| What's built (buffers, bank table, RAW redirect, timing model) | **9/10** |
| Full architecture including unfinished parts | **7.5-8/10** vs industry standard |
| Vs typical capstone MC project | **Significantly above** — CAM-based forwarding, BG-aware scheduling, absolute-deadline timing model all match Synopsys/ARM/Cadence patterns |

---

## 21. Next Steps (Priority Order)

1. Maintenance Engine — draw into block diagram (Model A, peer block), spec 4 sub-FSM interfaces into Bank FSM Table
2. Stage 0 — can now be defined (depends on Maintenance Engine outputs)
3. Stage 1 — resolve age-escalation tradeoff (force-interrupt vs priority-only)
4. Stage 3 tie-break — define exact rule
5. RAW Redirect — patch §3 (partial-hit-with-gaps must stall not degrade-to-DRAM)
6. 32b→20b global_counter fix in mc_v0_1.png diagram
7. Throttled burst splitter — per-client burst context state machine
8. Address mapping doc (ADR-0002 formalization + XOR hashing option)
9. Python address-map hash optimizer script (Mess dataset, parameterized config tool)
