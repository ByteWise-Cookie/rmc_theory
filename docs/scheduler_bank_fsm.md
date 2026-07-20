# RMC Scheduler — Per-Bank Request FSM + Weight Arbiter

The **per-bank** view of the greedy scheduler: one request's life (a read or write
arrival → `PRE`/`ACT`/`CAS` → data → retire) as an explicit state machine, plus the
**4-lane weight arbiter** that decides which command class emits each cycle. `N_BANKS`
copies of this FSM run independently; the arbiter merges them onto the one CA slot.

Companion to [[scheduler_staged_logic]] (the S0–S4 stage/port view). Same logic, two
lenses: staged_logic reads by command **class** (S1 PRE / S2 ACT / S3 CAS), this doc
reads by **bank** — the unit of independence. Both are the golden model
(`tools/sched_model/sched_test.js`, bench `1d271c33`) in prose. Timing is JEDEC-locked
per [[datapath_busy_timing]]; numbers below are the model's `b4800` bin (DDR5-4800B,
`tCK = 0.4167 ns`).

Diagram: `docs/diagrams/bank_fsm.excalidraw`.

---

## 0. What the FSM is (and is not)

- **Per request, per bank.** The state is the request's `work_state`
  (`NEED_PRE → NEED_ACT → NEED_CAS → DONE`) crossed with the **bank's** open-row state.
  A request is a table slot (§0 of staged_logic — "token is virtual"); the FSM below is
  the transition rule that slot obeys. There is **no marching token** — every slot that
  is `NEED_*` nominates in parallel; the arbiter emits one.
- **The bank is the independence unit.** Its own open row, own `next_pre/act/cas`, own
  row-lock, own aging counters. `N_BANKS` FSMs advance in parallel. Cross-bank timing
  (`tCCD_L`, `tRRD_L`, `tFAW`, DQ bus) is **not** in the FSM — it is applied at the
  arbiter (§4), because a single bank cannot see it.
- **Two independent things gate a command:** (1) **timing eligibility** — the DDR
  constraint countdown (§3), a hard legal/illegal mask; (2) **the weight** — priority
  among *eligible* lanes (§4). Timing says *may I*; weight says *do I win this cycle*.

---

## 1. The state machine

```
                         (arrival: RD_REQ or WR_REQ, allocate slot)
                                       │
                                       ▼
                              ┌──────────────────┐
                              │  CLASSIFY (S1)   │  TCAM: bank open? row match?
                              └──────────────────┘
                 closed│idle         open, row==R        open, row!=R
                (row-empty)          (row-HIT)           (row-MISS)
                       │                  │                   │
                       ▼                  │                   ▼
                 ┌───────────┐            │             ┌───────────┐
                 │ NEED_ACT  │            │             │ NEED_PRE  │
                 └───────────┘            │             └───────────┘
                       │                  │                   │  emit PRE
                  emit ACT                │                   │  (row-lock releasable
                  (tRP since PRE,         │                   │   AND next_pre clear)
                   tRRD/tFAW)             │                   ▼
                       │                  │             ┌───────────┐
                       │                  │             │ NEED_ACT  │  (miss re-opens)
                       ▼                  │             └───────────┘
                 ┌───────────┐            │                   │  emit ACT (tRP)
                 │ NEED_CAS  │◄───────────┴───────────────────┘
                 └───────────┘
                       │  emit CAS  (row open+match, tRCD since ACT,
                       │             tCCD, DQ-free, turnaround)
                       ▼
                 ┌───────────┐
                 │   DONE    │  read: data at RL → ROB.  write: drains WDB at WL.
                 └───────────┘  free slot → watermark.
```

**Classify is the fork.** Same three cases as staged_logic's classify table:

| bank state | case | command chain | entry `work_state` |
|---|---|---|---|
| closed / idle | **row-empty** | `ACT → CAS` | `NEED_ACT` |
| open, `row == R` | **row-hit** | `CAS` | `NEED_CAS` |
| open, `row != R` | **row-miss** | `PRE → ACT → CAS` | `NEED_PRE` |

Read and write share the FSM identically — only the CAS flavour (`CAS_RD`/`CAS_WR`) and
the tail timing differ (write adds `tWR` recovery before the row can PRE; §5).

---

## 2. Command emission per state (the four lanes)

Each `NEED_*` state drives exactly one **emission lane**. Per bank there are three
request lanes; `REF` is the global maintenance lane (S0), which overrides all banks.

| lane | fires in state | emits | frees the state to |
|---|---|---|---|
| **PRE** | `NEED_PRE` | close the open (wrong) row | `NEED_ACT` |
| **ACT** | `NEED_ACT` | open row `R` | `NEED_CAS` |
| **CAS** | `NEED_CAS` | read/write burst | `DONE` |
| **REF** (S0) | — (bank-independent) | REFab/REFsb/RFM/ZQ | (maintenance) |

A lane "wants to emit" iff it has a request in its state **and** that request is
timing-eligible (§3). Multiple lanes want the slot every cycle — the weight arbiter (§4)
picks one.

---

## 3. Timing eligibility — the countdown gate (per bank)

Eligibility is a per-lane countdown to the bank's `next_*` scoreboard register. `cd ≤ 0`
⇒ the command is legal this cycle. This is a **hard mask**, evaluated before weight.

```
cd_pre = next_pre − gc     next_pre = MAX( ACT_gc + tRAS,            # tRAS ACT→PRE
                                           last_rdCAS_gc + tRTP,     # tRTP RD→PRE
                                           last_wrCAS_gc + WL+BL2+tWR)# write recovery
                            AND  row-lock releasable  (§ below)
cd_act = next_act − gc     next_act = MAX( PRE_gc + tRP,             # tRP PRE→ACT
                                           tRRD_L/S spacing, tFAW ring )
cd_cas = next_cas − gc     next_cas = MAX( ACT_gc + tRCD,            # tRCD ACT→CAS
                                           tCCD_L/S spacing,
                                           dqFree, turnaround tRTW / tWTR )
```

`next_pre = MAX over its writers` (ACT's `tRAS` vs the last CAS's `tRTP`/`tWR`) — the bug
the golden model caught; the RTL must replicate the MAX. See staged_logic S4 §3.

**Row-lock (the PRE gate).** A bank locks to its freshly-opened row on `ACT` and will not
`PRE` until the lock releases — this protects a "ready-but-busy" row-hit from being closed
out from under it while it waits its DQ turn.

```
acquire : on ACT (lock_row[bank] = new row)
hold    : while demand_count[bank] > 0        (pending hits to the open row)
release : demand_count == 0  OR  oldest_miss_age >= AGE_MAX   (starvation cap)
break   : s0_override (maintenance) force-breaks
```

The age cap is **two-sided** (golden-model finding): when it fires the bank must also
**stop serving hits** (gate its CAS), so the in-flight burst finishes, `tRTP`/`tWR`
clears, and the starved miss's `PRE` can actually issue — permitting the PRE alone is not
enough. Full treatment in staged_logic S1.

---

## 4. The weight arbiter (emission control)

Every cycle up to four lanes are eligible and want the one CA slot. The arbiter picks the
**highest total weight**, emits it, and advances the scoreboard.

**Total weight = control weight (SJF, stage-fixed) + aging counter (per lane).**

### 4a. Control weight — shortest-job-first, fixed per class

Shortest job = fewest commands left to deliver data = closest to filling a DQ slot.
`CAS` is the shortest job (0 prep, data now), so it carries the top control weight.

| lane | control weight | why |
|---|---|---|
| **CAS** | highest | 0 prep — feeds DQ **this** burst; keep the bus full |
| **ACT** | mid | 1 hop from data (`tRCD` then CAS) |
| **PRE** | low | 2 hops from data (`tRP`, `tRCD`, then CAS) |
| **REF** | override tier | correctness-first; S0 preempts via `s0_override` |

This is the CAS-first / prep-second priority of staged_logic S4, stated as a weight.

### 4b. Aging counter — one per lane, the fairness layer

```
each cycle, per lane:
    if lane has a candidate AND did NOT win this cycle:   age[lane] += 1
    elif lane won this cycle:                             age[lane]  = 0
    else (no candidate):                                 age[lane]  = 0
```

The counter ticks **every cycle the lane waits**, including while timing-blocked (user
decision) — a command stuck on `tRP`/`tRCD` still banks priority, so the instant it turns
eligible it already carries the weight it earned waiting. On a win the counter **resets to
0**. A starved lane therefore climbs until it out-weighs the default CAS-first ordering
and preempts — **bounded starvation, no hard timer needed** in the common case (the S1
row-lock age cap is still the backstop for the pathological hot-row).

### 4c. Pick

```
candidates = { lane : eligible(lane) }              # §3 hard mask
winner     = argmax over candidates of  ( control_weight[lane] + age[lane] )
             tie-break: oldest request age, then BG-rotate (bg != last_cas_bg)
emit winner (1 command per CA slot);  advance scoreboard;  age[winner] = 0
if s0_override: REF wins regardless (correctness tier)
```

Per bank this collapses to a single head command (the row-lock already serializes
intra-bank: locked→its hit, releasable→PRE, idle+demand→ACT). Across banks the arbiter is
the S4 cross-class + cross-bank layer.

### 4d. ⚠ Scaling caveat (weights pass)

Because the aging counter ticks **every** waiting cycle (§4b) and the control weight is a
small fixed constant, after enough waiting `age` dominates and the arbiter **degenerates
to oldest-first** — losing the CAS-first / SJF behaviour that keeps DQ full. The two
weights must be **relatively scaled** so SJF governs normal waits and aging only breaks
through for genuine starvation, e.g.

```
total = K · control_weight[lane] + age[lane]
```

with `K` sized so a fresh CAS still out-weighs a lane that has waited a typical
prep-latency (`tRCD`/`tRP` ≈ 39 tCK) but loses to one that has waited pathologically long.
`K`, the control-weight values, and `AGE_MAX` are one joint **weights-pass** knob-set
(shared with staged_logic's open weights item). Flagged, not yet tuned.

---

### 4e. DQ-occupancy servo — the CAS$\leftrightarrow$ACT balance

CAS is the *consumer* of ready rows and the *producer* of DQ traffic; ACT is the
*producer* of ready rows. The prep (ACT) rate must track the drain (CAS) rate so the
ready-CAS pool **never empties** (DQ idles) and **never overfills** (ACT wasted, tFAW
burned, future DQ congested). A closed servo on top of the fixed control weights.

Signals (combinational, per cycle):

```
dq_free_in = max(0, dqFree − gc)          cycles until DQ frees (0 = free now)
ready_cas  = popcount(can_cas[N_BANKS])   ready-CAS pool depth
faw_budget = ACTs left in the tFAW window
```

`can_cas` already hard-gates on `gc ≥ dqFree`, re-evaluated every cycle — that is the
**busy/free re-gate** (§3, §7). The servo is a *soft* modulation of the **ACT lane
weight** (not a hard gate — hard-gating ACT on pool depth could starve prep):

```
boost ACT : ready_cas < POOL_LOW  AND  dq_free_in <= LOOKAHEAD   (prep now or DQ idles)
            act_boost  ∝ (POOL_LOW − ready_cas)
damp  ACT : ready_cas > POOL_HIGH  OR  faw_budget low            (rows already open)
            act_damp   ∝ (ready_cas − POOL_HIGH) + faw_pressure
w_act = K·control_act + age + act_boost − act_damp
```

**Hard guardrail** (prevents the over-correction — *"when DQ is free and something is
ready, CAS it"*): `dq_free_in == 0 AND ready_cas >= 1  ⇒  CAS wins absolutely`. A boosted
ACT can never preempt a ready CAS onto a free bus; the servo only spends
*otherwise-idle* CA slots on prep. **DQ never idles while a CAS is ready.**

Net: the servo holds `ready_cas` in a band `[POOL_LOW, POOL_HIGH]` — below → prep harder,
above → prep less — while the guardrail guarantees DQ is never starved. This is the
CAS-first invariant (§4a) **plus a prep-rate governor**; it makes the S2 lookahead
scorer's "hide tRCD under queued bursts" an explicit occupancy target. It also caps the
reverse failure: opening rows faster than CAS drains just parks rows (holds tRAS,
raises refresh / rowhammer exposure) without feeding DQ faster — the damp side bounds it.
`POOL_LOW` / `POOL_HIGH` / `LOOKAHEAD` = weights-pass knobs.

## 5. Latency chains — best case + every worst case

First-data latency and DQ occupancy per case, `b4800` (tCK). "First data" = command issue
→ first beat at the DRAM; add `BL/2 = 8` tCK for the full 16-beat burst.

| case | command chain | first-data latency (tCK) | notes |
|---|---|---|---|
| **row-hit, read** *(best)* | `CAS_RD` | `RL = 40` | back-to-back service = `tCCD_S=8` / `tCCD_L=12` |
| **row-hit, write** | `CAS_WR` | `WL = 38` | data drains from WDB |
| **row-empty, read** | `ACT → CAS_RD` | `tRCD + RL = 39+40 = 79` | +8 → 87 full burst |
| **row-miss, read** *(worst, no ref)* | `PRE → ACT → CAS_RD` | `tRP+tRCD+RL = 39+39+40 = 118` | +8 → **126** full — the sizing driver (`L_miss`) |
| **row-miss + refresh collision** | `…REF… → PRE → ACT → CAS` | `118 + tRFC` | `tRFC=708` (REFab) or `tRFCsb=312`; rare, S0 drains it |
| **write tail (recovery)** | `CAS_WR … → PRE` | `WL+BL2+tWR = 38+8+72 = 118` | before that bank can PRE its row |
| **R→W turnaround** | `CAS_RD → CAS_WR` | `tRTW = RL+BL2−WL+tWPRE = 12` | direction flip cost (adaptive batch amortizes) |
| **W→R turnaround** | `CAS_WR → CAS_RD` | `WL+BL2+tWTR_L = 38+8+24 = 70` | why writes batch |

**Why 126 is the number that sized the buffer.** `L_miss = 126 tCK`, service = `BL/2 = 8`
tCK/burst → latency floor `N = L_miss / (BL/2) ≈ 16` in-flight reads to hide one row-miss
and keep DQ full. Depth is 64 (4× the floor at the x16 pkg, 2× the `N_BANKS=32` ceiling) —
see staged_logic §0.

---

## 6. `N_BANKS` in parallel

```
   bank 0 FSM ─┐   (own row-lock, own next_*, own age[PRE/ACT/CAS])
   bank 1 FSM ─┤
     …         ├──►  WEIGHT ARBITER  ──►  1 command / 2 tCK (CA bus)  ──► DFI
   bank N−1 FSM┘        (§4 + cross-bank tCCD_L / tRRD_L / tFAW / DQ)
   S0 REF lane ─────────►  s0_override (correctness tier)
```

- Each bank runs §1–§4 on **its own** entries and scoreboard — fully independent up to the
  arbiter. This is the `N_BANKS` per-bank paths of staged_logic §0.
- **Paths ≠ emissions.** `N_BANKS` FSMs propose in parallel, but the CA bus is 1 cmd /
  2 tCK. Under one burst (8 tCK = 4 CA slots) the arbiter fills ~4 slots — 1 CAS + 3 prep
  in the burst shadow — never `N_BANKS` commands a cycle.
- **Cross-bank timing is arbiter-only.** `tCCD_L`/`tRRD_L`/`tFAW`/DQ-collision live
  *between* banks; a single FSM cannot see them, so they gate at §4, not §3-per-bank.
- **Bank count is parameterized.** `N_BANKS = 16` (x16 pkg, current frozen) or `32` (x8
  intent, 8 BG). The FSM is identical; only the count of parallel copies changes. See
  staged_logic §0 / OPEN items.

---

## 7. Hardware view — the eligibility-gate datapath

The FSM (§1) is *behaviour*; the hardware is a **gate-generation datapath with a
feedback loop**. Diagram: `docs/diagrams/sched_gate_hw.excalidraw`. Block/port/net list
+ placement for drawing it: [[scheduler_wiring_spec]].

The point that answers *"we can't issue a CAS every cycle"*: `can_cas` / `can_act` /
`can_pre` are **not static wires** — each is a **comparator output over a registered
`next_*` counter**, and the writeback *mutates those counters every issue*, so the gate
deasserts itself.

```
REGISTERED (FFs)          COMBINATIONAL gates            ARBITER
scoreboard next_* ─► (gc ≥ next_*) AND row/lock/faw ─► can_cas/act/pre[N_BANKS] ─► weight
      ▲                                                                              │
      └──────────── S4 writeback (feedback = the gate) ◄───────────── 1 winner ◄─────┘
```

Three pieces + one loop:
1. **Registered state (FFs)** — the scoreboard: per-bank `next_cas/act/pre`, `row_open`;
   global `dqFree`, `next_cas_any` (tCCD_S), `next_cas_bg[bg]` (tCCD_L), `tFAW` ring,
   turnaround window; the `age[lane]` counters; free-running `gc`.
2. **Combinational gates** — one AND per class per bank: `can_cas[b] = row_open &
   open_row==R & gc≥next_cas & gc≥next_cas_bg & gc≥next_cas_any & gc≥dqFree & turnaround
   & !age-cap`; `can_act[b] = !row_open & gc≥next_act & gc≥tRRD & tFAW<4 & !gate_rfc`;
   `can_pre[b] = (demand==0 | age≥AGE_MAX) & gc≥next_pre`. Outputs three `N_BANKS`-wide
   bitmaps — the §3 eligibility mask.
3. **Arbiter** — priority encoder (CAS>ACT>PRE) + aging (§4) over the three bitmaps →
   one winner → DFI.
4. **Feedback (the gate).** On a CAS issue the writeback sets `dqFree = gc+lat+BL2`,
   `next_cas_any = gc+tCCD_S`, `next_cas_bg = gc+tCCD_L`, `next_pre[b] = MAX(…,
   gc+tRTP/tWR)`. Next cycle `can_cas` **deasserts** for the burst window → 3 of the 4 CA
   slots (§0, 1 cmd / 2 tCK) are free → the arbiter spends them on ACT/PRE **prep for
   other banks** → their CAS is legal exactly when DQ frees → **DQ stays full**. That
   registered-timing feedback *is* the "CAS-first, prep-in-shadow" behaviour, in gates.

Same three `can_*` gates are the S2/S3 input ports in [[scheduler_staged_logic]]
(`can_cas_out` / `can_cas_bg_out` / `can_cas_any_out`, etc.) — this section is their
generation + why the loop keeps the bus busy.

## 8. Consistency / open items

- **Logic = golden model** `tools/sched_model/sched_test.js`; the eventual RTL matches it
  cycle-for-cycle. The row-lock, two-sided force-break, ping-pong classify, and windowed
  visibility are already in the model. **The aging-counter arbiter (§4) is a doc-stage
  refinement of the model's `class-priority + age` pick — the model uses a busy-first +
  BG-rotate + oldest tie-break today; adding the explicit per-lane aging counter + the
  `K` scaling (§4d) to `sched_test.js` is a follow-up so the reference stays authoritative.**
- **Weights pass (deferred, joint with staged_logic):** control-weight values, the `K`
  SJF-vs-aging scale (§4d), `AGE_MAX`, PRE/ACT scoring. One knob-set.
- Timing names/values = `datapath_busy_timing.md §1` + model `b4800`; not re-derived here.
- pkg values are **frozen**; `N_RD_ENTRIES=64` and `N_BANKS=32` are **design intent**
  (RTL phase), not current pkg. No pkg edit, no RTL — doc phase.
- No contradiction with staged_logic / dynamic / microarch / adaptive-batching.
