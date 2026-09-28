from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_49 — RD<->WR turnaround breakdown, by scope (bank/BG/rank).
# Invariant: turnaround REPLACES the dqFree gap at a direction flip (not added).
# DDR5-4800B CK: CL=40 CWL=38 BL/2=8 tRTRS=2 tWTR_S=6 tWTR_L=24 tRTW=12.

f = Fig(1200, 720)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "RD<->WR turnaround - component breakdown by scope", size=15,
       mono=False, bold=True)
f.note(40, 58, "Turnaround REPLACES the dqFree=8 gap AT A FLIP - it is NOT dqFree + tRTW. "
               "Same-dir back-to-back = dqFree/tCCD; a direction change = the value below.")
f.text(40, 84, "DDR5-4800B CK:  CL=40  CWL=38  BL/2=8  tRTRS=2  tWTR_S=6  tWTR_L=24  tRTW=12",
       size=11, mono=True, fill=MUTED)

# ---------------- table ----------------
X = [60, 200, 500, 790]        # col left edges
W = [140, 300, 290, 300]       # col widths
HY, H0, H1 = 120, 46, 96

# header row
cols = ["", "same BG\n(bank / diff-bank)", "diff BG\n(same rank)", "diff rank"]
for i, c in enumerate(cols):
    f.rect(X[i], HY, W[i], H0, fill=FILL_ACTIVE if i else PAPER, width=W_CELL)
    for j, ln in enumerate(c.split("\n")):
        f.text(X[i] + W[i] / 2, HY + 20 + j * 16, ln, size=11, mono=False,
               anchor="middle", bold=(i > 0))

# RD->WR row
y = HY + H0
f.rect(X[0], y, W[0], H0 + 34, fill=FILL_LOGIC, width=W_CELL)
f.text(X[0] + W[0] / 2, y + 34, "RD -> WR", size=13, anchor="middle", bold=True)
for i, txt in enumerate(["tRTW = 12", "12", "~12  (bus)"]):
    f.rect(X[i + 1], y, W[i + 1], H0 + 34, width=W_CELL)
    f.text(X[i + 1] + W[i + 1] / 2, y + 40, txt, size=12, anchor="middle")
cnote(X[1] + 8, y + 66, "flat - reads have no tWTR-style internal recovery")

# WR->RD row
y2 = y + H0 + 34
f.rect(X[0], y2, W[0], H1, fill=FILL_LOGIC, width=W_CELL)
f.text(X[0] + W[0] / 2, y2 + 52, "WR -> RD", size=13, anchor="middle", bold=True)
wr = [("CWL+BL/2+tWTR_L", "= 38+8+24 = 70"),
      ("CWL+BL/2+tWTR_S", "= 38+8+6 = 52"),
      ("CWL+BL/2+tRTRS", "= 38+8+2 = 48")]
for i, (form, val) in enumerate(wr):
    f.rect(X[i + 1], y2, W[i + 1], H1, fill=FILL_NEW, width=W_CELL)
    f.text(X[i + 1] + W[i + 1] / 2, y2 + 40, form, size=12, anchor="middle")
    f.text(X[i + 1] + W[i + 1] / 2, y2 + 62, val, size=12, anchor="middle", bold=True)
cnote(X[3] + 8, y2 + 82, "cross-rank: other device, no tWTR")

# ---------------- breakdown panel ----------------
by = y2 + H1 + 40
f.text(40, by, "what is happening:", size=13, mono=False, bold=True)
f.text(40, by + 26, "RD -> WR  =  CL + BL/2 + tRTRS  -  CWL   = 40+8+2-38 = 12",
       size=12, mono=True)
cnote(60, by + 44, "read data must return (CL) + burst (BL/2) + bus turn (tRTRS); "
                   "write leads by CWL, so subtract it -> 12, flat across scopes.")
f.text(40, by + 76, "WR -> RD  =  CWL + BL/2 + { tWTR_L | tWTR_S | tRTRS }",
       size=12, mono=True)
cnote(60, by + 94, "write data drives late (CWL) + burst (BL/2), THEN internal write "
                   "recovery before a same-device read:")
cnote(60, by + 110, "same BG -> tWTR_L=24 (70) ; diff BG -> tWTR_S=6 (52) ; diff rank -> "
                    "no tWTR, just bus turn tRTRS=2 (48).")

# key takeaways
f.rect(40, by + 134, 1100, 60, fill=PAPER, stroke=FAINT, width=W_CELL)
f.text(56, by + 156, "WR->RD >> RD->WR", size=12, mono=False, bold=True)
cnote(200, by + 156, "because the write must COMMIT internally (tWTR) before a same-device "
                     "read, and its data starts late (CWL). Read has no such recovery -> RD->WR flat 12.")
cnote(56, by + 178, "At a flip the turnaround is the WHOLE gap and replaces one dqFree; it is "
                    "NOT dqFree(8) + turnaround. WR batches run longer (costlier to leave).")

f.save("fig_49_turnaround.svg")
print("wrote fig_49_turnaround.svg")
