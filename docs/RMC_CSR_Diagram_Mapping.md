# RMC — CSR / Configuration Architecture: Diagram-Ready Mapping

## Legend

Same convention as `RMC_APB_Interface.md`:

- **[DEFINED — \<source\>]** — stated by an existing document.
- **[INFERENCE]** — a reasonable reading of a source's structure, not a verbatim statement.
- **[OPEN]** — destination/consumer genuinely unresolved by any source; not guessed here.

**Destination blocks** are named at the same architectural level as
`sched_rebuild/11_mc_core_architecture.md` §0's block diagram — the level the CIF diagram
is being drawn at: `IAF, ADEC/AMU, HZU, BQ, ARB, EMIT, RSP, SCB (per-bank/per-rank/global
timing tables + timing_reg_file), GC, BAC, ME (7 sub-FSMs), FAB, PHY`. Where a CSR's actual
consumer is an ME sub-FSM, the destination is written `ME → <sub-FSM>` — on the diagram this
is still one arrow into the ME box; the sub-FSM name is the arrowhead label, not a separate
box, unless the CIF diagram itself is expanding blocks to that depth.

Row format matches the requested example:
`Source/Owner → Destination → connection type → direction → interface/data concept → "Draw.io label"`

---

## 1. Global (3 registers)

| Row |
|---|
| `INIT_KICK` (Global CSR) → **ME → Init FSM** → request (pulse) → one-way → bring-up trigger → `"Init kick"` |
| `TRAIN_EN` (Global CSR) → **ME → Init FSM** → config → one-way → training enable → `"Train enable"` |
| `SOFT_RESET` (Global CSR) → **GC (Global Cycle Counter)** → control (reset) → one-way → sync reset → `"Soft reset"` **[DEFINED — IO Map §18: `rst_n sync reset on SOFT_RESET only`]** |
| `SOFT_RESET` (Global CSR) → **[OPEN — scope beyond GC undefined]** → control (reset) → — → — | 

**Note:** `SOFT_RESET`'s effect on GC is the only confirmed edge. No source document states
whether it also resets Scheduler/ME/FAB FSM state — **[OPEN, APB doc §12]**. Don't draw a
second `SOFT_RESET` arrow into ME/Scheduler/FAB without marking it explicitly speculative.

---

## 2. Scheduler (8 registers) — split confirmed vs. uncertain

**Confirmed current consumer:**

| Row |
|---|
| `RD_STARVATION_THR` → **ARB** → config → one-way → starvation backstop threshold → `"Starvation thresholds"` **[DEFINED — `08_arb_weight_arbiter.md` open item OA-1: "AGE_MAX vs the hard starvation backstops (RD_STARVATION_THR etc.)"]** |
| `WR_STARVATION_THR` → **ARB** → config → one-way → starvation backstop threshold → `"Starvation thresholds"` (same edge as above, one label) |

**Uncertain / likely superseded — flagged, not asserted:**

| Row | Why uncertain |
|---|---|
| `WR_HIGH_WM`, `WR_LOW_WM` → **BQ** (watermark/admission backpressure) → config → one-way → `"WR watermark config"` | `07_bq_bank_queues.md` describes BQ's "relocated watermark logic" feeding `queue_full` backpressure — plausible current home. But `watermark_mgr_scope.md` (pre-rebuild) ties these specifically to a Stage-3 **mode-flip** decision that `08_arb_weight_arbiter.md` §4 says is now driven by `gateLoss`/`stall` thresholds instead ("Adaptive R/W batching **supersedes** fixed bank partition"). Whether `WR_HIGH_WM`/`WR_LOW_WM` still gate anything live, or are vestigial, is **[OPEN]**. |
| `WINDOW_SIZE` → **[OPEN]** | Sole known consumer is IO Map §34 "Bank Partition Controller," which the fixed-partition scheme `08_arb_weight_arbiter.md` §4 explicitly says is **superseded** by adaptive batching. No current block claims this register. **Do not draw an edge for this one** without confirming a live consumer. |
| `AGE_THR1`, `AGE_THR2` → **[OPEN, possibly ARB]** | APB doc's owner column says "Stage 2/3" (pre-rebuild terminology). Current ARB uses `AGE_MAX` (a single swept constant, OQ-20) for the same role — `AGE_THR1`/`AGE_THR2` may be the legacy two-tier predecessor of `AGE_MAX`, not a still-live pair. Flag as possible duplication, same pattern as the CL/CWL/FAB overlap in §13 item 9 of the APB doc. |
| `PAGE_POLICY` → **[OPEN]** | Not referenced by name in any `sched_rebuild/*` block doc. No current consumer identified — genuinely open, not just uncertain. |

---

## 3. ME policy (11 registers) — all confirmed, one row per sub-FSM

| Row |
|---|
| `REF_MODE` → **ME → Refresh FSM** → config → one-way → REFab/REFsb mode select → `"Refresh mode"` |
| `MRR_POLL_INTERVAL` → **ME → MR_Poll FSM** → config → one-way → MR4/TUF poll period → `"Poll interval"` |
| `pd_en` → **ME → PwrMgmt FSM** → config → one-way → power-down enable → `"Power-down enable"` |
| `PD_IDLE_THRESHOLD` → **ME → PwrMgmt FSM** → config → one-way → idle-to-PD threshold → `"PD idle threshold"` |
| `RAAIMT` → **ME → RFM FSM** → config → one-way → RAA interrupt threshold → `"RFM thresholds"` |
| `RAAMMT` → **ME → RFM FSM** → config → one-way → RAA max threshold → `"RFM thresholds"` (same edge/label as RAAIMT) |
| `RAADec` → **ME → RFM FSM** → config → one-way → RAA decrement value → `"RFM thresholds"` (same edge/label) |
| `tZQCS_interval` → **ME → ZQcal FSM** → config → one-way → ZQ calibration period → `"ZQcal interval"` |
| `ZQCAL_TRIG` → **ME → ZQcal FSM** → request (pulse, semantics OPEN) → one-way → software-triggered ZQ start → `"ZQcal trigger"` (dashed/uncertain — width & exact session shape are OPEN per APB doc §13 item 8) |
| `T_CKSRE` → **ME → PwrMgmt FSM** → config → one-way → self-refresh entry clock-stable wait → `"SR entry/exit timing"` **[DEFINED — MR/PM v1.9.11 `WAIT_tCKSRE`]** |
| `T_CKSRX` → **ME → PwrMgmt FSM** → config → one-way → self-refresh exit clock-stable wait → `"SR entry/exit timing"` (same edge/label) **[DEFINED — MR/PM v1.9.11 `WAIT_tCKSRX`]** |

All ME-policy edges are one-way, config-type, continuously-sampled (no session/handshake) —
consistent with the APB doc's own classification of these as autonomous-FSM policy inputs,
not request/response registers.

---

## 4. MR_Write session (9 registers)

Single logical edge, but it's a genuine request/response **session**, not plain config — draw
it distinctly from the ME-policy edges above (e.g. a heavier/bidirectional arrow):

| Row |
|---|
| `MR_WR_ADDR`, `MR_WR_DATA`, `MR_WR_RANK`, `MR_WR_REQUIRE_IDLE`, `MR_WR_VERIFY` → **ME → MR_Write FSM** → request fields (config-shaped, staged before the pulse) → host→FSM only → MRW target/payload/mode → `"MR_WR request fields"` |
| `MR_WR_REQ` → **ME → MR_Write FSM** → request (pulse) → one-way → session kickoff → `"MR_WR_REQ"` |
| `MR_WR_BUSY`, `MR_WR_DONE`, `MR_WR_ERROR` → **ME → MR_Write FSM** → status → FSM→host only → session outcome → `"MR_WR status"` |

Net result on the diagram: **one bidirectional edge** between "MR_Write CSR (ME-local
window)" and `ME → MR_Write FSM`, composed of a host→FSM request half and an FSM→host status
half — this is the architecture this group's registers actually implement (v1.9.11 §A.3,
`IDLE → WAIT_REQ → GATE_CHECK → ISSUE_MRW → WAIT_tMRD → [VERIFY_MRR...] → DONE`). This is
almost certainly the shape you'll want to expand into the separate MR-programming-flow
diagram (Task B) rather than collapse here.

---

## 5. ADEC/AMU (9 fields, indexed aperture)

| Row |
|---|
| `amu_wr_en`, `amu_field_sel`, `amu_src_msb_a`, `amu_src_lsb_a`, `amu_src_msb_b`, `amu_src_lsb_b`, `amu_split_en`, `amu_hash_en`, `amu_xor_shift` → **ADEC/AMU** → config → one-way → per-field address-map descriptor (indexed by `amu_field_sel` over 6 fields: ch/rank/bg/bank/row/col) → `"AMU field descriptor (indexed)"` |

One edge, one label — this is a single indexed-write aperture (`amu_field_sel` selects which
of the 6 address-map fields the other 8 signals configure), not 9 independent registers, so
it shouldn't render as 9 separate arrows. **[DEFINED — `04_adec_address_map.md` §5]**.
Setup-time only, locked before `init_done` — worth a note/annotation on the edge rather than
a separate "locked" box.

---

## 6. FAB (register classes 2A–2E)

All terminate at the single **FAB** block. Draw as up to 5 edges (not 1) — the connection
*type* genuinely differs per class, which is useful information for the diagram:

| Row |
|---|
| 2A Static config (14 regs: `cfg_*`) → **FAB** → config → one-way (Baseline→FAB, 2-flop sync) → static PHY/DRAM config, written once at init → `"FAB static config"` |
| 2B Timing config (11 regs: `t_phy_*`, `t_ctrl_delay`, `t_dram_clk_enable`, `t_wrdata_delay`, wrlvl/rdlvl classes) → **FAB** → config → one-way (same sync) → PHY-negotiated latencies → `"FAB timing config"` — widths entirely OPEN (`OF-1`/`OF-4`), flag on the edge |
| 2C Live status (11 regs: `sts_*`) → **FAB** → status → one-way (FAB→Baseline, re-synced) → buffer occupancy / link / training state → `"FAB status"` |
| 2D Update/handshake (12 regs: `upd_ctrl_*`, `upd_phy_*`, `upd_phymstr_*`, `upd_freq_*`) → **FAB** → request/response → bidirectional → DFI update handshake (controller-init and PHY-init sub-flows share the edge) → `"FAB update handshake"` — **[OPEN]** `upd_phy_ack`/`upd_phymstr_ack` ownership (software-driven vs. autonomous) is unresolved (APB doc §13 item 11); don't commit the arrowhead direction for those two specifically |
| 2E Error/IRQ (11 regs: `err_*`) → **FAB** → status + W1C → bidirectional (status read/mask write from host, sticky-flag capture from FAB) → `"FAB error/IRQ"` |

Note: counting 14+11+11+12+11 = 59 vs. the stated 58 — the source itself has a known gap
(`sts_ca_quiesced` referenced in prose but missing from FAB's own §2C table, APB doc §13 item
10). Not resolved here; doesn't change which block owns the edges.

---

## 7. Timing/PHY (25 registers)

Two genuinely different destinations hide under this one label — keep them as separate
edges:

| Row |
|---|
| 23 `timing_reg_file` params (`T_RCD` … `T_RTW`) → **SCB → timing_reg_file** → config → one-way (CSR write port only; read side is combinational to all consumers) → nCK timing constants, indexed by `param_id` → `"Timing param write (indexed)"` **[DEFINED — MR/PM v1.9.11 §D.3, IO Map §17]** |
| `T_CKSRE`, `T_CKSRX` (2 regs) → **ME → PwrMgmt FSM** directly → config → one-way → self-refresh entry/exit wait → same edge as in §3 above — **these are not `timing_reg_file` members** despite being timing constants (v1.9.11 explicitly excludes them from the 23-param enum; representation conflict 5b legacy vs. 14b proposed is unresolved, §E-3) |

**If your "Timing/PHY = 25" bucket is meant as 23 + these 2**, both rows above cover it and
there is no separate open item. **If it's meant to include the legacy 5-register class
below instead**, that's a different (and unresolved) bucket — see next section.

---

## 8. FIFO_DEPTH — unresolved (as given)

| Row |
|---|
| `FIFO_DEPTH` → **IAF / RSP** (both async FIFOs consume an initial credit count) → config (compile-time, not clearly a runtime CSR) → one-way → `N_REQ_CREDITS` init value → `"FIFO depth (compile-time?)"` |

**Flag for the diagram itself:** `RMC_IO_Map.md` §0 treats this as a compile-time RTL
parameter, not an APB-writable register at all. If it isn't APB-exposed, it shouldn't appear
as a CSR-window edge on this diagram — it would instead be a build-time parameter feeding
IAF/RSP directly, outside the register-interface picture entirely. Recommend drawing it
dashed/annotated "compile-time?" rather than as a normal CSR edge, or omitting it and noting
the open question in the diagram's margin.

---

## 9. Registers that don't fit any of the 8 named groups — flag before finalizing

Legacy timing/PHY config (`RMC_APB_Interface.md` §7.4, 5 registers) doesn't cleanly belong to
either "ME policy" (11) or "Timing/PHY" (25) as counted, and isn't accounted for elsewhere in
your grouping. Surfacing it now so it isn't silently dropped from the diagram:

| Row |
|---|
| `CL` → **[OPEN — likely duplicate of FAB 2B, or Read-Data-Path-equivalent not present as a distinct box in the current architecture diagram]** |
| `CWL` → **[OPEN — likely duplicate of FAB 2B `t_phy_wrlat`-adjacent, or Write-Data-Path-equivalent]** |
| `PHY_WRLAT` → **[OPEN — possible duplicate of FAB `t_phy_wrlat`]** |
| `PHY_RDLAT` → **[OPEN — possible duplicate of FAB `t_rddata_en`]** |
| `FREQ_RATIO` → **[OPEN — possible duplicate of FAB `cfg_freq_ratio` (2A); also read by ME's DFI mux as `init_dfi_freq_ratio`]** |

`RMC_APB_Interface.md` §13 item 9 already flags this exact duplication and leaves it
unreconciled. **Do not invent which one is authoritative** — either omit this class from the
diagram with a note, or draw it as a dashed/questioned edge into FAB pending reconciliation.
This is the clearest "genuinely unclear" case in the whole mapping: two different-vintage
documents each claim a live register for the same PHY timing concept, and no source resolves
which (if either) is the one that survives to RTL.

---

## Summary — what's solid vs. what's open

**Solid (draw with confidence):**
- Global → ME/Init FSM (`INIT_KICK`, `TRAIN_EN`) and → GC (`SOFT_RESET`'s GC effect)
- ME policy (all 11) → their respective ME sub-FSMs
- MR_Write session (all 9) → ME/MR_Write FSM, as one bidirectional request/status edge
- ADEC/AMU (all 9) → ADEC/AMU, one indexed-config edge
- FAB (all 5 classes) → FAB, as up to 5 typed edges
- Scheduler: `RD_STARVATION_THR`/`WR_STARVATION_THR` → ARB
- Timing/PHY: 23 `timing_reg_file` params → SCB/TRF

**Genuinely open (don't force an edge):**
- `SOFT_RESET`'s scope beyond GC
- `WINDOW_SIZE` (likely-stale Bank Partition Controller consumer)
- `AGE_THR1`/`AGE_THR2` (possibly superseded by ARB's `AGE_MAX`)
- `PAGE_POLICY` (no named consumer anywhere in `sched_rebuild/*`)
- `WR_HIGH_WM`/`WR_LOW_WM` (plausible BQ consumer, but original mode-flip use may be superseded)
- `ZQCAL_TRIG` exact session shape (destination FSM is certain; the edge's shape isn't)
- FAB 2D's `upd_phy_ack`/`upd_phymstr_ack` direction/ownership
- `FIFO_DEPTH` (may not be a CSR edge at all — compile-time parameter)
- The 5-register legacy timing/PHY class vs. FAB 2A/2B duplication
