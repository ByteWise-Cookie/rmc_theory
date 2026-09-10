# DDR5 Maintenance Operations — RMC Architecture

**Status:** Architecture / documentation. Not RTL. Describes the DDR5 maintenance
operations that are *actually architected* in the current RMC (MC Core), how each
enters the controller, and the JEDEC timing constraints that bound it.

**Scope discipline:** This document covers only maintenance functionality that has
an owner (FSM / gate / scoreboard entry) in the current architecture. DDR5
features present in JESD79-5 but not architected here are listed in
[§8 Deferred / inventory-only features](#8-deferred--inventory-only-features) and
are **not** described as implemented. No maintenance architecture is added merely
because JESD79-5 contains a feature.

---

## 1. Sources and verification method

### 1.1 Authoritative JEDEC source

`DDR5 Spec JESD79-5.pdf` in the repository root. The front matter dates this as
the **original JESD79-5 release (July 2020)** — *not* revision 5A / 5B / 5C.

Every numeric timing value in this document was located in that exact PDF and is
cited as `JESD79-5, §X.Y, Table Z (p.N)` where `p.N` is the **printed** page
number (printed page = PDF page − 28).

- No value has been taken from a newer JESD79-5 revision or from general DDR
  knowledge.
- Where this edition marks a value **TBD** or renders it as light-grey
  ("should be considered TBD"), this document says so explicitly rather than
  filling it in.
- Table-number caveat: the body of this edition has an off-by-one glitch in the
  §13.3 timing tables (TOC "Table 519", body header "Table 520", etc.). Citations
  below give the section and printed page as the primary anchor.

`docs/ddr5_maintenance_investigation.txt` is an investigation aid only and is
**not** cited as a timing authority; every value below was re-checked against the
PDF.

### 1.2 Architecture sources inspected

| File | Used for |
|---|---|
| `docs/RMC_MR_Programming_and_Power_Management_v1_9_11.md` | MR Programming (MR_Write / MR_Poll), Power Management FSM, MC-core register interface, open decisions. Treated as an existing project document — not rewritten. |
| `docs/sched_rebuild/06_maintenance_engine.md` | Maintenance Engine (ME) peer-block model, 7 sub-FSMs, Stage-0 override, `init_done` DFI mux, refresh/ZQ gating |
| `docs/sched_rebuild/02_emit_timing_scoreboard.md` | Timing scoreboard (per-bank / per-rank / global tables), `timing_reg_file` (23 params), `can_*`/`next_*`, `sts_ca_quiesced` maintenance quiesce |
| `docs/sched_rebuild/11_mc_core_architecture.md` | Two-plane model (data vs control/timing), shared-state ownership, ME position |
| `docs/rmc_datapath_architecture.md` | Datapath ownership, `RL_line`/`WL_line`, what the datapath does *not* own; CDC boundary |
| `docs/sched_rebuild/08_arb_weight_arbiter.md` | Stage-3 arbiter, `s0_override` force-break of row-lock, NOP-cycle priority |
| `docs/scheduler_bank_fsm.md` | Per-bank FSM, per-bank timing eligibility gate, `REFRESHING_SB` state |
| `docs/architecture_reference.md` (§18–21) | ME port lists (Refresh / ZQcal / RFM / Power Mgmt / Init FSMs), Per-Bank / Per-Rank FSM Table fields, Stage 0–4 ports |
| `docs/sched_rebuild/00_ideas_and_naming.md` | Naming convention, ME idea provenance (I9, I13, I28) |
| `current_fyp_architecture_audit.txt` (§8.6–8.12, §14) | Consolidated maintenance status and known cross-document conflicts |

---

## 2. Architecture context (how maintenance reaches the DRAM)

The current architecture (`06_maintenance_engine.md`, `11_mc_core_architecture.md`,
`RMC_MR_Programming_and_Power_Management_v1_9_11.md`) establishes:

- **The Maintenance Engine (ME) is a peer block**, off the data plane. It reads
  activity counters / `all_idle` / `raa`, writes gates and `next_*` deadlines into
  the shared FSM tables, and issues its own **non-data** commands.
- **The ME never issues a CAS.** Reads and writes to DRAM data are the
  scheduler's alone (`06_maintenance_engine.md` §0, rule 1).
- **ME command path:** `me_cmd_valid / me_cmd_type / me_cmd_rank / me_cmd_bg /
  me_cmd_bank` → **Stage-0 maintenance override** → **Stage-4 emit** → FAB → PHY.
  No separate command path into the scheduler is introduced
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §0).
- **Stage-0 priority (documented):** `ref_urgent > ref_due > rfm_req > zq_due`
  (`06_maintenance_engine.md` §0; `architecture_reference.md` §19 Stage 0).
  MR_Poll bypasses Stages 1–3 (`architecture_reference.md`). PD/SR transitions are
  **gate-state changes, not Stage-0 contenders** — they block scheduler selection
  via `gate_pwr` the same way `gate_rfc`/`gate_zq` do
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §C.1). The runtime-MRW
  Stage-0 request contract is **OPEN** (see [§12](#12-open-architecture-decisions)).
- **`init_done` is a one-way latch** owned by the ME. The Init FSM drives DFI
  directly during boot; at `init_done` the scheduler inherits the DFI port
  permanently. A separate `dfi_cke` mux, also `init_done`-gated, hands CKE from
  Init FSM to Power Mgmt FSM
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.4).
- **Gating into Stage 2 (Legal Check Matrix):** `gate_rfc`, `gate_zq`,
  `gate_pwr` (PD/SR), `gate_mr` (MR_Write). Each blocks per-bank commands to the
  affected rank while asserted.
- **Maintenance quiesce:** on an ME command that needs the CA bus exclusively
  (e.g. refresh), Stage-4 asserts `sts_ca_quiesced`; emit then stalls CA and the
  maintenance operation owns the bus (`02_emit_timing_scoreboard.md` §4, §1C).
- **ME sub-FSM inventory (per `06_maintenance_engine.md` §1 and
  `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.15):**
  1 Init · 2 Refresh · 3 ZQcal · 4 RFM · 5 Power Mgmt · 6 MR_Poll · 7 MR_Write.
  *(Count discrepancy: `00_ideas_and_naming.md` I9 and some comments say "6";
  block-06 title and v1.9.11 say "7" (adds MR_Write). Flagged in
  [§12](#12-open-architecture-decisions).)*

---

## 3. Category A — Initialization and Reset

### 3.1 JEDEC-required DRAM sequence

JESD79-5 §3.3 defines the sequence the DRAM requires; the RMC Init FSM must
satisfy it but does not get to change it.

**Power-up initialization** (JESD79-5 §3.3.1, Figure 3, Table 11, p.10–12):

1. Voltage ramp (VPP ≥ VDD throughout); RESET_n held LOW.
2. After ramp (Tb), RESET_n LOW for ≥ `tINIT1`; CS_n LOW ≥ `tINIT2` before
   RESET_n deassert.
3. After RESET_n HIGH (Tc), wait ≥ `tINIT3` before driving CS_n HIGH.
4. After CS_n HIGH (Td), wait ≥ `tINIT4` (CMOS receiver registers the exit; ODT
   goes to strap/MR state); clock must be started and stable for `tCKSRX` before
   Te.
5. NOP for ≥ `tINIT5`; then `tXPR` timer starts (Tf).
6. Wait ≥ `tXPR` before the first legal configuration command (Tg). **During the
   config window (Tg–Tj) only MRR, MRW, MPC and VrefCA are legal**
   (JESD79-5 §3.3.1, step 6, p.11).
7. Mandatory configuration order (JESD79-5 §3.3.1, step 7, p.11):
   - **MPC "Configure tDLLK/tCCD_L"** (sets MR13 shadow) **before** MPC DLL RESET;
   - **MPC "DLL RESET"** **before** MPC ZQCal Start;
   - **MPC "ZQCal Start"** then **MPC "ZQCal Latch"** **before** any other
     training mode (CS training, etc.).
8. Between Tj and Tz: training/calibration modes are optional and
   system-architect's discretion (JESD79-5 §3.3.1, step 8).
9. After Tz, once `tZQLAT` is satisfied, the DRAM is ready for normal operation
   (JESD79-5 §3.3.1, step 9).

**Reset initialization with stable power** (JESD79-5 §3.3.2, Figure 4, Table 12,
p.12–13): assert RESET_n for ≥ `tPW_RESET` with CS_n LOW ≥ `tINIT2` before
deassert, then repeat steps 4–9 above.

**MR default settings** required before normal operation are listed in
JESD79-5 §3.3, Table 9 (p.9–10) — includes MR0 (BL / RL), MR6 (`tWR` / `tRTP`),
MR10–12 (Vref), MR32–36 (ODT).

**Initialization timing parameters** (JESD79-5 §3.3.1, Table 11, p.12):

| JEDEC symbol | Value in this edition | Meaning |
|---|---|---|
| `tINIT0` | MAX **20 ms** | Maximum voltage-ramp time |
| `tINIT1` | MIN **200 µs** | RESET_n LOW after voltage ramp complete |
| `tINIT2` | MIN **10 ns** | CS_n LOW before RESET_n HIGH |
| `tINIT3` | MIN **4 ms** | CS_n LOW after RESET_n HIGH |
| `tINIT4` | MIN **2 µs** | Time for DRAM to register EXIT on CS_n (CMOS) |
| `tINIT5` | MIN **3 nCK** | Min NOP cycles after CS_n HIGH |
| `tXPR` | MIN **= `tXS`** | Exit reset → first valid configuration command |
| `tCKSRX` | "See Self Refresh Timing Table" → `max(3.5 ns, 8 tCK)` | Stable clock required before init exit / SRX |

Reset (stable power) timing (JESD79-5 §3.3.2, Table 12, p.13):

| JEDEC symbol | Value | Meaning |
|---|---|---|
| `tPW_RESET` | MIN **1 µs** | RESET_n LOW for reset init with stable power |
| `tRST_ADC` | MAX **50 ns** | RESET_n assertion → ODT off |

**DLL initialization:** the DLL is reset via **MPC "DLL RESET"** (opcode
`0000 0010B`, JESD79-5 §4.15.2, Table 290, p.165). DLL lock time is `tDLLK`,
programmed via MR13 (JESD79-5 §3.5.15, Table 53, p.40):

| MR13 OP[3:0] | `tDLLK.min` | Data-rate range |
|---|---|---|
| `0000` | **1024 nCK** | 2000 < DR ≤ 2100 Mbps & DR = 3200 Mbps |
| `0001` | 1024 nCK | 3200 < DR ≤ 3600 |
| `0010` | 1280 nCK | 3600 < DR ≤ 4000 |
| `0011` | 1280 nCK | 4000 < DR ≤ 4400 |
| `0100` | 1536 nCK | 4400 < DR ≤ 4800 |
| `0101` | 1536 nCK | 4800 < DR ≤ 5200 |
| `0110` | 1792 nCK | 5200 < DR ≤ 5600 |
| `0111` | 1792 nCK | 5600 < DR ≤ 6000 |
| `1000` | 2048 nCK | 6000 < DR ≤ 6400 |
| `1001`–`1111` | Reserved | — |

**ZQ portion of initialization:** the first ZQ calibration is part of the boot
sequence — **MPC "ZQCal Start"** then **MPC "ZQCal Latch"**, subject to
`tZQCAL` / `tZQLAT` (see [§5](#5-category-c--zq-calibration)). It must complete
before any other training mode (JESD79-5 §3.3.1, step 7). Prior to ZQ completion,
MPC commands must be multi-cycle (JESD79-5 §3.3.1, Figure 3, note 6).

### 3.2 What the RMC Init FSM actually controls

Per `06_maintenance_engine.md` §1 (row 1), §4; `architecture_reference.md` §21;
`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.1, §B.4:

- **Init FSM = ME sub-FSM 1.** Trigger: `INIT_KICK` (CSR). Documented sequence:
  `reset → MRW (MRW_BURST) → ZQcal → training → DONE`.
- **Init FSM drives DFI directly** (its own `dfi_address / dfi_cs_n / dfi_act_n /
  dfi_wrdata / dfi_wrdata_en`) until it asserts `init_done` — a one-way latch. It
  also asserts `global_state_req = INIT` to the Global FSM.
- **`TRAIN_EN` (CSR)** gates whether training runs after `MRW_BURST`
  (`architecture_reference.md` §21; `RMC_MR_Programming_and_Power_Management_v1_9_11.md`
  §D.2 — this CSR is noted as absent from the Handoff §17 table).
- **Init FSM reads `tINIT1..tDLLK` from `timing_reg_file`**
  (`architecture_reference.md` §21 port `timing_reg_vals`).
- On `init_done`: the scheduler inherits the DFI port (FAB mux), and the `dfi_cke`
  mux hands CKE ownership to the Power Mgmt FSM
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.4).
- The v1.9.8 baseline specifies boot-time `MRW_BURST` and periodic MR4/TUF polling
  and **nothing else** for MR handling
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A "Scope assumption").

**Not specified by the architecture (do not assume):**

- The exact ordering/content of `MRW_BURST` (which MRs, in what order) is not
  enumerated in the inspected docs beyond "all Mode Registers that require defined
  settings" (JEDEC's wording, JESD79-5 §3.3.1, Figure 3, note 4).
- Whether the Init FSM issues the mandatory MPC configuration chain (tDLLK cfg →
  DLL RESET → ZQCal Start → ZQCal Latch) as discrete steps is **implied** by the
  `reset → MRW → ZQcal → training → DONE` sequence but not written out
  command-by-command in the inspected docs.
- `tINIT0`, `tINIT2`–`tINIT5`, `tXPR`, `tPW_RESET`, `tRST_ADC` are **not** members
  of the 23-parameter `timing_reg_file`
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.3). Only
  `T_DLLK`, `T_ZQCAL`, `T_ZQLAT`, `T_MRD` (of the init-relevant set) are present.
  See [§12](#12-open-architecture-decisions).

---

## 4. Category B — Mode Register Operations

### 4.1 Architecture context

Per `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A and
`06_maintenance_engine.md` §1, §3:

- **MR_Poll FSM (ME sub-FSM 6):** periodic MRR to **MR4** for TUF / temperature.
  Trigger `gc ≥ next_poll_gc`; default interval `MRR_POLL_INTERVAL = 32 × tREFI`
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.2). Return path is the
  existing **Read Data Path sideband**: `mrr_data_valid` / `mrr_data[7:0]` /
  `mrr_rank` — *not* the response FIFO. Drives `T_REFI_adjusted = T_REFI / 2`
  into the Refresh FSM on TUF = 1 (`06_maintenance_engine.md` §2).
- **MR_Write FSM (ME sub-FSM 7, 9 states):** single outstanding software-issued
  MRW via CSR (`MR_WR_REQ / MR_WR_ADDR[5:0] / MR_WR_DATA[7:0] / MR_WR_RANK /
  MR_WR_REQUIRE_IDLE / MR_WR_VERIFY`). Flow
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.3):

  ```
  IDLE → WAIT_REQ → GATE_CHECK → ISSUE_MRW → WAIT_tMRD →
    [VERIFY_MRR → WAIT_RDDATA → CHECK_MATCH]  (optional, MR_WR_VERIFY=1) →
  DONE → IDLE
  ```

  - `GATE_CHECK` waits for `gate_pwr[rank] == 0` and (if `MR_WR_REQUIRE_IDLE`)
    `bank_act_count[rank][*] == 0`. Bounded wait, no forced eviction, no timeout
    (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.3, §A.11).
  - `WAIT_tMRD` holds `gate_mr[rank] = 1` for **`T_MRD`** cycles (existing
    `timing_reg_file` param).
  - Optional verify reuses the MR_Poll MRR sideband, serialized by the shared
    **`mrr_busy`** mutual-exclusion bit (one outstanding MRR across both FSMs;
    **not** an arbiter — no requester tag, no response routing)
    (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.2, §A.12-5).
  - **No hardware path from MR_Write FSM to `timing_reg_file`.** Keeping the
    timing register file consistent with a timing-affecting MRW is a **software**
    two-step: software issues `MR_WR_REQ`, polls `MR_WR_BUSY`/`MR_WR_ERROR`, then
    performs an ordinary separate CSR write to `timing_reg_file`
    (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.4).
- **MPC:** the only MPC operations with an architectural owner today are those the
  ZQcal FSM issues — **ZQCal Start / ZQCal Latch** (see
  [§5](#5-category-c--zq-calibration)). No other MPC opcode has an FSM/owner in
  the inspected architecture (see [§8](#8-deferred--inventory-only-features)).
- **Scheduler interaction:** `gate_mr[rank]` is a Stage-2 gate input, same shape
  as `gate_rfc` / `gate_zq`. No changes to Stages 1–3, TCAM, or watermark
  managers (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.7).

### 4.2 JEDEC MR timing parameters (verified against the repository PDF)

**Mode Register Read/Write AC timing** — JESD79-5 §3.4.4, Table 20 (p.18):

| JEDEC symbol | Value in this edition | Meaning | Note |
|---|---|---|---|
| `tMRR` | MIN **`max(14 ns, 16 nCK)`** | Mode Register Read command period | MRR/MRW not allowed with pages open (Table 20, note 1) |
| `tMRR_p` | MIN **8 nCK** | Mode Register **Read Pattern** to Read Pattern spacing | Applies to back-to-back **Read Training Pattern** MRRs only (JESD79-5 §4.17.4, p.182). *Faster* than a normal MRR→MRR, which is `tMRR`. |
| `tMRW` | MIN **`max(5 ns, 8 nCK)`** | Mode Register Write command period | note 1 |
| `tMRD` | MIN **`max(14 ns, 16 nCK)`** | Mode Register Set command delay | — |
| `tDFE` | MIN **80 ns** | DFE Mode Register Write update delay | Applies **only** to MRWs to DFE registers (MR112–MR248), JESD79-5 §3.4.3, Table 20 note 2 |
| `tMRRI` | **NOT DEFINED in this edition** | — | Symbol `tMRRI` does not appear anywhere in `DDR5 Spec JESD79-5.pdf`. Treat as undefined / TBD-in-this-edition. |

**MRR/MRW → other-command restrictions** — JESD79-5 §3.4.4, Table 22
(*DQ ODT is Disable*, p.19):

| From | To | Minimum delay (this edition) |
|---|---|---|
| MRR | MRR | `tMRR` |
| MRR | MRW | `CL + BL/2 + 1` (tCK) |
| MRR | MPC | `CL + BL/2 + 1` (tCK) |
| MRR | VrefCA | `CL + BL/2 + 1` (tCK) |
| MRR | Any other valid command | `tMRD` |
| MRW | MRW | `tMRW` |
| MRW | Any other valid command | `tMRD` |
| PRE | MRR | `tRP` |
| PRE | MRW | `tRP` |
| REF | MRR | `tRFC` |
| REF | MRW | `tRFC` |

Table 22, note 1: *all data should be completed before entry into self refresh or
power down.* Note 2: *MRR can refer to both Target ODT MRR and Non-Target ODT MRR.*

**MRR/MRW → other, DQ ODT *Enable* case** — JESD79-5 §3.4.4, Table 23 (p.20):
in this edition the MRR-side cells of Table 23 are **blank** (no values filled
in). Only the MRW rows carry "Same as ODT Disable Case". **The DQ-ODT-enabled MRR
constraints are therefore undefined in this JESD79-5 edition.**

**Current state for MRR/MRW** — JESD79-5 §3.4.4, Table 21 (p.18): both require
current state **All Banks Idle**.

### 4.3 What the RMC currently implements vs what JEDEC specifies

The architecture **explicitly makes one simplification** and this document does
not extend it:

- `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.11 and §C.4:
  *"`T_MRD` … governs command spacing after MRW — reused directly, no new timing
  parameter needed"* and *"this document uses the single existing `T_MRD`
  parameter uniformly. Left as a future refinement."*
- Consequence: the MR_Write FSM enforces **`T_MRD` after MRW → any command**
  (`WAIT_tMRD` state, `gate_mr[rank]`). It does **not** model:
  - `tMRW` for MRW → MRW (there is no queue; a second `MR_WR_REQ` while busy is
    ignored, so back-to-back MRWs cannot occur through this FSM anyway);
  - `tMRR` for MRR → MRR (MR_Poll self-serializes via `WAIT_RDDATA` +
    `mrr_busy`);
  - `CL + BL/2 + 1` for MRR → MRW / MPC / VrefCA;
  - `tRP` for PRE → MRR/MRW or `tRFC` for REF → MRR/MRW as *explicit* fences —
    these are instead covered indirectly by the "all banks idle" / "no pending
    maintenance" preconditions in `GATE_CHECK` and by the existing scoreboard
    `next_*` deadlines the ME reads.
- **`tMRRI` is not used** by the architecture (and is not defined by this JEDEC
  edition).

This is recorded as a known limitation, not a defect — see
[§12](#12-open-architecture-decisions), item "Timing-scoreboard entries needed for
maintenance".

---

## 5. Category C — ZQ Calibration

### 5.1 Architecture context

Per `06_maintenance_engine.md` §1 (row 3); `architecture_reference.md` §20
"ZQcal FSM"; `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.2:

- **ZQcal FSM = ME sub-FSM 3, `N_RANKS` instances** (one per rank).
- Trigger: `gc ≥ next_zqcs` (per-rank deadline in the Per-Rank FSM Table).
- Issues **MPC "ZQCal Start"** then **MPC "ZQCal Latch"** via the `me_cmd_*` →
  Stage-0 → Stage-4 path.
- Drives **`gate_zq[rank]`** into Stage 2 while the latch phase needs the CA bus
  quiesced; blocks all per-bank commands to that rank.
- Updates `next_zqcs` from the CSR interval on completion.
- CSR: `tZQCS_interval` (a.k.a. `T_ZQCS_interval`), default **128 ms** converted
  to cycles at the operating bin
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.2;
  `06_maintenance_engine.md` open item OM-4). A separate host-triggered
  `ZQCAL_TRIG` CSR is mentioned in `mc_core_spec_v2.tex` but its semantics are
  undocumented (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.2).
- `timing_reg_file` already contains `T_ZQCAL` and `T_ZQLAT`
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.3, 23-param list).

### 5.2 JEDEC ZQ parameters (verified against the repository PDF)

JESD79-5 §4.23 "ZQ Calibration Commands":

| JEDEC symbol | Value in this edition | Meaning | Ref |
|---|---|---|---|
| `tZQCAL` | MIN **1 µs** | ZQ Calibration Time: **ZQCal Start → ZQCal Latch** | §4.23.1, Table 329 (p.201) |
| `tZQLAT` | MIN **`max(30 ns, 8 nCK)`** | ZQ Calibration Latch Time: **ZQCal Latch → CA/DQ usable for normal operation** | §4.23.1, Table 329 (p.201) |

Restrictions during the ZQ calibration interval (JESD79-5 §4.23.1, p.201):

- ZQCal Start may be issued any time the DRAM can receive valid commands; ZQ
  calibration "occurs in the background of device operation".
- **After a ZQCal Start and until `tZQCAL` finishes, neither another ZQCal Start
  nor a ZQCal Latch is allowed.**
- ZQCal Latch may be issued any time **outside of power-down** after `tZQCAL` has
  expired **and all DQ bus operations have completed**.
- **The CA bus must maintain a Deselect (DES) state during `tZQLAT`** to allow CA
  ODT calibration settings to update.

### 5.3 Rank scope / external-resistor serialization — architecture decision required

JESD79-5 §4.23.2 (p.201):

> "To use the ZQ calibration function, a 240 ohm +/- 1% tolerance external
> resistor must be connected between the ZQ pin and VSSQ. If the system
> configuration has more than one rank, and if the ZQ pins of both ranks are
> attached to a single resistor, then the SDRAM controller must ensure that the
> ZQCals don't overlap." (Total ZQ-pin capacitive loading ≤ 25 pF.)

**Current architecture:** the ZQcal FSM is instanced per rank with **no
cross-rank interlock** in the inspected docs. Whether the platform gives each
rank its own 240 Ω resistor (independent ZQCals allowed) or shares one resistor
across ranks (ZQCals **must** be serialized) is a **board / platform assumption
that has not been made explicit**. This must be a project-level decision, not a
silent choice. See [§12](#12-open-architecture-decisions).

---

## 6. Category D — Power Management

### 6.1 Architecture context

Per `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B;
`06_maintenance_engine.md` §1 (row 5); `architecture_reference.md` §20
"Power Management FSM":

- **Power Mgmt FSM = ME sub-FSM 5, `N_RANKS` instances**, 12 states
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.5, §B.15).
- **Power-down is autonomous / idle-triggered:** entry requires all banks in the
  rank idle (`bank_act_count[r][*] == 0`), `pd_en` (CSR), no pending maintenance,
  `gate_mr[r] == 0`, **and** the banks staying continuously idle for
  `PD_IDLE_THRESHOLD` cycles (default 64; activity resets the dwell counter)
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.5, §B.10).
- **Self-refresh is externally directed:** `sr_entry` / `sr_exit` are
  system-level signals (not CSRs), outside RMC
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.1 goal 5, §B.14).
  **SR has no auto-wake on traffic**; new requests to an SR-gated rank queue but
  wait for `sr_exit`
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.7).
- **PD auto-wake:** the moment any bank's `bank_act_count` for a PD-gated rank
  goes non-zero, `PDX_WAIT` is triggered; `gate_pwr[r]` stays asserted for the
  whole `PDX_WAIT` and clears only after `T_XP` has elapsed and `dfi_cke[r]` is
  reasserted (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.7).
- **Outputs:** `gate_pwr[rank]` (Stage-2 gate, shared by PD and SR),
  `dfi_cke[N_RANKS-1:0]` (via the `init_done`-gated CKE mux), and a broadcast
  write that updates all 16 Per-Bank FSM Table rows of the rank to
  `POWER_DOWN` / `SELF_REFRESH` / `IDLE`
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.4, §B.6).
- **Self-refresh exit is a sequential wait chain**
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.5, §B.11, §B.12-7):
  `SR_EXIT → WAIT_tCKSRX → WAIT_tXS → WAIT_tDLLK → NORMAL`
  (`T_CKSRX`, then `T_XS`, then `T_DLLK` for DLL-requiring commands).
  *(The v1.9.11 §B.5 state table also names a `WAIT_tCKSRE` state on the entry
  side; see [§12](#12-open-architecture-decisions) — JESD79-5 (this edition) has no
  `tCKSRE` symbol.)*
- **`timing_reg_file`** already contains `T_XP`, `T_XS`, `T_DLLK`
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.3, 23-param list).
  `T_CKSRE` / `T_CKSRX` are **not** members — representation OPEN
  (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.3, §E-3).
- **Refresh interaction** (`RMC_MR_Programming_and_Power_Management_v1_9_11.md`
  §B.8, invariants B.12-4/5):
  - REF targeting a `POWER_DOWN`-gated rank **unconditionally** forces
    `PDX_WAIT` before the REF can issue (fixed invariant, no CSR).
  - REF **never** pre-empts `SELF_REFRESH`; during SR the rank's
    `ref_credits[r]` is **frozen**.

### 6.2 JEDEC power-management parameters (verified against the repository PDF)

**Power-Down** — JESD79-5 §4.10, Table 272 (p.144):

| JEDEC symbol | Value in this edition | Meaning |
|---|---|---|
| `tCPDED` | MIN `max(5 ns, 8 nCK)` | Command-pass-disable delay after PDE |
| `tPD` | MIN `max(7.5 ns, 8 nCK)` | Minimum time in power-down |
| `tXP` | MIN `max(7.5 ns, 8 nCK)` | PDX → next valid command |
| `tACTPDEN` | MIN 2 nCK | ACT → PDE |
| `tPRPDEN` | MIN 2 nCK | PREab/PREsb/PREpb → PDE |
| `tRDPDEN` | `RL + RBL/2 + 1` (nCK) | RD / RD w/AP → PDE |
| `tWRPDEN` | `WL + WBL/2 + (tWR/tCK(avg)) + 1` (nCK) | WR → PDE |
| `tWRAPDEN` | `WL + WBL/2 + WR + 1` (nCK) | WR w/AP → PDE |
| `tREFPDEN` | MIN 2 nCK | REFab / REFsb → PDE |
| `tMRRPDEN` | `RL + 8 + 1` (nCK) | MRR → PDE |
| `tMRWPDEN` | `tMRD(min)` | MRW → PDE |
| `tMPCPDEN` | `tMPC_Delay` | MPC → PDE (opcode exceptions in Table 272, note 5) |

JESD79-5 §4.10.1 (p.143): *"Power-down duration is limited by 5 × `tREFI1` of the
device."* DLL is kept enabled during precharge power-down and active power-down
(Table 271, p.143). PDE/PDX are CS_n-triggered (no CKE pin) (JESD79-5 §4.10,
p.142).

**Self-Refresh** — JESD79-5 §4.9, Table 270 (p.140):

| JEDEC symbol | Value in this edition | Meaning |
|---|---|---|
| `tCPDED` | MIN `max(5 ns, 8 nCK)` | Command-pass-disable delay after SRE |
| `tCSL` | MIN **10 ns** | Self-Refresh CS_n low pulse width (min time in self-refresh) |
| `tCSH_SRexit` | MIN **13 ns**, MAX **30 ns** | SRX CS_n HIGH pulse width |
| `tCSL_SRexit` | MIN **3 nCK**, MAX **30 ns** | SRX CS_n LOW pulse width (≥ 3 NOP) |
| `tCKSRX` | MIN `max(3.5 ns, 8 tCK)` | Valid clock required **before** SRX |
| `tCKLCS` | MIN `tCPDED + 1 nCK` | Valid clock required **after** SRE |
| `tCASRX` | MIN **0 ns** | SRX CS_n high (CA-bus timing) |
| `tXS` | **= `tRFC1`** | Exit self-refresh → next valid command **not** requiring a DLL |
| `tXS_DLL` | **= `tDLLK`** | Exit self-refresh → next valid command **requiring** a DLL |

JESD79-5 §4.9 (p.138–139):

- **SRE preconditions:** the DRAM must be idle — all banks closed (`tRP` etc.
  satisfied), no data bursts in progress, all timings from previous operations
  satisfied (`tMRD`, `tRFC`, etc.). A DES must be registered on the last positive
  clock edge before SRE; DES continues until `tCPDED` is satisfied; then CS_n
  transitions LOW and stays LOW until exit.
- **SRX** is the CS_n LOW→HIGH transition held HIGH for `tCSH_SRexit`, followed by
  ≥ 3 NOP (`tCSL_SRexit`). Clocks must be valid for `tCKSRX` before those NOPs.
- **After SRX**, commands **not** requiring a locked DLL are legal after `tXS`:
  `ACT, MPC, MRW, PDE, PDX, PRE(ab,sb,pb), REF(ab,sb), RFM(ab,sb), SRE, VREFCA,
  WRP`. Commands **requiring** a locked DLL are legal after `tXS_DLL`:
  `RD, MRR, WR`.
- Upon SRX, one additional refresh (a single REFab or `n × REFsb`) shall be
  issued; it counts toward the postpone budget (this obligation is the refresh
  subsystem's concern — see [§7 Category E](#7-category-e--refresh--rfm-boundary)).
- `tXS` value **= `tRFC1`** (JESD79-5 §4.9, p.139), which grows with device
  density.

**Command-spacing vs power-state entry/exit — do not conflate:** the `t*PDEN`
values above are the *minimum spacing from a prior command to the PDE command*.
They are **not** the conditions to *be in* power-down. Likewise `tXS` / `tXS_DLL`
are *post-SRX command legality delays*, distinct from the SRE precondition list
(idle, `tRP`, `tMRD`, `tRFC` satisfied). The RMC models these separately:
`t*PDEN` would be scoreboard `next_*`-style fences on the PDE emit;
`tXS` / `tXS_DLL` are the Power Mgmt FSM's `WAIT_tXS` / `WAIT_tDLLK` states and
`next_xs` / `can_xs` in the Per-Rank FSM Table.

## 7. Category E — Refresh / RFM boundary

**Refresh is owned by the teammate's refresh subsystem.** This document defines
only the boundary the maintenance architecture must respect; it does not
duplicate or redesign the refresh implementation.

**What the current architecture already places at the boundary**
(`06_maintenance_engine.md` §2; `architecture_reference.md` §20 "Refresh FSM";
`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.8):

- **Refresh FSM = ME sub-FSM 2.** Leaky-bucket credits
  (`ref_credits += 1` per `T_REFI`, `−= 1` per REF). `ref_urgent` (credits ≥ 8)
  and `ref_due` (`gc ≥ next_trefi`) feed **Stage-0 priority**
  (`ref_urgent > ref_due > rfm_req > zq_due`).
- REFab asserts `gate_rfc[rank]` (all banks of the rank blocked for `T_RFC1`);
  REFsb asserts a per-bank gate (`gate_rfcpb[rank][bank]`) for `T_RFCsb`
  (`06_maintenance_engine.md` §2). Scoreboard writeback on `REF` sets
  `rk.next_rfc = gc + T_RFC1` (REFab) or `b.next_ref = gc + T_RFCsb` (REFsb) and
  asserts `sts_ca_quiesced` (`02_emit_timing_scoreboard.md` §3).
- `REF_MODE` CSR selects REFab / REFsb / FGR.
- **RAA (Rolling Accumulated ACT) counters** are incremented by **Stage-4** on
  every ACT (`raa_inc_en[N_RANKS][16]` → Per-Rank FSM Table
  `architecture_reference.md` §19 Stage 4, §20 RFM FSM).
- **RFM FSM = ME sub-FSM 4.** Reads `raa_out`, compares to `RAAIMT` (CSR),
  raises `rfm_req[N_RANKS][16]` into Stage-0, issues RFMab/RFMsb, decrements RAA
  via `raa_dec_en` / `raa_dec_val`.
- MR_Poll's `T_REFI_adjusted` feeds the Refresh FSM on MR4 TUF = 1.

**JEDEC parameters at the boundary (verified against the repository PDF):**

| JEDEC symbol | Value in this edition | Ref |
|---|---|---|
| `tREFI` (base) | `tREF / 8192 = 32 ms / 8192` → **3.9 µs** | §4.13.4 (p.155); Table 281 (p.156) |
| `tREFI1` | 0–85 °C: `tREFI` = 3.9 µs · 85–95 °C: `tREFI/2` = 1.95 µs | §4.13.4, Table 281 (p.156) |
| `tREFI2` (FGR) | 0–85 °C: 1.95 µs · 85–95 °C: 0.975 µs | Table 281 (p.156) |
| `tREFIsb` (FGR) | `tREFI/(2n)` = 1.95/n µs · hot: `tREFI/(4n)` (`n` = banks/BG) | Table 281 (p.156) |
| `tRFC1(min)` | 8 Gb **195 ns** · 16 Gb **295 ns** · 24 Gb **TBD** · 32 Gb **TBD** | Table 282 (p.156) |
| `tRFC2(min)` | 8 Gb **130 ns** · 16 Gb **160 ns** · 24 Gb / 32 Gb **TBD** | Table 282 (p.156) |
| `tRFCsb(min)` | 8 Gb **115 ns** · 16 Gb **130 ns** · 24 Gb / 32 Gb **TBD** | Table 282 (p.156) |
| `tREFSBRD(min)` | 8 Gb / 16 Gb **30 ns** · 24 Gb / 32 Gb **TBD** | Table 284 (p.156) |
| `tRFM1 / tRFM2 / tRFMsb (min)` | **= `tRFC1 / tRFC2 / tRFCsb` (min)** respectively | §4.41, Table 378 (p.270) |

**Refresh command scheduling separation** (JESD79-5 §4.13.3, Table 280, p.155) —
these govern REF/RFM ↔ ACT and are the refresh subsystem's to enforce, but the
maintenance architecture must be aware they exist:

| Symbol | From | To |
|---|---|---|
| `tRFC1` | REFab (Normal) | REFab · ACT to any bank |
| `tRFC2` | REFab (FGR) | REFab · REFsb · ACT to any bank |
| `tRFCsb` | REFsb (FGR) | REFab · REFsb · ACT to same bank as REFsb |
| `tREFSBRD` | REFsb (FGR) | ACT to a different bank from REFsb |
| `tRRD_L` | ACT (FGR) | REFsb to a different bank from ACT (same bank group) |

JESD79-5 §4.41 (p.271): *"RFM command scheduling shall meet the same minimum
separation requirements as those for the REF command (see Table 280)."*
*"An RFM command does not replace the requirement for the controller to issue
periodic REF commands."*

**RFM ownership is ambiguous in the current architecture** and is flagged as an
open ownership decision — see [§12](#12-open-architecture-decisions).

---

## 8. Deferred / inventory-only features

JESD79-5 contains additional maintenance-related functionality that the current
RMC architecture does **not** implement. These are recorded here so the document
does not imply support. No architecture is added for them.

| JEDEC feature | What it is | Owner/FSM in current RMC architecture? | Status |
|---|---|---|---|
| **VrefCA command** | 1-cycle command to set CA reference voltage (shadow reg), applied via MPC "Apply VrefCA/CS/RTT". JESD79-5 §4.24, Table 330/331 (p.202–203). `tVrefCA_Delay = tMRD`; `tVrefCA_CS = 3.5–8 nCK`. | **No** | Deferred — used during init/training and freq change, neither of which drives it from an RMC FSM in the inspected docs |
| **VrefCS command** | As VrefCA but for the CS pin. JESD79-5 §4.25, Table 332 (p.203). | **No** | Deferred |
| **Additional MPC operations** — Apply VrefCA/CS/RTT, Group A/B RTT_CA/CS/CK config, Set DQS_RTT_PARK / RTT_PARK, PDA Enumerate/Select ID, Set 1N/2N, Configure tDLLK/tCCD_L | MPC opcodes, JESD79-5 §4.15.2, Table 290 (p.165). `tMPC_Delay = tMRD`. | **No** (only ZQCal Start/Latch have an owner — the ZQcal FSM) | Deferred (init/training-time) or out of scope for runtime |
| **Manual ECS** | MPC "Manual ECS Operation" (`0000 1100B`) — on-die ECC scrub of one row on demand. JESD79-5 §4.15.2, §4.35–4.36 (p.243–249). On-die ECC also auto-scrubs 1 row per REFab and during self-refresh (automatic, no command). | **No** | Deferred — automatic ECS is invisible to the controller; Manual ECS has no FSM |
| **DQS interval oscillator** | MPC "Start/Stop DQS Interval Oscillator" (`0000 0111B` / `0000 0110B`); count read via MRR (MR46/MR47). Feeds tDQS2DQ adjustment. JESD79-5 §4.31–4.32 (p.234–238). | **No** | Deferred |
| **1N / 2N command-timing mode change** | MPC "Set 2N/1N Command Timing" (`0000 1000B` / `0000 1001B`). JESD79-5 §4.33 (p.239–240). 2N is typically set at power-on. | **No** dedicated FSM. `02_emit_timing_scoreboard.md` §4 has a "2N cadence" note (`caFree += 2` in 2N) but nothing *sets* the mode at runtime. | Deferred (set once at init; no runtime owner) |
| **MPSM (Maximum Power Saving Mode)** | Deepest static power state, entered/exited by MRW (MR2:OP[3]). Data retention **not** guaranteed. `tMPSMX = tMRD`. JESD79-5 §4.12, Table 276/277 (p.147–148). | **No** | Out of scope — no FSM, no CSR, not referenced in the inspected architecture |
| **Frequency change / SREF flow** | `SRE` with `CA9 = L` ("Self Refresh Entry w/ Frequency Change") — the only legal way to change the input clock frequency; requires MR13 / VrefCA / RTT preprogramming. `tCSL_FreqChg = VrefCA_time`. JESD79-5 §4.11, Table 274/275 (p.145–147). | **No** | Out of scope — Power Mgmt FSM handles SRE/SRX but not the frequency-change variant or the pre-programming sequence |
| **PPR (hard / soft / MBIST post-package repair)** | Field row repair via a guard-key + WRA sequence; hPPR requires a reset afterward. JESD79-5 §4.29 (p.223–227). Timing symbols `tPGM` etc. are **light-grey/TBD** in this edition. | **No** | Out of scope — RAS/software-plane, rare, not architected |
| **Training reruns** | Periodic re-execution of Write Leveling / Read / CA / CS / Vref training during operation. JESD79-5 §4.17–4.28 (p.175–222). | **No** (Init FSM runs training once at boot, gated by `TRAIN_EN`) | Deferred — no runtime retrain owner |
| **Connectivity Test (CT) mode** | Board-interconnect test via the TEN pin, asynchronous, pre-init. JESD79-5 §4.22 (p.198–200). | **No** | Out of scope — manufacturing/bring-up, not a functional mode |
| **Package Output Driver Test Mode** | Per-bit output-driver characterization via MR61; requires a device reset after exit. JESD79-5 §4.42 (p.271). | **No** | Out of scope — characterization only |

---

## 9. Maintenance command-to-command timing table

This table is **only** for maintenance commands and their interaction with each
other and with normal traffic where JESD79-5 defines a constraint. Normal
ACT/RD/WR/PRE-to-ACT/RD/WR/PRE timing is **not** here — that stays in the
scheduler timing documentation (`02_emit_timing_scoreboard.md` §0).

**Scope column values:**

- `same bank`
- `different bank, same bank group` — used **only** where JESD79-5 defines the
  constraint on a bank-within-bank-group basis. ("Same bank group, different
  bank" is the identical physical relationship and is not a separate row.)
- `different bank group`
- `rank` — the constraint applies to the whole rank / logical rank
- `device / global` — the constraint applies device-wide (no bank/BG/rank
  dimension)
- `state-dependent` — the constraint depends on DRAM state or command payload

A bank-relationship scope is shown **only** when JESD79-5 actually defines the
constraint that way. For every maintenance command below, JESD79-5 defines the
constraint at `rank` or `device / global` scope unless noted.

| From command | To command | Required delay / constraint | Scope | JEDEC parameter | JESD79-5 ref | Notes |
|---|---|---|---|---|---|---|
| MRW | MRW | `tMRW` = `max(5 ns, 8 nCK)` | device / global | `tMRW` | §3.4.4 Table 20, Table 22 (p.18–19) | RMC: cannot occur through MR_Write FSM (single outstanding, no queue). |
| MRW | any other valid command | `tMRD` = `max(14 ns, 16 nCK)` | device / global | `tMRD` | §3.4.4 Table 22 (p.19) | RMC enforces this via `gate_mr[rank]` held `T_MRD` (§4.3). |
| MRW (DFE register) | (setting active) | `tDFE` = 80 ns | device / global | `tDFE` | §3.4.3, Table 20 note 2 (p.18) | DFE MRs only (MR112–248). Not used by current RMC. |
| MRR | MRR | `tMRR` = `max(14 ns, 16 nCK)` | device / global | `tMRR` | §3.4.4 Table 20, Table 22 (p.18–19) | MR_Poll self-serializes (`WAIT_RDDATA` + `mrr_busy`). |
| MRR (Read Training Pattern) | MRR (Read Training Pattern) | `tMRR_p` = 8 nCK | device / global | `tMRR_p` | §3.4.4 Table 20 (p.18); §4.17.4 (p.182) | Read Training Pattern only. Not used by current RMC. |
| MRR | MRW | `CL + BL/2 + 1` (tCK) | device / global | (Table 22 expression) | §3.4.4 Table 22 (p.19) | DQ-ODT-disable case. Not modelled by RMC (§4.3). |
| MRR | MPC | `CL + BL/2 + 1` (tCK) | device / global | (Table 22 expression) | §3.4.4 Table 22 (p.19) | DQ-ODT-disable case. |
| MRR | VrefCA | `CL + BL/2 + 1` (tCK) | device / global | (Table 22 expression) | §3.4.4 Table 22 (p.19) | DQ-ODT-disable case. |
| MRR | any other valid command (incl. RD/WR) | `tMRD` | device / global | `tMRD` | §3.4.4 Table 22 (p.19) | — |
| MRR | (DQ-ODT-enabled variants) | **undefined in this edition** | — | — | §3.4.4 Table 23 (p.20) | Table 23 MRR-side cells are blank in this JESD79-5 edition. TBD. |
| RD / WR | MRW | *(not tabulated as a distinct pair)* — MRW requires **all banks idle** first | device / global (state-dependent) | — (Table 21 precondition) | §3.4.4 Table 20 note 1, Table 21 (p.18) | JESD79-5 gives the constraint as a *state* ("no pages open / all banks idle"), not a from-RD/WR delay. RMC: `MR_WR_REQUIRE_IDLE` in `GATE_CHECK`. |
| RD / WR | MRR | as above (all banks idle) | device / global (state-dependent) | — | §3.4.4 Table 21 (p.18) | — |
| PRE | MRR | `tRP` | same bank (PREpb) / rank (PREsb) / rank (PREab) | `tRP` | §3.4.4 Table 22 (p.19) | `tRP` is the standard PRE→ACT delay (speed-bin dependent, §10). Scope follows the precharge type. |
| PRE | MRW | `tRP` | same bank / rank | `tRP` | §3.4.4 Table 22 (p.19) | — |
| REF | MRR | `tRFC` | rank | `tRFC` (`tRFC1` / `tRFC2` / `tRFCsb` per mode) | §3.4.4 Table 22 (p.19) | `tRFC` value per refresh mode; see §7. |
| REF | MRW | `tRFC` | rank | `tRFC` | §3.4.4 Table 22 (p.19) | — |
| MPC | any other valid command | `tMPC_Delay` = `tMRD` | device / global | `tMPC_Delay` | §4.15.3 Table 293 (p.168) | Applies to all MPC opcodes except a few excluded from PDE (Table 272 note 5). |
| MPC | (CS assertion, multi-cycle mode) | `tMPC_CS` = 3.5 … 8 nCK; `tMC_MPC_Setup` / `tMC_MPC_Hold` = 3 nCK | device / global | `tMPC_CS`, `tMC_MPC_Setup`, `tMC_MPC_Hold` | §4.15.3 Table 293 (p.168) | Only when CS Assertion Duration MR bit = 0 (multi-cycle). Init uses multi-cycle before CA training. |
| MPC "ZQCal Start" | MPC "ZQCal Latch" | `tZQCAL` (MIN 1 µs); no ZQCal Start **or** Latch allowed in between | rank | `tZQCAL` | §4.23.1 Table 329 (p.201) | Background calibration during this window. |
| MPC "ZQCal Latch" | first normal CA/DQ use | `tZQLAT` = `max(30 ns, 8 nCK)`; **CA = DES throughout** | rank | `tZQLAT` | §4.23.1 Table 329 (p.201) | Also: Latch requires all DQ bus ops complete and **not in power-down** first. |
| MPC "ZQCal Latch" (rank A) | MPC "ZQCal Start/Latch" (rank B) | must **not overlap** if ranks share one 240 Ω resistor | rank (cross-rank) | — (no symbol) | §4.23.2 (p.201) | Board assumption — see §12 open decision. |
| ACT / PRE / RD / WR / WRA / REF / MRR / MRW / MPC | PDE | `tACTPDEN` / `tPRPDEN` / `tRDPDEN` / `tWRPDEN` / `tWRAPDEN` / `tREFPDEN` / `tMRRPDEN` / `tMRWPDEN` / `tMPCPDEN` respectively | rank (per prior command) | (see §6.2) | §4.10.1 Table 272 (p.144) | Minimum spacing *to the PDE command* — distinct from PD entry conditions. |
| PDE | PDX | `tPD` (MIN `max(7.5 ns, 8 nCK)`) minimum in power-down | rank | `tPD` | §4.10.1 Table 272 (p.144) | Also: PD duration ≤ `5 × tREFI1` (§4.10.1 p.143). |
| PDX | any valid command | `tXP` = `max(7.5 ns, 8 nCK)` | rank | `tXP` | §4.10.1 Table 272 (p.144) | DLL stays locked through PD → fast exit. |
| (idle DRAM) | SRE | Preconditions: all banks precharged, `tRP` satisfied, no bursts in progress, `tMRD` / `tRFC` / prior-op timings satisfied; DES on last edge; DES for `tCPDED`; then CS_n LOW | rank (state-dependent) | `tCPDED`, `tRP`, `tMRD`, `tRFC` (as preconditions) | §4.9 (p.138) | These are entry *conditions*, not a command→command delay. |
| SRE | (in self-refresh) | `tCSL` MIN 10 ns (minimum time in self-refresh) | rank | `tCSL` | §4.9 Table 270 (p.140) | — |
| SRE | (SRX) | `tCKSRX` valid clock before SRX; `tCSH_SRexit` / `tCSL_SRexit` pulse widths | rank | `tCKSRX`, `tCSH_SRexit`, `tCSL_SRexit` | §4.9 Table 270 (p.140) | `tCKLCS` = valid clock required *after* SRE. |
| SRX | non-DLL commands (`ACT, MPC, MRW, PDE, PDX, PRE, REF, RFM, SRE, VREFCA, WRP`) | `tXS` = `tRFC1` | rank | `tXS` | §4.9 (p.139), Table 270 (p.140) | `tXS` grows with device density (= `tRFC1`). |
| SRX | DLL-required commands (`RD`, `WR`, `MRR`) | `tXS_DLL` = `tDLLK` | rank | `tXS_DLL` | §4.9 (p.139), Table 270 (p.140) | RMC: `WAIT_tXS` then `WAIT_tDLLK` states (§6.1). |
| SRX | (refresh obligation) | one extra REFab or `n × REFsb` on exit (counts toward postpone budget) | rank | — | §4.9 (p.139) | Refresh subsystem's responsibility (§7). |
| MPSM exit (MRW) | first valid command | `tMPSMX` = `tMRD` | device / global | `tMPSMX` | §4.12.4 Table 277 (p.148) | MPSM not architected in current RMC (§8). |
| SRE (`CA9 = L`, freq change) | (in self-refresh, freq change) | `tCSL_FreqChg` = `VrefCA_time` | rank | `tCSL_FreqChg` | §4.11.1 Table 275 (p.146) | Frequency-change flow not architected in current RMC (§8). |

**Explicitly not tabulated** (no meaningful architectural pair in the current RMC,
or covered elsewhere): ACT↔ACT / RD↔RD / WR↔WR / PRE↔PRE and all normal-traffic
core timing (`tRCD`, `tRAS`, `tRC`, `tRRD_L/S`, `tCCD_L/S`, `tCCD_L_WR`,
`tWTR_L/S`, `tRTP`, `tFAW`, `tPPD`) — these live in the scheduler timing
scoreboard, not here. REF↔ACT / REF↔REF / REFsb↔ACT (`tRFC1/2/sb`, `tREFSBRD`,
`tRRD_L`-for-REFsb) are the refresh subsystem's (§7, Table 280).

---

## 10. JEDEC parameter reference (verified values and TBD status)

All values below were located in `DDR5 Spec JESD79-5.pdf` this pass.

### 10.1 Verified numeric / formula values

| Symbol | Value in this edition | JESD79-5 ref |
|---|---|---|
| `tMRW` | `max(5 ns, 8 nCK)` | §3.4.4 Table 20 (p.18) |
| `tMRD` | `max(14 ns, 16 nCK)` | §3.4.4 Table 20 (p.18) |
| `tMRR` | `max(14 ns, 16 nCK)` | §3.4.4 Table 20 (p.18) |
| `tMRR_p` | `8 nCK` | §3.4.4 Table 20 (p.18); §4.17.4 (p.182) |
| `tDFE` | `80 ns` | §3.4.4 Table 20 (p.18) |
| MRR → MRW/MPC/VrefCA | `CL + BL/2 + 1` (tCK) | §3.4.4 Table 22 (p.19) |
| `tMPC_Delay` | `tMRD` | §4.15.3 Table 293 (p.168) |
| `tMPC_CS` | `3.5 … 8 nCK` | §4.15.3 Table 293 (p.168) |
| `tMC_MPC_Setup` / `tMC_MPC_Hold` | `3 nCK` | §4.15.3 Table 293 (p.168) |
| `tZQCAL` | MIN `1 µs` | §4.23.1 Table 329 (p.201) |
| `tZQLAT` | MIN `max(30 ns, 8 nCK)` | §4.23.1 Table 329 (p.201) |
| `tCPDED` | `max(5 ns, 8 nCK)` | §4.9 Table 270 / §4.10 Table 272 (p.140, 144) |
| `tPD` | `max(7.5 ns, 8 nCK)` | §4.10.1 Table 272 (p.144) |
| `tXP` | `max(7.5 ns, 8 nCK)` | §4.10.1 Table 272 (p.144) |
| `tACTPDEN` / `tPRPDEN` / `tREFPDEN` | `2 nCK` each | §4.10.1 Table 272 (p.144) |
| `tRDPDEN` | `RL + RBL/2 + 1` (nCK) | §4.10.1 Table 272 (p.144) |
| `tWRPDEN` | `WL + WBL/2 + (tWR/tCK(avg)) + 1` (nCK) | §4.10.1 Table 272 (p.144) |
| `tWRAPDEN` | `WL + WBL/2 + WR + 1` (nCK) | §4.10.1 Table 272 (p.144) |
| `tMRRPDEN` | `RL + 8 + 1` (nCK) | §4.10.1 Table 272 (p.144) |
| `tMRWPDEN` | `tMRD(min)` | §4.10.1 Table 272 (p.144) |
| `tMPCPDEN` | `tMPC_Delay` | §4.10.1 Table 272 (p.144) |
| PD duration cap | `5 × tREFI1` | §4.10.1 (p.143) |
| `tCSL` | MIN `10 ns` | §4.9 Table 270 (p.140) |
| `tCSH_SRexit` | MIN `13 ns`, MAX `30 ns` | §4.9 Table 270 (p.140) |
| `tCSL_SRexit` | MIN `3 nCK`, MAX `30 ns` | §4.9 Table 270 (p.140) |
| `tCKSRX` | MIN `max(3.5 ns, 8 tCK)` | §4.9 Table 270 (p.140) |
| `tCKLCS` | MIN `tCPDED + 1 nCK` | §4.9 Table 270 (p.140) |
| `tCASRX` | MIN `0 ns` | §4.9 Table 270 (p.140) |
| `tXS` | `= tRFC1` | §4.9 (p.139), Table 270 (p.140) |
| `tXS_DLL` | `= tDLLK` | §4.9 Table 270 (p.140) |
| `tMPSMX` | `= tMRD` | §4.12.4 Table 277 (p.148) |
| `tCSL_FreqChg` | `= VrefCA_time` | §4.11.1 Table 275 (p.146) |
| `tINIT0` | MAX `20 ms` | §3.3.1 Table 11 (p.12) |
| `tINIT1` | MIN `200 µs` | §3.3.1 Table 11 (p.12) |
| `tINIT2` | MIN `10 ns` | §3.3.1 Table 11 (p.12) |
| `tINIT3` | MIN `4 ms` | §3.3.1 Table 11 (p.12) |
| `tINIT4` | MIN `2 µs` | §3.3.1 Table 11 (p.12) |
| `tINIT5` | MIN `3 nCK` | §3.3.1 Table 11 (p.12) |
| `tXPR` | MIN `= tXS` | §3.3.1 Table 11 (p.12) |
| `tPW_RESET` | MIN `1 µs` | §3.3.2 Table 12 (p.13) |
| `tRST_ADC` | MAX `50 ns` | §3.3.2 Table 12 (p.13) |
| `tDLLK` | `1024 nCK` (≤ 3200 Mbps) … `2048 nCK` (≤ 6400 Mbps), per MR13 | §3.5.15 Table 53 (p.40) |
| `tREFI` (base) | `32 ms / 8192` = `3.9 µs` | §4.13.4 (p.155), Table 281 (p.156) |
| `tRFC1(min)` | 8 Gb `195 ns` · 16 Gb `295 ns` | §4.13.4 Table 282 (p.156) |
| `tRFC2(min)` | 8 Gb `130 ns` · 16 Gb `160 ns` | §4.13.4 Table 282 (p.156) |
| `tRFCsb(min)` | 8 Gb `115 ns` · 16 Gb `130 ns` | §4.13.4 Table 282 (p.156) |
| `tREFSBRD(min)` | `30 ns` (8 Gb, 16 Gb) | §4.13.3 Table 284 (p.156) |
| `tRFM1/2/sb(min)` | `= tRFC1/2/sb(min)` | §4.41 Table 378 (p.270) |
| `tRP` (referenced by PRE→MRR/MRW) | speed-bin dependent, e.g. DDR5-3200A `13.75 ns` | §10 Table 467 (p.350) |

### 10.2 TBD / undefined in this JESD79-5 edition

| Item | Status |
|---|---|
| `tMRRI` | **Symbol does not appear** anywhere in `DDR5 Spec JESD79-5.pdf`. Undefined in this edition. |
| `tCKSRE` | **Symbol does not appear.** The SRE-side stable-clock requirement is expressed as `tCKLCS` in Table 270. The RMC `T_CKSRE` / `WAIT_tCKSRE` naming has no JEDEC symbol in this edition (see §12). |
| `tMOD` | **Symbol does not appear.** This edition provides no `tMOD`-style per-register MR settle beyond `tMRD` / `tDFE`. |
| Table 23 (MRR/MRW constraints, **DQ ODT Enable**) | MRR-side cells **blank** in this edition. Undefined. |
| `tRFC1 / tRFC2 / tRFCsb` for **24 Gb / 32 Gb** | **TBD** in Table 282. |
| `tREFSBRD` for **24 Gb / 32 Gb** | **TBD** in Table 284. |
| `tWR`, `tFAW` (ns), and several speed bins for **DDR5-5200 and faster** | Rendered **light-grey / "should be considered TBD"** in §13.3 Tables (p.454–457). |
| PPR timing (`tPGM`, `tPGMPST`, `tPGM_Exit`) | Light-grey / not numeric in §4.29. |
| Manual ECS scrub duration | Not given numerically in §4.36 of this edition. |
| `VrefCA_time` (used by `tCSL_FreqChg`, MPC "Apply Vref") | Referenced as a timing but not given a numeric MIN in the inspected tables. |

---

## 11. Architecture integration summary

How each **supported** maintenance operation enters the controller and what it
blocks/gates. (Deferred/inventory items from §8 have no integration path.)

| Operation | Owner | Enters via | Blocks / gates | Completion signal | Timing state remembered |
|---|---|---|---|---|---|
| **Init sequence** | Init FSM (ME sub-FSM 1) | `INIT_KICK` (CSR); Init FSM drives DFI **directly** until `init_done` | Entire channel until `init_done`; then hands DFI + CKE to scheduler / Power Mgmt | `init_done` (one-way latch) | `tINIT1..tDLLK` read from `timing_reg_file`; `tXPR`, `tINIT0/2..5` **not** in the register file (§12) |
| **MRW (runtime)** | MR_Write FSM (ME sub-FSM 7) | CSR `MR_WR_REQ`; `me_cmd_*` → Stage-0 → Stage-4 (request contract **OPEN**, §12) | `gate_mr[rank]` at Stage 2 for `T_MRD`; bounded wait in `GATE_CHECK` for `gate_pwr==0` (+ optional bank idle) | `MR_WR_DONE` (+ `MR_WR_ERROR` if verify) | `T_MRD` deadline; issue `gc`. `timing_reg_file` sync is **software's** 2-step, no HW path (§4.1) |
| **MRR (MR4 / TUF poll)** | MR_Poll FSM (ME sub-FSM 6) | `gc ≥ next_poll_gc`; MRR via `me_cmd_*` (bypasses Stages 1–3); return on Read Data Path sideband | `mrr_busy` interlock (shared with MR_Write); DQ bus for the MRR burst | `mrr_data_valid` sideband | `next_poll_gc` (`MRR_POLL_INTERVAL = 32 × tREFI`); `T_MRD` |
| **MRR (MR_Write verify)** | MR_Write FSM | `VERIFY_MRR` state; same sideband | `mrr_busy` | `mrr_data` consumed → `CHECK_MATCH` | — |
| **ZQCal Start** | ZQcal FSM (ME sub-FSM 3, per-rank) | `gc ≥ next_zqcs`; `me_cmd_*` → Stage-0 → Stage-4 | none (background) | `tZQCAL` (`T_ZQCAL`) expiry | `next_zqcs` (from `tZQCS_interval` CSR); `T_ZQCAL` window |
| **ZQCal Latch** | ZQcal FSM | after `tZQCAL` + DQ idle | `gate_zq[rank]` at Stage 2; CA quiesced (`sts_ca_quiesced`) for `tZQLAT` | `tZQLAT` (`T_ZQLAT`) expiry | `T_ZQLAT` deadline |
| **PDE / PDX** | Power Mgmt FSM (ME sub-FSM 5, per-rank) | Autonomous: all-rank-idle + `pd_en` + `PD_IDLE_THRESHOLD` dwell + `gate_mr==0`. Exit: `bank_act_count` ↑ auto-triggers `PDX_WAIT` | `gate_pwr[rank]` at Stage 2; `dfi_cke[rank] = 0`; broadcast `POWER_DOWN` to all 16 bank rows | `T_XP` elapsed + `dfi_cke` reasserted → `gate_pwr` clears | `next_xp` (`T_XP`); `t*PDEN` entry fences **not** modelled (§12) |
| **SRE / SRX** | Power Mgmt FSM | `sr_entry` / `sr_exit` **system signals** (not CSR). No auto-wake on traffic | `gate_pwr[rank]`; `dfi_cke[rank] = 0`; broadcast `SELF_REFRESH`; Refresh FSM `ref_credits[rank]` **frozen** | `WAIT_tXS` → `WAIT_tDLLK` complete → broadcast `IDLE` | `next_xs` (`T_XS = tRFC1`), `T_DLLK`; `T_CKSRX` (state exists, not in `timing_reg_file` — §12) |
| **REF pre-empts POWER_DOWN** | Refresh FSM ↔ Power Mgmt FSM | REF to a `POWER_DOWN`-gated rank | **unconditionally** forces `PDX_WAIT` before REF issues (fixed invariant B.12-5, no CSR) | — | — |
| **REFab / REFsb / RFM** | Refresh FSM / RFM FSM (**teammate scope** for the implementation) | `ref_urgent` / `ref_due` / `rfm_req` → Stage-0 priority (`ref_urgent > ref_due > rfm_req > zq_due`) | `gate_rfc[rank]` (REFab) / per-bank gate (REFsb) for `T_RFC1` / `T_RFCsb`; `sts_ca_quiesced` | `T_RFC1` / `T_RFCsb` expiry (scoreboard `next_rfc` / `next_ref`) | `next_trefi`, `ref_credits`, postpone count, per-bank RAA counters (fed by Stage-4 `raa_inc_en`) |

**Contradictions found in the existing documentation** are reported in
[§12](#12-open-architecture-decisions), not resolved here.

---

## 12. Open architecture decisions

Only items that are genuinely unresolved after inspecting the repository.

1. **ZQ calibration across multiple ranks / external-resistor assumption.**
   JESD79-5 §4.23.2 requires the controller to serialize ZQCals when ranks share
   one 240 Ω resistor. The ZQcal FSM is per-rank with no cross-rank interlock in
   the inspected docs. Decision needed: (a) declare "one resistor per rank"
   (independent ZQCals) as a platform assumption, or (b) add a cross-rank
   `zq_bus_busy`-style interlock (analogous to `mrr_busy`). Currently silent.

2. **RFM ownership boundary.** The RAA counter is incremented by **Stage-4**
   (`raa_inc_en`) and lives in the Per-Rank FSM Table; the RFM FSM reads it and
   raises `rfm_req`. But (a) who enforces the JEDEC rule that at `RAAMMT` the DRAM
   blocks further ACT — the scheduler `can_act` gate, or the RFM FSM raising a
   hard block? (b) `RAAMMT` / `RAADec` CSRs are noted as **absent from the
   Handoff §17 table** (`RMC_MR_Programming_and_Power_Management_v1_9_11.md`
   §D.2, §D.4-1). (c) Is RFM the maintenance team's or the refresh teammate's to
   own end to end? Ambiguous — flag as an open ownership decision.

3. **Runtime MRW / MPC request interface into Stage-0.** The baseline supplies
   only MR_Poll's MRR channel (`me_cmd_valid / me_cmd_type[2:0] / me_cmd_rank`).
   The runtime-MRW Stage-0 request line, MRW address/data carriage to Stage 4,
   and whether a runtime MRW is a Stage-0 override contender (like REF) or a
   NOP-cycle-only grant, are **OPEN**
   (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.7, §E-1;
   `06_maintenance_engine.md` open item OM-3). Same gap applies to any runtime
   MPC (e.g. host-triggered ZQCal via `ZQCAL_TRIG`).

4. **Timing-scoreboard / `timing_reg_file` entries needed for maintenance.**
   The 23-parameter `timing_reg_file`
   (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.3) contains
   `T_MRD, T_XP, T_XS, T_DLLK, T_ZQCAL, T_ZQLAT, T_RFC1, T_RFCsb, T_REFI` but
   **not**: `T_RFC2` (FGR), `T_REFSBRD`, `T_MRW`, `T_MRR`, `T_MPC_DELAY`,
   `T_MPSMX`, `T_CKSRX`, `T_CKLCS`, `T_CSL`, `T_CPDED`, `T_CSH_SRexit`,
   `T_CSL_SRexit`, `T_XPR`, `T_INIT0..5`, the nine `t*PDEN` entry fences,
   `T_DFE`. `param_id` is `[4:0]` (32 max) with 23 used → only 9 slots free.
   Decision: widen `param_id` to `[5:0]`, or add a second ME-owned maintenance
   timing register file. Also: the architecture uses a **single `T_MRD`
   uniformly** for MR spacing and does **not** model `tMRW`, `tMRR`, or
   `CL + BL/2 + 1` MRR→MRW
   (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §C.4 acknowledges this as
   "a future refinement") — accept or refine?

5. **Maintenance command encoding width (`me_cmd_type`).** `architecture_reference.md`
   §20 shows `me_cmd_type [2:0]` (3-bit, MRR encoding); more than eight
   maintenance command forms are named across the docs
   (`REFab, REFsb, RFMab, RFMsb, MRW, MRR, MPC/ZQ, PDE, PDX, SRE, SRX`). The
   authoritative enum, encodings, and width are **OPEN**
   (`RMC_MR_Programming_and_Power_Management_v1_9_11.md` §C.2, §A.15). Must be
   frozen before MRW / PD / SR forms get encodings.

6. **`T_CKSRE` / `T_CKSRX` representation and naming.**
   `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §B.5 names a `WAIT_tCKSRE`
   state and §D.2/§D.3/§E-3 flag `T_CKSRE` / `T_CKSRX` as a 5-bit-legacy vs
   14-bit-timing-file conflict, and neither is in the 23-param file.
   **This JESD79-5 edition has no `tCKSRE` symbol** — the SRE-side requirement is
   `tCKLCS` (Table 270). Decision: model `tCKSRX` + `tCKLCS` and drop the
   `tCKSRE` name, or keep `T_CKSRE` as an internal alias for `tCKLCS`. Also
   resolve the register width.

7. **ME sub-FSM count (6 vs 7).** `00_ideas_and_naming.md` I9 and some comments
   say 6 sub-FSMs; `06_maintenance_engine.md` title and
   `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §A.15 say 7 (adding
   MR_Write). Documentation inconsistency to reconcile.

8. **CSR / register definitions absent from the baseline.** Noted in
   `RMC_MR_Programming_and_Power_Management_v1_9_11.md` §D.2/§D.4: `TRAIN_EN`,
   `RAAIMT`, `RAAMMT`, `RAADec`, `pd_en`, `tZQCS_interval`, `ZQCAL_TRIG`,
   `CL`/`CWL`, `PHY_WRLAT`/`PHY_RDLAT`/`FREQ_RATIO` are absent from the Handoff
   §17 table; almost no baseline CSR has a stated access type (RW/RO/W1C);
   `ZQCAL_TRIG` semantics undefined; `tZQCS_interval` has no width/access
   type/ZQcal-FSM port.

9. **MPC "background" ops without an owner.** VrefCA/VrefCS commands, Apply
   VrefCA/CS/RTT, DQS interval oscillator, Manual ECS, 1N/2N runtime set — all
   are architected nowhere (§8). Decision: add a dedicated "PHY periodic
   calibration" ME sub-FSM, fold selected ones into MR_Write, or formally declare
   them out of scope for v1.

---

## 13. Document validation

No Markdown linter (`markdownlint`, `mdl`, `prettier`, `vale`) is available in
this repository. Manual checks performed: heading hierarchy is contiguous
(`#` → `##` → `###`), all pipe-tables have matching column counts, all internal
anchors (`#N-...`) resolve to existing headings. No automated validation was run.
