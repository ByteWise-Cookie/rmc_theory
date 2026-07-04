# `rmc_scheduler_ref.py` — Model Explainer

## What it is

Pure-Python behavioral model of `rmc_scheduler.sv` (block #22, handoff §8). No RTL, no synthesis — a second, independent implementation of the same spec, used to scoreboard the real RTL cycle-by-cycle once a cocotb testbench exists. Convention taken from OpenHBM's `dv/env/<ip>_ref.py` pattern.

Value: forces spec ambiguity and logic bugs out **before** RTL exists, not during RTL/DV divergence debug.

---

## Scope vs handoff §8

| Stage | Modeled | Method |
|---|---|---|
| 0 — Maintenance Override | partially | `stage0()` — reports override asserted; real REF/RFM/ZQ target selection deferred to ME (block #27) |
| 1 — TCAM Search | yes | `stage1_search()` |
| 2 — can_* Gate + SJF Cost | yes | `stage2_classify()` |
| 3 — SJF Winner Select | yes | `stage3_select()` |
| 4 — Command Emission + Writeback | yes | `stage4_emit()` |
| NOP-cycle: Opportunity REFsb | no | needs Bank Activity Counter Table ref model |
| NOP-cycle: Speculative ACT | no | needs Bank Partition Controller ref model |

---

## Data model

| Class | RTL equivalent | Note |
|---|---|---|
| `WrSlot` / `RdSlot` | WR_TCAM+WR_status_reg / RD_TCAM+RD_status_reg (blocks #10/#12, #11/#13) | CAM entry and status-reg fields **collapsed into one record** — behaviorally always read together (valid gates match), so the CAM/RAM physical split isn't worth modeling here |
| `BankFsm` | Per-Bank FSM Table (block #24) | state + 4 deadline fields + `can_cas/can_pre/can_act/can_ref` computed methods |
| `Candidate` | — (pipeline-internal) | one per bank per cycle: cost class, cost, `ready_now`, `starved` |

---

## Key mechanisms

**`gc_ge(gc, deadline)`** — wraparound-safe `gc >= deadline`, bit-for-bit matching the RTL's `(gc - deadline)[MSB]==0` trick instead of a naive Python `>=` (which would break at `GC_WIDTH` rollover).

**`ready_now` gating** — cost (for SJF ranking) and can_* gate (for issuability) are separate concerns in the spec; a candidate needs both. First draft only tracked cost and let anything with a finite cost win — see Bugs Found below.

**`_fsm_background_update()`** — §9A lists `ACTIVATING→ACTIVE` and `PRECHARGING→IDLE` as *condition-driven* (fires on `can_cas`/`can_act`, not on a Scheduler command). Modeled as a pass over all banks at the top of every `cycle()`, before Stage 1 — matches synchronous RTL semantics (Stage 1 sees the state as of the last clock edge).

**Starvation restricted to `MISS_SET`** — spec names it `STARVED_MISS` specifically; `HIT_SET` (cost=0) never needs a starvation boost, so promotion only applies to `MISS_SET` candidates, and only once `ready_now` is also true.

**RD/WR mode hysteresis** — `WR_HIGH_WM`/`WR_LOW_WM` flip logic implemented; `AGE_THR2` force-flip is not (needs a "cycles since last flip" counter, not yet added).

---

## Verified behavior (smoke test)

| Scenario | Sequence | Result |
|---|---|---|
| 1: IDLE bank, single RD | `ACT@0 → CAS_RD@14` | exact `t_rcd`=14 |
| 2: row-miss on ACTIVE bank | `PRE@22 → ACT@36 → CAS_RD@50` | exact `t_rp`=14, `t_rcd`=14, zero slack |

Both land exactly on the configured timing boundaries — the scheduler issues the instant a command is legal, never early, never late.

---

## Bugs the smoke test caught (fixed before shipping)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `CAS_RD` fired 1 cycle after `ACT` (should be after `t_rcd`) | `stage3_select` let `PENDING`-class (ACTIVATING) candidates into the winnable pool | excluded `PENDING` from `issuable`; added `_fsm_background_update()` so `ACTIVATING→ACTIVE` actually happens |
| 2 | `PRE` fired 2 cycles before `next_pre` deadline | Stage 2 computed *cost* for row-miss but never checked `can_pre` before letting Stage 3 pick it | added `ready_now` field, gated per-state on the correct `can_*` flag |

---

## Known gaps (not silently resolved — flagged in file docstring)

- **WR_TCAM dual-use ambiguity**: §6 defines it as full-address exact match (RAW hazard use); §8 Stage 1 implies a `{bg,bank}`-only pre-filter read too. Model resolves as a second ternary view; real RTL port count/structure undecided.
- **tCCD back-to-back spacing** not enforced — needs the Global Timing Table (block #26, not yet stubbed in RTL either).
- **can_\* registration timing** — model evaluates combinationally; RTL registers it 1 cycle later. Fine for functional checks, needs alignment before cycle-accurate cocotb scoreboarding.
- **Stage 0 → ME integration** — override detection only; actual REFAB/REFsb/RFM/ZQ target selection belongs to the (unmodeled) Maintenance Engine.
