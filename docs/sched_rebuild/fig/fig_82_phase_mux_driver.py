from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_82 — DFI command-port phase mux driver. Shows p0 as the representative
# lane: encoded per-UI vectors feed one mux per phase; gear picks the select
# (1:1 = temporal UI counter, 1:2/1:4 = constant spatial wiring). Same driver
# replicated across every command-group port.

SEL = "#7a4fb0"; GEAR = "#b0602a"; DATA = "#2a8f86"
f = Fig(1520, 900)


def mux(cx, cy, w, h, name, faint=False):
    st = FAINT if faint else INK
    # trapezoid: wide left (inputs), narrow right (output)
    f.path(f"M{cx-w/2} {cy-h/2} L{cx+w/2} {cy-h/4} L{cx+w/2} {cy+h/4} "
           f"L{cx-w/2} {cy+h/2} Z", stroke=st)
    f.text(cx-4, cy+4, name, size=10, anchor="middle", bold=True,
           fill=(FAINT if faint else INK))


f.text(40, 30, "DFI command-port phase mux driver  (p0 shown; all phases + all ports identical)",
       size=15, mono=False, bold=True)

# ---- clk/UI convention legend ----
f.rect(1160, 12, 340, 62, fill=FILL_LOGIC, width=1.2, stroke=INK)
f.text(1174, 32, "convention: 1 CK = 2 UI  (always)", size=10, mono=True, bold=True)
f.text(1174, 50, "DQ (data) = DDR, 2 UI/CK -> BL16 = 8 CK", size=8, mono=True, fill=MUTED)
f.text(1174, 66, "CA (command) = SDR, 1 beat/CK; 'ckN' = one CK beat", size=8, mono=True, fill=MUTED)

# ---- bundle slots ----
f.text(40, 74, "scheduler bundle", size=10, bold=True)
sy = [90, 138, 186, 234]
for i, y in enumerate(sy):
    f.rect(40, y, 130, 38, fill=FILL_CELL, width=1.4, rx=5)
    f.text(105, y+23, f"slot s{i}", size=10, anchor="middle", bold=True)
f.text(46, 292, "each = phaser record", size=8, mono=True, fill=MUTED)

# ---- encode ----
f.block(220, 90, 180, 182, "ENCODE", "OPCODE_ROM + FIELD_MUX")
f.text(228, 290, "per slot -> ca_ck0[13:0], ca_ck1[13:0]", size=8, mono=True, fill=DATA)
for y in sy:
    f.line(170, y+19, 220, y+19, arrow=True, stroke=INK)

# ---- candidate bus into p0 mux ----
cand = ["s0.ck0", "s0.ck1", "s1.ck0", "s1.ck1"]
cy0 = [120, 160, 200, 240]
for lab, y in zip(cand, cy0):
    f.line(400, 181, 470, y, arrow=True, stroke=DATA)
    f.text(408, y-4, lab, size=8, mono=True, fill=DATA)

# ---- p0 mux ----
mux(560, 180, 120, 150, "p0 MUX")
f.line(620, 180, 720, 180, arrow=True, stroke=INK)
f.text(628, 172, "dfi_address_p0[13:0]", size=9, mono=True, bold=True)

# select in from below (straight up into the mux)
f.line(560, 380, 560, 258, arrow=True, stroke=SEL)
f.text(575, 320, "phase_sel[p0]", size=9, mono=True, fill=SEL, bold=True)

# ---- gear / UI counter driving the select ----
f.block(485, 380, 150, 90, "GEAR + CLK_CNT", "-> phase_sel")
f.text(300, 402, "gear[1:0]", size=9, mono=True, fill=GEAR)
f.line(360, 398, 483, 410, arrow=True, stroke=GEAR)
f.text(300, 440, "two_clk / repeat", size=9, mono=True, fill=GEAR)
f.line(390, 436, 483, 440, arrow=True, stroke=GEAR)

# p1..p3 note (muxes identical, omitted for clarity)
f.text(430, 520, "p1..p3 = identical mux, phase_sel", size=9, mono=True, fill=MUTED)
f.text(430, 536, "offset by phase index (spatial)", size=9, mono=True, fill=MUTED)

# ---- gear behavior table ----
gx, gy = 780, 90
f.rect(gx, gy, 700, 190, fill=PAPER, width=1.4, stroke=INK)
f.text(gx+16, gy+24, "gear -> select behavior", size=11, bold=True)
f.text(gx+16, gy+50, "1:1 (gear=00): only p0. select = TEMPORAL CLK counter:",
       size=9, mono=True)
f.text(gx+40, gy+68, "clk0 -> s0.ck0 , clk1 -> s0.ck1 (held by two_clk/repeat). slot sel const = s0.",
       size=8, mono=True, fill=MUTED)
f.text(gx+16, gy+96, "1:2 (gear=01): p0=s0.ck0  p1=s0.ck1   (one 2-CLK cmd / mc_clk)",
       size=9, mono=True)
f.text(gx+16, gy+120, "1:4 (gear=11): p0=s0.ck0 p1=s0.ck1 p2=s1.ck0 p3=s1.ck1",
       size=9, mono=True)
f.text(gx+40, gy+138, "(two 2-CLK cmds / mc_clk). select = CONSTANT spatial wiring, no counter.",
       size=8, mono=True, fill=MUTED)
f.text(gx+16, gy+166, "1-CLK cmd (PRE/REF/RFM): occupies ONE phase; next phase free for another cmd.",
       size=8, mono=True, fill=SEL)

# ---- all command ports share the driver ----
px, py = 780, 320
f.rect(px, py, 700, 300, fill=PAPER, width=1.4, stroke=INK)
f.text(px+16, py+24, "same phase-mux driver, every command-group port (per phase pN):",
       size=11, bold=True)
ports = [
    ("dfi_address_pN[13:0]", "CA bus", "OPCODE_ROM+FIELD_MUX", "muxed / phase"),
    ("dfi_cs_n_pN[NR-1:0]", "rank select", "CS_GEN (one-cold)", "muxed / phase"),
    ("dfi_cke_pN[NR-1:0]", "clock enable", "POWER_FSM", "muxed / phase"),
    ("dfi_odt_pN[NR-1:0]", "ODT", "ODT_GEN (WL-aligned)", "muxed / phase"),
    ("dfi_parity_pN", "CA parity", "parity over CA", "muxed / phase"),
    ("dfi_2n_mode", "2N timing", "config bit", "STATIC (no mux)"),
    ("dfi_reset_n", "DRAM reset", "INIT_FSM", "STATIC (no mux)"),
    ("dfi_dram_clk_disable_pN", "CK gate", "power-down", "muxed / phase"),
]
yy = py + 48
for nm, role, drv, mode in ports:
    col = MUTED if "STATIC" in mode else INK
    f.text(px+24, yy, nm, size=9, mono=True, fill=col, bold=True)
    f.text(px+270, yy, role, size=8.5, mono=False, fill=col)
    f.text(px+390, yy, drv, size=8, mono=True, fill=col)
    f.text(px+560, yy, mode, size=8, mono=True, fill=(GEAR if "STATIC" in mode else DATA))
    yy += 30
f.text(px+16, yy+2, "STATIC ports (2n_mode, reset_n) = one value all phases -> no per-phase mux.",
       size=8, mono=True, fill=MUTED)

f.caption(40, 680,
          "One mux per phase per command port. Candidates = the bundle slots' per-UI encoded "
          "vectors; phase_sel routes {slot,ck} onto the phase. 1:1 = temporal CLK counter; "
          "1:2/1:4 = constant spatial wiring. Static ports skip the mux.")

f.save("fig_82_phase_mux_driver.svg")
print("wrote fig_82_phase_mux_driver.svg")
