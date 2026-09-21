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
f.note(40, 58, "Two up-counters per aw_id: gen_idx (nth packet -> addr offset) + done_cnt "
               "(wr_done -> retire at ==N). N=aw_len stored ONCE. No fill bit (up-count self-guards).")

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
f.text(466, 240, "offset = w_phy_adr + gen_idx*64B", size=11)
f.text(466, 260, "gen_idx = the nth packet (from tracker)", size=10, mono=False, fill=MUTED)
f.text(466, 280, "walks 0..N-1; N from meta.aw_len", size=10, mono=False, fill=MUTED)

# packet generator
f.line(630, 296, 630, 340, arrow=True)
f.path("M406 242 H430 V370 H448", arrow=True)
cnote(412, 360, "idx, vld")
f.rect(450, 340, 360, 60, fill=FILL_LOGIC, width=W_CELL)
f.text(630, 336, "wr_packet_genator", size=12, anchor="middle", fill=MUTED)
f.text(466, 374, "emit N packets {idx, wr_ptr, offset_addr}", size=11)
f.line(810, 370, 866, 370, arrow=True)
f.block(866, 340, 200, 60, "WD_SRAM -> MC", "WR_ACCUM (fig_47)")

# ---------------- THE MERGED TRACKER (two up-counters, N once) ----------------
f.rect(300, 470, 480, 172, fill=FILL_NEW, width=W_CELL)
f.text(540, 494, "WRITE TRACKER  (per aw_id / idx)", size=13, anchor="middle", bold=True)
# mini header + example row: vld | N | gen_idx | done_cnt
hdr = [("vld", 322, 55), ("N", 390, 55), ("gen_idx", 460, 95), ("done_cnt", 578, 95)]
for nm, x, w in hdr:
    f.text(x + w / 2, 522, nm, size=11, mono=False, anchor="middle")
    f.rect(x, 530, w, 26, width=W_CELL)
for val, x, w in [("1", 322, 55), ("5", 390, 55), ("3", 460, 95), ("2", 578, 95)]:
    f.text(x + w / 2, 548, val, size=12, anchor="middle")
cnote(688, 548, "(gen 3, done 2)")
f.text(316, 586, "N        = packet count from aw_len  (stored ONCE, at alloc)", size=10, mono=False)
f.text(316, 604, "gen_idx  ++ per packet issued  -> addr offset = base + gen_idx*64B", size=10, mono=False)
f.text(316, 622, "done_cnt ++ per wr_done        -> RETIRE when done_cnt == N", size=10, mono=False)

# gen_idx -> address offset (up to pkt gen)
f.path("M300 530 H250 V400", arrow=True, dashed=True)
cnote(150, 470, "gen_idx -> addr offset (nth packet)")
# done_cnt <- write_rob
f.block(870, 500, 200, 60, "write_rob", "per-pkt {vld, wr_done}")
f.line(868, 542, 782, 542, arrow=True, dashed=True)
cnote(792, 534, "++ done_cnt (wr_done)")

# retire out
f.line(540, 642, 540, 690, arrow=True)
f.text(550, 672, "RETIRE = (done_cnt == N)", size=11, mono=False)
f.text(550, 690, "-> mc_resp ; free tcam / ROB entry", size=11, mono=False, fill=MUTED)

# up-count note
f.text(316, 662, "done_cnt counts UP to N -> no mid-fill hazard (beats net==0, no fill bit)",
       size=10, mono=False, bold=True, fill="#1a7a3a")

# MERGED note (top-right)
f.rect(880, 80, 350, 108, fill=PAPER, stroke=FAINT, width=W_CELL)
f.text(896, 104, "MERGED (was aw_len x2):", size=11, mono=False, bold=True)
cnote(896, 124, "old pkt_offset.count (inflow) -> gen_idx")
cnote(896, 140, "old return_tracker.count (outflow) -> done_cnt")
cnote(896, 156, "both compare to N; N (=aw_len) stored ONCE")
cnote(896, 172, "no fill_done: done_cnt UP to N is self-guarding")

f.caption(40, 770,
          "aw_len -> N stored once (in the tracker row / meta). WRITE TRACKER per aw_id holds "
          "{vld, N, gen_idx, done_cnt}: gen_idx gives the nth-packet addr offset and stops gen "
          "at N; done_cnt counts wr_done and retires at ==N. Two up-counters vs one N - no "
          "double aw_len, and no fill bit needed (up-count is self-guarding).")

f.save("fig_48_write_tracker.svg")
print("wrote fig_48_write_tracker.svg")
