# IAF — Ingress Async Request FIFO (CIF → core)

**Phase 1, block 09.** The upstream boundary of the MC core. Requests cross from the CIF
clock domain into `mc_clk` here, **already formed** — the core does not build them. KB
name: Async REQ FIFO. This is the **one real async FIFO** in the design (block 00: the DFI
side runs at `mc_clk` baseline, so its CDC is degenerate).

Grounded in KB §4 + IO §2. Flow position: **before ADEC (block 04)**.

---

## 0. Role + scope

```
[ CIF ]  ══ credit push ══▶ [ IAF: gray-ptr async FIFO ]  ══ valid-credit ══▶ ADEC (04)
 not mine     CIF clock              CDC boundary                mc_clk
```

**CIF is not my job.** A request arrives as a finished descriptor; the core reads it and
schedules. The IAF's only jobs: cross the clock domain safely, and backpressure the CIF
with credits so it never overflows.

---

## 1. Packet format (what arrives)

```
req_type   1b               0 = RD, 1 = WR
axi_id     [AXI_ID_WIDTH]    rides through the core untouched, returns with the response
addr       [ADDR_WIDTH]      byte address (ADEC maps it)
size       [BURST_WIDTH]     8/16/32/64/128 B (ADEC alignment)
len        [AWLEN_WIDTH]     burst length (CIF pre-split to BL16 granules)
data       [DATA_WIDTH]      WR only — the write beats
mask       [STRB_WIDTH]      WR only — byte strobes
```

The `axi_id` is the core's only handle on ordering — the core carries it through and hands
it back on the response so **CIF** (not the core) can do AXI R/B reordering.

---

## 2. Req vs data split (OW-3)

Descriptor and write payload ride **parallel async FIFOs** — a stalled data path must not
block descriptor flow (mentor splits req vs data likewise):

```
REQ FIFO   : {req_type, axi_id, addr, size, len}     (both R and W)
WDATA FIFO : {data, mask}  tagged to the descriptor   (W only)
```
A read uses only the REQ FIFO. A write's descriptor can admit + classify while its data
still streams in.

---

## 3. CDC protocol (credit-based push, KB §4)

```
CIF write side (credit-based):
  FIFO_DEPTH credits issued at init (= FIFO depth)
  CIF sends when local_credit > 0        — no combinational wr_full
  local_credit -= 1 per push

MC read side (valid-credit):
  rd_valid + rd_data  (registered)
  after consume: credit_return → CIF   (1b registered, MC_clk → CIF_clk sync)
  CIF: local_credit += 1 on receipt
```
Gray-pointer async FIFO for the data crossing; single-bit credit return through a 2-flop
synchronizer. `FIFO_DEPTH` default 16 (= initial credit count).

> **Baseline sync degeneration:** if `mc_clk == cif_clk`, the FIFO collapses to a register
> stage — kept parameterized so an async CIF clock is a config change, not a redesign.

---

## 4. Interfaces

**CIF write side:** `wr_valid`, `wr_data[packet]`, `credit_return` (out, MC→CIF).
`N_REQ_CREDITS = FIFO_DEPTH`. No combinational `wr_full`.
**MC read side (→ ADEC):** `rd_valid` (registered), `rd_data[packet]`, `rd_credit_ret`
(one cycle after consume). Valid-credit.

---

## Open items (IAF)

- **OW-3** req vs data FIFO split — parallel (baseline); confirm the tag binding descriptor
  ↔ its data beats across the two FIFOs.
- **OW-4** outstanding-`id` tracking depth — the core keeps just enough to route the
  response back; sets the RD outstanding-tracker size (block-01 §3C).
- **OI-1** `FIFO_DEPTH` vs CIF burstiness — 16 default; size against the CIF's max
  in-flight so credits never throttle throughput.
