# Packet Walk — one AXI read + one AXI write, CIF → DRAM → CIF

**Phase 1, block 03 (and the architecture spine).** We trace a single write transaction
and a single read transaction from the **CIF (AXI ingress)** through every block to the
DRAM and back. Each stop *names and defines* the block the packet touches. This is the
redesign backbone — the block list falls out of the walk.

Front-end = **AXI slave** (CIF). Back-end = DFI (block 01). Legality = emit/scoreboard
(block 02). Everything between is defined here.

---

## 0. The spine (blocks, in path order)

```
        CIF ─▶ SLOT/ATTR ─▶ ISO-FIFO(cdc) ─▶ ADEC ─▶ HZU ─▶ BQ ─▶ ARB ─▶ EMIT ─▶ FAB ─▶ PHY ─▶ DRAM
      (AXI slave)  (id ram)   (Iface→core)   (map)  (RAW)  (bank q) (pick) (blk02) (blk01)
        ▲                                                                                    │
        │                                                                                    ▼
        └──────── RDR (reorder) ◀── FAB.rd ◀────────────────────────────────────────── read data
        └──────── WRSP (B chan)  ◀── FAB.wr-ack / commit
```

| Tag | Block | Role |
|-----|-------|------|
| **CIF** | AXI ingress | AR/AW/W/R/B slave channels, handshakes, credit |
| **SLOT** | slot-ID alloc + ATTR RAM | assign a tracking slot, stash AXI attributes |
| **ISO** | isolation CDC FIFO | Ifaceclk → coreclk crossing (per port) |
| **ADEC** | address decode + align | AXI addr → rank/bg/bank/row/col; LSB align by size |
| **HZU** | hazard unit | RAW/WAW/WAR detect (no-valid-bit, `wr_occupied` gate) |
| **BQ** | per-bank queues | 16 banks, in-flight FIFOs, occupancy = head/tail ptrs |
| **ARB** | arbiter | FR-FCFS row-hit + per-bank row-lock + weight score |
| **EMIT** | emit + timing scoreboard | block 02 — prove legal, drive CA |
| **FAB** | DFI exchange fabric | block 01 — pack phases, cross clocks |
| **RDR** | read return + reorder | reassemble, reorder per AXI ID, drive R channel |
| **WRSP** | write response gen | commit → BRESP → B channel |

---

## 1. WRITE packet walk

An AXI master issues a write burst. Follow it.

### 1.1 CIF — AXI ingress (AW + W)
- **AW channel** lands: `awid, awaddr, awlen, awsize, awburst, awcache, awprot, awregion,
  awvalid/awready`. CIF accepts when it has a free slot (below).
- **W channel** streams `wdata, wstrb, wlast, wvalid/wready` — the burst beats.
- CIF is pure protocol: handshake, backpressure (`awready/wready` deassert when full),
  no decode yet. One AXI port = one CIF instance (mentor's per-channel IF_MFIFO analog;
  here an AXI request FIFO + a write-data FIFO).
- **Out:** `{awid, addr, len, size, burst, attr}` + the write beats.

### 1.2 SLOT — slot-ID allocation + ATTR RAM
- Allocate a **slot-ID** (free-list pop). The slot is the transaction's handle for its
  whole life; freed at WRSP.
- Write the AXI attributes into **ATTR RAM[slot]**: `awid, len, size, burst, cache, prot,
  region`, and the byte offset. These don't travel with the packet downstream — only the
  slot-ID does; downstream reads ATTR RAM when it needs them (response gen, reorder).
- **Offset / LSB alignment:** from `awsize` (8/16/32/64/128 B) compute the sub-block
  offset `offset[2:0]` and the aligned base — mirrors mentor's `Attmem=offset[2:0]` +
  `LSB alignment`. This is where a sub-cacheline write's byte lanes get placed.
- **Out:** `{slot, aligned_addr, size, is_write}` + write beats tagged with `slot`.

### 1.3 ISO — isolation CDC FIFO (Ifaceclk → coreclk)
- AXI runs on the interface clock; the scheduler core runs on `mc_clk`. The request
  descriptor + write beats cross here (mentor's **ISO PTC FIFO**).
- Gray-pointer async FIFO; backpressure folds back to CIF `awready/wready`.
- Baseline may be synchronous (same clock) → degenerates to a register stage, FIFO kept
  parameterized (same discipline as block-01 CDC).
- **Out (coreclk):** request descriptor + write payload.

### 1.4 ADEC — address decode + map
- Map `aligned_addr` → **{rank, bank-group, bank, row, column}** per the address-map
  policy (interleave / bank-hash). This is where the DRAM geometry (block-01
  `cfg_density`/`cfg_dq_width`) picks bank count.
- Attach the command intent: WRITE → will need (ACT if row closed) + WR (+ WRP auto-pre?).
- **Out:** `{slot, rank, bg, bank, row, col, dir=W}`.

### 1.5 HZU — hazard unit (RAW / WAW / WAR)
- A new WRITE must order against in-flight accesses to the same address. The **CAM**
  matches address; **no valid bit** — the match is gated by `wr_occupied` (the write
  buffer's head/tail pointer range), so a retired entry can't false-match.
- WRITE vs prior WRITE (WAW) same addr → must serialize (keep order).
- WRITE vs prior READ (WAR) → the read must complete first.
- If clean (no hazard) → **non-hazard decode** path, straight to BQ. If hazard → hold in a
  **hazard queue** until the blocking entry drains, then merge (mentor's *Merge, 1
  request/cycle*).
- **Out:** `{slot, bank-addr, dir=W}` cleared for enqueue.

### 1.6 BQ — per-bank queues
- Push the write into the **bank's in-flight FIFO** (16 banks). Occupancy = head/tail
  pointers + depth counter (**no valid bit**). Write payload sits in the WR data staging
  (heads toward block-01 §3B WR buffer at emit time).
- Row-hit grouping: writes to the currently-open row cluster at the head for FR-FCFS.
- **Out:** candidate = queue head, visible to ARB.

### 1.7 ARB — arbiter
- Among all bank heads, score candidates: **FR-FCFS** (row-hit first) + **per-bank
  row-lock** (a freshly-opened row holds until its demand drains or age-caps) + **weight**
  = `K·control + age + servo`. Adaptive R/W batching decides whether we're in a write
  burst window (writes are expensive to turn around — `tWTR`, `tCCD_L_WR=48`).
- The winner is the next command (ACT or WR) for this packet's bank.
- **Out:** `{cmd, bank-addr, dir=W, slot}` → EMIT.

### 1.8 EMIT + SCB — legality (block 02)
- Prove the WR (and any needed ACT/PRE) JEDEC-legal against the scoreboard; drive CA into
  the fabric; **arm the WR data launch** (`wr_launch` → block-01 WR buffer releases the
  burst `t_phy_wrlat` after the WR hits CA).
- Advance scoreboard: `dqFree=gc+WL+BL/2`, `nWtp=…+tWR`, `nWrRd=…+tWTR`, etc.

### 1.9 FAB → PHY → DRAM (block 01)
- WR command phased onto the CA bus; write burst launched from the WR buffer through the
  launch aligner onto `dfi_wrdata` at `t_phy_wrlat`/`t_phy_wrdata`. PHY serializes to DRAM.

### 1.10 WRSP — write response (B channel), packet retires
- Once the write is committed (accepted into the WR buffer / write is non-posted per
  policy), **WRSP** generates `bresp` (OKAY/SLVERR), reads `awid` from **ATTR RAM[slot]**,
  drives the **B channel** (`bid=awid, bresp, bvalid/bready`) back through ISO → CIF.
- **Free the slot** (return to free-list). Write packet done.

---

## 2. READ packet walk

### 2.1 CIF — AXI ingress (AR)
- **AR channel**: `arid, araddr, arlen, arsize, arburst, arcache, arprot, arregion,
  arvalid/arready`. Accept on free slot.
- **Out:** `{arid, addr, len, size, burst, attr}`.

### 2.2 SLOT + ATTR RAM
- Allocate slot; stash attributes + `arid` + offset/alignment (same as write). The slot
  is what the returned data will be matched against for **AXI read-ordering per ID**.

### 2.3 ISO (Iface → core)
- Descriptor crosses to coreclk. (No write payload for reads.)

### 2.4 ADEC — map
- `addr` → {rank, bg, bank, row, col}, dir=R. Command intent: (ACT if closed) + RD
  (+ RDA auto-pre?).

### 2.5 HZU — hazard (RAW)
- READ vs in-flight WRITE same addr (**RAW**) → must wait for the write to drain (or
  forward, if a store-forward path is in scope — default: serialize). CAM match gated by
  `wr_occupied`. Clean → non-hazard path to BQ.
- **Out:** `{slot, bank-addr, dir=R}`.

### 2.6 BQ — per-bank queue
- Push read into the bank FIFO; row-hit reads to the open row promote for FR-FCFS. Reads
  are latency-critical → arbiter weight favors them (the `control` term).

### 2.7 ARB → 2.8 EMIT → 2.9 FAB → DRAM
- Arbiter picks RD (after any ACT); EMIT proves legal, registers the **RD outstanding
  tracker** entry (block-01 §3C) keyed by slot; CA phased; DRAM returns data
  `t_phy_rdlat` later.

### 2.10 FAB.rd — capture + unpack (block 01)
- `dfi_rddata_valid` fires; capture buffer + phase unpacker reassemble the burst; DBI/CRC;
  RD data CDC FIFO crosses back to coreclk; return router hands `{burst, slot}` up.

### 2.11 RDR — read return + reorder (R channel), packet retires
- AXI requires **read data returned in order per ID** (and interleaving rules across IDs).
  RDR holds a **reorder buffer** keyed by slot/`arid`; when the burst for the next-expected
  beat of that ID is ready, drive the **R channel**: `rid=arid, rdata, rresp, rlast,
  rvalid/rready` — reading `arid`/`len` from **ATTR RAM[slot]**.
- Beats stream out (`rlast` on final). **Free the slot.** Read packet done.

---

## 3. What the walk pinned (block inventory, this pass)

New blocks defined by the walk (beyond 01/02):

- **CIF** (AXI slave) — 03a
- **SLOT + ATTR RAM** — 03b
- **ISO CDC FIFO** — 03c
- **ADEC** (address map + align) — 03d
- **HZU** (hazard CAM, no-valid-bit) — 03e
- **BQ** (per-bank queues) — 03f
- **ARB** (arbiter) — 03g
- **RDR** (read reorder / R channel) — 03h
- **WRSP** (write response / B channel) — 03i

Each becomes its own detailed block (like 01/02) next. Order to detail them: **CIF →
SLOT → ISO → ADEC → HZU → BQ → ARB → RDR/WRSP**, i.e. front-to-back, the way the packet
flows.

---

## Open items (walk)

- **OW-1** posted vs non-posted writes — does WRSP fire at accept or at DRAM-commit?
  (affects B-channel latency + slot lifetime).
- **OW-2** store-to-load forwarding in HZU — forward or strict serialize on RAW? Default
  serialize; forwarding is a later optimization.
- **OW-3** write data path vs descriptor path — do beats ride the same ISO FIFO or a
  parallel data FIFO? (mentor splits req vs data — likely parallel.)
- **OW-4** slot count = max outstanding transactions — sets ATTR RAM depth + free-list
  width; pin with the AXI outstanding target.
- **OW-5** auto-precharge (WRA/RDA) vs explicit PRE — policy interacts with row-lock (ARB).
- **OW-6** address-map policy (interleave/hash) — its own doc; ADEC just applies it.
