from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_73 — write / read DFI data timing (schematic, not to scale). WL/RL lines arm
# off the CAS commit; enable/data/valid windows + latency params. burst = BL/2 = 8.

CMD = "#7a4fb0"; DATA = "#2a8f86"; ME = "#b0602a"; GREEN = "#3d8c40"
f = Fig(1560, 1000)


def sig(y, name, col=INK):
    f.text(40, y + 14, name, size=10, mono=True, fill=col)
    f.line(230, y + 24, 1500, y + 24, stroke=FAINT)   # baseline


def blk(x, w, y, label, fill, h=26):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + w / 2, y + 17, label, size=9, mono=True, anchor="middle")


def pulse(x, w, y, label, col):
    f.rect(x, y, w, 26, fill="none", width=1.6, stroke=col)
    f.text(x + w / 2, y + 17, label, size=8, mono=True, anchor="middle", fill=col)


def dim(x1, x2, y, label, col=ME):
    f.line(x1, y, x2, y, arrow=True, stroke=col)
    f.line(x2, y, x1, y, arrow=True, stroke=col)
    f.text((x1 + x2) / 2, y - 4, label, size=8, mono=True, anchor="middle", fill=col)


# ================= WRITE =================
f.text(40, 32, "WRITE data timing  (schematic, burst BL/2 = 8 beats)", size=14,
       mono=False, bold=True)
y = 60
sig(y, "CA (cmd)")
blk(240, 70, y, "WR (2UI)", FILL_ACTIVE)
y2 = y + 55
sig(y2, "WL_LINE")
f.line(275, y + 26, 275, y2 + 24, arrow=True, dashed=True, stroke=DATA)
y3 = y2 + 55
sig(y3, "dfi_wrdata_en")
pulse(560, 320, y3, "en (held BL/2)", DATA)
dim(275, 560, y3 - 12, "tphy_wrlat", ME)
y4 = y3 + 55
sig(y4, "dfi_wrdata_pN")
blk(610, 320, y4, "8 x 64b  (from WD_SRAM via WR_SPLIT)", FILL_CELL)
dim(560, 610, y4 - 12, "tphy_wrdata", ME)
y5 = y4 + 55
sig(y5, "dfi_odt[rank]")
pulse(500, 460, y5, "RTT_WR window", ME)
y6 = y5 + 55
sig(y6, "DQ @ DRAM")
blk(900, 320, y6, "write data on DQ", FILL_NEW)
dim(275, 900, y6 - 12, "CWL (PHY-side)", GREEN)

# ================= READ =================
f.text(40, 540, "READ data timing", size=14, mono=False, bold=True)
ry = 568
sig(ry, "CA (cmd)")
blk(240, 70, ry, "RD (2UI)", FILL_ACTIVE)
ry2 = ry + 55
sig(ry2, "RL_LINE")
f.line(275, ry + 26, 275, ry2 + 24, arrow=True, dashed=True, stroke=DATA)
ry3 = ry2 + 55
sig(ry3, "dfi_rddata_en")
pulse(560, 320, ry3, "en (capture window)", DATA)
dim(275, 560, ry3 - 12, "tphy_rdlat", ME)
ry4 = ry3 + 55
sig(ry4, "dfi_rddata_valid")
pulse(900, 320, ry4, "valid (per beat)", DATA)
ry5 = ry4 + 55
sig(ry5, "dfi_rddata_wN")
blk(900, 320, ry5, "8 x 64b  (PHY -> MC)", FILL_CELL)
dim(275, 900, ry5 - 12, "RL = CL (PHY-side)", GREEN)
ry6 = ry5 + 55
sig(ry6, "RD_ACCUM")
blk(910, 320, ry6, "gather on valid -> 512b -> RD_SRAM", FILL_NEW)

f.caption(40, 980,
          "WRITE: WR commit arms WL_LINE (tphy_wrlat) -> dfi_wrdata_en, then dfi_wrdata_pN after "
          "tphy_wrdata (8 beats from WD_SRAM via WR_SPLIT); dfi_odt = RTT_WR window; PHY drives DQ "
          "at CWL.  READ: RD commit arms RL_LINE (tphy_rdlat) -> dfi_rddata_en; PHY returns "
          "dfi_rddata_wN + valid at RL=CL; RD_ACCUM gathers on valid -> 512b -> RD_SRAM. tphy_* = "
          "PHY params; latencies deterministic -> plain shift lines, no CAM.")

f.save("fig_73_data_timing.svg")
print("wrote fig_73_data_timing.svg")
