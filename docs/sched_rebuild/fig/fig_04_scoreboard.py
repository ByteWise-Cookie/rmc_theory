from rtlfig import Fig, MUTED, FILL_CELL, FILL_NEW

# fig_04 — timing scoreboard, deadline form.
# Invariant: can_x = (GC - next_x)[MSB]==0. Comparators write only the 1-bit
# gates; timestamps are written once, at issue.

SB = "#7a5cb8"
f = Fig(1140, 760)

# ---------------- issue writes a deadline ----------------
f.text(430, 58, "cmd_issued  @ out_cmd_fifo commit", size=12, mono=False,
       anchor="middle")
f.line(430, 66, 430, 84, arrow=True)

f.logic(280, 86, 300, 86, "timing_reg_file   (T_*)", top=True)
f.text(300, 138, "parametric:  ns floor + tCK  ->  CK", size=11, mono=False,
       fill=MUTED)
f.text(300, 158, "T_RCD  T_RP  T_RAS  T_CCD  T_RTP ...", size=11)
f.line(430, 172, 430, 204, arrow=True)
f.text(444, 192, "T_x", size=11, fill=MUTED)

# GC counter
f.counter(150, 230, 44, "GC", "+gear")
f.text(150, 292, "13-bit CK, wraps", size=10, mono=False, anchor="middle",
       fill=MUTED)
f.line(196, 230, 358, 230, arrow=True)

f.logic(360, 204, 180, 52, "adder", "next_x = GC + T_x")
f.line(450, 256, 450, 312, arrow=True)
f.text(464, 288, "written once @ issue", size=10, mono=False, fill=MUTED)

# ---------------- deadline table ----------------
f.note(300, 306, "deadline table  (per bank)")
f.cells(300, 314, 3, 150, 52,
        ["next_act[b]", "next_cas[b]", "next_pre[b]"],
        fills=[None, FILL_NEW, None])

# ---------------- comparator = the hero ----------------
f.logic(790, 314, 320, 130, "comparator   (x3 class  x32 bank)", top=True)
f.text(950, 362, "can_x = (GC - next_x)[MSB] == 0", size=15, anchor="middle",
       bold=True)
f.text(950, 392, "MSB = sign of the wrap-subtract", size=11, mono=False,
       anchor="middle", fill=MUTED)
f.text(950, 410, "no full compare in the pick path", size=11, mono=False,
       anchor="middle", fill=MUTED)

f.line(750, 340, 788, 340, arrow=True)
f.slash(769, 340, "next_*[b]")

# GC broadcast into the comparator
f.path("M150 274 L150 500 L950 500 L950 446", arrow=True)
f.text(560, 490, "GC  (broadcast to every comparator)", size=10, mono=False,
       fill=MUTED)

# can_* out to elig_gen
f.line(950, 446, 950, 548, arrow=True, stroke=SB)
f.text(964, 528, "can_pre/act/cas", size=11, fill=SB)
f.text(950, 568, "->  elig_gen (fig_03)", size=12, mono=False, anchor="middle",
       fill=SB)

# ---------------- the two things that make can_* whole ----------------
f.note(300, 612, "cross-bank: a CAS issue ALSO writes tCCD_S/tRRD into OTHER "
                 "banks' next_cas deadlines,")
f.note(300, 628, "so can_* already carries cross-bank spacing  -  the arb tiers "
                 "never reject a winner.")

f.cells(300, 660, 4, 58, 40, ["t0", "t1", "t2", "t3"])
f.text(300, 650, "faw_ts[4]  (per rank)", size=11)
f.note(548, 684, "can_act also needs  (GC - faw_ts[oldest]) >= tFAW")
f.note(548, 700, "tWTR / tRTW: rank-scoped, keyed by last_cas_dir/ts")

f.caption(40, 748, "Legality is deadline-form: can_x is just the MSB of "
                   "GC - next_x. Comparators write only the 1-bit gates; "
                   "timestamps are written once, at issue.")

f.save("fig_04_scoreboard.svg")
print("wrote fig_04_scoreboard.svg")
