from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_78 — DFI_CMD_ENCODE logic level (one phase formatter). cmd_type -> opcode ROM
# (CA0..CA5 H/L pattern); field mux array -> CA6..CA13 (UI0) / CA0..CA13 (UI1),
# selected by (cmd_type, ui_idx); CS_GEN. Grounded in JESD79-5 Table 241.

CMD = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1560, 1000)


def blk(x, y, w, h, name, sub, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + w / 2, y + 20, name, size=11, anchor="middle", bold=True)
    if sub:
        f.text(x + w / 2, y + 38, sub, size=8, anchor="middle", fill=MUTED)


f.text(40, 30, "DFI_CMD_ENCODE - logic level (one phase formatter)", size=15,
       mono=False, bold=True)
f.text(40, 50, "Per phase slot: cmd_type + ui_idx + field bundle -> CA[13:0] + cs_n. "
       "Replicated x GEAR. Bit map = JESD79-5 Table 241.", size=9, mono=False, fill=MUTED)

# ---- inputs ----
blk(40, 90, 200, 150, "phaser slot in", "", FILL_ACTIVE)
f.text(140, 128, "cmd_type[5]", size=9, mono=True, anchor="middle", fill=CMD)
f.text(140, 146, "ui_idx (0/1)", size=9, mono=True, anchor="middle", fill=CMD)
f.text(140, 170, "fields:", size=9, mono=True, anchor="middle")
f.text(140, 186, "rank bg ba", size=8, mono=True, anchor="middle", fill=MUTED)
f.text(140, 200, "addr(row|col)", size=8, mono=True, anchor="middle", fill=MUTED)
f.text(140, 214, "ap MRA OP CID", size=8, mono=True, anchor="middle", fill=MUTED)

# ---- opcode ROM ----
blk(320, 90, 240, 90, "OPCODE_ROM", "cmd_type -> CA[5:0] H/L pattern", FILL_LOGIC)
f.text(332, 158, "+ 1cyc/2cyc bit (=CA1)", size=8, mono=True, fill=MUTED)
f.line(240, 135, 318, 135, arrow=True, stroke=CMD)      # cmd_type -> ROM
f.text(255, 128, "cmd_type", size=8, mono=True, fill=CMD)

# ---- field mux array ----
blk(320, 220, 240, 130, "FIELD_MUX array", "per CA pin: pick field bit", FILL_NEW)
f.text(332, 268, "sel = (cmd_type, ui_idx)", size=8, mono=True, fill=MUTED)
f.text(332, 286, "UI0: CA6..13 <- BA/BG/CID", size=8, mono=True)
f.text(332, 302, "UI1: CA0..13 <- row / col+ap", size=8, mono=True)
f.text(332, 318, "  / MRA+OP / ...", size=8, mono=True)
f.line(240, 200, 318, 260, arrow=True, stroke=CMD)      # fields -> mux
f.line(240, 155, 300, 155, arrow=False, stroke=CMD)
f.path("M300 155 V300 H318", arrow=True, stroke=CMD, dashed=True)  # ui_idx/cmd sel
f.text(262, 300, "sel", size=8, mono=True, fill=CMD)

# ---- CS_GEN ----
blk(320, 390, 240, 70, "CS_GEN", "ui0 & !DES -> rank one-cold (L), else H", FILL_LOGIC)

# ---- assemble ----
blk(640, 150, 180, 240, "ASSEMBLE", "concat -> CA[13:0]", FILL_ACTIVE)
f.line(560, 135, 638, 200, arrow=True, stroke=CMD)      # opcode -> assemble
f.text(575, 165, "CA[5:0]", size=8, mono=True, fill=CMD)
f.line(560, 285, 638, 285, arrow=True, stroke=CMD)      # fields -> assemble
f.text(575, 278, "CA[13:6]/UI1", size=8, mono=True, fill=CMD)

# outputs
f.line(820, 230, 940, 230, arrow=True, stroke=CMD)
f.text(946, 226, "dfi_address_p0[13:0]", size=10, mono=True, fill=CMD)
f.line(560, 425, 940, 425, arrow=True, stroke=CMD)
f.text(946, 421, "dfi_cs_p0 [N_RANKS]", size=10, mono=True, fill=CMD)

# ---- CA bit map reference (Table 241) ----
by = 520
f.text(40, by, "CA[13:0] bit map (JESD79-5 Table 241) - what ASSEMBLE builds:", size=12,
       mono=False, bold=True)
PINS = ["CS_n", "CA0", "CA1", "CA2", "CA3", "CA4", "CA5", "CA6", "CA7", "CA8",
        "CA9", "CA10", "CA11", "CA12", "CA13"]
ROWS = [
    ("ACT UI0", ["L", "L", "L", "R0", "R1", "R2", "R3", "BA0", "BA1", "BG0", "BG1", "BG2", "CID0", "CID1", "CID2"]),
    ("ACT UI1", ["H", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15", "R16", "R17"]),
    ("WR  UI0", ["L", "H", "L", "L", "H", "L", "H*", "BA0", "BA1", "BG0", "BG1", "BG2", "CID0", "CID1", "CID2"]),
    ("WR  UI1", ["H", "V", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "V", "AP", "H", "V", "CID3"]),
    ("PREpb", ["L", "H", "H", "L", "H", "H", "H", "CID3", "BA0", "BA1", "BG0", "BG1", "BG2", "CID0", "CID1"]),
    ("DES", ["H", "X", "X", "X", "X", "X", "X", "X", "X", "X", "X", "X", "X", "X", "X"]),
]
CW = 92
x = 40
f.rect(x, by + 12, CW, 24, fill=FILL_ACTIVE, width=W_CELL)
f.text(x + CW / 2, by + 29, "row \\ pin", size=8, anchor="middle", bold=True)
for i, p in enumerate(PINS):
    xx = x + CW + i * 90
    f.rect(xx, by + 12, 90, 24, fill=FILL_ACTIVE, width=W_CELL)
    f.text(xx + 45, by + 29, p, size=8, mono=True, anchor="middle", bold=True)
yy = by + 36
for nm, vals in ROWS:
    f.rect(x, yy, CW, 24, fill=FILL_CELL, width=W_CELL)
    f.text(x + 6, yy + 16, nm, size=8, mono=True, bold=True)
    for i, v in enumerate(vals):
        xx = x + CW + i * 90
        opc = i <= 6  # opcode region CS_n..CA5
        fill = FILL_LOGIC if (opc and v in "LHXV*") else PAPER
        f.rect(xx, yy, 90, 24, fill=fill, width=1.0)
        f.text(xx + 45, yy + 16, v, size=8, mono=True, anchor="middle",
               fill=(MUTED if v in "XV" else INK))
    yy += 24

f.text(40, yy + 22, "OPCODE_ROM drives the grey region (CS_n..CA5 fixed H/L per cmd; CA1 = 1cyc/2cyc). "
       "FIELD_MUX drives the rest (BA/BG/CID/row/col/ap...) picked by cmd+ui. * = BL bit.",
       size=9, mono=False, fill=MUTED)

f.caption(40, yy + 60,
          "Encoder per phase = OPCODE_ROM (cmd->CA[5:0]) + FIELD_MUX array (each higher CA pin picks "
          "a field bit by cmd_type & ui_idx) + CS_GEN (cs_n=L one-cold on UI0, else H) -> ASSEMBLE "
          "-> dfi_address_p0[13:0] + dfi_cs_p0. Bit positions from Table 241. Pure comb; x GEAR.")

f.save("fig_78_encode_logic.svg")
print("wrote fig_78_encode_logic.svg")
