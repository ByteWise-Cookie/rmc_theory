from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_65 — REFsb engine: interval->debt, target RR, drain handshake, 8-AND ready
# combine, gate_rfc writeback. REFsb(ba=k) = bank k across all 8 BGs (8 banks).

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"

f = Fig(1500, 900)


def state(cx, cy, name, fill=PAPER, w=120, h=44):
    f.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, width=1.6, rx=10)
    f.text(cx, cy + 5, name, size=12, anchor="middle", bold=True)


f.text(40, 32, "REFsb engine  (bank k across all 8 BGs = 8 banks)", size=15,
       mono=False, bold=True)

# ---------- left: interval + debt ----------
f.block(40, 90, 220, 60, "tREFI down-counter", "expire -> debt++  (>>rr_shift, temp)")
f.counter(120, 240, 36, "debt", "0..8 sat")
f.line(150, 150, 150, 208, arrow=True)
f.text(158, 185, "debt++", size=8, mono=True, fill=MUTED)
f.text(200, 220, "debt>=7 -> force", size=9, mono=True, fill=ME)
f.text(200, 238, "debt>0 & idle -> opp", size=9, mono=True, fill=MUTED)

# target rotation
f.block(40, 320, 220, 60, "target RR", "ba 0->3 , rank_sel")
f.line(120, 276, 120, 318, arrow=True)
f.text(128, 300, "trigger", size=8, mono=True, fill=MUTED)
f.text(48, 400, "target = {rank, bank ba, BG0..7}", size=9, mono=True, fill=INK)

# ---------- FSM ----------
IDLE = (500, 180); PICK = (720, 180); DRAIN = (940, 180)
ISS = (940, 360); REFING = (720, 360); REL = (500, 360)
state(*IDLE, "IDLE")
state(*PICK, "PICK", FILL_CELL)
state(*DRAIN, "DRAIN", FILL_ACTIVE)
state(*ISS, "ISSUE", FILL_NEW)
state(*REFING, "REFING", FILL_CELL)
state(*REL, "release", FILL_CELL)


def edge(p1, p2, col, lab, lx, ly, curve=None):
    f.path(curve, arrow=True, stroke=col) if curve else \
        f.line(p1[0], p1[1], p2[0], p2[1], arrow=True, stroke=col)
    f.text(lx, ly, lab, size=8, mono=True, fill=col)


edge(IDLE, PICK, ISSUE, "debt>0", 585, 168,
     f"M{IDLE[0]+60} {IDLE[1]} L{PICK[0]-60} {PICK[1]}")
edge(PICK, DRAIN, ISSUE, "set REF_pending[8]", 770, 168,
     f"M{PICK[0]+60} {PICK[1]} L{DRAIN[0]-60} {DRAIN[1]}")
edge(DRAIN, ISS, CMP, "refsb_ready (8-AND)", 955, 270,
     f"M{DRAIN[0]} {DRAIN[1]+22} L{ISS[0]} {ISS[1]-22}")
edge(ISS, REFING, ISSUE, "REFsb(ba)", 775, 350,
     f"M{ISS[0]-60} {ISS[1]} L{REFING[0]+60} {REFING[1]}")
edge(REFING, REL, CMP, "GC>=gate_rfc (tRFCsb)", 545, 350,
     f"M{REFING[0]-60} {REFING[1]} L{REL[0]+60} {REL[1]}")
edge(REL, IDLE, ME, "debt--, ba++", 470, 270,
     f"M{REL[0]} {REL[1]-22} L{IDLE[0]} {IDLE[1]+22}")

# ---------- drain: freeze + policy B ----------
f.text(940, 240, "DRAIN: freeze admit (row_valid=0),", size=8, mono=True, fill=MUTED)
f.text(940, 254, "finish hit-train (policy B), PRE -> IDLE", size=8, mono=True, fill=MUTED)

# ---------- ready combine (8-AND) ----------
CY = 560
f.text(500, 540, "ref_rdy[b] = (state==IDLE)   for bank k in BG0..7", size=9,
       mono=True, fill=INK)
for i in range(8):
    x = 470 + i * 34
    f.rect(x, CY, 26, 30, fill=FILL_CELL, width=W_CELL)
    f.text(x + 13, CY + 20, str(i), size=9, anchor="middle")
    f.line(x + 13, CY + 30, 780, 640, arrow=False, stroke=FAINT)
f.text(470, CY - 8, "ref_rdy  BG0..7 (bank k)", size=8, mono=False, fill=MUTED)
f.logic(760, 630, 120, 44, "8-AND", "", top=True)
f.line(880, 652, 960, 652, arrow=True)
f.text(966, 648, "refsb_ready[k]", size=9, mono=True, fill=CMP)
f.text(966, 668, "-> DRAIN done -> ISSUE", size=8, mono=False, fill=MUTED)

# ---------- writeback to scoreboard ----------
f.rect(1080, 560, 360, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(1260, 584, "writeback (8 target banks)", size=11, anchor="middle", bold=True)
f.text(1096, 612, "REF_pending[8] <- 1   (freeze admit)", size=9, mono=True)
f.text(1096, 632, "state[8] -> REFING", size=9, mono=True)
f.text(1096, 652, "gate_rfc[8] = GC + tRFCsb (312)", size=9, mono=True)
f.text(1096, 672, "release: GC>=gate_rfc -> IDLE, debt--", size=9, mono=True)
f.text(1096, 692, "ref_rdy FLAG -> scheduler (override inject)", size=9, mono=True, fill=ISSUE)

# ---------- notes ----------
f.text(40, 760, "REFsb(ba=k) targets bank k in ALL 8 BGs = 8 banks (diff-BG = drain-optimal, "
        "tCCD_S). refsb_ready = AND of 8 (not OR - all must be precharged).", size=9,
        mono=False, fill=MUTED)
f.text(40, 780, "Trigger: opportunistic (8 idle & debt>0) or forced (debt>=7). Drain budget "
        "~406 CK << tREFI 9360 (or 4680 at 2x temp). ME emits ref_rdy; scheduler ranks with demand.",
        size=9, mono=False, fill=MUTED)

f.caption(40, 872,
          "REFsb: tREFI->debt (temp-scaled); pick ba (RR) -> set REF_pending on the 8 target banks "
          "-> freeze admit + policy-B drain -> 8-AND ref_rdy = refsb_ready -> REFsb issue (gate_rfc[8] "
          "= GC+tRFCsb) -> release at GC>=gate_rfc, debt--, ba++. ME flag override-injects at the phaser.")

f.save("fig_65_refsb_engine.svg")
print("wrote fig_65_refsb_engine.svg")
