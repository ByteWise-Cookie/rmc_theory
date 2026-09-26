from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_81 — full BANK FSM (walk-confirmed). 6 states, edges tagged by trigger + the
# can-reset/timestamp-set (issue-edge) or comparator (out of -ing). Writer classes
# colored. + stall_acts drain-entry. No R/W state (direction = CAS attribute).

ISS = "#7a4fb0"   # issue-edge (into -ing / serve)
CMP = "#2a8f86"   # comparator (can toggle / gate release, out of -ing)
ME  = "#b0602a"   # maintenance engine

f = Fig(1580, 1060)


def st(cx, cy, name, fill=PAPER, w=120, h=46):
    f.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, width=1.8, rx=11)
    f.text(cx, cy + 5, name, size=12, anchor="middle", bold=True)


f.text(40, 30, "BANK FSM  (6 states; direction is a CAS attribute, not a state)", size=15,
       mono=False, bold=True)

IDLE = (330, 360); ACTING = (600, 170); OPEN = (660, 430)
PREING = (400, 640); REFING = (980, 250); RFMING = (980, 470)
st(*IDLE, "IDLE")
st(*ACTING, "ACTING", FILL_CELL)
st(*OPEN, "OPEN", FILL_ACTIVE)
st(*PREING, "PREING", FILL_CELL)
st(*REFING, "REFING", FILL_LOGIC)
st(*RFMING, "RFMING", FILL_LOGIC)


def edge(p1, p2, col, lab, lx, ly, curve=None, o1=(0, 0), o2=(0, 0)):
    if curve:
        f.path(curve, arrow=True, stroke=col)
    else:
        f.line(p1[0] + o1[0], p1[1] + o1[1], p2[0] + o2[0], p2[1] + o2[1],
               arrow=True, stroke=col)
    f.text(lx, ly, lab, size=8, mono=True, fill=col)


# 1 IDLE->ACTING (ACT issue)
edge(IDLE, ACTING, ISS, "1 ACT issue", 400, 240,
     curve=f"M{IDLE[0]+45} {IDLE[1]-22} L{ACTING[0]-55} {ACTING[1]+18}")
# 2 ACTING->OPEN (can_cas @tRCD)
edge(ACTING, OPEN, CMP, "2 can_cas@tRCD", 640, 300,
     curve=f"M{ACTING[0]+40} {ACTING[1]+20} L{OPEN[0]-30} {OPEN[1]-25}")
# 3 OPEN self (CAS hit)
f.path(f"M{OPEN[0]+55} {OPEN[1]-16} C {OPEN[0]+150} {OPEN[1]-70}, "
       f"{OPEN[0]+150} {OPEN[1]+60}, {OPEN[0]+55} {OPEN[1]+16}", arrow=True, stroke=ISS)
f.text(OPEN[0] + 95, OPEN[1] - 45, "3 CAS(hit)", size=8, mono=True, fill=ISS)
# 4 OPEN->PREING (PRE miss)
edge(OPEN, PREING, ISS, "4 PRE(miss)", 490, 560,
     curve=f"M{OPEN[0]-45} {OPEN[1]+20} L{PREING[0]+50} {PREING[1]-22}")
# 5 OPEN->IDLE (RDA/WRA ap)
edge(OPEN, IDLE, ISS, "5 RDA/WRA(ap)", 430, 400,
     curve=f"M{OPEN[0]-55} {OPEN[1]-8} L{IDLE[0]+50} {IDLE[1]+10}")
# 6 PREING->IDLE (can_act @tRP)
edge(PREING, IDLE, CMP, "6 can_act@tRP", 300, 520,
     curve=f"M{PREING[0]-40} {PREING[1]-18} L{IDLE[0]-10} {IDLE[1]+24}")
# 7 IDLE->REFING
edge(IDLE, REFING, ME, "7 REFsb", 760, 300,
     curve=f"M{IDLE[0]+55} {IDLE[1]-25} L{REFING[0]-62} {REFING[1]+6}")
# 8 REFING->IDLE
edge(REFING, IDLE, CMP, "8 gate_rfc@tRFCsb", 610, 360,
     curve=f"M{REFING[0]-62} {REFING[1]+18} L{IDLE[0]+58} {IDLE[1]-10}")
# 9 IDLE->RFMING
edge(IDLE, RFMING, ME, "9 RFMsb", 770, 520,
     curve=f"M{IDLE[0]+40} {IDLE[1]+28} L{RFMING[0]-62} {RFMING[1]+2}")
# 10 RFMING->IDLE
edge(RFMING, IDLE, CMP, "10 gate_rfm@tRFM", 790, 560,
     curve=f"M{RFMING[0]-62} {RFMING[1]+18} L{IDLE[0]+55} {IDLE[1]+30}")

# ---- edge actions table ----
ay = 720
f.text(40, ay, "edge actions  (issue-edge = RESET can + SET timestamp; comparator = advance only):",
       size=11, mono=False, bold=True)
rows = [
    ("1 IDLE->ACTING", "RST can_act/cas/pre; SET next_act=tRC, next_cas=tRCD, next_pre=tRAS; latch open_row (+BG tRRD_L, rank tRRD_S+faw)", ISS),
    ("3 OPEN->OPEN", "RST can_pre(RD:tRTP|WR:WR_TAIL), can_cas_bgs(tCCD_L); SET turn(next_rd/wr), dqFree(+BL/2), last_cas_dir; pop-on-CAS", ISS),
    ("4 OPEN->PREING", "RST can_act(tRP), can_cas; SET rank next_pre(tPPD); valid<=0", ISS),
    ("5 OPEN->IDLE", "RDA/WRA auto-PRE (last CAS ap=1); RST can_act(tRP), can_cas; valid<=0  [PREsb-merge, no explicit PRE]", ISS),
    ("7 IDLE->REFING", "gate_rfc=GC+tRFCsb (broadcast 8 targets); mask can_act/cas/pre; ME resets debt", ME),
    ("9 IDLE->RFMING", "gate_rfm=GC+tRFM; ME RAA-=RAAIMT", ME),
    ("2/6/8/10 (out of -ing)", "comparator SET only: can_cas->OPEN ; can_act->IDLE ; gate release->IDLE. No writeback.", CMP),
]
yy = ay + 20
for nm, act, col in rows:
    f.text(52, yy + 12, nm, size=9, mono=True, fill=col, bold=True)
    f.text(290, yy + 12, act, size=8.5, mono=True, fill=INK)
    yy += 20

# ---- stall_acts drain-entry ----
dy = ay + 175
f.rect(40, dy, 720, 90, fill=PAPER, width=1.2, stroke=INK)
f.text(54, dy + 18, "stall_acts drain-entry (non-IDLE -> IDLE before REF/RFM):", size=10, bold=True)
f.text(54, dy + 38, "OPEN -> AP-drain(last CAS ap=1) -> IDLE   .   ACTING -> wait tRAS -> AP/PRE -> IDLE",
       size=9, mono=True)
f.text(54, dy + 56, "PREING -> IDLE (PRE merges)   .   REFING/RFMING -> skip (busy)", size=9, mono=True)
f.text(54, dy + 76, "cas_complete=(state==IDLE) ; bank_busy=!(IDLE)", size=9, mono=True, fill=MUTED)

# ---- legend ----
ly = dy + 4
lx = 800
f.text(lx, ly + 14, "writer classes:", size=10, bold=True)
for i, (c, t) in enumerate([(ISS, "issue-edge (grant) -> into -ing / serve; RESET can + SET ts"),
                            (CMP, "comparator (can toggle / gate release) -> out of -ing"),
                            (ME, "maint engine -> REFsb/RFMsb issue + gate_rfc/rfm")]):
    f.line(lx, ly + 32 + i * 20, lx + 34, ly + 32 + i * 20, arrow=True, stroke=c)
    f.text(lx + 42, ly + 36 + i * 20, t, size=9, mono=False, fill=c)
f.text(lx, ly + 96, "in: grant_act/cas/pre, REFsb/RFMsb, stall_acts, GC", size=9, mono=True, fill=MUTED)
f.text(lx, ly + 112, "out: state[3], cas_complete, bank_busy, gate_rfc/rfm, open_row(OPEN)",
       size=9, mono=True, fill=MUTED)

f.caption(40, 1035,
          "issue-edge -> INTO -ing (RESET can + SET ts); comparator (can toggle / gate release) "
          "-> OUT of -ing. OPEN serves CAS in place. AP (RDA/WRA) folds precharge into last CAS. "
          "REF/RFM from IDLE after stall_acts drain. No read/write state.")

f.save("fig_81_bank_fsm_full.svg")
print("wrote fig_81_bank_fsm_full.svg")
