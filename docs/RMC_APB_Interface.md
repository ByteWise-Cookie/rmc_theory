# RMC — APB / MC-Core Register Interface Architecture

## Legend

Every architectural claim in this document is tagged so the reader can tell what kind of
statement it is:

- **[DEFINED — \<source\>]** — stated by an existing document; not reinterpreted here.
- **[ASSUMPTION]** — not stated by any existing document, but required to make this
  architecture concrete; stated explicitly so it can be revisited.
- **[PROPOSED]** — a design decision made by this document (the APB architecture itself),
  as opposed to something inherited from MR/PM or Scheduler architecture.
- **[OPEN]** — explicitly left unresolved by the source document(s); this document
  reserves space/behavior for it without guessing a value.
- **[INFERENCE]** — a reasonable reading of a source document's structure or naming (e.g.
  a handshake's own name implying its initiator), not a verbatim statement from that
  source; flagged so it isn't mistaken for a direct quotation.

---

## 0. Document status and authority

This document defines a **standalone APB / MC-Core register interface architecture**. It
does not redesign, reinterpret, or extend MR Programming, Power Management, Scheduler, or
FAB *behavior* — it defines how the software-visible register set those documents already
describe is exposed over an APB slave.

**Authority for register behavior and inventory:**
`RMC_MR_Programming_and_Power_Management_v1_9_11.md` is authoritative for Mode Register
Programming and Power Management behavior and for the consolidated MC-Core register
inventory (its §D). Where `docs/sched_rebuild/*` describes MR/PM mechanisms that conflict
with v1.9.11 — specifically the "shared MR Read Arbiter" / `mrr_requester` tag and the
hardware `timing_apply_en` shadow→apply path described in `00_ideas_and_naming.md` (I28)
and `06_maintenance_engine.md` §3, and the `timing_reg_file` ownership line in
`11_mc_core_architecture.md` §4 ("CSR init + ME MR_Write (verify→apply)") — **v1.9.11
wins**, per the standing finding from earlier analysis in this line of work. This document
follows v1.9.11's model: no hardware path exists between MR_Write FSM and
`timing_reg_file`, and MRR arbitration is a bare `mrr_busy` interlock, not an arbiter block.

**Authority for current Scheduler/MC-Core architecture:** `docs/sched_rebuild/*`, except
for the stale MR/PM assumptions above.

**This document does not exist as prior art anywhere in the repository.** No APB
architecture, address map, or register-bus RTL structure is defined by any other document
— this is new design content, not a transcription of something already decided elsewhere.

This document supersedes nothing. `RMC_IO_Map.md` is untouched and remains v1.9.8/v1.9.9
legacy port reference; it is not updated or deprecated by this document.

---

## 1. Scope / non-goals

**In scope:**
- The APB slave protocol, transaction behavior, and its clock/reset domain relationship to
  `mc_clk`/`dfi_clk`.
- The register *ownership and placement* model (Global / Baseline / ME-local windows) and
  the address-map structure that realizes it.
- How the existing software-visible register inventory (v1.9.11 §D, plus FAB's CSR classes
  from `sched_rebuild/01_dfi_exchange_fabric.md` §2) maps onto that structure.
- CDC strategy at the clock boundaries this architecture touches: the reused Baseline ↔
  FAB boundary (§4, §9), and the `apb_clk`↔`mc_clk` relationship, whose existence and
  synchronization mechanism remain OPEN rather than resolved (§4).

**Out of scope (non-goals):**
- Redesigning MR_Write, Power Management, Refresh, RFM, ZQcal, or FAB behavior. Every FSM
  state, invariant, and signal referenced here is quoted from its authoritative source, not
  reinterpreted.
- Resolving any v1.9.11 §E OPEN item, any FAB `OF-*` open item, or any of the additional
  open items surfaced during this analysis (§13 lists all of them). This document reserves
  space and behavior for them; it does not guess values.
- RTL. No signal-level Verilog/VHDL, no synthesizable register-bank code, appears in this
  document.
- A generic internal register bus. FAB is exposed through the CDC mechanism its own
  document already specifies (§4, §9), not a new addressed bus.

---

## 2. Architectural overview and block diagram

**[PROPOSED]** Three logical register windows behind a single external APB slave, plus one
CDC boundary into FAB's clock domain for the subset of registers that physically originate
or terminate there.

```mermaid
flowchart TB
  HOST["Host / software"]
  APB["APB slave (single external port)\napb_clk / apb_presetn"]

  subgraph MCCORE["MC-Core register windows (decode clock domain — OPEN, see §4)"]
    direction TB
    GLOBAL["Global / top-level window\nINIT_KICK, TRAIN_EN, SOFT_RESET"]
    BASE["Baseline CSR window\nScheduler config, PM/Refresh/RFM config,\ntiming_reg_file, FAB CSR classes (2A-2E)"]
    ME["ME-local CSR window (inside ME)\nMR_WR_* only, beside MR_Write FSM"]
  end

  subgraph FABDOM["FAB — dfi_clk domain"]
    FAB["DFI Exchange Fabric (block 01)\nlocal generation/capture logic +\nsynchronized shadow copies"]
  end

  HOST --> APB
  APB -->|address decode| GLOBAL
  APB -->|address decode| BASE
  APB -->|address decode| ME
  BASE <-->|existing FAB CSR CDC convention (§4, §9)| FAB
```

- The **Global**, **Baseline**, and **ME-local** windows are all decoded by one flat
  top-level address decoder inside the APB slave — this is *not* a bridge-and-sub-decoder
  topology; it is a single decode stage with three address ranges, consistent with keeping
  this a small, auditable design rather than a distributed bus (§6, §9).
- **FAB is not a fourth window.** Its CSR storage lives in the Baseline window; only the
  synchronized signal crossing at the FAB clock boundary is new work, and it reuses the
  crossing structures `01_dfi_exchange_fabric.md` §4 already defines. See §9.
- **[OPEN]** The `apb_clk`/`apb_presetn` relationship to `mc_clk` is not stated by any
  source document, and this document does not assume one — it could be synchronous (same
  clock) or asynchronous (a genuine CDC boundary). Whichever it turns out to be, the CDC
  mechanism at that boundary is **implementation-TBD**, not fixed by this document (§4).

---

## 3. APB protocol signals and transaction behavior

**[PROPOSED]** Standard AMBA APB (the exact revision — APB3 vs. APB4 — is not fixed by any
source document; **[OPEN]**, treated as APB3-equivalent minimum, i.e. `PSLVERR` optional,
for this draft).

| Signal | Direction (master→slave unless noted) | Role |
|---|---|---|
| `PCLK` | in | APB clock — **[OPEN]** relationship to `mc_clk` (same or distinct) is not stated by any source document and is not assumed here. |
| `PRESETn` | in | APB domain reset. |
| `PADDR` | in | Register address (width **[OPEN]** — depends on final address-map size, §6). |
| `PSEL` | in | Slave select. |
| `PENABLE` | in | Access-phase qualifier (standard 2-phase SETUP/ACCESS). |
| `PWRITE` | in | 1 = write, 0 = read. |
| `PWDATA` | in | Write data, 32b **[ASSUMPTION]** (no source document states a bus width; every register, regardless of true bit-width, is exposed word-aligned with unused bits reserved-read-as-0). |
| `PRDATA` | out | Read data, 32b. |
| `PREADY` | out | Transfer-complete qualifier. **[PROPOSED, target only]** zero-wait-state (`PREADY` asserted the same cycle) is the target for Global/Baseline/ME-local decode, since address decode there is local and combinational. **[OPEN]** Whether any access actually requires wait states — including the Baseline↔FAB crossing (§9) and the now-open `apb_clk`↔`mc_clk` boundary (§4) — is implementation-TBD; zero-wait-state is not frozen as an architectural requirement, only stated as the design target. |
| `PSLVERR` | out | Optional (whether the final interface implements it depends on the APB3/APB4 choice above — **[OPEN]**, not resolved here). **[PROPOSED]** If implemented, `PSLVERR` is asserted on access to an unimplemented/reserved address (see §13 — this is how OPEN-width registers are handled at the protocol level: the address is reserved, not silently aliased). If the final interface does not implement `PSLVERR`, reserved-address behavior is **[OPEN]** (§6). |

**Transaction behavior:** standard 2-phase (SETUP then ACCESS) per-register read/write.
Write path: address decode + `PWRITE` + `PENABLE` directly enable the target register's
write strobe. Read path: address decode selects the target register onto a combinational
mux feeding `PRDATA`. No burst/streaming mode is proposed — every register access is a
single, independent transaction, consistent with all documented registers being either
slow-changing config, one-shot requests, or status/error reads (none are documented as
requiring burst access).

---

## 4. Clock/reset domains and CDC strategy

| Domain | Scope |
|---|---|
| `apb_clk` / `apb_presetn` | APB slave protocol logic. **[OPEN]** relationship to `mc_clk` is not stated by any source and not assumed here; the physical clock domain in which Global/Baseline/ME-local register storage and decode actually lands is therefore also implementation-TBD. |
| `mc_clk` | Scheduler, ME. **[DEFINED — `sched_rebuild/11_mc_core_architecture.md` §1]** This states only that Scheduler and ME logic run in this domain — it does **not** establish where APB-visible register storage (including the ME-local window) physically lands; that remains OPEN per the `apb_clk` row above. |
| `dfi_clk` | FAB, PHY. `dfi_clk == mc_clk` at baseline (CDC degenerate), kept parameterized for an async ratio. **[DEFINED — same source]** |

**[OPEN]** Whether `apb_clk` differs from `mc_clk` is not stated by any source document and
is not assumed by this document. If it turns out they differ, a CDC boundary exists between
the APB slave's decode logic and the `mc_clk`-domain consumers it drives (Global triggers,
Baseline config reads, ME-local MR_Write session fields) — but this is a boundary this
document merely notes as a possibility, not one any existing document defines. The
synchronization mechanism for it (if it is ever needed) is **implementation-TBD**: this
document does not commit to a specific scheme (2-flop, FIFO, or otherwise) here. This is
different from the Baseline↔FAB boundary below, where an existing source document already
specifies the crossing structure to reuse.

**Baseline ↔ FAB boundary (`mc_clk` ↔ `dfi_clk`):** this crossing is **not new** — it
reuses `01_dfi_exchange_fabric.md` §4 exactly as documented: **[DEFINED —
`01_dfi_exchange_fabric.md` §4]**

| Crossing | Direction | Structure |
|---|---|---|
| CSR access (config write) | Baseline → FAB | 2-flop sync on control bits |
| CSR status (read mirror) | FAB → Baseline | re-synced back |
| Command/write-data/read-data | core↔dfi | async FIFOs (unrelated to CSR, data-plane only) |

No new crossing structure is proposed for FAB; see §9 for the register-class breakdown.

---

## 5. Global / Baseline / ME-local register ownership model

**[PROPOSED]**, refined from the classification exercise conducted before this freeze.

- **Global/top-level:** system bring-up/reset primitives that logically precede or
  supersede any single block's operation — `INIT_KICK`, `TRAIN_EN`, `SOFT_RESET`. Not
  owned by Scheduler, ME, or FAB specifically, even though their consumers (Init FSM,
  global reset fan-out) live inside those blocks.
- **Baseline CSR:** every register that is a continuously-sampled configuration value or a
  passively-read status/error flag, with **no software-visible multi-cycle session
  lifecycle** (no busy/done/error triad gated by live FSM state). This is the majority of
  the inventory: Scheduler tuning, Refresh/RFM/PM policy config, `timing_reg_file`, and — by
  the decision frozen this turn — all of FAB's CSR classes.
- **ME-local CSR:** registers that participate in a genuine session with hardware-enforced
  invariants tying their validity to live ME state (`GATE_CHECK`, the `mrr_busy`
  interlock, `gate_mr`/`gate_pwr` mutual exclusion). Under v1.9.11's actual inventory this
  is exactly the nine `MR_WR_*` registers — no other ME sub-FSM (Refresh, ZQcal, RFM, Power
  Mgmt, MR_Poll) contributes a session-coupled, host-visible register.

**Test applied (restated for this document's own record):** *session test* — does the
register's value only make sense evaluated against a live, multi-phase FSM state, with
hardware invariants coupling it to another gate/interlock? *Locality-matters test* — would
physically colocating the register's authoritative storage with its consumer change
correctness or timing, versus a synchronized central copy being architecturally
equivalent? A register failing both tests is Baseline regardless of which internal block
happens to consume it.

---

## 6. Proposed address-map structure

**[PROPOSED]** — a *structure*, not a finalized numeric map. Because many registers' true
widths are OPEN — a few as specifically-numbered v1.9.11 §E items (e.g. `T_CKSRE`/`T_CKSRX`,
§E-3), most simply left OPEN in v1.9.11 §D.2's own table cells (per §D.4's observation that
access types are largely unstated across the baseline set), and FAB's widths OPEN per its
own `OF-1`/`OF-4` — this document fixes window boundaries and grouping, not committed
per-register byte offsets.

```
0x0000_0000 – 0x0000_00FF   Global / top-level window        (illustrative base only)
0x0000_0100 – 0x0000_0FFF   Baseline CSR window
    0x100 – 0x1FF               Scheduler configuration
    0x200 – 0x2FF               Refresh / RFM / Power-Mgmt configuration
    0x300 – 0x3FF               Legacy timing/PHY config (CL/CWL/PHY_*/FREQ_RATIO) —
                                 see §13, possible FAB duplication, not finalized
    0x400 – 0x4FF               timing_reg_file aperture (param_id-indexed sub-window)
    0x500 – 0x5FF               FAB — static config (2A)
    0x600 – 0x6FF               FAB — timing config (2B)              [widths OPEN]
    0x700 – 0x7FF               FAB — live status (2C)
    0x800 – 0x8FF               FAB — update/handshake (2D)           [widths OPEN]
    0x900 – 0x9FF               FAB — error/IRQ (2E)
0x0000_1000 – 0x0000_10FF   ME-local CSR window (MR_WR_* only)
0x0000_1100 – ...           Reserved — future OPEN-item resolution, future windows
```

Every group is word-aligned (32-bit, per §3's assumption); an OPEN-width register still
consumes at least one reserved word so that resolving its width later does not require
renumbering the map (**[PROPOSED]**, mirrors the same reservation strategy discussed for
Option A/C in the prior architecture-options analysis). **[PROPOSED]** If `PSLVERR` is
implemented, access to a reserved-but-unassigned address returns an APB error (`PSLVERR`).
**[OPEN]** If the final APB revision/interface does not implement `PSLVERR`, reserved-address
behavior (e.g. reads as 0 / ignores writes) is not fixed by this document — see §3's
APB3/APB4 **[OPEN]** item.

This structure keeps the decode a single flat stage (per §2) while still giving the
register table (§7) a stable logical grouping independent of the still-unresolved widths.

---

## 7. Register table

Columns: **Width** and **Access** are quoted verbatim from source where stated, and marked
`OPEN` where the source marks them open — no value is invented in either column.
**Type** is this document's own **[PROPOSED]** behavioral classification, defined in §8; it
is assigned independently of the source's **Access** column, so a **Type** value (e.g.
"persistent RW") next to an `OPEN` **Access** cell is this document's proposed convention
for how that register would behave, not a source-defined access permission. **Status** cites
the source and flags anything carried forward unresolved.

### 7.1 Global / top-level

| Register | Width | Access | Type | Default | Owner | Status |
|---|---|---|---|---|---|---|
| `INIT_KICK` | 1b | OPEN | pulse/request | 0 | Init FSM | DEFINED (v1.9.11 §D.2) width/default; access OPEN |
| `TRAIN_EN` | 1b | OPEN | persistent RW | OPEN | Init FSM | DEFINED (v1.9.11 §D.2) width; "absent from Handoff §17." Note: legacy `mc_core_spec_v2.tex` implies a multi-bit, indexable field (`TRAIN_EN[WL]`) — non-authoritative, flagged, not reconciled. |
| `SOFT_RESET` | OPEN | OPEN (trigger-style) | pulse/request | 0 | Global | DEFINED (v1.9.11 §D.2) default; width/access OPEN |

### 7.2 Baseline CSR — Scheduler configuration

| Register | Width | Access | Type | Default | Owner | Status |
|---|---|---|---|---|---|---|
| `WR_HIGH_WM` | OPEN | OPEN | persistent RW | 16 | Watermark Mgr (implied) | DEFINED (v1.9.11 §D.2); default conflicts with `mc_core_spec_v2.tex` (32) — flagged, not reconciled |
| `WR_LOW_WM` | OPEN | OPEN | persistent RW | 4 | Watermark Mgr (implied) | Same — default conflicts with `mc_core_spec_v2.tex` (8) |
| `AGE_THR1` | OPEN | OPEN | persistent RW | 64 | Stage 2/3 | DEFINED (v1.9.11 §D.2) |
| `AGE_THR2` | OPEN | OPEN | persistent RW | 256 | Stage 2/3 | DEFINED (v1.9.11 §D.2) |
| `RD_STARVATION_THR` | OPEN | OPEN | persistent RW | 12480 (9×tREFI) | Stage 3 | DEFINED (v1.9.11 §D.2) |
| `WR_STARVATION_THR` | OPEN | OPEN | persistent RW | 37440 (3×RD) | Stage 3 | DEFINED (v1.9.11 §D.2) |
| `WINDOW_SIZE` | OPEN | OPEN | persistent RW | 2×tREFI | Bank Partition Ctrl | DEFINED (v1.9.11 §D.2) |
| `PAGE_POLICY` | 2b | OPEN | persistent RW | `00` (Open) | Scheduler | DEFINED (v1.9.11 §D.2) width/default |

### 7.3 Baseline CSR — Refresh / RFM / Power-Management configuration

| Register | Width | Access | Type | Default | Owner | Status |
|---|---|---|---|---|---|---|
| `REF_MODE` | `[1:0]` | OPEN | persistent RW | `00` | Refresh FSM | DEFINED (v1.9.11 §D.2) width/default |
| `MRR_POLL_INTERVAL` | OPEN | OPEN | persistent RW | 32×tREFI | MR_Poll FSM | DEFINED (v1.9.11 §D.2) default |
| `pd_en` | 1b | OPEN | persistent RW | OPEN | Power Mgmt FSM | DEFINED (v1.9.11 §D.2) width. Placement: Baseline, not ME-local — see §5's test; corrects a tentative ME-local placement considered earlier in this line of work. |
| `PD_IDLE_THRESHOLD` | OPEN | OPEN | persistent RW | 64 cycles | Power Mgmt FSM | DEFINED (v1.9.11 §D.2) default; consumer resolved per v1.9.11 §B.5/§B.10 |
| `RAAIMT` | `[7:0]` | OPEN | persistent RW\* | OPEN | RFM FSM | DEFINED (v1.9.11 §D.2) width. \*Access flagged: legacy (non-authoritative) source implies Init-FSM-mirrored-from-MR58 rather than plain host-write — not resolved, see §13 |
| `RAAMMT` | 8b | OPEN | persistent RW\* | OPEN | RFM-related logic OPEN | Same flag as `RAAIMT` |
| `RAADec` | 4b | OPEN | persistent RW | OPEN | RFM FSM | DEFINED (v1.9.11 §D.2) width |
| `tZQCS_interval` | OPEN | OPEN | persistent RW | 128 ms (→ cycles) | ZQcal FSM | DEFINED (v1.9.11 §D.2) default; "no formal ZQcal port" |
| `ZQCAL_TRIG` | OPEN | "Host write, exact semantics OPEN" | OPEN (pulse-shaped, unconfirmed) | OPEN | ZQcal FSM | DEFINED existence (v1.9.11 §D.2 / `mc_core_spec_v2.tex` §7.2); everything else OPEN. Window placement here is by elimination (no ZQcal-local window exists in the frozen architecture) — see §13. |
| `T_CKSRE` | CONFLICT: 5b legacy vs. 14b proposed | OPEN | persistent RW (timing) | OPEN | Power Mgmt FSM | OPEN — v1.9.11 §E-3, representation unresolved |
| `T_CKSRX` | Same conflict | OPEN | persistent RW (timing) | OPEN | Power Mgmt FSM | OPEN — v1.9.11 §E-3 |

### 7.4 Baseline CSR — legacy timing/PHY config (flagged, possible FAB duplication)

| Register | Width | Access | Type | Default | Owner | Status |
|---|---|---|---|---|---|---|
| `CL` | 7b | OPEN | persistent RW | OPEN | Read/Write Data Path | DEFINED (v1.9.11 §D.2) width. See §13 — possible duplication with FAB 2B / `timing_reg_file` `RL`. |
| `CWL` | 7b | OPEN | persistent RW | OPEN | Read/Write Data Path | Same flag (possible duplication with `WL`) |
| `PHY_WRLAT` | 6b | OPEN | persistent RW | OPEN | DFI data paths | Possible duplication with FAB `t_phy_wrlat` (§2B) |
| `PHY_RDLAT` | 6b | OPEN | persistent RW | OPEN | DFI data paths | Possible duplication with FAB `t_rddata_en` (§2B) |
| `FREQ_RATIO` | 2b | OPEN | persistent RW | OPEN | DFI data paths | Possible duplication with FAB `cfg_freq_ratio` (§2A) |

### 7.5 Baseline CSR — structural/uncertain

| Register | Width | Access | Type | Default | Owner | Status |
|---|---|---|---|---|---|---|
| `FIFO_DEPTH` | OPEN | OPEN | persistent RW (uncertain) | 16 | — | DEFINED existence (v1.9.11 §D.2), but `RMC_IO_Map.md` §0 treats it as a compile-time RTL parameter (`N_REQ_CREDITS = FIFO depth`, init-time), not a runtime register — flagged, not resolved. If it turns out to be compile-time-only, it should not be APB-exposed at all; retained here provisionally. |

### 7.6 Baseline CSR — `timing_reg_file` (single central instance, not a flat register)

**[DEFINED — v1.9.11 §D.3]** `param_id[4:0] → nCK value[13:0]`. Access: **RW via the
existing CSR write port** (`csr_wr_en`/`csr_param_id`/`csr_param_val`), **RO via all read
ports** (combinational, multi-port). No per-parameter reset/default value is stated. This
document exposes this file via one address sub-window (an indirect `param_id` + `param_val`
pair, or a direct per-param offset — **[OPEN]**, not decided here since it's an
address-map-mechanics choice orthogonal to the register inventory question this document
is scoped to answer) rather than flattening it into 23 individually-addressed registers;
either realization preserves the single-write-port invariant (v1.9.11 §A.6).

23 baseline params **[DEFINED — v1.9.11 §D.3, confirmed against `RMC_IO_Map.md` §17]**:
`T_RCD, T_RP, T_RAS, T_WR, T_RTP, T_CCD_L, T_CCD_L_WR, T_CCD_L_WR2, T_WTR_L, T_WTR_S,
T_RRD_L, T_RRD_S, T_FAW, T_RFC1, T_RFCsb, T_REFI, T_MRD, T_XP, T_XS, T_DLLK, T_ZQCAL,
T_ZQLAT, T_RTW`. `T_CKSRE`/`T_CKSRX` are explicitly **not** members of this list (§13).

### 7.7 Baseline CSR — FAB register classes

Housed in Baseline per the frozen decision; §9 covers the CDC mechanism, not repeated here.

**2A Static config** — all RW, persistent, written once at init:

| Reg | Width | Access | Type | Status |
|---|---|---|---|---|
| `cfg_freq_ratio` | 2b | RW | persistent RW | DEFINED |
| `cfg_2n_mode` | 1b | RW | persistent RW | DEFINED |
| `cfg_dram_density` | 3b | RW | persistent RW | DEFINED |
| `cfg_dq_width` | 2b | RW | persistent RW | DEFINED |
| `cfg_rank_count` | 2b | RW | persistent RW | DEFINED |
| `cfg_bl_mode` | 2b | RW | persistent RW | DEFINED |
| `cfg_geardown_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_dbi_wr_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_dbi_rd_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_ca_parity_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_wr_crc_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_rd_crc_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_odt_en` | 1b | RW | persistent RW | DEFINED |
| `cfg_cs_map` | Nb (parameterized) | RW | persistent RW | DEFINED (width parameterized, not numeric) |

**2B Timing config** — labeled RW, persistent; **all widths OPEN** — the source document
gives no width column for this class at all (`01_dfi_exchange_fabric.md` §2B has only
`Reg`/`Meaning` columns), consistent with `OF-1` ("exact CSR address map + access widths —
deferred to register-map pass"):

| Reg | Width | Access | Type | Status |
|---|---|---|---|---|
| `t_phy_wrlat` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_phy_wrdata` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_phy_rdlat` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_rddata_en` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_phy_wrcslat` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_phy_rdcslat` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_ctrl_delay` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_dram_clk_enable` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_wrdata_delay` | OPEN | RW | persistent RW | OPEN (width) — `OF-1` |
| `t_phy_wrlvl_*` | OPEN | RW | persistent RW | OPEN — class only, not individually enumerated, `OF-4` |
| `t_phy_rdlvl_*` | OPEN | RW | persistent RW | OPEN — class only, not individually enumerated, `OF-4` |

(`Access: RW` here reflects the class-level "RW, PHY-negotiated latencies" label
`01_dfi_exchange_fabric.md` §2B gives the whole group, not a per-register statement.)

**2C Live status** — all RO, status:

| Reg | Width | Access | Type | Status |
|---|---|---|---|---|
| `sts_init_complete` | 1b | RO | RO status | DEFINED |
| `sts_dram_clk_state` | 1b | RO | RO status | DEFINED |
| `sts_wr_buf_level` | log2(depth) | RO | RO status | DEFINED |
| `sts_rd_buf_level` | log2(depth) | RO | RO status | DEFINED |
| `sts_ca_buf_level` | log2(depth) | RO | RO status | DEFINED |
| `sts_wr_cdc_full` | 1b | RO | RO status | DEFINED |
| `sts_rd_cdc_full` | 1b | RO | RO status | DEFINED |
| `sts_lp_state` | 2b | RO | RO status | DEFINED |
| `sts_upd_state` | 2b | RO | RO status | DEFINED |
| `sts_training_state` | 3b | RO | RO status | DEFINED |
| `sts_freq_ratio_now` | 2b | RO | RO status | DEFINED |

Note: `sts_ca_quiesced` is referenced in `01_dfi_exchange_fabric.md` §2D's note and §5's
core-side contract, but is **not** listed in §2C's table — a gap in the source document
itself, not resolved here (§13).

**2D Update/handshake** — request/status/timer sub-classes; **all widths OPEN** (no width
given in source):

| Reg | Width | Access (per source) | Type | Note |
|---|---|---|---|---|
| `upd_ctrl_req` | OPEN | W1S | pulse/request | **[INFERENCE]** software/MC-initiated, from the handshake's source name "Controller update" |
| `upd_ctrl_ack` | OPEN | RO | RO status | — |
| `upd_ctrl_interval` | OPEN | RW (timer) | persistent RW | — |
| `upd_phy_req` | OPEN | RO | RO status | **[INFERENCE]** PHY-initiated, externally driven, from the handshake's source name "PHY update" |
| `upd_phy_ack` | OPEN | W1S | pulse/request | **Ownership OPEN** — software-driven vs. autonomous hardware ack, unresolved (§13) |
| `upd_phy_type` | OPEN | RO | RO status | — |
| `upd_phymstr_req` | OPEN | RO | RO status | **[INFERENCE]** PHY-initiated, from the handshake's source name "PHY master" |
| `upd_phymstr_ack` | OPEN | W1S | pulse/request | Same ownership flag as `upd_phy_ack` |
| `upd_phymstr_state` | OPEN | RO | RO status | — |
| `upd_freq_req` | OPEN | W1S | pulse/request | **[INFERENCE]** software/MC-initiated, from the handshake's source name "Freq change" |
| `upd_freq_ratio` | OPEN | RW | persistent RW | — |
| `upd_freq_ack` | OPEN | RO | RO status | — |

**2E Error/IRQ**:

| Reg | Width | Access | Type |
|---|---|---|---|
| `err_dfi_error` | 1b | RO+W1C | W1C |
| `err_dfi_error_info` | Nb | RO | RO status |
| `err_wr_cdc_ovf` | 1b | RO+W1C | W1C |
| `err_rd_cdc_ovf` | 1b | RO+W1C | W1C |
| `err_rddata_timeout` | 1b | RO+W1C | W1C |
| `err_ca_parity` | 1b | RO+W1C | W1C |
| `err_wr_crc` | 1b | RO+W1C | W1C |
| `err_rd_crc` | 1b | RO+W1C | W1C |
| `err_underrun_wr` | 1b | RO+W1C | W1C |
| `err_mask` | Nb | RW | persistent RW |
| `err_status` | Nb | RO | RO status |

### 7.8 ME-local CSR (inside ME, beside MR_Write FSM)

**[DEFINED — v1.9.11 §A.9/§A.10/§D.2]**

| Register | Width | Access | Type | Default | Status |
|---|---|---|---|---|---|
| `MR_WR_REQ` | 1b (implied) | Pulse | pulse/request | 0 | DEFINED |
| `MR_WR_ADDR` | `[5:0]` | RW | request field | — | DEFINED |
| `MR_WR_DATA` | `[7:0]` | RW | request field | — | DEFINED |
| `MR_WR_RANK` | `[RANK_BITS-1:0]` | RW | request field | — | DEFINED |
| `MR_WR_REQUIRE_IDLE` | 1b (implied) | RW | request field | 1 | DEFINED |
| `MR_WR_VERIFY` | 1b (implied) | RW | request field | 0 | DEFINED |
| `MR_WR_BUSY` | 1b (implied) | RO | status | — | DEFINED |
| `MR_WR_DONE` | 1b (implied) | RO, auto-clears on next `MR_WR_REQ` | status | — | DEFINED existence; access-type label itself is v1.9.11 §E-5 OPEN ("doesn't map cleanly onto RW/RO/W1C") |
| `MR_WR_ERROR` | 1b | RO | status | — | DEFINED |

---

## 8. Persistent RW, pulse/request, RO status, and W1C semantics

**[PROPOSED]** — four register-behavior conventions used consistently across all three
windows, referenced by the **Type** column above:

- **Persistent RW** — plain flops; host writes a value, it holds until overwritten;
  continuously read by hardware. No side effect on write beyond storing the value (e.g.
  `PAGE_POLICY`, `cfg_freq_ratio`, `AGE_THR1`).
- **Pulse/request** — a write (to a bit, or write-1-to-set for `W1S`-labeled registers)
  generates a single-cycle strobe consumed by the target FSM the same cycle or latched into
  its clock domain; the bit does not persist as "1" for the host to read back (e.g.
  `INIT_KICK`, `SOFT_RESET`, `MR_WR_REQ`, `upd_ctrl_req`/`upd_freq_req`).
- **RO status** — read-only, continuously or event-driven reflects internal hardware
  state; no write path exists (e.g. `MR_WR_BUSY`, `sts_wr_buf_level`, `upd_ctrl_ack`).
- **W1C** — read-only value with a write-1-to-clear side effect on the same address; used
  for FAB's sticky error flags (§7.7, 2E). Distinct from pulse/request: the *read* side
  carries real information (which error fired) that pulse/request registers don't have.

Only registers whose **Type** column is itself marked "OPEN" or "unconfirmed" in §7
(currently `ZQCAL_TRIG`) are left without one of these four conventions — assigning one
there would be guessing at semantics the source explicitly leaves undefined. Elsewhere in
§7, a **Type** value is this document's proposed classification per the conventions above
regardless of whether the corresponding **Access** cell is source-defined or marked `OPEN`;
**Type** is never itself a source-defined access permission, even where it reads as a
concrete label like "persistent RW."

---

## 9. FAB CSR interaction

**[PROPOSED — an ownership model, not a fixed mechanism]** FAB's CSR storage for
2A/2B/2C-mirror values and 2E's mask/clear side is placed in the Baseline window, per the
frozen decision. That placement (*where the addressable storage lives*) is what's fixed.
The update (write-propagation) and visibility (read-mirroring) *mechanics* described below
are this document's proposal for how that ownership model could be realized — they are not
themselves fixed, and they remain genuinely open wherever the underlying FAB register class
is itself open in `01_dfi_exchange_fabric.md` (see §13 items 9, 11, 12), most notably 2B
(widths entirely undefined per `OF-1`/`OF-4`) and 2D's ack-ownership question. FAB itself
retains, locally, only what correctness requires regardless of how the update/visibility
mechanics are finally realized:

- **2A/2B (config):** proposed model — a synchronized shadow register in FAB's own
  `dfi_clk` domain, refreshed on Baseline write via the existing 2-flop CSR-access sync
  (§4), with FAB's phase packer/unpacker reading the local shadow copy every cycle rather
  than reaching back into `apb_clk`/`mc_clk` domain state directly. This is proposed and
  illustrative, not settled: for 2A the register widths are defined by FAB's source, but
  for 2B specifically, since widths are entirely undefined (`OF-1`/`OF-4`), the concrete
  synchronization width/structure is correspondingly open and not fixed by this document.
- **2C (status):** the underlying counters/flags (buffer occupancy, CDC full) are generated
  by FAB's own internal pointers — this generation logic is mandatorily local regardless of
  ownership model. Only the read-mirror crossing into Baseline (the existing "status
  re-synced back" convention) is what makes them APB-visible; the exact per-bit re-sync
  structure is not itemized by FAB's source and is not invented here beyond that general
  convention.
- **2D (update/handshake):** proposed model — `upd_ctrl_req`/`upd_freq_req`
  (software-initiated) would follow the same write-side sync pattern proposed for 2A/2B;
  `upd_phy_req`/`upd_phymstr_req` are inherently FAB-side-generated (mirroring an external
  PHY-driven DFI signal) and would only need the existing sync-back path. Note that 2D's
  widths are themselves entirely open per FAB's own source (§7.7), so this proposed
  synchronization detail is correspondingly provisional. **The open question is
  `upd_phy_ack`/`upd_phymstr_ack`** — if these are software-driven per event, routing them
  through Baseline plus two CDC hops (`apb_clk`→wherever Baseline's flops are clocked, then
  Baseline→`dfi_clk`) risks DFI update-handshake timing; if they are autonomously generated
  by FAB's own quiesce sequencer once `sts_ca_quiesced` clears, there is no software
  involvement in the ack path and no risk. **This document does not resolve which** (§13) —
  it proceeds on the centralized ownership model as the primary proposal, consistent with
  the frozen decision, and documents the fallback: if the ack turns out to be
  software-driven, the narrower Option-C-style carve-out (a small FAB-local decode limited
  to just the 2D class) should be revisited rather than building a full FAB window.
- **2E (error):** the one-cycle error *pulse* must be captured into a sticky local flop
  inside FAB the instant it fires (mandatory-local, same reasoning as 2C, independent of
  ownership model); the host-facing W1C clear and `err_mask` write are proposed to use the
  standard write-side sync pattern, consistent with their being low-frequency and not
  timing-critical — this is proposed, not asserted as the only viable mechanism.

**No new addressed bus is introduced for FAB.** Every crossing described above is a
point-to-point synchronized signal or FIFO, reusing `01_dfi_exchange_fabric.md` §4's
already-documented convention — this directly satisfies the "no generic N-way register
bus" constraint for the one block where the question was live.

---

## 10. MR_Write APB interaction

**[DEFINED — v1.9.11 §A.2–§A.4]**, restated in terms of this document's window structure:

1. Software issues a request as a sequence of **ME-local window** writes: stage
   `MR_WR_ADDR`, `MR_WR_DATA`, `MR_WR_RANK`, `MR_WR_REQUIRE_IDLE`, `MR_WR_VERIFY`, then pulse
   `MR_WR_REQ`.
2. MR_Write FSM proceeds through `IDLE → WAIT_REQ → GATE_CHECK → ISSUE_MRW → WAIT_tMRD →
   [VERIFY_MRR → WAIT_RDDATA → CHECK_MATCH] → DONE`, entirely inside ME, with no APB
   transaction required mid-sequence.
3. Software polls `MR_WR_BUSY` (ME-local window, RO) until it clears, then checks
   `MR_WR_ERROR`.
4. **Only if** `MR_WR_ERROR == 0` and the register was timing-affecting, software performs
   a **separate, ordinary write to `timing_reg_file`** — a **Baseline window** transaction,
   via the existing `csr_wr_en`/`csr_param_id`/`csr_param_val` path (§7.6). This is a plain
   CSR write, indistinguishable in hardware from any other `timing_reg_file` write; nothing
   connects it to the ME-local session that preceded it.

This makes the ME-local/Baseline window split a direct, concrete realization of v1.9.11's
own explicit statement that there is "no signal, register, or datapath connecting MR_Write
FSM to `timing_reg_file`" (§A.4) — step 4 above is necessarily a second, independent APB
transaction into a different window, by construction, not by this document's choice.

---

## 11. Power-management/timing-register interaction

**[DEFINED — v1.9.11 §B]**, placement per §5's test:

- `pd_en` and `PD_IDLE_THRESHOLD` are Baseline-window, continuously-read policy inputs to
  Power Mgmt FSM's autonomous `PD_ENTRY_CHECK` gate. Software sets policy once; the FSM
  decides on its own when to act — no request/response session exists.
- `gate_pwr[rank]` itself is **not** exposed via APB at all. v1.9.11 §D.1 explicitly
  excludes internal runtime state (including `gate_*` signals) from the host-visible
  register set — this document does not add it, consistent with "do not invent missing
  fields."
- The `gate_mr`/`gate_pwr` mutual-exclusion invariant (v1.9.11 §A.12-4/§B.12-6) is enforced
  entirely inside ME's hardware; the APB layer never arbitrates between MR_Write and Power
  Management directly, and has no visibility into or role in that invariant.
- `T_CKSRE`/`T_CKSRX` sit in the Baseline window by the same continuously-read-timing-
  constant reasoning as the rest of `timing_reg_file`-adjacent config, but their
  representation conflict (§E-3) means their exact address/word-packing is not finalized by
  this document (§7.3, §13).

---

## 12. Reset and SOFT_RESET handling

- `PRESETn` **[ASSUMPTION]** resets the APB slave's own protocol logic and, by extension,
  whatever register storage physically lives in the `apb_clk` domain (Global, Baseline,
  ME-local, if `apb_clk` domain storage is how they're implemented).
- `mc_clk`-domain hardware reset (system-level, outside this document's scope) resets
  ME/Scheduler/FAB FSM logic independently.
- `SOFT_RESET` (Global window, pulse/request) is a host-triggered pulse register, placed in
  the Global window per §5's ownership model. That APB-level trigger/register placement is
  the only thing this document fixes about it.
- **[OPEN]** Reset scope and persistence behavior are not defined by this document and are
  not assumed. No authoritative document (v1.9.11 or `sched_rebuild`) states which FSMs
  `SOFT_RESET` resets, how that reset is sequenced, or whether it re-applies default values
  to Baseline persistent config registers or `timing_reg_file`. The only source that
  describes any scope at all is the non-authoritative legacy `mc_core_spec_v2.tex`
  ("Synchronous soft-reset of all MC Core FSMs"), which is not treated as authoritative
  here. Both reset scope and config-persistence behavior are implementation-TBD.

---

## 13. Handling of v1.9.11 §E OPEN items (and related open items surfaced by this analysis)

None of the following are resolved by this document. Each is reserved in the address map
(§6) and marked `OPEN` in the register table (§7) rather than guessed.

**v1.9.11 §E items:**
1. Runtime-MRW command interface (Stage-0 request contract, `me_cmd_type` enum/width) — §E-1.
2. Baseline CSR access types (RW/RO/W1C) largely undefined across the inventory — §E-2.
   This document's `Access: OPEN` cells throughout §7 are a direct consequence.
3. `T_CKSRE`/`T_CKSRX` representation conflict (5b legacy vs. 14b proposed) — §E-3.
4. `tZQCS_interval` formal interface (width/access/port) — §E-4.
5. `MR_WR_DONE`'s access-type label — §E-5.

**Additional items surfaced during this line of analysis (not v1.9.11-labeled, but
directly relevant to this document):**
6. `RAAIMT`/`RAAMMT` write ownership — plain host-RW vs. possibly hardware-mirrored from
   MR58 via Init FSM (non-authoritative legacy source only).
7. `FIFO_DEPTH` — register vs. compile-time RTL parameter status unresolved.
8. `ZQCAL_TRIG` — existence confirmed, width/semantics/session-shape entirely undefined.
9. `CL`/`CWL`/`PHY_WRLAT`/`PHY_RDLAT`/`FREQ_RATIO` (v1.9.11 legacy) vs. FAB's `t_phy_wrlat`/
   `cfg_freq_ratio`/etc. (§2A/2B) — possible duplication across two different-vintage
   documents, not reconciled.
10. `sts_ca_quiesced` — referenced in FAB's own prose but absent from its own §2C register
    table (a gap in the source document itself).
11. `upd_phy_ack`/`upd_phymstr_ack` ownership (software-driven vs. autonomous) — determines
    whether the "no FAB window" decision remains correct (§9).
12. FAB `OF-1` through `OF-5` generally (exact CSR address map/widths, buffer depths, async
    vs. sync baseline, training-path register detail, CA parity/CRC recovery policy).

---

## 14. Verification considerations

- **Register model:** three logical register banks (Global, Baseline, ME-local) behind one
  APB agent — a single UVM-style (or equivalent) register model can represent all three if
  it tags each register with its window, since the external protocol is uniform (§2, §6).
- **APB protocol compliance:** standard APB timing/handshake checks against the single
  external slave; independent of window structure.
- **CDC verification:** the `apb_clk`↔`mc_clk` boundary (§4, new) and the reused
  `mc_clk`↔`dfi_clk` boundary at Baseline↔FAB (§9, not new — existing FAB CDC checks should
  already cover it, extended to the CSR signals now crossing there too).
- **Session invariants:** MR_Write's five hardware invariants (v1.9.11 §A.12) need directed
  tests distinct from plain register read/write checks — at-most-one-outstanding-request,
  `gate_mr`/`gate_pwr` mutual exclusion, at-most-one-outstanding-MRR via `mrr_busy`,
  `GATE_CHECK` gating. These are ME-internal correctness properties that the APB layer must
  not be able to violate. This document does not itself define the acceptance/rejection
  behavior of a second `MR_WR_REQ` while a request is outstanding — that behavior is
  authoritatively defined by v1.9.11 §A.12-3, and verification should test against that
  source directly rather than against any paraphrase here.
- **W1C/pulse semantics:** dedicated test patterns per §8's four conventions — e.g., for
  W1C registers, verify write-1 clears only the addressed bit and write-0 has no effect;
  for pulse/request registers, verify the bit never reads back as persistently set.
- **Reserved-address behavior:** every OPEN-width register's reserved address should have a
  defined, tested response (§3's `PSLVERR`-or-ignore choice) rather than undefined behavior,
  so that later resolving an OPEN item doesn't change behavior at addresses software may
  have already probed.
- **FAB-specific:** verify the synchronized shadow-copy values inside FAB never glitch
  mid-update relative to the phase packer's per-cycle combinational read (§9) — this is the
  one place a CDC bug could silently corrupt DFI-facing timing rather than just a stale
  status read.

---

## 15. Open questions / future extensions

- **FAB window re-evaluation:** if `upd_phy_ack`/`upd_phymstr_ack` are confirmed
  software-driven, revisit §9/§2 with a narrow FAB-local carve-out for the 2D class only
  (not a full FAB window) — the earlier architecture-options analysis already scoped this
  as a smaller, targeted alternative rather than the all-or-nothing FAB-window question.
- **`gate_pwr`/`gate_mr` host visibility:** currently excluded per v1.9.11 §D.1; whether a
  future revision of v1.9.11 (or a driver requirement) wants read-only host visibility into
  these gates is unaddressed here.
- **Generalization toward per-block windows:** if Scheduler's or another block's
  software-visible register surface grows enough to develop its own session-coupled
  registers (analogous to MR_Write today), the Global/Baseline/ME-local structure
  generalizes to additional local windows using the same session/locality test from §5 —
  not a redesign, an extension of the same method.
- All items in §13 remain open and are prerequisites for finalizing exact byte offsets in
  §6 — this document's address-map *structure* is stable; its *numeric* map is not yet.
- `timing_reg_file`'s exact APB realization (indirect `param_id`/`param_val` pair vs. 23
  flattened per-param addresses, §7.6) is an implementation choice not yet made.
- APB revision (APB3 vs. APB4, `PSLVERR` presence) and exact `PADDR`/`PWDATA` widths (§3)
  are not fixed by this document.
