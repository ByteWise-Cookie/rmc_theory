# Dynamic Greedy Scheduler — Design Brainstorm

**Status:** brainstorm / architecture. No RTL. Goal is to converge on a *dynamic,
greedy* scheduler that keeps the DQ bus busy, and to keep the old staged per-bank-FSM
design as a **benchmark** to score the new one against. Numbers come from
[[datapath_busy_timing]] (JEDEC-locked). This doc answers "correct me if I'm wrong"
inline — refinements are marked **⟳ correction**.

---

## 0. The one goal

Every cycle, choose the command (PRE / ACT / RD / WR / REF) that keeps the DQ data
bus occupied, out of order, respecting all DDR5 timing. The only legal DQ bubbles
are the R↔W turnarounds. Everything below is judged by **DQ-busy %**.

---

## 1. Two designs at a glance

| | **Baseline (benchmark)** | **Candidate (this doc)** |
|---|---|---|
| Core abstraction | per-bank FSM + per-rank FSM tables (state machines) | per-request **token** (demand) + thin shared **scoreboard** (resource) |
| Selection | staged pipeline, Shortest-Job-Winner at S2 | greedy per-cycle arbiter over ready tokens |
| State location | bank/rank FSM rows hold everything | token = demand; scoreboard = timing; **separated** |
| Ordering | pipeline order | dynamic, re-evaluated every cycle |
| Known weakness | only services already-active banks → inactive-bank starvation; heavy FSM tables | must not become a blocking conveyor (see §3.4) |

Both run against the **same request traces** and the **same timing engine**
(the GUI bench's `cons()`/`validate()`), so DQ-busy%, latency, energy proxy and
starvation are directly comparable.

---

## 2. Baseline — staged per-bank-FSM SJW scheduler (benchmark only)

The design already in the handoff, restated as the reference to beat. 5 stages:

- **S0 — Refresh / maintenance manager.** Owns per-bank request counters and the
  refresh/ZQ/RFM deadlines. Can **override** S1–S3 when a REF/ZQ/RFM becomes
  critical (correctness-first). Highest authority.
- **S1 — TCAM hit/miss + validate.** Looks the request address up in the row TCAM,
  classifies row-hit / row-miss / bank-idle, validates the entry.
- **S2 — timing check + Shortest-Job-Winner (SJW).** Checks all timing constraints
  for candidate commands and picks the winner by shortest remaining cost (SJF-like).
- **S3 — command formation / bank-state update.** (Old design left this loosely
  defined.)
- **S4 — DFI command emission.** Drive the chosen command onto the DFI/CA bus.

**Documented flaws (the reasons to move):**
1. **Inactive-bank starvation.** The scheduler biases toward banks that are *already
   active* (their CAS is cheap), so it feeds those to the TCAM search. A request to
   an **idle** bank never gets its ACT prioritized → it starves.
2. **Precharge/power tension.** Holding many banks open to serve hits wastes power
   (activate energy + open-row leakage + restricted refresh); closing aggressively
   forces row-miss penalties. The baseline has no principled precharge policy.
3. **FSM weight.** Per-bank *and* per-rank FSM tables (`[N_RANKS×16]` bank rows,
   per-rank rows, global timing table) are area- and verification-heavy.

Keep it as-is for benchmarking; do not extend it.

---

## 3. Candidate — request tokens + resource scoreboard + greedy arbiter

Your core move: **make the request a thread/token that flows and shrinks**, instead
of pushing all state into per-bank FSMs. I think that's the right instinct for
*demand*, with two corrections that decide whether it hits the datapath-busy goal.

### 3.1 Separate three concerns (this is the key idea)

| Concern | Lives in | Why |
|---|---|---|
| **Demand** — what work a request still needs, its age/QoS, its row/col | **per-request token** (your thread) | naturally per-request; shrinks as commands issue |
| **Resource state** — when each bank/BG/rank is next legal, which row is open | **shared scoreboard** | timing is *between* commands to a shared resource; no single token can own it |
| **Choice** — which legal command to emit this cycle | **greedy arbiter** | must see all ready tokens at once to keep the bus busy |

Your idea nails column 1. Columns 2 and 3 are the corrections.

### 3.2 The token (demand)

A token is created when a request enters, carrying a **work-list** that shrinks:

```
token {
  id, dir(R/W), rank, bg, bank, row, col,
  work  : ordered list, one of:
            [CAS]              // row hit
            [ACT, CAS]         // bank idle (row empty)
            [PRE, ACT, CAS]    // row miss
  age, qos,                    // for starvation + priority
  hint_ready_gc                // cached earliest-legal for work.head (a HINT, §3.3)
  data_ptr                     // WDB slot (write) / ROB slot (read)
}
```

Each time its head command issues, `work.pop()`. Token retires when `work` is empty
**and** data has moved (read data captured / write drained). This is exactly your
"thread gets smaller and smaller going down the pipe" — clean, and correct.

**Row-hit / bank-hit fast path (yours, kept):** at classify time, if the scoreboard
says the bank already holds `row`, `work = [CAS]` — the token skips PRE/ACT entirely
and goes straight to the CAS picker. If the bank is open on a *different* row,
`work = [PRE, ACT, CAS]`. If idle, `[ACT, CAS]`. Good — this is open-page locality.

### 3.3 The scoreboard (resource) — **⟳ correction: you can't delete this**

You hoped to drop per-bank / per-rank FSMs entirely. You can drop the **state
enum** (IDLE/ACTIVE/… is derivable), but the **timing deadlines are shared and must
stay** — because a constraint like tRC / tRRD / tCCD_L is *between two different
requests' commands to the same bank/BG/rank*. A new token to bank 5 must see that
another token just ACTed bank 5. That information cannot live privately in a token.

So keep a **thin scoreboard** (registers, not state machines):

```
per bank[N_BANKS] : { open, open_row, next_act, next_pre, next_cas, next_ref }
per BG  [N_BG]    : { next_cas_bg,  next_act_bg }        // tCCD_L/_WR, tRRD_L
per rank[N_RANKS] : { next_act_any, faw_ring[4], next_rd_wr, next_wr_rd, next_ref }
global bus        : { next_cas_any, dq_free_gc, last_dir } // tCCD_S, DQ occupancy
```

This is *lighter* than the baseline (no 16-state FSM per bank, no per-rank FSM
enum) — just deadline counters. **⟳** So the honest claim is: "drop the FSM *enums*,
keep a thin per-bank/BG/rank timing scoreboard," not "no per-bank state at all."

**⟳ correction — the token's cached timestamp goes stale.** Your token carries
`hint_ready_gc` computed when it was classified. But while it waits, *other* tokens
issue commands that push the bank/BG/rank deadlines later (a neighbor's ACT bumps
tRRD/tFAW). So the cached stamp is only a **priority hint** for ordering — the
**authority is the live scoreboard, re-checked at the emit cycle**. Never issue on
the stale stamp alone.

### 3.4 The arbiter — your S1/S2/S3, made non-blocking **⟳ the big correction**

Your plan: S1 handles PRE, S2 ACT, S3 RD/WR; a token marches down and a stage
**stalls** until its command is legal. **⟳ A marching, stall-on-not-ready pipeline
is the opposite of datapath-busy** — one token waiting in the ACT stage blocks every
other token behind it, and the bus goes idle. To keep DQ busy you *must* interleave
many banks, so not-ready tokens have to step aside and let others issue.

Reframe your per-stage-per-command idea as **parallel per-class pickers that never
block**, feeding one CA-bus mux:

```
each cycle:
  READY(class) = tokens whose work.head is of that class AND legal-now per scoreboard
  cas_cand = best of READY(CAS)   // row-hit, oldest, keeps bus busy
  act_cand = best of READY(ACT)   // for banks with demand, lookahead depth tRCD+tRP
  pre_cand = best of READY(PRE)   // close for a pending miss / policy
  ref_cand = S0 refresh/ZQ if due

  emit = CA_MUX(priority):        // 1 command per 2 tCK (DDR5 CA)
     1. ref_cand if CRITICAL      (S0 override, correctness first)
     2. cas_cand if it fills the next DQ slot   (busy-first)
     3. act_cand / pre_cand into the idle CA slots (lookahead)
     4. ref_cand if merely due
  apply emit -> scoreboard update + winning token.work.pop()
```

- Tokens that aren't ready simply don't appear in READY this cycle — **no stall, no
  refetch**; they sit in the pool and re-enter next cycle. That preserves your "one
  token, carries its own data, no refetch" property **without** blocking the bus.
- The CA mux is the greedy policy: **busy-first** (a CAS that lands in the next open
  DQ slot wins), then spend the free CA slots (the 3 per burst from
  [[datapath_busy_timing]] §3) on ACT/PRE **lookahead** so future banks are ready.
- This is literally your S1/S2/S3 as three pickers + S4 as the mux/DFI emit, but
  data-flow instead of a conveyor.

### 3.5 Fixing inactive-bank starvation (baseline flaw #1)

The baseline starved idle banks because it only fed active banks to selection. Here
the **ACT picker** exists precisely to prep idle banks that have demand, using the
free CA slots. Add: `act_cand` priority += token.age, so an aging request to an idle
bank forces its ACT out before it starves. Lookahead depth must be ≥ tRCD+tRP
(≈78 tCK @4800B) — the token's ACT/PRE must fire ~10 bursts ahead of its CAS. The
scoreboard + age-boosted ACT picker make that automatic.

### 3.6 Precharge / power policy (baseline flaw #2)

Make it an explicit knob on the PRE picker, not an accident:
- **Open-page default:** leave the row open after CAS (bet on locality).
- **Close-on-idle:** if a bank has no pending token for its open row for `T_close`
  cycles, the PRE picker closes it (frees it for a future miss, saves open-row
  power). `T_close` is a CSR.
- **Auto-precharge (RDA/WRA):** if the token is the *last* pending request for that
  row (visible from the pool), issue RDA/WRA so the precharge hides in the CAS —
  zero extra CA slot. Cheapest close. This needs the pool scan you already wanted
  ("look into other outstanding requests").

### 3.7 QoS / stall — **⟳ don't stall the pipe**

You suggested: on QoS trigger, the thread "just stays there stalling the pipeline,
no refetch." **⟳** Stalling the shared pipe stalls *every* request → bus bubbles.
Instead: QoS is a **priority bump in the arbiter** — the token stays in the pool
(so, yes, no refetch, your instinct is right), but it *wins* the picker earlier via
`qos` weight. A single token can be pinned/urgent without freezing the others. Same
"no refetch" benefit, no global stall.

---

## 4. Corrections to the raw idea (your "correct me if I'm wrong")

| # | Your claim | Verdict | Correction |
|---|---|---|---|
| 1 | Token per request carrying remaining work + row/col | ✅ right | keep exactly |
| 2 | Thread shrinks down the pipe, row-hit skips stages | ✅ right | keep |
| 3 | No need for per-bank / per-rank FSMs at all | ⚠ half | drop the **enums**; keep a thin per-bank/BG/rank **timing scoreboard** (§3.3) |
| 4 | Token carries its next-legal timestamp | ⚠ | it's a **hint**; re-check live scoreboard at emit (staleness, §3.3) |
| 5 | One token per stage, stage stalls till legal | ❌ | **non-blocking** per-class pickers + pool; stalling kills DQ-busy (§3.4) |
| 6 | On QoS, stall the pipeline, no refetch | ⚠ | keep "no refetch" (token stays in pool) but make it a **priority bump**, not a stall (§3.7) |
| 7 | Upper stage adds delay-stamp, lower stage handles it | ✅ mostly | works as the scoreboard-update + pop; just don't trust the stamp blindly (#4) |

Net: your architecture survives, minus the blocking pipeline and the "zero shared
state" claim. What you actually built is **demand tokens over a thin timing
scoreboard, picked greedily** — which is a clean, defensible design.

---

## 5. Walkthrough — RRWR row-miss, through the candidate

Two reads (banks in different BGs, both row-miss) then a write:
1. R0, R1, W2 tokens enter → classify vs scoreboard → each `work=[PRE,ACT,CAS]`.
2. Cycle-by-cycle the PRE and ACT pickers drain the free CA slots: PRE0, PRE1 (diff
   BG, tPPD apart), then ACT0, ACT1 (tRRD_S apart, inside tFAW). Scoreboard deadlines
   advance; tokens shrink to `[CAS]`.
3. CAS picker: R0 CAS fires when `next_cas` legal; R1 CAS `tCCD_S` later (diff BG →
   gapless). DQ busy.
4. W2: R→W turnaround — CAS picker defers it (busy-first prefers the gapless reads);
   only after the read run does the mux take W2 (small R→W bubble). Matches the
   partition-window intuition without a hard-coded window: it *emerges* from
   busy-first + age.

That "it emerges from the greedy policy" is the thing to verify on the bench.

---

## 6. Benchmark plan

Reuse the GUI bench's timing engine as the **oracle** (already the JEDEC-locked
`cons()`/`validate()`), and add a driver:

- **Traces:** synthetic streams — all-hit, all-miss, RRWR mixes, hot-bank,
  uniform-random bank, adversarial same-BG — plus a couple realistic ones.
- **Metrics per run:** DQ-busy % (headline), total bubble tCK, avg/`p99` request
  latency, ACT count + open-row-cycles (energy proxy), max token age (starvation),
  CA-slot utilization.
- **Compare:** baseline SJW-FSM vs candidate greedy-token on identical traces. The
  candidate wins only if DQ-busy is ≥ baseline at ≤ its energy and ≤ its worst-case
  latency. If it doesn't, the doc says so.
- **The GUI becomes the scoreboard viewer:** feed either scheduler's emitted command
  stream into the bench → it renders the schedule + prints the metrics. That is the
  point where the bench stops being a drawing tool and starts *measuring an
  algorithm* — the pivot from the last session.

---

## 7. Open decisions

- **S4's job** (your "idk"): propose = CA-bus mux + DFI emit + scoreboard commit +
  token pop. Confirm.
- Picker "best" functions: exact priority weights (age vs row-hit vs BG-rotation vs
  QoS). Start simple (row-hit > oldest > BG-rotate), tune on the bench.
- `T_close` open-page timeout; when to prefer RDA/WRA auto-precharge.
- Pool size (max in-flight tokens) = the lookahead window; needs ≥ tRCD+tRP of demand
  visible (~10 bursts @4800B).
- Refresh (S0) override granularity — per-bank REFsb vs all-bank REF, and how it
  preempts the pickers.

## 8. RTL impact (when we get there — not now)

- **Drop/shrink:** `per_bank_fsm_table` (enum) → thin scoreboard regs; `per_rank_fsm`
  and `global_timing_table` fold into scoreboard.
- **New:** token pool + classifier, three class pickers, CA mux (maps onto the
  existing `scheduler.sv` 5-stage shell, but stages become pickers).
- **Reuse:** `timing_reg_file` (CSR nCK values), `wr_tcam`/`rd_tcam` (classify →
  row-hit), watermark/starvation counters (→ token age).
- Baseline stays implementable from the handoff for the bench comparison.

pkg untouched. This is a brainstorm — nothing here is committed to RTL until the
bench says the greedy token design beats the baseline.
