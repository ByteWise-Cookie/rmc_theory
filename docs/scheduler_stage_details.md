# RMC Scheduler — Per-Stage Detail Diagrams

Zoom views for [`scheduler_cmd_pipeline_diagram.md`](scheduler_cmd_pipeline_diagram.md).
One Mermaid block per stage (S0–S4), each expanded to net / gate level. Ports = frozen
`RMC_IO_Map.md §19`; `[v1.9.9]` = per-bank-queue / weight-arbiter rework nets. Golden
reference: [`../tools/sched_model/sched_test.js`](../tools/sched_model/sched_test.js).

Signal direction convention (matches the IO map): `→` an input the stage consumes,
`←` an output the stage drives.

---

## Stage 0 — Maintenance Override

Sits beside the pipe. Reaches DFI only through Stage-4's `s4_mux`. Pure priority select.

```mermaid
flowchart LR
    subgraph IN0["→ inputs"]
        direction TB
        I0a["ref_urgent 1b"]
        I0b["ref_due 1b"]
        I0c["zq_due 1b"]
        I0d["rfm_req[N_RANKS][DFI_MASK]"]
        I0e["global_state [BURST_WIDTH]"]
    end
    subgraph LOG0["s0 logic"]
        direction TB
        PRI{"priority mux<br/>ref_urgent &gt; ref_due<br/>&gt; rfm &gt; zq"}
        FMT["format maint cmd<br/>rank/bg/bank select"]
        PRI --> FMT
    end
    subgraph OUT0["← outputs (to s4_mux)"]
        direction TB
        O0a["s0_override 1b"]
        O0b["s0_cmd_type [BURST_WIDTH]"]
        O0c["s0_rank [RANK_BITS]"]
        O0d["s0_bg [BG_BITS]"]
        O0e["s0_bank [BANK_BITS]"]
    end
    I0a --> PRI
    I0b --> PRI
    I0c --> PRI
    I0d --> PRI
    I0e --> FMT
    FMT --> O0a
    FMT --> O0b
    FMT --> O0c
    FMT --> O0d
    FMT --> O0e
```

---

## Stage 1 — TCAM Search / Admission / Per-Bank Queues

ANDs TCAM hit with `VALID`, resolves RAW once, evicts classified entry into its per-bank
FIFO. Held reads raise `raw_block_en` (not evicted). Only the 16 heads leave the stage.

```mermaid
flowchart LR
    subgraph IN1["→ from MCC (mcc_v3.1)"]
        direction TB
        M1a["wr_tcam_hit_bitmap [N_WR_ENTRIES]"]
        M1b["wr_tcam_hit_meta (per bank)"]
        M1c["rd_tcam_hit_bitmap [N_RD_ENTRIES]"]
        M1d["rd_tcam_hit_meta (per bank)"]
        M1e["wr_status_valid / rd_status_valid"]
    end
    subgraph LOG1["Stage 1 logic"]
        direction TB
        AND1["hit &amp; VALID<br/>→ s1_hit_bitmap[N_BANKS]<br/>s1_hit_meta{row,col,req_type,<br/>entry_idx,axi_id}"]
        RAW{"RAW: older write<br/>same addr in flight?"}
        EVL["s1_evict: classify<br/>+ RAW-clear"]
        AND1 --> RAW
        RAW -- "no → evict" --> EVL
        RAW -- "yes → hold" --> RB(["raw_block_en 1b"])
    end
    subgraph QUE1["per-bank queues [v1.9.9]"]
        direction TB
        F["16 FIFOs · depth BANK_DEPTH<br/>head-only active<br/>row-hit promotion on evict"]
        H["queue_head[N_BANKS]<br/>{cmd-class-ready}"]
        D["queue_depth[N_BANKS]<br/>relocated watermark"]
        F --> H
        F --> D
    end
    subgraph OUT1["← outputs"]
        direction TB
        O1a["s1_hit_bitmap [N_BANKS]"]
        O1b["s1_hit_meta[]"]
        O1c["queue_full[N_BANKS]"]
        O1d["tcam_full 1b"]
    end
    M1a --> AND1
    M1b --> AND1
    M1c --> AND1
    M1d --> AND1
    M1e --> AND1
    EVL -- "s1_evict_en/_bank/_entry(§9E)" --> F
    H --> O1a
    H --> O1b
    D --> O1c
    AND1 --> O1d
```

---

## Stage 2 — can_* Gate Check + Cost Classification

Hard-masks legality from precomputed timing (no subtractor in path), splits hit/miss sets,
tags each bank's remaining cost. Candidate set = the 16 `queue_head`s, not the flat bitmap.

```mermaid
flowchart LR
    subgraph IN2["→ inputs"]
        direction TB
        P2a["s1_hit_bitmap / s1_hit_meta[]"]
        P2b["state_out / row_open_out"]
        P2c["next_cas_out / next_pre_out / next_act_out"]
        P2d["gc [GC_WIDTH]"]
    end
    subgraph LOG2["gate_gen · legal()"]
        direction TB
        GC2["can_cas / can_pre / can_act<br/>(hard mask per bank)"]
        GG["can_cas_any / can_act_any<br/>can_cas_bg / can_act_bg<br/>can_faw / can_rd_wr / can_wr_rd"]
        RFC["gate_rfc[N_RANKS]<br/>gate_zq[N_RANKS]"]
        CLS["cost classify<br/>hit vs miss + remaining cost"]
        GC2 --> CLS
        GG --> CLS
    end
    subgraph OUT2["← outputs"]
        direction TB
        O2a["can_cas_out / can_pre_out / can_act_out"]
        O2b["can_*_any / can_*_bg / can_faw"]
        O2c["can_rd_wr_out / can_wr_rd_out"]
        O2d["hit_set_bitmap [N_BANKS]"]
        O2e["miss_set_bitmap [N_BANKS]"]
        O2f["remaining_cost[] [GC_WIDTH]"]
    end
    P2a --> GC2
    P2b --> GC2
    P2c --> GC2
    P2d --> GC2
    P2b --> RFC
    GC2 --> O2a
    GG --> O2b
    GG --> O2c
    CLS --> O2d
    CLS --> O2e
    CLS --> O2f
```

---

## Stage 3 — Winner Select (weight arbiter [v1.9.9])

Guardrail first (never idle DQ), else `argmax(K·control + age + servo_mod)` over legal
heads. Watermarks bias R/W batch direction.

```mermaid
flowchart LR
    subgraph IN3["→ inputs"]
        direction TB
        P3a["hit_set_bitmap / miss_set_bitmap"]
        P3b["remaining_cost[]"]
        P3c["rd_status_age / wr_status_age"]
        P3d["wr_count / wr_high_wm_hit / wr_low_wm_hit"]
        P3e["last_act_bg_out [AWLEN][GC_WIDTH]"]
        P3f["gc [GC_WIDTH]"]
    end
    subgraph LOG3["arbiter"]
        direction TB
        GRD{"DQ free now AND<br/>legal CAS ready?"}
        WT["weight = K·control<br/>+ age + servo_mod<br/>control: CAS 2 / ACT 1 / PRE 0"]
        BAT["R/W batch bias<br/>from watermarks"]
        ARG["argmax over legal heads"]
        GRD -- "yes: guardrail CAS" --> WSEL["winner"]
        GRD -- no --> WT
        BAT --> WT
        WT --> ARG
        ARG --> WSEL
    end
    subgraph OUT3["← outputs"]
        direction TB
        O3a["winner_valid 1b"]
        O3b["winner_cmd_type (ACT/CAS_RD/CAS_WR/PRE)"]
        O3c["winner_rank/bg/bank"]
        O3d["winner_row/col"]
        O3e["winner_entry_idx"]
        O3f["winner_req_type 1b"]
    end
    P3a --> GRD
    P3a --> ARG
    P3b --> WT
    P3c --> WT
    P3d --> BAT
    P3e --> ARG
    P3f --> WT
    WSEL --> O3a
    WSEL --> O3b
    WSEL --> O3c
    WSEL --> O3d
    WSEL --> O3e
    WSEL --> O3f
```

---

## Stage 4 — Command Emission + Writeback

Muxes maintenance vs winner, encodes DDR5 command onto DFI, runs the single writeback that
closes every feedback loop. The next clock edge feeds `timing_reg_file` back into Stage 2.

```mermaid
flowchart LR
    subgraph IN4["→ inputs"]
        direction TB
        P4a["winner_* (all fields)"]
        P4b["s0_override / s0_cmd_*"]
        P4c["timing_reg_vals (parallel)"]
        P4d["wr_req_buffer_rd_data (write payload)"]
        P4e["gc [GC_WIDTH]"]
    end
    subgraph LOG4["Stage 4 logic"]
        direction TB
        MUX{"s4_mux<br/>s0_override ? maint : winner"}
        DRV["dfi_drv · encode DDR5 cmd"]
        WBK["writeback — ONLY state writer"]
        MUX --> DRV
        MUX --> WBK
    end
    subgraph OUT4["← outputs"]
        direction TB
        D4["DFI: dfi_address / dfi_cs_n / dfi_act_n<br/>dfi_bg / dfi_bank<br/>dfi_wrdata / _en / _mask"]
        W4a["bank_fsm_update_en/_*"]
        W4b["global_timing_update_*"]
        W4c["status_update_en/_idx/_val → MCC"]
        W4d["sched_ack → Maintenance Engine"]
        W4e["raa_inc_en → Per-Rank FSM"]
    end
    P4a --> MUX
    P4b --> MUX
    P4c --> DRV
    P4d --> DRV
    P4e --> WBK
    DRV --> D4
    WBK --> W4a
    WBK --> W4b
    WBK --> W4c
    WBK --> W4d
    WBK --> W4e
```

**Loop closure:** `W4a/W4b` write `timing_reg_file` → next clock edge → Stage 2 gates.
`W4c` writes req status back to MCC (`*_invalidate/update_status_schd_cmd`). Stage 0 gets
`sched_ack` only after its override actually emitted. No second command path exists.
