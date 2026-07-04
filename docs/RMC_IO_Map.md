## 0. Parameter Definitions

All widths are compile-time parameters. No hardcoded bit-widths anywhere.

```
GC_WIDTH         global cycle counter width
ADDR_WIDTH       byte address width
AXI_ID_WIDTH     AXI transaction ID width
AWLEN_WIDTH      AXI burst length field width
DATA_WIDTH       data bus width (request/response payload)
STRB_WIDTH       byte strobe width = DATA_WIDTH/8
CH_BITS          channel select bits
RANK_BITS        rank select bits
BG_BITS          bank group bits
BANK_BITS        bank bits
ROW_BITS         row address bits
COL_BITS         column address bits
N_RANKS          number of ranks
N_BG             number of bank groups = 2^BG_BITS
N_BANKS          banks per rank = N_BG × 2^BANK_BITS
N_WR_ENTRIES     write buffer depth
N_RD_ENTRIES     read buffer depth
WR_BUF_DEPTH     write data buffer depth
FIFO_DEPTH       async FIFO depth (= initial credit count)
DFI_ADDR_WIDTH   DFI CA bus width
DFI_DATA_WIDTH   DFI data bus width
DFI_MASK_WIDTH   DFI byte mask width
STATUS_WIDTH     request status field width
CREDIT_WIDTH     refresh credit counter width
RAA_WIDTH        per-bank RAA counter width
TIMING_WIDTH     timing parameter register width
PARAM_ID_WIDTH   timing param address bits
BANK_STATE_WIDTH per-bank FSM state encoding width
RANK_STATE_WIDTH per-rank FSM state encoding width
FAW_DEPTH        four-activate window depth (= 4, fixed by JEDEC)
```

---


# RMC — Complete Block I/O Map
## All blocks, all ports, all table fields
---

## 0. Signal Convention

```
→   input to block
←   output from block
↔   bidirectional
GC_WIDTH = GC_WIDTH
all widths parameterized unless stated
```

---

## 1. CIF (AXI Clock Domain)

### 1A. AXI Write Port
```
→ AWID    [AXI_ID_WIDTH]
→ AWADDR  [ADDR_WIDTH]
→ AWLEN   [AWLEN_WIDTH]
→ AWSIZE  [BURST_WIDTH]
→ AWBURST [RESP_WIDTH]
→ AWVALID
← AWREADY

→ WID     [AXI_ID_WIDTH]
→ WDATA   [STRB_WIDTH-1:0]
→ WSTRB   [AWLEN_WIDTH]
→ WLAST
→ WVALID
← WREADY

← BID     [AXI_ID_WIDTH]
← BRESP   [RESP_WIDTH]
← BVALID
→ BREADY
```

### 1B. AXI Read Port
```
→ ARID    [AXI_ID_WIDTH]
→ ARADDR  [ADDR_WIDTH]
→ ARLEN   [AWLEN_WIDTH]
→ ARSIZE  [BURST_WIDTH]
→ ARBURST [RESP_WIDTH]
→ ARVALID
← ARREADY

← RID     [AXI_ID_WIDTH]
← RDATA   [STRB_WIDTH-1:0]
← RRESP   [RESP_WIDTH]
← RLAST
← RVALID
→ RREADY
```

### 1C. Burst Splitter
```
→ raw_addr        [ADDR_WIDTH]
→ raw_len         [AWLEN_WIDTH]
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
→ alloc_seqnum    [AWLEN_WIDTH]
← rob_slot        [$clog2(WR_BUF_DEPTH)]
→ retire_id       [AXI_ID_WIDTH]
→ retire_data     [DATA_WIDTH-1:0]
← rd_data_out     [DATA_WIDTH-1:0]
← rd_last
← rob_full
```

### 1F. Merge Logic
```
→ frag_data       [DATA_WIDTH-1:0]
→ frag_mask       [STRB_WIDTH-1:0]
→ frag_id         [AXI_ID_WIDTH]
→ frag_seqnum     [AWLEN_WIDTH]
← merged_data     [DATA_WIDTH-1:0]
← merged_valid
```

---

## 2. Async Request FIFO (CIF → MC Core)

### Protocol
```
CIF write side: credit-based push
  FIFO_DEPTH credits issued at init = FIFO depth
  CIF sends when local_credit > 0
  no combinational wr_full check

MC read side: valid-credit receive
  rd_valid + rd_data (registered)
  after consume: credit_return → CIF (registered, sync path)

credit return path: 1b registered signal, MC clock → CIF clock
  separate gray-coded or pulse sync
```


### Packet format
```
req_type   1b        0=RD, 1=WR
axi_id     [AXI_ID_WIDTH]
addr       [ADDR_WIDTH]
data       [DATA_WIDTH-1:0]   WR only
mask       [STRB_WIDTH-1:0]    WR only
```

### Ports — CIF write side (credit-based)
```
← wr_valid        (CIF side: send when local_credit > 0)
← wr_data         [packet width]
→ credit_return   1b   registered, MC→CIF clock domain
                       CIF increments local_credit on receipt
N_REQ_CREDITS = FIFO depth (init time)
no combinational wr_full path
```

### Ports — MC read side (valid-credit)
```
→ rd_valid        (MC side: data available, registered)
→ rd_data         [packet width]
← rd_credit_ret   1b   asserted one cycle after consume
```

---

## 3. Async Response FIFO (MC Core → CIF)

### Protocol
```
MC write side: credit-based push
  FIFO_DEPTH credits issued at init = FIFO depth
  gate_resp_fifo_avail = (local_credit > reserved_slots)
  MC sends when gate_resp_fifo_avail==1
  no combinational wr_full check

CIF read side: valid-credit receive
  rd_valid + rd_data (registered)
  after consume: credit_return → MC (registered, sync path)

credit return path: registered, CIF clock → MC clock
```

### Packet format
```
resp_type  2b        00=RD_DATA, 01=WR_ACK, 10=ERR
axi_id     [AXI_ID_WIDTH]
data       [DATA_WIDTH-1:0]   RD only
status     [STATUS_EXT_WIDTH]     0=OK
```

### Ports — MC write side (credit-based)
```
← wr_valid        (MC side: send when gate_resp_fifo_avail==1)
← wr_data         [packet width]
→ gate_resp_fifo_avail   1b   (local_credit > reserved_slots)
→ credit_return   1b   registered, CIF→MC clock domain
```

### Ports — CIF read side (valid-credit)
```
→ rd_valid        registered
→ rd_data         [packet width]
← rd_credit_ret   1b   after consume
```

**MC never issues RD without gate_resp_fifo_avail==1. CIF always accepts immediately.**

---

## 4. Write Data Buffer (SRAM)

### Fields (WR_BUF_DEPTH entries, DATA_WIDTH+STRB_WIDTH bits/entry)
```
data   [DATA_WIDTH-1:0]
mask   [STRB_WIDTH-1:0]
```

### Ports
```
→ wr_idx          [$clog2(WR_BUF_DEPTH)]
→ wr_data         [DATA_WIDTH-1:0]
→ wr_mask         [STRB_WIDTH-1:0]
→ wr_en
→ rd_idx          [$clog2(WR_BUF_DEPTH)]
← rd_data         [DATA_WIDTH-1:0]
← rd_mask         [STRB_WIDTH-1:0]
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
data_buf_idx [$clog2(WR_BUF_DEPTH)]                    optional, → Write Data Buffer
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
→ update_status  [RESP_WIDTH]
→ update_en

← rd_valid       [N_WR_ENTRIES-1:0]   all valid bits (scheduler reads)
← rd_status      [N_WR_ENTRIES-1:0][RESP_WIDTH]
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
→ update_status  [RESP_WIDTH]
→ update_en

← rd_valid       [N_RD_ENTRIES-1:0]
← rd_status      [N_RD_ENTRIES-1:0][RESP_WIDTH]
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
← wr_status_update_val [RESP_WIDTH]
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
← rd_status_update_val [RESP_WIDTH]
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
→ new_rd_mask      [STRB_WIDTH-1:0]
→ new_rd_age       [GC_WIDTH]

→ wr_tcam_hit_vector  [N_WR_ENTRIES-1:0]
→ wr_tcam_hit_entry   [entry width]
→ wr_status_age       [N_WR_ENTRIES-1:0][GC_WIDTH-1:0]
→ wr_data_buf_data    [DATA_WIDTH-1:0]
→ wr_data_buf_mask    [STRB_WIDTH-1:0]
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
← raw_data         [DATA_WIDTH-1:0]
← raw_data_mask    [STRB_WIDTH-1:0]
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
← hold_valid[RESP_WIDTH]
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
→ inc_en           [N_RANKS-1:0][DFI_MASK_WIDTH]   per bank
→ dec_en           [N_RANKS-1:0][DFI_MASK_WIDTH]
→ dirty_set        [N_RANKS-1:0][DFI_MASK_WIDTH]   on WR alloc
→ dirty_clr        [N_RANKS-1:0][DFI_MASK_WIDTH]   on last WR retire

← count_out        [N_RANKS-1:0][DFI_MASK_WIDTH][$clog2(BUF_DEPTH+1)]
← dirty_out        [N_RANKS-1:0][DFI_MASK_WIDTH]
← all_idle[rank]   1b    count==0 for all banks in rank
```

---

## 14. Per-Bank FSM Table

### Entry fields (16 × N_RANKS, LOCKED)
```
state        [BURST_WIDTH]
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

→ update_en        [N_RANKS-1:0][DFI_MASK_WIDTH]
→ update_rank      [RANK_BITS]
→ update_bg        [BG_BITS]
→ update_bank      [BANK_BITS]
→ update_state     [BURST_WIDTH]
→ update_row_open  [ROW_BITS]
→ update_next_cas  [GC_WIDTH]
→ update_next_pre  [GC_WIDTH]
→ update_next_act  [GC_WIDTH]
→ update_next_ref  [GC_WIDTH]
→ set_ref_pending  [N_RANKS-1:0][DFI_MASK_WIDTH]
→ clr_ref_pending  [N_RANKS-1:0][DFI_MASK_WIDTH]

← state_out        [N_RANKS-1:0][DFI_MASK_WIDTH][BURST_WIDTH]
← row_open_out     [N_RANKS-1:0][DFI_MASK_WIDTH][ROW_BITS-1:0]
← can_cas_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
← can_pre_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
← can_act_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
← can_ref_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
← ref_pending_out  [N_RANKS-1:0][DFI_MASK_WIDTH]
← next_cas_out     [N_RANKS-1:0][DFI_MASK_WIDTH][GC_WIDTH-1:0]
← next_pre_out     [N_RANKS-1:0][DFI_MASK_WIDTH][GC_WIDTH-1:0]
← next_act_out     [N_RANKS-1:0][DFI_MASK_WIDTH][GC_WIDTH-1:0]

writer: Scheduler Stage 4 + Maintenance Engine
reader: Scheduler Stage 2
```

---

## 15. Per-Rank FSM Table

### Entry fields (N_RANKS, LOCKED)
```
state        [BURST_WIDTH]
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
ref_credits  [STATUS_EXT_WIDTH]
raa[16]      [6:0] × 16
```

### Ports
```
→ gc               [GC_WIDTH]

→ update_rank      [RANK_BITS]
→ update_state     [BURST_WIDTH]
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
→ raa_inc_en       [N_RANKS-1:0][DFI_MASK_WIDTH]
→ raa_dec_val      [STATUS_EXT_WIDTH]
→ raa_dec_en       [N_RANKS-1:0][DFI_MASK_WIDTH]

← state_out        [N_RANKS-1:0][BURST_WIDTH]
← gate_rfc_out     [N_RANKS-1:0]
← gate_zq_out      [N_RANKS-1:0]
← ref_credits_out  [N_RANKS-1:0][STATUS_EXT_WIDTH]
← raa_out          [N_RANKS-1:0][DFI_MASK_WIDTH][6:0]
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
global_state     [BURST_WIDTH]
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
→ update_global_state [BURST_WIDTH]

← can_act_any_out  1b
← can_cas_any_out  1b
← can_rd_wr_out    1b
← can_wr_rd_out    1b
← can_faw_out      1b
← can_act_bg_out   [AWLEN_WIDTH]
← can_cas_bg_out   [AWLEN_WIDTH]
← can_wtr_bg_out   [AWLEN_WIDTH]
← last_act_bg_out  [AWLEN_WIDTH][GC_WIDTH-1:0]
← global_state_out [BURST_WIDTH]

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
→ param_id[]       [$clog2(WR_BUF_DEPTH)] × N_read_ports
← param_val[]      [DFI_ADDR_WIDTH] × N_read_ports   combinational

→ csr_wr_en
→ csr_param_id     [$clog2(WR_BUF_DEPTH)]
→ csr_param_val    [DFI_ADDR_WIDTH]

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
← gc               [GC_WIDTH]   free-running GC_WIDTH counter
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
→ rfm_req          [N_RANKS-1:0][DFI_MASK_WIDTH]
→ global_state     [BURST_WIDTH]

← s0_override      1b
← s0_cmd_type      [BURST_WIDTH]
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
→ can_cas_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
→ can_pre_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
→ can_act_out      [N_RANKS-1:0][DFI_MASK_WIDTH]
→ can_act_bg_out   [AWLEN_WIDTH]
→ can_act_any_out  1b
→ can_cas_bg_out   [AWLEN_WIDTH]
→ can_cas_any_out  1b
→ can_rd_wr_out    1b
→ can_wr_rd_out    1b
→ can_faw_out      1b
→ gate_rfc_out     [N_RANKS-1:0]
→ gate_zq_out      [N_RANKS-1:0]
→ state_out        [N_RANKS-1:0][DFI_MASK_WIDTH][BURST_WIDTH]
→ row_open_out     [N_RANKS-1:0][DFI_MASK_WIDTH][ROW_BITS-1:0]
→ next_cas_out     [N_RANKS-1:0][DFI_MASK_WIDTH][GC_WIDTH-1:0]
→ next_pre_out     [N_RANKS-1:0][DFI_MASK_WIDTH][GC_WIDTH-1:0]
→ next_act_out     [N_RANKS-1:0][DFI_MASK_WIDTH][GC_WIDTH-1:0]
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
→ last_act_bg_out  [AWLEN_WIDTH][GC_WIDTH-1:0]

← winner_valid     1b
← winner_cmd_type  [BURST_WIDTH]   ACT/CAS_RD/CAS_WR/PRE
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

← dfi_address      [DFI_ADDR_WIDTH]
← dfi_cs_n         [RESP_WIDTH]
← dfi_bg           [BURST_WIDTH]
← dfi_bank         [RESP_WIDTH]
← dfi_act_n        1b
← dfi_wrdata       [DFI_DATA_WIDTH]
← dfi_wrdata_en    1b
← dfi_wrdata_mask  [DFI_MASK_WIDTH]

← bank_fsm_update_en
← bank_fsm_update_* (state, next_cas, next_pre, next_act, row_open)
← global_timing_update_* (next_act_any, next_cas_any, faw, bg arrays)
← status_update_en
← status_update_idx
← status_update_val [RESP_WIDTH]

← sched_ack        1b    → Maintenance Engine
← raa_inc_en       [N_RANKS-1:0][DFI_MASK_WIDTH]   → Per-Rank FSM (RAA++)
```

---

## 20. Maintenance Engine

### Refresh FSM
```
→ gc               [GC_WIDTH]
→ next_trefi_out   [N_RANKS-1:0][GC_WIDTH-1:0]
→ ref_credits_out  [N_RANKS-1:0][STATUS_EXT_WIDTH]
→ bank_act_count   [N_RANKS-1:0][DFI_MASK_WIDTH][$clog2(BUF_DEPTH+1)]
→ all_idle         [N_RANKS-1:0]
→ sched_ack        1b
→ REF_MODE         [RESP_WIDTH]   CSR

← ref_urgent       1b
← ref_due          1b
← me_cmd_valid     1b
← me_cmd_type      [BURST_WIDTH]
← me_cmd_rank      [RANK_BITS]
← me_cmd_bg        [BG_BITS]
← me_cmd_bank      [BANK_BITS]
← set_gate_rfc     [N_RANKS-1:0]
← clr_gate_rfc     [N_RANKS-1:0]
← inc_ref_credits  [N_RANKS-1:0]
← dec_ref_credits  [N_RANKS-1:0]
← update_next_trefi [RANK_BITS + GC_WIDTH]
← set_ref_pending  [N_RANKS-1:0][DFI_MASK_WIDTH]
← clr_ref_pending  [N_RANKS-1:0][DFI_MASK_WIDTH]
```

### ZQcal FSM
```
→ gc               [GC_WIDTH]
→ next_zqcs_out    [N_RANKS-1:0][GC_WIDTH-1:0]
→ all_idle         [N_RANKS-1:0]
→ sched_ack        1b

← zq_due           1b
← me_cmd_valid     1b
← me_cmd_type      [BURST_WIDTH]
← me_cmd_rank      [RANK_BITS]
← set_gate_zq      [N_RANKS-1:0]
← clr_gate_zq      [N_RANKS-1:0]
← update_next_zqcs [RANK_BITS + GC_WIDTH]
```

### RFM FSM
```
→ gc               [GC_WIDTH]
→ raa_out          [N_RANKS-1:0][DFI_MASK_WIDTH][6:0]
→ RAAIMT           [AWLEN_WIDTH]   CSR
→ sched_ack        1b
→ raa_inc_en       [N_RANKS-1:0][DFI_MASK_WIDTH]   from Stage 4

← rfm_req          [N_RANKS-1:0][DFI_MASK_WIDTH]
← me_cmd_valid     1b
← me_cmd_type      [BURST_WIDTH]
← me_cmd_rank      [RANK_BITS]
← me_cmd_bg        [BG_BITS]
← me_cmd_bank      [BANK_BITS]
← raa_dec_en       [N_RANKS-1:0][DFI_MASK_WIDTH]
← raa_dec_val      [STATUS_EXT_WIDTH]
```

### Power Management FSM
```
→ gc               [GC_WIDTH]
→ all_idle         [N_RANKS-1:0]
→ bank_act_count   [N_RANKS-1:0][DFI_MASK_WIDTH]
→ pd_en            1b   CSR
→ sr_entry         1b   system signal
→ sr_exit          1b   system signal
→ can_xp_out       [N_RANKS-1:0]
→ can_xs_out       [N_RANKS-1:0]
→ sched_ack        1b

← me_cmd_valid     1b
← me_cmd_type      [BURST_WIDTH]
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

← dfi_address      [DFI_ADDR_WIDTH]
← dfi_cs_n         [RESP_WIDTH]
← dfi_act_n        1b
← dfi_wrdata       [DFI_DATA_WIDTH]   MRW data
← dfi_wrdata_en    1b
← init_done        1b   → Global FSM, releases Scheduler
← global_state_req [BURST_WIDTH]   INIT state assertion
```

---

## 22. Write Data Path

```
→ wr_data_buf_data [DATA_WIDTH-1:0]   from Write Data Buffer
→ wr_data_buf_mask [STRB_WIDTH-1:0]
→ CWL              [6:0]   CSR
→ PHY_WRLAT        [5:0]   CSR
→ gc               [GC_WIDTH]

← dfi_wrdata       [DFI_DATA_WIDTH]
← dfi_wrdata_en    1b
← dfi_wrdata_mask  [DFI_MASK_WIDTH]
← crc_err_flag     1b   → error handler
```

---

## 23. Read Data Path

```
→ dfi_rddata       [DFI_DATA_WIDTH]
→ dfi_rddata_valid 1b
→ PHY_RDLAT        [5:0]   CSR
→ CL               [6:0]   CSR
→ gc               [GC_WIDTH]
→ rd_entry_idx     [$clog2(N_RD_ENTRIES)]   expected return tag

← rd_data_out      [DATA_WIDTH-1:0]
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

← err_status_reg   [AWLEN_WIDTH]
← err_interrupt    1b   → system
← err_cmd          [BURST_WIDTH]   recovery action
```

---

## 25. Buffer Sizing Summary (Locked)

```
N_WR_ENTRIES:  64 (v1), 96 (v2, 3x RD)
N_RD_ENTRIES:  32 (v1 and v2)
Write Data Buffer: WR_BUF_DEPTH entries × 576b
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

---

## 27. Speculative Prefetch ACT — Stage 2 Extension

### New inputs to Stage 2
```
→ cur_col_out      [N_RANKS][N_BANKS][COL_BITS]   current col being served
→ COL_MAX          COL_BITS                        from timing_reg / param
→ BL_BYTES         param                           burst length in bytes
→ row_open_out     [N_RANKS][N_BANKS][ROW_BITS]    from Per-Bank FSM Table
→ bank_act_count   [N_RANKS][N_BANKS]              from Bank Act Counter
→ can_act_out      [N_RANKS][N_BANKS]              existing
→ can_faw_out      1b                              existing
→ rd_tcam_hit_meta per bank                        existing
→ winner_valid     1b                              from Stage 3 (feedback)
```

### New outputs from Stage 2
```
← spec_act_valid   1b
← spec_act_rank    RANK_BITS
← spec_act_bg      BG_BITS
← spec_act_bank    BANK_BITS
← spec_act_row     ROW_BITS
```

### New logic (combinational, per active bank)
```
col_remaining[r][bg][b] = COL_MAX - cur_col_out[r][bg][b]
boundary_imminent[r][bg][b] = (col_remaining <= BL_BYTES)
  AND (state[r][bg][b] == ACTIVE)

pred_bank = b + 1
pred_row  = row_open[r][bg][b]

spec_gate[r][bg][b] =
  boundary_imminent[r][bg][b]
  AND rdtcam_hit[r][bg][pred_bank]
  AND (tcam_out[pred_bank].row == pred_row)
  AND (bank_act_count[r][bg][pred_bank] > 0)
  AND (state[r][bg][pred_bank] == IDLE)
  AND can_act[r][bg][pred_bank]
  AND can_faw

spec_act_valid = (|spec_gate) AND (winner_valid == 0)
spec_act_{rank,bg,bank,row} = mux from first set spec_gate bit
```

### Stage 3 integration
```
if spec_act_valid AND winner_valid==0:
  winner_cmd_type = ACT
  winner_rank     = spec_act_rank
  winner_bg       = spec_act_bg
  winner_bank     = spec_act_bank
  winner_row      = spec_act_row
  winner_valid    = 1
  (no entry_idx — no request buffer entry consumed)
```

---

## 28. Merge Unit (new block)

### Purpose
```
combines WDB partial hit data with DRAM return data
fires only when RD status reg merge_pending==1
```

### Ports
```
→ merge_pending    1b
→ wdb_entry_idx    $clog2(WR_BUF_DEPTH)
→ wdb_data         DATA_WIDTH      from Write Data Buffer
→ wdb_mask         STRB_WIDTH      from Write Data Buffer
→ dram_data        DATA_WIDTH      from Read Data Path
→ dram_valid       1b

← merged_data      DATA_WIDTH
← merged_valid     1b
← merged_axi_id    AXI_ID_WIDTH
```

### Logic
```
merged[byte] = wdb_data[byte] if wdb_mask[byte]==1
               else dram_data[byte]
combinational, one cycle at dram_valid
```

---

## 28. RAW Bypass Manager — Updated Ports

### Stage A (cycle 0, combinational with RD alloc)
```
→ new_rd_bg        BG_BITS
→ new_rd_bank      BANK_BITS
→ new_rd_row       ROW_BITS
→ new_rd_col       COL_BITS
→ new_rd_axi_id    AXI_ID_WIDTH    (masked in TCAM search)
→ new_rd_age       GC_WIDTH

→ wr_tcam_hit_vector  N_WR_ENTRIES
→ wr_status_valid     N_WR_ENTRIES
→ wr_status_age       N_WR_ENTRIES × GC_WIDTH
→ wdb_data            DATA_WIDTH
→ wdb_mask            STRB_WIDTH
```

### Stage B (cycle 1)
```
hit valid: wr_age <= rd_age

← raw_full_hit      1b    → forward WDB directly
← raw_partial_hit   1b    → issue DRAM + set merge_pending
← raw_miss          1b    → pass to scheduler
← raw_wdb_data      DATA_WIDTH
← raw_wdb_mask      STRB_WIDTH
← raw_wdb_entry_idx $clog2(WR_BUF_DEPTH)
← raw_axi_id        AXI_ID_WIDTH
```

---

## 29. Per-Rank FSM Table — Updated Fields (v1.9.7)

### New field
```
last_refsb_gc[32]   GC_WIDTH × 32
  index: bg × N_BANKS_PER_BG + bank  (0..31)
  updated: Stage 4 on every REFsb
  read by: Maintenance Engine Refresh FSM
```

### New ports
```
→ refsb_issued_en    1b
→ refsb_bank_idx     5b   ($clog2(32))
→ refsb_gc           GC_WIDTH

← last_refsb_gc_out  32 × GC_WIDTH
← overdue_bitmap     32b   (gc - last_refsb_gc[b]) > tREFI×32
← most_overdue_idx   5b    argmax(gc - last_refsb_gc[b])
```

---

## 30. NOP Cycle Arbitration (updated priority)

```
winner_valid==0 → NOP cycle detected

priority:
  1. opportunity REFsb
       bank_act_count[r][bg][b]==0
       AND can_ref[b]==1
       AND overdue_bitmap any set (watchdog)
       OR argmax(gc - last_refsb_gc) most overdue
       → emit REFsb

  2. speculative ACT
       boundary_imminent AND RD_TCAM confirmed
       AND bank_act_count[next_bank] > 0
       AND can_act AND can_faw
       → emit speculative ACT

  3. true NOP → nothing issued
```

---

## 31. DFI Output Mux (inside ME)

### Ports
```
inputs from Init FSM (ME internal):
  init_dfi_address     DFI_ADDR_WIDTH
  init_dfi_cs_n        N_RANKS
  init_dfi_bg          BG_BITS
  init_dfi_bank        BANK_BITS
  init_dfi_act_n       1b
  init_dfi_wrdata      DFI_DATA_WIDTH
  init_dfi_wrdata_en   1b
  init_dfi_wrdata_mask DFI_MASK_WIDTH
  init_dfi_freq_ratio  2b

inputs from Scheduler Stage 4:
  sched_dfi_address     DFI_ADDR_WIDTH
  sched_dfi_cs_n        N_RANKS
  sched_dfi_bg          BG_BITS
  sched_dfi_bank        BANK_BITS
  sched_dfi_act_n       1b
  sched_dfi_wrdata      DFI_DATA_WIDTH
  sched_dfi_wrdata_en   1b
  sched_dfi_wrdata_mask DFI_MASK_WIDTH

control:
  init_done            1b

outputs to PHY:
  dfi_address          DFI_ADDR_WIDTH
  dfi_cs_n             N_RANKS
  dfi_bg               BG_BITS
  dfi_bank             BANK_BITS
  dfi_act_n            1b
  dfi_wrdata           DFI_DATA_WIDTH
  dfi_wrdata_en        1b
  dfi_wrdata_mask      DFI_MASK_WIDTH
  dfi_freq_ratio       2b
```

---

## 32. MR_Poll FSM Ports

```
→ gc                  GC_WIDTH
→ init_done           1b
→ mrr_data_valid      1b      from Read Data Path sideband
→ mrr_data            8b
→ mrr_rank            RANK_BITS
→ sched_ack           1b
→ MRR_POLL_INTERVAL   GC_WIDTH   CSR

← me_cmd_valid        1b
← me_cmd_type         3b      = MRR
← me_cmd_mr           4b      = 4 (MR4)
← me_cmd_rank         RANK_BITS
← tuf_bit             1b      → Refresh FSM
← next_poll_gc_wr     GC_WIDTH
← mrr_data_wr         8b
← last_tuf_wr         1b
```

---

## 33. AMU — Address Map Unit

### Replaces
Address Translator (CIF §1D)

### Ports
```
CSR setup (init time only):
→ amu_wr_en       1b
→ amu_field_sel   3b
→ amu_src_msb_a   5b
→ amu_src_lsb_a   5b
→ amu_src_msb_b   5b
→ amu_src_lsb_b   5b
→ amu_split_en    1b
→ amu_hash_en     1b
→ amu_xor_shift   5b

runtime (combinational):
→ byte_addr       ADDR_WIDTH
← hashed_addr     ADDR_WIDTH
← ch              CH_BITS
← rank            RANK_BITS
← bg              BG_BITS
← bank            BANK_BITS
← row             ROW_BITS
← col             COL_BITS
```

---

## 34. Bank Partition Controller

### Fields
```
partition_reg      1b
window_ctr         GC_WIDTH
rd_partition_mask  N_BANKS
wr_partition_mask  N_BANKS
```

### Ports
```
→ gc               GC_WIDTH
→ WINDOW_SIZE      GC_WIDTH   CSR
→ wr_count         clog2(N_WR_ENTRIES+1)
→ WR_HIGH_WM       CSR
→ rd_starvation_override [N_BANKS]   from Stage 3
→ sched_mode       1b   RD=0 WR=1

← rd_partition_mask  N_BANKS   → Stage 2
← wr_partition_mask  N_BANKS   → Stage 2
← partition_reg      1b
```

---

## 35. Read Data Path — Updated Ports

### New sideband output (MRR)
```
← mrr_data_valid   1b      asserted when MRR response captured
← mrr_data         8b      MR4 register contents
← mrr_rank         RANK_BITS
```
