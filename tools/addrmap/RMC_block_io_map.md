# RMC — Complete Block I/O Map
## All blocks, all ports, all table fields
---

## 0. Signal Convention

```
→   input to block
←   output from block
↔   bidirectional
GC_WIDTH = 20b
all widths parameterized unless stated
```

---

## 1. CIF (AXI Clock Domain)

### 1A. AXI Write Port
```
→ AWID    [AXI_ID_WIDTH]
→ AWADDR  [ADDR_WIDTH]
→ AWLEN   [7:0]
→ AWSIZE  [2:0]
→ AWBURST [1:0]
→ AWVALID
← AWREADY

→ WID     [AXI_ID_WIDTH]
→ WDATA   [63:0]
→ WSTRB   [7:0]
→ WLAST
→ WVALID
← WREADY

← BID     [AXI_ID_WIDTH]
← BRESP   [1:0]
← BVALID
→ BREADY
```

### 1B. AXI Read Port
```
→ ARID    [AXI_ID_WIDTH]
→ ARADDR  [ADDR_WIDTH]
→ ARLEN   [7:0]
→ ARSIZE  [2:0]
→ ARBURST [1:0]
→ ARVALID
← ARREADY

← RID     [AXI_ID_WIDTH]
← RDATA   [63:0]
← RRESP   [1:0]
← RLAST
← RVALID
→ RREADY
```

### 1C. Burst Splitter
```
→ raw_addr        [ADDR_WIDTH]
→ raw_len         [7:0]
→ raw_id          [AXI_ID_WIDTH]
→ raw_type        1b
← split_addr[]    [ADDR_WIDTH]    one per BL16 chunk
← split_id        [AXI_ID_WIDTH]
← split_valid
→ split_ready
```

### 1D. Address Translator
```
→ byte_addr       [ADDR_WIDTH]
← ch              [CH_BITS]
← rank            [RANK_BITS]
← bg              [BG_BITS]
← bank            [BANK_BITS]
← row             [ROW_BITS]
← col             [COL_BITS]
```

### 1E. Reorder Buffer (ROB)
```
→ alloc_id        [AXI_ID_WIDTH]
→ alloc_seqnum    [7:0]
← rob_slot        [4:0]
→ retire_id       [AXI_ID_WIDTH]
→ retire_data     [511:0]
← rd_data_out     [511:0]
← rd_last
← rob_full
```

### 1F. Merge Logic
```
→ frag_data       [511:0]
→ frag_mask       [63:0]
→ frag_id         [AXI_ID_WIDTH]
→ frag_seqnum     [7:0]
← merged_data     [511:0]
← merged_valid
```

---

## 2. Async Request FIFO (CIF → MC Core)

### Packet format
```
req_type   1b        0=RD, 1=WR
axi_id     [AXI_ID_WIDTH]
addr       [ADDR_WIDTH]
data       [511:0]   WR only
mask       [63:0]    WR only
```

### Ports
```
← wr_en           (CIF side write)
← wr_data         [packet width]
→ wr_full
→ rd_en           (MC side read)
← rd_data         [packet width]
→ rd_empty
```

---

## 3. Async Response FIFO (MC Core → CIF)

### Packet format
```
resp_type  2b        00=RD_DATA, 01=WR_ACK, 10=ERR
axi_id     [AXI_ID_WIDTH]
data       [511:0]   RD only
status     [3:0]     0=OK
```

### Ports
```
← wr_en           (MC side write)
← wr_data         [packet width]
→ wr_full
→ gate_resp_fifo_avail   1b   (free unreserved slot exists)
→ rd_en           (CIF side read)
← rd_data         [packet width]
→ rd_empty
```

**valid-only: no ready from CIF. MC checks gate_resp_fifo_avail before every RD issue.**

---

## 4. Write Data Buffer (SRAM)

### Fields (32 entries, 576b/entry)
```
data   [511:0]
mask   [63:0]
```

### Ports
```
→ wr_idx          [4:0]
→ wr_data         [511:0]
→ wr_mask         [63:0]
→ wr_en
→ rd_idx          [4:0]
← rd_data         [511:0]
← rd_mask         [63:0]
```

**random access, not FIFO. index = data_buf_idx from WR TCAM entry.**

---

## 5. WR_TCAM (Write Address CAM)

### Entry fields (N_WR_ENTRIES, no valid/ts)
```
bg           [BG_BITS]
bank         [BANK_BITS]
row          [ROW_BITS]
col          [COL_BITS]
req_type     1b          always WR=1
axi_id       [AXI_ID_WIDTH]
entry_idx    [$clog2(N_WR_ENTRIES)]   → indexes wr_status_reg
data_buf_idx [4:0]                    optional, → Write Data Buffer
```

### Ports
```
→ wr_alloc_en
→ wr_alloc_data  [entry width]
→ wr_alloc_idx   [$clog2(N_WR_ENTRIES)]

→ raw_search_key [BG_BITS+BANK_BITS+ROW_BITS+COL_BITS]
← raw_hit_vector [N_WR_ENTRIES-1:0]   masked by wr_status_valid
← raw_hit_entry  [entry width]        newest age winner

→ sched_search_key [BG_BITS+BANK_BITS]   ternary
← sched_hit_bitmap [N_WR_ENTRIES-1:0]
← sched_hit_meta   per bank: {row, col, req_type, entry_idx}

→ retire_idx     [$clog2(N_WR_ENTRIES)]
→ retire_en
```

**valid gating: raw_hit_vector[i] AND wr_status_reg[i].valid**

---

## 6. RD_TCAM (Read Address CAM)

### Entry fields (N_RD_ENTRIES)
```
bg           [BG_BITS]
bank         [BANK_BITS]
row          [ROW_BITS]
col          [COL_BITS]
req_type     1b          always RD=0
axi_id       [AXI_ID_WIDTH]
entry_idx    [$clog2(N_RD_ENTRIES)]   → indexes rd_status_reg
```

### Ports
```
→ rd_alloc_en
→ rd_alloc_data  [entry width]
→ rd_alloc_idx   [$clog2(N_RD_ENTRIES)]

→ sched_search_key [BG_BITS+BANK_BITS]   ternary
← sched_hit_bitmap [N_RD_ENTRIES-1:0]
← sched_hit_meta   per bank: {row, col, req_type, entry_idx}

→ retire_idx     [$clog2(N_RD_ENTRIES)]
→ retire_en
```

**valid gating: sched_hit_bitmap[i] AND rd_status_reg[i].valid**

---

## 7. WR Status Register File

### Entry fields (N_WR_ENTRIES)
```
valid    1b
status   2b    00=PENDING 01=ISSUED 10=DONE 11=ERROR
age      [GC_WIDTH]    allocation timestamp = gc at alloc
```

### Ports
```
→ alloc_idx      [$clog2(N_WR_ENTRIES)]
→ alloc_age      [GC_WIDTH]
→ alloc_en

→ update_idx     [$clog2(N_WR_ENTRIES)]
→ update_status  [1:0]
→ update_en

← rd_valid       [N_WR_ENTRIES-1:0]   all valid bits (scheduler reads)
← rd_status      [N_WR_ENTRIES-1:0][1:0]
← rd_age         [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]

owner: Write Watermark Buffer Manager (R/W)
scheduler: READ ONLY
```

---

## 8. RD Status Register File

### Entry fields (N_RD_ENTRIES)
```
valid    1b
status   2b    00=PENDING 01=ISSUED 10=DONE 11=ERROR
age      [GC_WIDTH]
```

### Ports
```
→ alloc_idx      [$clog2(N_RD_ENTRIES)]
→ alloc_age      [GC_WIDTH]
→ alloc_en

→ update_idx     [$clog2(N_RD_ENTRIES)]
→ update_status  [1:0]
→ update_en

← rd_valid       [N_RD_ENTRIES-1:0]
← rd_status      [N_RD_ENTRIES-1:0][1:0]
← rd_age         [N_RD_ENTRIES-1:0][GC_WIDTH-1:0]

owner: Read Watermark Buffer Manager (R/W)
scheduler: READ ONLY
```

---

## 9. Write Watermark Buffer Manager

```
→ wr_status_valid  [N_WR_ENTRIES-1:0]   from WR status reg
→ wr_status_age    [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ global_cycle     [GC_WIDTH]
→ new_wr_req_valid
→ sched_ack_wr     1b    scheduler issued a WR cmd

← wr_alloc_en
← wr_alloc_idx     [$clog2(N_WR_ENTRIES)]
← wr_status_update_en
← wr_status_update_idx
← wr_status_update_val [1:0]
← wr_count         [$clog2(N_WR_ENTRIES+1)]   to scheduler
← wr_high_wm_hit   1b
← wr_low_wm_hit    1b
← wr_full
← wr_empty
```

---

## 10. Read Watermark Buffer Manager

```
→ rd_status_valid  [N_RD_ENTRIES-1:0]
→ rd_status_age    [N_RD_ENTRIES-1:0][GC_WIDTH-1:0]
→ global_cycle     [GC_WIDTH]
→ new_rd_req_valid
→ sched_ack_rd     1b

← rd_alloc_en
← rd_alloc_idx     [$clog2(N_RD_ENTRIES)]
← rd_status_update_en
← rd_status_update_idx
← rd_status_update_val [1:0]
← rd_count         [$clog2(N_RD_ENTRIES+1)]
← rd_full
← rd_empty
← gate_resp_fifo_avail  1b   passed through to resp FIFO check
```

---

## 11. RAW Bypass Manager

### Stage A — WR_TCAM search
```
→ new_rd_bg        [BG_BITS]
→ new_rd_bank      [BANK_BITS]
→ new_rd_row       [ROW_BITS]
→ new_rd_col       [COL_BITS]
→ new_rd_mask      [63:0]
→ new_rd_age       [GC_WIDTH]

→ wr_tcam_hit_vector  [N_WR_ENTRIES-1:0]
→ wr_tcam_hit_entry   [entry width]
→ wr_status_age       [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ wr_data_buf_data    [511:0]
→ wr_data_buf_mask    [63:0]
```

### Stage B — mask coverage
```
hit valid condition:
  wr_age <= rd_age   (write arrived same or earlier)
  else → not a hit → normal mem_read

coverable = (rd_mask & wr_mask) == rd_mask

cases:
  full hit        → route wr_data → hold_forward
  masked/overlap  → route covered bytes → hold_forward
                    overshoot bytes → drop
  partial gaps    → stall rd, wait wr retire
  no hit / late   → pass rd to scheduler normally
```

### Outputs
```
← raw_hit          1b
← raw_data         [511:0]
← raw_data_mask    [63:0]
← raw_stall_rd     1b
← raw_pass_to_sched 1b
```

---

## 12. Hold and Forward (2-Deep)

```
→ src0_valid
→ src0_data        [resp packet width]   RAW bypass source
→ src1_valid
→ src1_data        [resp packet width]   DRAM return source

← hold_slot[0]    [resp packet width]
← hold_slot[1]    [resp packet width]
← hold_valid[1:0]
← out_valid
← out_data         [resp packet width]
→ resp_fifo_wr_en
→ resp_fifo_wr_data
```

---

## 13. Bank Activity Counter Table

### Entry fields (16 × N_RANKS)
```
count   [$clog2(BUF_DEPTH+1)]
dirty   1b
```

### Ports
```
→ inc_en           [N_RANKS-1:0][15:0]   per bank
→ dec_en           [N_RANKS-1:0][15:0]
→ dirty_set        [N_RANKS-1:0][15:0]   on WR alloc
→ dirty_clr        [N_RANKS-1:0][15:0]   on last WR retire

← count_out        [N_RANKS-1:0][15:0][$clog2(BUF_DEPTH+1)]
← dirty_out        [N_RANKS-1:0][15:0]
← all_idle[rank]   1b    count==0 for all banks in rank
```

---

## 14. Per-Bank FSM Table

### Entry fields (16 × N_RANKS, LOCKED)
```
state        [2:0]
row_open     [ROW_BITS]
next_cas     [GC_WIDTH]
next_pre     [GC_WIDTH]
next_act     [GC_WIDTH]
next_ref     [GC_WIDTH]
can_cas      1b          registered: (gc-next_cas)[19]==0
can_pre      1b          registered
can_act      1b          registered
can_ref      1b          registered
ref_pending  1b          set by Maintenance Engine
```

### Ports
```
→ gc               [GC_WIDTH]   for can_* update every cycle

→ update_en        [N_RANKS-1:0][15:0]
→ update_rank      [RANK_BITS]
→ update_bg        [BG_BITS]
→ update_bank      [BANK_BITS]
→ update_state     [2:0]
→ update_row_open  [ROW_BITS]
→ update_next_cas  [GC_WIDTH]
→ update_next_pre  [GC_WIDTH]
→ update_next_act  [GC_WIDTH]
→ update_next_ref  [GC_WIDTH]
→ set_ref_pending  [N_RANKS-1:0][15:0]
→ clr_ref_pending  [N_RANKS-1:0][15:0]

← state_out        [N_RANKS-1:0][15:0][2:0]
← row_open_out     [N_RANKS-1:0][15:0][ROW_BITS-1:0]
← can_cas_out      [N_RANKS-1:0][15:0]
← can_pre_out      [N_RANKS-1:0][15:0]
← can_act_out      [N_RANKS-1:0][15:0]
← can_ref_out      [N_RANKS-1:0][15:0]
← ref_pending_out  [N_RANKS-1:0][15:0]
← next_cas_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
← next_pre_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
← next_act_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]

writer: Scheduler Stage 4 + Maintenance Engine
reader: Scheduler Stage 2
```

---

## 15. Per-Rank FSM Table

### Entry fields (N_RANKS, LOCKED)
```
state        [2:0]
next_rfc     [GC_WIDTH]
next_zq      [GC_WIDTH]
next_xp      [GC_WIDTH]
next_xs      [GC_WIDTH]
next_trefi   [GC_WIDTH]
next_zqcs    [GC_WIDTH]
can_rfc      1b
can_zq       1b
can_xp       1b
can_xs       1b
gate_rfc     1b
gate_zq      1b
ref_credits  [3:0]
raa[16]      [6:0] × 16
```

### Ports
```
→ gc               [GC_WIDTH]

→ update_rank      [RANK_BITS]
→ update_state     [2:0]
→ update_next_rfc  [GC_WIDTH]
→ update_next_zq   [GC_WIDTH]
→ update_next_xp   [GC_WIDTH]
→ update_next_xs   [GC_WIDTH]
→ update_next_trefi [GC_WIDTH]
→ update_next_zqcs [GC_WIDTH]
→ set_gate_rfc     [N_RANKS-1:0]
→ clr_gate_rfc     [N_RANKS-1:0]
→ set_gate_zq      [N_RANKS-1:0]
→ clr_gate_zq      [N_RANKS-1:0]
→ inc_ref_credits  [N_RANKS-1:0]
→ dec_ref_credits  [N_RANKS-1:0]
→ raa_inc_en       [N_RANKS-1:0][15:0]
→ raa_dec_val      [3:0]
→ raa_dec_en       [N_RANKS-1:0][15:0]

← state_out        [N_RANKS-1:0][2:0]
← gate_rfc_out     [N_RANKS-1:0]
← gate_zq_out      [N_RANKS-1:0]
← ref_credits_out  [N_RANKS-1:0][3:0]
← raa_out          [N_RANKS-1:0][15:0][6:0]
← can_rfc_out      [N_RANKS-1:0]
← can_xp_out       [N_RANKS-1:0]
← can_xs_out       [N_RANKS-1:0]
← next_trefi_out   [N_RANKS-1:0][GC_WIDTH-1:0]
← next_zqcs_out    [N_RANKS-1:0][GC_WIDTH-1:0]

writer: Maintenance Engine
reader: Maintenance Engine + Scheduler Stage 0
```

---

## 16. Global Timing Table

### Fields (1 instance, LOCKED)
```
global_state     [2:0]
next_act_any     [GC_WIDTH]
next_cas_any     [GC_WIDTH]
next_rd_wr       [GC_WIDTH]
next_wr_rd       [GC_WIDTH]
faw_window[4]    [GC_WIDTH] × 4
next_act_bg[8]   [GC_WIDTH] × 8
next_cas_bg[8]   [GC_WIDTH] × 8
next_wtr_bg[8]   [GC_WIDTH] × 8
last_act_bg[8]   [GC_WIDTH] × 8
can_act_any      1b
can_cas_any      1b
can_rd_wr        1b
can_wr_rd        1b
can_faw          1b
can_act_bg[8]    1b × 8
can_cas_bg[8]    1b × 8
can_wtr_bg[8]    1b × 8
```

### Ports
```
→ gc               [GC_WIDTH]

→ update_act_any   [GC_WIDTH]
→ update_cas_any   [GC_WIDTH]
→ update_rd_wr     [GC_WIDTH]
→ update_wr_rd     [GC_WIDTH]
→ update_faw       [GC_WIDTH]      shift in new ACT timestamp
→ update_act_bg    [BG_BITS + GC_WIDTH]
→ update_cas_bg    [BG_BITS + GC_WIDTH]
→ update_wtr_bg    [BG_BITS + GC_WIDTH]
→ update_last_act_bg [BG_BITS + GC_WIDTH]
→ update_global_state [2:0]

← can_act_any_out  1b
← can_cas_any_out  1b
← can_rd_wr_out    1b
← can_wr_rd_out    1b
← can_faw_out      1b
← can_act_bg_out   [7:0]
← can_cas_bg_out   [7:0]
← can_wtr_bg_out   [7:0]
← last_act_bg_out  [7:0][GC_WIDTH-1:0]
← global_state_out [2:0]

writer: Scheduler Stage 4
reader: Scheduler Stage 2
```

---

## 17. timing_reg_file

### Fields
```
param_id → nCK value
addressed by timing_param_e enum (5b, up to 32 params)
width per entry: 14b (max tREFI)
```

### Params
```
T_RCD, T_RP, T_RAS, T_WR, T_RTP
T_CCD_L, T_CCD_L_WR, T_CCD_L_WR2
T_WTR_L, T_WTR_S
T_RRD_L, T_RRD_S
T_FAW
T_RFC1, T_RFCsb
T_REFI
T_MRD, T_XP, T_XS, T_DLLK
T_ZQCAL, T_ZQLAT
T_RTW
```

### Ports
```
→ param_id[]       [4:0] × N_read_ports
← param_val[]      [13:0] × N_read_ports   combinational

→ csr_wr_en
→ csr_param_id     [4:0]
→ csr_param_val    [13:0]

cmd → timing_update_vector (parallel):
  ACT    → T_RCD, T_RAS, T_RRD_L, T_RRD_S, T_FAW
  CAS_RD → T_CCD_L, T_CCD_S, T_RTP, T_WTR_L, T_WTR_S, T_RTW
  CAS_WR → T_CCD_L_WR, T_CCD_L_WR2, T_WR, T_WTR_L, T_WTR_S
  PRE    → T_RP
  REFab  → T_RFC1
  REFsb  → T_RFCsb

read: combinational, multi-port
write: CSR only (slow path, init time)
```

---

## 18. Global Cycle Counter

```
← gc               [GC_WIDTH]   free-running 20b counter
→ clk
→ rst_n            sync reset on SOFT_RESET only
```

---

## 19. Scheduler (5 Stages)

### Stage 0 — Maintenance Override
```
→ ref_urgent       1b
→ ref_due          1b
→ zq_due           1b
→ rfm_req          [N_RANKS-1:0][15:0]
→ global_state     [2:0]

← s0_override      1b
← s0_cmd_type      [2:0]
← s0_rank          [RANK_BITS]
← s0_bg            [BG_BITS]
← s0_bank          [BANK_BITS]
```

### Stage 1 — TCAM Search
```
→ wr_tcam_hit_bitmap  [N_WR_ENTRIES-1:0]
→ wr_tcam_hit_meta    per bank
→ rd_tcam_hit_bitmap  [N_RD_ENTRIES-1:0]
→ rd_tcam_hit_meta    per bank
→ wr_status_valid     [N_WR_ENTRIES-1:0]
→ rd_status_valid     [N_RD_ENTRIES-1:0]

← s1_hit_bitmap    [N_BANKS-1:0]    gated by valid
← s1_hit_meta[]    per bank: {row, col, req_type, entry_idx, axi_id}
```

### Stage 2 — can_* Gate Check + Cost Classification
```
→ s1_hit_bitmap    [N_BANKS-1:0]
→ s1_hit_meta[]
→ can_cas_out      [N_RANKS-1:0][15:0]
→ can_pre_out      [N_RANKS-1:0][15:0]
→ can_act_out      [N_RANKS-1:0][15:0]
→ can_act_bg_out   [7:0]
→ can_act_any_out  1b
→ can_cas_bg_out   [7:0]
→ can_cas_any_out  1b
→ can_rd_wr_out    1b
→ can_wr_rd_out    1b
→ can_faw_out      1b
→ gate_rfc_out     [N_RANKS-1:0]
→ gate_zq_out      [N_RANKS-1:0]
→ state_out        [N_RANKS-1:0][15:0][2:0]
→ row_open_out     [N_RANKS-1:0][15:0][ROW_BITS-1:0]
→ next_cas_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
→ next_pre_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
→ next_act_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
→ gc               [GC_WIDTH]

← hit_set_bitmap   [N_BANKS-1:0]
← miss_set_bitmap  [N_BANKS-1:0]
← remaining_cost[] [GC_WIDTH] per bank
```

### Stage 3 — SJF Winner Selection
```
→ hit_set_bitmap
→ miss_set_bitmap
→ remaining_cost[]
→ rd_status_age    [N_RD_ENTRIES-1:0][GC_WIDTH-1:0]
→ wr_status_age    [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ gc               [GC_WIDTH]
→ wr_count         [$clog2(N_WR_ENTRIES+1)]
→ wr_high_wm_hit   1b
→ wr_low_wm_hit    1b
→ last_act_bg_out  [7:0][GC_WIDTH-1:0]

← winner_valid     1b
← winner_cmd_type  [2:0]   ACT/CAS_RD/CAS_WR/PRE
← winner_rank      [RANK_BITS]
← winner_bg        [BG_BITS]
← winner_bank      [BANK_BITS]
← winner_row       [ROW_BITS]
← winner_col       [COL_BITS]
← winner_entry_idx [$clog2(BUF_DEPTH)]
← winner_req_type  1b
```

### Stage 4 — Command Emission + Writebacks
```
→ winner_*         (all winner fields from Stage 3)
→ s0_override      1b
→ s0_cmd_*         (maintenance cmd fields)
→ timing_reg_vals  (from timing_reg_file, parallel)
→ gc               [GC_WIDTH]

← dfi_address      [13:0]
← dfi_cs_n         [1:0]
← dfi_bg           [2:0]
← dfi_bank         [1:0]
← dfi_act_n        1b
← dfi_wrdata       [127:0]
← dfi_wrdata_en    1b
← dfi_wrdata_mask  [15:0]

← bank_fsm_update_en
← bank_fsm_update_* (state, next_cas, next_pre, next_act, row_open)
← global_timing_update_* (next_act_any, next_cas_any, faw, bg arrays)
← status_update_en
← status_update_idx
← status_update_val [1:0]

← sched_ack        1b    → Maintenance Engine
← raa_inc_en       [N_RANKS-1:0][15:0]   → Per-Rank FSM (RAA++)
```

---

## 20. Maintenance Engine

### Refresh FSM
```
→ gc               [GC_WIDTH]
→ next_trefi_out   [N_RANKS-1:0][GC_WIDTH-1:0]
→ ref_credits_out  [N_RANKS-1:0][3:0]
→ bank_act_count   [N_RANKS-1:0][15:0][$clog2(BUF_DEPTH+1)]
→ all_idle         [N_RANKS-1:0]
→ sched_ack        1b
→ REF_MODE         [1:0]   CSR

← ref_urgent       1b
← ref_due          1b
← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← me_cmd_bg        [BG_BITS]
← me_cmd_bank      [BANK_BITS]
← set_gate_rfc     [N_RANKS-1:0]
← clr_gate_rfc     [N_RANKS-1:0]
← inc_ref_credits  [N_RANKS-1:0]
← dec_ref_credits  [N_RANKS-1:0]
← update_next_trefi [RANK_BITS + GC_WIDTH]
← set_ref_pending  [N_RANKS-1:0][15:0]
← clr_ref_pending  [N_RANKS-1:0][15:0]
```

### ZQcal FSM
```
→ gc               [GC_WIDTH]
→ next_zqcs_out    [N_RANKS-1:0][GC_WIDTH-1:0]
→ all_idle         [N_RANKS-1:0]
→ sched_ack        1b

← zq_due           1b
← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← set_gate_zq      [N_RANKS-1:0]
← clr_gate_zq      [N_RANKS-1:0]
← update_next_zqcs [RANK_BITS + GC_WIDTH]
```

### RFM FSM
```
→ gc               [GC_WIDTH]
→ raa_out          [N_RANKS-1:0][15:0][6:0]
→ RAAIMT           [7:0]   CSR
→ sched_ack        1b
→ raa_inc_en       [N_RANKS-1:0][15:0]   from Stage 4

← rfm_req          [N_RANKS-1:0][15:0]
← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← me_cmd_bg        [BG_BITS]
← me_cmd_bank      [BANK_BITS]
← raa_dec_en       [N_RANKS-1:0][15:0]
← raa_dec_val      [3:0]
```

### Power Management FSM
```
→ gc               [GC_WIDTH]
→ all_idle         [N_RANKS-1:0]
→ bank_act_count   [N_RANKS-1:0][15:0]
→ pd_en            1b   CSR
→ sr_entry         1b   system signal
→ sr_exit          1b   system signal
→ can_xp_out       [N_RANKS-1:0]
→ can_xs_out       [N_RANKS-1:0]
→ sched_ack        1b

← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← update_next_xp   [RANK_BITS + GC_WIDTH]
← update_next_xs   [RANK_BITS + GC_WIDTH]
← rank_state_update [RANK_BITS + 2:0]
```

---

## 21. Init FSM

```
→ clk
→ rst_n
→ INIT_KICK        1b   CSR
→ TRAIN_EN         1b   CSR
→ gc               [GC_WIDTH]
→ timing_reg_vals  (tINIT1..tDLLK from timing_reg_file)

← dfi_address      [13:0]
← dfi_cs_n         [1:0]
← dfi_act_n        1b
← dfi_wrdata       [127:0]   MRW data
← dfi_wrdata_en    1b
← init_done        1b   → Global FSM, releases Scheduler
← global_state_req [2:0]   INIT state assertion
```

---

## 22. Write Data Path

```
→ wr_data_buf_data [511:0]   from Write Data Buffer
→ wr_data_buf_mask [63:0]
→ CWL              [6:0]   CSR
→ PHY_WRLAT        [5:0]   CSR
→ gc               [GC_WIDTH]

← dfi_wrdata       [127:0]
← dfi_wrdata_en    1b
← dfi_wrdata_mask  [15:0]
← crc_err_flag     1b   → error handler
```

---

## 23. Read Data Path

```
→ dfi_rddata       [127:0]
→ dfi_rddata_valid 1b
→ PHY_RDLAT        [5:0]   CSR
→ CL               [6:0]   CSR
→ gc               [GC_WIDTH]
→ rd_entry_idx     [$clog2(N_RD_ENTRIES)]   expected return tag

← rd_data_out      [511:0]
← rd_data_valid    1b
← rd_axi_id        [AXI_ID_WIDTH]
← ecc_err_flag     1b   → error handler
← crc_err_flag     1b   → error handler
```

---

## 24. Error Handler

```
→ scheduler_error  1b
→ dfi_alert_n      1b   CRC/CA parity from PHY
→ crc_err_wr       1b   from Write Data Path
→ ecc_err_rd       1b   from Read Data Path
→ crc_err_rd       1b   from Read Data Path

← err_status_reg   [7:0]
← err_interrupt    1b   → system
← err_cmd          [2:0]   recovery action
```

---

## 25. Buffer Sizing Summary (Locked)

```
N_WR_ENTRIES:  64 (v1), 96 (v2, 3x RD)
N_RD_ENTRIES:  32 (v1 and v2)
Write Data Buffer: 32 entries × 576b
BUF_DEPTH:     max(N_WR_ENTRIES, N_RD_ENTRIES)

rationale:
  larger WR buffer → scheduler drains WR in background
  RD sees less blocking → lower read latency
  bandwidth unchanged
  WR_TCAM sized to N_WR_ENTRIES
  RD_TCAM sized to N_RD_ENTRIES
```

---

## 26. Ownership Summary

| Block | Owner (R/W) | Scheduler access |
|---|---|---|
| WR Status Reg | Write Watermark Manager | READ ONLY |
| RD Status Reg | Read Watermark Manager | READ ONLY |
| WR_TCAM | Write Watermark Manager | READ ONLY (search) |
| RD_TCAM | Read Watermark Manager | READ ONLY (search) |
| Write Data Buffer | Write Watermark Manager | READ ONLY (emit) |
| Per-Bank FSM Table | Scheduler Stage 4 + Maint Engine | WRITE (S4), READ (S2) |
| Per-Rank FSM Table | Maintenance Engine | READ (S0) |
| Global Timing Table | Scheduler Stage 4 | READ (S2) |
| Bank Activity Counter | WR/RD Watermark Managers | READ (Maint Engine, Power Mgmt) |
| timing_reg_file | CSR (init time) | READ ONLY |
| Global Cycle Counter | Free-running | READ all blocks |
ENDOFFILEcat > /home/claude/RMC_IO_Map.md << 'ENDOFFILE'
# RMC — Complete Block I/O Map
## All blocks, all ports, all table fields
---

## 0. Signal Convention

```
→   input to block
←   output from block
↔   bidirectional
GC_WIDTH = 20b
all widths parameterized unless stated
```

---

## 1. CIF (AXI Clock Domain)

### 1A. AXI Write Port
```
→ AWID    [AXI_ID_WIDTH]
→ AWADDR  [ADDR_WIDTH]
→ AWLEN   [7:0]
→ AWSIZE  [2:0]
→ AWBURST [1:0]
→ AWVALID
← AWREADY

→ WID     [AXI_ID_WIDTH]
→ WDATA   [63:0]
→ WSTRB   [7:0]
→ WLAST
→ WVALID
← WREADY

← BID     [AXI_ID_WIDTH]
← BRESP   [1:0]
← BVALID
→ BREADY
```

### 1B. AXI Read Port
```
→ ARID    [AXI_ID_WIDTH]
→ ARADDR  [ADDR_WIDTH]
→ ARLEN   [7:0]
→ ARSIZE  [2:0]
→ ARBURST [1:0]
→ ARVALID
← ARREADY

← RID     [AXI_ID_WIDTH]
← RDATA   [63:0]
← RRESP   [1:0]
← RLAST
← RVALID
→ RREADY
```

### 1C. Burst Splitter
```
→ raw_addr        [ADDR_WIDTH]
→ raw_len         [7:0]
→ raw_id          [AXI_ID_WIDTH]
→ raw_type        1b
← split_addr[]    [ADDR_WIDTH]    one per BL16 chunk
← split_id        [AXI_ID_WIDTH]
← split_valid
→ split_ready
```

### 1D. Address Translator
```
→ byte_addr       [ADDR_WIDTH]
← ch              [CH_BITS]
← rank            [RANK_BITS]
← bg              [BG_BITS]
← bank            [BANK_BITS]
← row             [ROW_BITS]
← col             [COL_BITS]
```

### 1E. Reorder Buffer (ROB)
```
→ alloc_id        [AXI_ID_WIDTH]
→ alloc_seqnum    [7:0]
← rob_slot        [4:0]
→ retire_id       [AXI_ID_WIDTH]
→ retire_data     [511:0]
← rd_data_out     [511:0]
← rd_last
← rob_full
```

### 1F. Merge Logic
```
→ frag_data       [511:0]
→ frag_mask       [63:0]
→ frag_id         [AXI_ID_WIDTH]
→ frag_seqnum     [7:0]
← merged_data     [511:0]
← merged_valid
```

---

## 2. Async Request FIFO (CIF → MC Core)

### Packet format
```
req_type   1b        0=RD, 1=WR
axi_id     [AXI_ID_WIDTH]
addr       [ADDR_WIDTH]
data       [511:0]   WR only
mask       [63:0]    WR only
```

### Ports
```
← wr_en           (CIF side write)
← wr_data         [packet width]
→ wr_full
→ rd_en           (MC side read)
← rd_data         [packet width]
→ rd_empty
```

---

## 3. Async Response FIFO (MC Core → CIF)

### Packet format
```
resp_type  2b        00=RD_DATA, 01=WR_ACK, 10=ERR
axi_id     [AXI_ID_WIDTH]
data       [511:0]   RD only
status     [3:0]     0=OK
```

### Ports
```
← wr_en           (MC side write)
← wr_data         [packet width]
→ wr_full
→ gate_resp_fifo_avail   1b   (free unreserved slot exists)
→ rd_en           (CIF side read)
← rd_data         [packet width]
→ rd_empty
```

**valid-only: no ready from CIF. MC checks gate_resp_fifo_avail before every RD issue.**

---

## 4. Write Data Buffer (SRAM)

### Fields (32 entries, 576b/entry)
```
data   [511:0]
mask   [63:0]
```

### Ports
```
→ wr_idx          [4:0]
→ wr_data         [511:0]
→ wr_mask         [63:0]
→ wr_en
→ rd_idx          [4:0]
← rd_data         [511:0]
← rd_mask         [63:0]
```

**random access, not FIFO. index = data_buf_idx from WR TCAM entry.**

---

## 5. WR_TCAM (Write Address CAM)

### Entry fields (N_WR_ENTRIES, no valid/ts)
```
bg           [BG_BITS]
bank         [BANK_BITS]
row          [ROW_BITS]
col          [COL_BITS]
req_type     1b          always WR=1
axi_id       [AXI_ID_WIDTH]
entry_idx    [$clog2(N_WR_ENTRIES)]   → indexes wr_status_reg
data_buf_idx [4:0]                    optional, → Write Data Buffer
```

### Ports
```
→ wr_alloc_en
→ wr_alloc_data  [entry width]
→ wr_alloc_idx   [$clog2(N_WR_ENTRIES)]

→ raw_search_key [BG_BITS+BANK_BITS+ROW_BITS+COL_BITS]
← raw_hit_vector [N_WR_ENTRIES-1:0]   masked by wr_status_valid
← raw_hit_entry  [entry width]        newest age winner

→ sched_search_key [BG_BITS+BANK_BITS]   ternary
← sched_hit_bitmap [N_WR_ENTRIES-1:0]
← sched_hit_meta   per bank: {row, col, req_type, entry_idx}

→ retire_idx     [$clog2(N_WR_ENTRIES)]
→ retire_en
```

**valid gating: raw_hit_vector[i] AND wr_status_reg[i].valid**

---

## 6. RD_TCAM (Read Address CAM)

### Entry fields (N_RD_ENTRIES)
```
bg           [BG_BITS]
bank         [BANK_BITS]
row          [ROW_BITS]
col          [COL_BITS]
req_type     1b          always RD=0
axi_id       [AXI_ID_WIDTH]
entry_idx    [$clog2(N_RD_ENTRIES)]   → indexes rd_status_reg
```

### Ports
```
→ rd_alloc_en
→ rd_alloc_data  [entry width]
→ rd_alloc_idx   [$clog2(N_RD_ENTRIES)]

→ sched_search_key [BG_BITS+BANK_BITS]   ternary
← sched_hit_bitmap [N_RD_ENTRIES-1:0]
← sched_hit_meta   per bank: {row, col, req_type, entry_idx}

→ retire_idx     [$clog2(N_RD_ENTRIES)]
→ retire_en
```

**valid gating: sched_hit_bitmap[i] AND rd_status_reg[i].valid**

---

## 7. WR Status Register File

### Entry fields (N_WR_ENTRIES)
```
valid    1b
status   2b    00=PENDING 01=ISSUED 10=DONE 11=ERROR
age      [GC_WIDTH]    allocation timestamp = gc at alloc
```

### Ports
```
→ alloc_idx      [$clog2(N_WR_ENTRIES)]
→ alloc_age      [GC_WIDTH]
→ alloc_en

→ update_idx     [$clog2(N_WR_ENTRIES)]
→ update_status  [1:0]
→ update_en

← rd_valid       [N_WR_ENTRIES-1:0]   all valid bits (scheduler reads)
← rd_status      [N_WR_ENTRIES-1:0][1:0]
← rd_age         [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]

owner: Write Watermark Buffer Manager (R/W)
scheduler: READ ONLY
```

---

## 8. RD Status Register File

### Entry fields (N_RD_ENTRIES)
```
valid    1b
status   2b    00=PENDING 01=ISSUED 10=DONE 11=ERROR
age      [GC_WIDTH]
```

### Ports
```
→ alloc_idx      [$clog2(N_RD_ENTRIES)]
→ alloc_age      [GC_WIDTH]
→ alloc_en

→ update_idx     [$clog2(N_RD_ENTRIES)]
→ update_status  [1:0]
→ update_en

← rd_valid       [N_RD_ENTRIES-1:0]
← rd_status      [N_RD_ENTRIES-1:0][1:0]
← rd_age         [N_RD_ENTRIES-1:0][GC_WIDTH-1:0]

owner: Read Watermark Buffer Manager (R/W)
scheduler: READ ONLY
```

---

## 9. Write Watermark Buffer Manager

```
→ wr_status_valid  [N_WR_ENTRIES-1:0]   from WR status reg
→ wr_status_age    [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ global_cycle     [GC_WIDTH]
→ new_wr_req_valid
→ sched_ack_wr     1b    scheduler issued a WR cmd

← wr_alloc_en
← wr_alloc_idx     [$clog2(N_WR_ENTRIES)]
← wr_status_update_en
← wr_status_update_idx
← wr_status_update_val [1:0]
← wr_count         [$clog2(N_WR_ENTRIES+1)]   to scheduler
← wr_high_wm_hit   1b
← wr_low_wm_hit    1b
← wr_full
← wr_empty
```

---

## 10. Read Watermark Buffer Manager

```
→ rd_status_valid  [N_RD_ENTRIES-1:0]
→ rd_status_age    [N_RD_ENTRIES-1:0][GC_WIDTH-1:0]
→ global_cycle     [GC_WIDTH]
→ new_rd_req_valid
→ sched_ack_rd     1b

← rd_alloc_en
← rd_alloc_idx     [$clog2(N_RD_ENTRIES)]
← rd_status_update_en
← rd_status_update_idx
← rd_status_update_val [1:0]
← rd_count         [$clog2(N_RD_ENTRIES+1)]
← rd_full
← rd_empty
← gate_resp_fifo_avail  1b   passed through to resp FIFO check
```

---

## 11. RAW Bypass Manager

### Stage A — WR_TCAM search
```
→ new_rd_bg        [BG_BITS]
→ new_rd_bank      [BANK_BITS]
→ new_rd_row       [ROW_BITS]
→ new_rd_col       [COL_BITS]
→ new_rd_mask      [63:0]
→ new_rd_age       [GC_WIDTH]

→ wr_tcam_hit_vector  [N_WR_ENTRIES-1:0]
→ wr_tcam_hit_entry   [entry width]
→ wr_status_age       [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ wr_data_buf_data    [511:0]
→ wr_data_buf_mask    [63:0]
```

### Stage B — mask coverage
```
hit valid condition:
  wr_age <= rd_age   (write arrived same or earlier)
  else → not a hit → normal mem_read

coverable = (rd_mask & wr_mask) == rd_mask

cases:
  full hit        → route wr_data → hold_forward
  masked/overlap  → route covered bytes → hold_forward
                    overshoot bytes → drop
  partial gaps    → stall rd, wait wr retire
  no hit / late   → pass rd to scheduler normally
```

### Outputs
```
← raw_hit          1b
← raw_data         [511:0]
← raw_data_mask    [63:0]
← raw_stall_rd     1b
← raw_pass_to_sched 1b
```

---

## 12. Hold and Forward (2-Deep)

```
→ src0_valid
→ src0_data        [resp packet width]   RAW bypass source
→ src1_valid
→ src1_data        [resp packet width]   DRAM return source

← hold_slot[0]    [resp packet width]
← hold_slot[1]    [resp packet width]
← hold_valid[1:0]
← out_valid
← out_data         [resp packet width]
→ resp_fifo_wr_en
→ resp_fifo_wr_data
```

---

## 13. Bank Activity Counter Table

### Entry fields (16 × N_RANKS)
```
count   [$clog2(BUF_DEPTH+1)]
dirty   1b
```

### Ports
```
→ inc_en           [N_RANKS-1:0][15:0]   per bank
→ dec_en           [N_RANKS-1:0][15:0]
→ dirty_set        [N_RANKS-1:0][15:0]   on WR alloc
→ dirty_clr        [N_RANKS-1:0][15:0]   on last WR retire

← count_out        [N_RANKS-1:0][15:0][$clog2(BUF_DEPTH+1)]
← dirty_out        [N_RANKS-1:0][15:0]
← all_idle[rank]   1b    count==0 for all banks in rank
```

---

## 14. Per-Bank FSM Table

### Entry fields (16 × N_RANKS, LOCKED)
```
state        [2:0]
row_open     [ROW_BITS]
next_cas     [GC_WIDTH]
next_pre     [GC_WIDTH]
next_act     [GC_WIDTH]
next_ref     [GC_WIDTH]
can_cas      1b          registered: (gc-next_cas)[19]==0
can_pre      1b          registered
can_act      1b          registered
can_ref      1b          registered
ref_pending  1b          set by Maintenance Engine
```

### Ports
```
→ gc               [GC_WIDTH]   for can_* update every cycle

→ update_en        [N_RANKS-1:0][15:0]
→ update_rank      [RANK_BITS]
→ update_bg        [BG_BITS]
→ update_bank      [BANK_BITS]
→ update_state     [2:0]
→ update_row_open  [ROW_BITS]
→ update_next_cas  [GC_WIDTH]
→ update_next_pre  [GC_WIDTH]
→ update_next_act  [GC_WIDTH]
→ update_next_ref  [GC_WIDTH]
→ set_ref_pending  [N_RANKS-1:0][15:0]
→ clr_ref_pending  [N_RANKS-1:0][15:0]

← state_out        [N_RANKS-1:0][15:0][2:0]
← row_open_out     [N_RANKS-1:0][15:0][ROW_BITS-1:0]
← can_cas_out      [N_RANKS-1:0][15:0]
← can_pre_out      [N_RANKS-1:0][15:0]
← can_act_out      [N_RANKS-1:0][15:0]
← can_ref_out      [N_RANKS-1:0][15:0]
← ref_pending_out  [N_RANKS-1:0][15:0]
← next_cas_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
← next_pre_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
← next_act_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]

writer: Scheduler Stage 4 + Maintenance Engine
reader: Scheduler Stage 2
```

---

## 15. Per-Rank FSM Table

### Entry fields (N_RANKS, LOCKED)
```
state        [2:0]
next_rfc     [GC_WIDTH]
next_zq      [GC_WIDTH]
next_xp      [GC_WIDTH]
next_xs      [GC_WIDTH]
next_trefi   [GC_WIDTH]
next_zqcs    [GC_WIDTH]
can_rfc      1b
can_zq       1b
can_xp       1b
can_xs       1b
gate_rfc     1b
gate_zq      1b
ref_credits  [3:0]
raa[16]      [6:0] × 16
```

### Ports
```
→ gc               [GC_WIDTH]

→ update_rank      [RANK_BITS]
→ update_state     [2:0]
→ update_next_rfc  [GC_WIDTH]
→ update_next_zq   [GC_WIDTH]
→ update_next_xp   [GC_WIDTH]
→ update_next_xs   [GC_WIDTH]
→ update_next_trefi [GC_WIDTH]
→ update_next_zqcs [GC_WIDTH]
→ set_gate_rfc     [N_RANKS-1:0]
→ clr_gate_rfc     [N_RANKS-1:0]
→ set_gate_zq      [N_RANKS-1:0]
→ clr_gate_zq      [N_RANKS-1:0]
→ inc_ref_credits  [N_RANKS-1:0]
→ dec_ref_credits  [N_RANKS-1:0]
→ raa_inc_en       [N_RANKS-1:0][15:0]
→ raa_dec_val      [3:0]
→ raa_dec_en       [N_RANKS-1:0][15:0]

← state_out        [N_RANKS-1:0][2:0]
← gate_rfc_out     [N_RANKS-1:0]
← gate_zq_out      [N_RANKS-1:0]
← ref_credits_out  [N_RANKS-1:0][3:0]
← raa_out          [N_RANKS-1:0][15:0][6:0]
← can_rfc_out      [N_RANKS-1:0]
← can_xp_out       [N_RANKS-1:0]
← can_xs_out       [N_RANKS-1:0]
← next_trefi_out   [N_RANKS-1:0][GC_WIDTH-1:0]
← next_zqcs_out    [N_RANKS-1:0][GC_WIDTH-1:0]

writer: Maintenance Engine
reader: Maintenance Engine + Scheduler Stage 0
```

---

## 16. Global Timing Table

### Fields (1 instance, LOCKED)
```
global_state     [2:0]
next_act_any     [GC_WIDTH]
next_cas_any     [GC_WIDTH]
next_rd_wr       [GC_WIDTH]
next_wr_rd       [GC_WIDTH]
faw_window[4]    [GC_WIDTH] × 4
next_act_bg[8]   [GC_WIDTH] × 8
next_cas_bg[8]   [GC_WIDTH] × 8
next_wtr_bg[8]   [GC_WIDTH] × 8
last_act_bg[8]   [GC_WIDTH] × 8
can_act_any      1b
can_cas_any      1b
can_rd_wr        1b
can_wr_rd        1b
can_faw          1b
can_act_bg[8]    1b × 8
can_cas_bg[8]    1b × 8
can_wtr_bg[8]    1b × 8
```

### Ports
```
→ gc               [GC_WIDTH]

→ update_act_any   [GC_WIDTH]
→ update_cas_any   [GC_WIDTH]
→ update_rd_wr     [GC_WIDTH]
→ update_wr_rd     [GC_WIDTH]
→ update_faw       [GC_WIDTH]      shift in new ACT timestamp
→ update_act_bg    [BG_BITS + GC_WIDTH]
→ update_cas_bg    [BG_BITS + GC_WIDTH]
→ update_wtr_bg    [BG_BITS + GC_WIDTH]
→ update_last_act_bg [BG_BITS + GC_WIDTH]
→ update_global_state [2:0]

← can_act_any_out  1b
← can_cas_any_out  1b
← can_rd_wr_out    1b
← can_wr_rd_out    1b
← can_faw_out      1b
← can_act_bg_out   [7:0]
← can_cas_bg_out   [7:0]
← can_wtr_bg_out   [7:0]
← last_act_bg_out  [7:0][GC_WIDTH-1:0]
← global_state_out [2:0]

writer: Scheduler Stage 4
reader: Scheduler Stage 2
```

---

## 17. timing_reg_file

### Fields
```
param_id → nCK value
addressed by timing_param_e enum (5b, up to 32 params)
width per entry: 14b (max tREFI)
```

### Params
```
T_RCD, T_RP, T_RAS, T_WR, T_RTP
T_CCD_L, T_CCD_L_WR, T_CCD_L_WR2
T_WTR_L, T_WTR_S
T_RRD_L, T_RRD_S
T_FAW
T_RFC1, T_RFCsb
T_REFI
T_MRD, T_XP, T_XS, T_DLLK
T_ZQCAL, T_ZQLAT
T_RTW
```

### Ports
```
→ param_id[]       [4:0] × N_read_ports
← param_val[]      [13:0] × N_read_ports   combinational

→ csr_wr_en
→ csr_param_id     [4:0]
→ csr_param_val    [13:0]

cmd → timing_update_vector (parallel):
  ACT    → T_RCD, T_RAS, T_RRD_L, T_RRD_S, T_FAW
  CAS_RD → T_CCD_L, T_CCD_S, T_RTP, T_WTR_L, T_WTR_S, T_RTW
  CAS_WR → T_CCD_L_WR, T_CCD_L_WR2, T_WR, T_WTR_L, T_WTR_S
  PRE    → T_RP
  REFab  → T_RFC1
  REFsb  → T_RFCsb

read: combinational, multi-port
write: CSR only (slow path, init time)
```

---

## 18. Global Cycle Counter

```
← gc               [GC_WIDTH]   free-running 20b counter
→ clk
→ rst_n            sync reset on SOFT_RESET only
```

---

## 19. Scheduler (5 Stages)

### Stage 0 — Maintenance Override
```
→ ref_urgent       1b
→ ref_due          1b
→ zq_due           1b
→ rfm_req          [N_RANKS-1:0][15:0]
→ global_state     [2:0]

← s0_override      1b
← s0_cmd_type      [2:0]
← s0_rank          [RANK_BITS]
← s0_bg            [BG_BITS]
← s0_bank          [BANK_BITS]
```

### Stage 1 — TCAM Search
```
→ wr_tcam_hit_bitmap  [N_WR_ENTRIES-1:0]
→ wr_tcam_hit_meta    per bank
→ rd_tcam_hit_bitmap  [N_RD_ENTRIES-1:0]
→ rd_tcam_hit_meta    per bank
→ wr_status_valid     [N_WR_ENTRIES-1:0]
→ rd_status_valid     [N_RD_ENTRIES-1:0]

← s1_hit_bitmap    [N_BANKS-1:0]    gated by valid
← s1_hit_meta[]    per bank: {row, col, req_type, entry_idx, axi_id}
```

### Stage 2 — can_* Gate Check + Cost Classification
```
→ s1_hit_bitmap    [N_BANKS-1:0]
→ s1_hit_meta[]
→ can_cas_out      [N_RANKS-1:0][15:0]
→ can_pre_out      [N_RANKS-1:0][15:0]
→ can_act_out      [N_RANKS-1:0][15:0]
→ can_act_bg_out   [7:0]
→ can_act_any_out  1b
→ can_cas_bg_out   [7:0]
→ can_cas_any_out  1b
→ can_rd_wr_out    1b
→ can_wr_rd_out    1b
→ can_faw_out      1b
→ gate_rfc_out     [N_RANKS-1:0]
→ gate_zq_out      [N_RANKS-1:0]
→ state_out        [N_RANKS-1:0][15:0][2:0]
→ row_open_out     [N_RANKS-1:0][15:0][ROW_BITS-1:0]
→ next_cas_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
→ next_pre_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
→ next_act_out     [N_RANKS-1:0][15:0][GC_WIDTH-1:0]
→ gc               [GC_WIDTH]

← hit_set_bitmap   [N_BANKS-1:0]
← miss_set_bitmap  [N_BANKS-1:0]
← remaining_cost[] [GC_WIDTH] per bank
```

### Stage 3 — SJF Winner Selection
```
→ hit_set_bitmap
→ miss_set_bitmap
→ remaining_cost[]
→ rd_status_age    [N_RD_ENTRIES-1:0][GC_WIDTH-1:0]
→ wr_status_age    [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ gc               [GC_WIDTH]
→ wr_count         [$clog2(N_WR_ENTRIES+1)]
→ wr_high_wm_hit   1b
→ wr_low_wm_hit    1b
→ last_act_bg_out  [7:0][GC_WIDTH-1:0]

← winner_valid     1b
← winner_cmd_type  [2:0]   ACT/CAS_RD/CAS_WR/PRE
← winner_rank      [RANK_BITS]
← winner_bg        [BG_BITS]
← winner_bank      [BANK_BITS]
← winner_row       [ROW_BITS]
← winner_col       [COL_BITS]
← winner_entry_idx [$clog2(BUF_DEPTH)]
← winner_req_type  1b
```

### Stage 4 — Command Emission + Writebacks
```
→ winner_*         (all winner fields from Stage 3)
→ s0_override      1b
→ s0_cmd_*         (maintenance cmd fields)
→ timing_reg_vals  (from timing_reg_file, parallel)
→ gc               [GC_WIDTH]

← dfi_address      [13:0]
← dfi_cs_n         [1:0]
← dfi_bg           [2:0]
← dfi_bank         [1:0]
← dfi_act_n        1b
← dfi_wrdata       [127:0]
← dfi_wrdata_en    1b
← dfi_wrdata_mask  [15:0]

← bank_fsm_update_en
← bank_fsm_update_* (state, next_cas, next_pre, next_act, row_open)
← global_timing_update_* (next_act_any, next_cas_any, faw, bg arrays)
← status_update_en
← status_update_idx
← status_update_val [1:0]

← sched_ack        1b    → Maintenance Engine
← raa_inc_en       [N_RANKS-1:0][15:0]   → Per-Rank FSM (RAA++)
```

---

## 20. Maintenance Engine

### Refresh FSM
```
→ gc               [GC_WIDTH]
→ next_trefi_out   [N_RANKS-1:0][GC_WIDTH-1:0]
→ ref_credits_out  [N_RANKS-1:0][3:0]
→ bank_act_count   [N_RANKS-1:0][15:0][$clog2(BUF_DEPTH+1)]
→ all_idle         [N_RANKS-1:0]
→ sched_ack        1b
→ REF_MODE         [1:0]   CSR

← ref_urgent       1b
← ref_due          1b
← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← me_cmd_bg        [BG_BITS]
← me_cmd_bank      [BANK_BITS]
← set_gate_rfc     [N_RANKS-1:0]
← clr_gate_rfc     [N_RANKS-1:0]
← inc_ref_credits  [N_RANKS-1:0]
← dec_ref_credits  [N_RANKS-1:0]
← update_next_trefi [RANK_BITS + GC_WIDTH]
← set_ref_pending  [N_RANKS-1:0][15:0]
← clr_ref_pending  [N_RANKS-1:0][15:0]
```

### ZQcal FSM
```
→ gc               [GC_WIDTH]
→ next_zqcs_out    [N_RANKS-1:0][GC_WIDTH-1:0]
→ all_idle         [N_RANKS-1:0]
→ sched_ack        1b

← zq_due           1b
← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← set_gate_zq      [N_RANKS-1:0]
← clr_gate_zq      [N_RANKS-1:0]
← update_next_zqcs [RANK_BITS + GC_WIDTH]
```

### RFM FSM
```
→ gc               [GC_WIDTH]
→ raa_out          [N_RANKS-1:0][15:0][6:0]
→ RAAIMT           [7:0]   CSR
→ sched_ack        1b
→ raa_inc_en       [N_RANKS-1:0][15:0]   from Stage 4

← rfm_req          [N_RANKS-1:0][15:0]
← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← me_cmd_bg        [BG_BITS]
← me_cmd_bank      [BANK_BITS]
← raa_dec_en       [N_RANKS-1:0][15:0]
← raa_dec_val      [3:0]
```

### Power Management FSM
```
→ gc               [GC_WIDTH]
→ all_idle         [N_RANKS-1:0]
→ bank_act_count   [N_RANKS-1:0][15:0]
→ pd_en            1b   CSR
→ sr_entry         1b   system signal
→ sr_exit          1b   system signal
→ can_xp_out       [N_RANKS-1:0]
→ can_xs_out       [N_RANKS-1:0]
→ sched_ack        1b

← me_cmd_valid     1b
← me_cmd_type      [2:0]
← me_cmd_rank      [RANK_BITS]
← update_next_xp   [RANK_BITS + GC_WIDTH]
← update_next_xs   [RANK_BITS + GC_WIDTH]
← rank_state_update [RANK_BITS + 2:0]
```

---

## 21. Init FSM

```
→ clk
→ rst_n
→ INIT_KICK        1b   CSR
→ TRAIN_EN         1b   CSR
→ gc               [GC_WIDTH]
→ timing_reg_vals  (tINIT1..tDLLK from timing_reg_file)

← dfi_address      [13:0]
← dfi_cs_n         [1:0]
← dfi_act_n        1b
← dfi_wrdata       [127:0]   MRW data
← dfi_wrdata_en    1b
← init_done        1b   → Global FSM, releases Scheduler
← global_state_req [2:0]   INIT state assertion
```

---

## 22. Write Data Path

```
→ wr_data_buf_data [511:0]   from Write Data Buffer
→ wr_data_buf_mask [63:0]
→ CWL              [6:0]   CSR
→ PHY_WRLAT        [5:0]   CSR
→ gc               [GC_WIDTH]

← dfi_wrdata       [127:0]
← dfi_wrdata_en    1b
← dfi_wrdata_mask  [15:0]
← crc_err_flag     1b   → error handler
```

---

## 23. Read Data Path

```
→ dfi_rddata       [127:0]
→ dfi_rddata_valid 1b
→ PHY_RDLAT        [5:0]   CSR
→ CL               [6:0]   CSR
→ gc               [GC_WIDTH]
→ rd_entry_idx     [$clog2(N_RD_ENTRIES)]   expected return tag

← rd_data_out      [511:0]
← rd_data_valid    1b
← rd_axi_id        [AXI_ID_WIDTH]
← ecc_err_flag     1b   → error handler
← crc_err_flag     1b   → error handler
```

---

## 24. Error Handler

```
→ scheduler_error  1b
→ dfi_alert_n      1b   CRC/CA parity from PHY
→ crc_err_wr       1b   from Write Data Path
→ ecc_err_rd       1b   from Read Data Path
→ crc_err_rd       1b   from Read Data Path

← err_status_reg   [7:0]
← err_interrupt    1b   → system
← err_cmd          [2:0]   recovery action
```

---

## 25. Buffer Sizing Summary (Locked)

```
N_WR_ENTRIES:  64 (v1), 96 (v2, 3x RD)
N_RD_ENTRIES:  32 (v1 and v2)
Write Data Buffer: 32 entries × 576b
BUF_DEPTH:     max(N_WR_ENTRIES, N_RD_ENTRIES)

rationale:
  larger WR buffer → scheduler drains WR in background
  RD sees less blocking → lower read latency
  bandwidth unchanged
  WR_TCAM sized to N_WR_ENTRIES
  RD_TCAM sized to N_RD_ENTRIES
```

---

## 26. Ownership Summary

| Block | Owner (R/W) | Scheduler access |
|---|---|---|
| WR Status Reg | Write Watermark Manager | READ ONLY |
| RD Status Reg | Read Watermark Manager | READ ONLY |
| WR_TCAM | Write Watermark Manager | READ ONLY (search) |
| RD_TCAM | Read Watermark Manager | READ ONLY (search) |
| Write Data Buffer | Write Watermark Manager | READ ONLY (emit) |
| Per-Bank FSM Table | Scheduler Stage 4 + Maint Engine | WRITE (S4), READ (S2) |
| Per-Rank FSM Table | Maintenance Engine | READ (S0) |
| Global Timing Table | Scheduler Stage 4 | READ (S2) |
| Bank Activity Counter | WR/RD Watermark Managers | READ (Maint Engine, Power Mgmt) |
| timing_reg_file | CSR (init time) | READ ONLY |
| Global Cycle Counter | Free-running | READ all blocks |
