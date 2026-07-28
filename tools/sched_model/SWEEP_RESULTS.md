# Scheduler Weights/Sizing Sweep — Results (OQ-20 / OQ-21)

Sweep of the weight arbiter + per-bank queue sizing against the golden model
(`sched_test.js`, `queueArch`, DDR5-4800B timing). Reproduce:

```
node tools/sched_model/sweep.js          # full grid
node tools/sched_model/sweep.js --quick  # smaller grid
```

Trace suite: 6 traces (interleave/rowlocal × R/W mix × locality × seed), 4000 reqs each.
Objective: max suite-mean DQ-busy, keep tail wait bounded, every emit legal
(0 violations / 0 unscheduled). Metrics: `busy` = DQ occupancy %; `tailWait` = max
over traces of the worst request wait (tCK, from admission to service); `meanWait` = mean.

## Headline finding

**Arbiter weights are second-order; sizing + the never-idle-DQ guardrail dominate.**
Suite-mean DQ-busy holds ~35.2% essentially flat across every `K` / control-tier /
servo combination. Only the 16 bank *heads* are reorderable — per-bank FIFO order fixes
intra-bank waiting, so the `age` term has little leverage (the "16 queues lose global
age order" caveat, `scheduler_queue_arch.md §7`). The DQ-occupancy **servo showed no
measurable gain** on the synthetic suite; the **guardrail** (DQ free + a legal CAS ⇒ CAS
wins absolutely) is the part that matters.

Note: the ~35% ceiling reflects the synthetic suite being ACT-bound / low-locality — a
**relative-tuning** number, not a hardware throughput target.

## Pass A — arbiter weights (fixed depth=8, tcam=32)

DQ-busy flat at 35.2% across K ∈ {50…100000}, control ∈ {2/1/0, 3/1/0, 4/2/1},
servo ∈ {off, std, aggr}. High K (control-led) gives the same busy as low K; low K only
inflates tail (age reordering among heads without throughput benefit). Chosen: control
**2/1/0**, **K=5000** (control leads normal ops, age is a pure starvation backstop),
**servo default-off**, guardrail on.

## Pass B — sizing (chosen arbiter fixed)

| bankDepth | tcam | inflight | busy | tailWait | meanWait |
|--:|--:|--:|--:|--:|--:|
| 2 | 32 | ≤32 | 32.2% | 13263 | 1958 |
| 4 | 32 | ≤64 | 33.5% | 14742 | 2262 |
| 6 | 32 | ≤96 | 34.0% | 15797 | 2567 |
| **8** | **32** | **≤128** | **35.2%** | **16773** | **2863** |
| 12 | 32 | ≤192 | 35.5% | 19771 | 3424 |
| 8 | 16 | ≤128 | 33.0% | 11123 | 2028 |
| 8 | 8 | ≤128 | 31.5% | 8292 | 1578 |
| 4 | 16 | ≤64 | 30.7% | 8549 | 1486 |
| 4 | 8 | ≤64 | 28.2% | 5721 | 1070 |
| 2 | 8 | ≤32 | 26.0% | 4170 | 819 |

- Throughput plateaus past depth ≈8 (<0.3pt/step for +50% storage beyond).
- **tcam=32 is worth it** — dropping to 16/8 costs 3–7pt busy (admission visibility).
- R/W org probe: `rawPause` on/off = 35.2% vs 35.0% (negligible). Unified per-bank+tag
  confirmed; `rawPause` is the guard reserved for the split-R/W-queue variant.

## Chosen design point (recorded as intent — pkg frozen until RTL go)

| Knob | Value | Note |
|---|---|---|
| arbiter | weighted | `K·control + age + servo_mod(ACT)`, argmax over legal |
| control (CAS/ACT/PRE) | 2 / 1 / 0 | SJF tiers |
| K | 5000 | control-vs-age scale; age = starvation backstop |
| guardrail | ON | DQ free + legal CAS ⇒ CAS absolute (essential) |
| servo | retained, default-OFF | no synthetic gain; revisit with real traces |
| AGE_MAX | 256 | row-lock cap (independently validated by hammer test) |
| bankDepth | 8 | per-bank in-flight FIFO; total in-flight ≤ 128 |
| tcam | 32 | admission depth |
| R/W org | unified per-bank + tag | rawPause guard reserved for split variant |

Suite result at this point: mean DQ-busy 35.2%, tailWait 16773, all traces legal.

Open follow-ups: real (non-synthetic) traffic traces to re-test the servo and the
depth/tail trade; the arbiter `age` leverage is inherently capped by per-bank FIFO order,
so global-QoS fairness (if needed) would require cross-queue age visibility, not tuning.
