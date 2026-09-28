from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_67 — REFab (all-bank) engine + REFsb/REFab selector. Shared debt/interval
# (fig_65/66) feeds both. REFab = whole rank (32 banks), tRFC1, no ba/8-AND.

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1440, 820)


def state(cx, cy, name, fill=PAPER, w=120, h=44):
    f.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, width=1.6, rx=10)
    f.text(cx, cy + 5, name, size=12, anchor="middle", bold=True)


f.text(40, 32, "REFab engine (all-bank, 32 banks) + REFsb/REFab selector", size=15,
       mono=False, bold=True)

# ---------- shared debt in ----------
f.counter(110, 150, 36, "debt", "shared")
f.text(60, 205, "from interval engine (fig_66)", size=8, mono=False, fill=MUTED)
f.line(146, 150, 300, 150, arrow=True)
f.text(190, 138, "debt>0", size=9, mono=True, fill=MUTED)

# ---------- selector ----------
f.decision(360, 150, 150, 60, "")
f.text(360, 146, "all 32 idle?", size=10, anchor="middle", bold=True)
f.text(360, 162, "(precharged)", size=8, anchor="middle", fill=MUTED)
f.line(435, 150, 560, 150, arrow=True, stroke=CMP)
f.text(490, 138, "YES", size=9, mono=True, fill=CMP)
f.line(360, 210, 360, 300, arrow=True, stroke=ISSUE)
f.text(368, 260, "NO -> REFsb (fig_65)", size=9, mono=True, fill=ISSUE)
f.text(230, 320, "targeted 8 + drain", size=8, mono=True, fill=MUTED)

# ---------- REFab FSM ----------
ISS = (660, 150); REFING = (900, 150); REL = (1140, 150)
state(*ISS, "ISSUE", FILL_NEW)
state(*REFING, "REFING", FILL_CELL, w=140)
state(*REL, "release", FILL_CELL)
f.line(ISS[0] + 60, 150, REFING[0] - 70, 150, arrow=True, stroke=ISSUE)
f.text(760, 138, "REFab", size=9, mono=True, fill=ISSUE)
f.line(REFING[0] + 70, 150, REL[0] - 60, 150, arrow=True, stroke=CMP)
f.text(1035, 138, "GC>=gate_rfc", size=8, mono=True, fill=CMP)
f.text(900, 190, "all 32 banks REFING (tRFC1=708)", size=8, mono=True, fill=MUTED)
# release -> debt--
f.path(f"M{REL[0]} 172 V240 H110 V190", arrow=True, dashed=True, stroke=ME)
f.text(600, 250, "debt--", size=9, mono=True, fill=ME)

# ---------- writeback ----------
f.rect(560, 340, 400, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(760, 364, "REFab writeback (whole rank)", size=11, anchor="middle", bold=True)
f.text(576, 392, "no drain (rank already idle -> no CAS to finish)", size=9, mono=True)
f.text(576, 412, "state[32] -> REFING", size=9, mono=True)
f.text(576, 432, "gate_rfc[32] = GC + tRFC1 (708)", size=9, mono=True)
f.text(576, 452, "release: GC>=gate_rfc -> IDLE[32], debt--", size=9, mono=True)
f.text(576, 472, "ref_rdy FLAG -> scheduler (override inject)", size=9, mono=True, fill=ISSUE)

# ---------- REFsb vs REFab compare ----------
f.rect(60, 540, 620, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(370, 564, "REFsb  vs  REFab", size=11, anchor="middle", bold=True)
rows = [
    ("target", "bank k x 8 BG = 8 banks", "all 32 banks"),
    ("tRFC", "tRFCsb = 312", "tRFC1 = 708"),
    ("others", "24 banks keep feeding DQ", "whole rank blocked"),
    ("drain", "yes (policy B)", "none (already idle)"),
    ("use when", "under load (default)", "rank idle (free opportunity)"),
]
f.text(80, 590, "", size=9)
for i, (a, b, c) in enumerate(rows):
    y = 588 + i * 19
    f.text(80, y, a, size=9, mono=True, fill=MUTED)
    f.text(210, y, b, size=9, mono=True)
    f.text(460, y, c, size=9, mono=True)

# ---------- DDR portability ----------
f.rect(720, 540, 680, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(1060, 564, "DDR portability", size=11, anchor="middle", bold=True)
dd = ["DDR1/2/3 : all-bank REF only = REFab-equivalent. NO selector,",
      "           NO REFsb, NO ba/8-AND. Engine = this panel alone.",
      "DDR4     : all-bank REF + FGR (1x/2x/4x -> tRFC1/tRFC2/tRFC4).",
      "           Still no REFsb.",
      "DDR5     : REFsb primary (fig_65) + REFab fallback (this). Selector",
      "           picks by all-rank-idle. + RFM."]
for i, s in enumerate(dd):
    f.text(736, 590 + i * 18, s, size=9, mono=True)

f.caption(40, 780,
          "REFab = one command refreshes all 32 banks (tRFC1=708), no drain needed because it fires "
          "only when the whole rank is ALREADY idle (free - nothing running to stall). Under load, "
          "REFsb is preferred (8 banks, 24 keep feeding DQ). Shared debt/interval feeds both; the "
          "selector routes by all-rank-idle. DDR1-4 have only the all-bank flavor (this panel).")

f.save("fig_67_refab_engine.svg")
print("wrote fig_67_refab_engine.svg")
