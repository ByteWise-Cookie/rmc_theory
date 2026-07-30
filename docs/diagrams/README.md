# RMC — Diagrams

All GitHub-native **mermaid** block/signal diagrams for the RMC front-end and scheduler.
Every file renders inline on GitHub (no export needed). All are `[v1.9.9]`-consistent:
residency split, per-bank queues, weight arbiter, row-hit promotion, never-idle-DQ guardrail,
**no valid bit** (occupancy = FIFO head/tail, RAW gate = `wr_occupied`).

| File | Scope | Detail level |
|---|---|---|
| [`mcc_v3.1_diagram.md`](mcc_v3.1_diagram.md) | **MCC front-end** — request buffers + RAW engine (mermaid recreation of the `mcc_v3.1.vsdx` Visio drawing) | full block + signal + ports |
| [`scheduler_cmd_pipeline_detailed.md`](scheduler_cmd_pipeline_detailed.md) | **Scheduler**, mcc_v3.1-style — every sub-block, signal, port + glossary + signal dictionary | maximum |
| [`scheduler_cmd_pipeline_diagram.md`](scheduler_cmd_pipeline_diagram.md) | Scheduler — MCC handoff → DFI emission, 5-stage | high |
| [`scheduler_full_diagram.md`](scheduler_full_diagram.md) | Scheduler — one stitched overview flowchart | medium |
| [`scheduler_block_diagram.md`](scheduler_block_diagram.md) | Scheduler — per-stage block views (dataflow / residency / arbiter) | medium |
| [`scheduler_stage_details.md`](scheduler_stage_details.md) | Scheduler — S0–S4 net-level zoom | high |

**Reading order:** `mcc_v3.1_diagram` (where requests come from) → `scheduler_cmd_pipeline_detailed`
(the full picks-up-from-there) → `scheduler_full_diagram` (overview) → the per-stage zooms.

Source specs: [`../scheduler_queue_arch.md`](../scheduler_queue_arch.md),
[`../../short_notes/scheduler_deep.md`](../../short_notes/scheduler_deep.md).
Golden model: [`../../tools/sched_model/sched_test.js`](../../tools/sched_model/sched_test.js).
