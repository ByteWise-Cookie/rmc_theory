from rtlfig import Fig, MUTED, FILL_ACTIVE, FILL_CELL

# fig_03 — per-bank cell cell[{rank,bank}]: CAM(open_row) + 16-state FSM + elig.
# Invariant: row_valid = (state==OPEN) & !pre_pending.

SB = "#7a5cb8"   # scoreboard / can_* net class
f = Fig(1060, 760)

f.note(1050, 32, "cell[{rank, bank}]   -   x32 / lane", anchor="end")
f.note(1050, 48, "N_RANKS = 2  ->  64 cells (fig_00, fig_08)", anchor="end")
f.note(1050, 64, "lives in rank r's lane; rank fixed per lane", anchor="end")

# ---------------- packet in from decoder ----------------
f.text(270, 66, "from per_bank_decoder (stage 2)", size=12, mono=False,
       anchor="middle")
f.line(270, 74, 270, 116, arrow=True)
f.slash(270, 96, "REQ_W")
f.text(284, 96, "{rob_index, phy_adr{row,col}, op}", size=10, fill=MUTED)

# ---------------- row_comparator + open_row (CAM) ----------------
f.logic(120, 118, 300, 64, "row_comparator[{r,b}]",
        "packet.row vs open_row  ->  is_hit, need_pre/act/cas")
f.rect(470, 126, 160, 48, fill=FILL_CELL, width=1.4)
f.text(550, 148, "open_row[{r,b}]", size=13, anchor="middle")
f.text(550, 165, "active_row", size=10, mono=False, anchor="middle", fill=MUTED)
f.line(470, 150, 422, 150, arrow=True)

# ---------------- hit / miss split ----------------
f.line(270, 182, 270, 217, arrow=True)
f.decision(270, 250, 150, 66, "is_hit?")

f.path("M198 250 L120 250 L120 356", arrow=True)
f.text(150, 240, "hit", size=11, mono=False, fill=MUTED)
f.logic(70, 356, 200, 60, "cas_path", "need_cas")

f.path("M342 250 L470 250 L470 356", arrow=True)
f.text(430, 240, "miss", size=11, mono=False, fill=MUTED)
f.logic(350, 356, 240, 72, "act_path", "need_pre -> need_act -> need_cas")

# ---------------- 16-state FSM ----------------
fsm = f.logic(680, 200, 360, 224, "fsm_state[{r,b}]   (4-bit / 16)", top=True)
sy = 244
for ln in ["IDLE", "ACT_pending  ->  ACTING (tRCD)", "OPEN",
           "PRE_pending  ->  PREING (tRP)",
           "REF_pending  ->  REFING (tRFC)", "+ MRW / ZQ   (headroom)"]:
    f.text(702, sy, ln, size=11)
    sy += 24
f.text(702, sy + 2, "-ing states hold until timer expires", size=10,
       mono=False, fill=MUTED)

# open_row written on ACT
f.path("M760 200 L760 150 L630 150", arrow=True, dashed=True)
f.text(690, 140, "open_row <- row @ ACT", size=10, mono=False, fill=MUTED)

# ---------------- row_valid gate  (THE INVARIANT) ----------------
rv = f.logic(300, 470, 320, 60, "row_valid")
f.rect(300, 470, 320, 60, fill=FILL_ACTIVE, width=1.6)
f.text(460, 496, "row_valid", size=13, anchor="middle", bold=True)
f.text(460, 514, "= (state == OPEN) & !pre_pending", size=11, anchor="middle")

f.path("M720 424 L720 500 L622 500", arrow=True)
f.text(735, 452, "state==OPEN", size=10, mono=False, fill=MUTED)

# pre_pending intent flag
f.rect(700, 476, 150, 46, fill=FILL_CELL, width=1.4)
f.text(775, 499, "pre_pending", size=12, anchor="middle")
f.text(775, 514, "1-bit intent", size=10, mono=False, anchor="middle", fill=MUTED)
f.line(700, 500, 622, 500, arrow=True)
f.line(775, 570, 775, 524, arrow=True, dashed=True)
f.text(775, 588, "set @ tier-1 PRE propose", size=10, mono=False,
       anchor="middle", fill=MUTED)

# ---------------- elig_gen (arb L0) ----------------
f.line(120, 416, 120, 610, arrow=True)          # cas_path need_cas
f.line(470, 428, 470, 610, arrow=True)          # act_path need_*
f.line(460, 530, 460, 610, arrow=True)          # row_valid gate
f.logic(300, 610, 360, 58, "elig_gen[{r,b}]",
        "need_* & can_*  ->  bank_go, bank_cmd, is_hit")

# can_* from scoreboard
f.line(1040, 638, 662, 638, arrow=True, stroke=SB)
f.slash(840, 638, "can_pre/act/cas")
f.text(840, 616, "from scoreboard (fig_04)  -  ALL legality folded in", size=10,
       mono=False, anchor="middle", fill=SB)
f.text(890, 686, "global last_cas_rank + per-rank faw feed can_*", size=9,
       mono=False, anchor="middle", fill=MUTED)

# ---------------- output ----------------
f.line(480, 668, 480, 712, arrow=True)
f.text(494, 692, "{bank_go, bank_cmd, is_hit}", size=10, fill=MUTED)
f.text(480, 734, "->  L1 bg_arb[r]   (this rank's lane -> L2 -> L3)", size=12,
       mono=False, anchor="middle")

f.caption(40, 752, "One cell of 64 (cell[{r,b}], N_RANKS=2). row_valid gates "
                   "admission: high only while the row is OPEN and no PRE is in "
                   "flight. Intent drops it early; FSM commits at out_cmd_fifo.")

f.save("fig_03_perbank.svg")
print("wrote fig_03_perbank.svg")
