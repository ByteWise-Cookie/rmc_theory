# RMC Scheduler — Detailed Command Pipeline (MCC handoff → DFI emission)

Companion to `mcc_v3.1` (the front-end request-buffer / RAW block diagram). That drawing
stops where the request buffers expose their **scheduler interface**: the timestamped req
arrays (**no valid bit** [v1.9.9] — occupancy is head/tail), the TCAM hit vectors, the read-port pairs, and the
`*_invalidate/update_status_schd_cmd` writeback ports. **This** diagram picks up exactly
there and runs the 5-stage scheduler all the way to **command (CM) emission on DFI**.

Signal names on the wires are the frozen external ports from `RMC_IO_Map.md §19` (Stage 0–4),
annotated with the `[v1.9.9]` internal-rework nets (per-bank queues, weight arbiter,
row-hit promotion, never-idle-DQ guardrail, no valid bit). Renders inline on GitHub. Golden reference:
[`../tools/sched_model/sched_test.js`](../../tools/sched_model/sched_test.js). Per-stage zoom
views (S0–S4, net level): [`scheduler_stage_details.md`](scheduler_stage_details.md).
Stitched overview: [`scheduler_full_diagram.md`](scheduler_full_diagram.md).

```mermaid
flowchart TB
    %% ============================================================
    %%  MCC handoff boundary  (right edge of mcc_v3.1)
    %% ============================================================
    subgraph MCC["MCC front-end handoff (from mcc_v3.1)"]
        direction TB
        RDBUF["rd_reqest_buffer *sram<br/>N_RD_ENTRIES x{rd_tag,rd_row,rd_col}"]
        WRBUF["wr_data_buffer *sram<br/>N_WR_ENTRIES x{wr_tag,wr_data,wr_byte_mask}"]
        RDTCAM["rd_reg_tcam_reg_array<br/>{rd_rank,rd_bg,rd_bank,rd_row}"]
        WRTCAM["wr_reg_tcam_reg_array<br/>{wr_rank,wr_bg,wr_bank,wr_row,wr_col}"]
        VALID["write/read_status_register<br/>{age, work_state}<br/>[v1.9.9] no valid bit — occ = head/tail"]
        GC["global_32b_counter"]
    end

    %% ============================================================
    %%  STAGE 0 — maintenance override
    %% ============================================================
    subgraph S0["Stage 0 — Maintenance Override"]
        direction TB
        MEIN["ref_urgent / ref_due / zq_due<br/>rfm_req[rank] / global_state"]
        S0LOG["s0 priority mux<br/>ref_urgent &gt; ref_due &gt; rfm &gt; zq"]
        MEIN --> S0LOG
    end

    %% ============================================================
    %%  STAGE 1 — TCAM search + admission + per-bank queues
    %% ============================================================
    subgraph S1["Stage 1 — TCAM Search / Admission"]
        direction TB
        HITGEN["hit-bitmap gate<br/>RAW hit &amp; wr_occupied (no valid bit) → s1_hit_bitmap[N_BANKS]<br/>s1_hit_meta{row,col,req_type,entry_idx,axi_id}"]
        RAW{"RAW: older write<br/>to same addr in flight?"}
        EVICT["s1_evict: entry classified<br/>+ RAW-clear → bank queue"]
        RAW -- "raw_block_en (held, not evicted)" --> HITGEN
        RAW -- clear --> EVICT
    end

    subgraph QUE["Per-bank in-flight queues [v1.9.9]"]
        direction TB
        BQ["16 FIFOs · depth BANK_DEPTH<br/>arrival order · head-only active<br/>row-hit promotion on evict (FR-FCFS)"]
        HEADS["queue_head[N_BANKS]<br/>{cmd-class-ready}"]
        DEPTH["queue_depth[N_BANKS]<br/>= relocated watermark"]
        BQ --> HEADS
        BQ --> DEPTH
    end

    %% ============================================================
    %%  STAGE 2 — can_* gates + cost classify
    %% ============================================================
    subgraph S2["Stage 2 — can_* Gate Check + Cost Classify"]
        direction TB
        GATE["gate_gen · legal()<br/>can_cas / can_act / can_pre (hard mask)<br/>can_cas_any / can_act_any / can_faw<br/>can_rd_wr / can_wr_rd"]
        COST["cost classify<br/>hit_set_bitmap / miss_set_bitmap<br/>remaining_cost[bank]"]
        GATE --> COST
    end

    %% ============================================================
    %%  STAGE 3 — winner selection (SJF → weight arbiter)
    %% ============================================================
    subgraph S3["Stage 3 — Winner Select (weight arbiter [v1.9.9])"]
        direction TB
        GRD{"DQ free now AND<br/>a legal CAS ready?"}
        ARB["argmax weight<br/>K·control + age + servo_mod<br/>control: CAS 2 / ACT 1 / PRE 0"]
        WMARK["wr_count / wr_high_wm_hit<br/>wr_low_wm_hit → R/W batch bias"]
        GRD -- "yes: guardrail CAS" --> WIN["winner_*"]
        GRD -- no --> ARB
        WMARK --> ARB
        ARB --> WIN
    end

    %% ============================================================
    %%  STAGE 4 — emission + writeback
    %% ============================================================
    subgraph S4["Stage 4 — Command Emission + Writeback"]
        direction TB
        MUX{"s4_mux<br/>s0_override ? maint : winner"}
        DRV["dfi_drv · encode DDR5 command"]
        WB["writeback — the ONLY state writer<br/>bank_fsm_update / global_timing_update<br/>status_update / raa_inc / sched_ack"]
        MUX --> DRV
        MUX --> WB
    end

    TRF["timing_reg_file<br/>next_cas/pre/act, tFAW ring, nRdWr/nWrRd<br/>row_open, state, last_act_bg"]
    DFI[("DFI bus<br/>dfi_address / dfi_cs_n / dfi_act_n<br/>dfi_bg / dfi_bank / dfi_wrdata(_en/_mask)")]

    %% ---------------- MCC → Stage 1 ----------------
    WRTCAM -- "wr_tcam_hit_bitmap / wr_tcam_hit_meta" --> HITGEN
    RDTCAM -- "rd_tcam_hit_bitmap / rd_tcam_hit_meta" --> HITGEN
    VALID  -- "wr_occupied (head/tail · no valid bit)<br/>rd pre-filter retired" --> HITGEN
    HITGEN --> RAW
    EVICT -- "s1_evict_en / _bank / _entry(§9E)" --> BQ
    DEPTH -- "queue_full[N_BANKS] (backpressure)" --> RDBUF
    HITGEN -- "tcam_full (admission stall)" --> RDBUF

    %% ---------------- Stage 1/queues → Stage 2 ----------------
    HEADS -- "s1_hit_bitmap / s1_hit_meta[]" --> GATE
    TRF -- "next_cas/pre/act_out, state_out, row_open_out" --> GATE
    GC -- gc --> GATE

    %% ---------------- Stage 2 → Stage 3 ----------------
    COST -- "hit_set_bitmap / miss_set_bitmap / remaining_cost[]" --> GRD
    COST --> ARB
    VALID -- "rd_status_age / wr_status_age" --> ARB
    DEPTH -- "queue_depth (age term)" --> ARB
    TRF -- "last_act_bg_out (BG rotation)" --> ARB
    GC -- gc --> ARB

    %% ---------------- Stage 3 → Stage 4 ----------------
    WIN -- "winner_valid / winner_cmd_type<br/>winner_rank/bg/bank/row/col<br/>winner_entry_idx / winner_req_type" --> MUX
    S0LOG -- "s0_override / s0_cmd_type<br/>s0_rank/bg/bank" --> MUX

    %% ---------------- Stage 4 emission ----------------
    WRBUF -- "wr_req_buffer_rd_data (write payload)" --> DRV
    TRF -- "timing_reg_vals (parallel)" --> DRV
    DRV --> DFI

    %% ---------------- writeback loop + acks ----------------
    WB -. "bank_fsm_update_* / global_timing_update_*" .-> TRF
    TRF -. "next clock edge" .-> GATE
    WB -. "status_update_en/idx/val" .-> VALID
    VALID -. "*_invalidate/update_status_schd_cmd → MCC" .-> RDBUF
    WB -. "sched_ack → Maintenance Engine" .-> S0LOG
    WB -. "raa_inc_en → Per-Rank FSM" .-> TRF
    WB -. "retire / dequeue" .-> BQ
```

## Reading it

- **Boundary (top).** Everything in the `MCC` box is the right-hand edge of `mcc_v3.1`:
  the read/write buffers, the two TCAM reg arrays, the status/age registers (no valid bit),
  and `global_32b_counter` (= `gc`). The scheduler consumes hit vectors + `wr_occupied` + gc
  (**no valid bit** [v1.9.9]) and returns `*_schd_cmd` invalidate/update writes — no second
  command path back to MCC.
- **Stage 0** sits *beside* the pipe, not in it: it only reaches DFI through `s4_mux`
  (`s0_override`). Priority `ref_urgent > ref_due > rfm > zq`.
- **Stage 1** masks the RAW TCAM hit with `wr_occupied` (write-buffer head/tail range,
  **no valid bit** [v1.9.9]; the RD bank pre-filter is retired — candidates are the queue
  heads), resolves RAW once at admission (held reads
  raise `raw_block_en`, they are **not** evicted), then `s1_evict` drops the classified
  entry into its **per-bank FIFO**. `queue_full` / `tcam_full` are the only backpressure.
- **Per-bank queues [v1.9.9]** are the real reorder surface: 16 FIFOs, head-only active,
  row-hit promotion on eviction (FR-FCFS open-page). Only the 16 `queue_head`s compete —
  not the flat TCAM bitmap.
- **Stage 2** hard-masks legality (`can_*`) and splits `hit_set` / `miss_set` with a
  `remaining_cost` per bank. No subtractor in the emit path — timing is precomputed in
  `timing_reg_file`.
- **Stage 3** picks the winner. Guardrail first (**never idle DQ**: DQ free + legal CAS ⇒
  CAS wins), else `argmax(K·control + age + servo_mod)`. Watermarks bias R/W batching.
- **Stage 4** muxes maintenance vs winner, encodes the DDR5 command onto DFI, and runs the
  **single** writeback: it advances `timing_reg_file`, writes req status back to MCC,
  acks the maintenance engine, bumps RAA, and retires the queue entry. The next clock edge
  feeds `timing_reg_file` back into Stage 2 — that is the scheduler loop.

Solid arrows = command/data flow forward to emission. Dashed arrows = the writeback /
feedback edges (state update, status writeback, acks) that close on the next clock.
