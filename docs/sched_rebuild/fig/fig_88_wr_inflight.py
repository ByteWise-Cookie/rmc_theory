from rtlfig import Fig, INK, MUTED, FAINT, FILL_ACTIVE, FILL_NEW, FILL_CELL

# fig_88 - why wr_launch needs a DELAY LINE, not one counter. wrlat(14) > spacing(8)
# -> WR0/WR1/WR2 latency pipes OVERLAP -> multiple writes in flight -> a single
# restartable counter fails; a shift-reg delay line (depth=WL) holds all of them.

CW = 40; RH = 36; X0 = 160
LAT = "#7a4fb0"; DAT = "#2a8f86"
wrlat = 14; wrdata = 2


def xc(c): return X0 + c * CW


def clk(f, y, n):
    top = y+8; bot = y+RH-8; x = X0
    for _ in range(n):
        f.line(x, top, x+CW/2, top, stroke=INK); f.line(x+CW/2, top, x+CW/2, bot, stroke=INK)
        f.line(x+CW/2, bot, x+CW, bot, stroke=INK); f.line(x+CW, bot, x+CW, top, stroke=INK); x += CW


def bit(f, y, lv):
    top = y+8; bot = y+RH-8; x = X0; prev = lv[0]
    for c, v in enumerate(lv):
        yl = top if v else bot
        if c > 0 and v != prev: f.line(x, top if prev else bot, x, yl, stroke=INK)
        f.line(x, yl, x+CW, yl, stroke=INK, width=1.7 if v else 1.0); prev = v; x += CW


def bus(f, y, cells, fill=FILL_ACTIVE):
    top = y+9; bot = y+RH-9; mid = y+RH/2; x = X0
    for cell in cells:
        if cell is None: f.line(x, mid, x+CW, mid, stroke=FAINT)
        else:
            f.rect(x+1, top, CW-2, bot-top, fill=fill, stroke=INK, width=1.0, rx=2)
            f.text(x+CW/2, mid+3, cell, size=6.5, mono=True, anchor="middle")
        x += CW


def darrow(f, c1, c2, y, label, col):
    x1 = xc(c1); x2 = xc(c2)
    f.line(x1, y, x2, y, arrow=True, stroke=col); f.line(x2, y, x1, y, arrow=True, stroke=col)
    f.text((x1+x2)/2, y-5, label, size=7, mono=True, anchor="middle", fill=col)


N = None
n = 44
f = Fig(X0 + n*CW + 24, 470)
f.text(20, 26, "wr_launch needs a DELAY LINE (not one counter)  -  wrlat(14) > spacing(8)",
       size=14, bold=True, mono=False)
f.text(20, 44, "WR0/1/2 @ 0/8/16; each launch injects a shift-reg entry; taps fire en@wrlat, "
       "wd_read_ptr@data. Pipes OVERLAP -> multiple in flight.", size=8, mono=True, fill=MUTED)

y0 = 70
ycmd = y0+RH; ylau = ycmd+RH; yband = ylau+RH; yen = yband+64; ydat = yen+RH+22; yrd = ydat+RH
for c in range(n+1): f.line(xc(c), y0-6, xc(c), yrd+RH, stroke=FAINT)
for c in range(0, n, 2): f.text(xc(c)+CW/2, y0-10, str(c), size=6, mono=True, fill=MUTED, anchor="middle")

f.text(X0-10, y0+RH/2+4, "dfi_clk", size=8.5, mono=True, anchor="end"); clk(f, y0, n)
f.text(X0-10, ycmd+RH/2+4, "wr_cmd", size=8.5, mono=True, anchor="end")
bus(f, ycmd, ["WR0"]+[N]*7+["WR1"]+[N]*7+["WR2"]+[N]*27, FILL_NEW)
f.text(X0-10, ylau+RH/2+4, "wr_launch", size=8.5, mono=True, anchor="end")
bit(f, ylau, [1 if c in (0, 8, 16) else 0 for c in range(n)])

# stacked wrlat arrows (the delay-line transit) - they OVERLAP
starts = [0, 8, 16]
for i, s in enumerate(starts):
    darrow(f, s, s+wrlat, yband+12+i*16, "wrlat (WR%d in flight)" % i, LAT)
f.text(X0-10, yband+30, "delay_line", size=8.5, mono=True, anchor="end")
# overlap shading region cyc 8..14 and 16..22
for a, b in [(8, 14), (16, 22)]:
    f.rect(xc(a), yband+6, xc(b)-xc(a), 46, fill=FILL_CELL, stroke="none", width=0)
f.text(xc(11), yband+62, "2 in flight", size=7, mono=True, anchor="middle", fill=INK)
f.text(xc(19), yband+62, "2 in flight", size=7, mono=True, anchor="middle", fill=INK)

f.text(X0-10, yen+RH/2+4, "wr_en_p0", size=8.5, mono=True, anchor="end")
bit(f, yen, [0]*14 + [1]*24 + [0]*6)     # en 14..37
darrow(f, 14, 16, yen+RH+9, "wrdata=2", DAT)
f.text(X0-10, ydat+RH/2+4, "wrdata_p0", size=8.5, mono=True, anchor="end")
bus(f, ydat, [N]*16 + ["W0"]*8 + ["W1"]*8 + ["W2"]*8 + [N]*4)   # data 16..39
f.text(X0-10, yrd+RH/2+4, "wd_read_ptr", size=8.5, mono=True, anchor="end")
bus(f, yrd, [N]*15 + ["rd0"] + [N]*7 + ["rd1"] + [N]*7 + ["rd2"] + [N]*12, FILL_NEW)  # @15,23,31

f.text(20, yrd+RH+22,
       "wrlat=14 > spacing=8 -> when WR1 launches (cyc8) WR0 is still in the WL pipe -> 2 entries "
       "coexist. one counter cannot; a shift-reg delay line of depth WL holds them all. real DDR5: "
       "WL~40 -> ~5 in flight.", size=8, mono=True, fill=INK)

f.save("fig_88_wr_inflight.svg")
print("wrote fig_88_wr_inflight.svg")
