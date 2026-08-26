from rtlfig import Fig, MUTED, FILL_CELL, FILL_LOGIC

# fig_08 — decoder -> L2 path = ONE rank subtree, instanced x N_RANKS.
# Invariant: 1 shared decoder; per-rank subtree {32 cells -> 8 bg_arb -> 1
# rank_arb}; L3 collects N_RANKS winners into one issue path.

f = Fig(1340, 780)


def subtree(xc, rk):
    # 32-cell block (L0)
    f.rect(xc - 190, 196, 380, 60, fill=FILL_CELL, width=1.4)
    f.text(xc, 220, f"cell[{{{rk}, 0..31}}]   -   32 cells", size=12,
           anchor="middle", bold=True)
    f.text(xc, 240, "L0: CAM + FSM + elig", size=10, mono=False,
           anchor="middle", fill=MUTED)
    # 8x bg_arb (L1) - draw 3 + ellipsis
    for i in range(3):
        f.mux(xc - 180 + i * 108, 322, 92, 42, "bg")
    f.text(xc + 150, 346, "... x8", size=11, mono=False, fill=MUTED)
    f.text(xc, 300, f"8x  bg_arb[r{rk}]   (L1)   4 banks -> 1", size=11,
           anchor="middle", fill=MUTED)
    for i in range(3):
        cx = xc - 180 + i * 108 + 46
        f.line(cx, 256, cx, 322, arrow=True)
    # rank_arb (L2)
    f.mux(xc - 110, 442, 220, 48, f"rank_arb[r{rk}]", sel="L2")
    f.line(xc, 364, xc, 442, arrow=True)


# ---------------- shared decoder ----------------
f.text(430, 56, "from head_mux (lookahead)", size=12, mono=False,
       anchor="middle")
f.line(430, 64, 430, 92, arrow=True)
f.logic(300, 92, 520, 58, "per_bank_decoder",
        "1 request -> cell[{rank,bank}]   (64/128-way one-hot)")

# ---------------- N_RANKS subtrees ----------------
subtree(360, 0)
subtree(880, 1)
f.text(620, 226, "...  x N_RANKS", size=12, mono=False, anchor="middle",
       fill=MUTED)

# decoder -> both cell blocks
f.path("M470 150 L360 150 L360 194", arrow=True)
f.path("M650 150 L880 150 L880 194", arrow=True)

# ---------------- L3 collects the rank winners ----------------
f.path("M360 490 L500 490 L500 560", arrow=True)
f.path("M880 490 L740 490 L740 560", arrow=True)
f.mux(500, 560, 240, 50, "inter_rank_arb", sel="L3")
f.text(360, 516, "rank0 winner", size=10, mono=False, anchor="middle", fill=MUTED)
f.text(880, 516, "rank1 winner", size=10, mono=False, anchor="middle", fill=MUTED)

f.line(620, 610, 620, 664, arrow=True)
f.text(620, 686, "->  packer  ->  one shared issue path", size=12, mono=False,
       anchor="middle")

# ---------------- instance-count ledger ----------------
lx = 1120
f.rect(lx, 92, 200, 420, fill="none", stroke=MUTED, width=1.0)
f.text(lx + 100, 116, "instance count", size=12, mono=False, anchor="middle",
       bold=True)
ledger = [(160, "per_bank_decoder", "x1  (shared)"),
          (240, "cell[{rank,bank}]", "N_RANKS x 32 = 64/128"),
          (320, "bg_arb  (L1)", "N_RANKS x 8 = 16/32"),
          (400, "rank_arb  (L2)", "N_RANKS = 2/4"),
          (480, "inter_rank_arb (L3)", "x1")]
for y, name, cnt in ledger:
    f.text(lx + 12, y, name, size=11, mono=True)
    f.text(lx + 12, y + 16, cnt, size=11, mono=False, fill=MUTED)

f.caption(40, 748, "The decoder->L2 path is ONE rank subtree {32 cells -> 8 "
                   "bg_arb -> 1 rank_arb}, instanced x N_RANKS. One shared "
                   "decoder feeds them; L3 collects the N_RANKS winners into one "
                   "issue path.")

f.save("fig_08_rank_funnel.svg")
print("wrote fig_08_rank_funnel.svg")
