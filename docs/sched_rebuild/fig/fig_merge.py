from rtlfig import Fig, MUTED, FILL_ACTIVE

SB = "#7a5cb8"
f = Fig(980, 800)

# ---------------- scoreboard: owns ALL timing ----------------
f.logic(660, 60, 300, 178, "timing_scoreboard", "deadline form", top=True)
f.text(680, 118, "next_pre_ck[b]  next_act_ck[b]", size=11)
f.text(680, 138, "next_cas_ck[b]", size=11)
f.text(680, 162, "cross-bank constraints are WRITTEN", size=10, mono=False, fill=MUTED)
f.text(680, 176, "into other banks' deadlines,", size=10, mono=False, fill=MUTED)
f.text(680, 190, "not checked at a shared arbiter", size=10, mono=False, fill=MUTED)
f.text(680, 214, "tFAW: 4-deep timestamp window, per rank", size=10,
       mono=False, fill=MUTED)

# ---------------- level 0 ----------------
f.note(40, 62, "level 0   -   per bank, x32")
f.note(40, 78, "row_comparator[b] + elig_gen[b], wired straight to open_row[b]")

f.rect(40, 96, 250, 54, fill=FILL_ACTIVE, width=1.4)
f.text(165, 118, "row_comparator[b]", size=12, anchor="middle", bold=True)
f.text(165, 134, "need_pre / need_act / need_cas, is_hit", size=10,
       mono=False, anchor="middle", fill=MUTED)
f.line(165, 150, 165, 186, arrow=True)

f.rect(40, 190, 250, 66, fill=FILL_ACTIVE, width=1.4)
f.text(165, 212, "elig_gen[b]", size=12, anchor="middle", bold=True)
f.text(165, 228, "need_* & can_*", size=10, mono=False, anchor="middle", fill=MUTED)
f.text(165, 242, "-> bank_go[b], bank_cmd[b], is_hit[b]", size=10,
       mono=False, anchor="middle", fill=MUTED)

f.line(658, 150, 296, 150, arrow=True, stroke=SB)
f.text(320, 144, "can_pre / can_act / can_cas   -   all timing, direction, "
       "refresh, rfm, wdb_ready", size=10, mono=False, fill=SB)

f.note(40, 300, "can_* already contains every constraint, whatever its scope,")
f.note(40, 316, "so downstream arbiters CANNOT reject a candidate.")

# ---------------- level 1 ----------------
f.line(165, 258, 165, 330, arrow=True)
f.text(178, 278, "32 x {go, cmd, is_hit}", size=11, fill=MUTED)
f.mux(90, 334, 240, 50, "bg_arb[0..7]")
f.note(40, 412, "level 1   -   4-way per bank group")
f.note(40, 428, "hit-biased round robin   -   selection only")

f.line(210, 384, 300, 462, arrow=True)
f.text(300, 400, "8 x {go, cmd, is_hit}", size=11, fill=MUTED)

# ---------------- level 2 ----------------
f.mux(250, 466, 380, 52, "rank_arb")
f.note(40, 548, "level 2   -   8-way per rank")
f.note(40, 564, "bank-group round robin + per-group starvation override")
f.note(40, 580, "selection only, no timing")

f.line(440, 518, 440, 618, arrow=True)
f.text(452, 570, "one command", size=11, fill=MUTED)

# grant back
f.path("M628 492 L648 492 L648 274 L292 274", arrow=True, dashed=True)
f.text(340, 268, "grant_oh[32]   -   pop only on CAS", size=10,
       mono=False, fill=MUTED)

# ---------------- packer ----------------
f.logic(310, 622, 260, 52, "phase_packer",
        "2-CK atomic  -  ck mod RATIO -> phase")
f.line(440, 674, 440, 716, arrow=True)
f.text(440, 736, "to DFI", size=12, mono=False, anchor="middle")

f.logic(660, 622, 200, 52, "ref_engine", "tREFI deadline")
f.line(658, 648, 574, 648, arrow=True)
f.text(600, 690, "ref_urgent preempts", size=11, mono=False, fill=MUTED)
f.text(600, 706, "outside the arbiter tree", size=10, mono=False, fill=MUTED)

f.path("M310 648 L296 648 L296 600 L810 600 L810 242", arrow=True,
       dashed=True, stroke=SB)
f.text(660, 594, "cmd_issued  ->  update deadlines", size=10,
       mono=False, fill=SB)

f.caption(40, 762, "Corrected: selection and legality are not separated. "
                   "All timing folds into can_*[b] at level 0, so no arbiter "
                   "can ever reject its own winner.")
f.caption(40, 780, "The two-level tree is now justified by timing closure and "
                   "bank-group fairness only - build the flat 32-way version "
                   "first if it closes.")
f.save("two_level_merge.svg")
