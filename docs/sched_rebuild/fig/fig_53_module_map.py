from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_53 — MC-core module map: every block + named connections + glue.
# Build view (modules/interfaces), not per-invariant. One channel.

f = Fig(1640, 1060)


def group(x, y, w, h, title, mods, fill=FILL_LOGIC):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    f.text(x + 12, y + 24, title, size=13, mono=False, bold=True)
    for i, m in enumerate(mods):
        f.text(x + 20, y + 50 + i * 22, m, size=11, mono=True)


def alab(x, y, s, anchor="middle"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 40, "MC-Core module map - blocks, connections, glue (one channel)",
       size=16, mono=False, bold=True)

# ---- spine: INGRESS -> ARB -> PHASER -> DFI ----
group(40, 110, 300, 320, "INGRESS  (per rank lane)", [
    "axi_if  (req in)", "r/w_req_afifo  (CDC)", "rd/wr_bp_fifo  (split)",
    "turn_ctrl + wlr_sel", "lookahead  (4-entry)", "bank_dec  (1-of-32)"],
    fill=FILL_CELL)
group(380, 110, 320, 320, "ARB TREE", [
    "bank_cells x32  (FSM)", "cmd_arb  (cas/act/pre W)", "bgb_arb x8  (bank-in-BG)",
    "bg_arb  (BG-in-rank)", "l3  class-split 2:1", "-> <=3 class winners"],
    fill=FILL_ACTIVE)
group(740, 110, 280, 320, "PHASER", [
    "phase_packer  (tokens", "   + phase_off)", "ca_beat_encoder", "   (2-cyc -> 2 beats)",
    "dfi_mux  (init sel)"], fill=FILL_NEW)
f.rect(1050, 170, 120, 110, fill=FILL_LOGIC, width=W_CELL)
f.text(1110, 210, "DFI / PHY", size=12, mono=False, anchor="middle", bold=True)
f.text(1110, 230, "-> DRAM", size=11, mono=False, anchor="middle", fill=MUTED)

# ---- scoreboard rail (under ARB) ----
group(380, 470, 320, 250, "SCOREBOARD  (timestamp)", [
    "gc  (CK, += gear)", "timing_const  (shared)", "bank/bgs/bgd/rank/global",
    "  next_* regs (13b)", "cmp: (gc-next)[MSB]", "  -> can_act/cas/pre"],
    fill=FILL_LOGIC)

# ---- maint engine (under ingress) ----
group(40, 470, 300, 250, "MAINT ENGINE  (peer)", [
    "7 FSMs: init/refresh/rfm", "   /zqcal/mr_poll/mr_write/pwr",
    "mr_read_arb", "freq_change  (stub)", "error/alert_n  (stub)"],
    fill=FILL_LOGIC)

# ---- glue ----
group(740, 470, 280, 250, "GLUE  (portability)", [
    "mc_pkg  (params,", "  timing_t, typedefs)", "dfi_if   axi_if",
    "arb_if   sb_if", "-> swap pkg = diff DDR"], fill=FILL_NEW)

# ---- data path (right) ----
group(1200, 110, 400, 610, "DATA PATH", [
    "WRITE:", "  wr_accum (64B+WSTRB)", "  wd_sram + wr_ptr", "  write_rob {N,gen,done}",
    "  wr_split + wl_launch", "     -> dfi_wrdata", "", "READ:",
    "  rd_cap + rd_accum", "     <- dfi_rddata", "  -> rd_sram", "",
    "COMPLETION:", "  rd_done/wr_done merge", "  -> resp_afifo -> CIF"],
    fill=FILL_CELL)

# ================= connections =================
f.line(10, 200, 38, 200, arrow=True)
alab(20, 192, "AXI", "start")
f.line(340, 250, 378, 250, arrow=True)
alab(360, 242, "REQ")
f.line(700, 250, 738, 250, arrow=True)
alab(720, 242, "<=3 grants")
f.line(1020, 225, 1048, 225, arrow=True)
alab(1034, 217, "dfi_if")
f.line(1170, 225, 1210, 225, arrow=True)
alab(1210, 217, "DRAM", "end")

# scoreboard <-> arb
f.line(520, 468, 520, 432, arrow=True)
alab(516, 450, "can_*", "end")
f.path("M560 432 V468", arrow=True, dashed=True)
alab(566, 450, "commit", "start")
# scoreboard -> phaser
f.path("M700 555 H720 V430", arrow=True, dashed=True)
alab(724, 450, "gc/dqFree", "start")

# maint -> arb + phaser + dfi
f.path("M340 545 H358 V430", arrow=True, dashed=True)
alab(344, 450, "flags", "start")
f.path("M300 470 V455 H1090 V280", arrow=True, dashed=True)
alab(1000, 300, "init_done -> dfi_mux", "middle")

# phaser -> data (arm) ; axi wdata -> data
f.line(1020, 340, 1198, 340, arrow=True)
alab(1110, 332, "arm wr/rd @ CAS-commit")
f.path("M120 110 V80 H1300 V110", arrow=True, dashed=True)
alab(700, 74, "AXI write data -> wr_accum", "middle")
# data -> CIF
f.line(1400, 720, 1400, 760, arrow=True)
alab(1412, 752, "-> CIF (resp)", "start")

f.caption(40, 1030,
          "Build as parametric SystemVerilog: mc_pkg + interfaces (dfi/axi/arb/sb) glue the "
          "modules; ports come from figs 39-51. Ingress -> arb (scoreboard folds legality into "
          "can_*) -> phaser -> DFI; maint injects flags; data path arms at CAS-commit. IP "
          "Integrator only at the SoC top - internals stay text SV (git + DDR-portable).")

f.save("fig_53_module_map.svg")
print("wrote fig_53_module_map.svg")
