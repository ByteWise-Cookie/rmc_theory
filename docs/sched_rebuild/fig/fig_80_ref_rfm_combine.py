from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_80 — combined REF + RFM maintenance drain. Two triggers (debt / RAA), shared
# drain + target select, REFsb-first priority, recheck-skip, cross-credited counters.

REFC = "#2a8f86"; RFMC = "#b0602a"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"
f = Fig(1560, 940)


def state(cx, cy, name, fill=PAPER, w=126, h=44):
    f.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, width=1.6, rx=10)
    f.text(cx, cy + 5, name, size=11, anchor="middle", bold=True)


f.text(40, 30, "Combined REF + RFM maintenance drain  (shared drain, REFsb-first)",
       size=15, mono=False, bold=True)

# ---- triggers (left) ----
f.block(40, 80, 250, 66, "REFRESH trigger", "per-bank debt (tREFI)")
f.text(52, 158, "ref_rdy=|debt  ref_force=&debt", size=8, mono=True, fill=REFC)
f.block(40, 200, 250, 66, "RFM trigger", "per-bank RAA (ACT)")
f.text(52, 278, "rfm_rdy=RAA>=RAAIMT", size=8, mono=True, fill=RFMC)
f.text(52, 292, "rfm_force=RAA>=RAAMMT", size=8, mono=True, fill=RFMC)

# ---- priority ----
f.logic(330, 150, 170, 90, "PRIORITY", "both? -> REFsb first", top=True)
f.line(290, 130, 328, 175, arrow=True, stroke=REFC)
f.line(290, 233, 328, 210, arrow=True, stroke=RFMC)
f.text(340, 250, "cmd_type = REF | RFM", size=8, mono=True, fill=ISSUE)

# ---- shared drain / target select ----
f.block(330, 300, 230, 70, "PICK ba + DRAIN", "1 maint_pending -> freeze+drain")
f.text(342, 388, "ba: REF=8-AND ready . RFM=8-OR need", size=8, mono=True, fill=MUTED)
f.text(342, 404, "drain = finish CAS + PRE (shared for both)", size=8, mono=True, fill=MUTED)

# ---- FSM ----
IDLE = (720, 150); PICK = (720, 300); DRAIN = (960, 300)
ISS = (960, 470); GATE = (720, 470); RECK = (720, 620)
state(*IDLE, "IDLE")
state(*PICK, "PICK/DRAIN", FILL_CELL, w=140)
state(*DRAIN, "8 idle?", FILL_ACTIVE)
state(*ISS, "ISSUE cmd_type", FILL_NEW, w=150)
state(*GATE, "GATE (REFING/RFMING)", FILL_CELL, w=180)
state(*RECK, "RECHECK", FILL_LOGIC)


def edge(p1, p2, col, lab, curve):
    f.path(curve, arrow=True, stroke=col)
    f.text((p1[0]+p2[0])/2, (p1[1]+p2[1])/2 - 6, lab, size=8, mono=True, fill=col)


edge(IDLE, PICK, ISSUE, "rdy/force", f"M{IDLE[0]} {IDLE[1]+22} L{PICK[0]} {PICK[1]-22}")
edge(PICK, DRAIN, ISSUE, "", f"M{PICK[0]+70} {PICK[1]} L{DRAIN[0]-58} {DRAIN[1]}")
edge(DRAIN, ISS, REFC, "drained", f"M{DRAIN[0]} {DRAIN[1]+22} L{ISS[0]} {ISS[1]-22}")
edge(ISS, GATE, ISSUE, "REFsb|RFMsb", f"M{ISS[0]-75} {ISS[1]} L{GATE[0]+90} {GATE[1]}")
edge(GATE, RECK, REFC, "GC>=tRFC/tRFM", f"M{GATE[0]} {GATE[1]+22} L{RECK[0]} {RECK[1]-22}")

# recheck outcomes
f.line(658, 620, 500, 620, arrow=True, stroke=GREEN)
f.text(505, 616, "RAA<RAAMMT -> DONE (RFM skipped)", size=8, mono=True, fill=GREEN)
f.path(f"M{RECK[0]+63} {RECK[1]} H1120 V470 H{ISS[0]+75}", arrow=True, stroke=RFMC)
f.text(1000, 600, "RAA>=RAAMMT -> RFM (back-to-back, still drained)", size=8, mono=True, fill=RFMC)
f.path(f"M{RECK[0]} {RECK[1]+22} V700 H{IDLE[0]-300} V150 H{IDLE[0]-63}", arrow=True,
       dashed=True, stroke=MUTED)
f.text(430, 700, "loop -> IDLE", size=8, mono=True, fill=MUTED)

# ---- counter update / gate table ----
f.rect(40, 720, 1480, 120, fill=PAPER, width=1.4, stroke=INK)
f.text(60, 744, "ISSUE effects (cross-credited):", size=11, bold=True)
f.text(60, 768, "REFsb : cmd=REF ; gate_rfc (+tRFCsb) ; debt[8] <= 0  AND  RAA[8] -= REF_amt   "
       "(full refresh: retention + mitigation -> can clear BOTH)", size=9, mono=True, fill=REFC)
f.text(60, 788, "RFMsb : cmd=RFM ; gate_rfm (+tRFM=tRFCsb) ; RAA[8] -= RAAIMT   (targeted "
       "mitigation only; does NOT reset debt)", size=9, mono=True, fill=RFMC)
f.text(60, 810, "REFsb-first when both pending: same duration (tRFM=tRFC), superset effect -> "
       "recheck RAA after; issue RFM only if still >= RAAMMT (usually skipped).", size=9,
       mono=False)

f.caption(40, 900,
          "One drain serves both (same 8 banks, both need precharge). PRIORITY = REFsb-first "
          "(superset, same tRFC time). RECHECK after the gate: RAA<RAAMMT -> done (RFM skipped); "
          "else back-to-back RFMsb on the still-drained banks. REF also -=RAA -> RFM rarely fires.")

f.save("fig_80_ref_rfm_combine.svg")
print("wrote fig_80_ref_rfm_combine.svg")
