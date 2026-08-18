# ARB — Weight Arbiter (winner selection)

**Phase 1, block 08.** Picks the next command from the 16 bank heads (+ maintenance via
Stage-0). Weight-based, with a never-idle-DQ guardrail, per-bank row-lock, and adaptive
R/W batching. KB name: Weight Arbiter (Stage 3). **Model-proven** (`sched_test.js`, 33/33).

Grounded in KB §8 Stage 3 + datapath analysis (block 00 I19–I22) + the sweep (OQ-20).

---

## 0. Role

```
16 queue heads (block 07) ──▶ [ legal filter | weight score | guardrail ] ──▶ winner → EMIT (02)
   + readyAt/can_* (block 02)                                              (ACT/PRE/CAS/REF)
   + last_act_bg (block 02)
```

Among all bank heads that are DRAM-legal this cycle, choose the one that best serves
datapath-busy + fairness. The arbiter is where FR-FCFS, batching, and the DQ guardrail
live. It **never** re-checks RAW (block 05 already gated eviction) and **never** touches
timing legality directly — it reads block-02's `can_*`/`readyAt`.

---

## 1. Weight function

```
weight(lane) = K·control[lane] + age[lane] + (lane==ACT ? servo_mod : 0)

  control : CAS > ACT > PRE            (SJF baseline, fixed; sweep pt 2/1/0)
  age     : +1 per waiting cycle, 0 on win   (breaks real starvation)
  servo_mod (DQ-occupancy balance, default OFF):
     ready_cas = popcount(can_cas) ; dq_free_in = dqFree - gc
     pool thin & DQ freeing → +boost ACT ; pool deep / tFAW tight → −damp ACT

winner = argmax(weight) over legal candidates
ties → oldest age → BG-rotate (bg != last_act_bg : tCCD_S 8 < tCCD_L 12)
```

**Sweep design point (OQ-20 DONE):** `control = 2/1/0`, `K = 5000`, guardrail ON, servo
retained but default-OFF, `AGE_MAX = 256`. Weights are **second-order**; the guardrail +
sizing dominate. Model: low-K (age-led) cuts tail-wait vs high-K (SJF-led) — self-test PASS.

---

## 2. Never-idle-DQ guardrail (the dominant rule)

```
GUARDRAIL: dq_free_in == 0  AND  ready_cas >= 1   ⇒   CAS wins absolutely
```
If the DQ bus is about to go idle and any CAS is ready, a CAS fires — no weight can
override. This is what actually holds datapath-busy; the weights only tie-break under it.

### ≥2-live-BG invariant (I20)
Same-BG CAS pays `T_CCD_L`(rd, 4-tCK bubble) / `T_CCD_L_WR`(wr, 24-tCK bubble); diff-BG =
`T_CCD_S`=8=gapless. The arbiter **must keep ≥2 bank-groups holding a ready
same-direction CAS** and ping-pong between them (`bg != last_act_bg`). This is the #1
datapath-busy job — BG rotation, every cycle.

---

## 3. Per-bank row-lock (FR-FCFS with a starvation cap)

```
acquire : on ACT — bank locks to the freshly-opened row
hold    : while demand[bank][open_row] > 0   (pending row-hits to the open row)
release : demand == 0  OR  oldest_miss_age[bank] >= AGE_MAX
next    : oldest NEED_PRE miss on that bank acquires (FCFS)
break   : s0_override (maintenance) force-breaks the lock

two-sided cap: when locked AND aged out, can_cas ALSO deasserts so the burst finishes,
  tRTP/tWR clears, and the starved miss's PRE force-breaks in.
```
The lock protects **ready-but-busy** row-hits: a hit waiting on DQ/tCCD/turnaround can't
have its row precharged out from under it. Model: row-hit promotion → fewer ACTs, keeps
locality (adversarial busy 11%→24%). **PRE-eligible iff** the lock is releasable AND
`next_pre` timing met.

---

## 4. Adaptive R/W batching (supersedes fixed bank partition)

```
run a batch direction (R or W); flip on:
  gateLoss >= BL2   (a free DQ slot wasted skipping an opposite-direction CAS)
  OR stall >= tRAS + tRP   (opposite work waiting too long)
```
Pays the W→R turnaround once per batch, demand-driven. **Direction asymmetry (I21):** R→W
≈ 3 tCK, W→R = tWTR+RL (46–64 tCK) — so batch writes, drain them, then batch reads. **Use
rank (I22):** steer the unavoidable W→R across ranks (different dies skip tWTR, ~42 vs 64).
Defer a lone write between reads unless its age hit the starvation threshold.

---

## 5. NOP-cycle priority (winner_valid == 0)

```
1. Opportunity REFsb   (correctness first — idle bank, most overdue; block 06)
2. Speculative ACT     (TCAM-confirmed prefetch, boundary imminent; KEEP-deferred)
3. Opposite-batch drain
4. True NOP
```

---

## 6. Interfaces (valid-credit)

**In:** `queue_head[16]{rw,row,col,state,seqnum}` + `queue_depth[16]` (block 07);
`readyAt`/`can_*`/`last_act_bg`/`dqFree` (block 02); `s0_override` + maintenance cmd
(block 06 via Stage-0); `wr_count`/batch state.
**Out (to EMIT, block 02):** `winner_valid`, `winner_cmd_type` (ACT/CAS_RD/CAS_WR/PRE),
`winner_rank/bg/bank/row/col`, `winner_tag`. Back: `emit_ack`/`emit_stall`.

---

## Open items (ARB)

- **OQ-20** `K`, `control`, `AGE_MAX`, servo pools — swept (design pt recorded); re-confirm
  after buffer-depth sweep (OW-7) settles.
- **OL-2** speculative ACT + opportunity REFsb — in v1 RTL or deferred? (complexity vs
  gain; sweep-gate).
- **OA-1** `AGE_MAX` vs the hard starvation backstops (`RD_STARVATION_THR` etc.) — AGE_MAX
  is the primary fairness knob; THR is the last-resort backstop. Confirm no double-fire.
- **OA-2** batch-flip thresholds (`BL2`, `tRAS+tRP`) — tune with the R/W mix in the sweep.
