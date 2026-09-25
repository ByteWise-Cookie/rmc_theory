from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_77 — DFI ports split two ways: PHASE-replicated (_pN, x GEAR) box vs COMMON
# single (control-clk, no _pN) box.

OUT = "#2a8f86"; IN = "#b0602a"
ROWH = 20


def box(x, y, w, title, sub, rows, fill):
    h = 50 + len(rows) * ROWH
    f.rect(x, y, w, h, fill="none", width=1.8)
    f.rect(x, y, w, 44, fill=fill, width=1.8)
    f.text(x + w / 2, y + 20, title, size=12, anchor="middle", bold=True)
    f.text(x + w / 2, y + 36, sub, size=8, anchor="middle", fill=MUTED)
    yy = y + 44
    for d, nm, wd in rows:
        yc = yy + 14
        col = OUT if d == "o" else IN
        if d == "o":
            f.line(x + 6, yc - 4, x + 18, yc - 4, arrow=True, stroke=col)
        else:
            f.line(x + 18, yc - 4, x + 6, yc - 4, arrow=True, stroke=col)
        f.text(x + 24, yc, nm, size=8, mono=True)
        f.text(x + w - 6, yc, wd, size=7, mono=True, anchor="end", fill=MUTED)
        f.line(x, yy, x + w, yy, stroke=FAINT)
        yy += ROWH
    return h


PHASE = [
    ("o", "dfi_address_pN", "14"), ("o", "dfi_cs_pN", "N_RANKS"),
    ("o", "dfi_cke_pN", "N_RANKS"), ("o", "dfi_odt_pN", "N_RANKS"),
    ("o", "dfi_reset_n_pN", "1"), ("o", "dfi_2n_mode_pN", "1"),
    ("o", "dfi_cs_geardown_pN", "1"), ("o", "dfi_dram_clk_disable_pN", "per-clk"),
    ("o", "dfi_parity_in_pN", "1"), ("i", "dfi_alert_n_pN", "1"),
    ("o", "dfi_wrdata_pN", "2*DQ"), ("o", "dfi_wrdata_en_pN", "slices"),
    ("o", "dfi_wrdata_mask_pN", "2*DQ/8"), ("o", "dfi_wrdata_cs_pN", "PHY_RANK"),
    ("o", "dfi_wrdata_crc_pN", "DATA/8"), ("o", "dfi_wrdata_ecc_pN", "opt"),
    ("i", "dfi_rddata_wN", "2*DQ"), ("o", "dfi_rddata_en_pN", "slices"),
    ("i", "dfi_rddata_valid_wN", "slices"), ("o", "dfi_rddata_cs_pN", "PHY_RANK"),
    ("i", "dfi_rddata_dnv_wN", "slices"), ("i", "dfi_rddata_dbi_wN", "DATA/8"),
    ("i", "dfi_rddata_crc_wN", "DATA/8"),
]
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

H = 50 + max(len(PHASE), len(COMMON)) * ROWH
f = Fig(760, 130 + H)
f.text(40, 32, "DFI ports: phase-replicated vs common-single", size=15, mono=False, bold=True)
f.text(40, 52, "arrow: -> MC->PHY, <- PHY->MC. widths parametric.", size=9, mono=False, fill=MUTED)

box(50, 90, 300, "PHASE-REPLICATED", "_pN / _wN  (x GEAR copies)", PHASE, FILL_ACTIVE)
box(420, 90, 300, "COMMON SINGLE", "control-clk, no _pN (x1)", COMMON, FILL_LOGIC)

f.caption(40, 110 + H,
          "PHASE box: each signal exists x GEAR (dfi_*_p0.._p(GEAR-1)) - command CA/CS/CKE/ODT + "
          "write + read data; scale with the frequency ratio. COMMON box: single-instance control-"
          "clk handshakes (status/freq/update/error/low-power) - NO phase replication.")

f.save("fig_77_dfi_phase_common.svg")
print("wrote fig_77_dfi_phase_common.svg")
