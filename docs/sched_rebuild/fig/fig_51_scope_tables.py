from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_51 — split scoreboard by scope: BANK / BGS (same-BG) / BGD (diff-BG) / RANK.
# Each holds next_* deadlines (13b, GC+const) + emits can_x gates. Assumed DDR5
# model (not JEDEC lookup). 13-bit wrap-compare timestamps.

f = Fig(1300, 1000)


def panel(x, y, w, h, title, depth, stored, canx, frm, fill=FILL_LOGIC):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + 14, y + 26, title, size=14, mono=True, bold=True)
    f.text(x + w - 12, y + 24, depth, size=11, mono=False, anchor="end", fill=MUTED)
    yy = y + 48
    f.text(x + 14, yy, "STORED", size=11, mono=False, bold=True, fill=MUTED)
    for ln in stored:
        yy += 16
        f.text(x + 24, yy, ln, size=10, mono=True)
    yy += 18
    f.text(x + 14, yy, "CAN_X (comparator out)", size=11, mono=False, bold=True, fill=MUTED)
    for ln in canx:
        yy += 16
        f.text(x + 24, yy, ln, size=10, mono=True, fill="#1a5aa8")
    yy += 16
    f.text(x + 14, yy, "FROM", size=11, mono=False, bold=True, fill=MUTED)
    f.text(x + 24, yy + 15, frm, size=10, mono=False, fill=MUTED)


f.text(40, 38, "Split scoreboard by scope - fields + can_x per stage", size=15,
       mono=False, bold=True)
f.note(40, 58, "Each scope stores next_* = GC+const (13b) and emits its can_x gate "
               "(GC >= next_*). Arb reads can_x; NEVER rejects. Assumed DDR5-4800B CK.")

# ---- BANK ----
panel(40, 82, 610, 366, "BANK", "x N_RANKS*32 = 64",
      ["state[4] valid open_row[17]", "pre_pending last_op ref_pending",
       "next_act[13]  <- tRC / tRP",
       "next_cas[13]  <- tRCD / tCCD_L(sb)",
       "next_pre[13]  <- tRAS / tRTP / WR:CWL+BL/2+tWR"],
      ["can_act = GC>=next_act & state ok",
       "can_cas = GC>=next_cas & OPEN & row_hit & dqFree",
       "can_pre = GC>=next_pre"],
      "tRC117 tRCD40 tRAS77 tRP40 tRTP18 tWR->118 tCCD_L(sb)",
      fill=FILL_CELL)

# ---- BGS (bank-group SAME) ----
panel(680, 82, 580, 176, "BGS  (bank-group SAME)", "x N_RANKS*8 = 16",
      ["next_act_bg[13] <- tRRD_L",
       "next_cas_bg[13] <- tCCD_L / tCCD_L_WR"],
      ["can_act_bgs = GC>=next_act_bg",
       "can_cas_bgs = GC>=next_cas_bg"],
      "tRRD_L=12  tCCD_L=12  tCCD_L_WR=48",
      fill=FILL_NEW)

# ---- BGD (bank-group DIFF = cross-BG) ----
panel(680, 274, 580, 174, "BGD  (bank-group DIFF / cross-BG)", "per rank x2",
      ["next_act_dbg[13] <- tRRD_S",
       "(CAS diff-BG = tCCD_S folds into dqFree)"],
      ["can_act_bgd = GC>=next_act_dbg",
       "can_cas_bgd = dqFree  (=tCCD_S, shared global)"],
      "tRRD_S=8  tCCD_S=8 (=dqFree)",
      fill=FILL_NEW)

# ---- RANK ----
panel(40, 468, 1000, 300, "RANK", "x N_RANKS = 2",
      ["faw_ts[4][13] = 52   <- tFAW rolling 4-ACT window",
       "next_rd[13] <- WR:CWL+BL/2+tWTR(L70/S52)   (turnaround)",
       "next_wr[13] <- RD:tRTW=12                  (turnaround)",
       "last_cas_ts[13] last_cas_dir last_cas_rank last_cas_bg",
       "raa_count[7] (RFM)   gate_rfc/gate_zq/gate_mr (+release ts)"],
      ["can_act_rank = faw_ok & GC>=next_act_dbg          (tFAW+tRRD_S)",
       "turnaround   = GC>=next_rd|next_wr on dir flip    (tWTR/tRTW)",
       "maint block  = !gate_rfc & !gate_zq & !gate_mr"],
      "tFAW32 tWTR(70/52) tRTW12 tRTRS2 tRFC1=708 tRFCsb=312 tZQ tMRD16 tMOD36",
      fill=FILL_ACTIVE)

# ---- GLOBAL / DQ note ----
f.rect(1060, 468, 200, 300, fill=FILL_LOGIC, width=W_CELL)
f.text(1074, 494, "GLOBAL / DQ", size=13, mono=True, bold=True)
f.text(1160, 492, "x1", size=11, mono=False, anchor="end", fill=MUTED)
for i, ln in enumerate(["dqFree[13]", " = GC+BL/2 (8)", "caFree[13]",
                        "last_cas (bus)", "", "can_cas &=", "  GC>=dqFree",
                        "", "one DQ bus,", "one CA bus"]):
    f.text(1074, 522 + i * 22, ln, size=10, mono=True,
           fill=("#1a5aa8" if "can_cas" in ln or "GC>=dq" in ln else INK))

f.caption(40, 800,
          "Backtracking the timestamp path from the scope tables: BANK (same-bank) -> BGS "
          "(same-BG) -> BGD (cross-BG) -> RANK -> GLOBAL. Each stamps next_* at issue (fig_50) "
          "and emits can_x; the arb ANDs the can_x of the scopes a candidate touches. Depth "
          "collapses 64 -> 16 -> 2 -> 1; RANK is widest per-entry (faw_ts[4]=52b).")

f.save("fig_51_scope_tables.svg")
print("wrote fig_51_scope_tables.svg")
