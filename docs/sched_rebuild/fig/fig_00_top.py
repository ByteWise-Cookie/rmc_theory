from rtlfig import Fig, MUTED, FILL_CELL, FILL_LOGIC

# fig_00 — MC-core top: N_RANKS full lanes + one L3 cap + shared back-end.
# Invariant: each rank = a complete lane (= fig_01..06); the ONLY rank arb is
# L3; scoreboard-global + packer + DFI + SRAM are shared.

SB = "#7a5cb8"
f = Fig(1440, 860)


def lane(x, r):
    f.rect(x, 150, 340, 322, fill=FILL_LOGIC, width=1.6)
    f.text(x + 170, 176, f"rank {r} lane", size=14, anchor="middle", bold=True)
    f.text(x + 170, 194, "= fig_01..06 (one full front)", size=10, mono=False,
           anchor="middle", fill=MUTED)
    rows = [("rd_fifo[r] | wr_fifo[r]", "fig_01"),
            ("WLR[r]   (batch_dir)", ""),
            ("lookahead[r]  4-entry bypass", "fig_02"),
            ("decoder[r]  32-way", ""),
            ("cells[r] x32  CAM+FSM+elig (L0)", "fig_03"),
            ("bg_arb[r] x8   (L1)", ""),
            ("rank_arb[r]    (L2)", "")]
    y = 224
    for txt, fig in rows:
        f.text(x + 18, y, txt, size=11)
        if fig:
            f.text(x + 322, y, fig, size=9, mono=False, anchor="end", fill=MUTED)
        if y > 224:
            f.text(x + 170, y - 20, "|", size=10, anchor="middle", fill=MUTED)
        y += 35
    return x + 170  # lane center x


# ---------------- CIF feeds both lanes ----------------
f.rect(600, 60, 240, 52, fill=FILL_CELL, width=1.4)
f.text(720, 84, "CIF", size=14, anchor="middle", bold=True)
f.text(720, 100, "not mine", size=10, mono=False, anchor="middle", fill=MUTED)

l0 = lane(150, 0)
l1 = lane(820, 1)
f.text(670, 300, "...  x N_RANKS", size=13, mono=False, anchor="middle",
       fill=MUTED)
f.text(670, 320, "identical lanes", size=10, mono=False, anchor="middle",
       fill=MUTED)

f.path(f"M660 112 L{l0} 112 L{l0} 148", arrow=True)
f.text(l0, 132, "async", size=9, mono=False, anchor="middle", fill=MUTED)
f.path(f"M780 112 L{l1} 112 L{l1} 148", arrow=True)
f.text(l1, 132, "async", size=9, mono=False, anchor="middle", fill=MUTED)

# ---------------- L3 cap ----------------
f.path(f"M{l0} 472 L{l0} 512 L560 512 L560 540", arrow=True)
f.text(l0, 498, "rank0 winner", size=10, mono=False, anchor="middle", fill=MUTED)
f.path(f"M{l1} 472 L{l1} 512 L720 512 L720 540", arrow=True)
f.text(l1, 498, "rank1 winner", size=10, mono=False, anchor="middle", fill=MUTED)
f.mux(500, 540, 280, 52, "inter_rank_arb   (L3)", sel="tRTRS wt")
f.text(640, 616, "the ONLY rank arb", size=10, mono=False, anchor="middle",
       fill=MUTED)

# ---------------- shared back-end ----------------
f.rect(360, 640, 560, 150, fill=FILL_CELL, width=1.6)
f.text(640, 664, "shared back-end", size=13, anchor="middle", bold=True)
f.text(915, 654, "fig_05 / fig_06", size=9, mono=False, anchor="end", fill=MUTED)
for i, ln in enumerate([
        "phase_packer -> DFI -> PHY -> DRAM",
        "DRAM -> rddata -> read_accum -> RD_SRAM",
        "RD_SRAM -> completion -> CIF   (async)",
        "WD_SRAM -> write_splitter -> dfi_wrdata"]):
    f.text(384, 694 + i * 22, ln, size=11)
f.line(640, 592, 640, 640, arrow=True)

# ---------------- shared scoreboard-global ----------------
f.rect(1180, 210, 240, 180, fill="none", stroke=SB, width=1.4)
f.text(1300, 236, "scoreboard-GLOBAL", size=12, anchor="middle", bold=True,
       fill=SB)
for i, ln in enumerate(["gc, last_cas_rank,", "last_cas_dir,",
                        "dqFree_ts, caFree_ts"]):
    f.text(1200, 264 + i * 20, ln, size=11, fill=SB)
f.text(1300, 338, "one CA + one DQ bus", size=10, mono=False, anchor="middle",
       fill=MUTED)
f.text(1300, 354, "broadcast-read, 1 writer/slot", size=10, mono=False,
       anchor="middle", fill=MUTED)
f.text(1300, 372, "per-lane: faw_ts[4], raa, gate_rfc", size=10, mono=False,
       anchor="middle", fill=MUTED)
f.line(1178, 300, 1000, 300, arrow=True, stroke=SB)          # -> rank1 cells
f.path("M1180 340 L490 340", arrow=True, stroke=SB)          # -> rank0 cells
f.text(720, 332, "can_* / global broadcast to every lane's cells", size=9,
       mono=False, anchor="middle", fill=SB)

f.caption(40, 838, "Multi-rank core = N_RANKS copies of fig_01..06 (one lane "
                   "each) + ONE L3 inter_rank_arb + one shared back-end + one "
                   "shared scoreboard-global. Ingress rank-arb deleted; lanes "
                   "are independent to L3.")

f.save("fig_00_top.svg")
print("wrote fig_00_top.svg")
