from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_75 — the PHY as one tall rectangle with ALL DFI ports inside; curly braces on
# the right group ports by interface type. _p0 shown (rest _pN copies). Parametric.

OUT = "#2a8f86"; IN = "#b0602a"
RX, RW = 360, 250          # rect x, width (slim)
ROWH = 20
Y0 = 96

# (dir, name, width)  grouped; group boundaries by the GROUPS list
PORTS = [
    # COMMAND
    ("o", "dfi_address_p0", "14"),
    ("o", "dfi_cs_p0", "N_RANKS"),
    ("o", "dfi_cke_p0", "N_RANKS"),
    ("o", "dfi_odt_p0", "N_RANKS"),
    ("o", "dfi_reset_n_p0", "1"),
    ("o", "dfi_2n_mode_p0", "1"),
    ("o", "dfi_cs_geardown_p0", "1"),
    ("o", "dfi_dram_clk_disable_p0", "per-clk"),
    ("o", "dfi_parity_in_p0", "1"),
    ("i", "dfi_alert_n_p0", "1"),
    # WRITE
    ("o", "dfi_wrdata_p0", "2*DQ"),
    ("o", "dfi_wrdata_en_p0", "slices"),
    ("o", "dfi_wrdata_mask_p0", "2*DQ/8"),
    ("o", "dfi_wrdata_cs_p0", "PHY_RANK"),
    ("o", "dfi_wrdata_crc_p0", "DATA/8"),
    ("o", "dfi_wrdata_ecc_p0", "opt"),
    # READ
    ("i", "dfi_rddata_w0", "2*DQ"),
    ("o", "dfi_rddata_en_p0", "slices"),
    ("i", "dfi_rddata_valid_w0", "slices"),
    ("o", "dfi_rddata_cs_p0", "PHY_RANK"),
    ("i", "dfi_rddata_dnv_w0", "slices"),
    ("i", "dfi_rddata_dbi_w0", "DATA/8"),
    ("i", "dfi_rddata_crc_w0", "DATA/8"),
    # STATUS / UPDATE
    ("o", "dfi_init_start", "1"),
    ("i", "dfi_init_complete", "1"),
    ("o", "dfi_cmd_freq_ratio", "2"),
    ("o", "dfi_data_freq_ratio", "2"),
    ("o", "dfi_freq_fsp", "1-2"),
    ("o", "dfi_frequency", "W"),
    ("o", "dfi_ctrlupd_req", "1"),
    ("i", "dfi_ctrlupd_ack", "1"),
    ("i", "dfi_phyupd_req", "1"),
    ("o", "dfi_phyupd_ack", "1"),
    ("i", "dfi_phyupd_type", "2"),
    # ERROR / LP
    ("i", "dfi_error", "1"),
    ("i", "dfi_error_info", "W*4"),
    ("o", "dfi_lp_ctrl_req", "1"),
    ("i", "dfi_lp_ctrl_ack", "1"),
    ("o", "dfi_lp_ctrl_wakeup", "1"),
    ("o", "dfi_lp_data_req", "1"),
    ("i", "dfi_lp_data_ack", "1"),
    ("o", "dfi_lp_data_wakeup", "1"),
]
# group: (label, count)
GROUPS = [
    ("COMMAND  (cmd-clk)", 10),
    ("WRITE DATA  (data-clk)", 6),
    ("READ DATA  (data-clk)", 7),
    ("STATUS / UPDATE  (ctrl-clk)", 11),
    ("ERROR / LOW-POWER  (ctrl-clk)", 8),
]

N = len(PORTS)
H = N * ROWH
f = Fig(1000, Y0 + H + 80)

f.text(40, 34, "PHY  -  DFI interface (all ports, one module)", size=15, mono=False, bold=True)
f.text(40, 54, "arrow: -> = MC->PHY (drive), <- = PHY->MC.  _p0 = phase 0 (rest _pN copies).  "
       "widths parametric.", size=9, mono=False, fill=MUTED)

# the rect
f.rect(RX, Y0, RW, H, fill=FILL_ACTIVE, width=1.8)
f.text(RX + RW / 2, Y0 - 8, "PHY", size=13, anchor="middle", bold=True)

# rows
for i, (d, nm, wd) in enumerate(PORTS):
    y = Y0 + i * ROWH + 14
    col = OUT if d == "o" else IN
    if d == "o":
        f.line(RX + 5, y - 4, RX + 17, y - 4, arrow=True, stroke=col)
    else:
        f.line(RX + 17, y - 4, RX + 5, y - 4, arrow=True, stroke=col)
    f.text(RX + 22, y, nm, size=8, mono=True)
    f.text(RX + RW - 6, y, wd, size=7, mono=True, anchor="end", fill=MUTED)
    if i:
        f.line(RX, Y0 + i * ROWH, RX + RW, Y0 + i * ROWH, stroke=FAINT)


def brace(x, y1, y2, label):
    ym = (y1 + y2) / 2
    f.path(f"M{x} {y1} C{x+10} {y1} {x+10} {ym} {x+18} {ym} "
           f"C{x+10} {ym} {x+10} {y2} {x} {y2}", stroke=INK)
    f.text(x + 26, ym + 4, label, size=10, mono=False, bold=True)


# braces per group on the right
bx = RX + RW + 6
acc = 0
for lab, cnt in GROUPS:
    y1 = Y0 + acc * ROWH + 3
    y2 = Y0 + (acc + cnt) * ROWH - 3
    brace(bx, y1, y2, lab)
    acc += cnt

f.caption(40, Y0 + H + 50,
          "The PHY presents ONE DFI interface; all ports live on it. Braces group by interface type "
          "/ reference clock domain: command (cmd-clk), write & read data (data-clk), status/update "
          "and error/low-power (ctrl-clk). Phase signals (_pN) are x GEAR copies; only _p0 drawn.")

f.save("fig_75_phy_port_rect.svg")
print("wrote fig_75_phy_port_rect.svg")
