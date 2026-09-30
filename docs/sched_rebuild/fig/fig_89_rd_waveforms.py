from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_ACTIVE, FILL_NEW, FILL_CELL

# fig_89 - read data-return waveforms per gear. rd_cmd +tphy_rdlat -> rddata_en
# (MC opens window); PHY returns rddata_valid + rddata within it; RD_ACCUM
# gathers -> one 512b RD_SRAM write -> rd_done. PHY-timed (not self-timed).

CW = 74; RH = 40; X0 = 250
RL = "#7a4fb0"; PHY = "#2a8f86"


def xc(c, x0=X0): return x0 + c * CW


def clk(f, y, n):
    top = y+8; bot = y+RH-8; x = X0
    for _ in range(n):
        f.line(x, top, x+CW/2, top, stroke=INK); f.line(x+CW/2, top, x+CW/2, bot, stroke=INK)
        f.line(x+CW/2, bot, x+CW, bot, stroke=INK); f.line(x+CW, bot, x+CW, top, stroke=INK); x += CW


def bit(f, y, lv, col=INK):
    top = y+8; bot = y+RH-8; x = X0; prev = lv[0]
    for c, v in enumerate(lv):
        yl = top if v else bot
        if c > 0 and v != prev: f.line(x, top if prev else bot, x, yl, stroke=col)
        f.line(x, yl, x+CW, yl, stroke=col, width=1.9 if v else 1.0); prev = v; x += CW


def bus(f, y, cells, fill=FILL_ACTIVE):
    top = y+9; bot = y+RH-9; mid = y+RH/2; x = X0
    for cell in cells:
        if cell is None: f.line(x, mid, x+CW, mid, stroke=FAINT)
        else:
            f.rect(x+1.5, top, CW-3, bot-top, fill=fill, stroke=INK, width=1.0, rx=2)
            f.text(x+CW/2, mid+3, cell, size=7, mono=True, anchor="middle")
        x += CW


def darrow(f, c1, c2, y, label, col):
    x1 = xc(c1); x2 = xc(c2)
    f.line(x1, y, x2, y, arrow=True, stroke=col); f.line(x2, y, x1, y, arrow=True, stroke=col)
    f.text((x1+x2)/2, y-5, label, size=7.5, mono=True, anchor="middle", fill=col)


def panel(title, sub, n, rows, disabled, rdlat_to, fname):
    W = X0 + n*CW + 24
    H = 78 + len(rows)*RH + (70 if disabled else 40)
    f = Fig(W, H)
    f.text(20, 26, title, size=14, bold=True, mono=False)
    f.text(20, 45, sub, size=8.5, mono=True, fill=MUTED)
    y0 = 74
    for c in range(n+1): f.line(xc(c), y0-6, xc(c), y0+len(rows)*RH, stroke=FAINT)
    for c in range(n): f.text(xc(c)+CW/2, y0-10, str(c), size=6.5, mono=True, fill=MUTED, anchor="middle")
    yy = {}
    for i, (kind, name, data) in enumerate(rows):
        ry = y0 + i*RH; yy[name] = ry
        f.text(X0-12, ry+RH/2+4, name, size=8.5, mono=True, anchor="end")
        if kind == "clk": clk(f, ry, n)
        elif kind == "bit": bit(f, ry, data)
        elif kind == "bite": bit(f, ry, data, RL)
        elif kind == "bitv": bit(f, ry, data, PHY)
        elif kind == "bus": bus(f, ry, data)
        elif kind == "busv": bus(f, ry, data, fill=FILL_NEW)
        elif kind == "busm": bus(f, ry, data, fill=FILL_CELL)
    # tphy_rdlat arrow cmd(0) -> en
    darrow(f, 0, rdlat_to, yy["rd_cmd"]+RH+9, "tphy_rdlat=%d" % rdlat_to, RL)
    if disabled:
        dy = y0 + len(rows)*RH + 12
        f.rect(X0, dy, n*CW, 46, fill=PAPER, stroke=INK, width=1.1)
        f.text(X0+10, dy+18, "disabled this gear (no toggle):", size=8.5, bold=True)
        f.text(X0+10, dy+36, disabled, size=8.5, mono=True, fill=MUTED)
    f.save(fname); print("wrote", fname)


N = None
# ---- 1:1 ----
panel("Read burst 1:1 (gear=00)",
      "p0 only; rd_cmd +tphy_rdlat=5 -> rddata_en (MC window); PHY drives rddata_valid+rddata; accum -> 512b write",
      16, [
      ("clk", "dfi_clk", None),
      ("bus", "rd_cmd", ["RD","COL"]+[N]*14),
      ("bite", "rddata_en_p0 [MC>PHY]", [0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0]),
      ("bitv", "rddata_valid_p0 [PHY>MC]", [0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0]),
      ("busv", "rddata_p0", [N]*5+["B0-7","B8-15","B16-23","B24-31","B32-39","B40-47","B48-55","B56-63"]+[N]*3),
      ("busm", "rd_sram_wr", [N]*13+["512b @dbuf"]+[N]*2),
      ("bus", "rd_done", [N]*13+["done"]+[N]*2),
      ], "rddata_en/valid/rddata _p1/p2/p3", 5, "fig_89a_rd_1to1.svg")

# ---- 1:2 ----
panel("Read burst 1:2 (gear=01)",
      "p0,p1; window 4 mc_clk; PHY returns 2 phases/cyc",
      10, [
      ("clk", "dfi_clk", None),
      ("bus", "rd_cmd", ["RD"]+[N]*9),
      ("bite", "rddata_en_p0 [MC>PHY]", [0,0,0,0,0,1,1,1,1,0]),
      ("bite", "rddata_en_p1 [MC>PHY]", [0,0,0,0,0,1,1,1,1,0]),
      ("bitv", "rddata_valid_p0 [PHY>MC]", [0,0,0,0,0,1,1,1,1,0]),
      ("bitv", "rddata_valid_p1 [PHY>MC]", [0,0,0,0,0,1,1,1,1,0]),
      ("busv", "rddata_p0", [N]*5+["B0-7","B16-23","B32-39","B48-55"]+[N]),
      ("busv", "rddata_p1", [N]*5+["B8-15","B24-31","B40-47","B56-63"]+[N]),
      ("busm", "rd_sram_wr", [N]*9+["512b"]),
      ("bus", "rd_done", [N]*9+["done"]),
      ], "rddata _p2/p3", 5, "fig_89b_rd_1to2.svg")

# ---- 1:4 ----
panel("Read burst 1:4 (gear=11)",
      "p0..p3; window 2 mc_clk; PHY returns 4 phases/cyc (all active)",
      9, [
      ("clk", "dfi_clk", None),
      ("bus", "rd_cmd", ["RD"]+[N]*8),
      ("bite", "rddata_en_p0..p3 [MC>PHY]", [0,0,0,0,0,1,1,0,0]),
      ("bitv", "rddata_valid_p0..p3 [PHY>MC]", [0,0,0,0,0,1,1,0,0]),
      ("busv", "rddata_p0", [N]*5+["B0-7","B32-39"]+[N]*2),
      ("busv", "rddata_p1", [N]*5+["B8-15","B40-47"]+[N]*2),
      ("busv", "rddata_p2", [N]*5+["B16-23","B48-55"]+[N]*2),
      ("busv", "rddata_p3", [N]*5+["B24-31","B56-63"]+[N]*2),
      ("busm", "rd_sram_wr", [N]*7+["512b"]+[N]),
      ("bus", "rd_done", [N]*7+["done"]+[N]),
      ], None, 5, "fig_89c_rd_1to4.svg")
