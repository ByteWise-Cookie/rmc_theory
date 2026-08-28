from rtlfig import Fig, MUTED, FILL_CELL, FILL_ACTIVE, FILL_NEW, FILL_LOGIC

# fig_15 - the enc-tagged micro-op. One fixed-width command rides the whole arb
# tree; enc reinterprets a union operand (ACT row and CAS {col,sram,rob} share
# the same bit slots) and keys the per-scope timing check at every level.

f = Fig(1160, 660)
f.note(1150, 30, "enc-tagged micro-op  -  ~36 b / lane, union operand", anchor="end")

BIT = 25.3
X0 = 120
def X(b):        # x of bit offset b
    return X0 + b * BIT
def fld(b0, nb, y, h, label, sub=None, fill=FILL_CELL, stroke=None):
    x, w = X(b0), nb * BIT
    kw = {"stroke": stroke} if stroke else {}
    f.rect(x, y, w, h, fill=fill, width=1.6, **kw)
    f.text(x + w / 2, y + h / 2 + 1, label, size=12, anchor="middle", bold=True)
    if sub:
        f.text(x + w / 2, y + h / 2 + 16, sub, size=9, mono=False,
               anchor="middle", fill=MUTED)
    return x, w

# ---------- row A: the format ----------
f.text(X0, 66, "format", size=12, mono=False, anchor="end", fill=MUTED)
fld(0, 2,  74, 52, "enc",     "2", fill=FILL_NEW)
fld(2, 1,  74, 52, "dir",     "1", fill=FILL_LOGIC)
fld(3, 6,  74, 52, "idx",     "rank1·bg3·bank2", fill=FILL_ACTIVE)
fld(9, 27, 74, 52, "operand  (tagged union)", "27 = widest member (CAS)", fill=FILL_CELL)

# ---------- rows B..D: the union under operand ----------
f.text(X(9) - 12, 168, "enc =", size=11, mono=False, anchor="end", fill=MUTED)

f.text(X0, 168, "PRE", size=12, mono=False, anchor="end", bold=True)
f.rect(X(9), 150, 27 * BIT, 34, fill="none", stroke=MUTED, width=1.4, dashed=True)
f.text(X(9) + 27 * BIT / 2, 172, "(idx only - no operand)", size=10, mono=False,
       anchor="middle", fill=MUTED)

f.text(X0, 214, "ACT", size=12, mono=False, anchor="end", bold=True)
fld(9, 18, 196, 34, "row", "18", fill=FILL_ACTIVE)
f.rect(X(27), 196, 9 * BIT, 34, fill="none", stroke=MUTED, width=1.2, dashed=True)
f.text(X(27) + 9 * BIT / 2, 217, "unused", size=9, mono=False, anchor="middle",
       fill=MUTED)

f.text(X0, 260, "CAS", size=12, mono=False, anchor="end", bold=True)
fld(9,  10, 242, 34, "col", "10", fill=FILL_NEW)
fld(19, 9,  242, 34, "sram_addr", "9  (dbuf|wd_slot)", fill=FILL_NEW)
fld(28, 8,  242, 34, "rob_index", "8", fill=FILL_NEW)
f.text(X(9) + 27 * BIT / 2, 296, "only enc==CAS carries data + arms the RD/WL "
       "engine (via sram_addr)", size=9, mono=False, anchor="middle", fill=MUTED)

# ---------- row E: enc keys the per-scope timing at every level ----------
f.text(X0 - 40, 350, "enc rides every level - keys the per-scope timing check:",
       size=12, mono=False, fill=MUTED)

lv = [
    ("CMD_ARB", "L0 same-bank", "PRE:tRAS/tRTP/tWR  ACT:tRC  CAS:tCCD_Lsb"),
    ("BGB_ARB", "L1 bank-in-BG", "CAS hit-bias · ACT age"),
    ("BG_ARB",  "L2 BG-in-rank", "CAS:tCCD_S/L +diffBG  ACT:tRRD_S/L"),
    ("RANK_ARB","L3 cross-rank", "CAS+dir:tWTR/tRTW/tRTRS  ACT:tFAW"),
    ("PHASE_PACKER", "CA + data", "enc->CA decode; arm iff CAS"),
]
bx, bw, by, bh = 60, 205, 380, 96
for i, (nm, sc, tm) in enumerate(lv):
    x = bx + i * (bw + 8)
    f.logic(x, by, bw, bh, nm, top=True)
    f.text(x + bw / 2, by + 40, sc, size=10, mono=False, anchor="middle",
           fill=MUTED)
    # wrap timing text
    words, line, yy = tm.split("  "), "", by + 60
    for w in tm.split("  "):
        f.text(x + bw / 2, yy, w, size=9, mono=False, anchor="middle")
        yy += 13
    if i < 4:
        f.line(x + bw, by + bh / 2, x + bw + 8, by + bh / 2, arrow=True)

# enc bus under the level row
f.line(bx, by + bh + 26, bx + 5 * (bw + 8) - 8, by + bh + 26, stroke=FILL_NEW,
       width=3)
f.text(bx, by + bh + 44, "enc (+dir) broadcast to every level - one tag, reused",
       size=10, mono=False, fill=MUTED)

f.caption(40, 640, "One enc-tagged micro-op rides the arb tree: enc reinterprets "
                   "a 27-b union operand (ACT row and CAS {col,sram,rob} share "
                   "slots) and keys the per-scope timing at every level.")

f.save("fig_15_microop.svg")
print("wrote fig_15_microop.svg")
