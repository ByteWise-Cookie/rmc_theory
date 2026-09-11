from rtlfig import (Fig, MUTED, FILL_ACTIVE, FILL_NEW, FILL_CELL,
                    FILL_LOGIC, FAINT, INK, PAPER, W_CELL)

# fig_27 — every DDR5 command: phase width, scope, co-issue, across all gears.
# Companion to fig_26 (CAS/ACT/PRE core packs).
# Invariant: most maintenance/config cmds are rank-exclusive (solo bundle);
# co-issue/filler is a 1:4 luxury — at 1:2 a 2-phase cmd fills both slots,
# at 1:1 it straddles 2 bundles (one object per bundle).

f = Fig(1120, 1030)
CW = 28
RED = "#c0392b"
FILLS = {"C": FILL_ACTIVE, "A": FILL_NEW, "P": FILL_CELL, "R": FILL_CELL,
         "M": FILL_LOGIC, "Z": FILL_LOGIC}
X14, X12, X11 = 765, 905, 990


def draw_strip(x, y, slots, border=False, straddle=False):
    for i, c in enumerate(slots):
        fill = FILLS.get(c, PAPER)
        stroke = FAINT if c == "-" else INK
        f.rect(x + i * CW, y, CW, CW, fill=fill, stroke=stroke, width=W_CELL)
        f.text(x + i * CW + CW / 2, y + CW / 2 + 5, c, size=12,
               anchor="middle", fill=(MUTED if c == "-" else INK))
    if straddle and len(slots) == 2:
        f.line(x + CW, y - 3, x + CW, y + CW + 3, dashed=True, stroke=FAINT)
    if border:
        f.rect(x - 3, y - 3, len(slots) * CW + 6, CW + 6, stroke=MUTED, width=1.3)


# ---------------- header ----------------
f.text(40, 38, "Every DDR5 command - phase width, scope, co-issue, per gear",
       size=15, mono=False, bold=True)
f.note(40, 58, "Extends fig_26.  C=CAS  A=ACT  P=PRE  R=REF  M=MRW/MRR  Z=ZQ  "
               "- =NOP.   grey border = solo (rank-exclusive).   1:1 dashed = "
               "straddles 2 bundles.")

hy = 100
f.text(55, hy, "COMMAND", size=12, mono=False, bold=True)
f.text(250, hy, "phases", size=12, mono=False, bold=True)
f.text(318, hy, "scope", size=12, mono=False, bold=True)
f.text(490, hy, "co-issue (1:4)", size=12, mono=False, bold=True)
f.text(X14, hy - 14, "example bundle", size=11, mono=False, bold=True)
f.text(X14 + 40, hy, "1:4", size=11, mono=False, bold=True, anchor="middle")
f.text(X12 + 28, hy, "1:2", size=11, mono=False, bold=True, anchor="middle")
f.text(X11 + 28, hy, "1:1", size=11, mono=False, bold=True, anchor="middle")
f.line(40, 110, 1090, 110, stroke=FAINT)

# name, phases, scope, coissue, s14, s12, s11, marker
ROWS = [
    ("group", "DATA - DQ burst  (<=1 DQ-op / bundle, one shared burst)"),
    ("RD / RDA", "2", "bank", "yes: + ACT/PRE diff-bank",
     ["C", "C", "A", "A"], ["C", "C"], ["C", "C"], None),
    ("WR / WRA / MWR", "2", "bank", "yes: + PRE filler",
     ["C", "C", "P", "-"], ["C", "C"], ["C", "C"], None),
    ("MRR", "2", "device (DQ)", "NO - DQ + device",
     ["M", "M", "-", "-"], ["M", "M"], ["M", "M"], "solo"),
    ("group", "ROW / PRECHARGE"),
    ("ACT", "2", "bank", "yes: + CAS diff-bank",
     ["A", "A", "C", "C"], ["A", "A"], ["A", "A"], None),
    ("PRE", "1", "bank", "filler: other bank",
     ["C", "C", "P", "-"], ["P", "-"], ["P"], None),
    ("PREsb", "1", "bank in all BG (8)", "partial: non-target bank",
     ["P", "-", "C", "C"], ["P", "-"], ["P"], None),
    ("PREab", "1", "rank (all banks)", "NO - solo",
     ["P", "-", "-", "-"], ["P", "-"], ["P"], "solo"),
    ("group", "REFRESH"),
    ("REFsb", "1", "bank in all BG (8)", "partial: 24 banks feed DQ",
     ["R", "-", "C", "C"], ["R", "-"], ["R"], None),
    ("REFab", "1", "rank (all banks)", "NO - solo",
     ["R", "-", "-", "-"], ["R", "-"], ["R"], "solo"),
    ("RFMsb / RFMab", "1", "BG / rank", "partial / solo",
     ["R", "-", "-", "-"], ["R", "-"], ["R"], "solo"),
    ("group", "MODE . CAL . POWER  - device/rank state"),
    ("MRW", "2", "device", "NO - solo",
     ["M", "M", "-", "-"], ["M", "M"], ["M", "M"], "solo"),
    ("ZQCAL (ZQCL/ZQCS)", "1", "rank / channel", "NO - solo",
     ["Z", "-", "-", "-"], ["Z", "-"], ["Z"], "solo"),
    ("MPC / SRE.SRX / PDE.PDX", "1-2", "rank / device", "NO - state change",
     ["-", "-", "-", "-"], ["-", "-"], ["-"], "idle"),
]

y = 132
for row in ROWS:
    if row[0] == "group":
        f.text(48, y + 4, row[1], size=12, mono=False, bold=True, fill=MUTED)
        f.line(40, y + 12, 1090, y + 12, stroke=FAINT)
        y += 34
        continue
    name, ph, scope, coi, s14, s12, s11, mk = row
    solo = (mk == "solo")
    f.text(55, y + CW / 2 + 4, name, size=12)
    f.text(258, y + CW / 2 + 4, ph, size=12, mono=False)
    f.text(318, y + CW / 2 + 4, scope, size=11, mono=False, fill=MUTED)
    f.text(490, y + CW / 2 + 4, coi, size=11, mono=False,
           fill=(RED if coi.startswith("NO") else INK))
    draw_strip(X14, y, s14, border=solo)
    draw_strip(X12, y, s12, border=solo)
    draw_strip(X11, y, s11, border=solo, straddle=True)
    y += 40

# ---------------- takeaways ----------------
ty = y + 14
f.line(40, ty - 6, 1090, ty - 6, stroke=FAINT)
f.text(48, ty + 12, "read-out", size=12, mono=False, bold=True)
f.note(48, ty + 34, "Co-issue is a 1:4 LUXURY: at 1:2 a 2-phase cmd fills both slots (no filler); at 1:1 it straddles 2 bundles. One object per bundle at 1:2 / 1:1.")
f.note(48, ty + 54, "DQ rule: RD / WR / MRR share ONE burst -> <=1 DQ-op per bundle; MRR blocks a CAS.")
f.note(48, ty + 74, "Rank-exclusive (REFab, PREab, MRW, MRR, ZQ, RFMab, SR/PD) = SOLO bundle at every gear -> gate whole rank.")
f.note(48, ty + 94, "Same-bank-scope (REFsb, PREsb, RFMsb) co-issue a CAS only at 1:4; at 1:2/1:1 they still spare the rank across adjacent bundles (stage 9).")

f.caption(40, ty + 126,
          "Filler/co-issue exists only at 1:4 (4 slots); 1:2 fits one 2-phase "
          "object, 1:1 streams one phase/clk with 2-cyc cmds straddling. "
          "Rank-exclusive maintenance is solo at every gear.")

f.save("fig_27_all_cmd_packing.svg")
print("wrote fig_27_all_cmd_packing.svg")
