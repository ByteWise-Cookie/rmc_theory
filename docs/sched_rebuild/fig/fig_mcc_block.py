from rtlfig import Fig, MUTED, FAINT, FILL_CELL, FILL_ACTIVE

# fig_mcc_block - MC-core master floorplan (CIF-abstraction peer).
# Every functional block once, named, arrowed. One rank lane in full + xN_RANKS
# badge; one L3 cap; scoreboard side-rail; shared back-end + maintenance.
# Invariant: N_RANKS full lanes fan into one L3; scoreboard folds legality into
# can_* so arb only selects; one shared back-end drives DFI + returns data.

SB = "#7a5cb8"
f = Fig(1680, 1200)

f.note(1660, 34, "MC-core  -  one channel  (32-bit DDR5 sub-channel)", anchor="end")
f.note(1660, 50, "abstraction = CIF sub-block peer", anchor="end")


def box(x, y, w, h, name, sub=None, fill=FILL_CELL):
    f.rect(x, y, w, h, fill=fill, width=1.4)
    f.text(x + w / 2, y + (h / 2 + 5 if not sub else h / 2 - 2), name,
           size=13, anchor="middle", bold=True)
    if sub:
        f.text(x + w / 2, y + h / 2 + 14, sub, size=10, mono=False,
               anchor="middle", fill=MUTED)


# ================= CIF source =================
box(210, 44, 300, 48, "CIF", "not mine  -  async boundary")

# ================= rank lane (drawn full) =================
LX, LY, LW, LH = 80, 120, 560, 660
f.rect(LX, LY, LW, LH, fill="none", stroke=MUTED, width=1.6, dashed=True)
f.text(LX + 14, LY + 22, "rank lane", size=13, bold=True)
f.text(LX + 14, LY + 38, "x N_RANKS = 2", size=10, mono=False, fill=MUTED)
cxl = 360

# -- async req FIFOs in --
box(180, 150, 140, 46, "R_REQ_AFIFO")
box(400, 150, 140, 46, "W_REQ_AFIFO")
f.path("M320 92 L250 92 L250 148", arrow=True)
f.path("M400 92 L470 92 L470 148", arrow=True)
f.text(360, 124, "async", size=10, mono=False, anchor="middle", fill=MUTED)

# -- back-pressure FIFOs, split by direction --
box(180, 224, 140, 46, "RD_BP_FIFO", "depth 16")
box(400, 224, 140, 46, "WR_BP_FIFO", "depth 16")
f.line(250, 196, 250, 224, arrow=True)
f.line(470, 196, 470, 224, arrow=True)

# -- turnaround control + WLR select mux --
f.rect(92, 300, 100, 52, fill="#f4f4f4", width=1.4)
f.text(142, 322, "TURN", size=12, anchor="middle", bold=True)
f.text(142, 338, "_CTRL", size=12, anchor="middle", bold=True)
f.path("M180 247 L150 247 L150 300", arrow=True, dashed=True)
f.text(158, 288, "full/partial", size=9, mono=False, fill=MUTED)

wm = f.mux(260, 300, 200, 52, "WLR_SEL", sel="batch_dir")
f.path("M250 270 L250 292 L312 292 L312 300", arrow=True)
f.path("M470 270 L470 292 L408 292 L408 300", arrow=True)
f.line(192, 326, 258, 326, arrow=True)          # turn_ctrl -> mux select

# -- lookahead --
f.logic(210, 386, 300, 58, "LOOKAHEAD",
        "e0..e3 . bank_cmp . prio_enc . head_mux")
f.line(360, 352, 360, 386, arrow=True)
f.slash(360, 370, "REQ_W")

# -- per-bank decoder --
f.logic(210, 474, 300, 48, "BANK_DEC", "1-of-32  (8 BG x 4 banks)")
f.line(360, 444, 360, 474, arrow=True)

# -- per-bank cell array --
f.logic(175, 544, 370, 82, "BANK_CELL[{r,b}]   x32", top=True)
f.text(360, 590, "open_row CAM . 16-state FSM . elig_gen (L0)", size=11,
       mono=False, anchor="middle", fill=MUTED)
f.text(360, 608, "row_valid = OPEN & !pre_pending", size=10, mono=False,
       anchor="middle", fill=MUTED)
f.line(360, 522, 360, 544, arrow=True)

# -- L1 bg_arb --
f.logic(210, 650, 300, 42, "BG_ARB  x8    (L1)")
f.line(360, 626, 360, 650, arrow=True)

# -- L2 rank_arb --
f.mux(260, 708, 200, 44, "RANK_ARB (L2)")
f.line(360, 692, 360, 708, arrow=True)

# ================= ghost 2nd lane =================
f.rect(690, 300, 150, 452, fill="none", stroke=FAINT, width=1.4, dashed=True)
f.text(765, 500, "rank 1 lane", size=12, anchor="middle", fill=MUTED)
f.text(765, 518, "(identical)", size=10, mono=False, anchor="middle", fill=MUTED)
f.text(765, 534, "ingress -> L2", size=10, mono=False, anchor="middle", fill=MUTED)

# ================= L3 inter-rank arb =================
f.mux(470, 838, 300, 54, "INTER_RANK_ARB  (L3)", sel="tRTRS wt")
f.path("M360 752 L360 812 L540 812 L540 838", arrow=True)
f.text(360, 800, "rank0 winner", size=10, mono=False, anchor="middle", fill=MUTED)
f.path("M765 752 L765 812 L700 812 L700 838", arrow=True)
f.text(770, 800, "rank1 winner", size=10, mono=False, fill=MUTED)
f.text(620, 912, "the ONLY rank arb", size=10, mono=False, anchor="middle",
       fill=MUTED)

# ================= shared back-end =================
f.logic(490, 924, 260, 64, "PHASE_PACKER", top=True)
f.text(620, 968, "gear 1:N . bundle . FSM-commit", size=10, mono=False,
       anchor="middle", fill=MUTED)
f.line(620, 892, 620, 924, arrow=True)

# DFI mux out
box(810, 930, 170, 58, "DFI_MUX", "init / sched", fill="#f4f4f4")
f.line(750, 956, 810, 956, arrow=True)
f.slash(780, 956, "N phases")
f.line(980, 956, 1120, 956, arrow=True)
f.text(1130, 952, "DFI / PHY -> DRAM", size=12, mono=False)

# write-data path
box(120, 1004, 150, 60, "WD_SRAM", "512b/line")
f.logic(310, 1004, 220, 60, "WR_SPLIT + WL_LAUNCH", "512b -> serialize")
f.line(270, 1034, 310, 1034, arrow=True)
f.slash(290, 1034, "512b")
f.line(530, 1034, 660, 1034, arrow=True)
f.slash(595, 1034, "2*gear")
f.text(668, 1030, "dfi_wrdata", size=11)
f.path("M560 988 L420 988 L420 1004", arrow=True, dashed=True)
f.text(490, 980, "arm @ CAS-commit", size=9, mono=False, anchor="middle",
       fill=MUTED)

# read-data path
f.logic(1120, 1004, 230, 60, "RD_CAP + RD_ACCUM", "deserialize -> 64B")
box(1400, 1004, 150, 60, "RD_SRAM", "512b/line")
f.path("M1000 990 L1235 990 L1235 1004", arrow=True)
f.text(1120, 982, "dfi_rddata (RL later)", size=10, mono=False, fill=MUTED)
f.line(1350, 1034, 1400, 1034, arrow=True)
f.slash(1375, 1034, "512b")

# completion + async out
f.logic(1150, 1100, 250, 56, "COMPLETION", "rd_done | wr_done")
box(1430, 1100, 150, 56, "R/W_RESP_AFIFO", fill=FILL_CELL)
f.path("M1475 1064 L1475 1128 L1400 1128", arrow=True)
f.text(1500, 1088, "rd_done", size=9, mono=False, anchor="middle", fill=MUTED)
f.path("M420 1064 L420 1128 L1150 1128", arrow=True, dashed=True)
f.text(700, 1120, "wr_done (self-timed)", size=9, mono=False, fill=MUTED)
f.line(1400, 1128, 1430, 1128, arrow=True)
f.path("M1580 1120 L1630 1120 L1630 68 L512 68", arrow=True, dashed=True)
f.text(1360, 1180, "completion -> CIF (async)", size=10, mono=False,
       anchor="end", fill=MUTED)

# ================= maintenance engine =================
f.logic(880, 150, 260, 150, "MAINT_ENG", top=True)
for i, ln in enumerate([
        "INIT  (owns init_done)",
        "REFRESH  (per rank, REFsb)",
        "RFM . ZQ . MRW   (stub)",
        "peer source - NEVER CAS"]):
    f.text(900, 196 + i * 24, ln, size=11,
           fill=(MUTED if i == 3 else "#000000"),
           mono=(i != 3))
f.path("M1010 300 L1010 900 L620 900 L620 924", arrow=True)
f.text(1010, 318, "inject (override)", size=9, mono=False, anchor="middle",
       fill=MUTED)
f.path("M1140 180 L1170 180 L1170 934 L980 934", arrow=True)
f.text(1120, 172, "init_done", size=9, mono=False, anchor="end", fill=MUTED)
f.path("M880 210 L640 210 L640 566 L543 566", arrow=True, stroke=SB)
f.text(660, 202, "REF_pending", size=9, mono=False, fill=SB)

# ================= scoreboard, SPLIT by arb level =================
# one timing-reg per level (bank / BG / rank), each with its CMP (-> can_*) and
# its UPDATE block (next_* = GC + timing @ cmd_issued). GLOBAL_REG = shared bus.
f.text(1405, 168, "SCOREBOARD  -  split by arb level", size=13, anchor="middle",
       bold=True, fill=SB)
f.counter(1645, 214, 30, "GC", "CK cnt")

# GC broadcast bus down the far right (feeds every UPDATE)
f.line(1645, 244, 1645, 916)
f.text(1660, 560, "GC", size=9, mono=False, fill=MUTED)
# cmd_issued bus from packer (triggers every UPDATE, carries issued cmd)
f.path("M740 924 L740 586 L1150 586 L1150 916", dashed=True, stroke=SB)
f.text(905, 578, "cmd_issued", size=10, mono=False, anchor="middle", fill=SB)


def level(y, treg, params, cmpn, upd, tier_path, lbl_xy, th=60):
    # CMP (left, emits can_*) -- TREG (mid, holds next_*) -- UPD (below)
    f.logic(1180, y + 2, 150, 54, "CMP", cmpn)
    f.logic(1360, y, 270, th, treg, params, top=True)
    uy = y + th + 12
    f.logic(1360, uy, 270, 40, upd, "next_* = GC + t")
    f.line(1360, y + 30, 1330, y + 30, arrow=True)              # next_* -> CMP
    f.line(1495, uy, 1495, uy - 12, arrow=True)                 # UPD writes TREG
    f.line(1645, uy + 20, 1632, uy + 20, arrow=True)            # GC -> UPD
    f.line(1150, uy + 20, 1360, uy + 20, arrow=True, stroke=SB)  # cmd_issued -> UPD
    f.path(tier_path, arrow=True, stroke=SB)                    # can_* -> tier
    f.text(lbl_xy[0], lbl_xy[1], cmpn, size=9, mono=False, anchor="middle",
           fill=SB)


level(500, "BANK_TREG", "tRC . tRTP . tWR . tRAS . tCCD_Lsb", "can_bank",
      "BANK_UPD", "M1180 530 L620 530 L620 590 L545 590", (1055, 522))
level(668, "BG_TREG", "tCCD_L . tRRD_L . tRFCsb (REFsb)", "can_bg",
      "BG_UPD", "M1180 698 L560 698 L560 671 L513 671", (1055, 690), th=52)
level(820, "RANK_TREG", "tWTR/tRTW . tFAW[4] . tRTRS . RAA . REFab", "can_rank",
      "RANK_UPD", "M1180 850 L800 850 L800 866 L772 866", (975, 843))
f.text(975, 828, "-> L3  (+L2 rank_arb)", size=9, mono=False, anchor="middle",
       fill=SB)

# global reg under the rank level (shared bus state)
f.logic(1360, 936, 270, 40, "GLOBAL_REG", "CAFREE . DQFREE . LAST_CAS")

# REF / gate_rfc fan from maintenance -> every ref-scoped level.
# bank = solo REF_pending (arrow above); BG = REFsb; rank = REFab; global = gate_rfc.
f.path("M1140 270 L1345 270 L1345 956 L1360 956", arrow=True, stroke=SB)  # -> GLOBAL
f.line(1345, 706, 1360, 706, arrow=True, stroke=SB)                       # REFsb -> BG
f.line(1345, 858, 1360, 858, arrow=True, stroke=SB)                       # REFab -> RANK
f.text(1150, 262, "REF / gate_rfc", size=9, mono=False, anchor="end", fill=SB)
f.text(1352, 700, "REFsb", size=8, mono=False, fill=SB)
f.text(1352, 852, "REFab", size=8, mono=False, fill=SB)
f.text(1352, 950, "gate_rfc", size=8, mono=False, fill=SB)

f.caption(40, 1190, "N_RANKS full lanes (ingress -> L2) fan into ONE L3 cap; the "
                    "scoreboard is SPLIT by arb level - bank / BG / rank+global "
                    "timing regs, each with its own UPDATE - feeding can_* to its "
                    "tier; one shared back-end drives DFI and returns data to CIF.")

f.save("fig_mcc_block.svg")
print("wrote fig_mcc_block.svg")
