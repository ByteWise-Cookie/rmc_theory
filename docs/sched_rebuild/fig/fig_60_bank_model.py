from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_60 — per-bank MODEL: the 4 reg arrays + the FSM state diagram, every edge
# tagged by its WRITER. Two driver classes: issue-edge (into -ing states) and
# timestamp comparator (out of -ing states); + ME (ref_pending), propose (pre_pending).

ISSUE = "#7a4fb0"   # issue-edge (packer commit)
CMP   = "#2a8f86"   # timestamp comparator (GE)
ME    = "#b0602a"   # maintenance engine

f = Fig(1500, 820)


def state(cx, cy, name, fill=PAPER):
    w, h = 120, 46
    f.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, width=1.6, rx=10)
    f.text(cx, cy + 5, name, size=12, anchor="middle", bold=True)


f.text(40, 34, "Per-bank model - reg arrays + FSM + who writes", size=15,
       mono=False, bold=True)
f.note(40, 54, "4 parallel arrays per bank (x32/rank). FSM driven by TWO classes: "
               "issue-edge INTO -ing states, comparator OUT of -ing states.")

# ================= LEFT : reg arrays =================
def regbox(y, name, fields, writer, fill):
    f.rect(40, y, 360, 46 + len(fields) * 16, fill=fill, width=W_CELL)
    f.text(52, y + 22, name, size=12, mono=True, bold=True)
    for i, fl in enumerate(fields):
        f.text(52, y + 42 + i * 16, fl, size=9, mono=True)
    f.text(52, y + 42 + len(fields) * 16 - 2, writer, size=8, mono=False, fill=MUTED)

regbox(100, "BANK_STATUS  (FSM)",
       ["state[4]  open_row[17]", "valid  pre_pending  ref_pending"],
       "<- issue-edge + comparator + ME + propose", FILL_ACTIVE)
regbox(230, "BANK_TREG  (deadlines)",
       ["next_act  next_cas  next_pre  (13b ea)"],
       "<- issue-edge (3 adders: GC_ph+const)", FILL_CELL)
regbox(330, "BANK_CAN  (SR flops)",
       ["can_act  can_cas  can_pre"],
       "<- RESET=issue-edge   SET=comparator", FILL_NEW)
regbox(430, "BANK_REQ  (payload)",
       ["rob_index  col  op(R/W)  sram_addr"],
       "<- admit (lookahead/decode); read at CAS", FILL_LOGIC)

# ================= RIGHT : FSM =================
IDLE   = (900, 300)
ACTING = (1120, 170)
OPEN   = (1340, 300)
PREING = (1120, 440)
REFING = (900, 520)

state(*IDLE, "IDLE")
state(*ACTING, "ACTING", FILL_CELL)
state(*OPEN, "OPEN", FILL_ACTIVE)
state(*PREING, "PREING", FILL_CELL)
state(*REFING, "REFING", FILL_CELL)


def edge(p1, p2, col, label, lx, ly, curve=None):
    if curve:
        f.path(curve, arrow=True, stroke=col)
    else:
        f.line(p1[0], p1[1], p2[0], p2[1], arrow=True, stroke=col)
    f.text(lx, ly, label, size=9, mono=True, fill=col)


# IDLE -> ACTING (issue)
edge(IDLE, ACTING, ISSUE, "ACT issue", 940, 220,
     curve=f"M{IDLE[0]+40} {IDLE[1]-20} L{ACTING[0]-55} {ACTING[1]+18}")
# ACTING -> OPEN (cmp tRCD)
edge(ACTING, OPEN, CMP, "tRCD: GC>=next_cas", 1180, 218,
     curve=f"M{ACTING[0]+55} {ACTING[1]+18} L{OPEN[0]-55} {OPEN[1]-20}")
# OPEN self loop RD/WR (issue)
f.path(f"M{OPEN[0]+35} {OPEN[1]-18} C {OPEN[0]+120} {OPEN[1]-70}, "
       f"{OPEN[0]+120} {OPEN[1]+70}, {OPEN[0]+35} {OPEN[1]+18}",
       arrow=True, stroke=ISSUE)
f.text(OPEN[0] + 70, OPEN[1] - 40, "RD/WR issue", size=9, mono=True, fill=ISSUE)
# OPEN -> PREING (issue)
edge(OPEN, PREING, ISSUE, "PRE issue", 1230, 400,
     curve=f"M{OPEN[0]-55} {OPEN[1]+20} L{PREING[0]+55} {PREING[1]-18}")
# PREING -> IDLE (cmp tRP)
edge(PREING, IDLE, CMP, "tRP: GC>=next_act", 930, 400,
     curve=f"M{PREING[0]-55} {PREING[1]-8} L{IDLE[0]+45} {IDLE[1]+22}")
# IDLE -> REFING (issue)
edge(IDLE, REFING, ISSUE, "REF issue", 800, 410,
     curve=f"M{IDLE[0]-10} {IDLE[1]+23} L{REFING[0]+10} {REFING[1]-23}")
# REFING -> IDLE (cmp tRFC)
edge(REFING, IDLE, CMP, "tRFC", 905, 410,
     curve=f"M{REFING[0]+35} {REFING[1]-23} L{IDLE[0]+15} {IDLE[1]+23}")

# flag setters (dashed, into states)
f.path(f"M470 470 L{REFING[0]-60} {REFING[1]}", arrow=True, dashed=True, stroke=ME)
f.text(560, 560, "ME: set ref_pending", size=9, mono=True, fill=ME)
f.text(1120, 520, "propose: set pre_pending (drops can_cas early)",
       size=9, mono=True, fill=MUTED)

# ================= legend =================
ly = 700
for i, (col, lab) in enumerate([
        (ISSUE, "issue-edge (packer commit @{addr,cmd}) - INTO -ing states"),
        (CMP,   "timestamp comparator (GC>=next_*) - OUT of -ing states"),
        (ME,    "maintenance engine - sets ref_pending")]):
    f.line(60, ly + i * 22, 100, ly + i * 22, arrow=True, stroke=col)
    f.text(110, ly + i * 22 + 4, lab, size=10, mono=False, fill=col)

f.caption(40, 800,
          "TREG does double duty: its GE gates the can_* AND clocks the FSM out of transient "
          "states (next_cas=tRCD -> ACTING->OPEN, next_act=tRP -> PREING->IDLE, gate_rfc=tRFC -> "
          "REFING->IDLE). Issue writes the START of a transition; the comparator writes the DONE.")

f.save("fig_60_bank_model.svg")
print("wrote fig_60_bank_model.svg")
