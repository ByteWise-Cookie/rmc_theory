from rtlfig import Fig, MUTED, FILL_LOGIC, FILL_NEW, FILL_ACTIVE

# fig_07 — L0 with all ranks in flight.
# Invariant: L0 is per cell [rank][bank] - all N_RANKS x N_BANKS live, each emits
# ITS ONE state-picked cmd. Rank is picked ONLY at L3; L1/L2 are per-rank subtrees.

SB = "#7a5cb8"
f = Fig(1300, 880)


def cell(x, y, name, s, emit, hl=False):
    f.rect(x, y, 190, 76, fill=(FILL_NEW if hl else FILL_LOGIC), width=1.4)
    f.text(x + 95, y + 22, name, size=12, anchor="middle", bold=True)
    f.text(x + 95, y + 41, s, size=10, mono=False, anchor="middle", fill=MUTED)
    f.text(x + 95, y + 60, emit, size=11, anchor="middle")
    return x + 95


# ---------------- decoder ----------------
f.text(430, 56, "from head_mux (lookahead)", size=12, mono=False,
       anchor="middle")
f.line(430, 64, 430, 92, arrow=True)
f.logic(300, 92, 470, 58, "per_bank_decoder",
        "1 request -> cell[{rank,bank}]   (64-way one-hot)")

# routes ONE request this cycle (example: to cell[{1,5}]); rest already in flight
f.path("M540 150 L825 150 L825 204", arrow=True, stroke=SB)
f.text(825, 174, "decode this cycle", size=10, mono=False, anchor="middle",
       fill=SB)

# ---------------- cell bands, per rank ----------------
f.note(70, 196, "rank 0   -   32 cells  cell[{0, bank}]")
c05 = cell(70, 206, "cell[{0,5}]", "OPEN -> MISS", "need_pre -> PRE", hl=True)
c06 = cell(290, 206, "cell[{0,6}]", "OPEN, row hit", "need_cas -> RD")
f.text(560, 246, "... x30 cells", size=11, mono=False, fill=MUTED)

f.note(730, 196, "rank 1   -   32 cells  cell[{1, bank}]")
c15 = cell(730, 206, "cell[{1,5}]", "OPEN -> MISS", "need_pre -> PRE", hl=True)
c16 = cell(950, 206, "cell[{1,6}]", "IDLE", "need_act -> ACT")
f.text(1195, 244, "... x30", size=11, mono=False, fill=MUTED)

f.note(70, 300, "all 64 cells LIVE every cycle - each emits its ONE state-picked cmd (L0)")

# bank_rdy + can_* from scoreboard into the cells (enters below the cell row)
f.line(1280, 336, 1150, 336, arrow=True, stroke=SB)
f.text(1215, 326, "bank_rdy[64]", size=10, mono=False, anchor="middle", fill=SB)
f.text(1215, 352, "+ can_* (fig_04)", size=10, mono=False, anchor="middle",
       fill=SB)

# ---------------- L1 bg_arb, per rank ----------------
f.mux(160, 360, 260, 50, "bg_arb[r0]")
f.mux(820, 360, 260, 50, "bg_arb[r1]")
for cx in (c05, c06):
    f.line(cx, 282, cx if 160 < cx < 420 else 290, 360, arrow=True)
for cx in (c15, c16):
    f.line(cx, 282, cx if 820 < cx < 1080 else 950, 360, arrow=True)
f.note(160, 432, "L1  -  4 banks within a BG, per rank  (x8 BG)")

# ---------------- L2 rank_arb, per rank ----------------
f.line(290, 410, 290, 470, arrow=True)
f.mux(190, 470, 200, 50, "rank_arb[r0]")
f.line(950, 410, 950, 470, arrow=True)
f.mux(850, 470, 200, 50, "rank_arb[r1]")
f.note(190, 542, "L2  -  8 BGs -> 1 winner per rank")
f.text(430, 500, "rank0 winner", size=10, mono=False, fill=MUTED)
f.text(770, 500, "rank1 winner", size=10, mono=False, anchor="end", fill=MUTED)

# ---------------- L3 inter-rank ----------------
f.path("M290 520 L500 520 L500 590", arrow=True)
f.path("M950 520 L740 520 L740 590", arrow=True)
mux3 = f.mux(470, 590, 300, 54, "inter_rank_arb", sel="tRTRS wt")
f.note(300, 668, "L3  -  pick ACROSS ranks: skip tWTR on a rank hop, charge tRTRS; "
                 "same rank -> normal tCCD/tWTR")

f.line(620, 644, 620, 700, arrow=True)
f.text(620, 722, "->  packer (bundle)", size=12, mono=False, anchor="middle")

# parallelism note
f.note(70, 772, "two diff-rank misses run in PARALLEL: both PRE share a bundle "
                "(tPPD=2), both ACT share a bundle (cross-rank = no tRRD);")
f.note(70, 788, "only the two CAS serialize on the one DQ bus (~tRTRS apart).")

f.caption(40, 858, "L0 is per cell [rank][bank] - all 64 live, each emits its one "
                   "state-picked cmd. Rank is chosen ONLY at L3; L1/L2 are "
                   "per-rank subtrees, one shared issue path below.")

f.save("fig_07_l0_rank.svg")
print("wrote fig_07_l0_rank.svg")
