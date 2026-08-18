# RSP — Response Route + Egress Async RESP FIFO (core → CIF)

**Phase 1, block 10.** The downstream-to-CIF boundary. Takes read data (from the fabric)
and write acks (from commit), tags them with `axi_id`, and pushes them to the CIF across
the response async FIFO. KB name: Async RESP FIFO + response path. Thin — the core does
**not** reorder; CIF owns AXI R/B ordering.

Grounded in KB §4 + IO §3. Flow position: **after FAB read return (block 01 §3C)**.

---

## 0. Role + scope

```
FAB.rd (01) ─ read burst {data, id} ──┐
                                       ├─▶ [ RSP: tag + RESP FIFO ] ══ credit push ══▶ [ CIF ]
EMIT commit (02) ─ write ack {id} ─────┘         mc_clk        CDC boundary            not mine
```

Two response sources, one egress. The core's return duty is only: **tag with `id`, push**.
CIF turns pushes into AXI R beats (in `arid` order) and B beats — the core never sequences
them.

---

## 1. Packet format (what leaves)

```
resp_type  2b               00 = RD_DATA, 01 = WR_ACK, 10 = ERR
axi_id     [AXI_ID_WIDTH]    the id that came in on the request
data       [DATA_WIDTH]      RD_DATA only — the read burst
status     [STATUS_EXT]      0 = OK, else error code
last       1b               final beat of this id's burst
```

---

## 2. Two sources, rate-limited (RAW-pause simplification)

- **RD_DATA** — from the fabric read path (block 01 §3C): reassembled burst + `id` (from
  the RD outstanding tracker). One per cycle max.
- **WR_ACK** — from emit/commit (block 02, timing per OW-1): `{id, status}`. One per cycle
  max.

Because **RAW is a pause, not a bypass** (block 05), there is **only one data source**
(DRAM) — the old 2nd hold-forward slot + Merge Unit are retired. A simple 2:1 arbiter
between RD_DATA and WR_ACK feeds the RESP FIFO; a 3rd collision is impossible (each source
rate-limited to 1/cycle).

---

## 3. Reserved-slot gate (the correctness knob, I17)

```
gate_resp_fifo_avail = (local_credit > reserved_slots)
```
- **Every RD reserves a RESP slot at issue time.** The arbiter (block 08) / emit (block 02)
  **must not issue a read** unless `gate_resp_fifo_avail == 1`. This guarantees a landing
  slot exists when the data returns `T_PHY_RDLAT` later — no RESP FIFO overflow, no
  read-return deadlock. (Scheduler invariant: *RD never issues without
  gate_resp_fifo_avail*.)
- Reservation clears when the read's data is pushed (or on error).

---

## 4. CDC protocol (credit-based push, KB §4)

```
MC write side (credit-based):
  FIFO_DEPTH credits at init
  MC sends when gate_resp_fifo_avail == 1    — no combinational wr_full
CIF read side (valid-credit):
  rd_valid + rd_data (registered)
  after consume: credit_return → MC (registered, CIF_clk → MC_clk sync)
```
**valid-only to CIF: no ready from CIF.** The MC self-throttles via
`gate_resp_fifo_avail`; the CIF always accepts immediately.

---

## 5. Interfaces

**In:** `rd_return{data, id, last}` (block 01); `wr_ack{id, status}` (block 02);
`rd_issue_reserve` (from ARB/EMIT, bumps `reserved_slots`).
**Out (MC write side):** `wr_valid`, `wr_data[packet]`, `gate_resp_fifo_avail` (→ ARB/EMIT
read-issue gate), `credit_return` (in, CIF→MC).
**CIF read side:** `rd_valid` (registered), `rd_data`, `rd_credit_ret`.

---

## Open items (RSP)

- **OW-1** write-ack timing — fire at IAF-accept, WR-buffer-accept, or DRAM-commit?
  (response latency vs slot lifetime). Likely WR-buffer-accept (posted-like).
- **OR-1** RESP `FIFO_DEPTH` vs reserved-slot count — depth must cover peak outstanding
  reads so reservations never throttle; pin with the sizing sweep.
- **OR-2** ERR path — how CA-parity/CRC/timeout errors (block 01 §2E) surface as `resp_type
  = ERR` vs the separate error IRQ.
