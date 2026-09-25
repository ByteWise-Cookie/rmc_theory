from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_74 — DDR5 command x phaser-field matrix. which record fields each command
# USES vs don't-care (-), how addr is reused (row/col/MRA), DFI-encode path.

USE = "#e3f2f1"; DC = "#f4f4f4"
f = Fig(1580, 900)

COLS = ["cmd_type", "rw", "rank", "bg", "bank", "addr", "ap", "bl", "rob", "sram"]
CW = [140, 46, 52, 46, 70, 110, 40, 40, 52, 90]
X0 = 40

# rows: (cmd, [per-col value or '-'])   -- 2ui is NOT a field (separate flag)
ROWS = [
    ("ACT",   ["ACT", "-", "Y", "Y", "Y", "row", "-", "-", "-", "-"]),
    ("RD",    ["RD", "R", "Y", "Y", "Y", "col", "Y", "Y", "Y", "dbuf"]),
    ("WR",    ["WR", "W", "Y", "Y", "Y", "col", "Y", "Y", "Y", "wd_slot"]),
    ("PRE",   ["PRE", "-", "Y", "Y", "Y", "-", "-", "-", "-", "-"]),
    ("PREA",  ["PREA", "-", "Y", "-", "-", "-", "-", "-", "-", "-"]),
    ("PREsb", ["PREsb", "-", "Y", "-", "k", "-", "-", "-", "-", "-"]),
    ("REF",   ["REF", "-", "Y", "-", "-", "-", "-", "-", "-", "-"]),
    ("REFsb", ["REFsb", "-", "Y", "-", "k", "-", "-", "-", "-", "-"]),
    ("RFM",   ["RFM", "-", "Y", "-", "k/-", "-", "-", "-", "-", "-"]),
    ("MRW",   ["MRW", "-", "Y", "-", "-", "MRA+d", "-", "-", "-", "-"]),
    ("MRR",   ["MRR", "R", "Y", "-", "-", "MRA", "-", "-", "Y", "sideband"]),
    ("ZQ/MPC", ["MPC", "-", "Y", "-", "-", "op", "-", "-", "-", "-"]),
    ("SRE",   ["SRE", "-", "Y", "-", "-", "-", "-", "-", "-", "-"]),
    ("SRX",   ["SRX", "-", "Y", "-", "-", "-", "-", "-", "-", "-"]),
    ("DES",   ["DES", "-", "-", "-", "-", "-", "-", "-", "-", "-"]),
]

f.text(40, 30, "DDR5 command x phaser-field matrix  (used vs don't-care)", size=15,
       mono=False, bold=True)
f.text(40, 50, "Y = field used   .   value = what it carries   .   - = don't-care.  addr is REUSED: "
       "row(ACT) | col(RD/WR) | MRA(+data)(MRW/MRR) | op(MPC).", size=9, mono=False, fill=MUTED)

# header
hy = 70
x = X0
for i, c in enumerate(COLS):
    f.rect(x, hy, CW[i], 28, fill=FILL_ACTIVE, width=W_CELL)
    f.text(x + CW[i] / 2, hy + 19, c, size=9, mono=True, anchor="middle", bold=True)
    x += CW[i]

# rows
y = hy + 28
for cmd, vals in ROWS:
    x = X0
    for i, v in enumerate(vals):
        fill = DC if v == "-" else USE
        f.rect(x, y, CW[i], 26, fill=fill, width=W_CELL)
        f.text(x + CW[i] / 2, y + 18, v, size=9, mono=True, anchor="middle",
               fill=(MUTED if v == "-" else INK), bold=(i == 0))
        x += CW[i]
    y += 26

# ---- addr visual ----
ay = y + 30
f.text(40, ay, "addr field is the GENERAL address, decoded per cmd by DFI_CMD_ENCODE:",
       size=11, mono=False, bold=True)
boxes = [("ACT", "{rank,bg,bank} + row", FILL_NEW),
         ("RD/WR", "{rank,bg,bank} + col + ap + bl", FILL_CELL),
         ("MRW/MRR", "{rank} + MRA (+ data)", FILL_LOGIC),
         ("PRE/REF/RFM", "{rank,(bank k)} - no addr", PAPER)]
bx = 40
for lab, txt, fl in boxes:
    f.rect(bx, ay + 14, 350, 50, fill=fl, width=W_CELL)
    f.text(bx + 12, ay + 34, lab, size=10, mono=True, bold=True)
    f.text(bx + 12, ay + 52, txt, size=9, mono=True, fill=MUTED)
    bx += 370

# ---- DFI encode path notes ----
ny = ay + 90
f.text(40, ny, "DFI encode path:", size=11, mono=False, bold=True)
notes = [
    "ALL rows go through DFI_CMD_ENCODE -> CA[13:0] beats + dfi_cs  (one CA bus, one issue point).",
    "2ui is NOT a record field: SEPARATE single flag scheduler -> DFI driver (outside port). 1=2-UI",
    "  (ACT/RD/WR/MRW/MRR/MPC) -> 2 phase slots; 0=1-UI (PRE*/REF*/RFM/SRE/SRX/DES). Held @1:1.",
    "RD/WR arm the data path: WR->WL_LAUNCH (sram=wd_slot), RD->RD_CAP (sram=dbuf).",
    "MRR reads MR on DQ -> arms RD_CAP too (sram=sideband, rob=return tag) - why it can't be offloaded.",
    "PDE/PDX (power-down) are NOT phaser records - pure dfi_cke transitions (POWER_MGMT).",
    "bg/bank are DDR5-encoded INTO addr/CA (no dfi_bg/dfi_bank pins); PREsb/REFsb use bank index k across all BGs.",
]
for i, s in enumerate(notes):
    f.text(52, ny + 22 + i * 19, "- " + s, size=9, mono=False)

f.save("fig_74_cmd_field_matrix.svg")
print("wrote fig_74_cmd_field_matrix.svg")
