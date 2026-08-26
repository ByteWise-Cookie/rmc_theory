from rtlfig import Fig, MUTED, FILL_CELL, FILL_ACTIVE

# fig_06 — RL/WL data streaming: accumulator (read) + splitter (write).
# Invariant: one 512b SRAM access per packet; the accumulator/splitter are the
# only blocks that know the gear ratio - the RAMs stay ratio-agnostic.

f = Fig(1180, 700)

# ---------------- the gear boundary ----------------
f.line(720, 60, 720, 566, dashed=True, stroke=MUTED)
f.text(400, 50, "SRAM side  -  512b wide, ratio-agnostic", size=11,
       mono=False, anchor="middle", fill=MUTED)
f.text(980, 50, "DFI side  -  2*gear beats / mc_clk", size=11,
       mono=False, anchor="middle", fill=MUTED)

# ---------------- arm from packer ----------------
f.text(300, 118, "from packer @ CAS-commit", size=11, mono=False)
f.text(300, 136, "{op, tag, sram_addr}", size=11)
f.path("M430 114 L520 114 L520 86 L598 86", arrow=True)
f.text(548, 78, "if RD", size=10, mono=False, fill=MUTED)
f.path("M430 140 L520 140 L520 406 L598 406", arrow=True)
f.text(548, 398, "if WR", size=10, mono=False, fill=MUTED)

# ================= READ path (top) =================
f.rect(120, 150, 160, 66, fill=FILL_CELL, width=1.4)
f.text(200, 178, "RD_SRAM", size=13, anchor="middle")
f.text(200, 196, "512b / line", size=10, mono=False, anchor="middle", fill=MUTED)

f.cells(600, 66, 5, 46, 40)
f.text(600, 56, "RL_line   depth = CL", size=11)
f.text(830, 100, "{rob_index, dbuf_addr}", size=10, mono=False, fill=MUTED)
f.line(720, 106, 720, 148, arrow=True)
f.text(732, 130, "fire @ slot 0", size=10, mono=False, fill=MUTED)

f.logic(600, 148, 240, 84, "read_accumulator", "deserialize -> gather 64B")

f.line(598, 183, 284, 183, arrow=True)
f.slash(440, 183, "512b")
f.text(440, 172, "1 x 512b write @ dbuf_addr", size=10, mono=False,
       anchor="middle", fill=MUTED)

f.line(1090, 183, 842, 183, arrow=True)
f.slash(960, 183, "2*gear")
f.text(966, 172, "dfi_rddata", size=11)
f.text(720, 258, "last beat committed -> rd_done", size=10, mono=False,
       anchor="middle", fill=MUTED)

# ================= WRITE path (bottom) =================
f.rect(120, 470, 160, 66, fill=FILL_CELL, width=1.4)
f.text(200, 498, "WD_SRAM", size=13, anchor="middle")
f.text(200, 516, "512b / line", size=10, mono=False, anchor="middle", fill=MUTED)

f.cells(600, 386, 5, 46, 40)
f.text(600, 376, "WL_line   depth = CWL", size=11)
f.text(830, 420, "{wd_slot}", size=10, mono=False, fill=MUTED)
f.line(720, 426, 720, 468, arrow=True)
f.text(732, 450, "fire @ slot 0", size=10, mono=False, fill=MUTED)

f.logic(600, 468, 240, 84, "write_burst_splitter", "512b -> serialize")

f.line(284, 503, 598, 503, arrow=True)
f.slash(440, 503, "512b")
f.text(440, 492, "1 x 512b read @ wd_slot", size=10, mono=False,
       anchor="middle", fill=MUTED)

f.line(842, 503, 1090, 503, arrow=True)
f.slash(966, 503, "2*gear")
f.text(966, 492, "dfi_wrdata", size=11)
f.text(720, 578, "last beat driven -> wr_done  (self-timed, no ack)", size=10,
       mono=False, anchor="middle", fill=MUTED)

# completion note
f.text(1090, 640, "rd_done | wr_done  ->  completion  ->  CIF", size=11,
       mono=False, anchor="end", fill=MUTED)

f.caption(40, 686, "One 512b SRAM access per packet. The accumulator and "
                   "splitter are the ONLY blocks that know the gear ratio - the "
                   "RAMs stay ratio-agnostic.")

f.save("fig_06_datapath.svg")
print("wrote fig_06_datapath.svg")
