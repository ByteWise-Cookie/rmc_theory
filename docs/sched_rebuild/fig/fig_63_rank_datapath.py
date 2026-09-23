from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_63 — RANK-scope timestamp datapath (x2 = N_RANKS). Widest scope, 5 gate
# outputs but only 2 writeback adders + a faw ring:
#   adder0 = next_act_dbg (tRRD_S, ACT)
#   adder1 = {next_wr(tRTW,RD) | next_rd(tWTR,WR) | next_pre(tPPD,PRE)}  demux by cmd
#   FAW_RING[4] = ACT pushes GC_ph (latch, no adder); read-side +tFAW -> can_act_rank

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"; MAXC = "#b0602a"
f = Fig(1480, 1240)

# gate output columns
G = {"dbg": 250, "faw": 470, "wr": 740, "rd": 960, "pre": 1200}
LAB = {"dbg": "can_act_bgd", "faw": "can_act_rank", "wr": "can_wr",
       "rd": "can_rd", "pre": "can_pre_rk"}


def adder(cx, cy, r=20):
    f.counter(cx, cy, r, "+", "")
    f.text(cx, cy + 4, "+", size=13, anchor="middle", bold=True)


f.text(40, 32, "RANK-scope timestamp datapath  (x2 = N_RANKS)", size=15,
       mono=False, bold=True)
f.text(40, 150, "5 gate outputs, but only 2 writeback adders (2 cmds/cycle) + a faw ring.",
       size=9, mono=False, fill=INK)
f.text(40, 168, "adder0 = next_act_dbg (ACT).  adder1 = next_wr|next_rd|next_pre demux by cmd.",
       size=9, mono=False, fill=MUTED)
f.text(40, 186, "faw = ring latch (ACT pushes GC_ph, NO adder); +tFAW is read-side only.",
       size=9, mono=False, fill=MUTED)

# ---------- bottom: grant + ctl ----------
f.block(40, 1120, 300, 54, "r0 GRANT", "{cmd, rank, ph_off}")
f.block(410, 1120, 240, 54, "FEEDBACK_CTL", "cmd -> op_code")
f.line(340, 1147, 408, 1147, arrow=True)

# ---------- const + sel ----------
f.block(40, 1010, 300, 66, "RANK_CONST", "tRRD_S tFAW tRTW WTR_L/S tPPD tRTRS")
f.logic(410, 1005, 760, 78, "const_sel  (op_code)", "", top=True)
f.line(340, 1040, 408, 1040, arrow=True)
f.path("M520 1120 V1085", arrow=True, stroke=MUTED)
f.text(528, 1105, "op_code", size=8, mono=True, fill=MUTED)

# ---------- GC + phase (shared) ----------
f.block(40, 880, 300, 56, "global_counter_24b", "shared; compare low 13b")
adder(400, 908)
f.line(340, 908, 378, 908, arrow=True)
f.text(404, 886, "+ph_off", size=8, mono=True, fill=MUTED)
f.path("M422 908 H1330 V845", arrow=False, stroke=GREEN)
f.text(760, 900, "GC_ph -> adders + faw push + (13b) compares", size=8, fill=GREEN)

# ---------- adders ----------
adder(250, 820)                         # adder0 = dbg
f.line(250, 1005, 250, 840, arrow=True)
f.text(258, 980, "tc_dbg (tRRD_S)", size=8, mono=True, fill=INK)
f.line(210, 845, 244, 806, arrow=True, stroke=GREEN)

adder(960, 820)                         # adder1 = turn/pre
f.line(960, 1005, 960, 840, arrow=True)
f.text(968, 980, "tc_turn (tRTW|tWTR|tPPD 3:1)", size=8, mono=True, fill=INK)
f.line(920, 845, 954, 806, arrow=True, stroke=GREEN)
f.text(760, 782, "2-PRE corner: max-select later phase before +tPPD", size=8,
       mono=True, fill=MAXC)

# ---------- FAW ring (own path) ----------
f.block(410, 760, 130, 90, "FAW_RING[4]", "push GC_ph (ACT)")
f.text(418, 862, "latch, no adder", size=8, mono=False, fill=MUTED)
adder(470, 660)
f.text(430, 638, "+tFAW", size=8, mono=True, fill=INK)
f.line(470, 760, 470, 680, arrow=True)
f.text(478, 720, "oldest", size=8, mono=True, fill=MUTED)

# ---------- write demux ----------
WY = 620
# adder0 -> dbg demux
f.path(f"M{250-26} {WY+34} L{250+26} {WY+34} L{250+46} {WY} L{250-46} {WY} Z",
       arrow=False, stroke=INK)
f.line(250, 800, 250, WY + 34, arrow=True)
# adder1 -> demux fanning to wr/rd/pre
f.path(f"M{960-26} {WY+34} L{960+26} {WY+34} L{960+70} {WY} L{960-70} {WY} Z",
       arrow=False, stroke=INK)
f.line(960, 800, 960, WY + 34, arrow=True)
f.text(150, WY + 8, "{rank} WE + field mask", size=8, mono=True, fill=ISSUE)
# fan from adder1 demux to the 3 fields
for cx in (G["wr"], G["rd"], G["pre"]):
    f.line(960, WY, cx, WY - 10, arrow=False, stroke=INK)

# ---------- cells (x2) ----------
CY = 470
cell_cols = {"dbg": 250, "wr": 740, "rd": 960, "pre": 1200}
for k, cx in cell_cols.items():
    f.rect(cx - 24, CY, 48, 130, fill=PAPER, width=W_CELL)
    f.text(cx, CY + 70, "ts", size=10, anchor="middle", bold=True)
    f.rect(cx + 34, CY + 8, 34, 114, fill=PAPER, width=1.0, stroke=FAINT)
    f.text(cx + 50, CY + 142, "x2", size=9, anchor="middle", fill=MUTED)
    if k == "dbg":
        f.line(cx, WY, cx, CY + 130, arrow=True)
    else:
        f.line(cx, WY - 10, cx, CY + 130, arrow=True)

# ---------- comparators + cans ----------
GY = 350
KY = 230
for k, cx in G.items():
    f.counter(cx, GY, 21, ">=", "")
    f.text(cx - 42, GY + 4, "GC13", size=8, mono=True, fill=GREEN)
    f.line(cx - 58, GY, cx - 21, GY, arrow=True, stroke=GREEN)
    f.rect(cx - 62, KY - 18, 124, 32, fill=FILL_NEW, width=W_CELL)
    f.text(cx, KY, LAB[k], size=10, mono=True, anchor="middle")
    f.line(cx + 10, GY - 21, cx + 10, KY + 14, arrow=True, stroke=CMP)
    f.text(cx + 14, 300, "set", size=8, fill=CMP)
    f.line(cx - 12, GY - 21, cx - 12, KY + 14, arrow=True, stroke=ISSUE)
    f.text(cx - 30, 300, "rst", size=8, fill=ISSUE)
# faw compare feeds from ring adder
f.line(470, 620, 470, GY + 21, arrow=True)
# cells -> their comparators
for k, cx in cell_cols.items():
    f.line(cx, CY, cx, GY + 21, arrow=True)

f.text(40, 210, "RST = issue-decode (reset-dominant).  SET = GC[12:0] >= ts (>=, never ==).",
       size=9, mono=False, fill=INK)

f.caption(40, 1228,
          "Rank = 2 writeback adders + faw ring, feeding 5 gates over x2 rank entries. adder0 -> "
          "next_act_dbg (tRRD_S, ACT). adder1 -> next_wr/next_rd/next_pre (demux by cmd: RD->wr, "
          "WR->rd, PRE->pre). FAW_RING[4] latches GC_ph on ACT (no adder); read-side +tFAW on the "
          "oldest -> can_act_rank. 2-PRE both target next_pre -> max-select later phase, one write.")

f.save("fig_63_rank_datapath.svg")
print("wrote fig_63_rank_datapath.svg")
