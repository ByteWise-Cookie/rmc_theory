# BQ — Per-Bank In-Flight Queues

**Phase 1, block 07.** Holds classified, hazard-cleared requests after admission — one
FIFO per bank. Only the **head** is active in the command pipe. Occupancy = **head/tail
pointers**, no valid bit. KB name: Per-Bank In-Flight Queue (§9E).

Grounded in KB §9E (v1.9.9) + the datapath sizing floor (block 00 I24).

---

## 0. Role

```
HZU evict ──▶ [ bank 0 FIFO ] head ──┐
              [ bank 1 FIFO ] head ──┤
                    ...              ├──▶ 16 heads = candidate set → ARB (block 08)
              [ bank 15 FIFO] head ──┘
```

After admission, a request lives in its bank's FIFO in **arrival order** (natural row
locality). The arbiter only ever sees the 16 heads — the residency split (short TCAM →
per-bank FIFO) is what makes the candidate set small and CAM-free.

---

## 1. Structure

16 FIFOs per rank (`[N_RANKS][16]`). Per entry:

| Field | Width | Meaning |
|-------|-------|---------|
| `rw` | 1 | R / W (unified queue + tag; split-queue is a sweep variant) |
| `seqnum` | SEQ_BITS | program order (RAW / retirement) |
| `bg`, `bank` | BG_BITS, BANK_BITS | target (redundant with FIFO index, carried for emit) |
| `row`, `col` | ROW_BITS, COL_BITS | target address |
| `state` | 2 | NEED_PRE / NEED_ACT / NEED_CAS / DONE (command-progress) |
| `blocked` | 1 | RAW-held (set at admission; cleared on write drain) |

```
depth per bank : 8 (swept, OQ-20) ; total in-flight = N_BANKS × depth ≤ 128 ; tcam = 32
head-only      : head asserts one ready-bit per class → can_pre/act/cas[16] to arbiter
                 the next_cas/pre/act TIMERS are per-bank SCOREBOARD props (block 02),
                 NOT per-entry — the head reads them; deeper entries just wait
advance        : head self-advances state locally as ACT/PRE/CAS issue (thread model);
                 on CAS done → retire, pop, next entry becomes head next cycle
occupancy      : head/tail pointers + depth counter + full flag = relocated watermark →
                 admission backpressure. NO per-entry valid bit — head..tail = occupied,
                 rest empty by construction.
owner          : allocator / watermark manager (R/W). Scheduler + arbiter: READ head only.
```

---

## 2. No valid bit (mentor)

Occupancy is the **FIFO pointers**, full stop. `head..tail` is the live range; everything
else is empty by construction. The relocated watermark logic (inv-LSB priority encoder +
depth popcount) counts queue depth, not TCAM rows, and feeds admission backpressure
(`queue_full[bank]` → HZU holds eviction). This is the same no-valid-bit discipline as the
WR_TCAM `wr_occupied` gate (block 05) — pointers define liveness everywhere.

---

## 3. Row locality + command-progress

- Arrival order preserves natural **row locality** — requests to the same open row cluster
  near the head, so FR-FCFS promotion (block 08 ARB) finds row-hits at the head.
- The head's `state` is the **command-progress thread**: NEED_ACT (bank idle) → NEED_CAS
  (row open) → DONE (CAS issued, retire). NEED_PRE when the head needs a row closed first.
  Stage-4 emit (block 02) advances it; the arbiter reads it.

---

## 4. Sizing (OW-7 — RESOLVED by sweep)

Sweep `tools/sched_model/sweep_ow7.js` (`OW7_RESULTS.md`) on the RTL-reference arbiter:

- **N_RD = 32, N_WR = 96 (3×)** — the sweep optimum (busy 41%, readMean 1026).
- **Plan's 64/64 is the *worst* tested point** (busy 39%, readMean 1933 — ~2× read
  latency). Symmetric over-buffers reads and under-buffers writes.
- **Reads want shallow:** busy saturates at rdCap≈32; rd64 *regresses* (piled-up reads →
  more ACTs/contention). Floor ≥24.
- **Writes want deep:** busy climbs with wrCap, saturates ~96 (accumulate + background
  drain via adaptive batching — the throughput lever).
- **Datapath floor (I24):** row-miss lookahead ≈ `T_RCD+T_RP` ≈ 10 bursts is served by
  `tcam`(32) + `bankDepth`(8×16=128); rdCap only needs ≥24 to feed it — 32 clears it.

Confirms **KB §25** exactly. Sweep design point (OQ-20): `bankDepth=8`, `tcam=32`,
in-flight ≤128. pkg intent `N_RD_ENTRIES=32`, `N_WR_ENTRIES=96`; edit at RTL-go.

---

## 5. Interfaces (valid-credit)

**In (from HZU, block 05):** `evict_en`, `evict_bank`, `evict_entry{...}`.
**Backpressure out:** `queue_full[N_BANKS]` → HZU (admission stall).
**To arbiter (block 08):** `queue_head[N_BANKS]{rw, row, col, state, seqnum}`,
`queue_depth[N_BANKS]`, and the per-class head ready-bits `can_pre/act/cas[16]` (derived
from the head's `state` × block-02 `can_*`).
**Retire:** on CAS-done → pop head, advance tail-of-life pointer.

---

## Open items (BQ)

- **OW-7** read vs write buffer depth (64/64 vs 2–3×) — **sizing sweep**, floored by the
  ~10-burst lookahead (I24).
- **OQ-20** bankDepth swept to 8 (DONE); revisit if the lookahead floor forces deeper.
- **OB-1** unified-queue + `rw` tag vs split RD/WR queues — sweep variant; unified is the
  baseline.
- **OB-2** head-of-line blocking on `blocked` (RAW-held) entries — does a blocked head stall
  the whole bank FIFO, or can a younger same-bank request pass? (Default: FIFO order — no
  pass; confirm this doesn't starve a bank behind one RAW.)
