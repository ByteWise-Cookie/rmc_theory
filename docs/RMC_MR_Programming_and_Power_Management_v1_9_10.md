# RMC — Architecture Addendum v1.9.10

## Mode Register Programming & Power Management — Completed Architecture

---

## 0. Status of This Addendum

This document extends the v1.9.8 architecture (`RMC_Full_Knowledge_v1.9.8.md`, `RMC_Handoff_v1.9.8.md`, `RMC_IO_Map.md`) with the two features left unfinished at that version: **Mode Register Programming beyond boot** and **Power Management**. It does not redesign any existing block. Every change below is additive or a narrow, justified width/port extension to an existing block, called out explicitly in §C.

Both features are handled inside the **Maintenance Engine (ME)**, consistent with the project's existing model: ME is a peer to the Scheduler, writes into FSM tables directly for maintenance events, and never issues CAS. Both features route their DRAM-facing commands through the existing **Stage-0 override → Stage-4 emission** path — no new command path is introduced into the Scheduler.

**Changes from v1.9.9** (all from an independent architecture review; no new features beyond what the review agreed to):

- Section A now states explicitly, up front, that runtime MR write is an inferred extension, not a stated requirement.
- `MR_WR_REQUIRE_IDLE`'s rationale as a per-request field (not a fixed policy) is now stated.
- The MRR read-back path is now a properly arbitrated shared resource between MR_Poll and MR_Write, rather than an implicitly-single-owner reuse.
- The `timing_reg_file` shadow mechanism is now a single-entry `{shadow_val, shadow_param_id}` pair, replacing the originally proposed full-table shadow copy.
- Gate-check timeout is now stated as an intentional baseline non-requirement, not a gap.
- The Stage-4 broadcast write is now described accurately as a structural change to the Per-Bank FSM Table's write-enable decoder, not a free reuse of existing logic.
- §B.7 now states explicitly that TCAM allocation during `POWER_DOWN` does not imply permission to issue until `gate_pwr` clears.
- `PD_FORCE_EXIT_ON_REF` is removed as a CSR; REF unconditionally pre-empting `POWER_DOWN` is now a fixed architectural invariant.

---

# SECTION A — Mode Register Programming

**Assumption, stated explicitly (previously left implicit):** the v1.9.8 ground-truth documents specify only two MR-related capabilities — boot-time `MRW_BURST` (Init FSM) and periodic MR4/TUF read polling (MR_Poll FSM). No runtime mode-register **write** requirement is stated anywhere in the ground truth. This entire section is therefore an inferred extension, adopted on the reading that "Mode Register Programming" is one of the two features explicitly called out as unfinished — if runtime MR write was not intended to be in scope, Section A should be dropped in full, and MR_Poll requires no changes at all (the shared MR-read arbitration introduced below, §A.3/§A.9, exists solely because MR_Write is introduced alongside it).

## A.1 Design Goals

1. Preserve the existing boot-time `MRW_BURST` behavior in Init FSM exactly as documented — zero changes to Init FSM.
2. Add a **runtime** mode-register write capability, since the architecture currently has no way to reprogram a DRAM mode register (ODT, drive strength, refresh mode, latency mode, etc.) after `init_done`.
3. Keep the mechanism a **slow, deliberate, software-triggered control-plane operation** — consistent with how `timing_reg_file` is already described ("write: CSR only, slow path"). No queue, no pipelining, no performance requirement.
4. Guarantee that any timing-affecting mode-register write can never leave the controller's internal timing expectations (`timing_reg_file`) out of sync with the DRAM's actual programmed latency — this is the single hardest correctness requirement in this feature and is treated as a first-class invariant (§A.12).
5. Reuse the existing MR4/TUF read infrastructure (MR_Poll FSM, sideband return path) as a **shared, arbitrated** resource rather than duplicating it.

## A.2 Functional Overview

A new ME sub-FSM, **MR_Write FSM**, accepts a single outstanding software-issued mode-register write request via CSR, waits for the target rank to be in a safe state, issues the MRW through the existing Stage-0/Stage-4 override path, optionally reads it back for verification through a small shared MR-read arbiter (§A.3, §A.9) it holds in common with MR_Poll, and — only if the request is flagged as timing-affecting — atomically commits a single staged timing value into `timing_reg_file`'s live table.

MR_Poll (MR4/TUF polling) keeps its existing state machine, poll interval, TUF parsing, and tREFI-adjustment logic entirely unchanged. It receives exactly one narrow modification: its `REQUEST_MRR`/`WAIT_RDDATA` states now go through the same shared MR-read arbiter MR_Write uses, rather than assuming sole ownership of the sideband return path — necessary because two independent FSMs can now issue MRRs, and rank alone is not a sufficient response tag once that's true. MR_Write remains a new peer sub-FSM, not a restructuring of MR_Poll — the two stay functionally distinct (periodic read vs. on-demand write), consistent with the existing one-concern-per-sub-FSM pattern (Refresh / ZQcal / RFM / PwrMgmt / MR_Poll are all separate for the same reason).

## A.3 New Block: MR_Write FSM (ME Sub-FSM 7)

```
IDLE → WAIT_REQ → GATE_CHECK → ISSUE_MRW → WAIT_tMRD →
  [VERIFY_MRR → WAIT_RDDATA → CHECK_MATCH] (optional, MR_WR_VERIFY=1) →
  [APPLY_TIMING] (optional, MR_WR_AFFECTS_TIMING=1) →
DONE → IDLE
```

- **WAIT_REQ**: idle until `mr_wr_req` (CSR pulse) is seen. Latches `MR_WR_ADDR`, `MR_WR_DATA`, `MR_WR_RANK`, `MR_WR_AFFECTS_TIMING`, `MR_WR_VERIFY`, `MR_WR_REQUIRE_IDLE` into internal request registers. Asserts `mr_wr_busy`.
- **GATE_CHECK**: waits until `gate_pwr[MR_WR_RANK]==0` (rank not in power-down/self-refresh — see §B) and, if `MR_WR_REQUIRE_IDLE=1`, until `bank_act_count[MR_WR_RANK][*]==0` for all 16 banks. No forced eviction of in-flight traffic is performed — this is a bounded wait, not an override of Scheduler activity. **Rationale for `MR_WR_REQUIRE_IDLE` as a per-request software field, not a fixed hardware policy:** different DDR5 mode registers have genuinely different safety requirements — registers that only affect status/monitoring behavior are typically safe to write with the rank active, while registers that affect latency, drive strength, or other timing-adjacent behavior generally require full rank quiescence. RMC has no built-in knowledge of what a given `MR_WR_ADDR` value means in DDR5 terms; only software, which does know the target register's semantics, is in a position to decide this correctly on a per-write basis. A fixed hardware policy (always-idle or never-idle) would either be unnecessarily conservative for registers that don't need it, or unsafe for the ones that do.
- **ISSUE_MRW**: requests the Stage-0 bypass lane (`mr_write_req`, new signal, see §A.9) with `me_cmd_type = MRW`, `me_cmd_rank = MR_WR_RANK`, plus `mr_wr_addr`/`mr_wr_data` carried alongside for Stage 4 to place on `dfi_address`/`dfi_wrdata`.
- **WAIT_tMRD**: holds `gate_mr[rank]=1` (new gate, see §A.9) for `T_MRD` cycles (already present in `timing_reg_file`).
- **VERIFY_MRR** (optional): requests the shared **MR Read Arbiter** (§A.9, new — a small arbitration point shared with MR_Poll, since both FSMs can independently need to issue an MRR and rank alone does not disambiguate which one a given response belongs to). The arbiter grants at most one requester at a time; if MR_Poll already holds it mid-transaction, MR_Write's request simply waits until MR_Poll's response completes (no preemption of an in-flight read). If both request in the same idle cycle, MR_Write is granted first (reusing the existing `mr_write_req > mrr_due` tie-break from §A.7) — MR_Poll's routine poll tolerates a short additional delay far more easily than a deliberate software verification step. Once granted, MR_Write issues an MRR to the just-written register number and waits on the sideband return path (`mrr_data_valid`/`mrr_data`/`mrr_rank`/`mrr_requester`) tagged for it. `CHECK_MATCH` compares `mrr_data` to `MR_WR_DATA` and sets `mr_wr_error` on mismatch.
- **APPLY_TIMING** (optional): pulses `timing_apply_en` into `timing_reg_file` (§A.4), committing the single staged timing value.
- **DONE**: clears `gate_mr[rank]`, sets `mr_wr_done` (sticky until next `mr_wr_req`), clears `mr_wr_busy`.

## A.4 Datapaths / Control Paths

**MR write command path** (new): `MR_Write FSM → Stage 0 (mr_write_req) → Stage 4 → dfi_address/dfi_cs_n/dfi_act_n/dfi_wrdata/dfi_wrdata_en`. This is the same physical DFI output register set the Scheduler and Init FSM already drive — no new DFI datapath is added, only a new source feeding the existing Stage-4 emission logic, exactly the way REF/ZQ/RFM/MRR already feed it today.

**MR read-back path** (existing sideband, now arbitrated): Read Data Path sideband → `mrr_data_valid`/`mrr_data`/`mrr_rank` (existing) plus a new `mrr_requester` tag → whichever of MR_Poll's `WAIT_RDDATA` or MR_Write's `WAIT_RDDATA` currently holds the **MR Read Arbiter** grant (§A.9, new). The Read Data Path itself is unmodified — only the two consumers upstream of it are now arbitrated rather than assumed to be a single owner.

**Timing shadow/apply path** (new, `timing_reg_file` only — single-entry):

```
csr_wr_en/csr_param_id/csr_param_val:
  while !init_done:  live_val[param_id] ← csr_param_val         (unchanged, direct, immediate)
  while  init_done:  {shadow_val, shadow_param_id} ← {csr_param_val, csr_param_id}
                      (runtime CSR write stages one {value, id} pair; live_val is untouched)

timing_apply_en (from MR_Write FSM, pulse):
  live_val[shadow_param_id] ← shadow_val        (single-entry commit, one cycle, one field)
```

`param_val[]` (the multi-port combinational read Stage 2/Stage 4 use) always reads `live_val`. This means: at init time, CSR writes take effect immediately (identical to today); after `init_done`, a CSR write to `timing_reg_file` stages a value that has **no effect on the Scheduler** until `timing_apply_en` fires — which only happens as the last step of a successful `MR_WR_AFFECTS_TIMING=1` write. This closes the correctness gap identified in research: it is structurally impossible for the Scheduler to assume a new timing value before the DRAM has actually been reprogrammed to match it.

This replaces the full-table shadow copy originally proposed with a single `{shadow_val, shadow_param_id}` register pair. Invariant A.12-4 (at most one MR write outstanding at a time) already guarantees at most one parameter's worth of shadow state is ever needed simultaneously, so duplicating the entire `timing_reg_file` — a table read every cycle on the Stage 2/4 hot path — bought no additional correctness and cost real storage for no benefit. The guarantee itself is unchanged: no runtime CSR write can affect scheduling behavior until `timing_apply_en` commits it, one parameter at a time.

## A.5 FSM State Table

|State|Purpose|Exit condition|
|---|---|---|
|IDLE|Wait for boot to complete|`init_done==1`|
|WAIT_REQ|Wait for software request|`mr_wr_req` pulse|
|GATE_CHECK|Wait for safe rank state|`gate_pwr[r]==0` AND (`!MR_WR_REQUIRE_IDLE` OR `bank_act_count[r][*]==0`)|
|ISSUE_MRW|Win Stage-0 arbitration, command emitted|`sched_ack`|
|WAIT_tMRD|Command spacing|`gc >= issue_gc + T_MRD`|
|VERIFY_MRR|Acquire MR Read Arbiter grant, issue read-back|`mrr_slot_grant_write && sched_ack`|
|WAIT_RDDATA|Wait for sideband return|`mrr_data_valid && mrr_rank==r && mrr_requester==WRITE`|
|CHECK_MATCH|Compare read-back to written value|always (1 cycle)|
|APPLY_TIMING|Commit staged timing value|`MR_WR_AFFECTS_TIMING` (else skipped)|
|DONE|Report completion, clear gates|always (1 cycle) → IDLE|

9 states (10 counting the skip-paths as no-ops through the same state slots — no new state needed for "not requested," it's a conditional bypass of VERIFY_MRR/APPLY_TIMING).

## A.6 State Ownership

|Item|Owner (R/W)|Others|
|---|---|---|
|MR_Write FSM internal state|MR_Write FSM|—|
|`timing_reg_file.shadow_val` / `shadow_param_id`|CSR|READ: MR_Write FSM (via apply)|
|`timing_reg_file.live_val[]`|CSR (init time, direct) / `timing_apply_en` pulse, single-entry (runtime)|READ ONLY: everyone else|
|MR Read Arbiter grant state|MR Read Arbiter (new, shared)|READ: MR_Poll FSM, MR_Write FSM|
|`gate_mr[rank]`|MR_Write FSM|READ ONLY: Scheduler Stage 2|
|`mr_wr_busy` / `mr_wr_done` / `mr_wr_error`|MR_Write FSM|READ ONLY: CSR/software|

This preserves Core Rule #2 (every register has exactly one owner) without exception.

## A.7 Scheduler Interaction

The Scheduler is not aware MR programming exists except through two gate signals it already has slots for structurally:

- `gate_mr[rank]` — new, added to the Legal Check Matrix (Stage 2 gate inputs), same shape as `gate_rfc`/`gate_zq`. Blocks all per-bank commands to that rank while an MRW/MRR/verify sequence is in flight.
- Stage 0 priority list gains one new entry at the **bottom** (lowest priority — MR writes are deliberate, non-urgent, software-paced): `ref_urgent > ref_due > rfm_req > zq_due > mr_access_req` where `mr_access_req = mrr_due (MR_Poll) OR mr_write_req (MR_Write)`, sub-arbitrated `mr_write_req > mrr_due` if both happen to fire the same cycle (a deliberate software write is treated as more consequential than a routine thermal poll; this collision is rare enough — MR_Poll's default interval is 32×tREFI — that the sub-priority choice has negligible practical effect and exists only to make the arbitration total/deterministic). This same tie-break is reused inside the MR Read Arbiter (§A.3, §A.9) for the analogous case of both FSMs wanting the read-back slot simultaneously.

No changes to Stage 1–3 logic. No changes to TCAM, status registers, or watermark managers.

## A.8 Maintenance Engine Interaction

MR_Write is a peer to the other 6 sub-FSMs, arbitrated the same way. It additionally depends on Power Management (§B): `GATE_CHECK` cannot proceed while `gate_pwr[r]==1`. This is a read-only dependency (MR_Write never writes Power Mgmt FSM state), so it doesn't create a new writer of shared state — it just adds one more consumer of a signal Power Management already needs to produce for the Scheduler.

This addendum also introduces one further cross-sub-FSM relationship, this time between MR_Write and MR_Poll directly: both request the shared MR Read Arbiter (§A.3, §A.9) before issuing any MRR. This is a narrow, single-purpose arbitration point, not a merging of the two FSMs, and it does not create a new writer of either FSM's own state — each FSM still owns its own state table entries exclusively; the arbiter only decides _whose turn_ it is to use the shared sideband return path.

## A.9 New Interfaces / Signals

```
MR_Write FSM
→ init_done, gc, T_MRD (from timing_reg_file), gate_pwr[N_RANKS], bank_act_count[N_RANKS][16]
→ mrr_data_valid, mrr_data[7:0], mrr_rank, mrr_requester   (existing sideband + new requester tag)
→ CSR: mr_wr_req, mr_wr_addr[5:0], mr_wr_data[7:0], mr_wr_rank[RANK_BITS-1:0],
       mr_wr_require_idle, mr_wr_affects_timing, mr_wr_verify

← mr_write_req            1b   → Stage 0 (new arbitration input)
← me_cmd_valid/type/rank   (existing ME→Stage4 channel, MRW added to me_cmd_type enum)
← gate_mr[N_RANKS]         → Scheduler Stage 2 (new gate)
← timing_apply_en          1b   → timing_reg_file (new, single-entry commit)
← mr_wr_busy, mr_wr_done, mr_wr_error   (CSR status, RO)

MR Read Arbiter (new, small shared resource — not a counted sub-FSM)
→ mrr_slot_req_poll (from MR_Poll), mrr_slot_req_write (from MR_Write)
← mrr_slot_grant_poll, mrr_slot_grant_write   (mutually exclusive, fixed priority: write > poll)
← mrr_requester            1b   (tags the outstanding MRR's owner; carried with the sideband
                                  response so a rank match alone is no longer used to route it)
```

`timing_reg_file` gains:

```
→ timing_apply_en   1b
  (internally: a single {shadow_val, shadow_param_id} register pair added alongside existing
   live_val[]; read ports unaffected — always read live_val[])
```

## A.10 CSR Requirements

|Register|Default|Description|
|---|---|---|
|`MR_WR_REQ`|0|Write-1-to-pulse: request a mode-register write|
|`MR_WR_ADDR`|—|Target mode register number [5:0] (covers DDR5's MR space)|
|`MR_WR_DATA`|—|8b payload (matches existing `mrr_data` width)|
|`MR_WR_RANK`|—|Target rank `[RANK_BITS-1:0]`|
|`MR_WR_REQUIRE_IDLE`|1|Wait for target rank's banks idle before issuing (per-request policy — see rationale in §A.3)|
|`MR_WR_AFFECTS_TIMING`|0|If 1, pulse `timing_apply_en` on successful completion|
|`MR_WR_VERIFY`|0|If 1, MRR read-back and compare after write|
|`MR_WR_BUSY`|— (RO)|FSM currently executing a request|
|`MR_WR_DONE`|— (RO, sticky)|Last request completed; cleared by next `MR_WR_REQ`|
|`MR_WR_ERROR`|— (RO)|Verify mismatch, or gate-check timeout in implementations that choose to detect it (see §A.13)|

## A.11 Timing Considerations

- `T_MRD` (already in `timing_reg_file`) governs command spacing after MRW — reused directly, no new timing parameter needed.
- `timing_apply_en` is a single-cycle, single-entry, registered commit — one extra cycle of latency on the rare runtime-reprogram path, invisible to steady-state performance.
- `GATE_CHECK` has no timeout. This is an intentional baseline position, not an omission: no other gate in this architecture (`gate_rfc`, `gate_zq`, `gate_pwr`) has a documented watchdog either, so timeout detection is left as an optional, implementation-specific addition rather than a baseline requirement (see §A.13).

## A.12 Architectural Invariants

1. **Init FSM behavior is unchanged.** MR_Write FSM only becomes reachable after `init_done`.
2. **`timing_reg_file.live_val[param_id]` may only change either (a) directly from a CSR write before `init_done`, or (b) via a `timing_apply_en` pulse committing the single staged `{shadow_val, shadow_param_id}` pair after `init_done`.** There is no third path, and at most one `live_val` entry can be pending commit at a time (following directly from invariant 4 below). This is the invariant that makes the timing-desync failure mode structurally unreachable rather than merely unlikely.
3. **`timing_apply_en` may only be asserted by MR_Write FSM, and only after the corresponding MRW (and, if requested, its verification) has completed successfully.** Software cannot pulse it directly — there is no CSR bit that drives it, by design, so a register-file value can never be "applied" without a matching DRAM-side write having actually happened.
4. **At most one MR write is outstanding at a time.** No queue exists; a second `MR_WR_REQ` while `mr_wr_busy==1` is ignored (software must poll `MR_WR_BUSY`).
5. **`gate_mr[rank]` and `gate_pwr[rank]` are mutually exclusive by construction** — GATE_CHECK will not enter `ISSUE_MRW` while `gate_pwr` is set, so the two gates never need to be asserted for the same rank simultaneously (documented for the benefit of anyone writing the integration assertions later).
6. **The MR Read Arbiter grants at most one requester (MR_Poll or MR_Write) at a time**, and a granted, in-flight read is never preempted — the other requester, if any, simply waits.

## A.13 Corner Cases

- **Target rank enters self-refresh while an MR write is in `WAIT_REQ`/`GATE_CHECK`.** Since SR exit is an externally-controlled `sr_exit` signal (§B), `GATE_CHECK` can stall indefinitely. This is an accepted trade-off, not a bug: software is expected not to schedule MR writes to a rank it knows is (or may soon be) in self-refresh. Gate-check timeout detection is intentionally not part of the baseline architecture — consistent with no other gate (`gate_rfc`, `gate_zq`, `gate_pwr`) having a documented watchdog either — so this stall has no hardware-enforced upper bound; implementations that choose to add a watchdog may report it through `MR_WR_ERROR`, but this addendum does not require one.
- **MR write targets a rank in power-down (not self-refresh).** Power-down is documented as exiting automatically the moment real traffic arrives (§B.7); a deliberate MR write request is treated the same as REF — see §B.8 for the PD-preemption rule that lets a pending `mr_write_req` similarly force `PDX_WAIT` rather than stalling behind an idle-only exit condition. This keeps MR_Write's worst-case latency bounded whenever the blocking condition is PD (only SR is unbounded, per the point above).
- **`MR_WR_VERIFY=1` and the read-back mismatches.** `mr_wr_error` is set, FSM still completes (goes to DONE) — it does not retry automatically. Software is responsible for deciding whether to retry, escalate, or treat it as fatal; the architecture doesn't presume the right policy for a verification failure this deep in the maintenance path.
- **`MR_WR_AFFECTS_TIMING=1` but the write itself fails verification.** `APPLY_TIMING` is skipped whenever `mr_wr_error` is set (verify runs before apply in the FSM order precisely so this is possible) — the staged shadow value is never committed to live if the DRAM never confirmed it took.
- **MR_Poll's periodic poll comes due while MR_Write holds the MR Read Arbiter.** MR_Poll's `REQUEST_MRR` simply waits for the grant; its poll interval (`MRR_POLL_INTERVAL`, default 32×tREFI) is large enough relative to any plausible MR_Write verify sequence that this delay has no material effect on thermal-monitoring responsiveness.

## A.14 Assumptions

- DDR5 mode registers are addressed with a 6-bit register number and carry an 8-bit payload, matching the width already implied by the existing `mrr_data[7:0]` port — this addendum does not introduce a new payload width, it reuses the one the docs already committed to for MR4.
- Software (not RMC) is responsible for knowing which mode registers are timing-affecting and setting `MR_WR_AFFECTS_TIMING` correctly, and for computing the correct new `timing_reg_file` shadow value before triggering the write — RMC does not derive nCK values from MR encodings.
- Software will not issue an MR write to a rank it knows to be in self-refresh (see corner case above).
- MR_Poll's thermal-monitoring poll can tolerate being delayed by a few cycles behind an in-flight or newly-arbitrated MR_Write verification without correctness impact, since its default interval is far larger than any plausible MR_Write verify sequence.

## A.15 Required Updates to Existing Tables

- **FSM Inventory / FSM Count Summary**: add row `MR_Write FSM | 9 | 1 | ME sub-FSM 7`.
- **`me_cmd_type` width**: bump from `[2:0]` to `[3:0]` — see §C.2 for the consolidated reason (this addendum's MRW plus Power Management's PD/SR command types exceed the existing 3-bit encoding space).
- **Legal Check Matrix**: add row `gate_mr[r] | MR_Write FSM | MRW/MRR sequence in progress`.
- **Config Registers table**: append the 10 registers in §A.10.
- **Block List (Handoff §5)**: ME entry gains "+ MR_Write FSM (7th sub-FSM), + MR Read Arbiter (shared, uncounted internal resource)".
- **MR_Poll FSM (existing block, narrow amendment)**: `REQUEST_MRR` and `WAIT_RDDATA` exit conditions are amended to acquire the MR Read Arbiter grant and check the `mrr_requester` tag, respectively. No states are added or removed; poll interval, TUF parsing, and tREFI-adjustment logic are unchanged.
- **`timing_reg_file` field list**: add a single `{shadow_val, shadow_param_id}` register pair alongside existing `live_val[]` (renaming the current unnamed register bank to `live_val[]` for clarity), and the `timing_apply_en` port. (Supersedes the full-table shadow copy described in v1.9.9.)

---

# SECTION B — Power Management

## B.1 Design Goals

1. Keep the existing Power Mgmt FSM's documented 10-state, two-branch (PD/SR) shape — it is already correctly scoped, just under-wired. Complete the wiring rather than redesign it.
2. Resolve the rank-vs-bank state granularity gap identified in research: entering/exiting PD or SR at the rank level must be visible at the bank level too, since the Per-Bank FSM Table already has `POWER_DOWN`/`SELF_REFRESH` encodings that nothing currently drives.
3. Give the Scheduler an actual way to know a rank is unavailable — the documented Legal Check Matrix has `gate_rfc`/`gate_zq` but nothing for PD/SR. Without this, the Scheduler could select a bank in a rank that's electrically powered down.
4. Give the PHY an actual way to know to power down — no `dfi_cke` (or equivalent) port exists anywhere in the current I/O map. Without it, "Power Management FSM" has no way to actually command power state at the DFI boundary.
5. Preserve the documented distinction that PD is autonomous/idle-triggered (`pd_en` + idle detection) while SR is externally directed (`sr_entry`/`sr_exit` "system signal") — this is a deliberate existing design choice and this addendum keeps it.
6. Correctly interleave power management with the two features that already contend for a rank's command bus: refresh (which must still happen — DRAM handles it internally during SR but not during PD) and, from Section A, mode-register writes.

## B.2 Functional Overview

Power Mgmt FSM gains: (a) a matching per-instance-per-rank replication so multi-rank configs don't serialize unrelated ranks' power transitions through one shared FSM, (b) a broadcast write path so entering/exiting PD or SR at the rank level correctly updates all 16 banks in that rank's Per-Bank FSM Table row set, (c) a new `gate_pwr[rank]` output consumed by Scheduler Stage 2, and (d) a new `dfi_cke[N_RANKS-1:0]` output, driven through a small dedicated mux inside the ME that hands ownership from Init FSM (during boot) to Power Mgmt FSM (after `init_done`) — structurally parallel to, but separate from, the existing DFI command mux, because CKE is a continuously-driven level signal, not a per-command field, and doesn't share the "one winner per cycle" contention the command bus mux exists to arbitrate.

## B.3 Block Responsibilities (Power Mgmt FSM, completed)

|Responsibility|Existing?|This addendum|
|---|---|---|
|PD entry decision (`bank_act_count==0`, `pd_en`, no pending maintenance)|Yes|unchanged|
|SR entry/exit decision|Yes (external signal)|unchanged|
|Drive `me_cmd_*` for PD/SR transitions|Implied, unwired|Wired: `me_cmd_type ∈ {PD_ENTRY, PD_EXIT, SR_ENTRY, SR_EXIT}`|
|Update Per-Rank FSM Table state/`next_xp`/`next_xs`|Yes|unchanged|
|Update Per-Bank FSM Table state (all 16 banks)|**No — gap**|**New: broadcast write, §B.4**|
|Signal Scheduler to stop targeting the rank|**No — gap**|**New: `gate_pwr[rank]`, §B.7**|
|Drive DFI-level power signaling|**No — gap**|**New: `dfi_cke[N_RANKS-1:0]`, §B.4**|
|Coordinate with Refresh FSM during SR|**No — gap**|**New: credit freeze, §B.8**|
|Coordinate with Refresh FSM during PD|**No — gap**|**New: REF-forces-PDX, §B.8 (fixed invariant)**|

## B.4 New Datapaths / Control Paths

**Broadcast bank-state write** (new, sourced from Stage 4 on an ME-originated PD/SR command, preserving Core Rule #1 — Stage 4 remains the sole writer of the Per-Bank FSM Table):

```
Power Mgmt FSM → me_cmd_valid, me_cmd_type ∈ {PD_ENTRY, PD_EXIT, SR_ENTRY, SR_EXIT}, me_cmd_rank
                                    │
                                    ▼
Stage 4 recognizes a rank-scoped (not bank-scoped) ME command and asserts:
  bank_fsm_broadcast_en     1b
  bank_fsm_broadcast_rank   [RANK_BITS-1:0]
  bank_fsm_broadcast_state  [2:0]   (POWER_DOWN or SELF_REFRESH on entry; IDLE on exit)
                                    │
                                    ▼
All 16 Per-Bank FSM Table rows where row.rank == bank_fsm_broadcast_rank update
`state` in the same cycle.
```

The existing Per-Bank FSM Table write path, as documented in v1.9.8, is a **one-hot decoder**: exactly one row's write-enable is active per cycle, selected by the winning bank from Stage 3/4 arbitration. Supporting the broadcast case requires a real, if narrow, structural change to that decoder: widening it from a single one-hot select to **16 independent write-enable terms**, each computed as `(bank_fsm_broadcast_en AND row.rank == bank_fsm_broadcast_rank) OR (existing single-row select for that row)`. This is the one place in Section B where existing Stage 4 logic is structurally modified rather than merely extended — stated explicitly here rather than described as free reuse, since it does change how the table's write-enables are generated, even though it adds no new storage and no new table.

**CKE Mux** (new, inside ME, parallel to the existing DFI Output Mux):

```
init_done==0  →  Init FSM drives dfi_cke[N_RANKS-1:0]   (CKE assertion sequence is already
                                                            part of Init FSM's documented
                                                            CS_PRE_DEASSERT/CS_POST_DEASSERT/
                                                            ODT_SETTLE states — this just gives
                                                            those states an actual output port)
init_done==1  →  Power Mgmt FSM drives dfi_cke[N_RANKS-1:0]
```

Same one-way-latch gating as the existing DFI mux; no third owner, consistent with the project's existing mux discipline.

## B.5 FSM State Table (10 states, completed)

|State|Branch|Entry condition|Exit condition|New wiring added|
|---|---|---|---|---|
|NORMAL|both|—|PD or SR entry condition|—|
|PD_ENTRY_CHECK|PD|`all bank_act_count[r][*]==0 AND pd_en AND no pending maintenance`|proceed|—|
|PRECHARGE_PD|PD|—|(all banks already precharged by entry check)|`dfi_cke[r]←0`; broadcast `POWER_DOWN`|
|ACTIVE_PD|PD|(reserved for future active-bank PD variant; unreachable in current entry-gate, since entry already requires all banks idle)|—|—|
|PDX_WAIT|PD|wake trigger (§B.7)|`gc >= exit_gc + T_XP`|`dfi_cke[r]←1`; broadcast `IDLE`|
|SR_ENTRY|SR|`sr_entry`|proceed|`dfi_cke[r]←0`|
|WAIT_tCKSRE|SR|—|`T_CKSRE` elapsed (new timing param, §B.10)|—|
|SELF_REFRESHING|SR|—|`sr_exit`|broadcast `SELF_REFRESH`|
|SR_EXIT|SR|`sr_exit`|proceed|`dfi_cke[r]←1`|
|WAIT_tXS_tDLLK|SR|—|`gc >= exit_gc + T_XS + T_DLLK`|broadcast `IDLE` on completion|

`ACTIVE_PD` is carried forward from the existing documented state list; this addendum does not add capability to enter it (the current PD entry gate requires full rank idle, which only ever produces `PRECHARGE_PD`). It's left in place unmodified rather than removed, since removing a documented state is a bigger change than leaving an currently-unreachable one — flagged as an open item in §B.14, not resolved here.

## B.6 State Ownership

|Item|Owner (R/W)|Others|
|---|---|---|
|Per-Rank FSM Table (state, `next_xp`, `next_xs`, `can_xp`, `can_xs`)|Power Mgmt FSM|READ ONLY: Scheduler S0|
|Per-Bank FSM Table `state` field, PD/SR values only|Stage 4 (broadcast write, ME-sourced)|READ ONLY: Scheduler S2|
|`dfi_cke[]`|Init FSM (boot) / Power Mgmt FSM (runtime), mutually exclusive via `init_done`|—|
|`gate_pwr[rank]`|Power Mgmt FSM|READ ONLY: Scheduler S2, MR_Write FSM (§A.8)|

No new violation of Core Rule #2 — every field still has exactly one writer.

## B.7 Scheduler Interaction

New gate, added to the Legal Check Matrix alongside `gate_rfc`/`gate_zq`:

|Gate|Source|Constraint|
|---|---|---|
|`gate_pwr[r]`|Per-rank, Power Mgmt FSM|Rank is in `POWER_DOWN` or `SELF_REFRESH` (PD and SR share one gate — both fully block rank command issue identically; they're already distinguished at the state/deadline level via `can_xp`/`can_xs`, so a shared entry gate doesn't lose any information)|

**Automatic PD wake**: Power Mgmt FSM already has `bank_act_count[N_RANKS][16]` as an input (existing port, unused for this purpose today). This addendum uses it directly: the moment any bank's `bank_act_count` for a gated-PD rank goes non-zero (i.e., the Watermark Manager allocates a new TCAM entry targeting that rank), `PDX_WAIT` is triggered automatically. No new signal is required — this reuses an existing input port for a new purpose, which is why it's called out as a datapath decision worth documenting rather than treated as free.

This transition only _triggers entry into_ `PDX_WAIT` — it does not itself permit command issue. `gate_pwr[r]` remains asserted for the entire `PDX_WAIT` duration and only clears once `T_XP` has elapsed and `dfi_cke[r]` has been reasserted (§B.5). TCAM allocation for a PD-gated rank is intentional, not a gap: allocation is unaffected by `gate_pwr` by design, identical to the already-documented self-refresh case below — this is the same accepted allocate-then-gate model already used for REF and ZQ elsewhere in this architecture (a rank can accumulate pending, allocated requests while gated; only _selection_ is blocked, never allocation).

**SR does not auto-wake on traffic.** Consistent with the existing "system signal" framing, new requests to an SR-gated rank simply queue normally in WR_TCAM/RD_TCAM (allocation is unaffected by `gate_pwr` — only Scheduler _selection_ is gated) and wait for `sr_exit`. This is an accepted, pre-existing design choice this addendum preserves rather than changes; see §B.13 for the starvation-interaction note this implies.

## B.8 Maintenance Engine Interaction

Two new cross-sub-FSM rules, both necessary for correctness and both additive:

1. **Refresh vs. Power-Down**: `ref_urgent`/`ref_due` targeting a rank with `gate_pwr[r]==1` due to `POWER_DOWN` (not `SELF_REFRESH`) **unconditionally** forces `PDX_WAIT` before the refresh command can be issued — real DRAM cannot receive a REF command while CKE is low, and there is no legitimate configuration in which delaying refresh in favor of staying in power-down is preferable to a data-retention risk. This is not a configurable policy: it is stated directly as an architectural invariant (§B.12-5) rather than gated behind a CSR, since disabling it would have no correctness-preserving use case — unlike `MR_WR_REQUIRE_IDLE` (§A.3), where different mode registers genuinely have different legitimate safety requirements, there is no equivalent legitimate variation here: REF must always win.
2. **Refresh vs. Self-Refresh**: while `gate_pwr[r]==1` due to `SELF_REFRESH`, the Refresh FSM's leaky-bucket `ref_credits[r]` counter is **frozen** (neither incremented on tREFI boundaries nor decremented on issue) rather than continuing to accumulate. Real DRAM refreshes itself internally during self-refresh, so RMC's own credit model would otherwise build a large backlog that fires as a burst of forced refreshes immediately after `sr_exit` — freezing avoids that entirely. `ref_credits[r]` resumes counting from wherever it was the instant `gate_pwr[r]` clears.

These two rules are the only changes to Refresh FSM behavior in this addendum; Refresh FSM's internal state machine, targeting policy (`argmin(bank_act_count)`), and watchdog logic are otherwise untouched.

## B.9 New Interfaces / Signals

```
Power Mgmt FSM (existing ports unchanged, new ones added)
← dfi_cke[N_RANKS-1:0]         → PHY, via new CKE mux (§B.4)
← gate_pwr[N_RANKS-1:0]        → Scheduler Stage 2, MR_Write FSM
← bank_fsm_broadcast_en        → Stage 4 (consumed there, not driven by Stage 4)
← bank_fsm_broadcast_rank      [RANK_BITS-1:0]
← bank_fsm_broadcast_state     [2:0]
→ ref_credits_freeze_ack       (from Refresh FSM, acknowledges freeze — optional handshake,
                                 included for the same reason other cross-FSM interactions in
                                 this design use explicit acks rather than implicit timing)

Refresh FSM (existing ports unchanged, new one added)
→ gate_pwr[N_RANKS-1:0]        (new input: freezes ref_credits per rank while SELF_REFRESH;
                                 unconditionally forces PDX_WAIT before issuing REF to a
                                 POWER_DOWN-gated rank, per fixed invariant B.12-5 — no CSR
                                 involved)
```

`me_cmd_type` enum extended (width bump, see §C.2): adds `MRW` (§A), `PD_ENTRY`, `PD_EXIT`, `SR_ENTRY`, `SR_EXIT`.

## B.10 CSR Requirements

|Register|Default|Description|
|---|---|---|
|`PD_IDLE_THRESHOLD`|64 cycles|Existing, unchanged|
|`T_CKSRE`|— (new `timing_reg_file` param)|Clock-stable cycles required before SR entry completes|
|`T_CKSRX`|— (new `timing_reg_file` param)|Clock-stable cycles required before SR exit completes (symmetric with `T_CKSRE`; both feed the existing `WAIT_tCKSRE`/`SR_EXIT` states)|

`T_XP`, `T_XS`, `T_DLLK` already exist in `timing_reg_file` and are reused unchanged. REF-forces-PDX (§B.8, rule 1) is a fixed architectural invariant (§B.12-5), not a CSR, and therefore does not appear in this table.

## B.11 Timing Considerations

- `T_CKSRE`/`T_CKSRX` are new entries in `timing_reg_file`'s param list (§17 of the I/O map), same 14-bit width as the other entries — no structural change to that table, just two new rows.
- The broadcast bank-state write (§B.4) is single-cycle regardless of rank width, since it's a parallel fan-out of write-enables, not a sequential per-bank loop — it does not add latency to PD/SR entry/exit beyond the DFI command cycle itself.
- `dfi_cke` mux switching is combinational on `init_done`, matching the existing DFI mux's timing model exactly — no new synchronizer needed since `init_done` is already a one-way latch inside the same clock domain.

## B.12 Architectural Invariants

1. **A rank's Per-Bank FSM Table rows and its Per-Rank FSM Table row report the same power state at all times** — enforced structurally by the broadcast write always accompanying the rank-level `rank_state_update` in the same Stage-4 cycle (both driven off the same `me_cmd_valid` pulse).
2. **`gate_pwr[r]` is asserted for the entire PD or SR sojourn, not just entry/exit transitions** — matches the existing `gate_rfc`/`gate_zq` behavior exactly (full-duration gate, not edge-triggered).
3. **`dfi_cke` has exactly one owner at any time** (`init_done`-gated, Init FSM or Power Mgmt FSM, never both) — same one-way-latch discipline as the primary DFI mux.
4. **`ref_credits[r]` is monotonically frozen during `SELF_REFRESH`, never during `POWER_DOWN`** — PD is expected to be a bounded, short-duration state (bank idle, not a sustained low-power mode), so real refresh obligations still apply and are handled via unconditional pre-emption (invariant 5, below) rather than freezing.
5. **REF unconditionally pre-empts `POWER_DOWN` — never `SELF_REFRESH`** (§B.8, rule 1) — `ref_urgent`/`ref_due` always forces `PDX_WAIT` before a refresh command can be issued to a `POWER_DOWN`-gated rank. This is a fixed architectural rule with no CSR override: `POWER_DOWN` always yields to a pending refresh obligation, unconditionally.
6. **`gate_pwr[r]` and `gate_mr[r]` (§A) are never asserted for the same rank simultaneously** — restated here as the Power Management side of the same invariant stated in §A.12.

## B.13 Corner Cases

- **New request arrives for a rank in self-refresh.** Allocation proceeds normally (TCAM entry created, status register updated, `age` starts accumulating) but Stage 2/3 cannot select it while `gate_pwr[r]==1`. Because SR has no auto-wake, this request's age can grow past `RD_STARVATION_THR`/`WR_STARVATION_THR` without the staggered starvation mechanism being able to fire — Stage 3 simply can't select a gated bank regardless of `STARVED_MISS` priority. This composes correctly (the existing mechanism already tolerates unbounded gating from REFab/ZQcal the same way); no new starvation-handling logic is required, but it's worth stating explicitly since SR's gating duration is the least bounded of any gate in the system.
- **PD entry check passes, then a request lands in the same cycle Stage 4 is committing the broadcast `POWER_DOWN` write.** Ordering rule: `bank_act_count` incrementing (new allocation) and the broadcast write are both synchronous to the MC clock; the Watermark Manager's allocation is defined to complete before Stage 4 in a given pipeline cycle (per existing pipeline ordering), so the auto-wake condition in §B.7 (`bank_act_count[r][*]` going non-zero) will be visible the cycle _after_ entry commits, correctly triggering `PDX_WAIT` on the very next cycle rather than missing the transition. No new arbitration logic needed — this falls out of `bank_act_count` already being a registered, one-cycle- visible signal.
- **`ACTIVE_PD` is unreachable** (§B.5) — not a corner case in the sense of needing a fix, but flagged so it isn't mistaken for a wiring bug when the tables are read later.

## B.14 Assumptions

- Multi-rank power management is treated as fully independent per rank — one rank entering PD or SR has no effect on any other rank's eligibility. Nothing in the existing docs suggests otherwise, and this is the natural reading of `all_idle[N_RANKS]`/`bank_act_count[N_RANKS][16]` already being per-rank vectors.
- `ACTIVE_PD` is left as a defined-but-unreachable state rather than removed, on the assumption that a future architecture revision may relax the PD entry gate to allow power-down with some banks still active (a real DDR5 capability) — this addendum does not implement that, only preserves the slot for it.
- `sr_entry`/`sr_exit` remain system-level (outside RMC) signals, as already documented; this addendum does not propose bringing self-refresh entry under RMC's autonomous control.

## B.15 Required Updates to Existing Tables

- **FSM Count Summary**: `Power Mgmt FSM | 10 | 1 → N_RANKS | ME sub-FSM 5` — instance count corrected from 1 to `N_RANKS`, matching the precedent already set by ZQcal FSM (also per-rank-independent, already documented as `N_RANKS` instances). This is the one required correction to an existing table value in this addendum, and it's a direct consequence of the FSM needing to manage each rank's power state independently (§B.14) while its documented ports are inherently per-rank-scoped in their effect.
- **Legal Check Matrix**: add row `gate_pwr[r] | Power Mgmt FSM | PD or SELF_REFRESH in progress`.
- **Per-Bank FSM Table**: no field changes — `POWER_DOWN`/`SELF_REFRESH` encodings already existed; this addendum adds the write path that finally drives them, which requires widening the table's write-enable decoder from one-hot to 16 parallel AND-OR terms per rank (§B.4) — a structural modification to existing decode logic, not merely a new control bit.
- **`timing_reg_file` Params list**: add `T_CKSRE`, `T_CKSRX`.
- **Config Registers table**: no addition required for Power Management in this revision (`PD_FORCE_EXIT_ON_REF` from v1.9.9 is retracted — see §B.8/§B.12-5).
- **Block List (Handoff §5)**: Maintenance Engine entry gains "+ CKE Mux", ME sub-FSM 5 description gains "N_RANKS instances (corrected)".

---

# SECTION C — Cross-Feature Integration Notes

## C.1 Consolidated Stage-0 Priority Order (final)

```
ref_urgent > ref_due > rfm_req > zq_due > mr_access_req
```

Unchanged from v1.9.8 except for the new `mr_access_req` tier at the bottom (§A.7). PD/SR transitions are **not** part of this list — they are not Stage-0 override commands; they're gate state changes that block Scheduler selection (`gate_pwr`) the same way `gate_rfc`/`gate_zq` already do, driven independently by Power Mgmt FSM's own trigger conditions rather than competing for the override lane. This is the correct model: PD/SR entry/exit commands (`PD_ENTRY`/`PD_EXIT`/`SR_ENTRY`/`SR_EXIT`) still travel through the `me_cmd_*` → Stage 4 path like every other ME command, but their _triggers_ aren't part of the same-cycle Stage-0 priority contest, since they're driven by idle/external conditions rather than a due/urgent deadline. (REF's unconditional pre-emption of `POWER_DOWN`, §B.8/§B.12-5, is the one place these two models touch — it is a fixed rule, not a CSR-mediated one.)

## C.2 `me_cmd_type` Width

Existing 3-bit (`[2:0]`) encoding already carries REFab, REFsb, ZQCAL (start/latch), RFM, and MRR — five to seven values depending on sub-state encoding, close to the 8-value ceiling. This addendum adds `MRW`, `PD_ENTRY`, `PD_EXIT`, `SR_ENTRY`, `SR_EXIT` — five more. **Required change**: widen `me_cmd_type` from `[2:0]` to `[3:0]` throughout (Scheduler Stage 4 input, Maintenance Engine outputs for all six — now seven — sub-FSMs that drive it). This is a pure width bump with no semantic change to any existing encoding value; it is the only place in this addendum where an existing port's width changes.

## C.3 Summary of All New Cross-Block Signals

|Signal|Source|Sink|Purpose|
|---|---|---|---|
|`mr_write_req`|MR_Write FSM|Stage 0|MRW arbitration|
|`gate_mr[N_RANKS]`|MR_Write FSM|Scheduler S2|Block rank during MRW/verify|
|`timing_apply_en`|MR_Write FSM|`timing_reg_file`|Atomic single-entry shadow→live commit|
|`mrr_requester`|Read Data Path sideband (existing path, new field)|MR_Poll FSM, MR_Write FSM|Tags which FSM an MRR response belongs to|
|`mrr_slot_req_poll` / `mrr_slot_req_write`|MR_Poll FSM / MR_Write FSM|MR Read Arbiter|Request the shared MRR issue slot|
|`mrr_slot_grant_poll` / `mrr_slot_grant_write`|MR Read Arbiter|MR_Poll FSM / MR_Write FSM|Mutually exclusive grant, fixed priority write > poll|
|`dfi_cke[N_RANKS]`|Init FSM / Power Mgmt FSM (muxed)|PHY|Power state signaling|
|`gate_pwr[N_RANKS]`|Power Mgmt FSM|Scheduler S2, MR_Write FSM|Block rank during PD/SR|
|`bank_fsm_broadcast_en/rank/state`|Power Mgmt FSM (via `me_cmd_*`)|Stage 4 → Per-Bank FSM Table|Rank-wide bank state update|

## C.4 What Remains Genuinely Open

Consistent with the research phase, this addendum intentionally does **not** resolve:

- **TCAM entries carrying no explicit rank field** (noted during research as a related but separate gap) — this addendum's PD auto-wake logic (§B.7) relies on `bank_act_count[r][*]`, which is already rank-indexed independent of TCAM entry format, so it doesn't need that gap closed to work correctly, but the gap itself is unresolved and out of scope here.
- **Per-DRAM (per-rank) mode register read-back timing model beyond `T_MRD`** — real DDR5 has additional spacing requirements (`tMOD`, `tCCD`-adjacent constraints) between certain MR writes and subsequent commands depending on which register is touched; this addendum uses the single existing `T_MRD` parameter uniformly, which is conservative but not necessarily optimal for every register. Left as a future refinement, not a correctness gap.