# RMC — Reconfigurable DDR5 Memory Controller
## Full Knowledge Document — v1.9.8

This document is the complete narrative knowledge base for the RMC project: what it is,
every architectural decision and why it was made, how data moves through the machine,
and how every block fits together. It consolidates `rmc_version_control.md`,
`RMC_Handoff_v1.9.8.md`, and `RMC_IO_Map.md` into one readable account.

---

## 1. What RMC Is

RMC is a capstone-grade, fully parameterized DDR5 memory controller RTL project targeting
the JEDEC JESD79-5 standard, with an AXI4 host-side interface and a DFI 5.2 PHY-side
interface. The baseline anchor configuration is 4GB, single-channel, single-rank, but every
width in the design — address bits, ID bits, data bus width, buffer depths, rank/channel
counts — is a compile-time parameter, with a documented ceiling of 46-bit addressing across
8 channels × 8 ranks × 64Gb × 3DS-8H (64TB).

The scope is deliberately the **MC block only**: not the PHY (DFI is the contract boundary),
not the CPU/AXI masters upstream. Inside that boundary, the project implements the full
DDR5 command pipeline: burst splitting, address translation/hashing, write/read buffering
with content-addressable search, read-after-write hazard detection and bypass, a five-stage
bank-aware command scheduler, per-bank/per-rank/global timing state, and a six-sub-FSM
maintenance engine handling initialization, refresh, ZQ calibration, RFM, power management,
and thermal throttling.

The DDR5 addressing hierarchy the whole design is built around is:
**Channel → Subchannel → Rank → Bank Group → Bank → Row → Column.**

---

## 2. Why It's Shaped the Way It Is — the Foundational Locks

A handful of early decisions shape everything downstream:

**BL16 only, no BL8/BC8.** A 64-byte AXI-aligned INCR burst maps to exactly one BL16 burst
on a 32-bit DDR5 subchannel. This one-to-one mapping is what lets the whole request/response
pipeline avoid burst-fragment bookkeeping — one AXI beat-group = one DRAM burst, always.

**AXI feature set is deliberately narrow.** INCR bursts only (WRAP/FIXED rejected at the
port), 64-bit data width, multiple outstanding IDs supported, but no narrow/unaligned
transfers, no exclusive access, no QoS. Every one of these was cut because it adds
verification surface without adding value for a DRAM controller — WRAP/FIXED don't map
cleanly to row/column addressing, narrow transfers don't matter when BL16 already forces
64B granularity, and QoS ordering conflicts with the scheduler's own SJF discipline.

**Exactly one clock-domain-crossing.** All CIF logic runs on the AXI clock; all MC-core
logic (buffers, scheduler, FSM tables, maintenance engine) runs on the MC clock. The *only*
place those two clocks meet is a single async-FIFO pair — one FIFO for requests
(CIF→MC), one for responses (MC→CIF). This was a conscious choice to concentrate 100% of
the CDC verification burden into one small, well-understood primitive instead of scattering
handshakes across dozens of blocks.

**Everything inside the MC core is valid-credit, not valid-ready.** A combinational
`ready` signal means combinational backpressure logic threading through the whole
pipeline, which is exactly what breaks timing closure at high frequency. Every intra-MC
interface instead uses registered credit counters: the sender tracks how many credits it
has, decrements on send, and the receiver returns a credit after it retires the entry. AXI
ports are the one exception, because valid-ready is what the AXI4 spec mandates there.

**Absolute deadline timestamps, not countdown counters.** Instead of ~200 per-bank
decrementing counters (next_cas--, next_pre--, ...), every timing field stores the absolute
global-cycle value at which the action becomes legal (`next_legal = gc + delay`), and
legality is a single comparison: `eligible = (gc - next_legal)[MSB] == 0`. This is the same
trick as TCP sequence-number wraparound comparison. It collapses ~200 decrementers into
~100 static comparators against one shared free-running counter — a huge area and power win,
and it's why the Global Cycle Counter is a first-class block instead of an implementation
detail.

**Registered `can_*` flags, computed off the critical path.** Even the comparison above is
too much to want inside the scheduler's decision cycle, so every gate the scheduler needs
(`can_cas`, `can_pre`, `can_act`, `can_ref`, and the cross-bank/rank/BG equivalents) is
computed every cycle as a background process and stored as a plain registered bit. Stage 2
of the scheduler *only ever reads these flags* — there is no subtractor anywhere in the
scheduling critical path.

---

## 3. The Data Path, Front to Back

### 3.1 CIF — Client Interface (AXI clock domain)

An AXI4 write and read port each terminate their side of the host interface (valid-ready,
spec-mandated). Addresses flow into the **AMU (Address Map Unit)**, which replaced the
original plain Address Translator: the AMU does an optional per-field XOR hash
(`hashed = raw XOR (raw >> shift)`) before extracting channel/rank/bank-group/bank/row/column,
and supports split (non-contiguous) bit-field extraction for channel interleave. Rank and
channel are hashed and pushed to the address MSBs (spreading traffic across the units that
benefit most from spreading); bank group, bank, row, and column are left un-hashed to
preserve row-hit locality, which is what read latency actually depends on.

The **Burst Splitter** runs two checks: does the request cross a row boundary (stage 1),
and is it BL16-aligned (stage 2). The **ROB (Reorder Buffer)** tags every request with a
composite `{AXID, seqnum}` key and keeps a per-AXID head pointer so that read completions
can be re-ordered back into AXI's required per-ID order even though the DRAM side services
requests out of arrival order. **Merge Logic** reassembles any request that got fragmented
by the splitter.

Everything then funnels through the **single CDC boundary**: one async request FIFO
(CIF→MC, credit-based push from the CIF side, valid-credit receive on the MC side) and one
async response FIFO (MC→CIF, the reverse). Both are 16 entries deep — roughly 2× the
round-trip pipeline latency, which is the whole sizing rationale.

### 3.2 MC Core — buffering, hazard detection, global state (MC clock domain)

Requests land in one of two **CAM-searched buffers**: the Write Request Buffer
(backed by **WR_TCAM**) or the Read Request Buffer (backed by **RD_TCAM**). Write *data*
lives separately in the **Write Data Buffer**, an index-addressed SRAM (not a FIFO) — the
TCAM entry carries a `data_buf_idx` pointer into it.

The two TCAMs are deliberately different animals:

- **WR_TCAM** does a *full* address match — `{bank group, bank, row, column}` — because its
  job is exact-match RAW hazard detection: does an incoming read collide with a pending
  write?
- **RD_TCAM** does a *ternary* match on just `{bank group, bank}` — row and column are
  carried in the entry but not searched — because its job is feeding the scheduler's
  per-bank pre-filter (Stage 1), which only needs to know "is there a request waiting for
  this bank," not the exact address.

Occupancy for both is tracked in separate **status registers** (`valid | status | age`,
plus `merge_pending` for reads) — these are the single source of truth for whether a TCAM
row is live (TCAM `match` output is gated by `status.valid`, which is also a power trick:
invalid rows go electrically dark, cutting dynamic power at low occupancy). `age` is the
allocation timestamp and is reused for three purposes: multi-hit tie-breaking (newest wins),
starvation detection, and SJF cost. Two **Watermark Buffer Managers** (one write, one read)
own their respective TCAM + status register pair outright — the scheduler only ever reads
them.

Sitting between the write and read sides is the **RAW Bypass Manager**: every incoming read
searches WR_TCAM in parallel with its own allocation (stage A, combinational, zero penalty
on a miss), then a stage-B mask-coverage check decides the outcome — full hit (forward
write-buffer data straight to the response path via the **Merge Unit**'s 64-lane 2:1 mux),
partial overlap (issue the DRAM fetch immediately with no stall, tag
`merge_pending`, and combine WDB + DRAM data at return time — again zero penalty vs a plain
miss), or miss/late-write (pass the read through to the scheduler normally). A hit is only
valid if the write's age is ≤ the read's age; a write that arrives *after* the read doesn't
count, which is what prevents stale-data forwarding. The **Hold-Forward** stage sits right
after: exactly two response sources can produce a result in the same cycle (the RAW bypass
path and a genuine DRAM return), so two hold slots are the proven exact minimum *and*
maximum — a third simultaneous collision is impossible by construction, not by chance.

Two blocks in this domain are pure infrastructure with no DRAM-specific logic at all: the
**Global Cycle Counter** (a free-running counter that never resets except on `SOFT_RESET`,
and is the timestamp source for every "absolute deadline" field in the design) and
**timing_reg_file** (a `param_id → nCK value` lookup table for every JEDEC timing parameter,
read combinationally and multi-ported, written only by CSR at init time).

The **Bank Partition Controller** implements a scheme where the bank set is split into a
read-half and a write-half that rotate every `WINDOW_SIZE` cycles — since a read and a write
never share a bank within a window, `tRTW`/`tWTR` simply don't apply inside the window; the
turnaround penalty is paid once, at the rotation boundary, and amortized across the whole
window.

### 3.3 Scheduler — five stages, read-only against state

The scheduler is architecturally a **read-only consumer**: it decides, but every actual
state mutation (bank FSM transitions, timing-table updates, status-register updates) happens
in one place — Stage 4. This single-writer discipline is one of the project's four "core
rules" (see §9).

- **Stage 0 — Maintenance Override.** Priority order `ref_urgent > ref_due > rfm_req >
  zq_due`. If any fires, Stages 1–3 are bypassed entirely and the maintenance command goes
  straight to Stage 4.
- **Stage 1 — TCAM Search.** RD_TCAM and WR_TCAM are searched in the same cycle (multi-port),
  producing a per-bank hit bitmap plus metadata (row, column, request type, entry index),
  gated by each entry's `status.valid`. A multi-hit within a bank is resolved by
  `argmax(age)` — newest wins — via a status-register lookup, not a TCAM field.
- **Stage 2 — can_\* Gate Check + SJF Cost Classification.** Reads only the pre-computed
  registered `can_*` flags (per-bank, per-BG, per-rank, global, plus the partition mask from
  the Bank Partition Controller) and classifies every candidate bank into a cost bucket:
  row-hit (cost 0), activating (cost = time left until CAS is legal), idle (cost = tRCD), or
  wrong-row-open (cost = tRP + tRCD, i.e. precharge then re-activate). This stage also
  detects **speculative-ACT opportunities**: on a true NOP cycle, if a bank is approaching
  its column boundary and RD_TCAM confirms a real request already exists for the next bank
  at the same row, an activate to that next bank can be issued speculatively — it's
  TCAM-confirmed, not blind prediction, so there is no mispredict path, only a possible
  wasted FAW slot in the worst case.
- **Stage 3 — SJF Winner Selection.** Priority is `Stage-0 override (already handled) >
  starved-miss > hit-set (lowest cost 0, preferring a bank group different from the last
  activate) > miss-set (lowest remaining cost)`. Starvation uses a staggered threshold —
  `age ≥ STARVATION_THR + entry_idx` — which guarantees at most one starved entry can fire
  per cycle, so there's never a collision between two "must-service-now" candidates.
  Read/write mode flips on watermark crossings (`wr_count ≥ WR_HIGH_WM` or RD empty →
  switch to WR; `wr_count ≤ WR_LOW_WM` or WR empty → switch to RD), with an `AGE_THR2`
  escalation that force-flips the mode if starvation gets bad enough. On a true NOP cycle
  the priority is opportunity refresh, then speculative ACT, then WR-partition drain, then
  genuinely nothing.
- **Stage 4 — Command Emission + Writebacks.** Drives the DFI command bus (through the
  Maintenance Engine's DFI mux) and is the *only* stage that writes the Per-Bank FSM Table,
  the Global Timing Table, the Per-Rank FSM Table (RAA increment), and status registers
  (`PENDING → ISSUED`). It also updates every `can_*` flag in the background for next cycle.

### 3.4 FSM Tables — the state Stage 4 writes and Stage 2 reads

Three tables hold all DRAM timing/state, all following the same pattern (absolute-deadline
fields + registered `can_*` companions):

- **Per-Bank FSM Table** (16 × N_RANKS rows): 8-state bank FSM (IDLE, ACTIVATING, ACTIVE,
  PRECHARGING, REFRESHING_SB, RFM_ACTIVE, POWER_DOWN, SELF_REFRESH), open row, and the four
  `next_*`/`can_*` timing pairs (CAS, PRE, ACT, REF). The five old "pending" bits
  (open/pre/act/wr/rd_pending) were removed once the TCAM's own hit/state outputs made them
  redundant — one less thing to keep in sync.
- **Per-Rank FSM Table** (N_RANKS rows): rank-level FSM (NORMAL, REFab_ACTIVE, ZQCAL_ACTIVE,
  POWER_DOWN, SELF_REFRESH), the REFab/ZQcal/power-down-exit deadlines and gates, a
  leaky-bucket refresh-credit counter, per-bank RAA (Row Activation Accumulator) counters for
  RFM, and the MR4 thermal-poll state (`last_TUF`, `next_poll_gc`, `mrr_data`).
- **Global Timing Table** (1 instance): everything that isn't per-bank or per-rank —
  cross-bank tRRD_S/tCCD_S, the tFAW ring buffer of recent activate timestamps, and the
  per-bank-group tRRD_L/tCCD_L/tWTR_L family.

Alongside them, the **Bank Activity Counter** (count + dirty per bank) is a small but
heavily-shared table: the Maintenance Engine uses it to target the least-loaded bank for
opportunistic refresh, Power Management uses `count==0` across all banks as its
power-down-entry gate, and the scheduler's Stage 3 uses it to prefer draining
high-count banks.

### 3.5 Maintenance Engine — six sub-FSMs, one peer to the scheduler

The ME is architecturally a *peer* to the scheduler, not a subordinate — it writes directly
into the FSM tables and never itself issues a CAS. Internal priority mirrors Stage 0:
`ref_urgent > ref_due > rfm_req > zq_due`.

1. **Init FSM** (16 states) walks the full DDR5 power-on-reset sequence — reset assertion/
   deassertion, ODT settle, DLL divider/reset via MPC, ZQ calibration start/latch, mode
   register writes, training — and on completion asserts `init_done`, which is a one-way
   latch that hands the DFI output mux from the Init FSM to the Scheduler permanently (never
   de-asserted).
2. **Refresh FSM** (6 states) runs a leaky-bucket credit counter (+1 per tREFI, -1 per issued
   refresh); `ref_urgent` fires the Stage-0 override at 8 credits, `ref_due` is the normal
   trigger. REFab blocks an entire rank for tRFC1; REFsb blocks a single bank for tRFCsb and
   targets the least-loaded bank (`argmin(bank_act_count)`) unless a per-bank watchdog
   (uncovered for tREFI×32) forces an overdue bank instead. On a true NOP cycle it can also
   fire an **opportunity refresh** — an idle, non-overdue-critical bank gets refreshed for
   free with zero traffic disruption, spreading load and reducing future forced stalls.
3. **ZQcal FSM** (7 states, one instance per rank) runs the MPC ZQ-calibration start/latch
   sequence and gates the whole rank for its duration.
4. **RFM FSM** (6 states) tracks per-bank RAA counters (+1 per activate, decremented per
   refresh) and requests a targeted RFM once a bank's count crosses `RAAIMT`, sitting in
   priority below refresh but above ZQcal.
5. **Power Management FSM** (10 states) has independent power-down and self-refresh
   branches; power-down entry requires every bank in the rank to be idle (`bank_act_count==0`)
   with no maintenance pending.
6. **MR_Poll FSM** (6 states) periodically issues an MRR to mode register 4 to read the
   thermal update flag (TUF); when TUF=1 (die temperature > 85°C) it halves the effective
   tREFI, informing the Refresh FSM. The MRR response comes back through a **sideband** path
   from the Read Data Path, not through the normal response FIFO — it's control-plane
   traffic, not host data.

The **DFI Output Mux** lives inside the ME: while `init_done==0` the Init FSM drives every
DFI output; once it goes high, the Scheduler's Stage 4 drives DFI permanently. MRR issue is
a Stage-0 bypass from MR_Poll straight to Stage 4 — there is no third mux input.

### 3.6 Write/Read Data Path and Error Handling

The **Write Data Path** handles write-level alignment (CWL), CRC, and DFI write-enable
timing. The **Read Data Path** runs the read latency counter, captures data into a FIFO,
checks ECC/CRC, and is where the MR4 sideband response is captured for MR_Poll. The
**Error Handler** watches `scheduler_error` and `dfi_alert_n` (the PHY's CRC/CA-parity alert)
and is the single point that would drive a recovery action.

### 3.7 DFI / PHY

The design's DFI-facing boundary is the PHY (DFI 5.2) and, beyond it, the DDR5 DRAM itself
(JESD79-5) — outside RMC's scope but drawn in the block diagram as the pipeline's actual
destination.

---

## 4. Address Mapping

Baseline 32-bit, 4GB configuration:

```
A[31:17] = Row    (15b)
A[16:14] = BG     (3b, 8 bank groups)
A[13:12] = Bank   (2b, 4 banks/BG)
A[11:2]  = Col    (10b)
A[1:0]   = Offset
Channel select = A[7]  (128B interleave baseline)
```

Bank-group and bank bit positions are fixed across every supported config; only the address
width and row/column split scale up as capacity grows. The **AMU** (see §3.1) replaced the
original fixed Address Translator specifically so this mapping can be reshuffled at runtime
via CSR (XOR hash per field, split-field extraction for arbitrary channel-interleave
granularity) without touching RTL. The channel-interleave granularity itself (4KB/8KB/16KB)
is the one open item left in the address-mapping design (OQ-19b) — it needs a Python
traffic-trace script to resolve, not an architectural decision.

Multi-config profiles range from Desktop-S (8GB, 33b) up to 3DS-Max (64TB, 46b with 3-bit
stack-ID for 8-high 3DS stacking) — all using the same RTL with different parameter values.

---

## 5. Why the Numbers Are What They Are

A few sizing decisions are worth remembering the *reasoning* for, not just the value:

- **N_WR_ENTRIES = 2–3× N_RD_ENTRIES** (64 vs 32 baseline, 96 vs 32 in v2). Writes can sit
  in the background and drain opportunistically; reads are latency-critical. A bigger write
  buffer means the scheduler can let writes wait longer without a read ever queuing behind
  them, at unchanged total bandwidth.
- **GC_WIDTH baseline reasoning: 20 bits.** Half-range is 524,288 cycles; the worst-case gap
  between a timestamp being written and being checked is ~12,480 cycles — a 42× margin, and
  the comparison technique (bit-MSB sign check after modular subtraction) is exactly TCP
  sequence-number wraparound math.
- **ROB_WATERMARK = 37, REF-stall timeout = 76 cycles.** 37 is the measured worst-case full
  round-trip latency (CIF pipeline ~2 + REQ FIFO CDC ~4 + RAW check ~1 + scheduler ~4 + DRAM
  row-miss 19 + capture FIFO 1 + RESP FIFO CDC ~4 + ROB retirement 1). The REF-stall timeout
  is 2× that, chosen as "wait for the in-flight CAS to complete" rather than the more
  aggressive "abort and retry" option.
- **RD_STARVATION_THR = 12,480 cycles (9× tREFI), WR_STARVATION_THR = 37,440 (3× that).**
  Write starvation is tolerated three times longer than read starvation before the hard
  safety net fires, because writes are already being drained preferentially by the
  watermark logic — the starvation threshold is a backstop, not the primary mechanism.
- **FIFO_DEPTH = 16 for both async FIFOs.** Roughly 2× the CDC-plus-pipeline round-trip
  latency, giving headroom without over-provisioning.
- **TCAM cell budget (v1.9.8 count): WR_TCAM 24,576T + RD_TCAM 1,920T + RAW BCAM 12,288T ≈
  38,784 transistors ≈ 6,464 SRAM-bit equivalent.** RD_TCAM is far cheaper than WR_TCAM
  because it only searches 2 fields (bank-group + bank) ternary, versus WR_TCAM's full
  4-field exact match — a direct payoff of splitting the two TCAMs by search semantics
  instead of using one general-purpose CAM for both jobs.

---

## 6. Interface Protocol Summary

| Interface | Protocol | Why |
|---|---|---|
| AXI4 ports | Valid-ready | Spec mandated |
| Async REQ FIFO write (CIF side) | Credit-based push | No combinational `wr_full` |
| Async REQ FIFO read (MC side) | Valid-credit receive | Registered `rd_valid`, credit returned after consume |
| Async RESP FIFO write (MC side) | Credit-based push | Gated by `gate_resp_fifo_avail` |
| Async RESP FIFO read (CIF side) | Valid-credit receive | Same pattern, reverse direction |
| Credit-return paths (both directions) | Registered 1-bit, pulse-synchronized | Crosses the CDC boundary safely |
| All intra-MC paths | Valid-credit | No combinational backpressure anywhere inside MC clock domain |
| DFI 5.2 | DFI protocol | Spec mandated |
| PHY → MC read data | Valid-only | No backpressure on a read return — MC must always be ready to sink it |

---

## 7. Pipeline Latency Reference (worked example @ 200MHz, tCK = 5ns)

| Path | Cycles |
|---|---|
| Row hit (CAS only) | RL + BL/2 = 11 |
| Row empty (IDLE → CAS) | tRCD + RL + BL/2 = 15 |
| Row miss (wrong row open) | tRP + tRCD + RL + BL/2 = 19 |
| **Full round trip, worst case (row miss, no REF in flight)** | **≈ 37** |

---

## 8. FSM Inventory

| FSM | States | Instances | Owner |
|---|---|---|---|
| Init FSM | 16 | 1 | ME sub-FSM 1 |
| Refresh FSM | 6 | 1 | ME sub-FSM 2 |
| ZQcal FSM | 7 | N_RANKS | ME sub-FSM 3 |
| RFM FSM | 6 | 1 | ME sub-FSM 4 |
| Power Mgmt FSM | 10 | 1 | ME sub-FSM 5 |
| MR_Poll FSM | 6 | 1 | ME sub-FSM 6 |
| Per-Bank FSM | 8 | 16 × N_RANKS | Scheduler |
| Per-Rank FSM | 5 | N_RANKS | ME |
| Global FSM | 5 | 1 | Global |
| Bank Partition FSM | 2 | 1 | Scheduler |
| Write CRC FSM | 4 | 1 | Write Data Path |
| ECS FSM | 4 | 1 | Read Data Path |

---

## 9. The Four Core Rules

Everything above ultimately answers to four invariants that define the whole architecture's
discipline:

1. **The Scheduler never writes state directly except through Stage 4's committed
   writebacks.** Stages 0–3 are pure decision logic; nothing they compute is visible to any
   other block until Stage 4 commits it.
2. **Every register has exactly one owner.** Status registers belong to their watermark
   manager, FSM tables belong to Stage 4 (with the ME also writing the Per-Bank/Per-Rank
   tables for maintenance events), the timing register file belongs to CSR. The scheduler's
   access to anything it doesn't own is READ ONLY, always.
3. **State changes happen only via a committed command** — there is no speculative state
   mutation anywhere; even the speculative-ACT feature only fires once the request it's
   speculating about is already TCAM-confirmed to exist.
4. **Everything else is read-only.** If a block isn't the documented owner of a piece of
   state, it reads it and nothing more.

---

## 10. Open Items (as of v1.9.8)

| ID | Item | Status |
|---|---|---|
| OQ-19b | Channel-interleave granularity (4KB / 8KB / 16KB) | Needs a Python traffic-trace script; CSR-configurable once decided |

Every other open question raised across the v1.0–v1.9.8 history (RAW hold-forward
collision limits, starvation thresholds, FIFO credit depths, ZQcal instancing, TCAM area
budget, PD idle threshold, ZQCS interval, runtime DIMM discovery) has been closed — see
`rmc_version_control.md` for the full closure history if the reasoning behind any of them
is needed later.

---

## 11. Architecture Self-Rating (as of v1.9.2, unchanged through v1.9.8)

| Scope | Rating |
|---|---|
| What's built (buffers, timing model, RAW bypass, scheduler) | 9/10 |
| Full architecture vs. industry practice | 8/10 |
| vs. a typical capstone project | Significantly above |

The TCAM split, registered `can_*` flags, credit-based CDC interfaces, SJF scheduling, bank
pipelining, and staggered starvation handling all match or exceed patterns found in real
DDR controller IP (Synopsys DDRC, ARM DMC-620 class designs).

---

## 12. What's Left Before RTL

Per the version-control roadmap, in priority order: patch the stale LaTeX docs (pending
bits, hardcoded buffer depths, and the RAW partial-hit "degrade to DRAM" line are all
known-stale — see BUG-02 through BUG-07 in `rmc_version_control.md`), resolve OQ-19b with a
Python address-hash optimizer script, and then begin the RTL skeleton: top-level module
hierarchy and parameter propagation. Architecture is complete; RTL has not been started.
