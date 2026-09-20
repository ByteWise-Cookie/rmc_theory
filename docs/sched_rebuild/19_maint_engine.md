# STAGE 19 — Maintenance Engine (ME) FSMs

Lifted from the v1.9.8 architecture (KB v3 / Full_Knowledge / architecture_reference) and
remapped to sched_rebuild naming. **Nothing here is new design** — the old build already
solved refresh / RFM / ZQ / MRR-temp / init; we adopt its FSMs.

## Remap (old name → sched_rebuild name)  — CORRECTED
- **There is NO ME-internal priority-select and NO "stage-0 override" block.** Each FSM just
  **raises a flag**; the **SCHEDULER** (arb + packer) ranks the flags WITH demand and places
  the winner. me_cmd flag wins packer priority (soft) — it still issues through the scheduler's
  own encoder.
- **INIT is the ONLY hard override** = the **DFI mux** (`sel=init_done`, power-on). It bypasses
  the scheduler because the scheduler isn't valid until init_done. Nothing else is DFI-direct.
- **DFI has exactly two drivers:** INIT FSM, and the scheduler encoder. No third wire.
- **Read Data Path** → **RD_CAP** (read-data capture, stage 5/7); MRR result returns on its
  **sideband** (not the resp FIFO).
- **ME writes the shared scoreboard directly** (`gate_rfc/gate_zq`, `RAA`/`raa_inc`, `tREFI`
  reload) and asserts `ref_pending`/p_bit on banks; never issues a CAS.

## Priority (in the SCHEDULER, not the ME)
The flags carry urgency; the scheduler ranks: `ref_urgent > ref_due > rfm_req > zq_due`
(+ demand cas/act/pre). **RECONCILE:** stage-9 wrote `ref_urgent > rfm > ref_due > zq`; the
v1.9.8 source has `ref_urgent > ref_due > rfm > zq`. Decide via a two-level RFM:
`rfm_urgent (RAA≥RAAMMT)` near `ref_urgent`, `rfm_opp (RAA≥RAAIMT)` below `ref_due`. TODO lock.

## The six sub-FSMs

| FSM | states | trigger | issues | gate | scope |
|---|---|---|---|---|---|
| **Init** | 16 | power-on reset | reset seq · ODT · DLL/MPC · ZQCL · MRW-train · training → `init_done` | owns DFI mux till init_done | device/PHY |
| **Refresh** | 6 | leaky bucket (+1/tREFI, −1/ref); `ref_urgent`@8 credits, `ref_due` normal | REFab / REFsb | `gate_rfc` (tRFC1 / tRFCsb) | rank / bank |
| **RFM** | 6 | per-bank RAA ≥ RAAIMT | RFMsb / RFMab | like refresh | bank / rank |
| **ZQcal** | 7 (per rank) | `next_zqcs` (tZQCS) + init | MPC `ZQCAL START` / `LATCH` | `gate_zq` (rank, tZQCAL/tZQLAT) | rank |
| **MR_Poll** | 6 | `gc ≥ next_poll_gc` (32×tREFI) | MRR(MR4) via stage-0 bypass | — (sideband return) | rank (temp) |
| **Power Mgmt** | 10 | PD/SR request + all-idle | PDE/PDX · SRE/SRX | `bank_act_count==0`, no maint pending | rank |

(MRW is **not** a standalone runtime FSM — it lives inside Init training + the odd runtime
config write; issue MRW then wait `tMOD` settle.)

## MR_Poll FSM (6 states, explicit)
```
IDLE → WAIT_INTERVAL → REQUEST_MRR → WAIT_RDDATA → PARSE_TUF → UPDATE_TREFI → IDLE
  WAIT_INTERVAL   count to next_poll_gc (MRR_POLL_INTERVAL CSR = 32×tREFI)
  REQUEST_MRR     me_cmd_valid, me_cmd_type=MRR, me_cmd_mr=4, me_cmd_rank ; wait sched_ack
  WAIT_RDDATA     wait mrr_data_valid (RD_CAP sideband)
  PARSE_TUF       extract TUF from MR4 response
  UPDATE_TREFI    TUF=1 (>85°C) → tREFI_adjusted = tREFI/2 → Refresh FSM next_trefi
```

## MRR command + response path
```
MR_Poll → stage-0 bypass:  me_cmd_type=MRR, me_cmd_mr=4, me_cmd_rank
       → phaser/encoder → DFI (MRR per JEDEC DDR5)
DRAM response → RD_CAP → SIDEBAND {mrr_data_valid, mrr_data[8b], mrr_rank} → MR_Poll
       (NOT through the resp FIFO — control-plane, not host data)
```
- **MRR (read)** needs the sideband tap; **MRW (write)** = fire-and-forget, no response, just tMOD.

## DFI Output Mux (inside ME)
`init_done==0` → Init FSM drives all DFI; `init_done==1` → scheduler phaser drives permanently
(one-way latch). MRR is a stage-0 bypass straight to the encoder — no third mux input.

## Key ports (per source)
- Common: `me_cmd_valid`, `me_cmd_type[2:0]`, `me_cmd_rank`, `me_cmd_bg/bank`, `me_cmd_mr`, `sched_ack`.
- Refresh/ZQ/RFM gates: `set_gate_*` / `clr_gate_*`, `update_next_{trefi,zqcs}`.
- RFM: `raa_out[rank][bank][6:0]`, `RAAIMT[7:0]` CSR, `raa_inc_en` (from encoder commit), `raa_dec_en/val`.
- MR_Poll: `mrr_data_valid`, `mrr_data[8b]`, `mrr_rank` (RD_CAP sideband); `last_TUF`, `next_poll_gc`, `mrr_data` per-rank fields.
- CSRs: `MRR_POLL_INTERVAL=32×tREFI`, `next_zqcs`, `RAAIMT`, `T_ZQCAL`, `T_ZQLAT`.
