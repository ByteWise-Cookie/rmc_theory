# RMC Scheduler — Staged Logic Reference (S0 → S4)

Port-level reference for the dynamic greedy scheduler. Ports are the real names from
[`RMC_IO_Map.md §19`](RMC_IO_Map.md) and `rmc/rtl/mc_core/scheduler.sv`; logic is the
greedy design validated in the golden model (`sched_test.js`, bench artifact
`1d271c33`). Where the skeleton's names say "SJF" / "cost classification", that is the
**baseline SJW** — noted inline; the greedy fills the same ports.

Companion docs: [[scheduler_dynamic_design]] (why greedy), [[scheduler_microarch]]
(token = table slot, §8 SVG deltas), [[scheduler_adaptive_batching]] (the batch
policy), [[datapath_busy_timing]] (JEDEC-locked timing). This doc is the **stage-by-
stage port + logic view**; those are the rationale.

---

## 0. Frame (read first)

- **Non-blocking, classify-all.** No marching token. Every cycle all N outstanding
  entries are visible; the three pickers (PRE / ACT / CAS) nominate in parallel; S4
  emits ONE. A not-ready request is simply not nominated — it steps aside, staying in
  its table slot. (Rejected alternative: fetch-one-and-work — a request stalled on
  tRAS/tRP blocks the picker and idles DQ.)
- **CA:DQ slot ratio — the core budget.** DDR5 CA is a 2-cycle command → 1 cmd / 2
  tCK. One CAS burst (BL16) = 8 tCK of DQ = **4 CA slots**. The CAS uses 1 slot; the
  other **3 are free** to emit ACT/PRE for *other* banks in the shadow of the burst.
  This is why "CAS-first, prep-second" (S4 priority) keeps DQ full without starving
  prep.
- **pkg (frozen):** `BG_BITS=2`, `BANK_BITS=2`, `N_RANKS=1`, `N_BG=4`, `N_BANKS=16`,
  `N_WR_ENTRIES=64`, `N_RD_ENTRIES=32`.
- **Token is virtual:** a request = a slot in `wr/rd_status_reg` + `wr/rd_tcam` + a
  2-bit `work_state` (`NEED_PRE → NEED_ACT → NEED_CAS → DONE`). The pipeline carries
  the entry **index**, not the token.

### Shared resources every stage reads

| resource | block | holds |
|---|---|---|
| outstanding tables | `wr/rd_tcam`, `wr/rd_status_reg` | addr {rank,bg,bank,row}, valid, age, work_state |
| allocator | `wr/rd_watermark_mgr` | free-slot alloc / retire, full flags |
| timing values | `timing_reg_file` | nCK per param (tRCD/tRP/…); combinational multi-port read |
| scoreboard | new thin regs (replaces `per_bank_fsm_table`) | per-bank next_act/next_pre/next_cas + row_open; per-BG/rank next_*; tFAW ring |
| global counter | `gc_counter` | free-running `gc`; age = `gc − status_age[idx]` |

### The classify table (the heart of S1)

A request wants `(bank, row_R)`. The bank is in one of three states — this determines
the whole command sequence:

| bank state | open row | case | commands to data | `work_state` | path gates |
|---|---|---|---|---|---|
| closed (idle) | none | row-empty | `ACT → CAS` | NEED_ACT | ACT, then tRCD → CAS |
| open | = row_R | row-hit | `CAS` | NEED_CAS | tCCD / DQ-free only |
| open | ≠ row_R | row-miss | `PRE → ACT → CAS` | NEED_PRE | tRAS→PRE, tRP→ACT, tRCD→CAS |

**PRE = close** the open row; **ACT = open** a row. "Bank open" is not enough — the
*right* row must be open. Never PRE an open bank on a row-hit (throws away the hit).
Classify first, then emit the head of that case's sequence.

---

## Stage 0 — Maintenance / refresh authority

**Role:** own REFab / REFsb / RFM / ZQ scheduling; assert OVERRIDE over S1–S3 when a
maintenance op is critical (correctness first). Decide, per refresh window,
**REFab vs REFsb vs skip-and-defer**.

### Input ports (`RMC_IO_Map.md §19 S0` + §20 ME + §29 per-rank FSM)

```
→ ref_urgent       1b                          watchdog: refresh no longer deferrable
→ ref_due          1b                          tREFI elapsed, refresh wanted
→ zq_due           1b                          ZQ calibration due
→ rfm_req          [N_RANKS][DFI_MASK_WIDTH]    RAA over RAAIMT → rowhammer refresh forced
→ global_state     [BURST_WIDTH]               rank state (idle / active / refreshing)
→ bank_act_count   [N_RANKS][mask][clog2]       outstanding-ACT demand per bank
→ all_idle         [N_RANKS]                    rank fully precharged?
→ next_trefi_out   [N_RANKS][GC_WIDTH]          next refresh deadline
→ ref_credits_out  [N_RANKS]                    REFsb credits (8 REFsb = 1 REFab)
→ last_refsb_gc    [32][GC_WIDTH]               per bank-index last-REFsb timestamp
→ overdue_bitmap   32b                          (gc − last_refsb_gc[b]) > tREFI×32
→ most_overdue_idx 5b                           argmax overdue — watchdog target
```

### Logic blocks

1. **Deadline tracker** — per-rank tREFI down-counter → `ref_due`; watchdog →
   `ref_urgent`. RFM RAA compare → `rfm_req`.
2. **REFab / REFsb / skip decision.**
   - REFsb granularity is **not** single-bank: JEDEC REFsb refreshes one bank-index
     `BA[1:0]` across **all 4 bank groups** at once, rotating `00→01→10→11`. Recovery
     `tRFCsb` (312 @4800B) < `tRFC1` (708); other banks stay accessible during it.
     8 REFsb = 1 REFab credit.
   - **Ordering constraint (JEDEC):** REFsb targets must cycle **in order**
     `00→01→10→11` for coverage; the controller tracks the rotation counter. So the
     predictor does **not** freely pick the coldest index — each window it decides
     *refresh-now vs defer* for the **current rotation index k** only. Free choice is
     timing, not which index.
   - **Predictor — cold-index refresh gate.** One index k = 4 banks
     `B_k = {k, k+4, k+8, k+12}` (same bank across all 4 BGs). Three tiers:

     **Tier 1 — correctness override (no prediction):**
     ```
     if ref_urgent | overdue_bitmap[k] | skip[k] >= SKIP_MAX:
         REFRESH NOW   (REFsb k; escalate to REFab if rank pressure high)
     ```
     **Tier 2 — hard safety gate (exact, the 96-entry queue is known):**
     ```
     if any bank_act_count[b] > 0 for b in B_k:
         DEFER; skip[k]++          # a queued request already wants these banks
     ```
     **Tier 3 — arrival predictor (will NEW arrivals hit B_k during the tRFCsb window?):**
     ```
     cold    = min over b in B_k of (gc - last_access_gc[b])    # hottest bank governs
     proj    = { b_head + i*Δ (mod N_BANKS) : i = 1..P }        # stride projection
     collide = proj ∩ B_k != ∅
     predict_no_arrival = (cold >= COLD_THRESH) AND NOT collide
     if predict_no_arrival: REFRESH NOW (REFsb k)
     else:                  DEFER; skip[k]++
     ```
     **Stride detector:** each new arrival pushes its bank into a 2-deep history;
     `Δ = b_curr − b_prev (mod N_BANKS)`, `b_head = b_curr`. Δ stable over last M
     arrivals ⇒ **locked**, projection trusted; else `collide=1` (unknown pattern —
     no speculative refresh, fall back to Tier 2 + coldness).

     | param | default @4800B | meaning |
     |---|---|---|
     | `COLD_THRESH` | `tRFCsb`=312 | idle > one refresh window ⇒ likely stays cold |
     | `P` | ≤ N_BANKS=16 | projection depth (near-future arrivals to dodge) |
     | `SKIP_MAX` | 3–4 | bounds deferral so a hot index refreshes within a few windows |

     **Weights tie-in (read/write-outstanding) — occupancy-scaled threshold:**
     `COLD_THRESH = tRFCsb * (1 + outstanding/depth)`. Low occupancy → ~312, refresh
     eagerly into the idle; high occupancy → threshold rises, protect throughput,
     defer.
   - **Why it self-limits (mirrors the adaptive-batching finding):**
     - concentrated / strided working set (< all banks) → cold indices exist, and with
       clean address mapping the stride projection is exact → REFsb hides in the
       datapath. This is the original insight made concrete.
     - uniform all-bank sweep (Δ=1 over all 16) → every index collides within one wrap
       → `predict_no_arrival` never fires → correctly falls through to **REFab on a
       drain** (Tier 1 when overdue). No free REFsb window exists when all banks are
       hot; the predictor routes to the right fallback instead of forcing a bad REFsb.
   - RFM tie-in: JEDEC mandates the per-bank RAA (Rolling Accumulated ACT) counter for
     rowhammer; clean mapping that avoids re-hammering one bank *reduces* RFM pressure.
   - New scoreboard state this needs: `last_access_gc[N_BANKS]` (per-bank idleness),
     `skip[4]` (per rotation-index defer counter), stride detector (2-deep bank
     history + locked flag). All thin regs, off the critical path.
3. **Override arbiter** — if `ref_urgent | rfm_req | zq_due`, raise `s0_override` and
   drive the maintenance command; S4 gives it top priority.

### Output ports

```
← s0_override   1b
← s0_cmd_type   [BURST_WIDTH]   REFab / REFsb / ZQCS / PREA(drain)
← s0_rank       [RANK_BITS]
← s0_bg         [BG_BITS]
← s0_bank       [BANK_BITS]     REFsb rotation index
```

Reuse: `maintenance_engine` (Refresh / ZQ / RFM FSMs), `bank_activity_ctr`, per-rank
FSM `last_refsb_gc` / `overdue_bitmap`. Predictor defined above (cold-index gate).

---

## Stage 1 — Classify-all + PRE pick

**Role:** every cycle, over ALL entries — TCAM-classify hit/empty/miss → `work_state`;
apply the sibling-tag PRE-defer; nominate ONE PRE. (Not fetch-one; see §0 frame.)

### Input ports (`RMC_IO_Map.md §19 S1` + new-request + sibling)

```
→ wr_tcam_hit_bitmap  [N_WR_ENTRIES]    row-hit per write entry
→ rd_tcam_hit_bitmap  [N_RD_ENTRIES]    row-hit per read entry
→ wr/rd_tcam_hit_meta  per bank          {row, col, req_type, entry_idx, axi_id}
→ wr_status_valid     [N_WR_ENTRIES]
→ rd_status_valid     [N_RD_ENTRIES]
→ new_rd_bank/row/col/axi_id/age         newest-arrival fast path (axi_id masked)
→ batch_policy_reg                       current mode R/W + QoS (from adaptive batch)
→ demand_count[bank]                     outstanding reqs on the open row (sibling/PRE gate)
```

### Logic blocks

1. **Classifier** — per valid entry, the TCAM hit-vector tags:
   `open && row==req → NEED_CAS (hit)`, `closed → NEED_ACT (empty)`,
   `open && row!=req → NEED_PRE (miss)`. Writes `work_state`. Emits `s1_hit_bitmap`
   (valid-gated) and `s1_hit_meta[]` per bank.
2. **Sibling-tag defer** — CIF `burst_splitter` fractures one AXI request into packets
   sharing `(bank, row)` under one tag. While unretired same-tag siblings still want a
   bank's open row, that bank is **not** PRE-eligible (the siblings are guaranteed
   row-hits — drain them first). Reuses the adaptive-batch demand counter, keyed by
   tag. Applies to reads **and** writes (writes split too; WDB holds the data).
   Effect: cuts per-request tail latency and raises row-hit rate.
3. **PRE picker** — among `NEED_PRE` + legal-PRE entries, nominate one, scored by
   `batch_policy + QoS + age`. `pre_ready` = `work_state` + timing gate clear.

### Output ports

```
← s1_hit_bitmap  [N_BANKS]     classified, valid-gated
← s1_hit_meta[]   per bank      {row, col, req_type, entry_idx, axi_id}
← s1_pre_nom      {entry_idx, bank, bg}     nominated PRE (to S4)
```

Reuse: `wr/rd_tcam` (search = classify), `wr/rd_status_reg` (+ `work_state` field).
**OPEN: PRE-picker scoring weights.**

---

## Stage 2 — ACT pick (lookahead prep)

**Role:** open the row the heartbeat needs *next*, tRCD ahead, so it completes in the
burst shadow. ACT is scarce — tFAW caps it at 4 per 32 tCK.

### Input ports (`RMC_IO_Map.md §19 S2` — the `can_*` gate vector)

```
→ s1_hit_bitmap / s1_hit_meta
→ can_act_out      [N_RANKS][mask]     per-bank ACT legal (tRP since PRE)
→ can_act_bg_out   [AWLEN_WIDTH]       tRRD_L (same-BG spacing)
→ can_act_any_out  1b                  tRRD_S (any-BG spacing)
→ can_faw_out      1b                  tFAW ring: < 4 ACT in window
→ gate_rfc_out / gate_zq_out           maintenance blocking a rank
→ state_out / row_open_out             per-bank open row
→ next_act_out     [N_RANKS][mask][GC]  per-bank next-legal-ACT gc
→ bank_act_count                        demand per bank (no speculative ACT)
→ gc
```

### Logic blocks

1. **ACT-legal gate** — `can_act & can_act_bg & can_act_any & can_faw`, and
   maintenance not gating the rank.
2. **Demand gate** — only banks with `bank_act_count > 0`. No speculative activation.
3. **Lookahead scorer** — prefer the demanded idle bank whose CAS the current batch
   mode needs soonest (hide tRCD under the already-queued bursts); BG-rotate to
   stretch the tRRD / tFAW budget.
4. **Age-boost (anti-starvation)** — the oldest demanded-but-idle bank eventually
   wins the ACT pick. This is the ACT-side livelock guard, the mirror of the S1 PRE
   demand gate.

**tFAW is the ACT throughput ceiling.** 4 ACT / 32 tCK; one burst = 8 tCK, so across
a 4-burst span you get ~4 ACTs — prep bandwidth ≈ burst bandwidth. That is why the
scheduler *just* keeps up when address mapping spreads banks, and collapses when a
stream lands in one bank (the interleave / one-bank case). S2 cannot beat tFAW; it can
only spend those 4 ACTs on the right banks.

*Baseline SJW at this stage = "cost classification": `remaining_cost` per bank, hit /
miss set split. The greedy replaces the cost sort with the lookahead + age score.*

### Output ports

```
← hit_set_bitmap   [N_BANKS]           baseline naming; greedy: ready-CAS set
← miss_set_bitmap  [N_BANKS]           need ACT/PRE first
← remaining_cost[] [GC] per bank        cycles-to-data (baseline SJW input)
← s2_act_nom       {entry_idx, bank, bg}   nominated ACT (to S4)
```

**OPEN: lookahead ordering + age-boost magnitude (same knob-pass as S1).**

---

## Stage 3 — CAS pick (the heartbeat)

**Role:** fill the next DQ slot every cycle. Nominate one CAS.

### Input ports (`RMC_IO_Map.md §19 S3`)

```
→ hit_set_bitmap / miss_set_bitmap / remaining_cost[]
→ can_cas_out      [N_RANKS][mask]     per-bank CAS legal (row open+match, tCCD, dqFree)
→ can_cas_bg_out   [AWLEN_WIDTH]       tCCD_L / tCCD_L_WR (same BG)
→ can_cas_any_out  1b                  tCCD_S (any BG)
→ can_rd_wr_out    1b                  tRTW clear (R→W turnaround)
→ can_wr_rd_out    1b                  tWTR+RL clear (W→R turnaround)
→ last_act_bg_out  [AWLEN_WIDTH][GC]   last-CAS BG (for the rotation score)
→ rd/wr_status_age [entries][GC]       age
→ wr_count / wr_high_wm_hit / wr_low_wm_hit    write watermark → batch pressure
→ gc
```

### Logic blocks

1. **CAS-legal gate** — row open AND `row == req`; `can_cas & can_cas_bg/any`; DQ-free
   (`gc + lat ≥ dqFree`); turnaround (`can_rd_wr` for R-after-W, `can_wr_rd` for
   W-after-R).
2. **Adaptive batch gate** — skip an opposite-direction CAS in the current mode;
   **charge gate-loss** for the idle DQ that skip costs; flip mode when the debt ≥ BL2
   and opposite work exists (the rule from [[scheduler_adaptive_batching]]). The
   watermarks `wr_high/low_wm_hit` add write-side pressure to the flip.
3. **BG-rotation tie-break** — prefer BG ≠ last-CAS BG (tCCD_S = 8 < tCCD_L = 12);
   score `s = (bg == lastCasBg ? 1e9 : 0) + id`. Age / id is the final tie-break.

*Baseline SJW at this stage = "SJF winner": min `remaining_cost`. The greedy is
busy-first + adaptive batch + BG-rotate.*

### Output ports

```
← winner_valid     1b
← winner_cmd_type  [BURST_WIDTH]   ACT / CAS_RD / CAS_WR / PRE
← winner_rank / bg / bank / row / col
← winner_entry_idx [clog2(BUF_DEPTH)]
← winner_req_type  1b   R/W
```

The three per-class nominations (S1 PRE, S2 ACT, S3 CAS) collapse onto this one
`winner_*` bus; S4 does the final cross-class priority.

---

## Stage 4 — CA-mux + DFI emit + writeback (single arbiter)

**Role:** the one point honoring 1-cmd / 2-tCK. Pick one winner, drive DFI, commit the
scoreboard, retire.

### Input ports (`RMC_IO_Map.md §19 S4`)

```
→ winner_*         from S3 (+ S1/S2 candidates)
→ s0_override / s0_cmd_*    maintenance
→ timing_reg_vals  parallel from timing_reg_file
→ gc
```

### Logic blocks

1. **Priority mux:**
   `REF(s0_override, critical) > CAS(busy-fill) > ACT/PRE(lookahead) > REF(due, not critical)`.
   The 3-free-slots-per-burst budget (§0) is what lets prep ride behind the CAS
   instead of being starved by it.
2. **DFI 5.2 driver** (spec `ddr5_ref.tex`):

   | cmd | act_n / ras / cas / we | extra |
   |---|---|---|
   | ACT | `act_n=L` (ras=L, cas=H, we=H) | row addr |
   | RD / WR | cas=L, we=H/L | col; `dfi_wrdata_en` / `rddata_en` issued ahead by WL / RL |
   | PRE | ras=L, cas=H, we=L | AP: `addr[10]=H` |
   | REFab / REFsb | ras=L, cas=L, we=H | REFsb: `dfi_bank[1:0]` = rotation index |

3. **Scoreboard commit** — advance every `next_*` (tRCD / tRAS / tRP / tCCD / tWTR /
   tFAW ring). **`next_pre = MAX` over its writers** (ACT's tRAS vs CAS's tRTP / tWR) —
   a real bug the golden model caught; the RTL must replicate it.
4. **Work-state + retire** — advance `NEED_PRE → ACT → CAS → DONE`; on CAS-complete
   free the status / TCAM slot back to the watermark; read data → ROB at RL, write
   drains from WDB.

### Output ports

```
← dfi_address / dfi_cs_n / dfi_bg / dfi_bank / dfi_act_n
← dfi_wrdata / dfi_wrdata_en / dfi_wrdata_mask
← bank_fsm_update_en + {state, next_cas, next_pre, next_act, row_open}
← global_timing_update_* {next_act_any, next_cas_any, faw, bg arrays}
← status_update_en / status_update_idx / status_update_val
← sched_ack   → Maintenance Engine (S0 handshake)
← raa_inc_en  → Per-Rank FSM (RAA++ per ACT, for RFM)
```

---

## Cross-stage data flow

```
S0 ─override──────────────────────────────────┐
tables → S1 classify → s1_hit → S2 ACT-pick ─┐ │
                     └───────────→ S3 CAS-pick┼─→ S4 mux → DFI + scoreboard commit
                     └─ S1 PRE-nom ───────────┘ │            └─ retire → watermark
scoreboard (next_*) ←────────────────────────────┘  (feeds S2/S3 can_* next cycle)
```

The pickers are parallel, not a conveyor: S1/S2/S3 all read the same classified pool
and the scoreboard in the same cycle. S4 serializes to one command per CA slot and
writes the scoreboard, which the `can_*` gates re-read the next cycle.

---

## OPEN items (deferred, non-blocking)

- **S1 PRE + S2 ACT scoring weights** — oldest / newest / QoS / age blend, lookahead
  ordering, age-boost magnitude. One dedicated "weights" pass.
- **CIF outstanding depth.** pkg currently gives `N_WR_ENTRIES=64 + N_RD_ENTRIES=32 =
  96` (and `N_WR_ENTRIES` carries a `TODO: lock 64 vs 96` note). The "256 packets"
  figure from the S0 discussion does not match the frozen pkg — reconcile before the
  predictor lookahead depth is fixed. (Not a pkg edit here — flagged only.)

## Consistency / verification

- Ports = `RMC_IO_Map.md §19` + `scheduler.sv`, verbatim.
- Logic = golden model `sched_test.js` — the eventual RTL must match it
  cycle-for-cycle on the same trace (the bench is the checker).
- Timing names = `datapath_busy_timing.md §1` + `ddr5_ref.tex`.
- No contradiction with the committed dynamic / microarch / adaptive-batching docs.
- pkg values quoted are frozen; no pkg edits.

## Hard rules

pkg FROZEN. Doc-only, **no RTL** until the sweep is done and the user says go. Commit
at milestone; push only when asked. See [[rmc-timing-sweep-phase]].
