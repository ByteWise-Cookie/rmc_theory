# Watermark Manager — Full Work Scope

Status: both `rmc_wr_watermark_mgr` and `rmc_rd_watermark_mgr` are stub (`// TODO: implement`).
This doc scope full work needed to bring them to RTL-complete, matching contracts already
fixed by `rmc_pkg.sv` and architecture doc (`RMC_Full_Knowledge_v1.9.8.md`).

## 1. Ownership Contract

Two Watermark Buffer Managers (WR, RD) own their TCAM + status-register pair outright.
Scheduler: **READ ONLY** on both. No other block writes these registers. This is one of
project's four core invariants — must not leak.

Owned pair:
- WR side: `rmc_wr_tcam` + `rmc_wr_status_reg` (`wr_status_t`: valid, status, age)
- RD side: `rmc_rd_tcam` + `rmc_rd_status_reg` (`rd_status_t`: valid, status, age,
  merge_pending, wdb_entry_idx)

## 2. Core Jobs (both managers)

1. **Free-list allocation** — `alloc_req` → `alloc_gnt` + `alloc_idx` (index into
   N_WR_ENTRIES=64 / N_RD_ENTRIES=32 status-reg array). Must track which indices are
   free vs in-flight (valid bit is source of truth, but allocator needs its own
   free-index search — e.g. priority encoder over `~valid`, or free-list FIFO).
2. **Entry retire** — `retire_valid` + `retire_idx` → clear `valid`, return index to
   free pool. Fires from Stage 4 (Command Emission) on completion (`status → DONE`) or
   from response-path retirement, not from scheduler directly (scheduler is read-only).
3. **Status-reg field ownership** — drive `wr_en`/`idx`/`wr_data` into
   `rmc_wr_status_reg` / `rmc_rd_status_reg` on both alloc (set valid=1, status=PENDING,
   age=current global counter) and status transitions (`PENDING → ISSUED → DONE`,
   or `→ ERROR`). Stage 4 is the one that *triggers* PENDING→ISSUED on command commit —
   confirm exact write path: does Stage 4 pulse a signal into watermark mgr, or does
   watermark mgr expose a status-update port Stage 4 drives directly? Must nail this
   interface — currently undefined in stub ports.
4. **age field** — populate from `gc_counter` (GC_WIDTH=32 global cycle counter) at
   alloc time. This one field is single source of truth for three consumers:
   multi-hit tie-break (`argmax(age)`, newest wins), starvation detection
   (`age ≥ STARVATION_THR + entry_idx`, staggered so ≤1 starved entry fires/cycle),
   SJF cost. Manager doesn't compute these consumers' logic, but must guarantee age
   is correctly latched once at alloc and never rewritten.

## 3. WR-specific scope (`rmc_wr_watermark_mgr`)

- Extra port vs RD: `wr_count` (`$clog2(N_WR_ENTRIES):0` wide) — running occupancy
  count of valid WR entries, output every cycle for scheduler's watermark-crossing
  check.
- Must implement WR_HIGH_WM=16 / WR_LOW_WM=4 crossing semantics correctly on the
  *consumer* side (scheduler Stage 3) — manager's job is just to keep `wr_count`
  accurate cycle-by-cycle as alloc/retire fire (increment on grant, decrement on
  retire, both same cycle must net correctly — no lost update if alloc+retire
  collide same cycle).
- N_WR_ENTRIES = 64 (locked value TBD — pkg has open TODO "lock 64 vs 96", watch for
  param change before finalizing internal array/counter widths).
- Feeds `rmc_wr_tcam`'s `entry_valid` input — must confirm valid bitmask export path
  (today TCAM takes `entry_valid` as raw input; is that wired straight from status-reg
  output, bypassing watermark mgr, or does watermark mgr re-export it? Check
  `rmc_top.sv` wiring intent).

## 4. RD-specific scope (`rmc_rd_watermark_mgr`)

- No `wr_count`-equivalent output in stub — RD side doesn't drive scheduler mode-flip
  directly (`RD empty` check instead reads status-reg valid bits directly, presumably).
  Confirm whether RD watermark mgr needs an occupancy/empty output too, since Stage 3
  logic references "RD empty → switch to WR" — if that's not sourced from RD status
  reg elsewhere, this manager needs to emit it.
- Must additionally own `merge_pending` field lifecycle (RAW Bypass Manager sets it on
  partial-overlap forward; cleared when DRAM return completes merge) — confirm write
  path: does RAW Bypass Mgr write directly into RD status reg (violates single-owner
  rule) or route the update through RD watermark mgr? Per invariant #2 ("every register
  has exactly one owner"), RD watermark mgr should be sole writer — RAW Bypass Mgr must
  request the update through it, not drive `rd_status_reg` directly.
- `wdb_entry_idx` field similarly — set at merge_pending assertion time, sourced from
  WDB allocation, but written through RD watermark mgr for same single-owner reason.

## 5. Interface Gaps To Resolve Before Coding

Current stub ports are minimal skeletons — several signals implied by architecture doc
aren't in the port list yet. Resolve these (likely add ports) before RTL:

| Gap | Needed for |
|---|---|
| Status-update port (idx + new status_e value) into status_reg | PENDING→ISSUED→DONE/ERROR transitions |
| `gc_counter` input (current global cycle count) | latching `age` at alloc |
| RD: merge_pending/wdb_entry_idx set port | RAW bypass merge tracking |
| RD: occupancy/empty output (if not read directly from status reg elsewhere) | Stage 3 mode-flip logic |
| Reset behavior spec | all `valid` bits → 0 on `rst_n`, wr_count → 0 |

## 6. Verification Scope

- Alloc/retire same-cycle collision (grant + retire same idx or different idx same
  cycle) — no dropped free-list entry, no double-alloc.
- `wr_count` never diverges from popcount(valid) across random alloc/retire sequences.
- age monotonic non-decreasing across allocations (ties broken by entry_idx, matching
  `argmax(age)` consumer assumption in RAW bypass / scheduler).
- Full-buffer backpressure: `alloc_gnt` deasserts correctly when no free index (all
  N_WR_ENTRIES / N_RD_ENTRIES valid).
- Status transition legality: no PENDING→DONE skip, no write to retired (invalid) index.
- Cross-check against `rmc_wr_tcam` / `rmc_rd_tcam` `entry_valid` gating — invalid rows
  must go dark same cycle status reg clears valid (power-invariant from architecture
  doc §3.3).

## 7. Out of Scope (owned elsewhere, read-only or no interaction)

- TCAM match logic itself (`rmc_wr_tcam` / `rmc_rd_tcam`) — separate stub module.
- SJF cost computation, starvation threshold comparison, mode-flip decision — Scheduler
  Stage 2/3, read-only consumers of `age`/`valid`/`status`.
- DFI command emission / Stage 4 commit logic — watermark mgr only reacts to
  Stage 4's retire/status-update signal, doesn't drive DFI itself.

## 8. Suggested Implementation Order

1. Lock N_WR_ENTRIES (64 vs 96 open TODO in `rmc_pkg.sv`) — blocks nothing structurally
   but should close before final area numbers.
2. Nail down status-update port interface with whoever owns Stage 4 stub
   (`scheduler.sv`) — shared contract, do first to avoid rework.
3. Implement RD/WR watermark mgr free-list + status-reg drive logic in parallel
   (near-identical structure, RD adds merge_pending/wdb_entry_idx handling).
4. Wire `wr_count` output, verify against `rmc_wr_status_reg` valid popcount.
5. Unit-test each manager standalone (alloc/retire/age/status sequences) before
   integrating into `rmc_top.sv`.
