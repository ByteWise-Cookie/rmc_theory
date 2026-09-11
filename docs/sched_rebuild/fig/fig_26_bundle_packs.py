from rtlfig import (Fig, MUTED, FILL_ACTIVE, FILL_NEW, FILL_CELL,
                    FAINT, INK, PAPER, W_CELL)

# fig_26 — DFI phase-packer bundle: legal command packs per gear ratio.
# Invariant: bundle width = gear (phases). Co-issue only when 2 different-bank
# objects fit AND every pair spacing <= window. >=2 CAS never (DQ). 2nd ACT
# only cross-rank. PRE x2 only at tPPD=2 gap.

f = Fig(1180, 820)
RED = "#c0392b"
CW = 44

FILLS = {"C": FILL_ACTIVE, "A": FILL_NEW, "P": FILL_CELL, "R": FILL_CELL}


def bundle(x, y, slots, illegal=False):
    for i, c in enumerate(slots):
        fill = FILLS.get(c, PAPER)
        stroke = FAINT if c == "-" else INK
        f.rect(x + i * CW, y, CW, CW, fill=fill, stroke=stroke, width=W_CELL)
        f.text(x + i * CW + CW / 2, y + CW / 2 + 7, c, size=18,
               anchor="middle", fill=(MUTED if c == "-" else INK))
    if illegal:
        f.rect(x - 4, y - 4, len(slots) * CW + 8, CW + 8,
               stroke=RED, width=1.6, dashed=True)


def tag(x, y, name, sub, bad=False):
    f.text(x, y + 16, name, size=12, mono=False, bold=True,
           fill=(RED if bad else INK))
    f.note(x, y + 34, sub)


# ---------------- header + legend ----------------
f.text(40, 40, "DFI phase-packer bundle - legal packs per gear",
       size=15, mono=False, bold=True)
f.note(40, 60, "slot = 1 CK phase.   C=CAS, A=ACT = 2 phases (even-aligned).   "
               "P=PRE, R=REF, - =NOP = 1 phase.")
for sx, sc, sl in [(700, FILL_ACTIVE, "CAS"), (800, FILL_NEW, "ACT"),
                   (900, FILL_CELL, "PRE/REF"), (1040, PAPER, "NOP")]:
    stk = FAINT if sl == "NOP" else INK
    f.rect(sx, 30, 18, 18, fill=sc, stroke=stk, width=W_CELL)
    f.text(sx + 24, 44, sl, size=12, mono=False)

# ================= gear 1:4 =================
f.text(40, 100, "gear 1:4  -  4 phase slots", size=13, mono=False, bold=True)
f.line(650, 112, 650, 512, stroke=FAINT)
f.text(70, 116, "LEGAL", size=12, mono=False, bold=True, fill=MUTED)
f.text(680, 116, "NEVER", size=12, mono=False, bold=True, fill=RED)

LX, LTX = 70, 262
RX, RTX = 680, 872
rows = 124
for i, (slots, nm, sub) in enumerate([
        (["C", "C", "A", "A"], "throughput", "1 CAS + 1 ACT, diff bank"),
        (["C", "C", "-", "-"], "steady state", "lone CAS - DQ-bound 1 / 8CK"),
        (["A", "A", "-", "-"], "lone ACT", "miss-refill / cold-start"),
        (["A", "A", "A", "A"], "cross-rank 2 ACT", "tFAW/tRRD dodge - rank0 + rank1"),
        (["C", "C", "P", "-"], "CAS + filler PRE", "PRE to a 3rd bank"),
        (["A", "A", "P", "-"], "ACT + filler PRE", "PRE to a 3rd bank"),
        (["P", "-", "P", "-"], "2 PRE @0,@2", "tPPD=2 gap, diff bank")]):
    y = rows + i * 56
    bundle(LX, y, slots)
    tag(LTX, y, nm, sub)

for i, (slots, nm, sub) in enumerate([
        (["C", "C", "C", "C"], "2 CAS", "dqFree=8 > 4CK - one DQ burst"),
        (["A", "A", "A", "A"], "2 ACT same-rank", "tRRD_S=8 > 4 (ok ONLY cross-rank)"),
        (["P", "P", "-", "-"], "PRE adjacent", "tPPD=2 needs gap -> use [P - P -]"),
        (["C", "C", "A", "A"], "same-bank C+A", "tRCD binds ACT->CAS (diff bank only)")]):
    y = rows + i * 56
    bundle(RX, y, slots, illegal=True)
    tag(RTX, y, nm, sub, bad=True)

# ================= gear 1:2 =================
yb = 548
f.text(40, yb, "gear 1:2  -  2 phase slots", size=13, mono=False, bold=True)
for i, (slots, nm, bad) in enumerate([
        (["C", "C"], "CAS", False), (["A", "A"], "ACT", False),
        (["P", "-"], "PRE / REF", False), (["P", "P"], "2 PRE", True)]):
    x = 70 + i * 230
    bundle(x, yb + 20, slots, illegal=bad)
    f.text(x, yb + 100, nm, size=12, mono=False, bold=True,
           fill=(RED if bad else INK))
    if bad:
        f.note(x, yb + 118, "adjacent - tPPD=2, only 1 PRE fits")
f.note(70, yb + 146, "one command per bundle: a 2-cyc fills both slots, or a "
                     "1-cyc + NOP. Two objects can't co-issue (2-cyc + anything "
                     "needs >= 3 slots).")

# ================= gear 1:1 =================
yc = 730
f.text(40, yc, "gear 1:1  -  1 phase slot", size=13, mono=False, bold=True)
bundle(70, yc + 16, ["C"])
f.line(70 + CW + 3, yc + 10, 70 + CW + 3, yc + 16 + CW + 6, stroke=FAINT, dashed=True)
bundle(70 + CW + 6, yc + 16, ["C"])
f.note(70 + 2 * CW + 24, yc + 30, "2-cyc cmd (CAS/ACT) straddles 2 mc_clk "
                                  "(2 bundles). No packing, no co-issue -")
f.note(70 + 2 * CW + 24, yc + 48, "pure stream, one phase per clk. PRE/REF = 1 clk.")

f.caption(40, 800,
          "Bundle width = gear (1:4->4, 1:2->2, 1:1->1 phases). Co-issue only "
          "when two different-bank objects fit and every pair spacing <= window. "
          ">=2 CAS never (DQ). 2nd ACT only cross-rank. PRE x2 only at tPPD=2 gap.")

f.save("fig_26_bundle_packs.svg")
print("wrote fig_26_bundle_packs.svg")
