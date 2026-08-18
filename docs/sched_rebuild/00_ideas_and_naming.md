# Ideas Harvest, Naming Convention & Design-Choice Validation Ledger

**Phase 1, block 00 (foundation).** Mine the prior RMC corpus (KB v1.9.9 handoff, full
IO map, golden model, mentor Visio) for **ideas + naming** — not whole blocks. Then a
loop that **validates every design choice** against three authorities: **DDR5 spec
(JESD79-5)**, the **golden model** (`sched_test.js`, 33/33 self-tests), and **mentor
decisions**. Verdict each: KEEP / ADAPT / DROP.

Sources: `RMC_Handoff_v1.9.9.md`, `RMC_IO_Map.md`, `tools/sched_model/sched_test.js`,
mentor chi2axi Visio (front-end vocabulary).

---

## 1. Naming convention (carried forward)

Prior work has a consistent, good convention. Adopt it wholesale.

### 1.1 Rules
- **Parameters:** `ALL_CAPS`, suffix by kind — `_WIDTH` (bit width), `_BITS` (field
  width), `_DEPTH` (entries), `N_` prefix for counts (`N_RANKS`, `N_BANKS`,
  `N_WR_ENTRIES`). No hardcoded widths anywhere.
- **Signals:** `lower_snake_case`.
- **Timing deadlines:** `next_<event>` = gc at which the event becomes legal
  (`next_act`, `next_pre`, `next_cas`, `next_ref`). Compare via sign bit:
  `can_x = (gc - next_x)[MSB]==0`.
- **Registered legal flags:** `can_<event>` (`can_act/pre/cas/ref/faw`,
  `can_act_bg[]`, `can_cas_any`). **Precomputed, out of critical path.**
- **Block/rank/BG scoping suffix:** `_bg[]`, `_rank[]`, `_any` (global).
- **Timing params:** `T_<PARAM>` in `timing_reg_file` (`T_RCD`, `T_CCD_L_WR`, …).
- **Gates/blocks:** `gate_<x>` (`gate_rfc`, `gate_zq`), `blocked` (RAW hold).
- **Directional prefixes:** `wr_`/`rd_`, `me_cmd_` (maintenance), `dfi_`, `sched_`,
  `s0_`/`s1_`/… (pipeline stage), `raw_`.
- **FSM states:** `UPPER` (`IDLE, ACTIVATING, ACTIVE, PRECHARGING, REFRESHING_SB`).
- **Command classes:** `ACT / CAS_RD / CAS_WR / PRE / REFab / REFsb`.
- **Queue-entry progress:** `NEED_PRE / NEED_ACT / NEED_CAS / DONE`.
- **Global cycle:** `gc` (free-running `GC_WIDTH`).

### 1.2 Block-name reconciliation (rebuild ↔ prior KB ↔ mentor Visio)
My rebuild block tags map onto the prior names — same logic, one vocabulary. **Prefer the
KB name in RTL; rebuild tags are for the packet-walk narrative.**

| Rebuild tag | KB name (authoritative) | Mentor Visio analog |
|-------------|-------------------------|---------------------|
| IAF | Async REQ FIFO (CIF→MC) | ISO PTC FIFO / IF_MFIFO |
| ADEC | **AMU** (Address Map Unit) | Attmem + LSB alignment |
| HZU | RAW pause + WR_TCAM/BCAM | Non-Hazd decode + CAM + hum queues |
| BQ | Per-Bank In-Flight Queue (§9E) | — (new in RMC) |
| ARB | Weight Arbiter (Stage 3) | Merge (1 req/cycle) / Rsp Arb |
| EMIT | Scheduler Stage 4 | — |
| SCB | Per-Bank/Rank/Global timing tables | — |
| FAB | DFI boundary + DFI mux + WR/RD data path | UNDBI/parity, WDATA GEN |
| RSP | Async RESP FIFO + response path | BRESP_GEN / DBID_RESP |

**Decision:** rename rebuild blocks 01–03 internal signals to the KB convention
(`nAct→next_act`, `nPre→next_pre`, `nCasBg→next_cas_bg`, `faw[]→faw_window`). `caFree`
and `dqFree` are new (CA-bus-free / DQ-bus-free) — keep, they have no KB equivalent and
name a real resource.

---

## 2. Ideas grabbed (not blocks)

Each: the idea, its source, how the rebuild uses it, verdict.

| # | Idea | Source | Rebuild use | Verdict |
|---|------|--------|-------------|---------|
| I1 | **Registered `can_*` legal flags** — precompute legality, no subtractor in the scheduling critical path | KB §8 S2, §16 | block 02 SCB: replace live `legal()` compare with registered `can_*` per level | **ADOPT** |
| I2 | **`next_*` deadline + sign-bit compare** `(gc-next_x)[MSB]==0` | KB §8 S4 | block 02 scoreboard advance table | **ADOPT** |
| I3 | **Three-level timing tables** (per-bank / per-rank / global) | KB §9A–C, IO §14–16 | block 02 SCB already 4-level; fold to KB's 3 tables (bank/rank/global) + naming | **ADAPT** |
| I4 | **Weight arbiter** `K·control + age + servo`, never-idle-DQ guardrail | KB §8 S3; model | block 03 ARB — already present | **KEEP** (model-proven: age-led cuts tail) |
| I5 | **Per-bank in-flight FIFO, head-only, no valid bit, ptr occupancy** | KB §9E | block 03 BQ — core | **KEEP** |
| I6 | **RAW = pause** (`blocked` bit gates eviction, `wr_occupied` masks CAM) | KB §11 | block 03 HZU | **KEEP** |
| I7 | **Adaptive R/W batching** — flip on `gateLoss≥BL2` or `stall≥tRAS+tRP` | KB §13; model | block 03 ARB | **KEEP** |
| I8 | **AMU** — per-field XOR hash + split-field extract, CSR setup-time | KB §12, IO §33 | block 03 ADEC = AMU | **KEEP** |
| I9 | **Maintenance Engine** peer block, 6 sub-FSMs, DFI mux `init_done` one-way latch | KB §10 | new block: ME (refresh/init/zq/rfm/pd/mrpoll); drives FAB during boot | **KEEP** |
| I10 | **timing_reg_file** — `param_id→nCK`, CSR write, combinational multi-port read, `cmd→timing_update_vector` | IO §17 | block 02 timing CSR source | **KEEP** |
| I11 | **Bank Activity Counter** (`count`, `dirty`) — REFsb argmin target, PD entry | KB §9D | ME + power-gating input | **KEEP** |
| I12 | **Speculative prefetch ACT** on NOP, TCAM-confirmed | KB §14 | ARB NOP-cycle option | **KEEP-deferred** (complexity; sweep-gated) |
| I13 | **Opportunity REFsb** on NOP, idle bank, most overdue | KB §10 | ME NOP option | **KEEP** |
| I14 | **DFI mux `init_done` latch** — Init FSM drives DFI at boot, scheduler after | KB §10 | block 01 FAB: add init-vs-sched DFI mux | **ADOPT** (missing from block 01) |
| I15 | **valid-credit intra-MC** interface (no combinational ready) | KB §4 | all rebuild block-to-block ports | **ADOPT** |
| I16 | **Async FIFO credit-based push**, `FIFO_DEPTH`=init credits, `gate_resp_fifo_avail` | IO §2–3 | block 03 IAF + RSP protocol | **KEEP** |
| I17 | **`gate_resp_fifo_avail`** — RD never issues without a reserved resp slot | KB inv 6 | ARB/EMIT gate on read issue | **KEEP** |
| I18 | **Staggered starvation** `age ≥ THR + entry_idx` (≤1 starved fires/cycle) | KB §15 | subsumed by weight `age` term; THR = hard backstop | **ADAPT** |
| I28 | **MR_Write sub-FSM + shared MR Read Arbiter** — runtime mode-register writes (timing changes) with shadow→apply into `timing_reg_file`, MRR verify read-back, `gate_mr[rank]`; shares the MRR sideband with MR_Poll via `mrr_requester` tag. **Hard invariant: `timing_reg_file` never out of sync with DRAM's programmed latency** | `RMC_MR_Programming_v1_9_10` | ME gains a 7th sub-FSM; the timing-sync invariant is first-class | **KEEP** (ME scope) |

---

## 3. Design-choice validation ledger (the loop)

Every locked choice, validated against spec / model / mentor. **Basis** column names the
authority.

| Choice | Verdict | Basis / rationale |
|--------|---------|-------------------|
| BL16 only | **KEEP** | Spec: DDR5 native BL16; AXI 64B INCR = one BL16 on 32b subchannel |
| AXI INCR/64b/no narrow/no exclusive/no QoS | **DROP from my scope** | Scope: CIF owns AXI; my ingress gets **formed** requests. These are CIF constraints |
| Single async FIFO at AXI↔MC only | **KEEP (reconciled)** | Scope: DFI runs at `mc_clk` baseline → fabric CDC degenerate. **One real async FIFO = IAF**; egress CDC is config-parameterized, off by default |
| Intra-MC valid-credit | **ADOPT** | Timing closure — no combinational ready across blocks |
| 5-stage pipeline (S0 maint / S1 admit / S2 gate / S3 arb / S4 emit) | **KEEP** | My ADEC/HZU/BQ/ARB/EMIT = the same stages re-drawn; the stage logic is unchanged |
| TCAM split WR(full)/RD(ternary) | **ADAPT** | Keep WR_TCAM/BCAM for RAW; **RD_TCAM pre-filter DROPPED** (v1.9.9 → candidate set = queue heads). Model-confirmed |
| Residency split (short admission → per-bank FIFO) | **KEEP** | Mentor decision; BQ core |
| No valid bit (ptr occupancy) | **KEEP** | Mentor decision; swept clean across repo |
| RAW = pause (not bypass) | **KEEP** | Mentor review; retires merge/hold-forward/2nd-slot |
| Weight arbiter (vs pure SJF) | **KEEP** | Model: age-led K cuts tail-wait (self-test PASS) |
| Row-hit promotion (FR-FCFS) | **KEEP** | Model: fewer ACTs, holds locality (busy 11%→24% adversarial) |
| Adaptive batching (vs fixed bank partition) | **KEEP** | Mentor; partition scheme superseded |
| Registered `can_*` flags | **ADOPT into block 02** | KB invariant 14 — no subtractor in critical path |
| AMU XOR-hash address map | **KEEP** | KB §12; ADEC = AMU |
| Open-page default, closed/adaptive CSR | **KEEP** | Spec-neutral; open best for sequential |
| Maintenance Engine peer, never issues CAS | **KEEP** | KB §10; clean separation |
| DFI mux `init_done` one-way latch | **ADOPT into block 01** | KB §10 — block 01 currently omits the init-vs-sched mux |
| Speculative prefetch ACT | **KEEP-deferred** | Zero-mispredict but adds Stage-2 logic; sweep-gate before RTL |
| Opportunity REFsb on NOP | **KEEP** | Zero traffic cost; correctness-first on NOP |
| Bank activity counter (count/dirty) | **KEEP** | REFsb targeting + PD entry + power-gate |
| Staggered starvation `THR+entry_idx` | **ADAPT** | Weight `age` term is primary now; THR = hard backstop only |
| Timing wheel | **DROP (rejected)** | Model: loses 4–6 pt DQ-busy multi-bank (OQ-22 CLOSED). Re-confirmed 33/33 |
| Sweep design point (control 2/1/0, K=5000, guardrail ON, servo default-OFF, AGE_MAX=256, bankDepth=8, tcam=32, in-flight≤128) | **KEEP** | OQ-20 DONE (`sweep.js`) — weights 2nd-order, guardrail+sizing dominate |
| Read buffer depth 32 vs 64 | **OPEN → 64 intent** | Plan file: read=write=64 for row-hit batching; pkg bump deferred to RTL. Not yet in a sweep — flag |
| N_WR = 2–3× N_RD | **TENSION** | KB says WR≫RD; plan file says read=write=64. **Reconcile in sizing pass** (OW-7) |

---

## 4. Action items — what changes in blocks 01–03

From the validation, concrete edits to make the rebuild consistent with the harvested
convention + ideas:

- **A1 (block 02):** rename `nAct/nPre/nCas/nRcd → next_act/next_pre/next_cas`, `nActBg/
  nCasBg → next_act_bg/next_cas_bg`, `faw[] → faw_window`. Keep `caFree`/`dqFree` (new).
- **A2 (block 02):** state the SCB as **registered `can_*` flags** (I1/I2), not a live
  `legal()` subtractor — `legal()` becomes the *reference* the flags precompute.
- **A3 (block 02):** collapse the 4-level scoreboard to KB's **3 tables** (per-bank /
  per-rank / global) + `timing_reg_file` (I10).
- **A4 (block 01):** add the **DFI mux + `init_done` one-way latch** (I14) — Init FSM
  drives DFI at boot, scheduler after.
- **A5 (block 03):** rename IAF/ADEC/HZU/BQ/ARB/RSP internal signals to KB names; adopt
  **valid-credit** (I15) on every inter-block port.
- **A6 (new block):** **Maintenance Engine** (I9) — peer to the scheduler, 6 sub-FSMs,
  writes FSM tables, never issues CAS. Its own block doc.
- **A7 (sizing pass):** resolve **OW-7** — read vs write buffer depth (64/64 plan vs
  2–3× KB). Needs a sweep — **now with a floor: I24 says lookahead depth ≥ tRCD+tRP ≈ 10
  bursts**, so BQ/outstanding depth must clear that to hit gap-0 on row-miss.
- **A8 (block 02/03):** elevate **≥2-live-BG (I20)** from an ARB tie-break to a stated
  hard invariant; add the **3-free-CA-slots/burst (I23)** budget to EMIT's `caFree` model.
- **A9 (block 02):** add the **slack vector `A` (I25)** — schedule prep commands as
  windows `[D−A, D]`, not points; CSR knobs `A_PRE/A_ACT/A_CAS/A_REF`. Fold the backward
  deadline chain (I26) into the emit feasibility check.
- **A10 (pkg intent):** record **N_RANKS 1→2 (C1)** as design intent — cross-rank W→R
  dodges tWTR. pkg edit deferred to RTL-go.

---

## 6. Datapath-busy timing — harvested ideas (from `datapath_busy_timing.md`)

The single richest non-consolidated source. The scheduler's whole objective restated in
DQ-bus terms. New ideas beyond the handoff:

| # | Idea | Detail | Rebuild use | Verdict |
|---|------|--------|-------------|---------|
| I19 | **DQ heartbeat = BL/2 = 8 tCK** | one CAS = 16 beats = 8 tCK on DQ; gapless ⇔ CAS spaced ≥8 | the atomic unit of `dqFree` in block 02 | **ADOPT** (naming: heartbeat) |
| I20 | **≥2 live bank-groups invariant** | same-BG CAS pays tCCD_L(12 rd)/tCCD_L_WR(32 wr) → bubble; BG-rotate drops to tCCD_S=8=gapless. **Scheduler's #1 datapath job** | ARB tie-break already prefers `bg≠last_act_bg`; **elevate to a hard invariant** | **ADOPT** |
| I21 | **R→W cheap / W→R expensive asymmetry** | R→W ≈ tWPRE+1 (3 tCK); W→R = tWTR+RL (64 same-BG / 46 diff-BG @4800B) | *why* adaptive batching exists — batch to pay W→R once/window | **KEEP** (grounds I7) |
| I22 | **Cross-rank W→R skips tWTR** | writes/reads hit different dies → ~42 tCK vs 64. Concrete payoff of 2-rank | ARB: prefer cross-rank for the unavoidable W→R flip | **ADOPT** (ties to conflict C1) |
| I23 | **CA lookahead budget: 3 free slots/burst** | 8-tCK burst = 4 CA slots (2-cyc cmds); 1 = next CAS, 3 free to prep future ACT/PRE | EMIT: the `caFree` budget = 3 prep-cmd/burst | **ADOPT** |
| I24 | **Required lookahead depth = tRCD+tRP ≈ 78 tCK ≈ 10 bursts** | row-miss PRE must fire ~10 bursts before its CAS to hit gap-0 | **sizing floor** for BQ / outstanding queue depth (OW-7 input!) | **ADOPT** |
| I25 | **Slack vector `A`** (windows not points) | each prep cmd gets `A_i`; legal window `[D_i−A_i, D_i]` floored by resource-ready. Smallest A_i keeping CA feasible | EMIT/ARB: schedule commands as windows → bin-pack into free CA slots | **ADOPT** (CSR-tunable `A_PRE/A_ACT/A_CAS/A_REF`) |
| I26 | **Backward scheduling from DQ slot** | plan the DQ burst at N, back-solve PRE@N−tRCD−tRP, ACT@N−tRCD | the mental model for EMIT's feasibility check | **ADOPT** |
| I27 | **Interactive scheduler GUI** | draggable DQ bursts, window bars, slack sliders, free-slot CSP fill | FUTURE tool, build on "go" only | **DEFER** |

## 7. Conflicts to resolve (from datapath §6 + tensions found)

These are settled-artifact conflicts the datapath analysis logged. Verdicts here; the pkg
edits wait for RTL-go.

| # | Settled | Conflict | Verdict / basis |
|---|---------|----------|-----------------|
| C1 | `rmc_pkg`: N_RANKS=1, RANK_BITS=0 | diff-rank W→R is ~22 tCK cheaper (I22); needs N_RANKS≥2 | **BUMP to 2 (intent)** — real turnaround win; pkg edit deferred |
| C2 | KB §18: tWTR_L=4 | JEDEC = max(16nCK,10ns) = 16/24; **4 is illegal** | **FIX to 24@4800B** — spec-locked. My block 02 already uses tWTR_L=24 ✓ |
| C3 | KB §18: tRTP=4 | JEDEC = max(12nCK,7.5ns) = 12/18 | **FIX to 18@4800B** — block 02 uses 18 ✓ |
| C4 | KB §18: tRCD=tRP=4, tRAS=7 | DDR4-scaled "toy", not DDR5 (39/39/77 → verified 40/40/77) | **toy = label-only; 4800B authoritative** — block 02 uses 40/40/77 ✓ |
| C5 | single toy timing set | need dual (toy + 4800B) CSR-loadable | **dual CSR profiles** — `timing_reg_file` already CSR-loaded (I10) |
| C6 | datapath doc: "CA = 7 bits/subchannel" | study doc verified CA[13:0] = 14 lanes | **reconcile** — 14 total; per-subchannel nuance to confirm. Budget (3 free/burst) holds either way |
| — | `architecture_reference.md` | corrupt: IO-map duplicated + leaked heredoc (line 959) | **repo hygiene** — delete/regenerate; not a design source |

**Note:** my block-02 timings already match the *corrected* (C2/C3/C4) values — the
datapath analysis and my rebuild independently landed on the JEDEC-verified numbers. Good
cross-check.

## 5. Open items (this ledger)

- **OW-7** read/write buffer depth reconcile (64/64 vs 2–3×) — sizing sweep.
- **OL-1** does the rebuild keep the 5-stage internal pipeline naming, or present purely
  as blocks? (I keep both: blocks for narrative, S0–S4 for RTL module boundaries.)
- **OL-2** speculative ACT + opportunity REFsb — in v1 RTL or deferred? (sweep-gate).
- **OL-3** ME scope vs "my core" — ME drives FAB; confirm ME is inside my deliverable
  (it is: FAB is mine, ME owns DFI at boot).
