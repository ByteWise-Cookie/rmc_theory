# Same-line R/W hazard — why CIF owns it, not the MC core

**Phase-2 rebuild.** Records the ordering decision from the walk: the read-after-write (and
write-after-write / write-after-read) hazard on a shared DRAM line is handled **upstream in the
CIF, request-wise**, not inside the MC core, packet-wise. Companion to the STAGE 13 back-end
decision; figure: `fig/fig_14_raw_timeline`.

---

## 1. The hazard

The MC core **reorders**. Two mechanisms do it:

- **Out-of-order across banks** — the lookahead bypass + per-bank arb serve a younger request to a
  ready bank ahead of a stalled older one.
- **WLR R/W batching** — reads and writes are grouped by direction per rank to hide turnaround, so
  a read batch can be issued ahead of an older write (or vice-versa).

Neither mechanism looks at whether two requests touch the **same 64 B line**. So a read can pass an
older write to the same line and return **stale data** — the DRAM still holds the pre-write value
because the write has not retired yet. This is the one class of bug a memory controller must never
have: silent data corruption, no error raised.

The three orderings that must be preserved on a shared line:

| hazard | order that must hold | violated when |
|---|---|---|
| **RAW** | write before a later read | read floats ahead of the write → reads old data |
| **WAW** | write before a later write | writes reorder → final value is the older write |
| **WAR** | read before a later write | write floats ahead of the read → read sees new data |

RAW is the common one; all three come from the same reorder freedom and are covered by the same
fix.

---

## 2. Worked example (RAW)

Program order (from the requester): **`W → line X`, then `R → line X`.**

```
cycle   event
------  ----------------------------------------------------------------
 t0     W(X) admitted; write data staged in WD_SRAM. CAS-W not yet issued
        (waits its turn / turnaround / tCCD_L_WR).
 t1     R(X) admitted into the SAME rank lane.
 t2     WLR is in a READS-first batch  ->  R(X) is eligible now,
        W(X) is held for the write batch.
 t3     R(X) wins arb, issues RD to DRAM.
 t4     RD returns  ->  DRAM drove the OLD line X  ->  stale data. BUG.
 t8+    W(X) finally issues, writes the new value  ->  too late.
```

The write's fresh data existed in `WD_SRAM` the whole time — but the read went to DRAM, which had
not been updated. Program order `W < R` was inverted by the batch.

---

## 3. Why it is expensive to catch inside the MC core

The **hash lives in the CIF**, so by the time a request reaches the MC core it is already
`daddr = {rank,bg,bank,row,col}`. The hash is deterministic and 1:1, so **same 64 B line ⟺ same
`daddr`** — line identity *is* `daddr` equality, no aliasing. Detection is not impossible MC-side;
it is just **redundant and badly placed**. To do it in the MC you would have to add, mid-pipe:

- a **dedicated in-flight-write `daddr` CAM** — a whole new structure holding every admitted,
  not-yet-retired write address (the scoreboard stores timing deadlines, not addresses), which
  **duplicates state the CIF ROB already keeps**, and
- **per-packet stall** logic that holds an individual read packet in the lane until the matching
  write retires — and a big request is segmented into many packets, so this fires deep in the pipe,
  one packet at a time.

And a tempting shortcut does **not** work: timestamping the last read / last write in the WLR
arbiter. Without an address match a timestamp is **global**, which forces one of two bad outcomes —
serialize *all* reads behind *all* older writes (kills the reorder engine the controller exists
for), or, with no address compare, miss the actual same-line conflict. The address match is
mandatory; a timestamp alone cannot substitute for it. (And once you *have* the address match, the
requester's arrival order already tells you which op is older — no extra timestamp needed.)

---

## 4. Why CIF wins — the argument

**CIF computes `daddr` and already holds the state.** The hash runs in the CIF, so it has `daddr`
at split time, plus the ROB (per-request order/timestamps) and the AXI handshake. The overlap test
is therefore plain `daddr`-equality against the ROB's set of in-flight writes — **reusing state the
CIF already keeps**, no new structure. The MC would have to rebuild that set in a dedicated CAM.

**Order is free.** Older/younger comes straight from ROB / AXI-request arrival order — no separate
timestamp store, and (per §3) a timestamp without an address match is useless anyway.

**Request-wise stall ≫ packet-wise stall.** This is the decisive point:

- **CIF, request-wise:** stall the whole AXI **read request** at the door — hold `ARREADY` low (or
  side-queue the request) until the conflicting write completes. One handshake. Nothing downstream
  changes.
- **MC, packet-wise:** track and stall **individual packets** mid-pipe — and post-hash the MC
  cannot even cleanly group packets back to a line. More logic, in a hotter path, to do a worse job.

Request-wise is *coarser* (it can stall a few non-conflicting packets of the same request too), but
**same-line overlaps are rare** — caches absorb write-then-immediate-read — so the wasted cycles are
negligible, while the simplification and the correctness guarantee are absolute.

---

## 5. Mechanism at CIF

```
AXI AR (read) arrives
   │
   ▼
compare read line  vs  in-flight write-address set        (from the ROB / a small
   │                    (writes admitted, not yet retired)  write-address table)
   ├─ no overlap ──▶ admit read normally
   └─ overlap ─────▶ HOLD the read  (ARREADY low, or side-queue)
                     release when the conflicting write's completion tag returns
```

Older/younger is read straight off ROB/AXI-request order — no separate timestamp store needed. The
same table and compare cover WAW and WAR (it is a general in-flight-write tracker, not read-only).

---

## 6. The MC-core contract (invariant, not a comment)

> **MC input invariant.** Every request admitted to the MC core is **independently reorderable**.
> Same-line ordering (RAW / WAW / WAR) is guaranteed **upstream by CIF**. The MC core performs
> **no overlap detection** and may reorder freely across banks and R/W batches.

If CIF ever violates this, the failure is **silent stale data**, so it lives in the interface spec
loudly — not as a source comment. The `WR_HAZ` CAM is explicitly **kept out** of the MC core, which
stays a pure reorderable scheduler.

---

## 7. Cost / rarity

Same-line RAW is rare in real traffic: caches absorb the write-then-read pattern before it ever
reaches DRAM. So the coarse, request-wise stall at CIF costs essentially nothing in throughput, and
in exchange the MC core is simpler and **provably correct by construction** — it never has to reason
about coherence at all. Correctness bought with near-zero performance, at the one place in the
pipeline that still has the information to do it cheaply.
