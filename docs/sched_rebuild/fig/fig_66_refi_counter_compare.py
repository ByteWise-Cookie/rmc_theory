from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_66 — refresh interval: 14b down-counter + 3b debt (LOCKED). GC-slice dropped.

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1240, 620)


def dec(cx, cy, w, h, t):
    f.decision(cx, cy, w, h, t)


f.text(40, 34, "Refresh interval - 14b down-counter + 3b debt  (LOCKED)", size=15,
       mono=False, bold=True)

# params
f.rect(830, 70, 380, 175, fill=PAPER, width=1.4, stroke=INK)
f.text(1020, 94, "PARAMS", size=11, anchor="middle", bold=True)
pp = ["tREFI = 9360 CK  (DDR5-4800, 3.9us)",
      "refi_cnt = 14b   (2^14=16384 >= 9360)",
      "debt = 3b (0..7) ; force = &debt (==7)",
      "{debt[2:0], refi_cnt[13:0]} = 17b total",
      "temp 2x: += tREFI>>1 = 4680 ; 4x: 2340",
      "DDR4: 12480  DDR3: 6240  DDR2: 3120",
      "DDR1: 1560  (reload const per bin)"]
for i, s in enumerate(pp):
    f.text(844, 118 + i * 18, s, size=9, mono=True)

# down-counter datapath
f.block(60, 110, 220, 60, "refi_cnt (14b)", "load tREFI")
f.line(170, 170, 170, 220, arrow=True)
f.text(178, 200, "-= gear / mc_clk", size=8, mono=True, fill=MUTED)
dec(170, 260, 90, 44, "<= 0 ?")
f.line(215, 260, 380, 260, arrow=True, stroke=CMP)
f.text(250, 248, "tick", size=9, mono=True, fill=CMP)
# reload loop
f.path("M170 282 V340 H60 V140 H60", arrow=True, dashed=True, stroke=MUTED)
f.text(70, 335, "reload += tREFI (constant step)", size=8, mono=True, fill=MUTED)

# debt
f.counter(470, 260, 36, "debt", "3b sat7")
f.text(360, 232, "tick -> debt++", size=9, mono=True, fill=CMP)
f.text(360, 300, "refresh done -> debt--", size=8, mono=True, fill=ME)
f.line(414, 290, 445, 285, arrow=True, dashed=True, stroke=ME)
# force
f.logic(590, 238, 120, 44, "&debt", "==7", top=True)
f.line(506, 260, 588, 260, arrow=True)
f.line(710, 260, 790, 260, arrow=True, stroke=ME)
f.text(796, 256, "ref_pending (force)", size=10, mono=True, fill=ME)
f.text(470, 320, "3-AND on the top 3 bits = debt==7", size=8, mono=False,
       anchor="middle", fill=MUTED)

# why
f.rect(60, 420, 1150, 130, fill=PAPER, width=1.4, stroke=INK)
f.text(80, 444, "WHY THIS (down-counter, GC-slice dropped)", size=11, bold=True)
f.text(80, 468, "1. Exact by construction - reload adds the real tREFI (constant step). Refresh "
       "is LINEAR (k.tREFI); a <<1 / x2 is geometric (2^k.tREFI) -> misses refresh -> rejected.",
       size=9, mono=False)
f.text(80, 486, "2. No compare, no upper-slice, no dropped-LSB, no GC-wrap edge case - just a "
       "zero/borrow detect. All those questions vanish.", size=9, mono=False)
f.text(80, 504, "3. 14b counter + 3b debt = 17b. Cheaper than GC-slice (which needs a ~13b "
       "ref_ts reg + adder + comparator for the same accuracy).", size=9, mono=False)
f.text(80, 522, "4. Parametric: reload const = tREFI(bin) >> rr_shift(temp). tREFI stays OUT of "
       "the per-command scoreboard - it is the ME's own counter.", size=9, mono=False)

f.caption(40, 592,
          "Interval = 14b down-counter (reload tREFI, -=gear, tick at 0), feeding a 3b debt "
          "(++ on tick, -- on refresh); ref_pending = &debt (force at 7). No GC compare.")

f.save("fig_66_refi_counter_compare.svg")
print("wrote fig_66_refi_counter_compare.svg")
