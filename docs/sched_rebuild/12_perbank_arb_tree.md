# Per-bank cell + arb tree (rebuild walk)

**Phase-2 rebuild.** The forward command path from `BANK_DEC` to `RANK_ARB`, as settled in the
interactive walk. Supersedes the old per-bank-queue + single-weight-arbiter framing (blocks 07/08)
for the rebuilt core. Companion figures: `fig/fig_12_perbank_block` (one cell) and
`fig/fig_mcc_block` (whole core).

---

## 1. Per-bank cell (L0)

One cell per `{rank,bank}` (N_RANKS×32 = 64 @ N_RANKS=2). Physically a **flop array,
parallel-read** — a single-entry CAM per bank (= 1 register + 1 comparator), not a 1-read-port RF
(a single read port can't serve 64 parallel `is_hit` compares each cycle).

- `BANK_STATUS_REG` — the state store. Holds `state[4] · open_row · pre_pending · valid ·
  ref_pending`. Emits, combinationally from its own fields:
  - `row_valid = (state==OPEN) & !pre_pending`  (the intent/commit fence)
  - `pre_pending` (stored bit; only external writer = `CMD_ARB` on a PRE-propose)
  `ROW_VLD` / `PRE_PEND` are **outputs of this reg, not separate blocks.** Feeds `PRE_BANK_ELIG`.
- `ACT_ROW_CAM` + `row_comparator` — `pkt.row vs open_row → is_hit, need_pre/act/cas`.
  - hit  → `cas_path` (need_cas)
  - miss → `act_path` (need_pre → need_act → need_cas)   [open-page]
- `PRE_BANK_ELIG` (elig_gen) — `need_* & can_* → bank_go, bank_cmd, is_hit`.
  The `can_*` half is the timing-legality gate from the scoreboard (`BANK_TREG → can_bank`);
  drawn in the full-arch diagram, deferred here.

State advances only on the grant (`grant_oh`, **pop on CAS**); `REF_pending` is injected by the
maintenance engine.

---

## 2. Arb tree — CMD_ARB → BGB_ARB → BG_ARB → RANK_ARB

Each level = per-candidate **weights** + a `W_MAX` (arg-max) selector. The tree is
**selection-only and cannot reject** — every candidate reaching `CMD_ARB` is already DRAM-legal
because legality is folded into `can_*` at `PRE_BANK_ELIG`. Weights only rank / enforce fairness.

| block | picks | weights | count / lane |
|---|---|---|---|
| `CMD_ARB`  | which COMMAND for this bank | `CAS_W` = K·row_hit_bonus · `ACT_W` = age(need_act) · `PRE_W` = close-row urgency | ×32 |
| `BGB_ARB`  | which BANK in the BG (4→1)  | `B0..B3_W` = hit-bias + age | ×8 |
| `BG_ARB`   | which BG in the rank (8→1)  | `BG0..BG7_W` = **diff-from-`last_cas_bg` bonus** + oldest-BG fairness | ×1 |
| `RANK_ARB` | which RANK (across lanes)   | tRTRS-weighted (cross-rank cheap, dodges tWTR) | ×1 (shared) |

- `CMD_ARB` = stage-3 `K·hit − age(need_act)`, split into per-command weights. A PRE-propose from
  its `W_MAX` writes `pre_pending` back into `BANK_STATUS_REG`, dropping `row_valid` early
  (intent/commit split — no new CAS admits into a row about to close).
- **`BG_ARB` owns the diff-BG preference.** Its weight must prefer a BG ≠ `last_cas_bg` so
  back-to-back CAS land at `tCCD_S = 8 CK` (DQ packed) instead of `tCCD_L = 12 CK` (bubble). Keep
  that preference only at this level.
- Labels: BGs are `BG0..BG7` (8), banks `B0..B3` (4).

---

## 3. Forward-path spine

```
{R_RD_BP_FIFO, R_WR_BP_FIFO} + TURN_CTRL
   → WLR_ABR                       (per-rank batch_dir; R/W turnaround-hide)
   → LOOKAHEAD (H3..H0 + HLD_PATH + P_ECOD)   (4-entry bank-stall bypass)
   → BANK_DEC + BANK_RDY           (1-of-32 to {rank,bank})
   → [per-bank cell: BANK_STATUS_REG, ACT_ROW_CAM, PRE_BANK_ELIG]   (§1)
   → CMD_ARB → BGB_ARB → BG_ARB → RANK_ARB   (§2)
   → packer → DFI
```

## 4. Deferred to the full-arch diagram
- `can_*` / scoreboard feed into `PRE_BANK_ELIG` (the timing-legality half).
- `grant_oh` / pop-on-CAS feedback; `pre_pending` writeback edge.
