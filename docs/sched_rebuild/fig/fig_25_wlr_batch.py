from rtlfig import Fig, MUTED, FILL_ACTIVE, FAINT

# fig_25 — WLR direction-batch (one rank lane).
# Invariant: direction lives ONLY in wlr_ctrl. batch_dir selects which split
# bp-FIFO feeds the single combined path; off-dir waits in its bp-FIFO.
# Lookahead sees one direction, stays direction-blind.

f = Fig(1180, 680)

# ---------------- lane / rank labels ----------------
f.note(530, 44, "rank r  (one lane)", anchor="middle")
f.note(1140, 60, "x N_RANKS", anchor="end")
f.note(497, 68, "split by direction (stage 1)", anchor="middle")

# ---------------- split bp-FIFOs (depth 16) ----------------
# rd shown as the currently-selected direction (active fill); wr waits.
f.cells(380, 88, 3, 44, 46, fills=[FILL_ACTIVE] * 3)
f.text(380, 80, "rd_bp_fifo[r]", size=12)
f.cells(548, 88, 3, 44, 46)
f.text(548, 80, "wr_bp_fifo[r]", size=12)
cx_rd, cx_wr = 446, 614
f.note(688, 100, "depth 16 - off-dir batch waits HERE (deep),", anchor="start")
f.note(688, 118, "never in the shallow lookahead window", anchor="start")

# streams down into the select mux
f.line(cx_rd, 134, cx_rd, 300, arrow=True)
f.line(cx_wr, 134, cx_wr, 300, arrow=True)
f.text(cx_rd, 152, "rd", size=11, anchor="middle", fill=MUTED)
f.text(cx_wr, 152, "wr", size=11, anchor="middle", fill=MUTED)

# ---------------- wlr_sel mux ----------------
f.mux(430, 300, 200, 54, "wlr_sel")

# ---------------- wlr_ctrl (the ONE direction owner) ----------------
wc = f.logic(70, 286, 250, 130, "wlr_ctrl[r]", top=True)
f.text(82, 332, "batch_dir : R | W   (1b)", size=11)
f.text(82, 356, "batch_cnt : run length", size=11)
f.text(82, 380, "cap_R = 12    cap_W = 24..42", size=11)
f.text(82, 404, "turnaround_ctrl", size=11, italic=True, fill=MUTED)
# batch_dir drives the mux select
f.line(322, 327, 424, 327, arrow=True)
f.text(373, 320, "batch_dir", size=11, anchor="middle", fill=MUTED)

# fifo empty/full flags -> wlr_ctrl (dashed, from fifo left edge)
f.path("M360 160 H300 V286", dashed=True, arrow=True)
f.text(356, 150, "rd/wr empty,full", size=10, mono=False, anchor="end", fill=MUTED)

# ---------------- scoreboard feed (last_cas_dir + turnaround price) ----------
f.logic(70, 452, 250, 74, "scoreboard[r]", top=True)
f.text(82, 486, "last_cas_dir", size=11)
f.text(82, 508, "turnaround gate  tWTR | tRTW", size=11)
f.line(195, 452, 195, 418, arrow=True)
f.text(207, 438, "flip price / dir", size=10, mono=False, fill=MUTED)

# ---------------- combined path out ----------------
f.line(530, 354, 530, 470, arrow=True)
f.slash(530, 410, "REQ_W")
f.text(514, 402, "{rob_index, phy_adr, op}", size=11, anchor="end", fill=MUTED)
f.text(514, 420, "single-dir stream", size=11, anchor="end", fill=MUTED)
f.text(530, 494, "->  to lookahead (stage 2)", size=12, mono=False, anchor="middle")

# ---------------- right panel: flip logic + asymmetry + downstream ----------
f.line(672, 176, 672, 610, stroke=FAINT)
x0 = 700
f.text(x0, 300, "flip batch_dir when:", size=13, mono=False, bold=True)
f.note(x0, 326, "1. chosen FIFO drained (empty)   ->  free flip, no waste")
f.note(x0, 348, "2. batch_cnt == cap              ->  starvation force")
f.text(x0, 380, "sequence = drain-then-flip:", size=12, mono=False, bold=True)
f.note(x0 + 16, 402, "stop pulling old dir")
f.note(x0 + 16, 422, "let window + cells clear (old-dir tail issues)")
f.note(x0 + 16, 442, "turnaround gate holds new-dir CAS (tWTR | tRTW)")
f.note(x0 + 16, 462, "flip batch_dir, pull new dir")
f.text(x0, 496, "asymmetry:", size=12, mono=False, bold=True)
f.note(x0 + 74, 496, "R->W = tRTW 12    W->R = CWL+BL/2+tWTR 24..42")
f.note(x0 + 16, 516, "=> write batch runs LONGER (costlier to leave)")
f.text(x0, 550, "residual mix:", size=12, mono=False, bold=True)
f.note(x0 + 16, 570, "r/w stragglers in cells cleaned downstream by")
f.note(x0 + 16, 590, "rank-bias (last_cas_dir streak bonus at rank_cas)")

# ---------------- caption (invariant) ----------------
f.caption(40, 654,
          "Direction lives ONLY in wlr_ctrl: batch_dir selects which split "
          "bp-FIFO feeds the one combined path; off-dir waits in its bp-FIFO. "
          "Lookahead sees one direction, stays direction-blind.")

f.save("fig_25_wlr_batch.svg")
print("wrote fig_25_wlr_batch.svg")
