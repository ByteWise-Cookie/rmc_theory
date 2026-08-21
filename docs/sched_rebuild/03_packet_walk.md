# Packet Walk — one read + one write, ingress FIFO → DRAM → ingress FIFO

**Phase 1, block 03 (and the architecture spine).** We trace a single write and a single
read through the **MC core** — from the ingress async FIFO (CIF boundary) to DRAM and
back. Each stop names and defines the block. This is the redesign backbone.

## Scope (locked)

```
[CIF]  ══IAF══▶  ADEC ─▶ HZU ─▶ BQ ─▶ ARB ─▶ EMIT ─▶ FAB ─▶ PHY ─▶ DRAM
 not mine  (ingress                              (blk02)  (blk01,
           async FIFO)                                    egress CDC)
   ▲                                                                  │
   └══IAF.return══ RSP ◀── FAB.rd ◀──────────────────────────────────┘
```

- **CIF is not my job.** Requests arrive **already formed** over the **ingress async FIFO
  (IAF)**: `{id, addr, dir, size, len, wdata (writes)}`. No AXI channel FSMs, no slot
  alloc, no ATTR RAM on my side — CIF owns those and owns AXI-side R/B reordering.
- **My two boundaries are both async FIFOs:** IAF (CIF side, req in / resp out) and the
  egress CDC inside the **DFI exchange fabric** (block 01, mine).
- The `id` rides through the core untouched and returns with the response so CIF can
  reorder. The core only tracks enough to route data back to the right `id`.

| Tag | Block | Role | Mine? |
|-----|-------|------|-------|
| **IAF** | ingress async FIFO | CIF↔core CDC; req in, resp out | yes (core side) |
| **ADEC** | address decode + align | addr → rank/bg/bank/row/col; size align | yes |
| **HZU** | hazard unit | RAW/WAW/WAR CAM (no-valid-bit, `wr_occupied`) | yes |
| **BQ** | per-bank queues | 16 banks, in-flight FIFOs, ptr occupancy | yes |
| **ARB** | arbiter | FR-FCFS row-hit + row-lock + weight | yes |
| **EMIT** | emit + timing scoreboard | block 02 — prove legal, drive CA | yes |
| **FAB** | DFI exchange fabric | block 01 — pack phases, egress CDC | yes |
| **RSP** | response route | tag read data / write-ack with `id`, push IAF.return | yes |
| CIF | AXI slave | channels, slot/ATTR RAM, AXI reorder | **no** |

---

## 1. WRITE packet walk

### 1.1 IAF — ingress async FIFO (from CIF)
- A formed write request crosses: `{id, addr, dir=W, size, len}` + the write beats
  (`wdata, wstrb, last`). Gray-pointer async FIFO, CIF-clock → `mc_clk`. Backpressure
  (FIFO near-full) folds back to CIF.
- Write descriptor and write data may ride **parallel FIFOs** (req vs data split, like
  mentor's design) so a stalled data path doesn't block descriptors. (OW-3)
- **Out (coreclk):** `{id, addr, dir=W, size, len}` + tagged write payload.

### 1.2 ADEC — address decode + map
- Map `addr` → **{rank, bank-group, bank, row, column}** per address-map policy
  (interleave / hash). DRAM geometry from block-01 `cfg_density`/`cfg_dq_width`.
- Sub-block **offset / LSB alignment** from `size` (8/16/32/64/128 B) → byte-lane
  placement for sub-burst writes (mentor's `offset[2:0]` + `LSB alignment`).
- Attach command intent: WRITE → (ACT if row closed) + WR (+ auto-precharge? OW-5).
- **Out:** `{id, rank, bg, bank, row, col, dir=W, wdata}`.

### 1.3 HZU — hazard unit (RAW / WAW / WAR)
- A new WRITE orders against in-flight same-address accesses. **CAM** matches address;
  **no valid bit** — match gated by `wr_occupied` (write-buffer head/tail pointer range),
  so a retired entry can't false-match.
- WAW same addr → serialize (hold order). WAR (prior read) → read completes first.
- Clean → **non-hazard** path straight to BQ. Hazard → **hazard queue** until the blocker
  drains, then merge (1 request/cycle).
- **Out:** `{id, bank-addr, dir=W, wdata}` cleared to enqueue.

### 1.4 BQ — per-bank queues
- Push into the **bank in-flight FIFO** (16 banks). Occupancy = head/tail pointers + depth
  counter (**no valid bit**). Write payload heads to block-01 §3B WR buffer at emit time.
- Row-hit writes to the open row cluster at head for FR-FCFS.
- **Out:** candidate = queue head, visible to ARB.

### 1.5 ARB — arbiter
- Score bank heads: **FR-FCFS** (row-hit first) + **per-bank row-lock** (freshly-opened
  row holds until demand drains or age-caps) + **weight** `K·control + age + servo`.
  Adaptive R/W batching decides if we're in a write window (`tWTR`, `tCCD_L_WR=48` make
  turnaround costly).
- Winner = next command (ACT or WR) for this bank.
- **Out:** `{cmd, bank-addr, dir=W, id}` → EMIT.

### 1.6 EMIT + SCB — legality (block 02)
- Prove WR (+ any ACT/PRE) JEDEC-legal; drive CA into fabric; **arm WR data launch**
  (`wr_launch` → block-01 WR buffer releases the burst `t_phy_wrlat` after WR hits CA).
- Advance scoreboard (`dqFree=gc+WL+BL/2`, `nWtp=…+tWR`, `nWrRd=…+tWTR`, …).

### 1.7 FAB → PHY → DRAM (block 01)
- WR phased onto CA; write burst launched from the WR buffer through the launch aligner
  onto `dfi_wrdata` at `t_phy_wrlat`/`t_phy_wrdata`; PHY serializes to DRAM.

### 1.8 RSP — write-ack, packet retires
- On commit (accept-vs-DRAM-commit policy, OW-1), **RSP** forms a write-ack `{id, status}`
  and pushes it out **IAF.return** to CIF. CIF turns it into the AXI B beat. Core drops
  any per-`id` tracking. Write done.

---

## 2. READ packet walk

### 2.1 IAF (from CIF)
- Formed read request crosses: `{id, addr, dir=R, size, len}`. No payload.

### 2.2 ADEC — map
- `addr` → {rank, bg, bank, row, col}, dir=R. Intent: (ACT if closed) + RD (+ auto-pre? OW-5).

### 2.3 HZU — hazard (RAW)
- READ vs in-flight WRITE same addr (**RAW**) → wait for the write to drain (default
  serialize; store-forward is OW-2). CAM match gated by `wr_occupied`. Clean → BQ.

### 2.4 BQ — per-bank queue
- Push read; row-hit reads to open row promote. Reads latency-critical → ARB weight favors
  them (the `control` term).

### 2.5 ARB → 2.6 EMIT → 2.7 FAB → DRAM
- ARB picks RD (after any ACT); EMIT proves legal, registers the **RD outstanding tracker**
  entry (block-01 §3C) keyed by `id`; CA phased; DRAM returns data `t_phy_rdlat` later.

### 2.8 FAB.rd — capture + unpack (block 01)
- `dfi_rddata_valid` fires; capture + phase unpacker reassemble the burst; DBI/CRC; RD data
  CDC FIFO crosses to `mc_clk`; return router hands `{burst, id}` up.

### 2.9 RSP — read return, packet retires
- **RSP** pushes `{id, rdata, status, last}` out **IAF.return** to CIF. **CIF** does the
  AXI R-channel ordering/interleave per `id` — not the core. Core drops per-`id` tracking
  on last beat. Read done.

> The core does **not** own AXI read reordering (RDR/RRESP) or write response (BRESP) — the
> earlier spine had those as core blocks; corrected: CIF owns them. Core's return duty is
> just: tag with `id`, push IAF.return.

---

## 3. Block inventory (this pass, corrected)

Core blocks to detail (front-to-back), beyond 01/02:

- **IAF** — ingress async FIFO (req/resp, CIF boundary) — 03a
- **ADEC** — address decode + map + align — 03b
- **HZU** — hazard CAM (no-valid-bit) — 03c
- **BQ** — per-bank queues — 03d
- **ARB** — arbiter — 03e
- **RSP** — response route (thin) — 03f

Detail order: **IAF → ADEC → HZU → BQ → ARB**, then RSP (thin), with EMIT (02) and FAB
(01) already done.

### 3b. Naming + protocol (A5, per block-00 ledger)

Rebuild tags map onto the authoritative KB names (use KB names in RTL):

| Tag | KB name | Key signals |
|-----|---------|-------------|
| IAF | Async REQ FIFO | credit-based push, `credit_return`, `FIFO_DEPTH` |
| ADEC | **AMU** (Address Map Unit) | per-field XOR hash, `split_en`, `xor_shift` |
| HZU | RAW pause + WR_TCAM/BCAM | `wr_occupied`, `blocked`, `raw_block_en` |
| BQ | Per-Bank In-Flight Queue | `queue_head[16]`, `queue_depth[16]`, entry `state` |
| ARB | Weight Arbiter (Stage 3) | `K·control+age+servo`, `last_act_bg` |
| RSP | Async RESP FIFO | `gate_resp_fifo_avail`, `resp_type` |

**Protocol:** every inter-block port inside the core is **valid-credit** (I15) — no
combinational ready, better timing closure. Only the two boundaries differ: the CIF-facing
IAF uses **credit-based push** (I16), and the DRAM-facing FAB speaks DFI. `gate_resp_fifo_avail`
(I17) gates every RD issue so a read never launches without a reserved response slot.

---

## Open items (walk)

- **OW-1** write-ack timing — RSP fires at IAF-accept, at WR-buffer-accept, or at DRAM
  commit? (affects response latency; likely accept-into-WR-buffer for posted-like behavior).
- **OW-2** store-to-load forwarding in HZU — forward or strict serialize on RAW? Default
  serialize.
- **OW-3** req vs data FIFO split at IAF — parallel FIFOs (likely) so data stall ≠
  descriptor stall.
- **OW-4** outstanding-`id` tracking depth in core — minimal (just route-back), but sets
  the RD outstanding tracker size (block-01 §3C).
- **OW-5** auto-precharge (WRA/RDA) vs explicit PRE — interacts with row-lock (ARB).
- **OW-6** address-map policy (interleave/hash) — own doc; ADEC applies it.
