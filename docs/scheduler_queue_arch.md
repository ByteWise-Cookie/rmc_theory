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
   occupancy/valid stays for the allocator but relocates to **queue occupancy**. Not
   deleted, **relocated.** (§4)

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
{ valid, R/W, seqnum, bg, bank, row, col, state, blocked }
state   : NEED_PRE | NEED_ACT | NEED_CAS | DONE
blocked : RAW-held (read waiting on a write drain) — set at admission, §3
```
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
- **occupancy / valid** → still needed by the allocator/retire, but becomes **per-bank
  queue occupancy** (depth counter + full flag), fed to admission backpressure. This is
  where the **watermark logic relocates** — see [[watermark_mgr_scope]]: the inv-LSB
  priority encoder + `wr_count` popcount now count **queue** slots, not TCAM slots.

Answer to "status useless": it was doing two jobs in one register; the split gives each a
home. Nothing lost.

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

Only one active request per bank at a time (physically correct). The queue behind the
head is a dumb FIFO of pending work. Row-lock (from [[scheduler_bank_fsm]]) sits at the
head: hold while `demand_count[bank] > 0`, release on drain or `AGE_MAX`.

---

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

Exact depth, ready-bank count = the deferred weights/sizing sweep (with `AGE_MAX`, servo
`POOL_LOW/HIGH`).

---

## 7. Open items / risks to nail

- **Admission backpressure.** Hot bank fills its queue → TCAM can't evict → TCAM backs up
  → front-end credit stall. Per-bank queue **full flag** must feed admission (this is the
  relocated watermark, §4).
- **Read vs write queues.** Unified per-bank with an R/W tag, or two sets per bank? Row
  buffer shared; data paths differ (WDB write vs read return). **Open** — lean unified +
  tag, batch-mode selects head R or W (matches [[scheduler_adaptive_batching]]).
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

## 8. Golden-model debt

`tools/sched_model/sched_test.js` still models the single-residency picker. To stay the
RTL reference it must adopt:
1. admission stage that evicts classified entries out of the searched set,
2. 16 per-bank FIFOs with head-only activation,
3. RAW = block-at-admission (drop any bypass modeling),
4. backpressure from queue-full to admission.

Selection logic (legal()/emit()/arbiter) is unchanged — it reoperates on queue heads.
Flagged for the same sweep pass that adds the aging counter + DQ servo (already deferred).

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
