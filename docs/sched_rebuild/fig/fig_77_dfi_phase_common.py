from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_77 — DFI ports split: PHASE-replicated (_p0 shown, x GEAR) vs COMMON single.
# curly braces group by interface (DFI spec Table 1). _p0 only; rest are copies.

OUT = "#2a8f86"; IN = "#b0602a"
ROWH = 19


def brace(x, y1, y2, label):
    ym = (y1 + y2) / 2
    f.path(f"M{x} {y1} C{x+8} {y1} {x+8} {ym} {x+15} {ym} "
           f"C{x+8} {ym} {x+8} {y2} {x} {y2}", stroke=INK)
    f.text(x + 21, ym + 4, label, size=9, mono=False, bold=True)


def box(x, y, w, title, rows, groups, fill):
    h = 30 + len(rows) * ROWH
    f.rect(x, y, w, h, fill="none", width=1.6)
    f.rect(x, y, w, 26, fill=fill, width=1.6)
    f.text(x + w / 2, y + 18, title, size=11, anchor="middle", bold=True)
    yy = y + 26
    for d, nm, wd in rows:
        yc = yy + 13
        col = OUT if d == "o" else IN
        if d == "o":
            f.line(x + 5, yc - 4, x + 16, yc - 4, arrow=True, stroke=col)
        else:
            f.line(x + 16, yc - 4, x + 5, yc - 4, arrow=True, stroke=col)
        f.text(x + 22, yc, nm, size=8, mono=True)
        f.text(x + w - 6, yc, wd, size=7, mono=True, anchor="end", fill=MUTED)
        f.line(x, yy, x + w, yy, stroke=FAINT)
        yy += ROWH
    # braces per group
    acc = 0
    bx = x + w + 5
    for lab, cnt in groups:
        y1 = y + 26 + acc * ROWH + 2
        y2 = y + 26 + (acc + cnt) * ROWH - 2
        brace(bx, y1, y2, lab)
        acc += cnt
    return h


PHASE = [
    ("o", "dfi_address_p0", "14"), ("o", "dfi_cs_p0", "N_RANKS"),
    ("o", "dfi_cke_p0", "N_RANKS"), ("o", "dfi_odt_p0", "N_RANKS"),
    ("o", "dfi_reset_n_p0", "1"), ("o", "dfi_2n_mode_p0", "1"),
    ("o", "dfi_cs_geardown_p0", "1"), ("o", "dfi_dram_clk_disable_p0", "per-clk"),
    ("o", "dfi_parity_in_p0", "1"), ("i", "dfi_alert_n_p0", "1"),
    ("o", "dfi_wrdata_p0", "2*DQ"), ("o", "dfi_wrdata_en_p0", "slices"),
    ("o", "dfi_wrdata_mask_p0", "2*DQ/8"), ("o", "dfi_wrdata_cs_p0", "PHY_RANK"),
    ("o", "dfi_wrdata_crc_p0", "DATA/8"), ("o", "dfi_wrdata_ecc_p0", "opt"),
    ("i", "dfi_rddata_w0", "2*DQ"), ("o", "dfi_rddata_en_p0", "slices"),
    ("i", "dfi_rddata_valid_w0", "slices"), ("o", "dfi_rddata_cs_p0", "PHY_RANK"),
    ("i", "dfi_rddata_dnv_w0", "slices"), ("i", "dfi_rddata_dbi_w0", "DATA/8"),
    ("i", "dfi_rddata_crc_w0", "DATA/8"),
]
PGRP = [("Command", 10), ("Write Data", 6), ("Read Data", 7)]

COMMON = [
    ("o", "dfi_init_start", "1"), ("i", "dfi_init_complete", "1"),
    ("o", "dfi_cmd_freq_ratio", "2"), ("o", "dfi_data_freq_ratio", "2"),
    ("o", "dfi_freq_fsp", "1-2"), ("o", "dfi_frequency", "W"),
    ("o", "dfi_ctrlupd_req", "1"), ("i", "dfi_ctrlupd_ack", "1"),
    ("i", "dfi_phyupd_req", "1"), ("o", "dfi_phyupd_ack", "1"),
    ("i", "dfi_phyupd_type", "2"), ("i", "dfi_error", "1"),
    ("i", "dfi_error_info", "W*4"), ("o", "dfi_lp_ctrl_req", "1"),
    ("i", "dfi_lp_ctrl_ack", "1"), ("o", "dfi_lp_ctrl_wakeup", "1"),
    ("o", "dfi_lp_data_req", "1"), ("i", "dfi_lp_data_ack", "1"),
    ("o", "dfi_lp_data_wakeup", "1"),
]
CGRP = [("Status", 6), ("Update", 5), ("Error / Low-Power", 8)]

H = 30 + max(len(PHASE), len(COMMON)) * ROWH
f = Fig(1120, 110 + H)
f.text(40, 28, "DFI ports - phase-replicated vs common-single", size=12, mono=False, bold=True)
f.text(40, 45, "-> MC->PHY, <- PHY->MC.  _p0 shown (x GEAR copies).  braces = DFI interface groups.",
       size=8, mono=False, fill=MUTED)

box(50, 66, 250, "PHASE (_p0, x GEAR)", PHASE, PGRP, FILL_ACTIVE)
box(560, 66, 250, "COMMON (single, x1)", COMMON, CGRP, FILL_LOGIC)

f.save("fig_77_dfi_phase_common.svg")
print("wrote fig_77_dfi_phase_common.svg")
