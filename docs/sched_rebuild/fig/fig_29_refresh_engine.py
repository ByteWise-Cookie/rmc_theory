from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FAINT, INK, W_CELL)

# fig_29 — refresh engine with the MR4 temperature-poll reload path.
# Invariant: tREFI reload is f(temp, FGR) — not a constant 9360. MR4 poll ->
# rate 1x/2x/4x -> reload mux; debt gives the +-8 slip; REFsb RR issues.
# Highlighted (purple) = the temp-poll path.

f = Fig(1240, 720)


def cnote(x, y, s):
    f.text(x, y, s, size=11, mono=False, fill=MUTED)


# ---------------- header ----------------
f.text(40, 38, "Refresh engine - MR4 temperature-poll reload (per rank)",
       size=15, mono=False, bold=True)
f.note(40, 58, "tREFI reload = f(temp, FGR mode), NOT a fixed 9360. Purple = the "
               "MR4 temp-poll path. debt gives the +-8 slip.")

# ======== ROW A : temp poll -> rate -> reload -> tREFI counter ========
mp = f.counter(112, 140, 34, "MR4_POLL", "tMR4")
mr = f.logic(186, 113, 150, 54, "MRR(MR4)", "poll temp", top=True)
f.line(146, 140, 184, 140, arrow=True)
f.line(336, 140, 388, 140, arrow=True)
td = f.logic(388, 113, 180, 54, "TEMP_DECODE", "MR4 -> 1x/2x/4x", top=True)
# MRR goes to scheduler (maint inject) and temp returns
f.line(261, 113, 261, 84, arrow=True, dashed=True)
cnote(270, 88, "-> sched (mrr_rdy)")
f.line(478, 200, 478, 167, arrow=True, dashed=True)
cnote(486, 192, "temp code (via DQ)")
# reload mux
f.line(568, 140, 610, 140, arrow=True)
rm = f.mux(610, 118, 170, 52, "reload_sel")
f.text(695, 108, "9360 / 4680 / 2340", size=11, mono=False, anchor="middle", fill=MUTED)
f.line(695, 92, 695, 116, arrow=True)
f.text(695, 188, "sel: rate x FGR", size=11, mono=False, anchor="middle", fill=MUTED)
# tREFI counter
f.line(780, 144, 835, 144, arrow=True)
tc = f.counter(880, 144, 38, "tREFI_CTR", "down /rank")
cnote(560, 232, "reload MOVES with temp: hot >85C halves (2x), extreme quarters (4x)")

# highlight the temp path (redraw fills)
for blk in (mr, td):
    f.rect(blk.x, blk.y, blk.w, blk.h, fill=FILL_NEW, width=W_CELL)
    f.text(blk.cx, blk.y + 22, "MRR(MR4)" if blk is mr else "TEMP_DECODE",
           size=13, anchor="middle", bold=True)
    f.text(blk.cx, blk.y + 37, "poll temp" if blk is mr else "MR4 -> 1x/2x/4x",
           size=11, mono=False, anchor="middle", fill=MUTED)

# ======== ROW B : counter -> debt -> decide -> RR -> ref_pending ========
f.line(880, 182, 880, 250, arrow=True)
cnote(888, 220, "hit 0")
db = f.counter(880, 284, 34, "DEBT", "++ / sat 8")
dd = f.logic(560, 257, 250, 54, "REF_DECIDE",
             "debt>0 & idle = opp ; ==7 = force", top=True)
f.line(846, 284, 812, 284, arrow=True)
rr = f.logic(300, 257, 230, 54, "REFSB_RR", "refresh_ba 0->3  => k", top=True)
f.line(558, 284, 532, 284, arrow=True)
# ref_pending out (down-left, to banks / p_bit)
f.line(300, 300, 300, 360, arrow=True)
f.path("M300 360 H120", arrow=True)
f.text(116, 356, "ref_pending[bank k, BG0..7]  =>  p_bit (CAS arb)", size=11,
       anchor="start", fill=MUTED)
f.text(116, 372, "assert on the 8 targets; drives drain-priority", size=10,
       mono=False, anchor="start", fill=MUTED)

# ======== ROW C : feedback - ref_rdy -> go -> issue ========
go = f.logic(300, 440, 210, 54, "REFSB_GO", "8-AND ref_rdy[k, BG0..7]", top=True)
f.line(405, 540, 405, 496, arrow=True)
f.text(405, 556, "ref_rdy[8]  <-  target banks (state==IDLE)", size=11,
       anchor="middle", fill=MUTED)
f.line(512, 467, 556, 467, arrow=True)
iss = f.logic(556, 440, 250, 54, "issue PREsb(k)+REFsb(k)",
              "override-inject -> packer", top=True)
# outputs: gate_rfc, REFING, debt--
f.line(806, 455, 900, 455, arrow=True, dashed=True)
cnote(834, 448, "gate_rfc")
f.line(806, 480, 900, 480, arrow=True, dashed=True)
cnote(834, 496, "REFING(tRFCsb)")
f.path("M681 440 V400 H880 V318", arrow=True, dashed=True)
cnote(700, 396, "refresh done -> DEBT--")

f.caption(40, 690,
          "MR4 poll sets rate 1x/2x/4x -> reload mux picks 9360/4680/2340 -> tREFI "
          "down-counter (per rank). Hit 0 -> debt (+-8 slip). REFsb RR asserts "
          "ref_pending on bank k across 8 BGs (= p_bit); 8-AND ref_rdy -> issue "
          "PREsb+REFsb, gate_rfc, DEBT--.")

f.save("fig_29_refresh_engine.svg")
print("wrote fig_29_refresh_engine.svg")
