from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_ACTIVE, FILL_NEW

# fig_86 - wr_en vs wrdata timing. per write: cmd +tphy_wrlat -> en, +tphy_wrdata
# -> data. WR0@0, WR1@13 (gap). shows the two delay hops as marked arrows, and
# that en leads data by wrdata, both gapping with the command spacing.

CW = 62; RH = 50; X0 = 150
LAT = "#7a4fb0"; DAT = "#2a8f86"
wrlat = 4; wrdata = 2   # WL = 6


def xc(c):
    return X0 + c * CW


def clk(f, y, n):
    top = y + 9; bot = y + RH - 9; x = X0
    for _ in range(n):
        f.line(x, top, x+CW/2, top, stroke=INK); f.line(x+CW/2, top, x+CW/2, bot, stroke=INK)
        f.line(x+CW/2, bot, x+CW, bot, stroke=INK); f.line(x+CW, bot, x+CW, top, stroke=INK)
        x += CW


def bit(f, y, levels):
    top = y+9; bot = y+RH-9; x = X0; prev = levels[0]
    for c, lv in enumerate(levels):
        yl = top if lv else bot
        if c > 0 and lv != prev:
            f.line(x, top if prev else bot, x, yl, stroke=INK)
        f.line(x, yl, x+CW, yl, stroke=INK, width=1.7 if lv else 1.0); prev = lv; x += CW


def bus(f, y, cells, fill=FILL_ACTIVE):
    top = y+11; bot = y+RH-11; mid = y+RH/2; x = X0
    for cell in cells:
        if cell is None:
            f.line(x, mid, x+CW, mid, stroke=FAINT)
        else:
            f.rect(x+1.5, top, CW-3, bot-top, fill=fill, stroke=INK, width=1.1, rx=2)
            f.text(x+CW/2, mid+3, cell, size=7.5, mono=True, anchor="middle")
        x += CW


def darrow(f, c1, c2, y, label, col):
    x1 = xc(c1); x2 = xc(c2)
    f.line(x1, y, x2, y, arrow=True, stroke=col)
    f.line(x2, y, x1, y, arrow=True, stroke=col)
    f.text((x1+x2)/2, y-6, label, size=8, mono=True, anchor="middle", fill=col)


N = None
n = 28
f = Fig(X0 + n*CW + 24, 430)
f.text(20, 28, "wr_en / wrdata timing  -  cmd +tphy_wrlat -> en , +tphy_wrdata -> data",
       size=14, bold=True, mono=False)
f.text(20, 47, "WR0@0, WR1@13 (gap). wrlat=4, wrdata=2. en leads data by wrdata; both gap with spacing.",
       size=8.5, mono=True, fill=MUTED)

y0 = 78
yclk, ycmd, yen, ydat = y0, y0+RH+22, y0+2*RH+22, y0+3*RH+22

# grid
for c in range(n+1):
    f.line(xc(c), y0-6, xc(c), ydat+RH, stroke=FAINT)
for c in range(0, n, 2):
    f.text(xc(c)+CW/2, y0-10, str(c), size=6.5, mono=True, fill=MUTED, anchor="middle")

# rows
f.text(X0-10, yclk+RH/2+4, "dfi_clk", size=9, mono=True, anchor="end"); clk(f, yclk, n)
f.text(X0-10, ycmd+RH/2+4, "wr_cmd", size=9, mono=True, anchor="end")
bus(f, ycmd, ["WR0"]+[N]*12+["WR1"]+[N]*14, fill=FILL_NEW)
f.text(X0-10, yen+RH/2+4, "wr_en_p0", size=9, mono=True, anchor="end")
bit(f, yen, [0]*4+[1]*8+[0]*5+[1]*8+[0]*3)
f.text(X0-10, ydat+RH/2+4, "wrdata_p0", size=9, mono=True, anchor="end")
bus(f, ydat, [N]*6+["W0"]*8+[N]*5+["W1"]*8+[N])

# vertical guides at cmd/en/data edges
for c, col in [(0, LAT), (4, LAT), (6, DAT), (13, LAT), (17, LAT), (19, DAT)]:
    f.line(xc(c), ycmd-6, xc(c), ydat+RH, dashed=True, stroke=col)

# point labels
for c, t in [(0, "cmd"), (4, "en^"), (6, "data"), (13, "cmd"), (17, "en^"), (19, "data")]:
    f.text(xc(c)+3, ycmd-12, t, size=7, mono=True, fill=INK)

# delay arrows: wrlat between cmd and en band, wrdata between en and data band
darrow(f, 0, 4, ycmd+RH+11, "tphy_wrlat=4", LAT)
darrow(f, 4, 6, yen+RH+11, "tphy_wrdata=2", DAT)
darrow(f, 13, 17, ycmd+RH+11, "tphy_wrlat", LAT)
darrow(f, 17, 19, yen+RH+11, "tphy_wrdata", DAT)

f.text(20, ydat+RH+26,
       "each write re-adds wrlat+wrdata from ITS OWN cmd (parallel pipes). en window and data "
       "window are both 8 CK; data = en delayed by wrdata. gap on cmd -> gap on en -> gap on data.",
       size=8.5, mono=True, fill=INK)

f.save("fig_86_wr_en_delay.svg")
print("wrote fig_86_wr_en_delay.svg")
