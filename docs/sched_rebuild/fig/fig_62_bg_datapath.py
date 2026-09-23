from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_62 — BG-scope timestamp datapath (companion to fig_61 bank).
# 2 fields: next_act_bg (tRRD_L, ACT) / next_cas_bg (tCCD_L RD | tCCD_L_WR WR).
# 3 consts, x16 cells, addr = {rank,bg}. No vld AND - BG gate is pure spacing.

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"
f = Fig(1060, 1180)
COLS = {"act_bg": 470, "cas_bg": 790}
LAB = {"act_bg": "can_act_bgs", "cas_bg": "can_cas_bgs"}


def adder(cx, cy, r=20):
    f.counter(cx, cy, r, "+", "")
    f.text(cx, cy + 4, "+", size=13, anchor="middle", bold=True)


f.text(40, 32, "BG-scope timestamp datapath  (x16 = N_RANKS x 8 BG)", size=15,
       mono=False, bold=True)
f.text(40, 210, "Only 2 fields. next_act_bg written by ACT (fixed tRRD_L); next_cas_bg by "
        "RD/WR (2:1).", size=9, mono=False, fill=MUTED)
f.text(40, 228, "No vld/state gate - BG spacing is timing-only (unlike can_cas at bank).",
        size=9, mono=False, fill=MUTED)

# grant + ctl
f.block(40, 1090, 320, 56, "r0  GRANT", "{cmd, rank, bg, ph_off}")
f.block(430, 1090, 260, 56, "FEEDBACK_CTL", "cmd -> op_code")
f.line(360, 1118, 428, 1118, arrow=True)

# const + sel
f.block(40, 980, 320, 70, "BG_CONST", "3x8b: tRRD_L tCCD_L tCCD_L_WR")
f.logic(410, 975, 470, 80, "const_sel  (op_code)", "", top=True)
f.line(360, 1010, 408, 1010, arrow=True)
f.path("M560 1090 V1057", arrow=True, stroke=MUTED)
f.text(568, 1075, "op_code", size=8, mono=True, fill=MUTED)

# GC + phase
f.block(40, 855, 320, 60, "global_counter_24b", "shared; compare low 13b")
adder(410, 885)
f.line(360, 885, 388, 885, arrow=True)
f.text(414, 862, "+ph_off", size=8, mono=True, fill=MUTED)
f.line(410, 862, 410, 848, arrow=True)
f.path("M432 885 H880 V820", arrow=False, stroke=GREEN)
f.text(700, 878, "GC_ph -> adders + (13b) compares", size=8, mono=False, fill=GREEN)

# adders
ADDY = 800
for k, cx in COLS.items():
    adder(cx, ADDY)
    f.line(cx, 975, cx, ADDY + 20, arrow=True)
    f.text(cx + 8, 950, f"tc_{k}", size=9, mono=True, fill=INK)
    f.line(cx - 40, 820, cx - 6, ADDY - 6, arrow=True, stroke=GREEN)
f.text(COLS["act_bg"] - 20, 762, "tRRD_L (fixed)", size=8, mono=True, fill=MUTED)
f.text(COLS["cas_bg"] - 20, 762, "tCCD_L / tCCD_L_WR (2:1)", size=8, mono=True, fill=MUTED)

# write route
WY = 690
for k, cx in COLS.items():
    # DEMUX: narrow input (adder) -> wide output (N cells)
    f.path(f"M{cx-26} {WY+34} L{cx+26} {WY+34} L{cx+46} {WY} L{cx-46} {WY} Z",
           arrow=False, stroke=INK)
    f.line(cx, ADDY - 20, cx, WY + 34, arrow=True)
f.text(300, WY + 8, "{rank,bg} ->", size=9, mono=True, fill=ISSUE)
f.line(400, WY + 5, COLS["act_bg"] - 36, WY + 5, arrow=True, stroke=ISSUE)
f.text(150, WY + 60, "write DEMUX = 1 adder -> 1 of 16 (one-hot WE + field mask: ACT->act_bg, RD/WR->cas_bg)",
       size=8, mono=False, fill=ISSUE)

# cells
CY = 470
for k, cx in COLS.items():
    f.rect(cx - 26, CY, 52, 150, fill=PAPER, width=W_CELL)
    f.text(cx, CY + 78, "next_bg", size=9, anchor="middle", bold=True)
    f.line(cx, WY, cx, CY + 150, arrow=True)
    f.rect(cx + 40, CY + 10, 40, 130, fill=PAPER, width=1.0, stroke=FAINT)
    f.text(cx + 60, CY + 165, "....", size=12, anchor="middle", fill=MUTED)
f.text(880, CY + 20, "time_stamp  x16 flops", size=9, mono=False, fill=MUTED)
f.text(880, CY + 38, "broadcast D, one-hot WE", size=8, mono=False, fill=MUTED)

# comparators
GY = 380
for k, cx in COLS.items():
    f.counter(cx, GY, 22, ">=", "")
    f.line(cx, CY, cx, GY + 22, arrow=True)
    f.text(cx - 44, GY + 4, "GC13", size=8, mono=True, fill=GREEN)
    f.line(cx - 60, GY, cx - 22, GY, arrow=True, stroke=GREEN)

# can flops
KY = 230
for k, cx in COLS.items():
    f.rect(cx - 68, KY - 20, 136, 34, fill=FILL_NEW, width=W_CELL)
    f.text(cx, KY, LAB[k], size=11, mono=True, anchor="middle")
    f.line(cx + 10, GY - 22, cx + 10, KY + 14, arrow=True, stroke=CMP)
    f.text(cx + 15, 320, "set", size=8, fill=CMP)
    f.line(cx - 12, 640, cx - 12, KY + 14, arrow=True, stroke=ISSUE)
    f.text(cx - 34, 320, "rst", size=8, fill=ISSUE)

f.text(40, 150, "RST = issue-decode (reset-dominant).  SET = GC[12:0] >= next_bg.", size=9,
       mono=False, fill=INK)
f.text(40, 168, "can_act_bgs blocks the whole BG's ACTs; can_cas_bgs blocks the BG's CAS.",
       size=9, mono=False, fill=MUTED)

f.caption(40, 1168,
          "Same skeleton as bank (fig_61), 2 fields: next_act_bg <- ACT (fixed tRRD_L), "
          "next_cas_bg <- RD/WR (2:1 tCCD_L/tCCD_L_WR). x16 cells, {rank,bg} write-route. If ACT+CAS "
          "hit the SAME BG same cycle they write DIFFERENT fields -> no conflict. No vld - BG is "
          "spacing-only. Direction-match on next_cas_bg is by the const the last CAS wrote.")

f.save("fig_62_bg_datapath.svg")
print("wrote fig_62_bg_datapath.svg")
