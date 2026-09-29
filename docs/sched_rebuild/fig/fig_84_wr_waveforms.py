from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_CELL, FILL_ACTIVE, FILL_NEW

# fig_84 - write-path waveforms per gear. wr_cmd -> wr_en_pN -> wrdata_pN (byte
# placement) -> mask, + wd_read_ptr + burst_cnt. Disabled phases grouped, not
# drawn. tphy_wrlat/tphy_wrdata small + parametric (shown compact).

CW = 82; RH = 42; X0 = 220


def draw_clk(f, x0, ry, n):
    top = ry + 8; bot = ry + RH - 8; x = x0
    for _ in range(n):
        f.line(x, top, x + CW / 2, top, stroke=INK)
        f.line(x + CW / 2, top, x + CW / 2, bot, stroke=INK)
        f.line(x + CW / 2, bot, x + CW, bot, stroke=INK)
        f.line(x + CW, bot, x + CW, top, stroke=INK)
        x += CW


def draw_bit(f, x0, ry, levels):
    top = ry + 8; bot = ry + RH - 8; x = x0; prev = 0
    for c, lv in enumerate(levels):
        yl = top if lv else bot
        if c > 0 and lv != prev:
            f.line(x, top if prev else bot, x, yl, stroke=INK)
        f.line(x, yl, x + CW, yl, stroke=INK, width=1.6 if lv else 1.0)
        prev = lv; x += CW


def draw_bus(f, x0, ry, cells, fill=FILL_NEW):
    top = ry + 9; bot = ry + RH - 9; mid = ry + RH / 2; x = x0
    for cell in cells:
        if cell is None:
            f.line(x, mid, x + CW, mid, stroke=FAINT)
        else:
            f.rect(x + 2, top, CW - 4, bot - top, fill=fill, stroke=INK, width=1.2, rx=3)
            f.text(x + CW / 2, mid + 3, cell, size=7.2, mono=True, anchor="middle")
        x += CW


def panel(title, sub, n, rows, disabled, fname):
    W = X0 + n * CW + 30
    H = 74 + len(rows) * RH + (78 if disabled else 24)
    f = Fig(W, H)
    f.text(20, 28, title, size=15, bold=True, mono=False)
    f.text(20, 48, sub, size=9, mono=True, fill=MUTED)
    y0 = 74
    for c in range(n + 1):
        f.line(X0 + c * CW, y0 - 6, X0 + c * CW, y0 + len(rows) * RH, stroke=FAINT)
    for c in range(n):
        f.text(X0 + c * CW + CW / 2, y0 - 10, str(c), size=7, mono=True, fill=MUTED, anchor="middle")
    for i, (kind, name, data) in enumerate(rows):
        ry = y0 + i * RH
        f.text(X0 - 12, ry + RH / 2 + 4, name, size=9, mono=True, anchor="end")
        if kind == "clk":
            draw_clk(f, X0, ry, n)
        elif kind == "bit":
            draw_bit(f, X0, ry, data)
        elif kind == "bus":
            draw_bus(f, X0, ry, data)
        elif kind == "busm":
            draw_bus(f, X0, ry, data, fill=FILL_CELL)
        elif kind == "busc":
            draw_bus(f, X0, ry, data, fill=FILL_ACTIVE)
    if disabled:
        dy = y0 + len(rows) * RH + 14
        f.rect(X0, dy, n * CW, 54, fill=PAPER, stroke=INK, width=1.2)
        f.text(X0 + 10, dy + 20, "disabled this gear (no toggle -> DES / driven 0, no waveform):",
               size=9, bold=True)
        f.text(X0 + 10, dy + 40, disabled, size=9, mono=True, fill=MUTED)
    f.save(fname)
    print("wrote", fname)


N = None
# ================= 1:1  (dfi_clk = CK, 1 phase, burst = 8 cyc) =================
panel("Write burst  1:1  (gear=00)", "1 phase p0; 2-UI WR spans 2 CK; burst 8 CK; tphy_wrlat=4, tphy_wrdata=1",
      14, [
      ("clk", "dfi_clk", None),
      ("bus", "wr_cmd (CA p0)", ["WR", "COL"] + [N]*12),
      ("bit", "wr_en_p0", [0,0,0,0,1,1,1,1,1,1,1,1,0,0]),
      ("busc", "wrdata_p0", [N]*5 + ["B0-7","B8-15","B16-23","B24-31","B32-39","B40-47","B48-55","B56-63"] + [N]),
      ("busm", "mask_p0", [N]*5 + ["m0","m1","m2","m3","m4","m5","m6","m7"] + [N]),
      ("bus", "wd_read_ptr", [N]*4 + ["rd@slot"] + [N]*9),
      ("bus", "burst_cnt", [N]*5 + ["8","7","6","5","4","3","2","1"] + [N]),
      ], "dfi_wr_en_p1/p2/p3, dfi_writedata_p1/p2/p3, mask_p1/p2/p3",
      "fig_84a_wr_1to1.svg")

# ================= 1:2  (1 mc_clk = 2 CK, 2 phases, burst = 4 cyc) =============
panel("Write burst  1:2  (gear=01)", "2 phases p0,p1; 2-UI WR fits 1 mc_clk (p0=UI0,p1=UI1); burst 4 mc_clk; wrlat=3, wrdata=1",
      9, [
      ("clk", "dfi_clk", None),
      ("bus", "wr_cmd", ["WR"] + [N]*8),
      ("bit", "wr_en_p0", [0,0,0,1,1,1,1,0,0]),
      ("bit", "wr_en_p1", [0,0,0,1,1,1,1,0,0]),
      ("busc", "wrdata_p0", [N]*4 + ["B0-7","B16-23","B32-39","B48-55"] + [N]),
      ("busc", "wrdata_p1", [N]*4 + ["B8-15","B24-31","B40-47","B56-63"] + [N]),
      ("busm", "mask_p0", [N]*4 + ["m0","m2","m4","m6"] + [N]),
      ("busm", "mask_p1", [N]*4 + ["m1","m3","m5","m7"] + [N]),
      ("bus", "wd_read_ptr", [N]*3 + ["rd@slot"] + [N]*5),
      ("bus", "burst_cnt", [N]*4 + ["4","3","2","1"] + [N]),
      ], "dfi_wr_en_p2/p3, dfi_writedata_p2/p3, mask_p2/p3",
      "fig_84b_wr_1to2.svg")

# ================= 1:4  (1 mc_clk = 4 CK, 4 phases, burst = 2 cyc) =============
panel("Write burst  1:4  (gear=11)", "4 phases p0..p3; 2-UI WR in 1 mc_clk; burst 2 mc_clk; wrlat=3, wrdata=1 (all phases active)",
      8, [
      ("clk", "dfi_clk", None),
      ("bus", "wr_cmd", ["WR"] + [N]*7),
      ("bit", "wr_en_p0", [0,0,0,1,1,0,0,0]),
      ("bit", "wr_en_p1", [0,0,0,1,1,0,0,0]),
      ("bit", "wr_en_p2", [0,0,0,1,1,0,0,0]),
      ("bit", "wr_en_p3", [0,0,0,1,1,0,0,0]),
      ("busc", "wrdata_p0", [N]*4 + ["B0-7","B32-39"] + [N]*2),
      ("busc", "wrdata_p1", [N]*4 + ["B8-15","B40-47"] + [N]*2),
      ("busc", "wrdata_p2", [N]*4 + ["B16-23","B48-55"] + [N]*2),
      ("busc", "wrdata_p3", [N]*4 + ["B24-31","B56-63"] + [N]*2),
      ("busm", "mask_p0..p3", [N]*4 + ["m0-3","m4-7"] + [N]*2),
      ("bus", "wd_read_ptr", [N]*3 + ["rd@slot"] + [N]*4),
      ("bus", "burst_cnt", [N]*4 + ["2","1"] + [N]*2),
      ], None,
      "fig_84c_wr_1to4.svg")
