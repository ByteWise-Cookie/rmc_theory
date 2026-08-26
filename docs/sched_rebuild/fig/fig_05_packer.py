from rtlfig import Fig, MUTED, FILL_CELL, FILL_ACTIVE, FILL_NEW

# fig_05 — phase packer.
# Invariant: 4 phases available at 1:4, but DQ allows <=1 CAS per 8 CK, so a
# bundle is 1 CAS + 1 ACT + fill PRE; next CAS is two mc_clks later, diff BG.

f = Fig(1160, 720)

# ---------------- candidates in ----------------
f.logic(80, 78, 300, 92, "tier-3 ranked candidates", top=True)
f.text(96, 122, "{cmd, bg, bank, rob_index, width}", size=11)
f.text(96, 144, "ranked: timing distance + hit-bias", size=11, mono=False,
       fill=MUTED)
f.line(230, 170, 230, 212, arrow=True)

# ---------------- packer ----------------
f.logic(80, 212, 300, 188, "phase_packer   (gear 1:N)", top=True)
ry = 250
for ln in ["fill phase[0..N-1] greedily:",
           "- CA slot: 2-cyc cmd = 2 phases",
           "- <= 1 CAS / 8 CK   (dqFree)",
           "- >= 2 live BG: alternate CAS BG",
           "- losers spill -> next mc_clk"]:
    f.text(100, ry, ln, size=11, mono=False, fill=(MUTED if ln[0] == "-" else "#000000"))
    ry += 27

f.line(230, 400, 230, 470, arrow=True)
f.slash(230, 435, "N phases")
f.text(230, 492, "->  DFI cmd (dfi_address/cs per phase)", size=12,
       mono=False, anchor="middle")

# FSM-update pulse back to scoreboard
f.path("M380 300 L470 300 L470 560 L560 560", arrow=True, dashed=True)
f.text(475, 548, "cmd_issued -> update deadlines (fig_04)", size=10,
       mono=False, fill=MUTED)

# ---------------- phase bundle grid (hero) ----------------
f.note(560, 96, "phase bundle @ 1:4    (1 mc_clk = 4 CK = 4 phases)")
for k, cxk in enumerate((608, 704, 800, 896)):
    f.text(cxk, 122, f"phase {k}", size=10, mono=False, anchor="middle",
           fill=MUTED)

# mc_clk T : 1 CAS (BG0) + 1 ACT (BG3)
f.cells(560, 132, 4, 96, 52, ["RD", "RD", "ACT", "ACT"],
        fills=[FILL_ACTIVE, FILL_ACTIVE, FILL_NEW, FILL_NEW])
f.text(548, 162, "mc_clk T", size=11, anchor="end")
f.text(656, 204, "BG0  (1 CAS)", size=10, mono=False, anchor="middle", fill=MUTED)
f.text(848, 204, "BG3  (1 ACT)", size=10, mono=False, anchor="middle", fill=MUTED)

# mc_clk T+1 : fill only, no CAS
f.cells(560, 224, 4, 96, 52, ["PRE", ".", ".", "."],
        fills=[FILL_CELL, None, None, None])
f.text(548, 254, "mc_clk T+1", size=11, anchor="end")
f.text(700, 296, "no CAS until CK 8  (DQ still busy)", size=10, mono=False,
       anchor="middle", fill=MUTED)

# mc_clk T+2 : next CAS, different BG
f.cells(560, 316, 4, 96, 52, ["RD", "RD", ".", "."],
        fills=[FILL_ACTIVE, FILL_ACTIVE, None, None])
f.text(548, 346, "mc_clk T+2", size=11, anchor="end")
f.text(656, 388, "next CAS, different BG", size=10, mono=False,
       anchor="middle", fill=MUTED)

# 8-CK heartbeat bracket between the two CAS rows
f.path("M984 158 L1010 158 L1010 342 L984 342", arrow=False)
f.text(1022, 254, "8 CK", size=12, mono=False)
f.text(1022, 272, "tCCD_S", size=10, mono=False, fill=MUTED)
f.text(1022, 288, "DQ heartbeat", size=10, mono=False, fill=MUTED)

f.caption(40, 700, "At 1:4 the packer fills 4 phases, but the DQ allows <= 1 CAS "
                   "per 8 CK - so a bundle is 1 CAS + 1 ACT + fill PRE, and the "
                   "next CAS lands two mc_clks later in a different BG.")

f.save("fig_05_packer.svg")
print("wrote fig_05_packer.svg")
