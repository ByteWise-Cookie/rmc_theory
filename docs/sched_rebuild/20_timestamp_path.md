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

## GC + comparator (DECIDED)

**GC = CK-valued, mc_clk-domain register:** `@ mc_clk: GC <= GC + gear` (1:1→+1, 1:2→+2,
1:4→+4). Free-running timebase (advances every mc_clk whether or not a cmd issues), starts 0
after `init_done`. `gear` is the mc_clk:CK ratio (config reg; sole gear-aware element). GC is
NOT a CK-rate counter (CK is PHY-side) and NOT mc_clk-valued — it *holds* CK, *ticks* at mc_clk.
Deadlines/consts are all CK, so no /gear scaling and no shift in the compare.

**can_x = reset-dominant SR flop (fig_52):** `RESET = issue-decode` (block now, immediate,
reset-dominant so a fresh issue beats a coincident set); `SET = (GC >= next_x)` comparator.
Registered form of the pure comparator: the issue that stamps next_x also clears can_x, the
comparator re-sets it when the deadline passes. SET stays `≥` (or a gear-decrementing
countdown), NEVER `==`.

**Comparator = `≥` via subtract-MSB, NEVER `==`/XOR:**
```
can_x = (GC - next_x)[MSB] == 0        // = GC >= next_x, 13-bit wrap-safe
placement: (GC + phase_off) - next_x   // per phase, CK-granular
```
Two reasons == fails: (1) gear>1 SKIPS the exact value (140→144 skips 142) → == never matches
→ deadlock; (2) can_x is a persistent LEVEL ("legal now and onward"), == is a 1-cycle pulse
(wrong even at 1:1). 13-bit unambiguous within 2^12; max interval tRFC1=708 << 4096, safe.
phase_off (0..gear-1) recovers sub-mc_clk CK resolution at placement (STAGE 6).

**Freq change (DVFS):** timings are fixed in ns but their CK counts shift with tCK, so a real
speed change reloads `timing_reg_file` + reprograms MRs (CL/CWL) + ZQ — done QUIESCED (drain ->
self-refresh -> DFI freq-change handshake `dfi_freq_ratio` -> PHY relock/retrain -> reprogram ->
SRX -> update gear -> resume), by a freq-change FSM (maint sub-engine, stub). No in-flight
deadline survives (self-refresh drained), so no stale-timestamp problem; GC stays CK-valued.

## Parallel writeback -- 3-4 updates in one mc_clk (DECIDED)

**YES, all <=3-4 issued commands' writebacks land in ONE mc_clk, contention-free.** Three
structural facts, no write-port arbitration needed:
1. **Scoreboard = flop array (per-entry WE), not a ported RF** -> any number of distinct entries
   written same cycle; no port to contend.
2. **Different-bank bundle (packer rule)** -> the <=3 demand cmds (1 cas+1 act+1 pre) hit
   DIFFERENT bank entries -> independent WEs, zero BANK collision.
3. **Class-split -> <=1 writer per shared field:** `next_act_bg`<-only ACT, `next_cas_bg`<-only
   CAS, `next_act_dbg`/`faw_ts`<-only ACT, `turnaround`/`last_cas`/`dqFree`<-only CAS. No two
   commands write the same field of the same entry. Cross-rank corners (2 ACT / 2 PRE) hit
   different rank/BG entries -> still parallel.
- **Cost (RAW):** adder replication -- each (cmd x relationship) stamped needs its own
  `GC_ph + const` adder; worst bundle ACT(5)+CAS(4)+PRE(2) ~= 11 adders in parallel, each with
  its own `phase_off`. All combinational -> fits the cycle. SR-flop RESETs are per-flop WE too
  -> parallel, no limit. Optimize later by SHARING adders across scopes; the parallelism is free.
- **Safety invariant:** never 2 writers to one shared field -- guaranteed by class-split (1
  cas/act/pre) + different-bank + dqFree(1 CAS/bundle). If that broke you'd need write-arb; the
  rules make it impossible.

## Sizing (13-bit timestamps, N_RANKS=2)
BANK 64×(state~26 + 3×13=39) ; BGS 16×(2×13=26) ; BGD 2×13 ; RANK 2×~85 (faw fat) ; GLOBAL ~40b.
Timing-const table (tRC/tRCD/… ≈20 consts) shared ONCE, feeds every `*_UPD` adder — NOT per-bank.

## Timing-const reg file (FLAT, per scope) — DECIDED

**Form = flat shared bank, NOT per-command rows.** Store each *distinct* constant once; the
per-command selection is a `case(issued_cmd)` that synth folds to minimal muxes. Per-command
rows were rejected — RD/WR/PRE fill one field but pad to 3 columns → ~50% empty flops (BANK 96b
row-form vs 48b flat). Flat spends a tiny mux instead of padded storage; wins on both storage and
mux (row-form needs a 4:1 per column; flat needs one 2:1 + one 3:1).

**No read address.** Each bank is a flop array with *every output permanently wired out* — the
consts are standing wires, not a ported memory. So any subset (all 3 for ACT) is available in ONE
cycle, and any number of readers (both writeback control units) tap the same wires — pure fan-out,
no port contention. An addressed SRAM/ROM would serialize multi-fetch; flat flops do not. The
`cfg_we` write path (freq-FSM reload) is what keeps them as real flops — never constant-folded.

### BANK_CONST (6 × 8b = 48b)
| idx | const | val (CK) |
|---|---|---|
| 0 | tRC | 117 |
| 1 | tRCD | 40 |
| 2 | tRAS | 77 |
| 3 | tRTP | 18 |
| 4 | tRP | 40 |
| 5 | WR_TAIL = CWL+BL/2+tWR | 118 |

feed: `next_act` = 2:1 {tRC(ACT), tRP(PRE)} · `next_cas` = fixed tRCD(ACT) · `next_pre` = 3:1
{tRAS(ACT), tRTP(RD), WR_TAIL(WR)}.

### BG_CONST (3 × 8b = 24b)
| idx | const | val |
|---|---|---|
| 0 | tRRD_L | 12 |
| 1 | tCCD_L | 12 |
| 2 | tCCD_L_WR | 48 |

feed: `next_act_bg` = fixed tRRD_L(ACT) · `next_cas_bg` = 2:1 {tCCD_L(RD), tCCD_L_WR(WR)}.

### RANK_CONST (7 × 8b = 56b)
| idx | const | val |
|---|---|---|
| 0 | tRRD_S | 8 |
| 1 | tFAW | 32 |
| 2 | tRTW | 12 |
| 3 | WTR_TAIL_L = CWL+BL/2+tWTR_L | 70 |
| 4 | WTR_TAIL_S = CWL+BL/2+tWTR_S | 52 |
| 5 | tPPD | 2 |
| 6 | tRTRS | 2 |

feed: `next_act_dbg` = fixed tRRD_S(ACT) · `faw` = fixed tFAW(ACT) · `next_wr` = fixed tRTW(RD) ·
`next_rd` = 2:1 {WTR_TAIL_L, WTR_TAIL_S} by same/diff-BG (or conservative L, fixed — parked) ·
`next_pre` = fixed tPPD(PRE). tRTRS = cross-rank CAS (DQ handler, parked).

### CH_CONST (1 × 8b = 8b)
| idx | const | val |
|---|---|---|
| 0 | BL_HALF (BL/2) | 8 |

feed: `dqFree` = fixed BL_HALF(RD/WR).

### MAINT_CONST (separate path, wider — up to tRFC1)
| idx | const | val | bits |
|---|---|---|---|
| 0 | tRFCsb | 312 | 10 |
| 1 | tRFC1 | 708 | 10 |
| 2 | tRFM | ~ | 10 |
| 3 | tZQCAL | ~1024 | 12 |
| 4 | tZQLAT | 30 | 8 |
| 5 | tMRD | 16 | 8 |
| 6 | tMOD | 36 | 8 |

**Demand total = 48+24+56+8 = 136b**, stored ONCE, shared across all 64 banks / 16 BGs / 2 ranks.

### Selection = `case`, not hand-drawn muxes
Write one `case(issued_cmd)` per operand; `unique case` lets synth drop unused legs and derive the
minimal mux (fixed / 2:1 / 3:1). The source reads like the per-command spec; the netlist is the
flat bank + minimal muxes. Composites (WR_TAIL, WTR_TAIL) are stored precomputed — the freq-FSM
recomputes them (fn of new CWL/tCK) and rewrites on DVFS, so no runtime add.

### Write interface
`cfg_we` · `cfg_scope[2:0]` (BANK/BG/RANK/CH/MAINT) · `cfg_idx[3:0]` · `cfg_data[11:0]`.
Read: none (named static wires). Reload: freq-FSM walks all entries on DVFS.
