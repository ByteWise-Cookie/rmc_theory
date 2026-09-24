from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_66 — refresh interval: industry down-counter vs our GC-slice compare.
# Full technical reference: tREFI=9360, bit indices, MSB/LSB, which bits toggle,
# resolution, exact-add, debt, force. Reference to draw your own.

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1360, 1000)


def dec(cx, cy, w, h, t):
    f.decision(cx, cy, w, h, t)


f.text(40, 32, "Refresh interval: down-counter  vs  GC-slice compare  (why both work)",
       size=15, mono=False, bold=True)

# ---------- params box ----------
f.rect(940, 60, 380, 180, fill=PAPER, width=1.4, stroke=INK)
f.text(1130, 84, "PARAMS (DDR5-4800)", size=11, anchor="middle", bold=True)
pp = ["tREFI   = 9360 CK   (3.9us / tCK 0.4167)",
      "9360b   = 10_0100_1001_0000  (bits 13,10,7,4)",
      "LO = clog2(tREFI)-6 = 7   (res 2^7=128 CK)",
      "HI = clog2(tREFI)+2 = 16  (wrap 2^16=64k>4x)",
      "slice  = GC[16:7]  W=10b  (MSB..LSB)",
      "debt = 3b (0..7)   force = &debt (==7)",
      "temp 2x: tREFI>>1 = 4680 ; 4x: 2340"]
for i, s in enumerate(pp):
    f.text(952, 108 + i * 18, s, size=9, mono=True)

# =============== Panel A : down-counter ===============
f.text(40, 90, "A.  down-counter  (CHOSEN - textbook, zero bit-math)", size=13,
       mono=False, bold=True)
f.text(600, 90, "<= LOCKED", size=12, mono=True, bold=True, fill=CMP)
f.block(60, 120, 200, 60, "refi_cnt (14b)", "load 9360")
f.text(70, 200, "2^14=16384 >= 9360", size=8, mono=True, fill=MUTED)
f.line(160, 180, 160, 230, arrow=True)
f.text(168, 210, "-= gear / mc_clk", size=8, mono=True, fill=MUTED)
dec(160, 260, 90, 40, "==0 ?")
f.line(205, 260, 360, 260, arrow=True)
f.text(230, 250, "tick", size=9, mono=True, fill=CMP)
# reload loop
f.path("M160 280 V330 H60 V150 H60", arrow=True, dashed=True, stroke=MUTED)
f.text(70, 325, "reload 9360", size=8, mono=True, fill=MUTED)
f.text(60, 380, "exact by construction. no compare, no drift, no LSB/wrap edge. 14b + 3b debt "
       "= 17b. reload += tREFI (constant step, NOT a <<1 - shift = geometric = misses refresh).",
       size=9, mono=False, fill=MUTED)

# =============== Panel B : GC-slice ===============
f.text(40, 450, "B.  GC-slice compare  (reuse the 24b GC, add-exact / compare-coarse)",
       size=13, mono=False, bold=True)
f.block(60, 490, 200, 56, "global_counter_24b", "+= gear / mc_clk")

# bit ruler
RX, RY, BW = 60, 590, 48
f.text(60, 578, "GC bit ruler  (bit 23 = MSB ... bit 0 = LSB)", size=9, mono=False, fill=MUTED)
for i in range(24):
    b = 23 - i
    x = RX + i * BW
    if 7 <= b <= 16:
        fill, note = FILL_ACTIVE, "slice"
    elif b <= 6:
        fill, note = FILL_LOGIC, "ignored"
    else:
        fill, note = PAPER, "unused"
    f.rect(x, RY, BW, 40, fill=fill, width=1.0)
    f.text(x + BW / 2, RY + 25, str(b), size=9, anchor="middle", bold=(7 <= b <= 16))
# brackets
f.text(RX + 8 * BW, RY - 6, "HI=16  <--- compare GC[16:7] (W=10) --->  LO=7", size=9,
       mono=True, fill=CMP)
f.text(RX + 18.5 * BW, RY + 62, "GC[6:0] dropped in compare", size=8, mono=True, fill=MUTED)
f.text(RX + 18.5 * BW, RY + 76, "= 128 CK resolution", size=8, mono=True, fill=MUTED)
f.text(RX + 1.2 * BW, RY + 62, "not needed for ref window", size=8, mono=True, fill=MUTED)

# ref_ts + compare
f.block(60, 730, 200, 56, "ref_ts (24b)", "deadline reg")
dec(430, 700, 110, 44, ">=")
f.text(430, 668, "GC[16:7] >= ref_ts[16:7]", size=9, mono=True, anchor="middle", fill=CMP)
f.line(260, 640, 378, 700, arrow=True, stroke=CMP)
f.text(300, 665, "GC[16:7]", size=8, mono=True, fill=CMP)
f.line(260, 758, 382, 715, arrow=True)
f.text(300, 752, "ref_ts[16:7]", size=8, mono=True, fill=MUTED)
f.line(490, 700, 620, 700, arrow=True, stroke=CMP)
f.text(540, 690, "hit", size=9, mono=True, fill=CMP)

# on hit: ref_ts += 9360 (full add)
f.rect(430, 780, 260, 60, fill=FILL_NEW, width=W_CELL)
f.text(560, 804, "on hit: ref_ts += tREFI", size=10, mono=True, anchor="middle", bold=True)
f.text(560, 824, "FULL 24b add (carries low bits) -> no drift", size=8, mono=True,
       anchor="middle", fill=MUTED)
f.path("M560 780 V748 ", arrow=True, dashed=True, stroke=MUTED)
f.path("M620 780 H720 V760 H265 V786", arrow=True, dashed=True, stroke=MUTED)

# =============== shared: debt + force ===============
f.counter(760, 300, 34, "debt", "3b sat7")
f.line(360, 260, 726, 290, arrow=True, stroke=CMP)          # A tick -> debt
f.line(620, 700, 740, 330, arrow=True, stroke=CMP)          # B hit -> debt
f.text(700, 260, "tick/hit -> debt++", size=9, mono=True, fill=CMP)
f.logic(870, 278, 120, 44, "&debt", "==7", top=True)
f.line(794, 300, 868, 300, arrow=True)
f.line(990, 300, 1060, 300, arrow=True, stroke=ME)
f.text(1066, 296, "ref_pending (force)", size=10, mono=True, fill=ME)
f.text(760, 360, "debt=3b -> force@7 keeps it < 8-cap (JEDEC postpone)", size=8,
       mono=False, anchor="middle", fill=MUTED)

# ---------- why it works ----------
f.rect(60, 880, 1240, 90, fill=PAPER, width=1.4, stroke=INK)
f.text(80, 904, "WHY B WORKS", size=11, bold=True)
f.text(80, 926, "1. ADD is exact (ref_ts += full 9360) -> the deadline never drifts, "
        "no matter how coarse the compare.", size=9, mono=False)
f.text(80, 944, "2. COMPARE is truncated (drop low 7) -> hit fires <=128 CK EARLY of the exact "
        "deadline, ONCE (remainder varies per interval, 9360 mod 128 = 16 -> no pile-up).", size=9)
f.text(80, 962, "3. Reuses the 24b GC (no 2nd counter) + a ref_ts reg + a 10b compare. A vs B = "
        "wash in gates; B avoids a free-running counter, A avoids bit-math.", size=9)

f.save("fig_66_refi_counter_compare.svg")
print("wrote fig_66_refi_counter_compare.svg")
