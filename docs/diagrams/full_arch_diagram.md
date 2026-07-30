# RMC — Full Architecture (single mermaid, front-end + scheduler + PHY)

One stitched end-to-end diagram: **AXI/CIF → async-FIFO CDC → MCC front-end (buffers + RAW)
→ scheduler (S0–S4 + per-bank queues + weight arbiter) → DFI → PHY/DDR5**, plus the response
path back. Combines [`mcc_v3.1_diagram.md`](mcc_v3.1_diagram.md) and
[`scheduler_cmd_pipeline_detailed.md`](scheduler_cmd_pipeline_detailed.md) into one picture.
`[v1.9.9]`: no valid bit (occupancy = head/tail, RAW gate = `wr_occupied`), per-bank queues,
weight arbiter, row-hit promotion, never-idle-DQ guardrail.

Legend: `*fifo/*reg/*sram/*logic` = block type · solid = forward request/command/data ·
dashed = writeback / feedback / response.

```mermaid
flowchart TB

  %% ==================== CIF — AXI CLOCK DOMAIN ====================
  subgraph CIF["CIF — AXI clock domain"]
    direction TB
    AXI["AXI4 W/R ports"]
    SPL["burst_splitter *logic<br/>BL16 align, row-boundary split"]
    XLT["addr_translator *logic<br/>byte_addr → {rank,bg,bank,row,col}"]
    ROB["reorder_buffer *reg<br/>{AXID,seqnum} tag"]
    MRG["merge_logic *logic"]
    AXI --> SPL --> XLT --> ROB
    AXI --> MRG
  end

  %% ==================== CDC — THE ONE ASYNC CROSSING ====================
  subgraph CDC["CDC — single async-FIFO crossing (AXI ↔ MC clock)"]
    direction TB
    REQF[("async_request_fifo *fifo<br/>credit-based push")]
    RESPF[("async_response_fifo *fifo<br/>valid-credit")]
  end

  %% ==================== MCC FRONT-END — MC CLOCK ====================
  subgraph MCCFE["MCC front-end — MC clock"]
    direction TB
    WRTR["WR router + inv_lsb_priority_encoder *logic<br/>alloc slot (occ = head/tail, no valid bit)"]
    WRTCAM[("wr_reg_tcam *reg<br/>{rank,bg,bank,row,col}")]
    WRSTAT[("wr_status_register *reg<br/>{status,age} — no valid bit")]
    WRDATA[("wr_data_buffer *sram<br/>{tag,data,mask}")]
    RDTR["RD router + inv_lsb_priority_encoder *logic"]
    RDTCAM[("rd_reg_tcam *reg<br/>{rank,bg,bank}")]
    RDSTAT[("rd_status_register *reg<br/>{status,age} — no valid bit")]
    RDBUF[("rd_request_buffer *sram<br/>{tag,row,col}")]
    subgraph RAWE["RAW redirect engine"]
      direction LR
      RH["hit s1"] --> RF["fetch s2<br/>trd&gt;all(twr)"] --> RWc["write s3"]
      RF --> HNF["2x hold_and_forward"]
    end
    WRTR --> WRTCAM
    WRTR --> WRSTAT
    WRTR --> WRDATA
    RDTR --> RDTCAM
    RDTR --> RDSTAT
    RDTR --> RDBUF
    WRDATA -- "fetch_required_entries" --> RF
    RWc -- "unstall_rd_req" --> RDTR
  end

  GC[["global_32b_counter → gc"]]

  %% ==================== SCHEDULER — MC CLOCK ====================
  subgraph SCHED["Scheduler — MC clock  [v1.9.9]"]
    direction TB
    S0{{"S0 maintenance_override<br/>ref_urgent&gt;ref_due&gt;rfm&gt;zq"}}
    S1["S1 admission *logic<br/>hit &amp; wr_occupied (no valid bit) · RAW compare<br/>classify NEED_PRE/ACT/CAS · evict + row-hit promote"]
    QUE[("per-bank queues *reg<br/>16 × depth 8 · head-only · head/tail occ")]
    S2["S2 gate_gen + cost *logic<br/>can_cas/act/pre[16] · hit/miss set"]
    S3["S3 winner select *logic<br/>guardrail (never idle DQ) →<br/>argmax(K·control+age+servo) · R/W watermark"]
    S4["S4 s4_mux + dfi_drv + writeback *logic<br/>(single state writer)"]
    TRF[("timing_reg_file *reg (scoreboard)<br/>next_cas/pre/act · row_open · tFAW · last_act_bg")]
    ME["maintenance_engine *logic<br/>Refresh / ZQcal / RFM / PowerMgmt"]
    S1 --> QUE --> S2 --> S3 --> S4
    S4 -. "bank/global_timing_update" .-> TRF
    TRF -. "next_* / row_open (next clk)" .-> S2
    ME --> S0
    S0 -- "s0_override" --> S4
    S4 -. "sched_ack" .-> ME
  end

  %% ==================== PHY / DRAM ====================
  subgraph PHYD["PHY / DDR5"]
    direction TB
    DFI[("DFI bus<br/>address/cs_n/act_n/bg/bank/wrdata")]
    PHY["DDR5 PHY"]
    DRAM[("DDR5 device<br/>16 banks / 4 BG")]
    DFI --> PHY --> DRAM
  end

  %% ---------------- forward path ----------------
  ROB -- "async_wr/rd_req (packet)" --> REQF
  MRG --> REQF
  REQF -- "async_wr_req" --> WRTR
  REQF -- "async_rd_req" --> RDTR
  REQF -- "async_rd_req{tag,col}" --> RH

  GC -- "gc" --> WRTR
  GC -- "gc" --> RDTR
  GC -- "gc" --> S1

  %% ---------------- MCC → scheduler handoff ----------------
  WRTCAM -- "wr_tcam_hit_bitmap/meta" --> S1
  RDTCAM -- "rd_tcam_hit_bitmap/meta" --> S1
  WRSTAT -- "wr_occupied (head/tail, no valid bit)" --> S1
  WRSTAT -- "wr_status_age" --> S3
  RDSTAT -- "rd_status_age" --> S3
  QUE -. "queue_full (backpressure)" .-> RDTR

  %% ---------------- scheduler → PHY ----------------
  WRDATA -- "write payload" --> S4
  S4 -- "dfi command + wrdata" --> DFI

  %% ---------------- response path ----------------
  DRAM -. "dfi rd_data" .-> RESPF
  HNF -. "resp_rd_packet (RAW)" .-> RESPF
  S4 -. "wr/rd_*_schd_cmd (status update)" .-> WRSTAT
  S4 -. "status update" .-> RDSTAT
  RESPF -. "rd_data / wr_ack" .-> AXI
```

---

## The path in one paragraph

AXI bursts are split to BL16, address-translated to `{rank,bg,bank,row,col}`, tagged in the
ROB, and pushed across the **single async-FIFO CDC** into the **MCC front-end**. There the
WR/RD routers allocate slots (occupancy = **head/tail pointers, no valid bit**), store address
in the `*_reg_tcam` reg arrays and payload in `wr_data_buffer`/`rd_request_buffer`; the **RAW
engine** serves any read whose data is still an in-flight write (`trd > all(twr)`) straight
back through the response FIFO. The front-end's right edge — TCAM hit bitmaps/meta,
`wr_occupied`, status `age`, `gc` — is the **scheduler's** Stage-1 input. The scheduler
classifies + evicts into **16 per-bank FIFOs** (row-hit promoted), hard-masks legality (S2),
picks a winner (S3: **guardrail never idles DQ**, else `argmax(K·control+age+servo)` with R/W
watermark batching), and emits the DDR5 command on **DFI** (S4), which the **single writeback**
uses to advance the `timing_reg_file` scoreboard, update MCC request status (`schd_cmd`), ack
the maintenance engine, and retire the queue entry. Read data returns via DFI → response FIFO
→ CIF → AXI. Stage 0 (maintenance: REF/ZQ/RFM/PM) pre-empts everything through `s4_mux`.

Individual zooms: [`README.md`](README.md) indexes every per-block diagram.
