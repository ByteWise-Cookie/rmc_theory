# Maintenance Engine (ME) — peer block, 7 sub-FSMs

**Phase 1, block 06.** A **peer** to the scheduler, not in the packet path. The ME owns
everything the DRAM needs to stay alive and correct — bring-up, refresh, ZQ calibration,
RFM, power management, and mode-register traffic — plus the **DFI output mux** that hands
the port from boot to normal operation.

**Two hard rules (KB §10):**
1. **The ME never issues a CAS.** It writes into the scheduler's FSM tables (sets
   `ref_pending`, `gate_rfc`, timing deadlines) and issues its own non-data commands
   (REF/PRE/MRW/MRR/ZQ/PDE/SRE) — but reads/writes to DRAM data are the scheduler's alone.
2. **`init_done` is a one-way latch.** Init drives DFI at boot; once DONE, the scheduler
   inherits the port forever (block-01 §3D mux).

Grounded in KB §10 + the MR-programming addendum (block-00 I28). Adopts KB naming; ports
are valid-credit / table-writeback (I15).

---

## 0. Where it sits

```
        ┌──────────── Maintenance Engine (peer) ────────────┐
        │ Init · Refresh · ZQcal · RFM · PwrMgmt · MR_Poll  │
        │                 · MR_Write                        │
        └───────┬─────────────────┬───────────────┬─────────┘
   writes tables│        DFI mux   │      reads    │ bank_act_count,
   (ref_pending,│    (init_done)   ▼      counters │ all_idle, raa,
    gate_rfc…)  ▼             ┌────────┐            │ can_xp/xs
        Per-Bank/Rank    ─────│  FAB   │─── DFI ──▶ PHY
        FSM tables (blk02)    └────────┘
```

The ME and the scheduler **share** the per-bank/per-rank FSM tables: scheduler Stage-4 and
the ME both write; the scheduler reads for legality. Priority when both want the bus is
resolved by the scheduler's **Stage-0 maintenance override** (`ref_urgent > ref_due >
rfm_req > zq_due`).

---

## 1. Sub-FSM inventory (7)

| # | Sub-FSM | Concern | Trigger | Issues |
|---|---------|---------|---------|--------|
| 1 | **Init** | bring-up: reset→MRW→ZQcal→training→DONE | `INIT_KICK` | drives DFI directly until `init_done` |
| 2 | **Refresh** | tREFI leaky-bucket, REFab/REFsb, FGR-2x/4x | credits/`gc` | REF (via Stage-0 override) |
| 3 | **ZQcal** | periodic ZQ calibration, per-rank | `gc≥next_zqcs` | ZQCAL start/latch; `gate_zq` |
| 4 | **RFM** | Refresh Management, per-bank RAA | `raa[b]≤RAAIMT` | RFM |
| 5 | **PwrMgmt** | power-down + self-refresh entry/exit | idle / system | PDE/PDX, SRE/SRX |
| 6 | **MR_Poll** | MR4/TUF temperature polling | `gc≥next_poll_gc` | MRR to MR4 (sideband return) |
| 7 | **MR_Write** *(I28)* | runtime mode-register writes (timing changes) | `mr_wr_req` | MRW + verify MRR |

> "one concern per sub-FSM" — they stay functionally distinct (periodic vs on-demand,
> read vs write), never merged.

---

## 2. Refresh FSM (the load-bearing one)

- **Leaky bucket:** `ref_credits += 1` per `T_REFI`, `−= 1` per REF issued. `ref_urgent`
  at credits ≥ 8 → Stage-0 override; `ref_due` at `gc ≥ next_trefi` → normal trigger.
- **REFab:** `gate_rfc[rank]=1`, all banks blocked `T_RFC1`. **REFsb:**
  `gate_rfcpb[rank][bank]=1`, one bank blocked `T_RFCsb`.
- **REFsb targeting:** `argmin(bank_act_count[rank][*])` (idle bank first); watchdog forces
  any bank overdue by `T_REFI×32` (`last_refsb_gc`).
- **Opportunity REFsb (I13):** on a scheduler NOP cycle, idle bank, most-overdue → fire
  REFsb at zero traffic cost.
- **FGR / temperature:** FGR-2x→`T_RFC2` (rate ×2, threshold ÷2); FGR-4x→×4; MR4 TUF=1
  (>85 °C) → `T_REFI_adjusted = T_REFI/2` (fed by MR_Poll).

---

## 3. MR_Write + shared MR Read Arbiter (I28)

Runtime mode-register writes — the hardest correctness path, because a timing-affecting
MRW must never leave `timing_reg_file` out of sync with the DRAM's actual latency.

- **Flow:** `IDLE → REQUEST → WAIT_tMRD (gate_mr[rank]=1) → VERIFY_MRR → WAIT_RDDATA →
  CHECK_MATCH → APPLY_TIMING → DONE`.
- **Shadow → apply:** a timing-affecting MRW stages the new value; `APPLY_TIMING` pulses
  `timing_apply_en` into `timing_reg_file` **only after** the verify read-back matches
  (`CHECK_MATCH`). So the controller's expectation and the DRAM flip atomically.
- **Shared MR Read Arbiter:** MR_Poll and MR_Write both issue MRRs and share the sideband
  return path. A small arbiter grants one at a time; responses are disambiguated by a new
  **`mrr_requester`** tag (rank alone is insufficient once two FSMs can read). No
  preemption of an in-flight read; tie → MR_Write first (`mr_write_req > mrr_due`).
- **Invariant (first-class):** `timing_reg_file` is never out of sync with the DRAM's
  programmed latency. Every timing-affecting MRW goes verify-then-apply.

---

## 4. DFI output mux ownership

The ME owns `init_done` (one-way latch) and the Init FSM's DFI drive. The mux itself lives
in the fabric (block-01 §3D). Boot sequence hands the DFI port to the scheduler exactly
once, at Init DONE.

---

## 5. Interfaces (summary)

**Writes (into scheduler tables):** `set_ref_pending`/`clr_ref_pending`,
`set_gate_rfc`/`clr`, `set_gate_zq`/`clr`, `update_next_trefi/zqcs/xp/xs`,
`raa_dec_en/val`, `timing_apply_en`.
**Reads:** `bank_act_count`, `all_idle`, `raa_out`, `can_xp/can_xs`, `gc`, `sched_ack`.
**Own commands:** `me_cmd_valid/type/rank/bg/bank` → Stage-0 override → emit → FAB.
**MRR sideband in:** `mrr_data_valid/data/rank/requester`.
**Boot:** `INIT_KICK`, `TRAIN_EN` (CSR) → `init_done`.

---

## Open items (ME)

- **OM-1** REFsb vs REFab default policy — CSR `REF_MODE`; interacts with row-lock (ARB).
- **OM-2** self-refresh entry/exit latencies — pull `T_CKSRE/T_XS/T_DLLK` exact from spec.
- **OM-3** MR_Write ↔ scheduler bus contention — MRW needs the CA bus; treat as a Stage-0
  maintenance grant like REF.
- **OM-4** ZQcal interval default (`T_ZQCS_interval`) — 128 ms → cycles at bin.
