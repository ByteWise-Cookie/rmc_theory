# DFI ⇄ MC-core Exchange Fabric — register & buffer enumeration

**Phase 1, block 1.** The boundary block between the MC scheduler core and the DFI
port. Everything the core hands the PHY, everything the PHY hands back, and every
register that configures, observes, or errors that exchange lives here.

Grounded in **DFI 5.2** signal groups + the RMC clock plan. Numbers/latencies are
programmable — exact values land in the timing pass; this doc fixes the *structure*.

---

## 0. Where it sits, what it does

```
   MC core (scheduler)            EXCHANGE FABRIC              DFI port → PHY → DRAM
   ┌──────────────┐        ┌───────────────────────────┐        ┌──────────┐
   │ cmd emit     │──cmd──▶│ CA out path  → phase pack  │──DFI──▶│          │
   │ write data   │──wr───▶│ WR out path  → phase pack  │──DFI──▶│   PHY    │
   │ read return  │◀──rd───│ RD in  path  ← phase unpack│◀─DFI───│          │
   │ maint/refresh│◀─stat─▶│ update / status / error    │◀─DFI──▶│          │
   └──────────────┘        │ config + timing CSRs       │        └──────────┘
                           └───────────────────────────┘
```

Three jobs:
1. **Serialize/deserialize** — core speaks 1 command / 1 burst per transaction; DFI
   speaks *phases* (`dfi_*_pN`). Fabric packs core→phases, unpacks phases→core, per
   the gear ratio.
2. **Cross clocks** — core clock and DFI/PHY clock need not be edge-aligned. Data,
   command, and handshakes cross through CDC structures here.
3. **Hold the CSRs** — all DFI config, latency, status, update, and error state.

---

## 1. Clock domains & gear ratio

Two domains touch this fabric:

| Domain | Clock | Runs |
|--------|-------|------|
| `core` | `mc_clk` | scheduler, queues, arbiter, scoreboard |
| `dfi`  | `dfi_clk` | DFI port I/O, phase pack/unpack |

- **DRAM `tCK`** is faster still, PHY-internal. Fabric never sees `tCK` directly — the
  **gear ratio** abstracts it: 1 `dfi_clk` = *G* `tCK`.
- `dfi_freq_ratio` (`dfi_cmd_freq_ratio` / `dfi_data_freq_ratio`):
  - **1:1** → G=1 → 1 phase/`dfi_clk` (`_p0` only)
  - **1:2** → G=2 → 2 phases (`_p0`,`_p1`)
  - **1:4** → G=4 → 4 phases (`_p0`..`_p3`)
- **Worst case span = 1:1 … 1:4.** Fabric buffers/packers must parameterize on G. Phase
  count `NPH = G`; data-word count `NW = G` (each word = DQ×2, double-edge packed).
- If `mc_clk == dfi_clk` (planned baseline), CDC degenerates to a same-clock register
  stage — the CDC FIFOs stay in the design (parameterized depth ≥1) so an async ratio
  is a config change, not a redesign.

---

## 2. Register classes (CSR map)

Five classes. Address map is a later pass; here we fix **what exists**.

### 2A. Static configuration (RW, programmed once at init, then stable)

| Reg | Width | Meaning |
|-----|-------|---------|
| `cfg_freq_ratio`      | 2b  | 00=1:1, 01=1:2, 10=1:4 (drives NPH/NW everywhere) |
| `cfg_2n_mode`         | 1b  | 1=2N geardown on CA (DDR5 power-on default), 0=1N |
| `cfg_dram_density`    | 3b  | 8Gb/16Gb/24Gb/32Gb → bank count, tRFC select |
| `cfg_dq_width`        | 2b  | x4/x8/x16 (sets DQ lanes, wrdata width, banks-per-BG halving) |
| `cfg_rank_count`      | 2b  | ranks present (drives `dfi_cs` fan, per-rank timing) |
| `cfg_bl_mode`         | 2b  | BL16 / BL32 / BC8-OTF / BL16-OTF |
| `cfg_geardown_en`     | 1b  | DDR5 1N/2N geardown enable mirror |
| `cfg_dbi_wr_en`       | 1b  | write DBI enable |
| `cfg_dbi_rd_en`       | 1b  | read DBI enable |
| `cfg_ca_parity_en`    | 1b  | CA parity generation enable |
| `cfg_wr_crc_en`       | 1b  | write CRC enable |
| `cfg_rd_crc_en`       | 1b  | read CRC check enable |
| `cfg_odt_en`          | 1b  | ODT drive enable |
| `cfg_cs_map`          | Nb  | logical rank → `dfi_cs` bit mapping |

### 2B. Timing configuration (RW, PHY-negotiated latencies — DFI 5.2 `tphy_*`)

All in `dfi_clk` cycles unless noted. These set the fabric's pipe depths and the
release/capture offsets for the data buffers.

| Reg | Meaning |
|-----|---------|
| `t_phy_wrlat`      | WR command → assert `dfi_wrdata_en` (write launch offset) |
| `t_phy_wrdata`     | `dfi_wrdata_en` → `dfi_wrdata` valid (data-vs-enable skew) |
| `t_phy_rdlat`      | RD command → `dfi_rddata` returns |
| `t_rddata_en`      | RD command → assert `dfi_rddata_en` (read window open) |
| `t_phy_wrcslat`    | WR `dfi_wrdata_cs` lead |
| `t_phy_rdcslat`    | RD `dfi_rddata_cs` lead |
| `t_ctrl_delay`     | control-signal (CKE/ODT/etc.) pipeline delay |
| `t_dram_clk_enable`| clock-enable assert → stable |
| `t_wrdata_delay`   | fabric-side write-data staging delay |
| `t_phy_wrlvl_*`    | write-leveling latencies (training) |
| `t_phy_rdlvl_*`    | read-leveling / gate-training latencies |

> These are **inputs** to buffer sizing: RD buffer depth ≥ `t_phy_rdlat` worth of
> outstanding phases; WR buffer must hold data from enqueue until `t_phy_wrlat`.

### 2C. Live status (RO, sampled from DFI + fabric internals)

| Reg | Width | Meaning |
|-----|-------|---------|
| `sts_init_complete`   | 1b | `dfi_init_complete` seen — PHY/DRAM up |
| `sts_dram_clk_state`  | 1b | DRAM clock enabled/disabled |
| `sts_wr_buf_level`    | log2 | write-data buffer occupancy |
| `sts_rd_buf_level`    | log2 | read-data buffer occupancy |
| `sts_ca_buf_level`    | log2 | CA/command out buffer occupancy |
| `sts_wr_cdc_full`     | 1b | write CDC FIFO full flag |
| `sts_rd_cdc_full`     | 1b | read CDC FIFO full flag |
| `sts_lp_state`        | 2b | low-power handshake state |
| `sts_upd_state`       | 2b | ctrlupd/phyupd handshake state |
| `sts_training_state`  | 3b | current training phase (idle/wrlvl/rdlvl/…) |
| `sts_freq_ratio_now`  | 2b | active gear ratio (post frequency-change) |

### 2D. Update / handshake registers (RW/RO pairs — DFI update FSMs)

DFI has three update handshakes; fabric owns the MC side of each.

| Handshake | Signals | Fabric reg |
|-----------|---------|------------|
| **Controller update** | `dfi_ctrlupd_req` / `_ack` | `upd_ctrl_req` (W1S), `upd_ctrl_ack` (RO), `upd_ctrl_interval` (RW timer) |
| **PHY update** | `dfi_phyupd_req` / `_ack` / `_type` | `upd_phy_req` (RO), `upd_phy_ack` (W1S), `upd_phy_type` (RO) |
| **PHY master** | `dfi_phymstr_req` / `_ack` / `_cs_state`/`_state_sel` | `upd_phymstr_req` (RO), `upd_phymstr_ack` (W1S), `upd_phymstr_state` (RO) |
| **Freq change** | `dfi_freq_ratio` / `dfi_freq_fsp` | `upd_freq_req` (W1S), `upd_freq_ratio` (RW), `upd_freq_ack` (RO) |

> **Interlock:** when a `ctrlupd`/`phyupd` is in flight the fabric must quiesce the CA
> path (no new commands crossing) — a status bit `sts_ca_quiesced` gates the emit
> stage. This is the hook the scheduler's maintenance/refresh path reads.

### 2E. Error / interrupt registers (RO + W1C)

| Reg | Width | Meaning |
|-----|-------|---------|
| `err_dfi_error`      | 1b   | `dfi_error` asserted (W1C) |
| `err_dfi_error_info` | Nb   | captured `dfi_error_info` code |
| `err_wr_cdc_ovf`     | 1b   | write CDC overflow (W1C) — should never fire, backpressure bug |
| `err_rd_cdc_ovf`     | 1b   | read CDC overflow (W1C) |
| `err_rddata_timeout` | 1b   | RD launched, no `dfi_rddata_valid` within window (W1C) |
| `err_ca_parity`      | 1b   | CA parity error reported by DRAM (W1C) |
| `err_wr_crc`         | 1b   | write CRC error alert (W1C) |
| `err_rd_crc`         | 1b   | read CRC mismatch (W1C) |
| `err_underrun_wr`    | 1b   | `dfi_wrdata_en` high but buffer empty (W1C) — timing bug |
| `err_mask`           | Nb   | per-source interrupt mask (RW) |
| `err_status`         | Nb   | live OR of unmasked error bits (RO) → interrupt line |

---

## 3. Buffers (data-path)

Three transfer buffers + their CDC crossings. All parameterized on G (gear ratio).

### 3A. CA / command out path  (core → DFI)

- **Command out FIFO** — holds emitted commands (opcode + bank/bg/row/col + CID + rank)
  waiting to be phased onto `dfi_address[13:0]` / `dfi_cs` / `dfi_act_n`.
- **Phase packer** — expands 1 command into its CA phases:
  - 1-cycle command (REF/PRE/MPC/powerdown/Vref) → 1 phase slot.
  - 2-cycle command (ACT/RD/WR/WRP/MRW/MRR) → 2 phase slots; in **2N** the 2nd half is
    driven 2 `tCK` later, in 1N adjacent.
  - packer maps slots onto `_p0.._p(G-1)` per gear ratio; if a command's 2 halves span
    a `dfi_clk` boundary at low G, packer carries the tail into the next phase group.
- **CS/CKE/ODT lane driver** — per-phase `dfi_cs`, `dfi_cke`, `dfi_odt`, `dfi_reset_n`,
  timed by `t_ctrl_delay`.
- **CA parity gen** (if `cfg_ca_parity_en`).
- Depth: shallow (≥ NPH + slack); CA budget is 1 command / 2 `tCK`, packer never starves
  if scheduler respects `caFree`.

### 3B. Write data out path  (core → DFI)

- **Write-data buffer** — holds the full burst (BL16 → 16 UI × DQ bits) + write mask +
  optional DBI/CRC, from the cycle the scheduler commits the WR until `t_phy_wrlat`
  after the WR command reaches the CA bus. Core must hold data for the launch latency —
  this buffer *is* that hold.
  - Entry = one burst. Depth ≥ max outstanding writes in the wrlat window (≈
    `ceil(t_phy_wrlat / burst_spacing)` + margin).
  - Width per phase = `dfi_wrdata_pN` = DQ×2 (double-edge). NW words = G.
- **Write-mask lane** — `dfi_wrdata_mask` packed alongside.
- **WR data CDC FIFO** — if `mc_clk ≠ dfi_clk`, burst crosses here. Async FIFO,
  gray-pointer, `sts_wr_cdc_full` / `err_wr_cdc_ovf`.
- **Launch aligner** — asserts `dfi_wrdata_en` `t_phy_wrlat` after WR, drives
  `dfi_wrdata` `t_phy_wrdata` after enable; `dfi_wrdata_cs` led by `t_phy_wrcslat`.
- **Underrun guard** — `err_underrun_wr` if enable window opens on empty buffer.

### 3C. Read data in path  (DFI → core)

- **RD outstanding tracker** — for each launched RD, records expected return slot,
  rank/CID, target queue entry, so returned phases route back to the right requester.
  Sized ≥ commands in flight over `t_phy_rdlat`.
- **Read-data capture buffer** — captures `dfi_rddata_pN` when `dfi_rddata_valid`
  asserts (`t_phy_rdlat` after RD, window opened by `dfi_rddata_en` at `t_rddata_en`).
  - **Phase unpacker** — reassembles G phase-words into the full burst.
  - DBI decode (if `cfg_dbi_rd_en`), CRC check (`cfg_rd_crc_en` → `err_rd_crc`).
- **RD data CDC FIFO** — crosses `dfi_clk` → `mc_clk`. `sts_rd_cdc_full` /
  `err_rd_cdc_ovf`.
- **Return router** — hands the reassembled burst + tag back to the core's read-return
  path.
- **Timeout guard** — `err_rddata_timeout` if valid never arrives in window.

---

## 4. CDC crossing structures (summary)

| Crossing | Direction | Structure | Flags |
|----------|-----------|-----------|-------|
| Command  | core→dfi | gray-ptr async FIFO (or reg stage if synchronous) | `sts_ca_buf_level` |
| Write data | core→dfi | async FIFO, burst-wide | `sts_wr_cdc_full`, `err_wr_cdc_ovf` |
| Read data | dfi→core | async FIFO, burst-wide | `sts_rd_cdc_full`, `err_rd_cdc_ovf` |
| Handshakes | both | 2-flop synchronizers (req/ack, pulse→level→pulse) | per handshake |
| CSR access | core→dfi | 2-flop sync on control bits; status re-synced back | — |

**Rule:** every multi-bit field crossing domains goes through a FIFO or is captured on a
single synchronized enable — no bit-by-bit 2-flop on buses. Single-bit control/status →
2-flop synchronizers. Req/ack handshakes use the standard 4-phase level protocol.

---

## 5. What the scheduler core sees (the fabric's core-side contract)

Ports the scheduler talks to (names align later with `RMC_IO_Map`):

- `caFree` / `ca_credit` — from CA out FIFO: may I emit a command this cycle.
- `wr_data_push` + `wr_data_ready` — commit a write burst into the WR buffer.
- `rd_return` + `rd_tag` + `rd_return_valid` — reassembled read burst back to core.
- `maint_quiesce` (= `sts_ca_quiesced`) — update/refresh in flight, hold emit.
- `init_complete`, `error_irq` — bring-up + fault to the core's control path.

Everything else (phase packing, latencies, CDC, DFI signaling) is hidden behind this
contract. The scheduler schedules *commands*; the fabric makes them *DFI phases*.

---

## Open items (fabric)

- **OF-1** exact CSR address map + access widths — deferred to register-map pass.
- **OF-2** WR/RD buffer depths — pin once `t_phy_wrlat`/`t_phy_rdlat` chosen (timing pass).
- **OF-3** async vs synchronous baseline — plan is `mc_clk==dfi_clk`; confirm before
  sizing CDC FIFO depth (async needs deeper).
- **OF-4** training-path detail (wrlvl/rdlvl/wdqlvl regs) — enumerate in a training
  sub-pass; listed here as a class, not fully expanded.
- **OF-5** CA parity / CRC error recovery policy — replay vs report-only.
