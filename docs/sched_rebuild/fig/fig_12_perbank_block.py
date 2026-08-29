from rtlfig import Fig, MUTED, FILL_CELL, FILL_ACTIVE

# fig_12 — completed per-bank cell (L0).  Judged from user's sketch:
# single-entry CAM = open_row flop + comparator; state[4] beside it (same flop
# array, parallel-read = the physical FSM_TABLE slice). elig gates need_* by
# can_* from the scoreboard. Tier-1 picks cas/act/pre; grant pops on CAS.
# Invariant: cells own no separate FSM - the flop-array slice IS the state;
# elig = need_* & can_*, can_* sourced from BANK_TREG.

SB = "#7a5cb8"
f = Fig(1120, 800)

f.note(1110, 32, "per-bank cell[{rank,bank}]   -   x32 / lane", anchor="end")
f.note(1110, 48, "= physical FSM_TABLE slice (flop array, parallel-read)",
       anchor="end")

# ---------------- input from decoder ----------------
f.text(240, 58, "from BANK_DEC (stage 2)", size=12, mono=False, anchor="middle")
f.line(240, 66, 240, 108, arrow=True)
f.slash(240, 88, "REQ_W")
f.text(256, 88, "{rob_index, row, col, op}", size=10, fill=MUTED)

# ---------------- row_comparator + flop-array slice ----------------
f.logic(90, 108, 300, 66, "row_comparator",
        "pkt.row vs open_row  ->  is_hit / need_pre/act/cas")

f.rect(470, 102, 220, 96, fill="none", stroke=MUTED, width=1.4, dashed=True)
f.text(580, 119, "FSM_TABLE slice (flops)", size=11, anchor="middle", fill=MUTED)
f.rect(484, 128, 192, 30, fill=FILL_CELL, width=1.4)
f.text(580, 148, "open_row", size=12, anchor="middle")
f.rect(484, 162, 192, 30, fill=FILL_CELL, width=1.4)
f.text(580, 182, "state[4]  IDLE..REFING", size=11, anchor="middle")
f.line(470, 143, 392, 143, arrow=True)
f.text(430, 135, "active_row", size=9, mono=False, anchor="middle", fill=MUTED)

# REF_pending injected into state (from maintenance)
f.line(792, 177, 692, 177, arrow=True, stroke=SB)
f.text(800, 173, "REF_pending <- MAINT_ENG", size=9, mono=False, fill=SB)

# ---------------- hit / miss split ----------------
f.line(240, 174, 240, 214, arrow=True)
f.decision(240, 248, 150, 66, "is_hit?")

f.path("M165 248 L110 248 L110 336", arrow=True)
f.text(138, 238, "hit", size=10, mono=False, fill=MUTED)
f.logic(60, 336, 180, 56, "cas_path", "need_cas")

f.path("M315 248 L440 248 L440 336", arrow=True)
f.text(410, 238, "miss", size=10, mono=False, fill=MUTED)
f.logic(330, 336, 230, 68, "act_path", "need_pre -> need_act -> need_cas")

# ---------------- row_valid fence (intent/commit) ----------------
rv = f.logic(240, 440, 300, 60, "row_valid")
f.rect(240, 440, 300, 60, fill=FILL_ACTIVE, width=1.6)
f.text(390, 466, "row_valid", size=13, anchor="middle", bold=True)
f.text(390, 484, "= (state==OPEN) & !pre_pending", size=11, anchor="middle")

f.rect(600, 442, 170, 46, fill=FILL_CELL, width=1.4)
f.text(685, 462, "pre_pending", size=12, anchor="middle")
f.text(685, 478, "1-bit intent", size=9, mono=False, anchor="middle", fill=MUTED)
f.line(600, 466, 542, 466, arrow=True)
f.line(685, 540, 685, 488, arrow=True, dashed=True)
f.text(685, 556, "set @ tier-1 PRE propose", size=9, mono=False,
       anchor="middle", fill=MUTED)

# state==OPEN into the fence
f.path("M580 192 L580 420 L390 420 L390 440", arrow=True, dashed=True)
f.text(592, 300, "state==OPEN", size=9, mono=False, fill=MUTED)

# ---------------- elig_gen (L0) ----------------
f.line(150, 392, 150, 540, arrow=True)
f.text(162, 470, "need_cas", size=9, mono=False, fill=MUTED)
f.line(556, 404, 556, 540, arrow=True)
f.text(568, 456, "need_*", size=9, mono=False, fill=MUTED)
f.line(390, 500, 390, 540, arrow=True)

f.logic(240, 540, 340, 60, "elig_gen   (PRE_BANK_ELIG)",
        "need_* & can_*  ->  bank_go, bank_cmd, is_hit")

# can_* feed from the scoreboard (THE missing structural link)
f.line(1090, 568, 582, 568, arrow=True, stroke=SB)
f.slash(830, 568, "can_bank")
f.text(838, 548, "from BANK_TREG (scoreboard)  -  timing legality", size=10,
       mono=False, anchor="middle", fill=SB)

# ---------------- BANK_ARB (tier-1) ----------------
f.line(410, 600, 410, 644, arrow=True)
f.mux(310, 644, 200, 48, "BANK_ARB (tier-1)", sel="cas/act/pre")
f.line(410, 692, 410, 734, arrow=True)
f.text(410, 754, "->  BG_ARB (L1)", size=12, mono=False, anchor="middle")

# grant_oh feedback, pop on CAS
f.path("M410 712 L40 712 L40 178 L482 178", arrow=True, dashed=True, stroke=MUTED)
f.text(70, 400, "grant_oh <- L1/L2", size=9, mono=False, fill=MUTED)
f.text(70, 414, "pop on CAS", size=9, mono=False, fill=MUTED)

f.caption(40, 786, "One per-bank cell = a flop-array slice (open_row + state, "
                   "parallel-read = single-entry CAM) + row_comparator for is_hit "
                   "+ elig_gen gating need_* by can_* from BANK_TREG. Tier-1 picks "
                   "cas/act/pre; grant pops on CAS.")

f.save("fig_12_perbank_block.svg")
print("wrote fig_12_perbank_block.svg")
