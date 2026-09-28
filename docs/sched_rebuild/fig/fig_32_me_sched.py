from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_ACTIVE, FAINT, INK,
                    W_CELL)

# fig_32 — Maintenance Engine <-> NEW scheduler (class-split + token phaser).
# ME steers the demand arb (p_bit), reads ref_rdy, injects me_cmd at the packer,
# writes shared scoreboard gates. No "stage 0" - it rides the class-split arb.

f = Fig(1240, 760)


def seam(x, y, s, anchor="start"):
    f.text(x, y, s, size=11, mono=False, anchor=anchor, fill=INK, bold=True)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "Maintenance Engine <-> new scheduler (4 seams)", size=15,
       mono=False, bold=True)
f.note(40, 58, "ME STEERS the demand arb via p_bit, reads ref_rdy, then INJECTS "
               "me_cmd at the packer. No override stage - it rides the class-split arb.")

# ---------------- demand spine (left) ----------------
bc = f.block(110, 100, 360, 50, "BANK_CELLS  x32", "need_* & can_* -> class ready")
pre = f.block(110, 196, 105, 48, "PRE_ARB")
act = f.block(232, 196, 105, 48, "ACT_ARB")
cas = f.rect(354, 196, 116, 48, fill=FILL_ACTIVE, width=W_CELL)
f.text(412, 216, "CAS_ARB", size=13, anchor="middle")
f.text(412, 232, "+ p_bit", size=10, mono=False, anchor="middle", fill=MUTED)
for x in (162, 284, 412):
    f.line(x, 150, x, 196, arrow=True)
l3 = f.block(150, 288, 320, 46, "L3   cas/act/pre 2:1 per class")
for x in (162, 284, 412):
    f.line(x, 244, x, 288, arrow=True)
pk = f.block(150, 372, 320, 54, "PHASE_PACKER", "-> token bundle")
f.line(310, 334, 310, 372, arrow=True)
en = f.block(150, 460, 320, 44, "CA-BEAT ENCODER")
f.line(310, 426, 310, 460, arrow=True)
dm = f.block(150, 528, 320, 44, "DFI_MUX  (sel init_done)")
f.line(310, 504, 310, 528, arrow=True)
f.line(310, 572, 310, 606, arrow=True)
f.text(322, 598, "-> DFI / PHY / DRAM", size=12, mono=False)

# ---------------- maint engine + scoreboard (right) ----------------
me = f.logic(600, 150, 310, 176, "MAINT ENGINE", "6 FSMs -> priority-select",
             top=True)
f.text(755, 250, "refresh . rfm . zq", size=12, mono=False, anchor="middle", fill=MUTED)
f.text(755, 268, "mrr . mrw . init", size=12, mono=False, anchor="middle", fill=MUTED)
f.text(755, 292, "(fig_31)", size=10, mono=False, anchor="middle", fill=MUTED)
sb = f.block(600, 460, 310, 74, "SCOREBOARD (shared)",
             "gate_rfc/zq . RAA . tREFI . can_*")

# ---------------- seam 1: ref_pending -> p_bit ----------------
f.line(598, 226, 474, 220, arrow=True)
seam(486, 180, "(1) ref_pending")
cnote(486, 194, "-> p_bit  (drain-steer)")

# ---------------- seam 2: ref_rdy -> ME ----------------
f.line(472, 122, 598, 180, arrow=True)
seam(486, 112, "(2) ref_rdy 8-AND (drained)")

# ---------------- seam 3: me_cmd token override ----------------
f.path("M660 326 V399 H474", arrow=True)
seam(500, 356, "(3) me_cmd token")
cnote(500, 370, "override > demand")
f.path("M474 414 H590 V344", arrow=True, dashed=True)
cnote(600, 360, "sched_ack")

# ---------------- seam 4: scoreboard writeback + reads ----------------
f.line(830, 326, 830, 460, arrow=True, dashed=True)
seam(838, 400, "(4) writeback")
cnote(838, 414, "(gate/RAA/tREFI)")
# scoreboard -> demand can_*
f.path("M600 500 H70 V150 H108", arrow=True, dashed=True)
cnote(80, 470, "can_* -> demand arb (gates issue)")
# raa_inc from commit
f.path("M470 482 H540 V500 H598", arrow=True, dashed=True)
cnote(548, 492, "raa_inc (commit)")

# ---------------- init_done note ----------------
cnote(150, 592, "sel = init_done  (from ME/init FSM)")

f.caption(40, 730,
          "ME steers the CAS arb via ref_pending/p_bit (scheduler drains the target "
          "banks itself), reads ref_rdy, injects me_cmd as a priority token at the "
          "packer (sched_ack), and writes the shared scoreboard gates. init owns the "
          "DFI mux till init_done. MRR result returns on the RD_CAP sideband (fig_31).")

f.save("fig_32_me_sched.svg")
print("wrote fig_32_me_sched.svg")
