from rtlfig import (Fig, MUTED, FILL_ACTIVE, FILL_NEW, FILL_CELL, FAINT, INK,
                    PAPER, W_CELL)

# fig_55 — single-rank max command combo per gear (1:1 / 1:2 / 1:4).
# Single-rank limits: <=1 CAS (dqFree), <=1 ACT (tRRD_S=8>4; 2 ACT needs 2 ranks),
# <=2 PRE (tPPD=2). So the richest single-rank bundle = 1 CAS + 1 ACT.

f = Fig(1120, 640)
CW = 46
FILLS = {"C": FILL_ACTIVE, "A": FILL_NEW, "P": FILL_CELL}


def strip(x, y, slots, straddle=False):
    for i, c in enumerate(slots):
        fill = FILLS.get(c, PAPER)
        stroke = FAINT if c == "-" else INK
        f.rect(x + i * CW, y, CW, CW, fill=fill, width=W_CELL, stroke=stroke)
        f.text(x + i * CW + CW / 2, y + CW / 2 + 6, c, size=17, anchor="middle",
               fill=(MUTED if c == "-" else INK))
    if straddle and len(slots) == 2:
        f.line(x + CW, y - 3, x + CW, y + CW + 3, dashed=True, stroke=FAINT)


f.text(40, 38, "Single-rank max command combo per gear", size=15, mono=False, bold=True)
f.note(40, 58, "Single-rank limits:  <=1 CAS (dqFree=8)  .  <=1 ACT (tRRD_S=8 > 4; two ACTs "
               "need TWO ranks)  .  <=2 PRE (tPPD=2).  So richest bundle = 1 CAS + 1 ACT.")
# legend
for sx, sc, sl in [(720, FILL_ACTIVE, "CAS"), (820, FILL_NEW, "ACT"), (920, FILL_CELL, "PRE")]:
    f.rect(sx, 30, 16, 16, fill=sc, width=W_CELL)
    f.text(sx + 22, 43, sl, size=11, mono=False)

# ---- 1:4 ----
f.text(40, 108, "gear 1:4  -  4 slots", size=13, mono=False, bold=True)
strip(60, 124, ["C", "C", "A", "A"])
f.text(280, 152, "MAX = 1 CAS + 1 ACT  (diff bank)  -  2 objects, all 4 phases",
       size=12, mono=False, bold=True)
# alts
strip(60, 210, ["C", "C", "P", "-"])
f.text(60, 288, "CAS + PRE filler", size=11, mono=False, anchor="start")
strip(320, 210, ["A", "A", "P", "-"])
f.text(320, 288, "ACT + PRE filler", size=11, mono=False, anchor="start")
strip(580, 210, ["P", "-", "P", "-"])
f.text(580, 288, "2 PRE @0,@2 (tPPD)", size=11, mono=False, anchor="start")

# ---- 1:2 ----
f.text(40, 340, "gear 1:2  -  2 slots", size=13, mono=False, bold=True)
strip(60, 356, ["C", "C"])
strip(220, 356, ["A", "A"])
strip(380, 356, ["P", "-"])
f.text(500, 384, "MAX = ONE 2-cyc object (CAS or ACT); or 1 PRE.  No CAS+ACT (needs 4 slots).",
       size=12, mono=False, bold=True)

# ---- 1:1 ----
f.text(40, 452, "gear 1:1  -  1 slot", size=13, mono=False, bold=True)
strip(60, 468, ["C", "C"], straddle=True)
f.text(200, 496, "MAX = 1 cmd/bundle.  A 2-cyc (CAS/ACT) STRADDLES 2 bundles; PRE = 1 bundle.",
       size=12, mono=False, bold=True)

f.caption(40, 600,
          "Per single rank: never 2 CAS (one DQ burst), never 2 ACT (tRRD_S=8 > the 4-CK "
          "window - a second ACT needs a SECOND rank, [A A A A] cross-rank). PRE is the only "
          "x2 (tPPD=2). 1:4 is the only gear that fits two objects (CAS+ACT); 1:2 fits one; "
          "1:1 streams one phase/bundle.")

f.save("fig_55_single_rank_combo.svg")
print("wrote fig_55_single_rank_combo.svg")
