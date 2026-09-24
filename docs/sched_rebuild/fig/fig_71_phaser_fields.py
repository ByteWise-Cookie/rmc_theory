from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_71 — phaser output fields. Per-command record (CA fields + data meta) + phase
# placement. CA -> DFI_CMD_ENCODE, data meta -> WL/RD lines.

CMD = "#7a4fb0"; DATA = "#2a8f86"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1360, 900)

f.text(40, 32, "Phaser output fields  (per-command record + phase placement)", size=15,
       mono=False, bold=True)

# ---- record field table ----
rows = [
    ("valid", "1", "all", "slot used (else DES)", CMD),
    ("cmd_type", "5", "all", "general opcode: ACT/RD/WR/PRE/PREA/PREsb/REF/REFsb/RFM/MRW/MRR/ZQ/DES", CMD),
    ("rw", "1", "CAS", "read/write (also in cmd_type; kept explicit)", CMD),
    ("rank", "1", "all", "log2(N_RANKS=2) -> CS select", CMD),
    ("bg", "3", "all", "log2(N_BG=8)", CMD),
    ("bank", "2", "all", "bank within BG", CMD),
    ("addr", "18", "ACT/CAS", "GENERAL addr = row(ACT) | col(RD/WR); encoder splits UI0/UI1", CMD),
    ("ap", "1", "CAS/PRE", "auto-precharge", CMD),
    ("bl", "1", "CAS", "BL16/32 / on-the-fly", CMD),
    ("rob_index", "8", "CAS", "completion tag", DATA),
    ("sram_addr", "9", "CAS", "dbuf_addr(RD) | wd_slot(WR)", DATA),
]
X = [50, 220, 300, 400]
W = [170, 80, 100, 700]
hy = 80
for i, lab in enumerate(["field", "bits", "for", "meaning"]):
    f.rect(X[i], hy, W[i], 28, fill=FILL_ACTIVE, width=W_CELL)
    f.text(X[i] + 8, hy + 19, lab, size=10, mono=False, bold=True)
y = hy + 28
for nm, b, fr, mn, col in rows:
    f.rect(X[0], y, W[0], 26, fill=PAPER, width=W_CELL)
    f.text(X[0] + 8, y + 18, nm, size=10, mono=True, fill=col, bold=True)
    f.rect(X[1], y, W[1], 26, fill=PAPER, width=W_CELL)
    f.text(X[1] + W[1] / 2, y + 18, b, size=10, mono=True, anchor="middle")
    f.rect(X[2], y, W[2], 26, fill=PAPER, width=W_CELL)
    f.text(X[2] + 8, y + 18, fr, size=9, mono=True, fill=MUTED)
    f.rect(X[3], y, W[3], 26, fill=PAPER, width=W_CELL)
    f.text(X[3] + 8, y + 18, mn, size=9, mono=False)
    y += 26
# subtotal bar
f.text(X[0] + 8, y + 20, "CA subtotal ~32b -> DFI_CMD_ENCODE   .   data ~17b -> WL/RD   .   "
       "record total ~49b", size=10, mono=False, bold=True, fill=INK)
# separate control bit (NOT in the record)
f.rect(X[0], y + 34, 1400, 40, fill=FILL_LOGIC, width=W_CELL)
f.text(X[0] + 10, y + 52, "SEPARATE control bit (NOT a record field):  repeat/hold  "
       "= scheduler -> phaser side wire.", size=10, mono=False, bold=True, fill=ME)
f.text(X[0] + 10, y + 68, "Used ONLY @1:1 (hold the cmd 2 cycles: UI0 then UI1 on p0). At "
       "gear>1 the two UIs fit adjacent phases -> flag unused/wasted.", size=9,
       mono=False, fill=MUTED)

# ---- split arrows ----
sy = y + 95
f.rect(50, sy, 300, 60, fill=FILL_NEW, width=W_CELL)
f.text(200, sy + 24, "CA fields (~32b)", size=11, anchor="middle", bold=True)
f.text(200, sy + 44, "cmd/rank/bg/bank/addr/ap/bl", size=8, anchor="middle", fill=MUTED)
f.line(350, sy + 30, 470, sy + 30, arrow=True, stroke=CMD)
f.text(476, sy + 26, "-> DFI_CMD_ENCODE (per-phase CA beats)", size=9, mono=False, fill=CMD)

f.rect(50, sy + 80, 300, 60, fill=FILL_CELL, width=W_CELL)
f.text(200, sy + 104, "data meta (~17b)", size=11, anchor="middle", bold=True)
f.text(200, sy + 124, "rob_index, sram_addr", size=8, anchor="middle", fill=MUTED)
f.line(350, sy + 110, 470, sy + 110, arrow=True, stroke=DATA)
f.text(476, sy + 106, "-> WL_LAUNCH / RD_CAP (at CAS commit)", size=9, mono=False, fill=DATA)

# ---- bundle = K records + placement ----
by = sy + 180
f.text(50, by, "BUNDLE = up to K=3 command records + phase placement", size=12,
       mono=False, bold=True)
# K records
for k in range(3):
    x = 60 + k * 150
    f.rect(x, by + 20, 130, 46, fill=FILL_NEW, width=W_CELL)
    f.text(x + 65, by + 40, f"record[{k}]", size=10, anchor="middle", bold=True)
    f.text(x + 65, by + 57, "~49b", size=8, anchor="middle", fill=MUTED)
# placement map
px = 560
f.text(px, by + 14, "phase placement (per slot p0..p3):", size=10, mono=False)
for i in range(4):
    x = px + i * 120
    f.rect(x, by + 24, 110, 46, fill=FILL_LOGIC, width=W_CELL)
    f.text(x + 55, by + 44, f"p{i}", size=10, anchor="middle", bold=True)
    f.text(x + 55, by + 61, "{cmd_sel[2],ui[1]}", size=7.5, anchor="middle", fill=MUTED)

f.text(50, by + 100, "Each phase slot points to a record (cmd_sel) + which UI (ui_idx). A 2-UI cmd "
       "= two slots pointing to the same record, ui=0 then ui=1. Idle slot -> DES.", size=9,
       mono=False, fill=MUTED)

f.caption(40, by + 150,
          "Phaser emits K<=3 records (~49b: general cmd + general addr(row|col) + rw + "
          "rank/bg/bank/ap/bl + rob/sram) + per-phase placement {cmd_sel,ui}. CA fields -> "
          "DFI_CMD_ENCODE; rob/sram -> WL/RD at CAS commit; addr split UI0/UI1 by the encoder.")

f.save("fig_71_phaser_fields.svg")
print("wrote fig_71_phaser_fields.svg")
