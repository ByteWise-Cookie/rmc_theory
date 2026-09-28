from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_58 — ONE path: ACT issue -> writeback. Shows GC, phase_off adder, CONST_BANK
# taps, the 6 UPD adders (3 bank / 1 BG / 2 rank), the 3:1 mux on the shared
# next_pre adder, reg-file writes, then GE -> SR flop -> can_*. act_issue = WE + RESET.

f = Fig(1580, 880)


def adder(cx, cy, sub):
    f.counter(cx, cy, 20, "+", sub)


def gge(cx, cy):
    f.decision(cx, cy, 54, 28, "GE")


def srflop(x, y):
    f.rect(x, y - 15, 46, 30, fill=PAPER, width=W_CELL)
    f.text(x + 23, y + 5, "SR", size=10, anchor="middle", bold=True)


def canpill(x, y, name):
    f.rect(x, y - 14, 150, 28, fill=FILL_NEW, width=W_CELL)
    f.text(x + 75, y + 4, name, size=10, mono=True, anchor="middle")


f.text(40, 34, "ACT issue -> writeback datapath  (one command, all 6 deadlines)",
       size=15, mono=False, bold=True)
f.note(40, 54, "GC_ph = GC + phase_off feeds every adder. CONST_BANK taps: fixed wire "
               "(1 writer) or 3:1 mux (shared adder). act_issue = write-enable + RESET.")

# ---- GC + phase_off ----
f.counter(95, 150, 32, "GC", "+=gear")
f.text(60, 205, "CK-valued", size=9, mono=False, fill=MUTED)
adder(210, 150, "ph_off")
f.line(127, 150, 188, 150, arrow=True)
f.text(150, 140, "GC", size=9, mono=True, fill=MUTED)
f.text(232, 120, "phase_off", size=9, mono=True, fill=MUTED)
f.line(232, 138, 232, 128, arrow=True)      # phase_off in from top
# GC_ph broadcast rail (vertical)
f.line(232, 150, 300, 150, arrow=False)
f.path("M300 150 V620", arrow=False, stroke=INK)
f.text(305, 138, "GC_ph -> all adders", size=9, mono=False, fill=MUTED)

# ---- CONST_BANK ----
f.block(40, 300, 150, 250, "CONST_BANK", "15 x 8b, cfg-written")
f.text(48, 545, "tRC tRCD tRAS", size=8, mono=True, fill=MUTED)
f.text(48, 340, "freq FSM reload", size=8, mono=False, fill=MUTED)
f.text(48, 356, "-> real flops", size=8, mono=False, fill=MUTED)

# ---- adder stack ----
AX = 460
rows = [
    (110, "+tRC",   "next_act", "BANK", FILL_CELL),
    (180, "+tRCD",  "next_cas", "BANK", FILL_CELL),
    (250, "+tRAS*", "next_pre", "BANK", FILL_CELL),   # * = muxed
    (350, "+tRRD_L","next_act_bg", "BGS", FILL_NEW),
    (450, "+tRRD_S","next_act_dbg", "BGD", FILL_ACTIVE),
    (540, "+tFAW",  "next_faw", "RANK", FILL_ACTIVE),
]

# GC_ph tap into each adder (from rail x=300)
for (cy, sub, field, scope, fill) in rows:
    f.line(300, cy, AX - 20, cy, arrow=True)

# CONST_BANK taps (from x=190) — fixed wires, except muxed one
def const_tap(cy):
    f.path(f"M190 425 H360 V{cy} H{AX-14}", arrow=True, dashed=True, stroke=MUTED)

for (cy, sub, field, scope, fill) in rows:
    if cy != 250:
        f.path(f"M190 480 H{AX-60} V{cy+14} L{AX-16} {cy+10}", arrow=True,
               dashed=True, stroke=MUTED)

# adders
for (cy, sub, field, scope, fill) in rows:
    adder(AX, cy, sub)

# ---- 3:1 mux on next_pre adder ----
mx = AX - 90
f.rect(mx, 232, 44, 40, fill=FILL_LOGIC, width=W_CELL)   # trapezoid-ish mux body
f.text(mx + 22, 248, "MUX", size=8, anchor="middle", bold=True)
f.text(mx + 22, 262, "3:1", size=8, anchor="middle")
f.line(mx + 44, 252, AX - 18, 252, arrow=True)
# mux inputs: tRAS / tRTP / tWR-tail
f.text(mx - 92, 238, "tRAS(ACT)", size=8, mono=True, fill=INK)
f.text(mx - 92, 252, "tRTP(RD)", size=8, mono=True, fill=MUTED)
f.text(mx - 92, 266, "118(WR)", size=8, mono=True, fill=MUTED)
f.line(mx - 30, 238, mx, 240, arrow=True)
f.line(mx - 30, 252, mx, 252, arrow=True)
f.line(mx - 30, 266, mx, 264, arrow=True)
f.text(mx + 22, 290, "sel=issued_cmd", size=8, mono=True, anchor="middle", fill=MUTED)
f.line(mx + 22, 285, mx + 22, 273, arrow=True)

# ---- reg files ----
RX = 700
f.rect(RX, 90, 180, 210, fill=FILL_CELL, width=W_CELL)
f.text(RX + 90, 112, "BANK_RF[bank]", size=11, anchor="middle", bold=True)
for j, fld in enumerate(["next_act (13b)", "next_cas (13b)", "next_pre (13b)"]):
    f.text(RX + 14, 150 + j * 45, fld, size=9, mono=True)
f.rect(RX, 325, 180, 55, fill=FILL_NEW, width=W_CELL)
f.text(RX + 90, 347, "BGS_RF[bg]", size=11, anchor="middle", bold=True)
f.text(RX + 14, 368, "next_act_bg (13b)", size=9, mono=True)
f.rect(RX, 410, 180, 130, fill=FILL_ACTIVE, width=W_CELL)
f.text(RX + 90, 432, "RANK_RF", size=11, anchor="middle", bold=True)
f.text(RX + 14, 462, "next_act_dbg (13b)", size=9, mono=True)
f.text(RX + 14, 500, "faw_ts[4] -> +tFAW", size=9, mono=True)

# adder -> reg
amap = [(110, 150), (180, 195), (250, 240), (350, 352), (450, 462), (540, 500)]
for (ay, ry) in amap:
    f.path(f"M{AX+20} {ay} H{RX}", arrow=True) if ay == ry else \
        f.path(f"M{AX+20} {ay} H{RX-20} V{ry} H{RX}", arrow=True)

# ---- GE -> SR -> can_* (tail, per field) ----
GX, SX, CX = 960, 1050, 1130
tail = [
    (150, "can_act"), (195, "can_cas"), (240, "can_pre"),
    (352, "can_act_bgs"), (462, "can_act_bgd"), (500, "can_act_rank"),
]
for (ty, nm) in tail:
    f.line(RX + 180, ty, GX - 27, ty, arrow=True)
    gge(GX, ty)
    f.line(GX + 27, ty, SX, ty, arrow=True)
    f.text(GX + 33, ty - 6, "S", size=8, fill=MUTED)
    srflop(SX, ty)
    f.line(SX + 46, ty, CX, ty, arrow=True)
    canpill(CX, ty, nm)

# GC into every GE
f.path("M300 620 H960 V536", arrow=True, dashed=True, stroke=FAINT)
f.text(600, 632, "GC -> all GE (compare)", size=9, mono=False, fill=MUTED)

# act_issue = WE + RESET rail
f.text(RX + 40, 70, "act_issue", size=10, mono=True, bold=True)
f.path("M760 74 V300", arrow=True, dashed=True, stroke=MUTED)      # WE into regs
f.text(770, 315, "WE (write next_*)", size=8, mono=False, fill=MUTED)
f.path("M1073 70 H1073 V135", arrow=True, dashed=True, stroke=MUTED)  # RESET into SR
f.text(1080, 66, "RESET (block now, reset-dominant) -> every SR this issue writes",
       size=8, mono=False, fill=MUTED)

f.caption(40, 858,
          "ACT stamps 3 bank + 1 BG + 2 rank in one mc_clk: 6 parallel adders, each GC_ph + a "
          "CONST_BANK tap (fixed wire, or 3:1 mux where the adder is shared across cmds). act_issue "
          "write-enables the regs AND resets the can_* SR flops; each GE re-sets can_* at GC >= next_*.")

f.save("fig_58_act_writeback_adders.svg")
print("wrote fig_58_act_writeback_adders.svg")
