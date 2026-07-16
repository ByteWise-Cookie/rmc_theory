# Datapath-Busy Timing Analysis (DDR5)

**Goal:** keep the DQ data bus occupied every cycle. A channel is assumed always
busy — a read or a write burst is always in flight. The **only** legal bubbles on
the datapath are the unavoidable direction-turnaround delays (R→W, W→R). Any other
gap means the scheduler failed to hide an ACT/PRE, or failed to rotate bank-group /
rank, for an out-of-order request that could have filled the slot.

**Method (per user):** every constraint is written **symbolically** as
`max(nCK_floor, ns_floor)`, then evaluated in **two columns**:
- **Toy** — tCK = 5 ns (200 MHz). Matches the existing `RMC_Handoff §18` worked
  example so cross-checks stay valid.
- **4800B** — DDR5-4800B, tCK = 0.4167 ns (2400 MHz clock, 4800 MT/s).

Config is never hard-coded in RTL — these load from `timing_reg_file` CSRs. The
scheduler logic stays speed-bin-agnostic; only the numbers move.

> **Status: FOUNDATION.** Config table + gap model + pairwise matrix + CA budget +
> sample diagrams. Full worked sequences (RRRR, RRWR, diff-rank chains) and the
> per-bank scheduler deadline derivation come next, after the numbers below are
> validated. Params marked ⚠ need a JEDEC/PHY cross-check (see §7).

---

## 1. Config Table

BL16 on the 32b subchannel ⇒ **one CAS moves 16 beats = 8 tCK of data on DQ.**
That "8" is the heartbeat of the whole analysis: consecutive CAS must be spaced
**≥ 8 tCK** to be gapless, and **= 8 tCK** is perfect back-to-back.

| Param | Symbolic def | Toy (5 ns) | 4800B (0.4167 ns) | Note |
|---|---|---:|---:|---|
| tCK | — | 5 ns | 0.4167 ns | data rate 4800 MT/s |
| BL | fixed | 16 | 16 | BL16 only |
| **BL/2** (DQ occupancy/CAS) | BL/2 | **8** | **8** | the heartbeat |
| RL (=CL) | bin | 3 | 40 | toy from §18; 4800B bin 40-39-39 |
| WL (=CWL) | bin | 1 | 38 | ⚠ CWL 4800 nominal, verify |
| tRCD | ns floor | 4 | 39 (16.25 ns) | ⚠ toy=4 is DDR4-scaled |
| tRP | ns floor | 4 | 39 (16.25 ns) | ⚠ toy=4 is DDR4-scaled |
| tRAS | ns floor | 7 | 77 (32 ns) | ⚠ toy=7 is DDR4-scaled |
| tRC = tRAS+tRP | — | 11 | 116 | full row cycle |
| **tCCD_S** | 8 nCK | **8** | **8** | diff-BG / diff-rank CAS spacing |
| **tCCD_L** | max(8 nCK, 5 ns) | **8** | **12** | same-BG read spacing |
| **tCCD_L_WR** | max(32 nCK, —) ⚠ | **32** | **32** | same-BG write spacing |
| **tWTR_S** | max(4 nCK, 2.5 ns) ⚠ | **4** | **6** | diff-BG write→read, from write-data-end |
| **tWTR_L** | max(16 nCK, 10 ns) | **16** | **24** | same-BG write→read |
| tRTP | max(12 nCK, 7.5 ns) | 12 | 18 | read→precharge (same bank) |
| tWR | 30 ns | 6 | 72 | write recovery (write-data-end→PRE) |
| tRRD_S | 8 nCK ⚠ | 8 | 8 | diff-BG ACT→ACT |
| tRRD_L | max(8 nCK, 5 ns) ⚠ | 8 | 12 | same-BG ACT→ACT |
| tFAW | ns floor ⚠ | ~16 | ~77 (32 ns) | 4 ACTs / window |
| tWPRE | 1–2 tCK | 1 | 2 | write preamble |
| tRPRE | 1–2 tCK | 1 | 2 | read preamble |
| **tRTR** (diff-rank CAS bubble) | PHY/ODT ⚠ | 2 | 2 | not JEDEC-core; DQS driver + ODT handoff |
| tRTW (read→write cmd spacing) | RL+BL/2−WL+tWPRE+1 | 12 | 13 | derived, see §2 |

Derived at both bins from the same formulas — this is the "symbolic + both columns"
the analysis is built on.

---

## 2. The Datapath Gap Model

Define **gap** = idle tCK on the DQ bus between the end of one burst and the start
of the next. Gapless ⇔ gap = 0.

For two consecutive CAS separated by command spacing `S` (tCK between the two CAS
commands), where both are the **same direction** (RR or WW), the data bursts are
each 8 tCK and both sit at the same fixed latency after their command, so:

```
gap = S - BL/2 = S - 8
```

### 2a. Same-direction transitions — gap is AVOIDABLE

| Pair | Spacing S | Gap = S−8 (toy) | Gap = S−8 (4800B) |
|---|---|---:|---:|
| RR diff BG | tCCD_S = 8 | **0** | **0** |
| RR same BG | tCCD_L | **0** | **4** |
| WW diff BG | tCCD_S = 8 | **0** | **0** |
| WW same BG | tCCD_L_WR = 32 | **24** | **24** |

**Key result:** the same-BG penalty is *fully avoidable* by **bank-group
rotation** — steer consecutive same-direction CAS into *different* BGs so spacing
drops to tCCD_S = 8 = BL/2. This is the scheduler's #1 job for datapath-busy.
- At **toy**, tCCD_L = 8 already ⇒ reads never bubble even same-BG; only **writes**
  (tCCD_L_WR = 32) force rotation.
- At **4800B**, tCCD_L = 12 ⇒ **both** reads (4-tCK bubble) and writes (24-tCK
  bubble) require rotation. Same algorithm, stronger requirement.

Invariant the scheduler must hold: **always keep ≥2 bank-groups with a ready
same-direction CAS**, so it can ping-pong BGs and never pay tCCD_L / tCCD_L_WR.

### 2b. Direction-change transitions — gap is UNAVOIDABLE (turnaround)

The DQ bus is half-duplex; a direction flip costs a bus turnaround. This is the
**only** bubble the user's spec permits. The two directions are wildly asymmetric:

**R→W (cheap).** Read data ends at RL+8. A write issued tRTW later puts write data
on the bus at tRTW+WL. Choosing tRTW = RL+8−WL+tWPRE+1 makes write data land right
after read data:
```
gap_RW = tWPRE + 1   →  toy 2 tCK,  4800B 3 tCK
```

**W→R (expensive).** Write data ends at WL+8. tWTR must elapse before the RD
*command*; read data then appears RL later. The bus is idle the whole time:
```
gap_WR = tWTR + RL
  same BG, 4800B: tWTR_L + RL = 24 + 40 = 64 tCK
  diff BG, 4800B: tWTR_S + RL =  6 + 40 = 46 tCK
  same BG, toy  : 16 + 3 = 19 tCK
  diff BG, toy  :  4 + 3 =  7 tCK
```

This asymmetry is why the controller **batches**: run a window of writes, then a
window of reads, so the huge W→R penalty is paid **once per window** and amortized
over many CAS — exactly the read/write **partition-rotation** design already in the
handoff. RW/WR bubbles can never be zero; the goal is to make them **rare**.

> **tWTR is a same-device constraint.** Across **different ranks**, W→R does not pay
> tWTR (the write and read hit different DRAM dies). A cross-rank W→R costs only bus
> + ODT turnaround + RL ≈ tRTR + RL — cheaper than same-rank same-BG. ⚠ verify with
> PHY ODT timing. This is a real argument for the 2-rank config.

---

## 3. CA-Slot Lookahead Budget

DDR5 CA is 7 bits/subchannel; **ACT, RD, WR are 2-cycle commands** — one command
every 2 tCK. Under one 8-tCK data burst there are **4 CA slots**; one is spent
issuing the next CAS, leaving **3 free slots** to prep *future* out-of-order
requests:

```
tCK:  0    1    2    3    4    5    6    7
CA : [  next CAS ][   ACT   ][   PRE   ][   ACT   ]
DQ : <=========== current burst, 8 tCK ==========>
        ^slot0        ^slot1     ^slot2     ^slot3
        (mandatory)   <----- 3 free for lookahead ---->
```

So under **each** burst the scheduler can hide up to **3** ACT/PRE for banks that
will be needed later. To open a fresh row for a future CAS, a bank needs PRE then
ACT (2 commands) and must satisfy tRP+tRCD before that CAS fires. Across a few
bursts this is plenty to keep a rotating set of banks row-ready — provided the
request stream has bank/BG diversity. **Bank/BG-address diversity is the fuel;**
if all pending requests hit one bank, no rotation and no hiding is possible (this
is where the address-map optimizer `addrmap` earns its keep).

Back-tracking rule (derived fully in a later section): **for a CAS scheduled at
cycle N to a bank that is currently idle, ACT must issue by N−tRCD, and the PRE
that preceded it by N−tRCD−tRP.** The scheduler works *backward* from the datapath
slot it wants to fill.

---

## 4. Pairwise CAS→CAS Gap Matrix

Spacing = min command-spacing constraint. Gap = spacing − 8 for same-direction;
for direction-change, gap = bus-idle tCK (§2b). "avoid?" = can rotation/batching
remove it.

| # | From→To | Bank rel | Constraint (symbolic) | Gap toy | Gap 4800B | Avoid? |
|---|---|---|---|---:|---:|---|
| 1 | R→R | diff BG | tCCD_S=8 | 0 | 0 | — already 0 |
| 2 | R→R | same BG | tCCD_L | 0 | 4 | ✅ BG-rotate |
| 3 | R→R | diff rank | tCCD_S+tRTR ⚠ | 2 | 2 | partial (ODT) |
| 4 | W→W | diff BG | tCCD_S=8 | 0 | 0 | — already 0 |
| 5 | W→W | same BG | tCCD_L_WR=32 | 24 | 24 | ✅ BG-rotate |
| 6 | W→W | diff rank | tCCD_S+tRTR ⚠ | 2 | 2 | partial (ODT) |
| 7 | R→W | any, same rank | tRTW ⇒ gap=tWPRE+1 | 2 | 3 | ❌ turnaround |
| 8 | W→R | same BG | tWTR_L+RL | 19 | 64 | ❌ batch to amortize |
| 9 | W→R | diff BG | tWTR_S+RL | 7 | 46 | ❌ batch to amortize |
| 10 | W→R | diff rank | tRTR+RL ⚠ (no tWTR) | ~42 | ~42 | ❌ but cheaper than 8 |
| 11 | R→W | diff rank | tRTR+... ⚠ | ~2 | ~3 | ❌ turnaround |

Rows 1/4 are the target steady state (gap 0). Rows 2/5 are the avoidable sin —
scheduler must rotate BG. Rows 7–11 are the permitted turnarounds; minimize their
*frequency*, never their per-event cost.

---

## 5. Sample Diagrams (ASCII)

Notation: `A`=ACT `P`=PRE `R`=RD `W`=WR `-`=CA idle. DQ shows which burst occupies
the bus; `····` = **bubble** (the thing we hunt). bN = bank N, gN = bank-group N.

### 5a. R→R same BG — the AVOIDABLE bubble (4800B), then the fix

Bad — both reads in BG0, spacing forced to tCCD_L=12:
```
       tCCD_L = 12
      |<--------->|
CA : R(g0b0) . . . R(g0b1) . . .
DQ : <burst0 8tCK>····<burst1 8tCK>     bubble = 12-8 = 4 tCK  ✗
```
Fixed — rotate to BG1, spacing tCCD_S=8:
```
CA : R(g0b0) . . R(g1b0) . . R(g0b1) . .
DQ : <burst0 8 ><burst1 8 ><burst2 8 >   gap = 0  ✓ gapless
```

### 5b. W→R same BG — the UNAVOIDABLE turnaround (4800B)

```
CA : W(g0b0) . . . . . . . [wait tWTR_L=24 after data] . . R(g0b0) . .
DQ : <wr burst 8>·············· tWTR_L + RL = 64 ··············<rd burst 8>
```
Cannot be removed. Correct response: don't do isolated W→R — **batch** so one
64-tCK penalty covers a whole window of reads.

### 5c. RRWR sequence (4800B) — reads gapless, one turnaround at the W

```
CA : R(g0) . R(g1) . R(g2) . W(g3)... . . . . R(g0) ...
DQ : <rd 8 ><rd 8 ><rd 8 >·· gap_RW≈3 ··<wr 8 >···· gap_WR (batch!) ····<rd 8>
      \___ BG-rotated, gap 0 ___/         ^tiny         ^expensive — avoid isolated W
```
Lesson the sequence teaches: the lone W between reads is doubly bad — pays a small
R→W *and* a large W→R to get back to reads. The scheduler should **defer** that
write into a write-window unless its age forces it out (starvation threshold).

---

## 6. Conflicts Log (running — batched for one decision at sweep end)

Per the agreed workflow, settled artifacts are **not** edited now; conflicts
accumulate here for a single decision pass.

| # | Settled | New analysis says | Better? (recommendation) |
|---|---|---|---|
| C1 | `rmc_pkg.sv`: N_RANKS=1, RANK_BITS=0 | diff-rank cases need N_RANKS=2, RANK_BITS=1 | Bump to 2 — unlocks cheaper cross-rank turnaround (§2b, row 10) |
| C2 | §18 / KB: tWTR_L = 4 | JEDEC floor max(16 nCK,10 ns) ⇒ 16 (toy) / 24 (4800B). **4 is illegal** | Fix to 16/24 |
| C3 | §18 implies tRTP = 4 | max(12 nCK,7.5 ns) ⇒ 12/18 | Fix to 12/18 |
| C4 | §18 tRCD=tRP=4, tRAS=7 | DDR4-1600-scaled, not DDR5 | Keep for *toy* continuity, but label explicitly as toy-only |
| C5 | timing set single (toy) | need dual (toy + 4800B) as CSR-loadable sets | Add 4800B CSR profile |

## 7. Verify List (⚠ — JEDEC/PHY cross-check before locking numbers)

- CWL (WL) nominal for DDR5-4800 — used 38, confirm bin.
- tCCD_L_WR — used 32 nCK flat; confirm no ns floor at 4800.
- tWTR_S floor — used max(4 nCK, 2.5 ns); confirm 4 vs 2 nCK.
- tRRD_S / tRRD_L / tFAW — used 8 / max(8,5ns) / 32 ns; confirm DDR5-4800 bin.
- **tRTR (diff-rank CAS bubble)** — not a JEDEC core param; PHY/ODT-driven, used
  2 tCK placeholder. Needs the PHY's rank-to-rank DQS/ODT handoff spec. Blocks
  rows 3/6/10/11 numeric accuracy.
- tRTW exact form — used RL+BL/2−WL+tWPRE+1; confirm the +1/+2 preamble rounding.

---

## 8. Command Window & Slack Model

The scheduler works **backward** from a datapath slot it wants to fill. Each
prep-command has not a single deadline but a **legal window**. Filling the DQ box
first, then solving the CA lane, is the mental model for the whole tool.

### 8.1 Reference frame

The **draggable object is the DQ data burst.** Anchor everything to the **CAS
command** cycle `N` (the RD/WR that produces the burst). The data box then sits at
`[N+RL, N+RL+8)` for a read, `[N+WL, N+WL+8)` for a write.
> ⚠ Assumption to confirm: user's "44" = the CAS **command** cycle N (so ACT =
> N−tRCD). If instead "44" marks the **data-burst** start, subtract RL/WL: the
> command is at 44−RL and every deadline below shifts by RL.

### 8.2 Deadline chain (row-miss read — the deepest chain)

To serve a read whose bank holds the wrong row, three commands must precede the RD
in order: **PRE → ACT → RD**. Latest just-in-time issue cycles:

```
D_RD  = N                     (the datapath slot being filled)
D_ACT = N − tRCD              (ACT must precede RD by tRCD)
D_PRE = N − tRCD − tRP        (PRE must precede ACT by tRP)
```

### 8.3 Windows with slack vector **A**

Each command type gets a configurable slack `A_i`. The legal window is the deadline
pushed earlier by `A_i`, but never earlier than the resource is free:

```
window_i = [ E_i , D_i ]
E_i = max( D_i − A_i ,  resource_ready_i )

resource lower bounds (same bank):
  E_PRE ≥ max( D_PRE − A_PRE ,  last_RD_this_bank + tRTP ,  last_ACT + tRAS )
  E_ACT ≥ max( D_ACT − A_ACT ,  PRE_issue + tRP )
  E_RD  ≥ max( N       − A_RD  ,  ACT_issue + tRCD )
inter-bank gates on ACT:  tRRD_S/tRRD_L, tFAW window
```

**A_i is the schedulability knob.** A_i = 0 ⇒ each command has exactly one legal
cycle — zero freedom, and if that CA slot is already taken by another request the
schedule is infeasible. A_i > 0 ⇒ a window, so commands for many in-flight requests
**bin-pack** into the free CA slots (the 3 free/burst from §3). Cost of larger A_i:
the row opens earlier and stays open longer (more tRAS exposure, holds the bank,
more interference) — so the ideal is the **smallest A_i that keeps the CA lane
feasible**, per user's "constants should be zero but we need some slack." The vector
`A = {A_PRE, A_ACT, A_CAS, A_REF, …}` is a first-class CSR/GUI-tunable input.

### 8.4 Canonical worked example — user's cycle-44 read

Row-miss read, N = 44, slack A_ACT = A_PRE = 3:

| Command | Deadline D | Window [D−A, D] toy | Window [D−A, D] 4800B |
|---|---|---|---|
| RD | 44 | {44} | {44} |
| ACT | 44 − tRCD | [37, 40] (tRCD=4) | [2, 5] (tRCD=39) |
| PRE | 44 − tRCD − tRP | [33, 36] | [−37, −34] (tRCD+tRP=78) |

**Teaching point (4800B):** D_PRE = −34 is negative — to serve this row-miss read
with **zero** datapath bubble the PRE must have fired ~78 tCK (≈10 bursts) *before*
the reference. That fixes the **required lookahead depth** = tRCD + tRP, and is the
whole reason an outstanding-request queue + auto-fill is needed: the scheduler must
be prepping banks ~10 bursts ahead of the datapath. At toy the chain is only 8 tCK
deep, so 1-burst lookahead suffices — another reason the two bins teach different
lessons.

Row-hit read collapses the chain to just `D_RD = N` (bank already open, no
PRE/ACT). Row-empty (idle bank) needs ACT only: `D_ACT = N − tRCD`, no PRE.

---

## 9. Full Worked Sequences

Relative diagrams: each DQ block = one 8-tCK burst; `····` = bubble. CA lane shows
the CAS commands (prep ACT/PRE assumed already hidden by lookahead unless noted).
bN = bank, gN = bank-group, rN = rank. Per-sequence gap table gives both columns.

### 9.1 RRRR — four reads, BG-rotated (target steady state)

```
CA : R(g0) R(g1) R(g2) R(g3)
DQ : <r g0 ><r g1 ><r g2 ><r g3 >     spacing tCCD_S=8 each
                                       gap 0 everywhere  ✓ gapless
```
| Transition | Constraint | Gap toy | Gap 4800B |
|---|---|---:|---:|
| all R→R diff BG | tCCD_S=8 | 0 | 0 |

Degenerate (all same BG g0) — the scheduler's failure mode:
```
DQ : <r g0 >····<r g0 >····      spacing tCCD_L
     gap: toy 0 (tCCD_L=8) | 4800B 4 (tCCD_L=12)
```
Fix = rotate BG. Requires ≥2 BGs holding ready reads — the §2a invariant.

### 9.2 WWWW — four writes

Same shape as reads but the same-BG penalty is **huge** (tCCD_L_WR=32):
```
good (rotated):   DQ : <w g0 ><w g1 ><w g2 ><w g3 >   gap 0
bad  (same g0):   DQ : <w g0 >···························<w g0 >
                       spacing 32 → gap 24 (both bins!)
```
| Transition | Constraint | Gap toy | Gap 4800B |
|---|---|---:|---:|
| W→W diff BG | tCCD_S=8 | 0 | 0 |
| W→W same BG | tCCD_L_WR=32 | 24 | 24 |

Writes are where BG rotation matters at **every** bin (toy included) — the write
same-BG bubble never vanishes.

### 9.3 RRWR — reads with one intruding write (why isolate-writes is bad)

```
CA : R(g0) R(g1)      W(g2)              R(g3)
DQ : <r g0 ><r g1 >·· ·<w g2 >·········· ······<r g3 >
             gapless   ^R→W    ^^^^^ W→R (tWTR+RL) ^^^^^
             (rotated) ~2-3    64 tCK @4800B same-rank
```
| Transition | Constraint | Gap toy | Gap 4800B |
|---|---|---:|---:|
| R→R diff BG | tCCD_S | 0 | 0 |
| R→W | tWPRE+1 | 2 | 3 |
| W→R (same rank, diff BG) | tWTR_S+RL | 7 | 46 |

**Lesson:** one lone write costs a cheap R→W **and** an expensive W→R to return to
reads. Unless the write's age hit the starvation threshold, the scheduler should
**defer** it into a write-window (§9.4), not fire it between reads.

### 9.4 WW → (diff rank) → RRRR — rank switch dodges tWTR

Two writes on rank0, then reads on rank1. Cross-rank W→R skips tWTR entirely (writes
and reads hit different dies), so the return-to-read penalty shrinks to bus/ODT +
RL:
```
CA : W(r0g0) W(r0g1)  R(r1g0) R(r1g1) R(r1g2) R(r1g3)
DQ : <w r0 ><w r0 >·· ·······<r r1 ><r r1 ><r r1 ><r r1 >
             gap0     ^^ cross-rank W→R ^^   then gapless reads
             (rot)    tRTR+RL ≈ 42 (no tWTR)
```
| Transition | Constraint | Gap toy | Gap 4800B |
|---|---|---:|---:|
| W→W diff BG | tCCD_S | 0 | 0 |
| W→R **diff rank** | tRTR+RL (no tWTR) ⚠ | ~5 | ~42 |
| R→R diff BG | tCCD_S | 0 | 0 |

Compare to §9.3 same-rank W→R (64): cross-rank saves the full tWTR (24 tCK @4800B).
**This is the concrete payoff of the 2-rank config** (conflict C1). ⚠ pending tRTR.

### 9.5 R → (diff rank) W → RRR

```
CA : R(r0g0)      W(r1g0)      R(r0g1) R(r0g2) R(r0g3)
DQ : <r r0 >···· ·<w r1 >···· ·······<r r0 ><r r0 ><r r0 >
            ^R→W diff rank    ^W→R diff rank (no tWTR)
```
R→W stays cheap (turnaround-bound either way); the diff-rank W→R back to reads
avoids tWTR as in §9.4. Diff-rank buys the most on the **W→R** edge, little on R→W.

### 9.6 RRWR (diff rank) RW — the composite

```
CA : R(r0g0) R(r0g1)  W(r0g2)         R(r1g0)        W(r0g3)  ...
DQ : <r ><r >········ ·<w >·········· ·······<r r1> ········ ·<w>
      gap0   R→W~3     same-rank W→R    diff-rank    R→W~3
     (rot)             tWTR_S+RL=46     R→W cheap
```
Reads the RRWR head as §9.3, then the diff-rank hop lets the second read batch land
without tWTR, then another turnaround for the trailing W. Full gap ledger:

| Edge | Type | Constraint | Gap 4800B |
|---|---|---|---:|
| R→R | same rank diff BG | tCCD_S | 0 |
| R→W | same rank | tWPRE+1 | 3 |
| W→R | same rank diff BG | tWTR_S+RL | 46 |
| R→W | → diff rank | tRTR+… | ~3 |
| (return) | | | |

**Takeaway across all sequences:** gap-0 is sustainable only inside a same-direction
BG-rotated run; every direction flip is a turnaround tax. The scheduler's objective
= **maximize same-direction run length** (batch) **× keep ≥2 BGs live** (rotate),
and use **rank** to cheapen the unavoidable W→R flips.

---

## 10. Per-Bank Scheduler Deadline Rules (back-track generalization)

For any CAS scheduled at datapath slot `N` to bank `b`, the scheduler computes
prep-command windows from bank state. All "issue-by" are **latest**; earliest =
`deadline − A_i` floored by resource-ready (§8.3).

| Bank state at plan time | Prep needed | ACT issue-by | PRE issue-by |
|---|---|---|---|
| ACTIVE, row hit | none | — | — |
| IDLE (precharged) | ACT | N − tRCD | — |
| ACTIVE, row miss | PRE, ACT | N − tRCD | N − tRCD − tRP |
| PRECHARGING | ACT (after tRP) | N − tRCD | (in flight) |

Deadline update on issue (feeds the `next_*` registers already in handoff §9A):
```
issue ACT @ t : next_cas[b]=t+tRCD, next_pre[b]=t+tRAS, row_open[b]=req.row
issue PRE @ t : next_act[b]=t+tRP
issue RD  @ t : next_pre[b]=t+tRTP,  DQ box @ [t+RL, t+RL+8)
issue WR  @ t : next_pre[b]=t+WL+BL/2+tWR, DQ box @ [t+WL, t+WL+8)
inter-bank on ACT: respect tRRD_S/_L and the tFAW 4-in-window ring
```
The scheduler's per-cycle question becomes: *"for each future DQ slot I intend to
fill, are all prep windows still satisfiable given the CA slots already committed?"*
— a rolling feasibility check. That check is exactly what the GUI (§11) makes
visual and what the auto-fill solver optimizes.

---

## 11. Interactive Scheduler GUI — Requirements (FUTURE, not this phase)

Captured so the concept isn't lost; **build only when user says go.**

- **Lanes (top→bottom):** rank / bank-group / bank / CA (command, 2-cyc slots) / DQ
  (datapath). Time on X.
- **Draggable:** read & write **data bursts** (8-tCK blocks) onto the DQ lane. Also
  drag individual commands on the CA lane.
- **On drop of a burst at slot N:** auto-place its mandatory command chain
  (PRE→ACT→CAS) as **window bars** (not points) on the CA lane, colored per request.
  Window = `[N−…−A, N−…]` from §8.
- **Slack controls:** live sliders for the `A` vector; windows widen/narrow; wasted
  row-open time shown as a cost meter.
- **Free-slot fill:** the inter-command CA gaps highlight as fillable; commands for
  *other* pending requests snap into them. Collision on a 2-cyc CA slot = red.
- **Constraint checker:** any placement violating tCCD/tWTR/tRRD/tFAW/tRAS or a CA
  collision flags red with the offending constraint named.
- **Outstanding-request queue → auto-fill/optimize** (the "tomorrow" job): given a
  backlog, solver bin-packs commands to **minimize total DQ bubble** = maximize
  datapath busy, honoring all windows. This is the CA-lane bin-packing / CSP the
  whole doc formalizes.

Implementation later — candidate stack noted for then: single-file HTML + inline SVG
+ vanilla JS (drag/constraint math client-side), so it can live as an artifact or in
the repo. No dependency on external libs.
