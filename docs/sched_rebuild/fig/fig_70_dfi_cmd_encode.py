from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_70 — DFI_CMD_ENCODE internals. Phaser bundle -> per-phase CA formatters ->
# dfi_address_pN + dfi_cs_pN (DDR5 CA truth table). Comb, dfi_clk.

CMD = "#7a4fb0"; GREEN = "#3d8c40"; ME = "#b0602a"
f = Fig(1500, 940)


def blk(x, y, w, h, name, sub, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + w / 2, y + 20, name, size=10, anchor="middle", bold=True)
    if sub:
        f.text(x + w / 2, y + 37, sub, size=8, anchor="middle", fill=MUTED)


f.text(40, 32, "DFI_CMD_ENCODE internals  (bundle -> CA beats + CS, DDR5)", size=15,
       mono=False, bold=True)

# ---- phaser bundle in ----
blk(50, 120, 210, 260, "PHASER bundle", "", FILL_ACTIVE)
f.text(155, 160, "per phase tag:", size=9, mono=True, anchor="middle")
f.text(155, 178, "{cmd_ref, ui_idx}", size=9, mono=True, anchor="middle", fill=CMD)
f.text(155, 210, "cmd fields (BANK_REQ):", size=9, mono=True, anchor="middle")
for i, s in enumerate(["cmd_type", "rank", "bg / ba", "row / col", "AP / BL"]):
    f.text(155, 232 + i * 18, s, size=9, mono=True, anchor="middle", fill=MUTED)

# ---- N per-phase CA formatters ----
FX = 360
fy = [120, 215, 310, 405]
for i, y in enumerate(fy):
    blk(FX, y, 250, 80, f"CA_FORMAT p{i}", "case(cmd,ui) + field mux", FILL_NEW)
    f.text(FX + 8, y + 58, "-> dfi_address_p%d [13:0]" % i, size=8, mono=True, fill=CMD)
    f.line(260, 250, FX - 2, y + 40, arrow=True, stroke=CMD)

# ---- CS_GEN ----
blk(FX, 520, 250, 80, "CS_GEN", "assert cs on UI0 phase", FILL_LOGIC)
f.text(FX + 8, 578, "-> dfi_cs_pN [N_RANKS-1:0]", size=8, mono=True, fill=CMD)
f.line(260, 300, FX - 2, 555, arrow=True, stroke=CMD)

# ---- output bus ----
blk(720, 220, 190, 180, "phase pack", "p0..p3 buses", FILL_CELL)
for y in fy:
    f.line(610, y + 40, 720, 310, arrow=False, stroke=CMD)
f.line(610, 560, 720, 380, arrow=False, stroke=CMD)
f.line(910, 300, 1010, 300, arrow=True, stroke=CMD)
f.text(1016, 296, "-> DFI_MUX -> PHY", size=10, mono=False, fill=CMD)

# ---- inside one formatter (zoom) ----
zx, zy = 720, 460
f.rect(zx, zy, 720, 200, fill="none", width=1.2, stroke=FAINT)
f.text(zx + 12, zy + 18, "CA_FORMAT pN  (one slot, zoom)", size=10, bold=True)
blk(zx + 20, zy + 34, 150, 60, "opcode ROM", "cmd_type -> CA[4:0] pat", FILL_LOGIC)
blk(zx + 200, zy + 34, 150, 60, "field MUX", "ui_idx picks UI0/UI1", FILL_LOGIC)
blk(zx + 380, zy + 34, 150, 60, "assemble", "opcode + fields -> CA[13:0]", FILL_NEW)
f.line(zx + 170, zy + 64, zx + 200, zy + 64, arrow=True)
f.line(zx + 350, zy + 64, zx + 380, zy + 64, arrow=True)
f.line(zx + 530, zy + 64, zx + 560, zy + 64, arrow=True, stroke=CMD)
f.text(zx + 566, zy + 60, "dfi_address_pN", size=8, mono=True, fill=CMD)
f.text(zx + 20, zy + 120, "UI0: opcode + CS=0 + BG/BA + row/col-low", size=8, mono=True)
f.text(zx + 20, zy + 136, "UI1: CS=1 + row/col-high + AP/BL   (2-UI cmds)", size=8, mono=True)
f.text(zx + 20, zy + 152, "1-UI (PRE/REF): single slot, no UI1", size=8, mono=True, fill=MUTED)
f.text(zx + 20, zy + 172, "bit positions per JESD79-5 CA truth table (not hardcoded here)",
       size=8, mono=False, fill=ME)

# ---- rules ----
f.rect(50, 690, 1390, 210, fill=PAPER, width=1.4, stroke=INK)
f.text(70, 714, "ENCODE RULES", size=11, bold=True)
rr = ["N per-phase formatters (=GEAR). Each slot pN gets {cmd_ref, ui_idx} from the phaser and "
      "formats ONE CA beat -> dfi_address_pN. Pure comb, dfi_clk.",
      "2-UI command (ACT/RD/WR/MRW/MRR) occupies 2 ADJACENT phases: UI0 (CS=0) + UI1 (CS=1). The "
      "UI1 slot pulls the SAME cmd's upper-address fields (row/col-high, AP).",
      "1-UI command (PRE/REF/DES/NOP) = 1 phase. Idle phases -> DES (dfi_cs=1, CA don't-care).",
      "CS_GEN asserts the target rank's dfi_cs on the UI0 phase only; diff-rank cmds in one bundle "
      "-> different rank bits asserted on their own phase-pairs (fig_69 B).",
      "2N mode / CS-geardown (DDR5): hold CA >=1 cmd-clk after CS / single-data-rate CA format - a "
      "config-gated variant of CS_GEN + the assemble stage.",
      "At 1:1 only p0 formats a beat; a 2-UI cmd straddles p0 of two dfi_clk cycles (UI0 then UI1)."]
for i, s in enumerate(rr):
    f.text(70, 736 + i*24, f"{i+1}. {s}", size=9, mono=False)

f.caption(40, 924,
          "DFI_CMD_ENCODE = N per-phase CA formatters (case(cmd,ui)+field mux) + CS_GEN. Phaser "
          "places, encoder frames: each phase slot -> one CA[13:0] beat + its cs bit, 2-UI cmds "
          "span 2 slots, idle=DES. Bit layout from the JESD79-5 CA truth table.")

f.save("fig_70_dfi_cmd_encode.svg")
print("wrote fig_70_dfi_cmd_encode.svg")
