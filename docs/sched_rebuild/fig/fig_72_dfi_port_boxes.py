from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_72 — DFI ports grouped in boxes (draw.io style). Names inside, arrow = dir
# (out = MC->PHY, in = PHY->MC). Phase signals shown as _p0 only (rest _p1.._pN-1
# are identical copies, omitted). N_RANKS / DQ / GEAR parametric.

OUT = "#2a8f86"; IN = "#b0602a"
f = Fig(1720, 1180)

f.text(40, 32, "DFI 5.2 ports (DDR5) - grouped boxes", size=16, mono=False, bold=True)
f.text(40, 54, "arrow: -> = out (MC->PHY), <- = in (PHY->MC).  _p0 = phase 0 only; "
       "_p1.._p(GEAR-1) are identical copies (omitted).  N_RANKS/DQ/GEAR parametric.",
       size=10, mono=False, fill=MUTED)


def box(x, y, w, title, rows, fill=FILL_NEW):
    h = 42 + len(rows) * 22
    f.rect(x, y, w, h, fill="none", width=1.6)
    f.rect(x, y, w, 30, fill=fill, width=1.6)
    f.text(x + w / 2, y + 20, title, size=12, anchor="middle", bold=True)
    yy = y + 48
    for d, nm, wd in rows:
        col = OUT if d == "o" else IN
        if d == "o":
            f.line(x + 12, yy - 4, x + 30, yy - 4, arrow=True, stroke=col)
        else:
            f.line(x + 30, yy - 4, x + 12, yy - 4, arrow=True, stroke=col)
        f.text(x + 40, yy, nm, size=10, mono=True, fill=INK)
        f.text(x + w - 12, yy, wd, size=9, mono=True, anchor="end", fill=MUTED)
        yy += 22
    return h


# ---------- COMMAND ----------
box(40, 90, 400, "COMMAND  (Command-clk)", [
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
])

# ---------- WRITE DATA ----------
box(480, 90, 400, "WRITE DATA  (Data-clk)", [
    ("o", "dfi_wrdata_p0", "2*DQ"),
    ("o", "dfi_wrdata_en_p0", "slices"),
    ("o", "dfi_wrdata_mask_p0", "2*DQ/8"),
    ("o", "dfi_wrdata_cs_p0", "PHY_RANK"),
    ("o", "dfi_wrdata_crc_p0", "DATA/8"),
    ("o", "dfi_wrdata_ecc_p0", "opt"),
], fill=FILL_CELL)

# ---------- READ DATA ----------
box(920, 90, 400, "READ DATA  (Data-clk)", [
    ("i", "dfi_rddata_w0", "2*DQ"),
    ("o", "dfi_rddata_en_p0", "slices"),
    ("i", "dfi_rddata_valid_w0", "slices"),
    ("o", "dfi_rddata_cs_p0", "PHY_RANK"),
    ("i", "dfi_rddata_dnv_w0", "slices"),
    ("i", "dfi_rddata_dbi_w0", "DATA/8"),
    ("i", "dfi_rddata_crc_w0", "DATA/8"),
], fill=FILL_CELL)

# ---------- STATUS / UPDATE ----------
box(40, 430, 400, "STATUS / UPDATE  (Control-clk)", [
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
], fill=FILL_LOGIC)

# ---------- ERROR / LOW-POWER ----------
box(480, 430, 400, "ERROR / LOW-POWER  (Control-clk)", [
    ("i", "dfi_error", "1"),
    ("i", "dfi_error_info", "W*4"),
    ("o", "dfi_lp_ctrl_req", "1"),
    ("i", "dfi_lp_ctrl_ack", "1"),
    ("o", "dfi_lp_ctrl_wakeup", "1"),
    ("o", "dfi_lp_data_req", "1"),
    ("i", "dfi_lp_data_ack", "1"),
    ("o", "dfi_lp_data_wakeup", "1"),
], fill=FILL_LOGIC)

f.caption(40, 1160,
          "Command/Write/Read groups are phase-replicated: only _p0 shown; the interface carries "
          "_p0.._p(GEAR-1) identical copies (widths scale x GEAR). Status/Update/Error/LP are "
          "single-phase (Control-clk, no _pN). Legacy DDR3/4 discrete cmd (dfi_act_n/ras_n/cas_n/"
          "we_n/bank/bg) omitted - DDR5 encodes on dfi_address.")

f.save("fig_72_dfi_port_boxes.svg")
print("wrote fig_72_dfi_port_boxes.svg")
