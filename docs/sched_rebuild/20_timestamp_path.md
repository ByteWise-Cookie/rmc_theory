# STAGE 22 — Timestamp path: scope tables + writeback map

Assumed DDR5-4800B model (not a JEDEC lookup). GC counts CK. Timestamps are 13-bit
wrap-compare (`next_* = GC + const`); a later cmd is legal when `GC >= next_*`. The arb
reads the `can_*` gates and NEVER rejects — all legality is folded into `can_*`.
Figures: writeback = `fig_50`, scope tables = `fig_51`.

## Scope tables (fields + can_x)

### BANK   (per bank, x N_RANKS*32 = 64)
| field | bits | from |
|---|---|---|
| state | 4 | FSM (IDLE/ACTING/OPEN/PREING/REFING/…) |
| valid | 1 | |
| open_row | ~17 | active row shadow |
| pre_pending / last_op / ref_pending | 3 | intent/dir/refresh |
| next_act | 13 | tRC (ACT→ACT) / tRP (PRE→ACT) |
| next_cas | 13 | tRCD (ACT→CAS) / tCCD_L same-bank |
| next_pre | 13 | tRAS (ACT→PRE) / tRTP (RD→PRE) / CWL+BL/2+tWR (WR→PRE) |

**can_x:** `can_act = GC≥next_act & state ok` · `can_cas = GC≥next_cas & state==OPEN & row_hit & dqFree` · `can_pre = GC≥next_pre`

### BGS — bank-group SAME   (per BG, x N_RANKS*8 = 16)
| field | bits | from |
|---|---|---|
| next_act_bg | 13 | tRRD_L=12 (ACT→ACT same BG) |
| next_cas_bg | 13 | tCCD_L=12 (RD) / tCCD_L_WR=48 (WR), same BG |

**can_x:** `can_act_bgs = GC≥next_act_bg` · `can_cas_bgs = GC≥next_cas_bg`

### BGD — bank-group DIFF / cross-BG   (per rank, x2)
| field | bits | from |
|---|---|---|
| next_act_dbg | 13 | tRRD_S=8 (ACT→ACT diff BG) |
| (CAS diff-BG) | — | tCCD_S=8 folds into dqFree (global) |

**can_x:** `can_act_bgd = GC≥next_act_dbg` · `can_cas_bgd = dqFree`

### RANK   (per rank, x2)   ← widest per-entry
| field | bits | from |
|---|---|---|
| faw_ts[4] | 4×13=52 | tFAW=32 rolling 4-ACT window |
| next_rd | 13 | WR→RD turnaround: CWL+BL/2+tWTR (L=70 same-BG / S=52 diff-BG) |
| next_wr | 13 | RD→WR turnaround: tRTW=12 |
| last_cas_ts / dir / rank / bg | 13+~4 | streak + cross-rank |
| raa_count | ~7 | RFM (per bank, lives rank-adjacent) |
| gate_rfc / gate_zq / gate_mr | 3 (+release ts) | tRFC1=708 / tRFCsb=312 / tZQCAL / tMRD=16 |

**can_x:** `can_act_rank = faw_ok & GC≥next_act_dbg` (tFAW+tRRD_S) · `turnaround = GC≥next_rd|next_wr` on dir flip · `maint = !gate_rfc & !gate_zq & !gate_mr`

### GLOBAL / DQ   (x1)
| field | bits | from |
|---|---|---|
| dqFree | 13 | GC + BL/2 = 8 (one DQ bus) |
| caFree | 13 | CA bus |
| last_cas (bus) | — | shared |

**can_x:** `can_cas &= GC≥dqFree`. One DQ bus, one CA bus.

**Arb rule:** a candidate ANDs the `can_*` of every scope it touches (bank ∧ BGS ∧ BGD ∧ rank ∧ global). Depth collapses 64 → 16 → 2 → 1; RANK is the widest per-entry (faw_ts[4]=52b).

## Writeback map (on issue, which next_* is stamped, where) — fig_50

| issued | BANK | BGS (same-BG) | BGD/RANK (cross) | GLOBAL/DQ |
|---|---|---|---|---|
| **ACT** | next_act(tRC117), next_cas(tRCD40), next_pre(tRAS77) | next_act_bg(tRRD_L12) | next_act_dbg(tRRD_S8), faw_ts push(tFAW32) | — |
| **RD**  | next_pre(tRTP18) | next_cas_bg(tCCD_L12) | next_wr(tRTW12), last_cas_dir=R | dqFree(+8), last_cas{}, tRTRS(x-rank) |
| **WR**  | next_pre(CWL+BL/2+tWR=118) | next_cas_bg(tCCD_L_WR48) | next_rd(CWL+BL/2+tWTR 70/52), last_cas_dir=W | dqFree(+8), last_cas{} |
| **PRE** | next_act(tRP40); PREab=all banks, PREsb=8 | — | next_pre(tPPD2, diff bank) | — |
| **REFsb** | gate_rfc/REFING(+tRFCsb312, 8 targets) | targets span BGs | debt-- | — |
| **REFab** | — | — | gate_rfc all banks(+tRFC1=708), debt-- | — |
| **RFM** | gate_rfm(+tRFM, targets), RAA-=RAAIMT | RFMsb spans BGs | RFMab=whole rank | — |
| **ZQ** | — | — | gate_zq(+tZQCAL, then LATCH +tZQLAT=30) | DQ driver busy (cal) |
| **MRW** | — | — | gate_mr(+tMRD16), setting live +tMOD36 (device) | blocks issue in tMRD |
| **MRR** | — | — | dir=R (DQ read) | dqFree(+8), sideband return (no gate) |

**Notes:** same value diff scope — CAS→CAS diff-BG = tCCD_S=8 = dqFree (global); same-BG = tCCD_L/L_WR (BGS). Cross-bank constraints are written into the SHARED scope reg at issue. Turnaround REPLACES the dqFree gap at a flip (not added). MRR/ZQ touch DQ like a CAS; MRW/REF/RFM are gate-only.

## Sizing (13-bit timestamps, N_RANKS=2)
BANK 64×(state~26 + 3×13=39) ; BGS 16×(2×13=26) ; BGD 2×13 ; RANK 2×~85 (faw fat) ; GLOBAL ~40b.
Timing-const table (tRC/tRCD/… ≈20 consts) shared ONCE, feeds every `*_UPD` adder — NOT per-bank.
