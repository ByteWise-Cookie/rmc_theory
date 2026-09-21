from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_48 — write tracking: ONE counter, aw_len stored once.
# Merge inflow (old pkt_offset.count) + outflow (old return_tracker.count) into
# one n_outstanding; fill_done (wlast) gates retire and replaces the 2nd aw_len.

f = Fig(1260, 800)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "Write tracking - one counter, aw_len stored ONCE", size=15,
       mono=False, bold=True)
f.note(40, 58, "Merge inflow (pkt_offset.count) + outflow (return_tracker.count) -> "
               "one n_outstanding. fill_done (wlast) gates retire, replaces the 2nd aw_len.")

# ---------------- ingress + meta ----------------
f.block(50, 95, 150, 44, "axi_write_request")
f.line(200, 117, 256, 117, arrow=True)
f.rect(256, 88, 340, 74, fill=FILL_ACTIVE, width=W_CELL)
f.text(426, 84, "wr_meta_data", size=12, anchor="middle", fill=MUTED)
f.text(272, 116, "aw_id . aw_size . aw_len . w_phy_adr", size=11)
f.text(272, 138, "aw_len stored ONCE (feeds pkt gen)", size=10, mono=False, fill=MUTED)

# tcam
f.line(330, 162, 330, 212, arrow=True)
f.block(256, 212, 150, 60, "tcam {aw_id}", "-> idx")

# pkt_offset (address only)
f.line(540, 162, 540, 212, arrow=True)
cnote(548, 190, "aw_len, w_phy_adr")
f.rect(450, 212, 360, 84, fill=FILL_LOGIC, width=W_CELL)
f.text(630, 208, "pkt_offset  (ADDRESS gen only)", size=12, anchor="middle", fill=MUTED)
f.text(466, 240, "offset = w_phy_adr + i*64B", size=11)
f.text(466, 260, "i = 0..N-1   (N from meta.aw_len)", size=10, mono=False, fill=MUTED)
f.text(466, 280, "count = transient gen index, NOT a retire total", size=10,
       mono=False, fill=MUTED)

# packet generator
f.line(630, 296, 630, 340, arrow=True)
f.path("M406 242 H430 V370 H448", arrow=True)
cnote(412, 360, "idx, vld")
f.rect(450, 340, 360, 60, fill=FILL_LOGIC, width=W_CELL)
f.text(630, 336, "wr_packet_genator", size=12, anchor="middle", fill=MUTED)
f.text(466, 374, "emit N packets {idx, wr_ptr, offset_addr}", size=11)
f.line(810, 370, 866, 370, arrow=True)
f.block(866, 340, 200, 60, "WD_SRAM -> MC", "WR_ACCUM (fig_47)")

# ---------------- THE MERGED TRACKER ----------------
f.rect(300, 470, 470, 170, fill=FILL_NEW, width=W_CELL)
f.text(535, 494, "WRITE TRACKER  (per aw_id / idx)", size=13, anchor="middle", bold=True)
# mini header + example row
f.text(330, 522, "vld", size=11, mono=False)
f.text(400, 522, "fill_done", size=11, mono=False)
f.text(520, 522, "n_outstanding", size=11, mono=False)
f.rect(322, 530, 60, 26, width=W_CELL)
f.rect(400, 530, 90, 26, width=W_CELL)
f.rect(520, 530, 120, 26, width=W_CELL)
f.text(352, 548, "1", size=12, anchor="middle")
f.text(445, 548, "0", size=12, anchor="middle")
f.text(580, 548, "2", size=12, anchor="middle")
cnote(650, 548, "(mid-fill)")
f.text(316, 584, "++ n_outstanding  <- packet in SRAM (inflow)", size=10, mono=False)
f.text(316, 602, "-- n_outstanding  <- wr_done (write_rob, outflow)", size=10, mono=False)
f.text(316, 620, "fill_done <- AXI wlast", size=10, mono=False)

# inflow ++ (from SRAM/gen)
f.path("M960 400 V440 H760 V472", arrow=True, dashed=True)
cnote(770, 458, "++ inflow (pkt landed)")
# outflow -- (write_rob)
f.block(870, 500, 200, 60, "write_rob", "per-pkt {vld, wr_done}")
f.line(868, 530, 772, 530, arrow=True, dashed=True)
cnote(786, 522, "-- wr_done")
# fill_done <- wlast
f.path("M120 139 V560 H298 V560", arrow=True, dashed=True)
cnote(130, 540, "AXI wlast -> fill_done")

# retire out
f.line(535, 640, 535, 690, arrow=True)
f.text(545, 672, "RETIRE = fill_done & n_outstanding==0", size=11, mono=False)
f.text(545, 690, "-> mc_resp ; free tcam / ROB entry", size=11, mono=False, fill=MUTED)

# BUG note
f.text(316, 662, "n==0 ALONE false-retires mid-fill -> fill_done MANDATORY", size=10,
       mono=False, bold=True, fill="#c0392b")

# MERGED note (top-right)
f.rect(880, 80, 340, 90, fill=PAPER, stroke=FAINT, width=W_CELL)
f.text(896, 104, "MERGED (was stored twice):", size=11, mono=False, bold=True)
cnote(896, 124, "old pkt_offset.count  (inflow target)")
cnote(896, 140, "+ old return_tracker.count (outflow target)")
cnote(896, 158, "=> one n_outstanding; aw_len no longer duplicated")

f.caption(40, 770,
          "aw_len lives once in wr_meta_data (pkt gen only). One WRITE TRACKER per aw_id "
          "holds {vld, fill_done, n_outstanding}: ++ on inflow, -- on wr_done, retire when "
          "fill_done & n==0. pkt_offset does address gen only. No double aw_len; mid-fill "
          "early-retire fixed by fill_done.")

f.save("fig_48_write_tracker.svg")
print("wrote fig_48_write_tracker.svg")
