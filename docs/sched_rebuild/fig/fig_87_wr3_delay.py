from rtlfig import Fig, INK, MUTED, FAINT, FILL_ACTIVE, FILL_NEW

# fig_87 - 3 back-to-back WR (spacing 8) with the PHY delays shown: per write
# cmd +tphy_wrlat -> en, +tphy_wrdata -> data. Case A same-rank, Case B cross-rank.
# en + data both continuous (spacing 8 = burst 8), en leads data by wrdata.

CW = 46; RH = 44; X0 = 150
LAT = "#7a4fb0"; DAT = "#2a8f86"
wrlat = 4; wrdata = 2


def xc(c): return X0 + c * CW


def clk(f, y, n):
    top = y+9; bot = y+RH-9; x = X0
    for _ in range(n):
        f.line(x, top, x+CW/2, top, stroke=INK); f.line(x+CW/2, top, x+CW/2, bot, stroke=INK)
        f.line(x+CW/2, bot, x+CW, bot, stroke=INK); f.line(x+CW, bot, x+CW, top, stroke=INK); x += CW


def bit(f, y, lv):
    top = y+9; bot = y+RH-9; x = X0; prev = lv[0]
    for c, v in enumerate(lv):
        yl = top if v else bot
        if c > 0 and v != prev: f.line(x, top if prev else bot, x, yl, stroke=INK)
        f.line(x, yl, x+CW, yl, stroke=INK, width=1.7 if v else 1.0); prev = v; x += CW


def bus(f, y, cells, fill=FILL_ACTIVE):
    top = y+11; bot = y+RH-11; mid = y+RH/2; x = X0
    for cell in cells:
        if cell is None: f.line(x, mid, x+CW, mid, stroke=FAINT)
        else:
            f.rect(x+1.2, top, CW-2.4, bot-top, fill=fill, stroke=INK, width=1.0, rx=2)
            f.text(x+CW/2, mid+3, cell, size=6.8, mono=True, anchor="middle")
        x += CW


def darrow(f, c1, c2, y, label, col):
    x1 = xc(c1); x2 = xc(c2)
    f.line(x1, y, x2, y, arrow=True, stroke=col); f.line(x2, y, x1, y, arrow=True, stroke=col)
    f.text((x1+x2)/2, y-5, label, size=7.5, mono=True, anchor="middle", fill=col)


def cs(n, lows): return [0 if c in lows else 1 for c in range(n)]


N = None
n = 32
# spacing 8, WR at 0/8/16 ; wrlat=4, wrdata=2
en   = [0]*4 + [1]*24 + [0]*4                       # en continuous 4..27
data = [N]*6 + ["W0"]*8 + ["W1"]*8 + ["W2"]*8 + [N]*2   # data continuous 6..29
cmd  = ["WR0"]+[N]*7+["WR1"]+[N]*7+["WR2"]+[N]*15


def panel(title, sub, cs0, cs1, fname):
    f = Fig(X0 + n*CW + 24, 400)
    f.text(20, 26, title, size=13, bold=True, mono=False)
    f.text(20, 44, sub, size=8, mono=True, fill=MUTED)
    y0 = 70
    ycmd = y0+RH; yen = ycmd+RH+20; ydat = yen+RH+20; ycs0 = ydat+RH; ycs1 = ycs0+RH
    for c in range(n+1): f.line(xc(c), y0-6, xc(c), ycs1+RH, stroke=FAINT)
    for c in range(0, n, 2): f.text(xc(c)+CW/2, y0-10, str(c), size=6, mono=True, fill=MUTED, anchor="middle")
    f.text(X0-10, y0+RH/2+4, "dfi_clk", size=8.5, mono=True, anchor="end"); clk(f, y0, n)
    f.text(X0-10, ycmd+RH/2+4, "wr_cmd", size=8.5, mono=True, anchor="end"); bus(f, ycmd, cmd, FILL_NEW)
    f.text(X0-10, yen+RH/2+4, "wr_en_p0", size=8.5, mono=True, anchor="end"); bit(f, yen, en)
    f.text(X0-10, ydat+RH/2+4, "wrdata_p0", size=8.5, mono=True, anchor="end"); bus(f, ydat, data)
    f.text(X0-10, ycs0+RH/2+4, "cs_n_r0", size=8.5, mono=True, anchor="end"); bit(f, ycs0, cs0)
    f.text(X0-10, ycs1+RH/2+4, "cs_n_r1", size=8.5, mono=True, anchor="end"); bit(f, ycs1, cs1)
    # per-write guides + delay arrows (all 3)
    for i, s in enumerate([0, 8, 16]):
        enc = s + wrlat; dac = s + wrlat + wrdata
        for c, col in [(s, LAT), (enc, LAT), (dac, DAT)]:
            f.line(xc(c), ycmd-6, xc(c), ydat+RH, dashed=True, stroke=(col if i == 0 else FAINT))
        lab = ("=4" if i == 0 else ""); labd = ("=2" if i == 0 else "")
        darrow(f, s, enc, ycmd+RH+10, "wrlat"+lab, LAT)
        darrow(f, enc, dac, yen+RH+10, "wrdata"+labd, DAT)
        if i == 0:
            for c, t in [(s, "cmd"), (enc, "en^"), (dac, "data")]:
                f.text(xc(c)+3, ycmd-12, t, size=6.5, mono=True, fill=INK)
    # en-window boundary ticks (4|12|20|28) - shows the 8-CK en segments ABUT
    for c in [4, 12, 20, 28]:
        f.line(xc(c), yen-4, xc(c), yen+RH+4, stroke=DAT, width=1.4)
    for c, t in [(8, "WR0 en"), (16, "WR1 en"), (24, "WR2 en")]:
        f.text(xc(c), yen+RH-7, t, size=6.5, mono=True, fill=DAT, anchor="middle")
    f.text(20, ycs1+RH+22,
           "each write anchors its OWN wrlat/wrdata to its cmd. en windows = 8 CK, starts 8 apart "
           "(cyc 4/12/20) -> they ABUT at 12 & 20, never overlap (spacing 8 = burst 8).",
           size=8, mono=True, fill=INK)
    f.save(fname); print("wrote", fname)


panel("3 WR back-to-back  -  SAME rank, diff-BG  (PHY delays shown)",
      "WR0/1/2 @ 0/8/16 rank0; cmd +tphy_wrlat -> en, +tphy_wrdata -> data",
      cs(n, [0, 8, 16]), [1]*n, "fig_87a_wr3_samerank_delay.svg")

panel("3 WR back-to-back  -  CROSS rank (r0,r1,r0)  (PHY delays shown)",
      "WR0(r0)@0, WR1(r1)@8, WR2(r0)@16; SAME tphy all ranks -> identical hops + tiling",
      cs(n, [0, 16]), cs(n, [8]), "fig_87b_wr3_crossrank_delay.svg")
