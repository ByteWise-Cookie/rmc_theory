from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_47 — write path: AW-decoupled, allocate-on-arrival.
# Invariant: admit AW on ROB space (not SRAM); W allocates SRAM on arrival;
# inflow counter tracks packets from CIF; pop WD_SRAM on MC-complete, delayed
# past the ALERT_n window so a write-CRC error can retry from SRAM.

f = Fig(1280, 840)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "Write path - AW-decoupled, allocate-on-arrival", size=15,
       mono=False, bold=True)
f.note(40, 58, "Admit AW on ROB space (NOT SRAM). W allocates SRAM on arrival. "
               "inflow counter = packets left from CIF. Pop delayed past ALERT_n.")

# ---------------- AXI in (left) ----------------
cnote(60, 96, "AXI (one port)")
aw = f.block(60, 110, 150, 44, "AW", "addr req")
wd = f.block(60, 300, 150, 44, "W", "data + aw_id")
f.text(48, 128, "", size=10)

# ---------------- admit gate + WRITE_ROB ----------------
f.line(210, 132, 262, 132, arrow=True)
adm = f.decision(300, 132, 76, 56, "admit?", "ROB free")
f.line(338, 132, 400, 132, arrow=True)
rob = f.block(400, 96, 300, 150, "WRITE_ROB", "per-packet rows, grouped by aw_id")
f.text(416, 140, "aw_id  addr  sram_ptr  status", size=11, fill=MUTED)
f.text(416, 164, "inflow_cnt (pkts left from CIF)", size=11, mono=False)
f.text(416, 188, "outflow_cnt (pkts left to write)", size=11, mono=False, fill=MUTED)
# back-pressure AW
f.path("M300 160 V210 H236 V154", arrow=True, dashed=True)
cnote(244, 226, "ROB full -> back-pressure AW")

# ---------------- W data -> allocate-on-arrival -> WD_SRAM ----------------
f.line(210, 322, 262, 322, arrow=True)
al = f.decision(300, 322, 84, 58, "alloc?", "SRAM free")
f.line(342, 322, 400, 322, arrow=True)
sram = f.block(400, 296, 300, 120, "WD_SRAM")
f.text(416, 336, "incremental-order, 512b/line", size=11, mono=False, fill=MUTED)
f.text(416, 360, "1 packet = 1 line", size=11, fill=MUTED)
f.text(416, 382, "arrival order (OOO across reqs)", size=11, mono=False, fill=MUTED)
# back-pressure W
f.path("M300 351 V400 H250 V344", arrow=True, dashed=True)
cnote(258, 416, "SRAM full -> back-pressure W")
# write-ptr + aw_id up to ROB, inflow-- (dashed, left of the WD_SRAM title)
f.path("M470 296 V250", arrow=True, dashed=True)
cnote(410, 274, "write_ptr + aw_id -> ROB; inflow_cnt--")

# ---------------- ROB -> wr_pack -> MC ----------------
f.line(700, 150, 900, 150, arrow=True)
cnote(712, 142, "wr_pack {addr+off, rd_ptr}", )
mc = f.logic(900, 120, 260, 62, "MC SCHEDULER", "issue write (fig_28/32)", top=True)
f.line(1030, 182, 1030, 250, arrow=True)
cnote(1038, 220, "CAS-W -> DFI")

# ---------------- SRAM read -> splitter -> DFI (data) ----------------
f.line(700, 356, 900, 356, arrow=True)
cnote(720, 348, "512b line @ sram_rd_ptr")
sp = f.logic(900, 330, 260, 54, "WR_SPLIT + WL_LAUNCH",
             "512b -> 2*gear beats (fig_06)", top=True)
f.line(1030, 384, 1030, 430, arrow=True)
f.text(1041, 422, "-> dfi_wrdata", size=12, mono=False)

# ---------------- pop-delay past ALERT_n ----------------
pd = f.logic(780, 500, 300, 72, "POP CTRL", "delay pop past ALERT_n window", top=True)
# MC write-complete + wr_done in from the right/top
f.path("M1030 250 V486 H1080 V500", arrow=True, dashed=True)
cnote(1040, 478, "MC write-complete")
f.path("M1030 430 V492 H930 V500", arrow=True, dashed=True)
cnote(838, 488, "wr_done (self-timed)")
# ALERT_n in (left)
f.line(700, 540, 778, 540, arrow=True)
cnote(600, 534, "ALERT_n (write-CRC)")
# pop -> SRAM (free line) ; retry -> resend
f.path("M780 556 H540 V416", arrow=True, dashed=True)
cnote(548, 470, "clear -> POP line (free SRAM), outflow_cnt--")
cnote(548, 490, "alert in window -> RETRY from SRAM (data held)")

# ---------------- completion ----------------
f.line(1080, 556, 1180, 556, arrow=True)
cnote(1180, 550, "COMPLETION", anchor="end")
cnote(1090, 590, "wr_done | wr_error {rob_index, pkt}")

f.caption(40, 792,
          "AW admitted on ROB space (back-pressures AW); W allocates a WD_SRAM line on "
          "arrival (tag aw_id, inflow_cnt--), back-pressures W on SRAM full.")
f.caption(40, 808,
          "ROB issues wr_pack when data present; MC writes; POP CTRL frees the line only "
          "after the ALERT_n window (write-CRC error retries from SRAM). Request-level "
          "error -> CIF re-issues (stage 14).")

f.save("fig_47_write_path.svg")
print("wrote fig_47_write_path.svg")
