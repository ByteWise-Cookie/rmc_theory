from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_CELL, FILL_ACTIVE, FILL_NEW

# fig_85 - 3 back-to-back writes, two cases: (A) same rank diff-BG, (B) cross-rank.
# Shows WL = constant parallel shift; dqFree=8 gates command spacing; data tiles
# 8 CK apart either way; tphy_wrlat/wrdata SAME across ranks.

CW = 60; RH = 40; X0 = 150


def draw_clk(f, x0, ry, n):
    top = ry + 8; bot = ry + RH - 8; x = x0
    for _ in range(n):
        f.line(x, top, x + CW / 2, top, stroke=INK)
        f.line(x + CW / 2, top, x + CW / 2, bot, stroke=INK)
        f.line(x + CW / 2, bot, x + CW, bot, stroke=INK)
        f.line(x + CW, bot, x + CW, top, stroke=INK)
        x += CW


def draw_bit(f, x0, ry, levels):
    top = ry + 8; bot = ry + RH - 8; x = x0; prev = levels[0]
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
            f.rect(x + 1.5, top, CW - 3, bot - top, fill=fill, stroke=INK, width=1.0, rx=2)
            f.text(x + CW / 2, mid + 3, cell, size=6.6, mono=True, anchor="middle")
        x += CW


def cs_low_at(n, lows):
    return [0 if c in lows else 1 for c in range(n)]


def panel(title, sub, n, rows, note, fname):
    W = X0 + n * CW + 24
    H = 78 + len(rows) * RH + 40
    f = Fig(W, H)
    f.text(20, 28, title, size=14, bold=True, mono=False)
    f.text(20, 48, sub, size=8.5, mono=True, fill=MUTED)
    y0 = 74
    for c in range(n + 1):
        f.line(X0 + c * CW, y0 - 6, X0 + c * CW, y0 + len(rows) * RH, stroke=FAINT)
    for c in range(n):
        if c % 2 == 0:
            f.text(X0 + c * CW + CW / 2, y0 - 10, str(c), size=6.5, mono=True, fill=MUTED, anchor="middle")
    for i, (kind, name, data) in enumerate(rows):
        ry = y0 + i * RH
        f.text(X0 - 10, ry + RH / 2 + 4, name, size=8.5, mono=True, anchor="end")
        if kind == "clk":
            draw_clk(f, X0, ry, n)
        elif kind == "bit":
            draw_bit(f, X0, ry, data)
        elif kind == "bus":
            draw_bus(f, X0, ry, data)
        elif kind == "busc":
            draw_bus(f, X0, ry, data, fill=FILL_ACTIVE)
    f.text(20, y0 + len(rows) * RH + 26, note, size=8.5, mono=True, fill=INK)
    f.save(fname)
    print("wrote", fname)


N = None
n = 30
# WL = tphy_wrlat(4) + tphy_wrdata(1) = 5 ; burst 8 ; WR at 0,8,16
data = [N]*5 + ["W0"]*8 + ["W1"]*8 + ["W2"]*8 + [N]           # tiles 8 apart, shifted by WL=5
bcnt = [N]*5 + [str(k) for k in range(8,0,-1)]*3 + [N]
en   = [0]*5 + [1]*24 + [0]                                    # contiguous 5..28

# ---- Case 1: same rank, diff-BG ----
panel("Case 1 - 3 continuous WR, SAME rank, diff-BG (8 CK apart)",
      "1:1 gear; WR0/1/2 @ 0/8/16; WL=tphy_wrlat+tphy_wrdata=5 (const shift); each burst=8 beats(64B)",
      n, [
      ("clk", "dfi_clk", None),
      ("bus", "wr_cmd", ["WR0.BG0",N,N,N,N,N,N,N,"WR1.BG1",N,N,N,N,N,N,N,"WR2.BG2"]+[N]*13),
      ("bit", "cs_n_r0", cs_low_at(n, [0,8,16])),
      ("bit", "cs_n_r1", [1]*n),
      ("bit", "wr_en_p0", en),
      ("busc", "wrdata_p0", data),
      ("bus", "burst_cnt", bcnt),
      ],
      "spacing = tCCD_S = dqFree = 8. same-BG would be tCCD_L_WR=48. WL just shifts the whole "
      "stream; WR1/WR2 latency pipelines run DURING WR0's data -> back-to-back, no re-count.",
      "fig_85a_wr_samerank.svg")

# ---- Case 2: cross-rank (r0, r1, r0) ----
panel("Case 2 - 3 WR CROSS-rank (r0, r1, r0), 8 CK apart",
      "1:1 gear; WR0(r0)@0, WR1(r1)@8, WR2(r0)@16; tphy_wrlat/wrdata SAME for all ranks -> same WL=5",
      n, [
      ("clk", "dfi_clk", None),
      ("bus", "wr_cmd", ["WR0.r0",N,N,N,N,N,N,N,"WR1.r1",N,N,N,N,N,N,N,"WR2.r0"]+[N]*13),
      ("bit", "cs_n_r0", cs_low_at(n, [0,16])),
      ("bit", "cs_n_r1", cs_low_at(n, [8])),
      ("bit", "wr_en_p0", en),
      ("busc", "wrdata_p0", data),
      ("bus", "burst_cnt", bcnt),
      ],
      "cmd handoff tRTRS=2 but dqFree=8 still gates -> data 8 apart, no faster (DQ-bound). win = "
      "dodges same-BG tCCD_L_WR=48. CS toggles rank; SAME tphy -> bursts tile identically.",
      "fig_85b_wr_crossrank.svg")
