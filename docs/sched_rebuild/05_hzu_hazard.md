# HZU — Hazard Unit (RAW pause + WR_TCAM/BCAM)

**Phase 1, block 05.** Orders a new request against in-flight accesses to the same address
before it enters the per-bank queues. Detects RAW / WAW / WAR; **RAW is a pause, not a
bypass** (mentor review). KB name: RAW handling + WR_TCAM.

Grounded in KB §6/§7/§11 (v1.9.9 pause model, no-valid-bit gating).

---

## 0. Role

```
{rank,bg,bank,row,col, dir, seqnum} ──▶ [ CAM match vs pending writes ]
                                            │
                     clean (non-hazard) ────┴──▶ evict to BQ (block 07)
                     hazard ─────────────────▶ hold (blocked=1), no evict
```

A read must not pass an older write to the same address; two writes to the same address
must keep program order. The HZU is the ordering gate between admission and the bank
queues.

---

## 1. WR_TCAM / RAW BCAM

- **WR_TCAM** — full-address exact match `{bg, bank, row, col}`, `N_WR_ENTRIES`. Carries
  `req_type=WR`, `axi_id`, `entry_idx`, `seqnum`.
- **RAW BCAM** — XOR-based exact match cells (~6T/bit) for the RAW search primitive.
- **No valid bit (v1.9.9).** A match is gated by **`wr_occupied[i]`** — decoded from the
  write buffer's **head/tail pointer range**. A retired entry's stale contents can never
  false-match. Power-gated by pointer decode.
  ```
  raw_hit_vector[i] = cam_match[i] AND wr_occupied[i]
  ```
- **Multi-hit:** winner = oldest by program order (`seqnum`) / `argmax(age)`.

---

## 2. Hazard cases

| New req | vs in-flight | Hazard | Action |
|---------|--------------|--------|--------|
| READ | older WRITE same addr | **RAW** | pause: `blocked=1`, hold until write drains |
| WRITE | older WRITE same addr | **WAW** | serialize by `seqnum` (keep order) |
| WRITE | older READ same addr | **WAR** | read completes first |
| any | no match | — | non-hazard → evict to BQ |

### RAW = pause (v1.9.9, KB §11)
```
Detect at admission: read's full-addr search hits a pending, older, not-yet-emitted write
                     to the same address (seqnum = program order).
On hit:  set entry.blocked=1 (pin bit, on the READ side) — do NOT evict to bank queue.
Hold:    keep the read in the admission station until the blocking write retires.
Then:    clear blocked, evict to BQ; read proceeds through the normal DRAM path.
Cost:    the rare RAW read eats the write's latency serially — no forward, no reorder.
```
**What the pause retires** (vs the old bypass): the 2nd hold-forward slot, the Merge Unit,
and the `merge_pending`/`wdb_entry_idx` status fields. Only one response source remains
(DRAM), so downstream queues stay CAM-free — RAW is never re-checked after admission.

- **Non-hazard decode** → straight path to BQ. **Hazard** → hazard hold; on release, the
  **merge (1 request/cycle)** admits it (mentor's Merge). `raw_block_en` gates **eviction**,
  not a bypass mux.
- **Golden-model proxy:** `{rank,bank,row}` (no column) — conservative (may over-pause, never
  under-pause). RTL uses full `{bg,bank,row,col}`.

---

## 3. Residency (short admission, KB §6)

The WR_TCAM is a **short admission/classify station**, not a lifetime home. An entry is
searched + RAW-compared on admission, then (if clean) evicted into its per-bank in-flight
FIFO (block 07), freeing the slot. Dwell = burst+classify window, not the full ~118 tCK
latency window. TCAM depth `N_WR_ENTRIES` sized to the admission rate, not residency.

- The **RD pre-filter is retired** (v1.9.9): the read side no longer searches a
  `{bg,bank}` ternary TCAM — the candidate set is the per-bank queue heads (block 07). Only
  the WR_TCAM (for RAW) survives.

---

## 4. Interfaces (valid-credit)

**In (from ADEC, block 04):** `{rank, bg, bank, row, col, dir, size, seqnum, id}`.
**Search:** `raw_search_key[{bg,bank,row,col}]`, reads `wr_occupied`, `wr_status_age`.
**Out (to BQ, block 07):** `evict_en`, `evict_bank`, `evict_entry{rw,seqnum,bg,bank,row,col,
state,blocked}`; `raw_block_en` (held, not evicted); `queue_full[N_BANKS]` backpressure.
**Retire:** on blocking-write retire → clear `blocked`, release the held read.

---

## Open items (HZU)

- **OW-2** store-to-load forwarding — forward covered bytes vs strict serialize on RAW.
  Default: serialize (pause). Forwarding is a later optimization (re-introduces a merge).
- **OH-1** WR_TCAM depth vs admission rate — size so admission never stalls under peak
  write bursts; pin with the sizing sweep.
- **OH-2** WAR handling — is a write-after-read gated in the HZU, or naturally ordered by
  the read already being in a bank queue? Confirm the WAR path.
- **OH-3** cross-page RAW (same bank, different row) — conservative proxy pauses; confirm
  full-key precision doesn't over-serialize.
