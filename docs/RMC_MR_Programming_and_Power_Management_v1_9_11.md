# RMC — Architecture Specification v1.9.11
## Mode Register Programming, Power Management & MC-Core Register Interface

---

## 0. Status of This Document

This document supersedes `RMC_MR_Programming_and_Power_Management_v1_9_10.md` for the two
features it covers, and adds a consolidated MC-Core register interface section. It is written
as a specification, not a changelog; obsolete mechanisms are removed rather than retained as
legacy alternatives.

Ground truth for everything in this document is: `architecture_reference.md`,
`RMC_Handoff_v1.9.8.md`, `RMC_Full_Knowledge_v1.9.8.md` (the v1.9.8 baseline), and the finalized
external-review decisions for Runtime Mode Register Programming and Power Management. Where the
ground truth does not define something, this document says so explicitly (`OPEN/TBD`) rather
than filling in a plausible value — this applies throughout, including in the register tables.

As with v1.9.10, both Mode Register Programming and Power Management are handled inside the
**Maintenance Engine (ME)**. ME remains a peer to the Scheduler, writes into FSM tables directly
for maintenance events, and never issues CAS. Both features route their DRAM-facing commands
through the existing **Stage-0 override → Stage-4 emission** path — no new command path is
introduced into the Scheduler.

---

# SECTION A — Mode Register Programming

**Scope assumption, carried forward from prior analysis:** the v1.9.8 ground-truth documents
specify only two MR-related capabilities — boot-time `MRW_BURST` (Init FSM) and periodic
MR4/TUF read polling (MR_Poll FSM). No runtime mode-register **write** requirement is stated
anywhere in the ground truth. This section remains an inferred extension, adopted on the
reading that "Mode Register Programming" is one of the two features explicitly called out as
unfinished. If runtime MR write was not intended to be in scope, this section should be dropped
in full and MR_Poll requires no changes at all.

## A.1 Design Goals

1. Preserve the existing boot-time `MRW_BURST` behavior in Init FSM exactly as documented —
   zero changes to Init FSM.
2. Add a **runtime** mode-register write capability, since the architecture currently has no
   way to reprogram a DRAM mode register after `init_done`.
3. Keep the mechanism a **slow, deliberate, software-triggered control-plane operation** — no
   queue, no pipelining, no performance requirement.
4. Provide software with the primitives it needs to keep `timing_reg_file` consistent with the
   DRAM's actual programmed state for any timing-affecting mode register write. This is **not**
   a hardware-enforced guarantee — see the design decision in §A.4. Hardware's obligation is
   limited to reporting, accurately, whether a requested MR write reached the DRAM and (if
   verification was requested) whether it took the intended value; sequencing the corresponding
   `timing_reg_file` update correctly is software's responsibility.
5. Reuse the existing MRR Read Data Path sideband for read-back. A minimal shared `mrr_busy`
   interlock serializes MRR requests from MR_Poll and MR_Write verification; it is not an MR
   Read Arbiter and adds no requester identity or response-routing mechanism.

## A.2 Functional Overview

A new ME sub-FSM, **MR_Write FSM**, accepts a single outstanding software-issued mode-register
write request via CSR, waits for the target rank to be in a safe state, issues the MRW through
the existing Stage-0/Stage-4 override path, and — if requested — reads it back for verification
over the existing MRR sideband path, using it directly rather than through any intermediary.

Updating `timing_reg_file` for a timing-affecting mode register is **entirely a software
responsibility**, performed as a second, independent CSR transaction after MR_Write FSM reports
success — see §A.4 for the exact sequence. There is no hardware path from MR_Write FSM to
`timing_reg_file`.

Except for its participation in the shared `mrr_busy` interlock, MR_Poll (MR4/TUF polling) is
unmodified by this section. Its state machine, poll interval, TUF parsing, tREFI-adjustment
logic, and use of the MRR sideband path otherwise remain exactly as documented in v1.9.8.
MR_Write FSM is a new peer sub-FSM, not a restructuring of MR_Poll — the two remain functionally
distinct (periodic read vs. on-demand write), consistent with the existing one-concern-per-
sub-FSM pattern (Refresh / ZQcal / RFM / PwrMgmt / MR_Poll are all separate for the same reason).

MR_Poll itself is locally serialized: after `REQUEST_MRR` it waits in `WAIT_RDDATA` before it
can poll again. It may issue `REQUEST_MRR` only when shared `mrr_busy==0`; issuing the request
asserts `mrr_busy`, and consuming its sideband response clears it. Its documented request interface is `me_cmd_valid`, `me_cmd_type=MRR`,
`me_cmd_mr=4`, and `me_cmd_rank`, with `sched_ack` as the issue acknowledgement. Its documented
return is the Read Data Path sideband `mrr_data_valid`/`mrr_data`/`mrr_rank`, not the response
FIFO. This is the complete baseline model.

The shared `mrr_busy` interlock creates one global outstanding-MRR limit across MR_Poll and
MR_Write verification. When either FSM issues an MRR, it asserts `mrr_busy`; while it is set,
the other FSM cannot issue an MRR. The issuing FSM consumes the resulting sideband response and
clears `mrr_busy`. Consequently, its `WAIT_RDDATA` state owns the only outstanding response;
`mrr_rank` remains available as existing response information but is not used for routing.
This is a minimal interlock, not an MR Read Arbiter: there are no requester IDs, response tags,
response routing, or arbiter block.

## A.3 MR_Write FSM (ME Sub-FSM 7)

```
IDLE → WAIT_REQ → GATE_CHECK → ISSUE_MRW → WAIT_tMRD →
  [VERIFY_MRR → WAIT_RDDATA → CHECK_MATCH] (optional, MR_WR_VERIFY=1) →
DONE → IDLE
```

9 states total. `VERIFY_MRR`/`WAIT_RDDATA`/`CHECK_MATCH` are conditionally bypassed when
`MR_WR_VERIFY=0` — no separate state is needed for the skip.

- **WAIT_REQ**: idle until `MR_WR_REQ` (CSR pulse) is seen. Latches `MR_WR_ADDR`, `MR_WR_DATA`,
  `MR_WR_RANK`, `MR_WR_VERIFY`, `MR_WR_REQUIRE_IDLE` into internal request registers. Asserts
  `MR_WR_BUSY`.
- **GATE_CHECK**: waits until `gate_pwr[MR_WR_RANK]==0` (rank not in power-down/self-refresh —
  see §B) and, if `MR_WR_REQUIRE_IDLE=1`, until `bank_act_count[MR_WR_RANK][*]==0` for all 16
  banks. No forced eviction of in-flight traffic is performed — this is a bounded wait, not an
  override of Scheduler activity.
  **Rationale for `MR_WR_REQUIRE_IDLE` as a per-request software field, not a fixed hardware
  policy:** different DDR5 mode registers have genuinely different safety requirements —
  registers that only affect status/monitoring behavior are typically safe to write with the
  rank active, while registers affecting latency, drive strength, or other timing-adjacent
  behavior generally require full rank quiescence. RMC has no built-in knowledge of what a
  given `MR_WR_ADDR` value means in DDR5 terms; only software, which knows the target
  register's semantics, is in a position to decide this correctly per write.
- **ISSUE_MRW**: emits an MRW through the existing Stage-0 → Stage-4 command path. The baseline
  establishes the ME command channel (`me_cmd_valid/type/rank`) and `sched_ack`, but defines no
  runtime-MRW request line or MRW address/data carriage. Those additions are required interface
  work for this inferred feature; this document does not name an unverified request signal.
- **WAIT_tMRD**: holds `gate_mr[rank]=1` for `T_MRD` cycles (existing `timing_reg_file` param).
- **VERIFY_MRR** (optional): waits for `mrr_busy==0`, then requests an MRR to the just-written
  register and asserts `mrr_busy` when that MRR is issued. It must not reuse a hypothetical MRW
  request signal by assumption — no such reuse is documented in the baseline.
- **WAIT_RDDATA**: consumes the existing sideband response for this verification and clears
  `mrr_busy`. Mutual exclusion guarantees that this is the only outstanding MRR; no response
  routing is required.
- **CHECK_MATCH**: compares `mrr_data` to `MR_WR_DATA`, asserts the 1-bit `MR_WR_ERROR`
  verification-mismatch status on mismatch. No timeout or other error class is implied.
- **DONE**: clears `gate_mr[rank]`, sets `MR_WR_DONE`, clears `MR_WR_BUSY`.

## A.4 Datapaths / Control Paths

**MR write command path**: `MR_Write FSM → Stage 0 → Stage 4 →
dfi_address/dfi_cs_n/dfi_act_n/dfi_wrdata/dfi_wrdata_en`. The physical DFI output path is
existing, but the runtime-MRW request/address/data interface into it is not defined by the
baseline and remains an explicit extension required before RTL.

**MR read-back path**: Read Data Path sideband → `mrr_data_valid`/`mrr_data`/`mrr_rank`.
MR_Poll and MR_Write verification share it through `mrr_busy`: an FSM asserts the interlock when
it issues an MRR and clears it when it consumes that MRR's response. The other FSM cannot issue
while it is set, so no same-rank response routing is needed.

**Timing update path — software-sequenced, no hardware mechanism:**
```
1. Software: `MR_WR_REQ`  →  MR_Write FSM programs the DRAM mode register
2. Software polls `MR_WR_BUSY` until 0, then checks `MR_WR_ERROR`
3. Only if `MR_WR_ERROR==0`: software performs an ordinary, separate CSR write —
   csr_wr_en / csr_param_id / csr_param_val  →  timing_reg_file
   (the same direct-write interface `timing_reg_file` has always had; nothing is added to it
   for this purpose)
```
There is no signal, register, or datapath connecting MR_Write FSM to `timing_reg_file`. Step 3
is a plain CSR write, indistinguishable in hardware from any other runtime write to
`timing_reg_file`. The correctness of the overall sequence — that step 3 only happens after
step 2 confirms success — is enforced entirely by software discipline, not by hardware. This is
a deliberate architectural decision from the finalized review: hardware should not implement a
software responsibility, and no MR_Write interlock hardware is introduced to backstop it. See
§A.1 Goal 4 and §E for the consequence of this decision.

## A.5 FSM State Table

| State | Purpose | Exit condition |
|---|---|---|
| IDLE | Wait for boot to complete | `init_done==1` |
| WAIT_REQ | Wait for software request | `MR_WR_REQ` pulse |
| GATE_CHECK | Wait for safe rank state | `gate_pwr[r]==0` AND (`!MR_WR_REQUIRE_IDLE` OR `bank_act_count[r][*]==0`) |
| ISSUE_MRW | Win Stage-0 arbitration, command emitted | `sched_ack` |
| WAIT_tMRD | Command spacing | `gc >= issue_gc + T_MRD` |
| VERIFY_MRR | Wait for `mrr_busy==0`, then request read-back | MRR issued; assert `mrr_busy` |
| WAIT_RDDATA | Wait for this MRR's sideband return | Consume response; clear `mrr_busy` |
| CHECK_MATCH | Compare read-back to written value | always (1 cycle) |
| DONE | Report completion, clear gates | always (1 cycle) → IDLE |

## A.6 State Ownership

| Item | Owner (R/W) | Others |
|---|---|---|
| MR_Write FSM internal state | MR_Write FSM | — |
| `timing_reg_file` (all params) | CSR (existing, unchanged) | READ ONLY: all consuming blocks (§D.3) |
| `gate_mr[rank]` | MR_Write FSM | READ ONLY: Scheduler Stage 2 |
| `MR_WR_BUSY` / `MR_WR_DONE` / `MR_WR_ERROR` | MR_Write FSM | READ ONLY: CSR/software |

Every register has exactly one hardware writer. `timing_reg_file` is written only by the
pre-existing CSR interface — MR_Write FSM is not a writer of it, directly or indirectly.

## A.7 Scheduler Interaction

- `gate_mr[rank]` — added to the Legal Check Matrix (Stage 2 gate inputs), same shape as
  `gate_rfc`/`gate_zq`. It blocks per-bank commands to the rank during an MR_Write sequence.
- MR_Write is a peer ME sub-FSM, but its exact runtime-MRW Stage-0 request/arbitration contract
  remains OPEN (§E). The baseline Stage-0 priority is `ref_urgent > ref_due > rfm_req > zq_due`;
  it documents that MR_Poll bypasses Stage 1–3, but does not define MR_Poll's Stage-0 request
  input or priority. A runtime MRW/verification request and its relationship to that poll are
  therefore not frozen.

No changes to Stage 1–3 logic, TCAM, status registers, or watermark managers.

## A.8 Maintenance Engine Interaction

MR_Write is a peer to the other 6 ME sub-FSMs. Its exact runtime-MRW Stage-0 request/arbitration
contract remains OPEN (§E); peer status does not define that unresolved interface. It depends on
Power Management (§B): `GATE_CHECK` cannot proceed while `gate_pwr[r]==1`. This is a read-only
dependency — MR_Write never writes Power Mgmt FSM state.

MR_Write and MR_Poll are independent FSMs, with a shared `mrr_busy` interlock only for MRRs.
It permits exactly one outstanding MRR across both FSMs: the issuer asserts it on issue and
clears it upon consuming the response. It does not otherwise arbitrate requests or route
responses.

## A.9 New Interfaces / Signals

```
MR_Write FSM
→ init_done, gc, T_MRD (from timing_reg_file), gate_pwr[N_RANKS], bank_act_count[N_RANKS][16]
→ mrr_data_valid, mrr_data[7:0], mrr_rank        (existing sideband, unmodified)
↔ mrr_busy                                      (shared MR_Poll/MR_Write MRR interlock)
→ CSR: MR_WR_REQ, MR_WR_ADDR[5:0], MR_WR_DATA[7:0], MR_WR_RANK[RANK_BITS-1:0],
       MR_WR_REQUIRE_IDLE, MR_WR_VERIFY

← me_cmd_valid/type/rank   (existing ME command channel; MRW encoding/interface extension OPEN)
← gate_mr[N_RANKS]         → Scheduler Stage 2 (new gate)
← MR_WR_BUSY, MR_WR_DONE, MR_WR_ERROR   (CSR status, RO)
```

No signal exists between MR_Write FSM and `timing_reg_file`. The runtime-MRW request/address/
data interface remains unresolved; `mrr_busy` is the only new shared MRR control and is not an
arbitration block.

## A.10 CSR Requirements

See §D.2 for the full consolidated register table with widths, access types, and defaults.
Summary of the fields introduced by this section: `MR_WR_REQ`, `MR_WR_ADDR`, `MR_WR_DATA`,
`MR_WR_RANK`, `MR_WR_REQUIRE_IDLE`, `MR_WR_VERIFY`, `MR_WR_BUSY`, `MR_WR_DONE`, `MR_WR_ERROR`.

`MR_WR_AFFECTS_TIMING` is removed from the RMC hardware and CSR architecture. Whether a mode
register affects timing is software/driver knowledge; RMC has no corresponding field, signal, or
hardware consumer.

## A.11 Timing Considerations

- `T_MRD` (existing `timing_reg_file` param) governs command spacing after MRW — reused
  directly, no new timing parameter needed.
- The software-sequenced `timing_reg_file` update (§A.4) adds no hardware timing consideration
  beyond the existing CSR write path's — it's an ordinary register write.
- `GATE_CHECK` has no timeout. This is an intentional baseline position, not an omission: no
  other gate in this architecture (`gate_rfc`, `gate_zq`, `gate_pwr`) has a documented watchdog
  either, so timeout detection is left as an optional, implementation-specific addition.

## A.12 Architectural Invariants

1. **Init FSM behavior is unchanged.** MR_Write FSM only becomes reachable after `init_done`.
2. **`timing_reg_file` is written only by its existing CSR interface.** MR_Write FSM has no
   write path to it, direct or indirect. Any consistency between a DRAM-side MR value and the
   corresponding `timing_reg_file` entry is a software-maintained property, not a
   hardware-enforced one (§A.4).
3. **At most one MR write is outstanding at a time.** No queue exists; a second `MR_WR_REQ`
   while `MR_WR_BUSY==1` is ignored (software must poll `MR_WR_BUSY`).
4. **`gate_mr[rank]` and `gate_pwr[rank]` are mutually exclusive by construction** — `GATE_CHECK`
   will not enter `ISSUE_MRW` while `gate_pwr` is set, and Power Mgmt will not enter PD or SR
   while `gate_mr` is set, so the two gates are never asserted for the same rank simultaneously.
5. **At most one MRR is outstanding across MR_Poll and MR_Write.** The issuing FSM asserts
   `mrr_busy`; the other cannot issue while it is set; the issuing FSM clears it only when it
   consumes the outstanding response. This is mutual exclusion, not response routing.

## A.13 Corner Cases

- **Target rank enters self-refresh while an MR write is in `WAIT_REQ`/`GATE_CHECK`.** Since SR
  exit is externally controlled (`sr_exit`, §B), `GATE_CHECK` can stall indefinitely. Accepted
  trade-off, not a bug — software is expected not to schedule MR writes to a rank it knows is
  (or may soon be) in self-refresh. No hardware timeout exists (§A.11).
- **MR write targets a rank in power-down (not self-refresh).** Power-down exits automatically
  the moment real traffic arrives (§B.7). Whether a pending MR_Write request also forces PDX is
  part of the unresolved runtime-MRW request contract (§E); no baseline request signal defines
  that behavior.
- **`MR_WR_VERIFY=1` and the read-back mismatches.** `MR_WR_ERROR` is set; the FSM still
  completes to `DONE` — it does not retry automatically. Per the software sequence in §A.4,
  software must check `MR_WR_ERROR==0` before performing the corresponding `timing_reg_file`
  write; if it doesn't, nothing in hardware stops the write from happening anyway.
- **Software omits `MR_WR_VERIFY` on a timing-sensitive write.** This is permitted: verification
  is an optional software-controlled request, and RMC does not infer timing significance from
  `MR_WR_ADDR` or make verification mandatory. `MR_WR_DONE` then reports command completion after
  `T_MRD`, without read-back confirmation; software remains responsible for requesting verification
  when required.
- **MR_Poll's periodic poll and MR_Write's `VERIFY_MRR` become due at overlapping times.**
  Whichever issues first asserts `mrr_busy`; the other remains in its existing request state
  until the response is consumed and `mrr_busy` clears.

## A.14 Assumptions

- DDR5 mode registers are addressed with a 6-bit register number and carry an 8-bit payload,
  matching the width already implied by the existing `mrr_data[7:0]` port.
- Software is responsible for knowing which mode registers are timing-affecting, for computing
  the correct new `timing_reg_file` value, and for sequencing the two-step write (§A.4)
  correctly — RMC does not derive nCK values from MR encodings and does not enforce the
  sequencing.
- `MR_WR_VERIFY` is an optional software-controlled request. Software decides when verification
  is required, including for timing-sensitive MR writes; RMC does not infer this from the MR
  address or impose a mandatory verification policy.
- Software will not issue an MR write to a rank it knows to be in self-refresh.

## A.15 Required Updates to Existing Tables

- **FSM Inventory / FSM Count Summary**: add row `MR_Write FSM | 9 | 1 | ME sub-FSM 7`.
- **`me_cmd_type` enum/width**: define one authoritative maintenance-command enum before
  assigning a width or adding MRW/PD/SR command forms (§C.2, §E).
- **Legal Check Matrix**: add row `gate_mr[r] | MR_Write FSM | MR_Write sequence in progress`.
- **Config Registers**: see §D.2 for the consolidated table.
- **Block List (Handoff §5)**: ME entry gains "+ MR_Write FSM (7th sub-FSM)". MR_Poll FSM's
  entry is unchanged — no modification to it is required by this version.

---

# SECTION B — Power Management

This section preserves the repository-supported baseline behavior while resolving the documented
PD-idle consumer and Self-Refresh-exit sequencing decisions; remaining register-model conflicts
are identified explicitly.

## B.1 Design Goals

1. Preserve the existing two-branch (PD/SR) Power Mgmt FSM structure, adding the explicitly
   required Self-Refresh exit timing stages rather than otherwise redesigning it.
2. Resolve the rank-vs-bank state granularity gap: entering/exiting PD or SR at the rank level
   must be visible at the bank level too, since the Per-Bank FSM Table already has
   `POWER_DOWN`/`SELF_REFRESH` encodings that nothing currently drives.
3. Give the Scheduler an actual way to know a rank is unavailable — the documented Legal Check
   Matrix has `gate_rfc`/`gate_zq` but nothing for PD/SR.
4. Give the PHY an actual way to know to power down — no `dfi_cke` (or equivalent) port exists
   anywhere in the current I/O map.
5. Preserve the documented distinction that PD is autonomous/idle-triggered (`pd_en` + idle
   detection) while SR is externally directed (`sr_entry`/`sr_exit` "system signal").
6. Correctly interleave power management with refresh (must still happen — DRAM handles it
   internally during SR but not during PD) and mode-register writes (Section A).

## B.2 Functional Overview

Power Mgmt FSM gains: (a) a matching per-instance-per-rank replication so multi-rank configs
don't serialize unrelated ranks' power transitions through one shared FSM, (b) a broadcast
write path so entering/exiting PD or SR at the rank level correctly updates all 16 banks in
that rank's Per-Bank FSM Table row set, (c) a new `gate_pwr[rank]` output consumed by Scheduler
Stage 2, and (d) a new `dfi_cke[N_RANKS-1:0]` output, driven through a small dedicated mux
inside the ME that hands ownership from Init FSM (during boot) to Power Mgmt FSM (after
`init_done`) — structurally parallel to, but separate from, the existing DFI command mux,
because CKE is a continuously-driven level signal, not a per-command field.

## B.3 Block Responsibilities (Power Mgmt FSM, completed)

| Responsibility | Existing? | This addendum |
|---|---|---|
| PD entry decision (`bank_act_count==0`, `pd_en`, no pending maintenance) | Yes | Add continuous `PD_IDLE_THRESHOLD` dwell requirement |
| SR entry/exit decision | Yes (external signal) | unchanged |
| Drive `me_cmd_*` for PD/SR transitions | Implied, unwired | Proposed command forms; exact enum/encoding OPEN (§C.2) |
| Update Per-Rank FSM Table state/`next_xp`/`next_xs` | Yes | unchanged |
| Update Per-Bank FSM Table state (all 16 banks) | No — gap | New: broadcast write, §B.4 |
| Signal Scheduler to stop targeting the rank | No — gap | New: `gate_pwr[rank]`, §B.7 |
| Drive DFI-level power signaling | No — gap | New: `dfi_cke[N_RANKS-1:0]`, §B.4 |
| Coordinate with Refresh FSM during SR | No — gap | New: credit freeze, §B.8 |
| Coordinate with Refresh FSM during PD | No — gap | New: REF-forces-PDX, §B.8 (fixed invariant) |

## B.4 New Datapaths / Control Paths

**Broadcast bank-state write** (sourced from Stage 4 on an ME-originated PD/SR command,
preserving the rule that Stage 4 remains the sole writer of the Per-Bank FSM Table):
```
Power Mgmt FSM → me_cmd_valid, `me_cmd_type` = defined PD/SR command form, me_cmd_rank
                                    │
                                    ▼
Stage 4 recognizes a rank-scoped (not bank-scoped) ME command and asserts:
  bank_fsm_broadcast_en, bank_fsm_broadcast_rank[RANK_BITS-1:0], bank_fsm_broadcast_state[2:0]
                                    │
                                    ▼
All 16 Per-Bank FSM Table rows where row.rank == bank_fsm_broadcast_rank update `state`
in the same cycle.
```
The existing Per-Bank FSM Table write path is a **one-hot decoder**: exactly one row's
write-enable is active per cycle. Supporting the broadcast case requires widening it to **16
independent write-enable terms**, each computed as `(bank_fsm_broadcast_en AND row.rank ==
bank_fsm_broadcast_rank) OR (existing single-row select for that row)`. This is the one place
in this architecture where existing Stage 4 decode logic is structurally modified rather than
merely extended.

**CKE Mux** (inside ME, parallel to the existing DFI Output Mux):
```
init_done==0  →  Init FSM drives dfi_cke[N_RANKS-1:0]
init_done==1  →  Power Mgmt FSM drives dfi_cke[N_RANKS-1:0]
```
Same one-way-latch gating as the existing DFI mux; no third owner.

## B.5 FSM State Table (12 states, completed)

| State | Branch | Entry condition | Exit condition | New wiring added |
|---|---|---|---|---|
| NORMAL | both | — | PD or SR entry condition | — |
| PD_ENTRY_CHECK | PD | `all bank_act_count[r][*]==0 AND pd_en AND no pending maintenance AND gate_mr[r]==0` | proceed only after the relevant banks have remained idle continuously for `PD_IDLE_THRESHOLD` cycles and `gate_mr[r]==0` | Activity during the dwell period resets the dwell counter |
| PRECHARGE_PD | PD | — | (all banks already precharged by entry check) | `dfi_cke[r]←0`; broadcast `POWER_DOWN` |
| ACTIVE_PD | PD | reserved, unreachable given current entry gate | — | — |
| PDX_WAIT | PD | wake trigger (§B.7) | `gc >= exit_gc + T_XP` | `dfi_cke[r]←1`; broadcast `IDLE` |
| SR_ENTRY | SR | `sr_entry AND gate_mr[r]==0` | proceed | `dfi_cke[r]←0` |
| WAIT_tCKSRE | SR | — | `T_CKSRE` elapsed | — |
| SELF_REFRESHING | SR | — | `sr_exit` | broadcast `SELF_REFRESH` |
| SR_EXIT | SR | `sr_exit` | proceed | `dfi_cke[r]←1` |
| WAIT_tCKSRX | SR | — | `T_CKSRX` elapsed | — |
| WAIT_tXS | SR | — | `T_XS` elapsed after `WAIT_tCKSRX` | — |
| WAIT_tDLLK | SR | — | `T_DLLK` elapsed after `WAIT_tXS` | broadcast `IDLE` on completion |

`ACTIVE_PD` is carried forward from the existing documented state list, unreachable under the
current PD entry gate (which requires full rank idle). Left in place rather than removed —
flagged in §B.14, not resolved here.

`PD_IDLE_THRESHOLD` is consumed by Power Mgmt FSM as the autonomous PD-entry dwell interval.
This architectural decision resolves the previously undocumented CSR consumer; it adds no PM
state because the dwell counter is evaluated within the existing `PD_ENTRY_CHECK` path.

## B.6 State Ownership

| Item | Owner (R/W) | Others |
|---|---|---|
| Per-Rank FSM Table (state, `next_xp`, `next_xs`, `can_xp`, `can_xs`) | Power Mgmt FSM | READ ONLY: Scheduler S0 |
| Per-Bank FSM Table `state` field, PD/SR values only | Stage 4 (broadcast write, ME-sourced) | READ ONLY: Scheduler S2 |
| `dfi_cke[]` | Init FSM (boot) / Power Mgmt FSM (runtime), mutually exclusive via `init_done` | — |
| `gate_pwr[rank]` | Power Mgmt FSM | READ ONLY: Scheduler S2, MR_Write FSM (§A.8) |

## B.7 Scheduler Interaction

| Gate | Source | Constraint |
|---|---|---|
| `gate_pwr[r]` | Per-rank, Power Mgmt FSM | Rank is in `POWER_DOWN` or `SELF_REFRESH` — PD and SR share one gate |

**Automatic PD wake**: Power Mgmt FSM already has `bank_act_count[N_RANKS][16]` as an input.
The moment any bank's `bank_act_count` for a gated-PD rank goes non-zero (a new TCAM allocation
targeting that rank), `PDX_WAIT` is triggered automatically. No new signal is required.

This transition only *triggers entry into* `PDX_WAIT` — it does not itself permit command
issue. `gate_pwr[r]` remains asserted for the entire `PDX_WAIT` duration and only clears once
`T_XP` has elapsed and `dfi_cke[r]` has been reasserted. TCAM allocation for a PD-gated rank is
intentional, not a gap: allocation is unaffected by `gate_pwr` by design — the same
allocate-then-gate model already used for REF and ZQ elsewhere in this architecture.

**SR does not auto-wake on traffic.** New requests to an SR-gated rank queue normally in
WR_TCAM/RD_TCAM (allocation unaffected) and wait for `sr_exit`. Pre-existing design choice,
preserved — see §B.13 for the starvation-interaction note this implies.

## B.8 Maintenance Engine Interaction

1. **Refresh vs. Power-Down**: `ref_urgent`/`ref_due` targeting a rank with `gate_pwr[r]==1`
   due to `POWER_DOWN` (not `SELF_REFRESH`) **unconditionally** forces `PDX_WAIT` before the
   refresh command can be issued — real DRAM cannot receive a REF command while CKE is low, and
   there is no legitimate configuration in which delaying refresh in favor of staying in
   power-down is preferable to a data-retention risk. This is a fixed architectural invariant
   (§B.12-5), **not a configurable policy** — there is no `PD_FORCE_EXIT_ON_REF` CSR or
   equivalent, and none should be reintroduced.
2. **Refresh vs. Self-Refresh**: while `gate_pwr[r]==1` due to `SELF_REFRESH`, the Refresh
   FSM's leaky-bucket `ref_credits[r]` counter is **frozen** (neither incremented nor
   decremented) rather than continuing to accumulate. Real DRAM refreshes itself internally
   during self-refresh; freezing avoids a burst of forced refreshes immediately after
   `sr_exit`. `ref_credits[r]` resumes counting from wherever it was the instant `gate_pwr[r]`
   clears.

These are the only changes to Refresh FSM behavior in this document; its internal state
machine, targeting policy, and watchdog logic are otherwise untouched.

## B.9 New Interfaces / Signals

```
Power Mgmt FSM
← dfi_cke[N_RANKS-1:0]         → PHY, via CKE mux (§B.4)
← gate_pwr[N_RANKS-1:0]        → Scheduler Stage 2, MR_Write FSM
← bank_fsm_broadcast_en        → Stage 4
← bank_fsm_broadcast_rank      [RANK_BITS-1:0]
← bank_fsm_broadcast_state     [2:0]

Refresh FSM
→ gate_pwr[N_RANKS-1:0]        (freezes ref_credits during SR; unconditionally forces PDX_WAIT
                                 before issuing REF to a POWER_DOWN-gated rank, per invariant
                                 B.12-5 — no CSR involved)
```

`me_cmd_type` must be reconciled against one authoritative maintenance-command enum before MRW
or PD/SR command forms are assigned encodings (§C.2, §E).

## B.10 CSR Requirements

`pd_en` is an existing 1-bit CSR input to Power Mgmt FSM. `PD_IDLE_THRESHOLD` is consumed by
Power Mgmt FSM: autonomous PD entry requires the relevant banks to remain idle continuously for
that many cycles, in addition to `pd_en` and no pending maintenance; activity resets the dwell
counter. This resolves its previously undocumented consumer. `sr_entry` and `sr_exit` are system
signals, not CSRs. `T_XP`, `T_XS`, and `T_DLLK` are existing `timing_reg_file`
parameters. `T_CKSRE`/`T_CKSRX` require reconciliation before they are added to that file (§D.3,
§E). There is no `PD_FORCE_EXIT_ON_REF` CSR — that rule is a fixed invariant (§B.8, §B.12-5).

## B.11 Timing Considerations

- The authoritative Self-Refresh exit sequence is `SR_EXIT → WAIT_tCKSRX → WAIT_tXS →
  WAIT_tDLLK → NORMAL`: `T_CKSRX` stable clock time follows SRX, then `T_XS`, then `T_DLLK`
  for commands requiring locked DLL. `T_CKSRX` is therefore represented by its own explicit
  wait state and is neither folded into another delay nor combined with `T_XS`/`T_DLLK`.
- The exact `T_CKSRX` width and its membership in `timing_reg_file` remain OPEN because the
  repository's register-model definitions conflict (§D.3, §E).
- The broadcast bank-state write (§B.4) is single-cycle regardless of rank width.
- `dfi_cke` mux switching is combinational on `init_done`, matching the existing DFI mux's
  timing model.

## B.12 Architectural Invariants

1. **A rank's Per-Bank FSM Table rows and its Per-Rank FSM Table row report the same power
   state at all times** — enforced structurally by the broadcast write always accompanying the
   rank-level `rank_state_update` in the same Stage-4 cycle.
2. **`gate_pwr[r]` is asserted for the entire PD or SR sojourn, not just entry/exit
   transitions** — matches `gate_rfc`/`gate_zq` behavior exactly.
3. **`dfi_cke` has exactly one owner at any time** (`init_done`-gated, never both).
4. **`ref_credits[r]` is monotonically frozen during `SELF_REFRESH`, never during
   `POWER_DOWN`**.
5. **REF unconditionally pre-empts `POWER_DOWN` — never `SELF_REFRESH`** (§B.8, rule 1). Fixed
   architectural rule, no CSR override.
6. **`gate_pwr[r]` and `gate_mr[r]` (§A) are never asserted for the same rank simultaneously:**
   Power Mgmt enters PD or SR only while `gate_mr[r]==0`, and MR_Write issues only while
   `gate_pwr[r]==0`.
7. **Self-Refresh exit waits are sequential.** `WAIT_tCKSRX` completes before `WAIT_tXS`, which
   completes before `WAIT_tDLLK`; `NORMAL` is not reached through a combined or maximum delay.

## B.13 Corner Cases

- **New request arrives for a rank in self-refresh.** Allocation proceeds normally, but Stage
  2/3 cannot select it while `gate_pwr[r]==1`. Since SR has no auto-wake, request age can grow
  past `RD_STARVATION_THR`/`WR_STARVATION_THR` without the staggered starvation mechanism being
  able to fire. Composes correctly with existing behavior (same as REFab/ZQcal gating);
  no new starvation-handling logic required.
- **PD entry check passes, then a request lands in the same cycle Stage 4 is committing the
  broadcast `POWER_DOWN` write.** `bank_act_count` incrementing and the broadcast write are
  both synchronous; the Watermark Manager's allocation completes before Stage 4 in a given
  pipeline cycle, so the auto-wake condition (§B.7) is visible the cycle after entry commits,
  correctly triggering `PDX_WAIT` the very next cycle.
- **Activity occurs during the autonomous PD dwell period.** The relevant rank's idle dwell
  counter resets; a fresh continuous `PD_IDLE_THRESHOLD` interval is required before PD entry.
- **`ACTIVE_PD` is unreachable** (§B.5) — not a corner case needing a fix, flagged so it isn't
  mistaken for a wiring bug.

## B.14 Assumptions

- Multi-rank power management is fully independent per rank.
- `ACTIVE_PD` is left as a defined-but-unreachable state, on the assumption a future revision
  may relax the PD entry gate to allow power-down with some banks still active.
- `sr_entry`/`sr_exit` remain system-level (outside RMC) signals.

## B.15 Required Updates to Existing Tables

- **FSM Count Summary**: `Power Mgmt FSM | 12 | 1 → N_RANKS | ME sub-FSM 5` — instance count
  corrected from 1 to `N_RANKS`, matching the ZQcal FSM precedent.
- **Legal Check Matrix**: add row `gate_pwr[r] | Power Mgmt FSM | PD or SELF_REFRESH in
  progress`.
- **Per-Bank FSM Table**: no field changes; the write-enable decoder is widened per §B.4.
- **`timing_reg_file` Params list**: reconcile `T_CKSRE`/`T_CKSRX` with the existing 5-bit
  MC-core specification and the 14-bit IO-map timing-file model before adding either entry.
- **Config Registers**: no `PD_FORCE_EXIT_ON_REF` — see §D.2.
- **Block List (Handoff §5)**: ME entry gains "+ CKE Mux"; ME sub-FSM 5 description gains
  "N_RANKS instances (corrected)".

---

# SECTION C — Cross-Feature Integration

## C.1 Consolidated Stage-0 Priority Order

```
ref_urgent > ref_due > rfm_req > zq_due
```
PD/SR transitions are **not** part of this list — they are gate state changes that block
Scheduler selection (`gate_pwr`) the same way `gate_rfc`/`gate_zq` already do, driven
independently by Power Mgmt FSM's own trigger conditions rather than competing for the override
lane. `PD_ENTRY`/`PD_EXIT`/`SR_ENTRY`/`SR_EXIT` commands still travel through the `me_cmd_*` →
Stage 4 path like every other ME command, but their triggers aren't part of the same-cycle
Stage-0 priority contest. REF's unconditional pre-emption of `POWER_DOWN` (§B.8/§B.12-5) is the
one place these two models touch — it is a fixed rule, not a CSR-mediated one.

## C.2 `me_cmd_type` Width

The IO map explicitly gives MR_Poll's `me_cmd_type` a 3-bit MRR encoding. It does not provide a
complete authoritative maintenance-command enum. Other scheduler documentation names more than
eight maintenance command forms. Therefore a width greater than three bits is strongly implied,
but the complete enum, encodings, and the precise width are OPEN. This document must not claim a
four-bit bump preserves existing encoding values until that enum is frozen.

## C.3 Summary of New Cross-Block Signals

| Signal | Source | Sink | Purpose |
|---|---|---|---|
| `gate_mr[N_RANKS]` | MR_Write FSM | Scheduler S2 | Block rank during MRW/verify |
| `dfi_cke[N_RANKS]` | Init FSM / Power Mgmt FSM (muxed) | PHY | Power state signaling |
| `gate_pwr[N_RANKS]` | Power Mgmt FSM | Scheduler S2, MR_Write FSM | Block rank during PD/SR |
| `bank_fsm_broadcast_en/rank/state` | Power Mgmt FSM (via `me_cmd_*`) | Stage 4 → Per-Bank FSM Table | Rank-wide bank state update |
| `mrr_busy` | MR_Poll / MR_Write (issuer and response consumer) | MR_Poll, MR_Write | Single-outstanding-MRR interlock; not an arbiter |

No MR_Write signal connects to `timing_reg_file`. The document defines no dedicated MRR
arbitration block: `mrr_busy` is only a shared mutual-exclusion interlock.

## C.4 What Remains Genuinely Open (Non-Register Items)

- **TCAM entries carrying no explicit rank field** — noted during research as a related but
  separate gap. PD auto-wake (§B.7) doesn't need it resolved to work correctly, but it remains
  unresolved and out of scope here.
- **Per-DRAM mode register read-back timing model beyond `T_MRD`** — real DDR5 has additional
  spacing requirements (`tMOD`, `tCCD`-adjacent constraints) between certain MR writes and
  subsequent commands depending on which register is touched; this document uses the single
  existing `T_MRD` parameter uniformly. Left as a future refinement.

(Register-related open items are consolidated in §E, not repeated here.)

---

# SECTION D — MC-Core Register Interface

## D.1 Scope and Method

This section consolidates the repository's documented MC-Core configuration/status inventory —
not only the registers introduced for MR Programming and Power Management. The Handoff's
"Config Registers (Key)" table is not exhaustive; timing-register-file entries and several
block-local configuration fields are defined elsewhere (§D.4). Where sources disagree, this
table records the conflict rather than selecting a convenient value.

Internal runtime state — WR/RD Status Reg fields, Per-Rank/Per-Bank FSM Table fields, `gate_*`
signals — is **not** included here; these are Scheduler/ME-owned hardware state, not
host-configurable registers, even though some sit adjacent to CSR-driven behavior.

## D.2 Consolidated Register Table

| Register | Purpose | Width | Access | Default | Owner | Category | Source |
|---|---|---|---|---|---|---|---|
| `WR_HIGH_WM` | WR drain entry watermark | OPEN | OPEN | 16 | Watermark Mgr (implied) | Baseline | Handoff §17 |
| `WR_LOW_WM` | WR drain exit watermark | OPEN | OPEN | 4 | Watermark Mgr (implied) | Baseline | Handoff §17 |
| `AGE_THR1` | Intra-class HOL bypass | OPEN | OPEN | 64 | Stage 2/3 | Baseline | Handoff §17 |
| `AGE_THR2` | Cross-class mode flip | OPEN | OPEN | 256 | Stage 2/3 | Baseline | Handoff §17 |
| `RD_STARVATION_THR` | RD miss forced service | OPEN | OPEN | 12480 (9×tREFI) | Stage 3 | Baseline | Handoff §17 |
| `WR_STARVATION_THR` | WR miss forced service | OPEN | OPEN | 37440 (3×RD) | Stage 3 | Baseline | Handoff §17 |
| `WINDOW_SIZE` | RD/WR partition rotation window | OPEN | OPEN | 2×tREFI | Bank Partition Ctrl | Baseline | Handoff §17 |
| `PAGE_POLICY` | Open/Closed/Adaptive page policy | 2b | OPEN | `00` (Open) | Scheduler | Baseline | Handoff §17; `mc_core_spec_v2.tex` |
| `REF_MODE` | REFab/REFsb/FGR-2x/FGR-4x select | `[1:0]` (explicit) | OPEN | `00` | Refresh FSM | Baseline | arch_ref, Refresh FSM ports |
| `MRR_POLL_INTERVAL` | MR4 TUF poll interval | OPEN | OPEN | 32×tREFI | MR_Poll FSM | Baseline | Handoff §17 |
| `PD_IDLE_THRESHOLD` | Continuous idle cycles before autonomous PD entry | OPEN | OPEN | 64 cycles | Power Mgmt FSM | Baseline | Handoff §17; resolved architectural consumer (§B.5/§B.10) |
| `FIFO_DEPTH` | Async FIFO depth / initial credit | OPEN | OPEN | 16 | — | Baseline | Handoff §17 |
| `INIT_KICK` | Trigger Init FSM | 1b (explicit) | OPEN (trigger-style) | 0 | Init FSM | Baseline | arch_ref §21 |
| `SOFT_RESET` | Sync soft-reset all FSMs | OPEN | OPEN (trigger-style) | 0 | Global | Baseline | Handoff §17 |
| `TRAIN_EN` | Enable training after `MRW_BURST` | 1b (explicit) | OPEN | OPEN | Init FSM | Baseline — **absent from Handoff §17** | arch_ref §21 only |
| `RAAIMT` | RFM: RAA Initial Max Threshold | `[7:0]` (explicit) | OPEN | OPEN | RFM FSM | Baseline — **absent from Handoff §17** | arch_ref, RFM FSM ports |
| `RAAMMT` | RFM: RAA Maximum Management Threshold | 8b | OPEN | OPEN | RFM-related logic OPEN | Baseline — **absent from Handoff §17** | `mc_core_spec_v2.tex` |
| `RAADec` | RAA decrement per REF | 4b | OPEN | OPEN | RFM FSM | Baseline — **absent from Handoff §17** | `mc_core_spec_v2.tex` |
| `pd_en` | Enable autonomous PD entry | 1b (explicit) | OPEN | OPEN | Power Mgmt FSM | Baseline — **absent from Handoff §17** | arch_ref, Power Mgmt FSM ports |
| `tZQCS_interval` | ZQCS issue interval | OPEN | OPEN | 128ms (converted to cycles) | ZQcal FSM | Baseline — **no formal ZQcal port** | Handoff §10; version control OQ-18 |
| `ZQCAL_TRIG` | Host-triggered ZQcal request | OPEN | Host write, exact semantics OPEN | OPEN | ZQcal FSM | Baseline — **absent from Handoff/IO map** | `mc_core_spec_v2.tex` |
| `CL`, `CWL` | DRAM read/write latency configuration | 7b each (legacy table) | OPEN | OPEN | Read/Write Data Path | Baseline — **not in IO-map timing file** | `rmc_knowledge_base.md` |
| `PHY_WRLAT`, `PHY_RDLAT`, `FREQ_RATIO` | DFI latency/frequency configuration | 6b, 6b, 2b (legacy table) | OPEN | OPEN | DFI data paths | Baseline — **formal CSR model incomplete** | `rmc_knowledge_base.md` |
| `MR_WR_REQ` | Pulse: request MR write | 1b (implied by "pulse"; not stated as a bit-width) | Pulse | 0 | MR_Write FSM | New — MR Programming | §A.10 |
| `MR_WR_ADDR` | Target mode register number | `[5:0]` (explicit) | RW | — | MR_Write FSM | New — MR Programming | §A.9/A.10 |
| `MR_WR_DATA` | Payload to write | `[7:0]` (explicit) | RW | — | MR_Write FSM | New — MR Programming | §A.9/A.10 |
| `MR_WR_RANK` | Target rank | `[RANK_BITS-1:0]` | RW | — | MR_Write FSM | New — MR Programming | §A.9/A.10; configuration profiles |
| `MR_WR_REQUIRE_IDLE` | Gate write on bank idle | 1b (implied) | RW | 1 | MR_Write FSM | New — MR Programming | §A.10 |
| `MR_WR_VERIFY` | Enable MRR read-back verify | 1b (implied) | RW | 0 | MR_Write FSM | New — MR Programming | §A.10 |
| `MR_WR_BUSY` | FSM executing a request | 1b (implied) | RO | — | MR_Write FSM | New — MR Programming | §A.10 |
| `MR_WR_DONE` | Last request completed | 1b (implied) | RO, auto-clears on next `MR_WR_REQ` — **not a standard W1C** | — | MR_Write FSM | New — MR Programming | §A.10 |
| `MR_WR_ERROR` | Verification mismatch (`mrr_data != MR_WR_DATA`) | 1b | RO | — | MR_Write FSM | New — MR Programming | §A.3/A.13 |
| `T_CKSRE` | SR-entry clock-stable cycles | **CONFLICT:** 5b legacy register vs. proposed 14b timing-file entry | OPEN | OPEN | Power Mgmt FSM | Baseline function; integration OPEN | `mc_core_spec_v2.tex`; §B.10 |
| `T_CKSRX` | SR-exit clock-stable cycles | **CONFLICT:** 5b legacy register vs. proposed 14b timing-file entry | OPEN | OPEN | Power Mgmt FSM | Baseline function; integration OPEN | `mc_core_spec_v2.tex`; §B.10 |

`MR_WR_AFFECTS_TIMING` is removed; timing significance remains software/driver knowledge and
has no RMC hardware or CSR representation.
`PD_FORCE_EXIT_ON_REF` is **intentionally excluded** — removed per review, folded into
invariant B.12-5, not a register.

## D.3 `timing_reg_file` (Register File, Not a Single Register)

`param_id[4:0] → nCK value[13:0]`, written via `csr_wr_en` / `csr_param_id[4:0]` /
`csr_param_val[13:0]`; read combinationally via `param_id[]`/`param_val[13:0]` on
`N_read_ports`. Access type: **RW via CSR write port, RO via all read ports** (the only register
structure in this architecture with an explicitly documented access model on both sides).
No per-parameter reset/default value is stated for any entry.

**23 baseline params** (v1.9.8): `T_RCD, T_RP, T_RAS, T_WR, T_RTP, T_CCD_L, T_CCD_L_WR,
T_CCD_L_WR2, T_WTR_L, T_WTR_S, T_RRD_L, T_RRD_S, T_FAW, T_RFC1, T_RFCsb, T_REFI, T_MRD, T_XP,
T_XS, T_DLLK, T_ZQCAL, T_ZQLAT, T_RTW`.

`T_CKSRE` and `T_CKSRX` are not in the IO-map timing-file enum. Legacy MC-core specifications
define each as a 5-bit register, whereas §B previously proposed 14-bit timing-file entries.
Their representation must be reconciled before either is added to this list.

No new params were added for Mode Register Programming — the software-sequenced update in §A.4
uses the existing per-parameter write path unchanged.

## D.4 Known Gaps and Inconsistencies in the Baseline Register Set

These are properties of the v1.9.8 ground truth itself, not introduced by this document, and
are called out here because they affect how complete a register document can be without further
input:

1. **The Handoff §17 table is not exhaustive.** It omits `TRAIN_EN`, `RAAIMT`, `RAAMMT`,
   `RAADec`, `pd_en`, `tZQCS_interval`, `ZQCAL_TRIG`, the timing-register file, and the legacy
   CL/CWL/PHY/frequency fields listed above.
2. **`T_CKSRE`/`T_CKSRX` conflict across sources.** The legacy MC-core specs give each 5 bits;
   the IO-map timing file omits them; this document must not choose a 14-bit representation
   without a decision.
3. **Almost no baseline CSR has an explicit access type** (RW/RO/W1C) stated anywhere — this
   gap spans nearly the entire baseline set, not just the registers introduced in this document.

---

# SECTION E — Open Architectural Decisions

These are the items that genuinely require a decision before architecture freeze. Each is
carried forward rather than silently resolved.

1. **Runtime-MRW command interface** — define the Stage-0 request contract, MRW address/data
   carriage to Stage 4, and the `me_cmd_type` enum/width/encodings. The baseline supplies only
   MR_Poll's MRR channel, not a runtime-MRW interface.
2. **Access type for baseline CSRs** — essentially the entire baseline register set (§D.2) has
   no stated RW/RO/W1C designation. Needs either a wholesale pass to define these, or an
   explicit working assumption (e.g., "OPEN, presumed RW unless noted RO") accepted for now.
3. **`T_CKSRE`/`T_CKSRX` representation** — reconcile the legacy 5-bit registers with the
   IO-map timing-file model, which omits them; no 14-bit timing-file addition is frozen.
4. **`tZQCS_interval` formal interface** (§D.4) — its CSR role and default are documented, but
   its width, access type, and ZQcal-FSM port are not.
5. **`MR_WR_DONE`'s access-type label** — "RO, auto-clears on next request" doesn't map cleanly
   onto the standard RW/RO/W1C taxonomy; worth pinning down the intended label explicitly.
