from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_79 — RFM engine (Refresh Management, RAA-driven). Mirror of REFsb (fig_65) but
# ACT-triggered: per-bank RAA counter (++ACT / -=RAAIMT), RAAIMT->rfm_rdy,
# RAAMMT->rfm_force (gates can_act). RFMsb targets bank k across 8 BGs.

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1520, 900)


def state(cx, cy, name, fill=PAPER, w=120, h=44):
    f.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, width=1.6, rx=10)
    f.text(cx, cy + 5, name, size=12, anchor="middle", bold=True)


f.text(40, 32, "RFM engine  (RAA-driven, mirror of REFsb; anti-rowhammer)", size=15,
       mono=False, bold=True)

# ---- RAA counter + thresholds ----
f.block(40, 90, 250, 70, "RAA[bank]  (per bank)", "++ on ACT / -= RAAIMT on RFM")
f.text(48, 172, "~9-10b (holds RAAMMT); ACT grant 1-hot -> ++", size=8, mono=True, fill=MUTED)
f.text(48, 188, "REF also -= RAA (refresh mitigates too)", size=8, mono=True, fill=MUTED)

f.decision(360, 120, 130, 40, "")
f.text(360, 116, ">= RAAIMT", size=9, anchor="middle", bold=True)
f.text(360, 132, "(opportunistic)", size=7, anchor="middle", fill=MUTED)
f.line(290, 125, 295, 125, arrow=True)
f.line(425, 120, 500, 120, arrow=True, stroke=CMP)
f.text(510, 116, "rfm_rdy = |need", size=9, mono=True, fill=CMP)

f.decision(360, 200, 130, 40, "")
f.text(360, 196, ">= RAAMMT", size=9, anchor="middle", bold=True)
f.text(360, 212, "(hard cap)", size=7, anchor="middle", fill=MUTED)
f.line(425, 200, 500, 200, arrow=True, stroke=ME)
f.text(510, 196, "rfm_force -> gate_rfm", size=9, mono=True, fill=ME)
f.text(510, 214, "  (masks can_act[bank])", size=8, mono=False, fill=MUTED)

# ---- FSM (mirror REFsb) ----
IDLE = (560, 330); PICK = (760, 330); DRAIN = (960, 330)
ISS = (960, 470); RFMING = (760, 470); REL = (560, 470)
state(*IDLE, "IDLE")
state(*PICK, "PICK ba", FILL_CELL)
state(*DRAIN, "DRAIN", FILL_ACTIVE)
state(*ISS, "ISSUE", FILL_NEW)
state(*RFMING, "RFMING", FILL_CELL, w=130)
state(*REL, "release", FILL_CELL)


def edge(p1, p2, col, lab, curve):
    f.path(curve, arrow=True, stroke=col)
    mx = (p1[0] + p2[0]) / 2
    my = (p1[1] + p2[1]) / 2
    f.text(mx, my - 6, lab, size=8, mono=True, fill=col)


edge(IDLE, PICK, ISSUE, "rfm_rdy", f"M{IDLE[0]+60} {IDLE[1]} L{PICK[0]-60} {PICK[1]}")
edge(PICK, DRAIN, ISSUE, "gate_rfm[8]", f"M{PICK[0]+60} {PICK[1]} L{DRAIN[0]-60} {DRAIN[1]}")
edge(DRAIN, ISS, CMP, "8 idle", f"M{DRAIN[0]} {DRAIN[1]+22} L{ISS[0]} {ISS[1]-22}")
edge(ISS, RFMING, ISSUE, "RFMsb(ba)", f"M{ISS[0]-65} {ISS[1]} L{RFMING[0]+65} {RFMING[1]}")
edge(RFMING, REL, CMP, "GC>=tRFM", f"M{RFMING[0]-65} {RFMING[1]} L{REL[0]+60} {REL[1]}")
edge(REL, IDLE, ME, "RAA[8]-=RAAIMT", f"M{REL[0]} {REL[1]-22} L{IDLE[0]} {IDLE[1]+22}")

f.text(960, 400, "DRAIN: finish open-row CAS, PRE -> idle", size=8, mono=True, fill=MUTED)

# ---- OR-across-BG combine ----
CY = 600
f.text(40, 580, "need[bank] = (RAA >= RAAIMT).  RFMsb(ba=k) target = bank k across BG0..7:",
       size=10, mono=True)
for i in range(8):
    x = 60 + i * 30
    f.rect(x, CY, 24, 26, fill=FILL_CELL, width=W_CELL)
    f.text(x + 12, CY + 18, str(i), size=8, anchor="middle")
    f.line(x + 12, CY + 26, 420, 660, arrow=False, stroke=FAINT)
f.text(60, CY - 6, "need  BG0..7 (bank k)", size=8, fill=MUTED)
f.logic(400, 648, 110, 40, "8-OR", "", top=True)
f.line(510, 668, 590, 668, arrow=True)
f.text(596, 664, "rfm need for ba=k -> PICK", size=9, mono=True, fill=CMP)
f.text(40, 700, "(REFsb used 8-AND = all precharged; RFM uses 8-OR = any bank hammered -> manage that ba)",
       size=8, mono=False, fill=MUTED)

# ---- edge-case note ----
f.rect(880, 560, 600, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(900, 584, "EDGE CASE (last ACT hits RAAMMT)", size=11, bold=True)
ec = ["The ACT that reaches RAAMMT is LEGAL -> completes, opens row.",
      "Its open-row CAS train COMPLETES (RFM does not abort in-flight CAS).",
      "gate_rfm then blocks the NEXT ACT to that bank (can_act mask), not the CAS.",
      "flow: last ACT -> serve CAS -> PRE -> RFMsb  (before any new ACT to the bank).",
      "RFM = distinct command (own opcode/tRFM); same target+drain as REFsb."]
for i, s in enumerate(ec):
    f.text(900, 606 + i * 20, "- " + s, size=9, mono=False)

f.caption(40, 780,
          "RFM mirrors REFsb, ACT-driven: per-bank RAA (++ACT, -=RAAIMT/RFM, REF also -=). RAAIMT -> "
          "rfm_rdy (opportunistic); RAAMMT -> rfm_force -> gate_rfm masks can_act (blocks NEXT ACT). "
          "8-OR across BGs picks ba; drain -> RFMsb(ba) -> RFMING(tRFM) -> RAA[8]-=RAAIMT.")

f.save("fig_79_rfm_engine.svg")
print("wrote fig_79_rfm_engine.svg")
