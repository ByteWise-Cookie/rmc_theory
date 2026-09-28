from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_83 - clean write-launch datapath. 1 delay line (latency) + 1 burst counter
# (duration) replace the 3 compare-counters. Burst counter = single owner of
# beat position: drives wr_en window, WD_SRAM index, wr_done.

LAT = "#7a4fb0"   # latency / delay-line
DUR = "#2a8f86"   # duration / burst counter
GR  = "#b0602a"   # gear
f = Fig(1500, 840)


def port(x, y, name, fill=PAPER):
    f.rect(x, y-14, 150, 28, fill=fill, width=1.4, rx=4)
    f.text(x+8, y+4, name, size=9, mono=True)


f.text(40, 30, "Write-launch datapath  (1 delay line + 1 burst counter)", size=15,
       mono=False, bold=True)

# ---- write_handler ----
f.block(50, 150, 150, 66, "write_handler", "issue: launch pulse")
f.line(200, 183, 268, 183, arrow=True, stroke=INK)
f.text(206, 176, "launch", size=8, mono=True, fill=INK)

# ---- WL delay line ----
f.block(270, 138, 250, 112, "WL_DELAY_LINE", "shift reg, self-pop")
f.text(282, 236, "taps: en@tphy_wrlat, data@wrlat+wrdata", size=8, mono=True, fill=LAT)
# inputs from below
for i, (lab, col) in enumerate([("tphy_wrlat", LAT), ("tphy_wrdata", LAT), ("wd_slot", DUR)]):
    xx = 300 + i*80
    f.line(xx, 330, xx, 250, arrow=True, stroke=col)
    f.text(xx-24, 346, lab, size=8, mono=True, fill=col)

# taps out
f.line(520, 165, 618, 165, arrow=True, stroke=LAT)
f.text(528, 158, "en_tap", size=8, mono=True, fill=LAT)
f.path("M520 222 L575 222 L575 470 L618 470", arrow=True, stroke=LAT)
f.text(528, 214, "data_tap", size=8, mono=True, fill=LAT)

# ---- burst counter ----
f.block(620, 128, 190, 78, "BURST_CNT", "load BL/2>>gear ; -1/cyc")

# wr_en -> gear AND
f.line(810, 150, 888, 150, arrow=True, stroke=DUR)
f.text(816, 143, "wr_en=(cnt!=0)", size=8, mono=True, fill=DUR)

# index -> WD_SRAM (dashed, down the right of gear_cfg)
f.path("M790 206 L840 206 L840 462 L888 462", arrow=True, dashed=True, stroke=DUR)
f.text(846, 300, "index", size=8, mono=True, fill=DUR)

# done -> wr_done
f.path("M700 206 L700 250 L1050 250 L1050 300 L1118 300", arrow=True, stroke=DUR)
f.text(900, 243, "cnt==0", size=8, mono=True, fill=DUR)

# ---- gear cfg ----
f.block(620, 300, 190, 60, "gear_cfg_reg", "gear_mask + shift")
f.path("M715 300 L715 208", arrow=True, stroke=GR)        # shift/target up to burst
f.text(660, 285, "shift 8/4/2", size=8, mono=True, fill=GR)
f.path("M810 330 L953 330 L953 194", arrow=True, stroke=GR)  # mask to gear AND
f.text(858, 322, "mask", size=8, mono=True, fill=GR)

# ---- gear AND ----
f.logic(888, 128, 130, 78, "& gear_mask", "spatial width", top=True)
# 4 phase enables out
for i in range(4):
    yy = 132 + i*22
    f.line(1018, 150, 1118, 132+i*24, arrow=True, stroke=INK)
port(1118, 132, "dfi_wr_en_p0", FILL_NEW)
port(1118, 168, "dfi_wr_en_p1", FILL_NEW)
port(1118, 204, "dfi_wr_en_p2", FILL_NEW)
port(1118, 240, "dfi_wr_en_p3", FILL_NEW)
port(1118, 300, "wr_done", FILL_ACTIVE)

# ---- WD_SRAM -> WR_SPLIT -> wrdata ----
f.block(620, 430, 190, 66, "WD_SRAM", "512b line @ wd_slot")
f.line(810, 463, 888, 463, arrow=True, stroke=INK)
f.text(816, 456, "512b", size=8, mono=True, fill=INK)
f.block(888, 430, 150, 66, "WR_SPLIT", "512b -> 2*DQ/phase")
for i in range(4):
    f.line(1038, 463, 1118, 420+i*30, arrow=True, stroke=INK)
port(1118, 420, "dfi_wrdata_p0", FILL_CELL)
port(1118, 456, "dfi_wrdata_p1", FILL_CELL)
port(1118, 492, "dfi_wrdata_p2", FILL_CELL)
port(1118, 528, "dfi_wrdata_p3", FILL_CELL)

# ---- legend ----
f.rect(40, 560, 1000, 150, fill=PAPER, width=1.4, stroke=INK)
f.text(56, 584, "two axes, kept separate:", size=11, bold=True)
f.text(56, 608, "LATENCY (when)  = WL_DELAY_LINE, fixed depth, self-pop. two taps: en @ tphy_wrlat, "
       "data @ tphy_wrlat+tphy_wrdata.", size=9, mono=True, fill=LAT)
f.text(56, 630, "DURATION (how many) = BURST_CNT, load BL/2>>gear (1:1=8, 1:2=4, 1:4=2), -1/cyc. "
       "wr_en=(cnt!=0). drives en + SRAM index + done.", size=9, mono=True, fill=DUR)
f.text(56, 652, "SPATIAL width = gear_mask (1:1=1000, 1:2=1100, 1:4=1111). dfi_wr_en_pN = "
       "burst_active & mask[N].", size=9, mono=True, fill=GR)
f.text(56, 678, "read side mirrors: RD_ACCUM counts dfi_rddata_valid beats to BL/2 -> 512b line -> "
       "rd_done. same counter, opposite dir.", size=9, mono=False, fill=MUTED)

f.caption(40, 740,
          "3 compare-counters -> 1 delay line (latency) + 1 burst counter (duration). Burst counter "
          "= single source of beat position: holds wr_en, indexes WD_SRAM/WR_SPLIT, fires wr_done. "
          "Gear mask = spatial phases; burst count = temporal length.")

f.save("fig_83_wr_launch.svg")
print("wrote fig_83_wr_launch.svg")
