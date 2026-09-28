from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_69 — 1:4 gearing at the CA bus. dfi_clk=CK/4; 1 edge = 4 CK; MC drives 4 phase
# buses at once; PHY serializes p0..p3 onto ONE CA bus at CK. 2-UI cmd = 2 phases.

CMD = "#7a4fb0"; DATA = "#2a8f86"; GREEN = "#3d8c40"
BW = 150
X0 = 260
f = Fig(1180, 940)

FILLS = {"C": FILL_ACTIVE, "A": FILL_NEW, "P": FILL_CELL, "-": PAPER}


def clocks(y):
    # dfi_clk : one period over 4 beats
    f.text(60, y + 6, "dfi_clk", size=10, mono=True)
    f.path(f"M{X0} {y+14} H{X0+2*BW} V{y-14} H{X0+4*BW} V{y+14}", stroke=CMD)
    f.text(X0+4*BW+12, y+6, "= CK/4", size=8, mono=True, fill=MUTED)
    # CK : 4 periods
    yy = y+50
    f.text(60, yy+6, "CK (DRAM)", size=10, mono=True)
    d = "M"
    x = X0
    for i in range(4):
        d += f"{x} {yy+14} H{x+BW/2} V{yy-14} H{x+BW} V{yy+14} "
        x += BW
    f.path(d, stroke=INK)


def slot_row(y, label, cells, fill=True, sub=None):
    f.text(60, y + 26, label, size=10, mono=True)
    for i, c in enumerate(cells):
        x = X0 + i * BW
        fc = FILLS.get(c[0], PAPER) if fill else PAPER
        f.rect(x, y, BW, 44, fill=fc, width=W_CELL)
        f.text(x + BW/2, y + 27, c, size=10, mono=True, anchor="middle")


f.text(40, 32, "1:4 gearing at the CA bus  (dfi_clk=CK/4, 4 phases per edge)", size=15,
       mono=False, bold=True)

# clocks
clocks(90)

# phase / CK column headers
hy = 200
for i in range(4):
    x = X0 + i * BW
    f.text(x + BW/2, hy, f"CK{i}", size=10, mono=True, anchor="middle", fill=MUTED)
    f.text(x + BW/2, hy+16, f"phase p{i}", size=9, mono=True, anchor="middle", fill=CMD)

f.text(60, hy+8, "PHY serializes", size=8, mono=False, fill=GREEN)
f.text(60, hy+22, "p0..p3 -> CA", size=8, mono=False, fill=GREEN)

# ---- Example A: CAS + ACT (same rank) ----
ay = 240
f.text(60, ay-8, "A)  1 CAS + 1 ACT  =  [C C | A A]  (2 cmds, same rank)", size=11,
       mono=False, bold=True)
slot_row(ay, "CA bus", ["RD u0", "RD u1", "ACT u0", "ACT u1"])
slot_row(ay+50, "dfi_cs", ["r0", "r0", "r0", "r0"], fill=False)
f.text(X0, ay+110, "RD occupies p0-p1 (2 UI), ACT p2-p3 (2 UI). CS=r0 all four.",
       size=8, mono=False, fill=MUTED)

# ---- Example B: 2 ACT diff rank ----
by = 410
f.text(60, by-8, "B)  2 ACT diff rank  =  [A A | A A]  (needs BOTH ranks; CS routes)",
       size=11, mono=False, bold=True)
slot_row(by, "CA bus", ["ACT0 u0", "ACT0 u1", "ACT1 u0", "ACT1 u1"])
slot_row(by+50, "dfi_cs", ["r0", "r0", "r1", "r1"], fill=False)
f.text(X0, by+110, "ONE CA bus, time-shared. ACT to rank0 (p0-p1, cs=r0), ACT to rank1 "
       "(p2-p3, cs=r1). Not parallel - serialized, CS picks rank.", size=8, mono=False, fill=MUTED)

# ---- Example C: CAS + 2 PRE ----
cy = 580
f.text(60, cy-8, "C)  1 CAS + 2 PRE  =  [C C | P | P]  (3 cmds - 1-UI PREs fill)",
       size=11, mono=False, bold=True)
slot_row(cy, "CA bus", ["WR u0", "WR u1", "PRE a", "PRE b"])
slot_row(cy+50, "dfi_cs", ["r0", "r0", "r0", "r0"], fill=False)
f.text(X0, cy+110, "PRE is 1 UI -> fits one phase each. WR (2 UI) + 2 PRE (1 UI) = 4 phases "
       "= 3 cmds (tPPD=2 ok @ p2,p3).", size=8, mono=False, fill=MUTED)

# ---- rules box ----
f.rect(60, 740, 1080, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(80, 764, "THE RULES", size=11, bold=True)
rr = ["dfi_clk = CK/GEAR (slow). 1:4 -> one dfi_clk edge = 4 CK = 4 CA phases. MC drives "
      "dfi_address_p0..p3 + dfi_cs_p0..p3 ALL AT ONCE (parallel wires).",
      "PHY serializes: p0->CK0, p1->CK1, p2->CK2, p3->CK3 onto the ONE DRAM CA bus. Nothing runs "
      "4 commands in parallel - the CA bus is one bus at CK rate.",
      "DDR5 command = 2 UI = 2 CK = 2 phases (ACT/RD/WR); PRE/REF = 1 UI = 1 phase.",
      "4 phases -> max 2 two-UI cmds ([C C A A]) OR 1 two-UI + 2 one-UI ([C C P P]) = up to 3.",
      "2 ACT diff-rank = all 4 phases [A A A A]; dfi_cs per phase-pair selects the rank. One CA "
      "bus, time-shared, CS routes - that is the ONLY way two ACTs coexist in a bundle."]
for i, s in enumerate(rr):
    f.text(80, 786 + i*20, f"{i+1}. {s}", size=9, mono=False)

f.save("fig_69_gear_timing.svg")
print("wrote fig_69_gear_timing.svg")
