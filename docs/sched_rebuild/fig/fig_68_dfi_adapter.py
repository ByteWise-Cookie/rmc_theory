from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_68 — post-phaser DFI adapter (DDR5). PHASER bundle -> DFI_CMD_ENCODE / data
# lines -> DFI_MUX -> PHY. All in dfi_clk==mc_clk (=CK/GEAR); _pN phases spatial.

CMD = "#7a4fb0"; DATA = "#2a8f86"; CTRL = "#b0602a"; GREEN = "#3d8c40"
f = Fig(1580, 1020)


def blk(x, y, w, h, name, sub, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + w / 2, y + 22, name, size=11, anchor="middle", bold=True)
    if sub:
        f.text(x + w / 2, y + 40, sub, size=8, anchor="middle", fill=MUTED)


f.text(40, 32, "Post-phaser DFI adapter  (DDR5, DFI 5.2)", size=15, mono=False, bold=True)

# clock band
f.rect(300, 95, 900, 855, fill="none", width=1.2, stroke=FAINT)
f.text(310, 112, "dfi_clk == mc_clk  (= CK/GEAR)  .  _pN phases = spatial (N buses/edge), "
       "PHY serializes to CK", size=9, mono=False, fill=GREEN)

# ---- PHASER (upstream boundary) ----
blk(60, 300, 180, 300, "PHASER", "", FILL_ACTIVE)
f.text(150, 340, "placed bundle", size=9, mono=True, anchor="middle")
f.text(150, 356, "phase[0..N-1]", size=8, mono=True, anchor="middle", fill=MUTED)
f.text(150, 430, "CAS-W commit", size=9, mono=True, anchor="middle")
f.text(150, 446, "{op,rob,wd_slot}", size=8, mono=True, anchor="middle", fill=MUTED)
f.text(150, 520, "RD commit", size=9, mono=True, anchor="middle")
f.text(150, 536, "{op,rob,dbuf}", size=8, mono=True, anchor="middle", fill=MUTED)

# ---- MAINT / FREQ FSM (sideband source) ----
blk(60, 120, 300, 60, "MAINT / FREQ-CHANGE FSM", "control-clk sideband", FILL_LOGIC)

# ---- command encode + init ----
blk(320, 150, 210, 80, "DFI_CMD_ENCODE", "bundle -> CA beats + CS", FILL_NEW)
blk(320, 270, 210, 70, "INIT_FSM (CA)", "drives CA during init")
f.line(240, 340, 318, 200, arrow=True, stroke=CMD)     # phaser bundle -> encode
f.text(250, 250, "bundle", size=8, mono=True, fill=CMD)

# ---- DFI_MUX ----
f.path("M600 160 L648 175 L648 335 L600 350 Z", stroke=INK)
f.text(624, 258, "DFI", size=9, anchor="middle", bold=True)
f.text(624, 272, "MUX", size=9, anchor="middle", bold=True)
f.line(530, 190, 600, 200, arrow=True, stroke=CMD)     # encode -> mux
f.line(530, 300, 600, 300, arrow=True)                 # init -> mux
f.text(560, 250, "sel = dfi_init_complete", size=8, mono=True, fill=MUTED)
f.line(624, 335, 624, 360, arrow=True, dashed=True, stroke=MUTED)
f.text(624, 375, "init_complete", size=8, mono=True, anchor="middle", fill=MUTED)

# ---- WRITE data path ----
blk(320, 420, 210, 80, "WL_LAUNCH", "arm tphy_wrlat @ CAS-W", FILL_NEW)
blk(600, 420, 160, 80, "WR_SPLIT", "512b -> gear beats")
blk(60, 660, 180, 60, "WD_SRAM", "", FILL_CELL)
f.line(240, 440, 318, 450, arrow=True, stroke=DATA)    # phaser CAS-W -> WL
f.line(240, 660, 318, 480, arrow=True, stroke=DATA)    # WD_SRAM -> WL (read)
f.text(250, 600, "wd_slot", size=8, mono=True, fill=DATA)
f.line(530, 460, 600, 460, arrow=True, stroke=DATA)

# ---- READ data path ----
blk(320, 560, 210, 80, "RD_CAP", "arm tphy_rdlat @ RD", FILL_NEW)
blk(600, 560, 160, 80, "RD_ACCUM", "beats -> 512b line")
blk(860, 660, 180, 60, "RD_SRAM", "", FILL_CELL)
f.line(240, 540, 318, 590, arrow=True, stroke=DATA)    # phaser RD -> RD_CAP
f.line(760, 620, 858, 665, arrow=True, stroke=DATA)    # accum -> RD_SRAM
f.text(600, 545, "dfi_rddata_en", size=8, mono=True, fill=DATA)

# ---- ALERT / ERR ----
blk(320, 690, 210, 66, "ALERT / ERR mon", "alert_n / error", FILL_LOGIC)

# ---- PHY / DRAM ----
blk(1050, 200, 130, 620, "PHY", "", FILL_ACTIVE)
blk(1280, 430, 120, 160, "DRAM", "", FILL_CELL)
f.line(1180, 500, 1278, 500, arrow=True)
f.text(1215, 490, "CK", size=8, mono=True, fill=MUTED)

# ---- DFI signals to/from PHY ----
def sig(y, txt, col, indir=False):
    if indir:
        f.line(1050, y, 765, y, arrow=True, stroke=col)
    else:
        f.line(765, y, 1050, y, arrow=True, stroke=col)
    f.text(770, y - 5, txt, size=8, mono=True, fill=col)

# command bus out of mux -> PHY
f.line(648, 255, 1050, 255, arrow=True, stroke=CMD)
f.text(770, 248, "dfi_address_pN, dfi_cs_pN, cke/odt/reset_n", size=8, mono=True, fill=CMD)
# write out
f.line(760, 460, 1050, 460, arrow=True, stroke=DATA)
f.text(770, 453, "dfi_wrdata_en/_pN, wrdata_pN, mask_pN", size=8, mono=True, fill=DATA)
# rddata_en out
f.line(530, 600, 1050, 600, arrow=True, stroke=DATA)
f.text(770, 593, "dfi_rddata_en_pN", size=8, mono=True, fill=DATA)
# rddata in
f.line(1050, 640, 762, 640, arrow=True, stroke=DATA)
f.text(770, 633, "dfi_rddata_wN, dfi_rddata_valid_wN  (in)", size=8, mono=True, fill=DATA)
# alert in
f.line(1050, 720, 532, 720, arrow=True, stroke=CTRL)
f.text(770, 713, "dfi_alert_n / dfi_error  (in)", size=8, mono=True, fill=CTRL)

# ---- sideband control-clk out ----
f.line(360, 150, 360, 140, arrow=False)
f.path("M210 180 V880 H1050", arrow=True, stroke=CTRL, dashed=True)
f.text(500, 872, "dfi_init_start/complete, cmd/data_freq_ratio, freq_fsp, ctrlupd_*, phyupd_*  "
       "(control-clk sideband, from MAINT/FREQ FSM)", size=8, mono=False, fill=CTRL)

# ---- completion note ----
f.text(600, 528, "RD_ACCUM/WL_LAUNCH -> COMPLETION -> resp AFIFO (tag-only)", size=8,
       mono=False, fill=MUTED)

f.caption(40, 990,
          "PHASER bundle -> DFI_CMD_ENCODE (CA beats + CS per phase) -> DFI_MUX (init override, "
          "sel=init_complete) -> PHY. Write: CAS-W commit arms WL_LAUNCH (tphy_wrlat), WR_SPLIT "
          "streams WD_SRAM as gear beats + dfi_wrdata_en. Read: RD commit arms RD_CAP (tphy_rdlat, "
          "dfi_rddata_en), RD_ACCUM gathers dfi_rddata on _valid into RD_SRAM. All in dfi_clk==mc_clk.")

f.save("fig_68_dfi_adapter.svg")
print("wrote fig_68_dfi_adapter.svg")
