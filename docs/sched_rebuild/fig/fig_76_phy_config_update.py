from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_76 — PHY config / runtime update. init config push, MC-initiated ctrlupd,
# PHY-initiated phyupd. Which regs the MC updates vs the PHY updates.

MCU = "#7a4fb0"; PHU = "#2a8f86"; INI = "#b0602a"
f = Fig(1520, 840)


def blk(x, y, w, h, name, sub, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + w / 2, y + 20, name, size=11, anchor="middle", bold=True)
    if sub:
        f.text(x + w / 2, y + 38, sub, size=8, anchor="middle", fill=MUTED)


f.text(40, 32, "PHY config + runtime update  (init / ctrlupd / phyupd)", size=15,
       mono=False, bold=True)

# ---- MC side ----
f.rect(50, 90, 380, 300, fill="none", width=1.2, stroke=FAINT)
f.text(60, 108, "MC", size=12, bold=True)
blk(70, 120, 340, 70, "TIMING_REG_FILE / CONFIG", "tRC.. tphy_* gear MR-shadow ODT/CS-map",
    FILL_CELL)
blk(70, 210, 340, 60, "FREQ_CHANGE / CFG_CTRL", "computes + writes config", FILL_LOGIC)
blk(70, 290, 340, 70, "UPDATE_CTRL", "ctrlupd (out) / phyupd (in) handshakes", FILL_NEW)

# ---- PHY side ----
f.rect(1090, 90, 380, 300, fill="none", width=1.2, stroke=FAINT)
f.text(1100, 108, "PHY", size=12, bold=True)
blk(1110, 120, 340, 70, "PHY_CFG_REGS", "leveling VREF delay-lines drift", FILL_ACTIVE)
blk(1110, 210, 340, 60, "PHY_TRAIN / DRIFT", "retrain, VREF/gate track", FILL_LOGIC)
blk(1110, 290, 340, 70, "PHY UPDATE_IF", "raises phyupd / accepts ctrlupd", FILL_NEW)

# ---- channels (middle) ----
def chan(y, label, forward, col, note):
    if forward:
        f.line(430, y, 1090, y, arrow=True, stroke=col)
    else:
        f.line(1090, y, 430, y, arrow=True, stroke=col)
    f.text(760, y - 6, label, size=9, mono=True, anchor="middle", fill=col)
    f.text(760, y + 12, note, size=8, mono=False, anchor="middle", fill=MUTED)

chan(150, "dfi_init_start ->  ...  <- dfi_init_complete", True, INI,
     "INIT: MC pushes ALL config; PHY trains; init_complete")
chan(230, "dfi_ctrlupd_req -> / <- dfi_ctrlupd_ack", True, MCU,
     "MC-initiated: MC wants a quiet window to update PHY cfg")
chan(310, "<- dfi_phyupd_req/type / dfi_phyupd_ack ->", False, PHU,
     "PHY-initiated: PHY wants to retrain; MC grants (pauses)")

# ---- who updates what ----
uy = 440
f.text(50, uy, "Which registers get updated, by whom & when:", size=12, mono=False, bold=True)

# MC-updates box
f.rect(50, uy + 16, 700, 170, fill="none", width=1.4, stroke=MCU)
f.text(64, uy + 38, "MC UPDATES  (init + ctrlupd)", size=11, bold=True, fill=MCU)
mc = ["timing_reg_file: tRC/tRCD/... + tphy_wrlat/rdlat  (DRAM + PHY-iface timing)",
      "gear / dfi_cmd_freq_ratio / dfi_data_freq_ratio / freq_fsp  (on DVFS)",
      "MR shadow (CL/CWL/RTT...) - re-sent via MRW on freq change",
      "ODT / CS maps, 2N / geardown mode",
      "WHEN: at INIT (push all); at freq-change -> ctrlupd window to re-push to PHY"]
for i, s in enumerate(mc):
    f.text(64, uy + 60 + i * 22, "- " + s, size=9, mono=False)

# PHY-updates box
f.rect(780, uy + 16, 690, 170, fill="none", width=1.4, stroke=PHU)
f.text(794, uy + 38, "PHY UPDATES  (init-train + phyupd)", size=11, bold=True, fill=PHU)
ph = ["read/write leveling, gate training results",
      "VREF, DQ/DQS delay lines, per-bit deskew",
      "drift / temperature compensation (periodic)",
      "reported via phyupd_type; MC just grants the window",
      "WHEN: at INIT training; then PHY raises dfi_phyupd_req when it needs to retrain"]
for i, s in enumerate(ph):
    f.text(794, uy + 60 + i * 22, "- " + s, size=9, mono=False)

f.caption(40, uy + 220,
          "INIT (orange): MC pushes ALL config, PHY trains, init_complete. ctrlupd (purple, "
          "MC-initiated) = MC asks a quiet window to re-push PHY cfg (e.g. post freq-change); phyupd "
          "(teal, PHY-initiated) = PHY asks to retrain, MC grants by pausing. Neither writes the "
          "other's regs directly - they hand off through the update window.")

f.save("fig_76_phy_config_update.svg")
print("wrote fig_76_phy_config_update.svg")
