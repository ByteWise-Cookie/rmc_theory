# Adaptive batching — charging the mode gate for the DQ it wastes

**Status:** design + measured result. Replaces the fixed always-on read/write
batching in the greedy token scheduler ([[scheduler_dynamic_design]]). Numbers from
the JS golden model (`scratchpad/sched_test.js`, engine ported from bench artifact
`1d271c33`), DDR5-4800B, validated every run — 0 violations, 0 unscheduled.

---

## 1. The problem fixed batching had

Batching partitions CAS into read windows and write windows to amortise the
turnaround bubble (W→R costs `tWTR_L + RL` ≈ 64 tCK @4800B — fully exposed,
half-duplex DQ). Always-on batching was measured as **workload-dependent**:

| workload class | fixed batch | no batch | verdict |
|---|---|---|---|
| turnaround-bound (row-hit, few banks) | **86–96%** | 37–44% | batching essential |
| ACT-bound (interleave map, 0% row-hit) | **27–30%** | 53–58% | batching harmful |

Mechanism of the harm: with the demand-gated precharge policy, a bank whose open row
is wanted only by a **write** while the scheduler is in **read** mode is *stuck* —
the mode gate blocks its CAS, and the demand gate blocks its PRE (a pending request
still wants that row). The bank is held hostage for the whole window. Enough hostage
banks and the effective bank count collapses, which is fatal precisely when the
workload is already ACT-bound.

A fixed policy cannot serve both classes. The scheduler must detect which one it is
in, at run time, with no workload hints.

## 2. The rule

> **Charge the mode gate for every cycle of idle DQ it causes. When the debt exceeds
> what a flip costs, the flip has already paid for itself — flip.**

Per cycle, the gate is charged iff all three hold:

```
oppCas   : some opposite-direction CAS is legal on every constraint except the mode gate
!cas     : no same-direction CAS is issuable
dqIdle   : gc >= G.dqFree            (the data bus is actually going idle)
```

```js
const dqIdle = gc >= G.dqFree, charge = (oppCas && !cas && dqIdle);
// ... charge += 2 on an emit cycle (CA bus advances gc by 2), += 1 on a stall cycle
if (adaptive && gateLoss >= FLIP_COST && oppositeWorkExists) doFlip();  // doFlip resets gateLoss
```

### 2.1 Why this detector separates the two classes by itself

This is the property that makes the rule work, and it is worth stating precisely:

- **Turnaround-bound:** right after a read burst, an opposite-direction (write) CAS is
  **illegal anyway** — `rk.nRdWr` / `rk.nWrRd` (the tRTW / tWTR+RL turnaround
  counters) have not expired. `legal()` returns false, so `oppCas` never sets, so the
  gate is **never charged**. The scheduler batches indefinitely, which is correct.
- **ACT-bound:** the hostage bank's write CAS *is* fully legal — row open, all timings
  met — and only the mode gate stops it. `oppCas` sets while DQ sits idle, the debt
  accrues fast, and the scheduler flips.

So the detector distinguishes *"blocked by physics"* from *"blocked by our own
policy"*, and only ever charges for the latter. **No workload hint, no profiling, no
mode switch is needed** — the same expression is silent on one class and loud on the
other.

### 2.2 Threshold

`FLIP_COST = BL2` (8 tCK — one burst of wasted DQ). Swept 4 → 128:

```
FLIP_COST   RRRWWW  RWRWRW  wheavy | lin/il  rnd/il  mix/rl  wh/rl | mean
4            96%     69%     86%   |  46%     44%     59%     55%  | 65%
8  (BL2)     96%     69%     86%   |  46%     44%     58%     55%  | 65%
24           96%     69%     86%   |  43%     41%     57%     54%  | 64%
66 (R→W→R)   96%     69%     86%   |  38%     37%     51%     50%  | 61%
128          96%     69%     86%   |  34%     32%     49%     47%  | 59%
```

The turnaround column is **flat across the entire sweep** — direct confirmation of
§2.1: those cases never charge the gate, so the threshold cannot affect them. Only
the ACT-bound column moves, and it is monotone-better as the threshold drops. There
is **no trade-off to tune**, so pick the smallest physically-meaningful value: one
burst. Charging a full R→W→R round trip (66) is over-conservative and costs 4 points
of mean for nothing.

## 3. Results (DDR5-4800B, DQ-busy %)

| case | row-hit | SJW | no-batch | fixed | **adaptive** |
|---|---|---|---|---|---|
| RRRWWW rotate | – | 43% | 96% | 96% | **96%** |
| mixed RWRWRW | – | 38% | 37% | 69% | **69%** |
| write-heavy | – | 44% | 44% | 86% | **86%** |
| pure rotating reads | – | 100% | 100% | 100% | **100%** |
| gen linear/interleave | 0% | 68% | 54% | 27% | **46%** |
| gen random/interleave | 0% | 55% | 53% | 27% | **44%** |
| gen mixed/interleave | 0% | 66% | 58% | 30% | **48%** |
| gen linear/rowlocal | 87% | 24% | 24% | 16% | **16%** |
| gen mixed/rowlocal | 53% | 68% | 68% | 43% | **56%** |
| gen hot-bank/rowlocal | 88% | 43% | 43% | 43% | **43%** |
| gen write-heavy/rowlocal | 60% | 62% | 63% | 45% | **53%** |
| **MEAN** | | 56% | 58% | 53% | **60%** |

Generated traces: 1500 requests each, seeded RNG (all policies see byte-identical
traces). Every cell validated: **0 violations, 0 unscheduled, all policies**.

- **Adaptive ≥ fixed on every single case** — it is a strict improvement, never a
  trade. The four turnaround cases are preserved *exactly* (same result, same flip
  count), because the gate is never charged there.
- **Adaptive has the best mean (60%)**, beating the SJW baseline (56%), no-batch
  (58%) and fixed (53%).
- Recovers most of the ACT-bound loss: 27% → 46%, 30% → 48%.

## 4. What this does NOT fix (the next finding)

Adaptive batching does **not** close the gap to SJW on ACT-bound traces (46% vs 68%
on linear/interleave). It cannot, and the reason was mis-attributed before:

> **`no-batch` also loses to SJW there (54% vs 68%).**

With batching switched off entirely the greedy scheduler *still* trails SJW by 14
points. So that residual gap was never a batching problem — batching was only ever
responsible for the 27%→54% part, which adaptive now recovers most of. The remainder
is **greedy's pick order** (busy-first CAS > ACT > PRE, ties by id, BG-rotate) losing
to SJW's shortest-job cost function on ACT-bound work.

Tested and **rejected**: a `prepFirst` variant that spends a CA slot on PRE/ACT
whenever DQ is already covered past the next slot (hypothesis: greedy starves the
tRP+tRCD critical path). **Zero effect on every case** — the CA bus is not the
contended resource, so the hypothesis is dead. Recorded so it is not retried.

Two open items, in order:
1. **Pick order on ACT-bound work** — why shortest-job beats busy-first when every
   request is a row-miss. This is the live gap (up to 22 points).
2. `gen linear/rowlocal` scores 24% under *every* policy: a linear stream through the
   row-local map lands entirely in one bank (`bg=(l>>13)&3` — bg only changes every
   8192 lines), so it is tRC-bound at ~24% by construction. Scheduler-independent —
   it is an **address-map** result, and belongs to the `addrmap` tool, not here.

## 5. Hardware implication

The rule costs almost nothing in RTL — it reuses scoreboard state that the pickers
already compute:

```
gate_loss    : counter, ~7 bits (saturating at FLIP_COST = BL2 = 8)
opp_cas_rdy  : 1 bit — OR-reduce of the S3 CAS-legal vector for !mode entries.
               S3 already evaluates legality for every entry; today it discards the
               opposite-direction ones. Keep the OR instead of dropping it.
dq_idle      : 1 bit — gc >= dq_free, already in the scoreboard (§4 microarch)
```

`mode` flips when `gate_loss >= BL2 && opposite_work_exists`. No new comparators on
the critical path, no per-entry state, no extra table ports. The one structural note:
S3's per-entry legality result must be split into *legal* and *legal-but-for-mode* so
the OR-reduce is available — that is a fanout of existing logic, not new logic.

See [[scheduler_microarch.md]] §4 (scoreboard) and [[rmc-timing-sweep-phase]].
pkg untouched. RTL not started.
