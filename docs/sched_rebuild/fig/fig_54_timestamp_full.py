from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_54 — full timestamp path (generalizes fig_52 to all scopes + all cmds).
# grants -> writeback UPD -> per-scope next_* -> GE -> SR flop -> can_* ;
# arb ANDs the scope can_* per class. RAW/unoptimized.

f = Fig(1520, 840)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "Full timestamp path - all scopes, all commands (RAW)", size=15,
       mono=False, bold=True)
f.note(40, 58, "Any issued cmd (<=3 grants + ref) -> UPD stamps next_* per scope (fig_50) -> "
               "GE (GC>=next) SETS the SR flop; issue-decode RESETS it -> can_* -> arb ANDs per class.")

# ---- shared left column ----
f.block(40, 110, 175, 84, "GRANTS", "cas/act/pre/ref")
cnote(52, 178, "{rank,bg,bank,ph_off}")
f.counter(98, 250, 30, "GC", "+=gear")
f.block(40, 300, 175, 52, "TIMING_CONST", "shared consts")
upd = f.logic(240, 110, 170, 250, "WRITEBACK UPD",
              "next_*=GC_ph+const", top=True)
cnote(252, 176, "WE + RESET per scope")
cnote(252, 192, "(the fig_50 rows)")
f.line(215, 150, 238, 150, arrow=True)
f.line(128, 268, 128, 235, arrow=False)
f.path("M128 235 V150 H238", arrow=True)
f.line(215, 326, 238, 326, arrow=True)

ROWS = [
    ("BANK_TREG", ["next_act/cas/pre (13b)", "tRC/tRCD/tRAS,tRTP,tWR"],
     "can_act/cas/pre", FILL_CELL),
    ("BGS_TREG", ["next_act_bg, next_cas_bg", "tRRD_L, tCCD_L/L_WR"],
     "can_act_bgs/cas_bgs", FILL_NEW),
    ("BGD_TREG", ["next_act_dbg", "tRRD_S"],
     "can_act_bgd", FILL_NEW),
    ("RANK_TREG", ["faw_ts[4], next_rd/wr", "tFAW, tWTR/tRTW, gates"],
     "can_act_rank, turn", FILL_ACTIVE),
    ("GLOBAL", ["dqFree = GC+BL/2", "one DQ bus"],
     "can_cas_dq", FILL_LOGIC),
]

ys = [110, 240, 370, 500, 630]
for (nm, fields, canx, fill), y in zip(ROWS, ys):
    f.rect(450, y, 250, 96, fill=fill, width=W_CELL)
    f.text(462, y + 22, nm, size=12, mono=True, bold=True)
    for j, fl in enumerate(fields):
        f.text(462, y + 44 + j * 18, fl, size=10, mono=True, fill=MUTED)
    # UPD -> reg (WE + next_*)
    f.line(410, y + 48, 448, y + 48, arrow=True)
    # reg -> GE
    f.line(700, y + 48, 736, y + 48, arrow=True)
    f.decision(766, y + 48, 58, 30, "GE")
    cnote(738, y + 30, "GC>=")
    # GE -> SR (S)
    f.line(795, y + 48, 828, y + 48, arrow=True)
    cnote(806, y + 40, "S")
    f.rect(828, y + 32, 60, 32, fill=PAPER, width=W_CELL)
    f.text(858, y + 52, "SR", size=11, anchor="middle", bold=True)
    # RESET into SR (from UPD, shared) - short tick from below
    f.line(858, y + 82, 858, y + 64, arrow=True, dashed=True)
    # SR -> can_x
    f.line(888, y + 48, 924, y + 48, arrow=True)
    f.rect(924, y + 34, 168, 28, fill=FILL_NEW, width=W_CELL)
    f.text(1008, y + 52, canx, size=10, mono=True, anchor="middle")
    # can_x -> AND
    f.line(1092, y + 48, 1140, y + 48, arrow=True)

# GC broadcast to GE + RESET rail note
f.path("M128 268 V760 H766 V64", arrow=True, dashed=True)
cnote(300, 752, "GC -> all GE")
f.path("M325 360 V730 H858 V722", arrow=True, dashed=True)
cnote(360, 722, "RESET = issue-decode -> the SR flops it touches (reset-dominant)")

# ---- AND per class ----
f.logic(1140, 300, 210, 200, "AND per class", top=True)
f.text(1150, 350, "can_act = &(bank,bgs,", size=11, mono=True)
f.text(1150, 366, "            bgd,rank)", size=11, mono=True)
f.text(1150, 392, "can_cas = &(bank,bgs,", size=11, mono=True)
f.text(1150, 408, "            dq,turn)", size=11, mono=True)
f.text(1150, 434, "can_pre = bank", size=11, mono=True)
f.line(1350, 400, 1400, 400, arrow=True)
f.text(1410, 396, "-> ARB", size=12, mono=False)
cnote(1150, 470, "(never rejects - pure select)")

f.caption(40, 812,
          "Same slice as fig_52 replicated across BANK/BGS/BGD/RANK/GLOBAL and driven by every "
          "issued cmd via the fig_50 writeback: UPD stamps next_* (GC_ph+const) with per-scope WE, "
          "GE sets the SR flop at the deadline, issue-decode resets it. The arb ANDs the scope "
          "can_* a candidate touches into can_act/cas/pre. Optimize (share adders/cmps) later.")

f.save("fig_54_timestamp_full.svg")
print("wrote fig_54_timestamp_full.svg")
