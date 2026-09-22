from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_52 — RAW ACT-issue timestamp path (bank level, one rank).
# ACT grant {rank,bg,bank,row,phase_off} -> stamp bank's next_act/cas/pre =
# (GC+phase_off)+const -> comparators -> can_act/cas/pre (1-bit each). x32/rank.
# Unoptimized on purpose; optimize later.

f = Fig(1460, 700)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "RAW ACT-issue timestamp path - bank level, one rank", size=15,
       mono=False, bold=True)
f.note(40, 58, "ACT grant -> stamp bank next_act/cas/pre = (GC+phase_off)+const. can_* is an "
               "SR flop: RESET on issue (block now), SET when GC>=next (>=, not ==). x32/rank.")

# ---- ACT grant ----
g = f.block(40, 100, 170, 64, "ACT_GRANT", "{rank,bg,bank,row,phase_off}")
f.line(210, 118, 250, 118, arrow=True)
cnote(214, 110, "bank")
f.line(210, 148, 250, 148, arrow=True)
cnote(214, 168, "phase_off, row")

# ---- GC + phase adder ----
gc = f.counter(120, 250, 32, "GC", "CK")
f.line(152, 250, 200, 250, arrow=True)
pa = f.decision(238, 250, 64, 54, "+", "phase")
cnote(214, 232, "phase_off")
f.line(238, 223, 238, 168, arrow=True, dashed=True)
f.line(270, 250, 330, 250, arrow=True)
cnote(276, 242, "GC_phase")

# ---- timing const ----
tc = f.block(330, 90, 160, 60, "TIMING_CONST", "shared, 1 copy")
f.text(346, 138, "tRC=117 tRCD=40 tRAS=77", size=10, mono=True, fill=MUTED)

# ---- 3 adders ----
adds = [("+ tRC", "next_act", 190), ("+ tRCD", "next_cas", 250), ("+ tRAS", "next_pre", 310)]
for lab, out, y in adds:
    a = f.logic(360, y - 22, 130, 44, lab, top=False)
    f.line(330, 250, 358, y, arrow=True) if y != 250 else f.line(330, 250, 358, 250, arrow=True)
    f.line(410, 150, 410, y - 22, arrow=True, dashed=True) if y == 190 else None
    f.line(490, y, 700, y, arrow=True)
    cnote(560, y - 8, out + " = GC_phase + const")

# ---- bank decode / WE ----
bd = f.logic(360, 380, 150, 48, "bank_decode", "bank -> WE[32]", top=True)
f.line(250, 148, 250, 404, arrow=False)
f.path("M250 404 H358", arrow=True)
f.path("M510 404 H620 V360", arrow=True, dashed=True)
cnote(520, 420, "WE (write the winning bank's row)")

# ---- BANK_RF ----
rf = f.block(700, 120, 300, 260, "BANK_RF", "x32 entries")
f.text(716, 156, "state  open_row", size=11, mono=True, fill=MUTED)
for i, nm in enumerate(["next_act[13]", "next_cas[13]", "next_pre[13]"]):
    f.rect(716, 176 + i * 40, 268, 32, fill=FILL_CELL, width=W_CELL)
    f.text(724, 197 + i * 40, nm, size=11, mono=True)
cnote(716, 356, "1 row = 1 bank; WE selects the winner")

# ---- SET (comparator) + RESET (issue) -> SR flop -> can_* ----
# reset bus from issue-decode into the SR-flop stack (shared, reset-dominant)
f.path("M510 404 H1141 V296", arrow=True, dashed=True)
cnote(1000, 462, "RESET = issue-decode -> all affected can_* (reset-dominant)")
for i, (nm, y) in enumerate([("can_act", 192), ("can_cas", 232), ("can_pre", 272)]):
    f.line(984, y, 1014, y, arrow=True)
    f.decision(1040, y, 58, 32, "GE")
    cnote(1012, y - 22, "GC>=next")
    f.line(1069, y, 1104, y, arrow=True)
    cnote(1086, y - 6, "S")
    f.rect(1104, y - 16, 74, 32, fill=FILL_LOGIC, width=W_CELL)
    f.text(1141, y + 4, "SR", size=11, anchor="middle", bold=True)
    f.line(1178, y, 1224, y, arrow=True)
    f.rect(1224, y - 13, 96, 26, fill=FILL_NEW, width=W_CELL)
    f.text(1272, y + 5, nm, size=11, mono=True, anchor="middle")
    f.line(1320, y, 1372, y, arrow=True)
# GC broadcast to all GE
f.path("M120 282 V460 H1040 V296", arrow=True, dashed=True)
cnote(600, 452, "GC -> all GE comparators")
f.text(1372, 232, "-> ARB", size=12, mono=False, anchor="end")
cnote(1224, 300, "can_* = SR flop: RESET on issue, SET on deadline (x3 x32/rank)")

# ---- state note ----
cnote(490, 440, "ACT also: state ACTING->OPEN (after tRCD), open_row<-row")

f.caption(40, 668,
          "RAW: ACT grant decodes to one bank; (GC+phase_off) feeds three adders (+tRC/tRCD/tRAS) "
          "that load that bank's next_act/cas/pre. can_* is a reset-dominant SR flop: the "
          "issue-decode RESETS it (block now), the GC>=next comparator SETS it when the deadline "
          "passes (>=, never ==, or gear skips it). 3x32 flops+cmps/rank; shared const table.")

f.save("fig_52_act_timestamp_raw.svg")
print("wrote fig_52_act_timestamp_raw.svg")
