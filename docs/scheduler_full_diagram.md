# RMC Scheduler — Full Stitched Block Diagram

One Mermaid diagram of the whole scheduler the golden model
[`../tools/sched_model/sched_test.js`](../tools/sched_model/sched_test.js) implements:
front-end → admission → per-bank queues → gates → weight arbiter → emit → DFI, with the
timing-scoreboard feedback loop and the maintenance-engine override. Renders inline on
GitHub. Detail views: [`scheduler_block_diagram.md`](scheduler_block_diagram.md) (per-stage),
[`../short_notes/scheduler_deep.md`](../short_notes/scheduler_deep.md) §7 (net list).

```mermaid
flowchart TB
    %% ---------------- front-end ----------------
    subgraph FE["Front-end (AXI clock → single CDC)"]
        direction TB
        AXI["AXI4 host<br/>read / write ports"] --> AMU["AMU<br/>address map + XOR hash"]
        AMU --> ROB["ROB<br/>{AXID, seqnum} order"]
        ROB --> CDC["async REQ FIFO<br/>(the one CDC)"]
        WDB["Write Data Buffer<br/>(index SRAM)"]
    end

    CDC --> TCAM

    %% ---------------- admission ----------------
    subgraph ADM["Admission — short TCAM (classify station)"]
        direction TB
        TCAM["classify<br/>{bg,bank} search<br/>row vs open_row → hit/miss"] --> RAW{"RAW: older write<br/>same addr in flight?<br/>(match masked by wr_occupied,<br/>head/tail range · no valid bit)"}
        RAW -- yes --> HOLD["hold in TCAM<br/>(entry blocked)"]
        RAW -- no --> EV["evict when the<br/>bank queue has room"]
        HOLD -. write drains .-> RAW
    end

    EV -->|"row-hit promotion:<br/>insert after last same-row entry"| BQ

    %% ---------------- per-bank queues ----------------
    subgraph QUE["Per-bank in-flight queues"]
        direction TB
        BQ["16 FIFOs · row-clustered<br/>(not strict FIFO) · head-only active"] --> HEADS["queue heads<br/>(1 candidate per bank)"]
        BQ --> DEPTH["head/tail pointers + depth counter<br/>= relocated watermark (no valid bit)"]
    end
    DEPTH -. queue full .-> TCAM

    %% ---------------- scoreboard ----------------
    subgraph SB["Timing scoreboard — registered state"]
        direction TB
        S1["per-bank: open_row,<br/>next_cas / pre / act, lockAge, state"]
        S2["per-BG: next_cas_bg, next_act_bg"]
        S3["per-rank: next_act_any,<br/>tFAW ring, nRdWr, nWrRd"]
        S4["global: next_cas_any, dqFree,<br/>caFree, nPreAny, lastCasBg"]
        S5["demand[bank][row]<br/>+ row-lock (AGE_MAX)"]
    end

    %% ---------------- gates + candidates ----------------
    HEADS --> GATE
    SB --> GATE
    GATE["gate_gen · legal()<br/>can_cas / can_act / can_pre<br/>(hard mask, no subtractor)"] --> CAND["cand_gen<br/>one legal candidate per bank"]

    %% ---------------- weight arbiter ----------------
    subgraph ARBX["Weight arbiter (block 12)"]
        direction TB
        CTRL["control weight<br/>CAS 2 / ACT 1 / PRE 0"]
        AGE["aging counter<br/>+1 per wait, 0 on win"]
        SRV["DQ servo (default OFF)<br/>boost / damp ACT"]
        BAT["adaptive batch R/W<br/>flip on gateLoss / stall"]
        GRD{"DQ free now AND<br/>a legal CAS?"}
        ARB["argmax weight<br/>K·control + age + servo"]
    end
    CAND --> GRD
    CTRL --> ARB
    AGE --> ARB
    SRV --> ARB
    BAT --> ARB
    GRD -- "yes (guardrail): CAS" --> WIN["winner"]
    GRD -- no --> ARB
    ARB --> WIN

    %% ---------------- emit + maintenance ----------------
    ME["maintenance_engine<br/>Init / Refresh / RFM / ZQ / PwrMgmt / MR"] --> S0["s0_override<br/>ref_urgent → ref_due → rfm → zq"]
    WIN --> MUX
    S0 --> MUX
    MUX{"s4_mux<br/>override or winner"} --> DRV["dfi_drv<br/>encode command"]
    DRV --> DFI[("DFI bus<br/>cmd / addr / bank / bg")]
    WDB -. write data .-> DRV

    %% ---------------- writeback loop ----------------
    MUX --> WB["writeback (block 15) — the ONLY writer<br/>update next_*, retire entry,<br/>watermark, RAA, ref_credits"]
    WB -. next clock edge .-> SB
    WB -. retire / dequeue .-> BQ
```

**The loop:** `writeback` is the single state writer — it advances the scoreboard, which the
next clock edge feeds back into `gate_gen`; the arbiter picks; `writeback` commits. The
maintenance engine reaches the DFI bus only through `s4_mux` (`s0_override`), never a second
command path. TCAM classifies then evicts (short residency); on eviction a row-hit is
**promoted** next to its same-row siblings (insert after the last same-row entry) so it
isn't stranded behind a same-bank miss; only bank heads compete; RAW is
resolved once at admission.
