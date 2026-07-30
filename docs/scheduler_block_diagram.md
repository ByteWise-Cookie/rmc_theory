# RMC Scheduler — Block Diagrams

GitHub-native (Mermaid) block diagrams of the scheduler the golden model
[`../tools/sched_model/sched_test.js`](../tools/sched_model/sched_test.js) implements.
Authoritative wiring: [`../short_notes/scheduler_deep.md`](../short_notes/scheduler_deep.md) §7;
residency split: [`scheduler_queue_arch.md`](scheduler_queue_arch.md).

---

## 1. Scheduler dataflow (blocks 9–15, the closed loop)

```mermaid
flowchart TB
    SRC["front-end<br/>AMU / ROB / WDB"] --> ADM

    subgraph SCH["Scheduler (read-only vs state, writes only at 15)"]
        direction TB
        ADM["9 · classify / admission<br/>short TCAM: {bg,bank} search,<br/>row vs open_row, RAW compare<br/>(mask = wr_occupied, no valid bit),<br/>evict to bank queue"]
        Q["9b · per-bank queues ×16<br/>FIFO (head/tail ptr, no valid bit)<br/>head-only active"]
        GATE["10 · gate_gen<br/>can_cas / can_act / can_pre"]
        CAND["11 · cand_gen<br/>one candidate per bank"]
        ARB["12 · weight arbiter<br/>K·control + age + servo<br/>guardrail: never idle DQ"]
        MUX["13 · s4_mux<br/>winner + s0_override"]
        DRV["14 · dfi_drv"]
        WB["15 · writeback<br/>scoreboard next_*, retire"]

        ADM --> Q --> GATE --> CAND --> ARB --> MUX --> DRV
        MUX --> WB
    end

    ME["maintenance_engine<br/>REF / RFM / ZQ (s0_override)"] --> MUX
    DRV --> DFI[("DFI bus<br/>cmd / addr / bank / bg")]
    WB -. "next clock edge" .-> GATE
```

Loop: writeback updates the scoreboard, next edge feeds `gate_gen`, arbiter picks, writeback
commits. The maintenance engine injects refresh/RFM/ZQ through the same `s4_mux` — no third
command path.

---

## 2. Residency split — admission → per-bank queues → heads

The post-mentor rework: TCAM is a **short classify station**, not a lifetime home. Classified
requests **evict** into per-bank FIFOs; only the **head** of each bank competes. On
eviction a row-hit is **promoted** next to its same-row siblings (insert after the last
same-row entry, not the tail) so it isn't stranded behind a same-bank miss — reorders only
across *different* rows (no hazard); same-row order preserved.

```mermaid
flowchart LR
    A["arrivals<br/>(arrival order)"] --> T

    subgraph ADMIT["TCAM admission (short residency)"]
        T["classify {bg,bank}<br/>row-hit vs miss<br/>RAW full-addr compare<br/>(mask = wr_occupied · no valid bit)"]
    end
    T -- "RAW: older write<br/>same addr → hold" --> T

    T -->|"evict + row-hit promote"| B0["bank 0 FIFO"]
    T -->|"evict + row-hit promote"| B1["bank 1 FIFO"]
    T -->|"evict + row-hit promote"| BN["bank … 15 FIFO"]

    B0 --> H{{"heads only<br/>→ weight arbiter"}}
    B1 --> H
    BN --> H

    B0 -. "queue full" .-> BP["backpressure<br/>TCAM-full stalls admission"]
    BP -.-> T
```

Timers (`next_cas/pre/act`) are **per-bank scoreboard** properties the head reads — not
per-entry. Occupancy = per-bank **head/tail pointers + depth counter** = the relocated
watermark. **No per-entry `valid` bit** (mentor) — the pointers already say which slots are
live (head..tail occupied, rest empty by construction).

---

## 3. Per-cycle decision (the arbiter pick)

```mermaid
flowchart TB
    START(["cycle @ gc"]) --> CA{"gc below caFree?<br/>(CA bus busy)"}
    CA -- yes --> SKIP["gc = caFree"] --> START
    CA -- no --> REF{"refresh due?<br/>(s0 override)"}
    REF -- yes --> DOREF["drain → PREA → REF"] --> START
    REF -- no --> SCAN["scan bank heads:<br/>classify → CAS / ACT / PRE,<br/>apply legal() gates"]

    SCAN --> GUARD{"DQ free now<br/>AND a legal CAS?"}
    GUARD -- yes --> EMITC["CAS wins (guardrail)"]
    GUARD -- no --> WEIGH["argmax weight<br/>K·control + age (+servo on ACT)"]
    WEIGH --> PICK{"any legal<br/>candidate?"}
    PICK -- yes --> EMIT["emit + writeback"]
    PICK -- no --> STALL["stall++ ; adaptive batch flip / gc++"]
    EMITC --> EMIT
    EMIT --> START
    STALL --> START
```

---

## Rendering

GitHub, GitLab, VS Code (with Mermaid preview), and Obsidian all render ```mermaid fences
natively — no image export, no Excalidraw round-trip. Edit the fence text and the diagram
updates. The existing `.excalidraw` / `.png` diagrams (referenced from `scheduler_deep.md`)
stay as the hand-drawn detail views; these are the always-current, diff-able block views.
