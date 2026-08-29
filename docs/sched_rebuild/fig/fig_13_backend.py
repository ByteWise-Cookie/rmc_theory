from rtlfig import Fig, MUTED, FILL_CELL, FILL_ACTIVE

# fig_13 - back-end data path (post-RANK_ARB), user's naming.
# Judged from the walk: PHASE_PACKER commits + arms; rank_arb does NOT generate
# the data meta - sram_addr rode the pipe from CIF (dbuf_addr / wd_slot). ONE
# op-code routes which line arms, but WRITE and READ are TWO CONCURRENT engines
# (RL=CL vs WL=CWL, opposite data direction, turnaround overlaps them) - never
# one time-shared block. RL/WL = deterministic shift depth = the timing (no
# timestamp, no CAM). Slots are CIF-owned; MC only signals rd_done/wr_done.

SB = "#7a5cb8"
f = Fig(1260, 790)

f.note(1250, 30, "MC back-end  -  cmd packer + data engines + completion",
       anchor="end")
f.note(1250, 46, "two concurrent engines, not one time-shared block", anchor="end")

# ---------------- gear boundary ----------------
f.line(800, 205, 800, 560, dashed=True, stroke=MUTED)
f.text(500, 196, "SRAM side  -  512b / line, gear-agnostic", size=11,
       mono=False, anchor="middle", fill=MUTED)
f.text(1000, 196, "DFI side  -  2*gear beats / mc_clk", size=11,
       mono=False, anchor="middle", fill=MUTED)

# ================= PHASE_PACKER (cmd) =================
p = f.logic(120, 70, 260, 92, "PHASE_PACKER",
            "cmd only - gear 1:N - sole commit/arm edge", top=True)
f.text(112, 116, "from RANK_ARB", size=11, mono=False, anchor="end")
f.text(112, 132, "(L3 winner)", size=11, mono=False, anchor="end")
f.line(30, 124, 118, 124, arrow=True)

# dfi_cmd out
f.line(382, 108, 540, 108, arrow=True)
f.text(540, 100, "dfi_cmd  ->  DFI_MUX", size=11, mono=False, anchor="end")

# arm bus down -> op split
f.line(250, 162, 250, 186, arrow=True)
f.text(262, 178, "{op, rob_index, sram_addr}  @ CAS-commit", size=10,
       mono=False, fill=MUTED)
f.decision(250, 214, 120, 56, "op ?")

# WR branch -> arm WL_line
f.path("M310 214 L505 214 L505 250", arrow=True)
f.text(420, 206, "WR: arm WL_line", size=10, mono=False, fill=MUTED)
# RD branch -> arm RL_line
f.path("M250 242 L250 420 L505 420", arrow=True)
f.text(262, 350, "RD: arm RL_line", size=10, mono=False, fill=MUTED)

# ================= WRITE engine (upper) =================
f.rect(110, 300, 130, 60, fill=FILL_CELL, width=1.4)
f.text(175, 326, "WD_SRAM", size=13, anchor="middle")
f.text(175, 344, "512b / line", size=10, mono=False, anchor="middle", fill=MUTED)

f.cells(505, 232, 4, 48, 38)
f.text(505, 222, "WL_line   depth = CWL", size=11)
f.line(529, 270, 529, 328, arrow=True, dashed=True)
f.text(541, 296, "fire @ slot0 -> wd_slot", size=9, mono=False, fill=MUTED)

f.logic(560, 300, 210, 62, "BURST_SPLIT", "512b -> serialize 2*gear")

f.line(240, 330, 558, 330, arrow=True)
f.slash(400, 330, "512b")
f.text(408, 318, "WR_DATA_FETCH:  1x512b read @ wd_slot", size=10,
       mono=False, anchor="middle", fill=MUTED)

f.line(772, 330, 1060, 330, arrow=True)
f.slash(920, 330, "2*gear")
f.text(928, 318, "dfi_wrdata (self-timed)", size=11)

# ================= READ engine (lower) =================
f.rect(110, 470, 130, 60, fill=FILL_CELL, width=1.4)
f.text(175, 496, "RD_SRAM", size=13, anchor="middle")
f.text(175, 514, "512b / line", size=10, mono=False, anchor="middle", fill=MUTED)

f.cells(505, 402, 4, 48, 38)
f.text(505, 392, "RL_line   depth = CL", size=11)
f.line(529, 440, 529, 498, arrow=True, dashed=True)
f.text(541, 466, "fire @ slot0 -> dbuf_addr", size=9, mono=False, fill=MUTED)

f.logic(560, 470, 210, 62, "BURST_ACC", "deserialize 2*gear -> gather 64B")

f.line(558, 500, 242, 500, arrow=True)
f.slash(400, 500, "512b")
f.text(408, 488, "RD_DATA_SEND:  1x512b write @ dbuf_addr", size=10,
       mono=False, anchor="middle", fill=MUTED)

f.line(1060, 500, 772, 500, arrow=True)
f.slash(920, 500, "2*gear")
f.text(928, 488, "dfi_rddata (+valid)", size=11)

# ================= COMPLETION + resp =================
f.logic(560, 640, 240, 74, "COMPLETION",
        "rd_done | wr_done -> {rob_index,pkt_num,status}", top=True)
# done signals in
f.path("M665 362 L665 500 L665 640", arrow=True, dashed=True, stroke=MUTED)
f.text(676, 600, "rd_done (last beat in RD_SRAM)", size=9, mono=False, fill=MUTED)
f.path("M700 362 L700 638", arrow=True, dashed=True, stroke=MUTED)
f.text(712, 420, "wr_done (self-timed, no ack)", size=9, mono=False, fill=MUTED)

f.rect(860, 652, 150, 60, fill=FILL_ACTIVE, width=1.4)
f.text(935, 676, "RESP_AFIFO", size=12, anchor="middle")
f.text(935, 694, "async out", size=9, mono=False, anchor="middle", fill=MUTED)
f.line(800, 678, 858, 678, arrow=True)
f.line(1010, 678, 1100, 678, arrow=True)
f.text(1108, 674, "=async=> CIF", size=11, mono=False)

# ALERT_n monitor stub
f.rect(1040, 560, 200, 52, fill="none", stroke=MUTED, width=1.4, dashed=True)
f.text(1140, 582, "ALERT_n MON  (stub)", size=11, anchor="middle", fill=MUTED)
f.text(1140, 598, "write-CRC/parity -> status", size=9, mono=False,
       anchor="middle", fill=MUTED)
f.path("M1100 560 L1100 330", arrow=True, dashed=True, stroke=MUTED)
f.text(1112, 450, "dfi_alert_n", size=9, mono=False, fill=MUTED)
f.path("M1040 586 L800 586 L800 677", arrow=True, dashed=True, stroke=MUTED)

# ---------------- slot-ownership note ----------------
f.text(30, 640, "SLOTS = CIF-owned:", size=11, mono=False, bold=True, fill=SB)
f.text(30, 658, "CIF allocs dbuf_addr + wd_slot, rides them in;", size=10,
       mono=False, fill=SB)
f.text(30, 674, "MC never allocs. rd_done/wr_done -> CIF drains", size=10,
       mono=False, fill=SB)
f.text(30, 690, "RD_SRAM / frees WD_SRAM slot.", size=10, mono=False, fill=SB)

f.caption(30, 770, "PHASE_PACKER arms the data line at CAS-commit with the "
                   "sram_addr that rode the pipe; WRITE (SRAM->DFI, WL=CWL) and "
                   "READ (DFI->SRAM, RL=CL) are two concurrent engines - the "
                   "op-code only routes which line arms. RL/WL depth = the timing "
                   "(no timestamp/CAM). Slots freed by CIF on done.")

f.save("fig_13_backend.svg")
print("wrote fig_13_backend.svg")
