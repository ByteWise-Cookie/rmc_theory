# RMC Scheduler — Queue Architecture (post-mentor revision)

Architecture revision from the mentor review (this session). Reworks **where a request
lives across its lifetime**: splits the single TCAM-resident model into a short-residency
**admission/classify** stage plus **per-bank in-flight queues**. The command-selection
logic (per-class ready gates + weight arbiter) is **unchanged** — it now reads queue
heads instead of TCAM entries.

Companion docs: [[scheduler_staged_logic]] (S0–S4 port view), [[scheduler_bank_fsm]]
(per-bank FSM + weight arbiter), [[scheduler_wiring_spec]] (block/net inventory),
[[datapath_busy_timing]] (JEDEC timing). Ports referenced are the real names from
[`RMC_IO_Map.md §19`](RMC_IO_Map.md).

**Status:** design revision, **doc-only**. No pkg edit, no RTL, no golden-model edit
this pass. `sched_test.js` must later adopt the admission/queue split to stay the RTL
reference (flagged in §8).

---

## 0. What changed and why

Mentor review raised three points. Verdicts:

1. **RAW hazards — pause, don't bypass.** Kill the early-ACT RAW forwarding. A younger
   read to a pending write's address simply **stalls** until the write drains. Rare case,
   not worth the reorder hardware. *Accepted.* (§3)
2. **TCAM-residency penalty.** A request squatting a TCAM slot arrival→retire (~118 tCK
   worst) wastes scarce CAM — search cost scales with occupancy. Move the request to a
   **buffer/queue** after classify; free the TCAM slot for new incoming. *Accepted — this
   is the core rework.* (§1, §2)
3. **`status` field in reg_arr "useless".** Partly. The field did **two jobs**;
   the split gives each its own home — command-progress state moves into the queue entry,
   occupancy relocates to **queue occupancy** (head/tail pointers + depth counter —
   **no `valid` bit**, mentor). Not deleted, **relocated.** (§4)

Design decisions taken: **per-bank queues** (not per-command), **thread-style
self-contained entries**, RAW resolved **at admission**.

---

## 1. Two-stage split — admission vs in-flight

Old model (one home): `reg_arr` holds `{addr, meta, status}`, TCAM holds searchable
keys, entry lifetime = arrival→retire. TCAM slot occupied the **whole** latency window
even though search only matters during the classify/pick decision.

New model (two homes): decouple **searchable admission** from **in-flight tracking**.

```
front-end (AMU/ROB/WDB)
        |
        v
 [ TCAM  admission / classify station ]   <-- CAM, SHORT residency
   - search incoming {bg,bank} -> bank hit
   - compare row vs scoreboard.open_row -> row-hit / miss
   - RAW full-addr search vs pending writes -> block bit (§3)
   - classify: NEED_PRE / NEED_ACT / NEED_CAS
        |
        |  EVICT (once classified + RAW-clear)
        v
 [ per-bank queue x N_BANKS ]             <-- FIFO, NO CAM, in-flight home
   - holds {addr,row,col,seqnum,R/W,state}
   - only HEAD is active in command pipe
   - exposes 1 ready-bit / class to arbiter
        |
        v
 [ weight arbiter ]  (UNCHANGED)          <-- reads 16 heads, picks 1 cmd / CA slot
        |
        v
 DFI  (dfi_cmd, dfi_addr_row/col, dfi_bank, dfi_bg)
```

**Win:** TCAM now sized for *incoming burst + classify latency*, not the full latency
window. CAM depth/timing drops hard — the scarce searchable resource is held cycles, not
hundreds of cycles.

**TCAM is NOT removed.** The read path still owns a TCAM — it is the classify engine
(search `{bg,bank}`, row-hit compare vs `open_row`, RAW full-addr compare). The rework
**shortens residency only**: search/classify in TCAM, then evict to the queue. No
CAM-less read path — every read still transits the TCAM for its one search.

**TCAM keys unchanged:** `{bg,bank}` for classify (per [[scheduler_bank_fsm]] §0). RAW
adds a full-address compare at admission only (§3) — one search does classify + RAW.

---

## 2. Per-bank queue — structure

Chose **per-bank** over per-command. Rationale:

| | per-bank (chosen) | per-command |
|---|---|---|
| ordering | FIFO per bank — natural row-locality; same-row entries batch as row hits | lost — migrates PRE→ACT→CAS queue |
| row-lock | sits at queue head naturally | needs re-derivation |
| plumbing | entry stays put, state advances in place | entry hops queues each command |
| arbiter feed | via per-class ready bitmap (below) | direct per-class queue |

Per-command's only edge is feeding the CA arbiter by class. **Recover that without losing
per-bank ordering** via a ready bitmap:

- **16 per-bank queues** hold requests, in arrival order per bank.
- Each bank exposes **1 ready-bit per class** — `can_pre[16]`, `can_act[16]`,
  `can_cas[16]`. Only the **head** can assert a bit (one active request per bank — a bank
  serves one row-cycle at a time, physically true).
- These bitmaps are exactly the gate cloud from [[scheduler_wiring_spec]] §D /
  `sched_gate_hw`. The arbiter picks across the 16 heads by class-priority + age.

Net: mentor gets command-class selection, you keep per-bank ordering. **The weight
arbiter does not change** — it reads bank-queue heads where it used to read TCAM entries.

### Queue entry (thread context)
```
{ R/W, seqnum, bg, bank, row, col, state, blocked }
state   : NEED_PRE | NEED_ACT | NEED_CAS | DONE
blocked : RAW-held (read waiting on a write drain) — set at admission, §3
```
**No `valid` bit (mentor).** A FIFO's occupancy is defined by its **head/tail pointers**
(and the depth counter, §4) — a per-slot valid flag would be redundant. Slots between head
and tail are live; everything else is empty by construction. Retire advances the head; evict
advances the tail. This drops one bit per entry × 16 banks × depth and removes a
keep-in-sync field.

Timers (`next_pre/act/cas`, tRCD/tRTP/tWR…) are **NOT** per-entry — they are **per-bank
scoreboard** properties. The head reads its bank scoreboard; deeper entries just wait.

---

## 3. RAW — pause reads behind writes

- RAW = full-address match, read **younger** than a pending write to the same address
  (ROB `seqnum` gives program order).
- **Detect at admission** — TCAM is where the full-addr search already happens. On hit:
  set entry `blocked`, pin bit; **do not evict** to the bank queue until the blocking
  write retires.
- Reuse the existing pin-bit mechanism, now on the **read** side (was write_req). One
  search covers classify + RAW.
- Keeps per-bank queues **CAM-free** — RAW is never re-checked downstream.
- Cost: a RAW read eats the full write latency serially (no forward). Rare — accepted per
  mentor. Supersedes the early-ACT RAW-bypass proposal (subsumed; drop from design).

Interaction with [[raw_bypass_mgr]] ports: `wr_match[N_WR]` / `wr_age[]` / `rd_age`
feed the admission compare; `raw_hit` now gates **eviction**, not a datapath bypass mux.

---

## 4. Where `status` went — relocation, not deletion

The old reg_arr `status` conflated two roles. After the split:

- **command-progress state** (NEED_PRE/ACT/CAS/DONE) → lives in the **queue entry**
  (`state`). Advances locally as commands issue — the "thread" self-advances (§5). Mentor
  right that this does not belong in the TCAM reg_arr.
- **occupancy** → **no `valid` bit** (mentor). Occupancy is the FIFO's **head/tail
  pointers** plus a per-bank **depth counter + full flag**, fed to admission backpressure —
  not a per-entry valid flag. This is where the **watermark logic relocates** — see
  [[watermark_mgr_scope]]: the inv-LSB priority encoder + `wr_count` popcount now count
  **queue depth** (pointer delta), not TCAM valid bits.

Answer to "status useless": it was doing two jobs in one register; the split gives each a
home. Nothing lost.

**No valid bit — extends to the TCAM / RAW match gate.** The v1.8 design AND-ed every CAM
match with a per-entry `status.valid` (occupancy + power-gate). Under no-valid-bit that gate
becomes pointer-range, not a flag:
- **`rd_status_valid` retired.** It gated the RD_TCAM `{BG,bank}` bank pre-filter — a role
  that **moved entirely to the per-bank queue heads**. No consumer, no signal.
- **`wr_status_valid` → write-buffer occupied range.** The RAW search (a read matches
  *pending writes* by address) still needs "which writes are live", but that is the write
  buffer's **head/tail pointer range**, not a per-entry valid: `raw_hit_vector[i]` is masked
  by `wr_occupied[i]` (decoded from head..tail).
- **Power gating survives** as a pointer decode — rows outside head..tail are empty and can
  be clock/power-gated without a valid bit.

---

## 5. Thread model — carry on its own

Each queue entry = a **self-contained request-thread**: pack `{addr,row,col,seqnum,R/W,
state}` = the thread's context. Once ACT or PRE issues for the head, the entry advances
its own `state` **locally** — no trip back to TCAM or a central picker. Decentralized.

Correction to "carries its own timers": timers are **per-bank**, not per-entry (tRCD is a
bank property). So only the **queue head** is active in the command pipeline; it reads the
bank scoreboard timers. Sequence:

```
head NEED_ACT --(ACT issued, wait tRCD via bank next_cas)--> NEED_CAS
     NEED_CAS --(CAS issued, burst)--> DONE --> retire, dequeue
next entry becomes head:
     compare its row vs scoreboard.open_row
       row hit  -> NEED_CAS  (direct, no PRE/ACT)
       row miss -> NEED_PRE  (open row must precharge first)
       row empty-> NEED_ACT
```

Only one active request per bank at a time (physically correct). Row-lock (from
[[scheduler_bank_fsm]]) sits at the head: hold while `demand_count[bank] > 0`, release on
drain or `AGE_MAX`.

**Not a strictly-dumb FIFO — row-hit promotion (§5.2).** A pure tail-push FIFO strands a
row-hit that arrives *behind* a same-bank miss: the miss closes the open row, so the
stranded hit re-opens it (extra ACT), and the row-lock even stalls the miss's PRE to
`AGE_MAX` (the trailing hit's demand blocks it). Fix: on admission, **cluster same-row
entries** — insert a request after the last queued entry to the same row, not at the
absolute tail. Reorders only across *different* rows (different addresses → no hazard);
same-row order is preserved (RAW/WAW). One insertion point per bank, no downstream CAM.

---

## 5.2 Row-hit promotion — why not per-command sub-FIFOs

The alternative considered: split the depth-8 per-bank budget into per-command sub-FIFOs
(cas / act / miss). Rejected — it costs more for the same arbiter feed:

- **Class is live state, not a stored label.** A request's next command
  (`NEED_PRE/ACT/CAS`) is a function of the bank's *current* open row, which changes under
  it. A stored "hit" goes stale when the row closes → emitting it is an **illegal CAS**.
  So class must be **recomputed at the head** each cycle (`liveCmd`, §5) — physically
  bucketing by class forces entry **migration** between sub-FIFOs and a head re-check
  anyway.
- **"Purge on ACT" is a content match a FIFO can't do.** When a row opens, misses to it in
  the miss sub-FIFO should promote to hits — but a FIFO can't selectively extract, so the
  miss buffer would need to be a small **CAM**. Per-command split *relocates* the CAM, it
  doesn't remove it.
- **Static depth partition wastes the 8.** A hit-heavy bank overflows a shallow cas-FIFO
  while the miss-FIFO idles.

The per-command win is a ready-bit per class to the arbiter — already obtained from the
**unified** queue via the head's live class driving `can_pre/act/cas[16]` (§2). So: keep
one depth-8 FIFO per bank, recompute class at the head, expose the per-class ready bitmap,
and add **row-hit promotion** (§5) for locality — now the adopted default in the golden
model (`opts.promote`, default-on). Measured:
focused `hit,miss,hit` 3→2 ACTs and span 294→36 (kills the AGE_MAX stall); adversarial
same-bank interleave **11% → 24% DQ-busy**, ACTs 601→343; neutral on already-row-clustered
traffic. Self-tests cover all three.

## 5.3 Timing wheel — prototyped, rejected

The other alternative considered (the "spin-around buffer"): replace the per-bank FIFO +
per-cycle legality scan with a **timing wheel** — a ring where slot position = the cycle a
command becomes legal (`gc + delay`); the wheel rotates one slot/cycle, so the head is always
legal-now and you never scan. Reframes the "8-deep, 0-1 PRE / 2-3 ACT / 4-5 CAS, roles
rotate" idea (see [[scheduler_queue_ideas]] for the drawing). Prototyped in the golden model
(`opts.wheel`, event-driven: jump `gc` to the soonest ready-time among the bank heads) and
raced vs the FIFO. **Rejected — it trades throughput for scan cost:**

| trace | busy FIFO → wheel | ACTs | scheduler iters |
|---|---|---|---|
| adversarial (1 saturated bank) | 24% → **24%** (Δ0) | 343 = 343 | **73% fewer** |
| interleave (16 banks) | 46% → **40%** (Δ−6) | 4000 = 4000 | 47% fewer |
| rowlocal (16 banks) | 29% → **23%** (Δ−6) | 4000 = 4000 | 60% fewer |

On a single saturated bank the wheel matches the FIFO exactly with ~70% fewer iterations. But
under **dynamic admission** on multi-bank traffic it **loses 4–6 pt DQ-busy**: jumping past a
cycle skips a **freshly-evicted row-hit that became legal there**, which the per-tCK scan
catches. Since `timing_reg_file` already gives **O(1) per-cycle legality** — there is no scan
bottleneck to remove — the wheel's only benefit is moot while its throughput cost is real.
Same shape as the OQ-20 weights sweep: structure/scan tricks don't move the CA / tFAW /
BG-rotation ceiling; *which cycle you issue* does. **Keep the per-bank FIFO + per-cycle scan +
row-hit promotion.** (Aside: `lock:false` deadlocks a saturated bank — row-hits stuck in the
TCAM keep `demand > 0`, so the demand-gated PRE never fires — confirming the age-capped lock
is load-bearing, §5.)

## 6. Queue depth — round-trip / gear ratio

Sizing (numbers to lock in the deferred sweep):

- A bank **serializes** — few concurrently-useful entries. Row-hit stream drains at
  `tCCD_L`=12 tCK/CAS; row-miss ~118 tCK.
- **Per-bank depth** ≈ requests arriving during one bank round-trip so the head never
  starves waiting for the next. Small — **~4–8 per bank**.
- **Total in-flight** = `N_BANKS` × depth. Cross-check: read floor `N ≈ L_miss/BL2 =
  118/8 ≈ 16`, buffer target 64 → ~4/bank → 64 total. Consistent with the depth-64
  decision.
- **Freq / gear ratio** (DFI gear 1:2 or 1:4): controller issues in the slow domain, CA
  is ≤1 cmd / 2 tCK. The ratio governs **how many banks must have a ready head each
  controller cycle** to fill CA slots (fill the burst shadow) — not per-bank depth. Enough
  ready banks = `tCCD / CA_slot` worth of prep candidates.

**Sweep result (OQ-20 — `../tools/sched_model/SWEEP_RESULTS.md`):**
- **per-bank depth = 8, tcam = 32** → total in-flight ≤128 (throughput plateau; tcam<32
  costs 3–7pt DQ-busy). Depth past ~8 gains <0.3pt/step for +50% storage.
- **R/W organization = unified per-bank + tag** — `rawPause` on/off was negligible
  (35.2 vs 35.0%); the guard is reserved for the split variant (§7).
- ready-bank count for CA-slot fill: governed by the DFI gear ratio, not depth (above).

---

## 7. Open items / risks to nail

- **Admission backpressure.** Hot bank fills its queue → TCAM can't evict → TCAM backs up
  → front-end credit stall. Per-bank queue **full flag** must feed admission (this is the
  relocated watermark, §4).
- **Read vs write queues.** Unified per-bank with an R/W tag, or two sets per bank? Row
  buffer shared; data paths differ (WDB write vs read return). Lean unified + tag,
  batch-mode selects head R or W (matches [[scheduler_adaptive_batching]]). **Folded into
  the sweep** (§6) — decide with depth.
- **Global QoS / oldest.** 16 independent queues lose global age order. The arbiter's
  aging counters ([[scheduler_bank_fsm]] §4b) cover fairness; confirm the starvation
  bound `AGE_MAX` still holds across queues.
- **Maintenance inject.** `s0_override` (REF/RFM/ZQ/PRE-all from `maintenance_engine`)
  must push into the bank queues or bypass to head. Keep that path — it force-breaks the
  row-lock.
- **New blocks vs reused.** Genuinely new: admission-evict logic, the 16 per-bank FIFOs,
  relocated watermark counters. Reused unchanged: TCAM search core, weight arbiter, gate
  cloud, per-bank scoreboard timers.

---

## 8. Golden-model status

`tools/sched_model/sched_test.js` now implements this architecture, opt-gated
(`opts.queueArch`), so it A/Bs against the window model:
1. admission stage — short TCAM (`opts.tcam`, default 32) classifies then **evicts**
   each entry out of the searched set,
2. per-bank FIFOs (`opts.bankDepth`, default 8) with **head-only activation** —
   pickers see one candidate per bank,
3. RAW = block-at-admission (`opts.rawPause`) — older-write-to-same-address holds the
   read in TCAM; no bypass modeled,
4. backpressure — bank-queue-full keeps the entry in TCAM, TCAM-full stalls admission.

Selection logic (`legal()`/`emit()`/arbiter) is **unchanged** — it reoperates on queue
heads. Verified: 0 violations / 0 unscheduled both bins; DQ-busy within ±2pt of the
window model; drains at `tcam=8, bankDepth=2`; RAW keeps RD after its WR. A **timing-wheel**
variant (`opts.wheel`) is also in the model for the A/B in §5.3 — event-driven `gc` advance,
kept as a rejected-alternative datapoint (matches FIFO on 1 bank, loses 4–6 pt on multi-bank).

Note: the model's per-bank queue is **unified R/W** (batch-mode selects head R or W). The
split-R/W-queue variant is left as a documented option; `rawPause` is the guard reserved
for it — under the unified FIFO, same-bank program order already holds.

**Sweep closed (OQ-20/OQ-21).** The weighted arbiter (`K·control + age + servo`, never-
idle-DQ guardrail) + aging counter are now in the model (`opts.arbiter="weighted"`),
retiring the model debt. Swept: **weights are second-order — guardrail + sizing dominate**
(DQ-busy flat ~35.2% across `K`/control/servo, since only bank heads are reorderable).
Recorded design point: control 2/1/0, K=5000, guardrail ON, servo retained default-OFF,
AGE_MAX=256, depth=8, tcam=32, unified+tag. Full tables:
[`../tools/sched_model/SWEEP_RESULTS.md`](../tools/sched_model/SWEEP_RESULTS.md).

---

## 9. Map

| Concern | Home (new) | Doc |
|---|---|---|
| search / classify / RAW | TCAM admission (short) | §1, §3 |
| in-flight request | per-bank queue entry | §2, §5 |
| command-progress state | queue entry `state` | §4, §5 |
| occupancy / watermark | queue depth counters | §4, [[watermark_mgr_scope]] |
| timers (tRCD/tRTP/tWR) | per-bank scoreboard | §5 |
| ready-bit / class pick | gate bitmap → weight arbiter | §2, [[scheduler_bank_fsm]] |
| depth sizing | deferred sweep | §6 |
