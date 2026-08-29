from rtlfig import Fig, MUTED, INK, FILL_CELL, FILL_NEW

# fig_16 - address-map heat map. ONE 4KB linear read (64 pkt = 8x8 grid) landing
# in CH0 / RANK0 / 32 banks (8 BG x 4 bank). Map [row|rank|col|bank2|bg3|byte6].
# Top half = first-touch cols -> MISS -> ACT, throttled 4-per-tFAW (8 heat waves,
# yellow=early .. red=late = how long the req WAITS on ACT budget). Bottom half =
# same 32 banks, next col, row still OPEN -> all HIT, zero ACT. tFAW is the gate.

f = Fig(1240, 860)

# heat ramp for the 8 tFAW waves (cool = opens early, hot = waits longest)
WAVE = ["#fff2ac", "#ffdc86", "#ffc164", "#ffa347",
        "#f9812f", "#e85f27", "#d33f1c", "#bd2414"]
WTX  = [INK, INK, INK, INK, INK, "#ffffff", "#ffffff", "#ffffff"]
HIT  = "#d7ecc4"   # row already open -> CAS hit, free

# ---------------- title + top-down breadcrumb ----------------
f.note(1230, 30, "address-map heat map  -  one 4KB read = 64 pkt", anchor="end")
f.note(1230, 46, "map: [ row | rank | col | bank2 | bg3 | byte6 ]", anchor="end")

f.text(40, 42, "TOP-DOWN PICK", size=13, mono=False, bold=True)
def crumb(x, y, name, fields, hot):
    w = 120
    f.rect(x, y, w, 34, fill=FILL_NEW if hot else "none",
           stroke=INK if hot else MUTED, width=1.6 if hot else 1.0)
    f.text(x + w / 2, y + 15, name, size=12, anchor="middle",
           bold=hot, fill=INK if hot else MUTED)
    f.text(x + w / 2, y + 28, fields, size=9, mono=False, anchor="middle",
           fill=MUTED)
    return x + w
x = 40
for nm, fl, hot in [("CH0", "which MC inst", True),
                    ("RANK0", "rank bit", True),
                    ("BANK 0..3", "addr[10:9]", True),
                    ("BG 0..7", "addr[8:6]", True)]:
    xe = crumb(x, 58, nm, fl, hot)
    if nm != "BG 0..7":
        f.line(xe, 75, xe + 18, 75, arrow=True)
    x = xe + 18
f.text(40, 118, "byte[5:0]=0  (64B aligned, full burst)   pkt n = base + n*64B   "
       "n[2:0]=BG  n[4:3]=BANK  n[5]=col-step",
       size=11, mono=False, fill=MUTED)

# ---------------- the 8x8 grid ----------------
GX, GY, CW, CH = 300, 176, 82, 58

# BG column headers
for bg in range(8):
    f.text(GX + bg * CW + CW / 2, GY - 8, f"BG{bg}", size=12, anchor="middle",
           bold=True)

# left col-step brackets + bank row labels
def bracket(y0, y1, label, sub):
    f.line(280, y0, 280, y1)
    f.line(276, y0, 280, y0); f.line(276, y1, 280, y1)
    f.text(272, (y0 + y1) / 2 - 4, label, size=12, anchor="end", bold=True)
    f.text(272, (y0 + y1) / 2 + 12, sub, size=9, mono=False, anchor="end",
           fill=MUTED)
bracket(GY, GY + 4 * CH, "col C", "MISS -> ACT")
bracket(GY + 4 * CH, GY + 8 * CH, "col C+1", "HIT")

for row in range(8):
    bank = row % 4
    colstep = row // 4
    ry = GY + row * CH
    f.text(292, ry + CH / 2 + 4, f"bk{bank}", size=11, anchor="end", fill=MUTED)
    for bg in range(8):
        n = colstep * 32 + bank * 8 + bg
        cx, cy = GX + bg * CW, ry
        if colstep == 0:                       # first touch -> ACT
            wave = (bank * 8 + bg) // 4
            fill, tx = WAVE[wave], WTX[wave]
            f.rect(cx, cy, CW, CH, fill=fill, stroke=INK, width=1.4)
            f.text(cx + CW / 2, cy + 22, f"{n:02d}", size=15, anchor="middle",
                   fill=tx, bold=True)
            f.text(cx + CW / 2, cy + 40, f"ACT w{wave}", size=10, mono=False,
                   anchor="middle", fill=tx)
        else:                                  # row open -> HIT
            f.rect(cx, cy, CW, CH, fill=HIT, stroke=INK, width=1.4)
            f.text(cx + CW / 2, cy + 22, f"{n:02d}", size=15, anchor="middle",
                   bold=True)
            f.text(cx + CW / 2, cy + 40, "HIT", size=10, mono=False,
                   anchor="middle", fill=MUTED)

# ---------------- right rail: tFAW wave timeline ----------------
RX = GX + 8 * CW + 40
f.text(RX, GY - 8, "tFAW gate: 4 ACT / window", size=12, bold=True)
for w in range(8):
    wy = GY + w * 44
    f.rect(RX, wy, 26, 26, fill=WAVE[w], stroke=INK, width=1.2)
    lo, hi = w * 4, w * 4 + 3
    f.text(RX + 36, wy + 12, f"wave{w}: pkt {lo:02d}-{hi:02d}", size=11,
           mono=False)
    f.text(RX + 36, wy + 24, "ACT x4  +tFAW(32CK)", size=9, mono=False,
           fill=MUTED)
    if w < 7:
        f.line(RX + 13, wy + 26, RX + 13, wy + 44, dashed=True, stroke=MUTED)

# ---------------- bottom notes ----------------
ny = GY + 8 * CH + 34
f.text(40, ny, "READ IT:", size=12, bold=True)
f.text(40, ny + 20, "- top 32 pkt each pay ONE ACT, but tFAW caps issue at 4/window "
       "-> 8 waves -> ~8*tFAW ~ 256 CK to open all 32 banks. Req WAITS on ACT budget, not data.",
       size=11, mono=False, fill=INK)
f.text(40, ny + 38, "- bottom 32 pkt = same 32 banks, next col, row STILL OPEN -> "
       "straight CAS hits, zero ACT. Only the first row-open costs ACTs.",
       size=11, mono=False, fill=INK)
f.text(40, ny + 56, "- opened banks stream CAS at tCCD_S=8 (diff-BG pack) and overlap "
       "the next wave's ACTs. Heat = how late a bank gets its ACT slot.",
       size=11, mono=False, fill=INK)

f.caption(40, 840, "One 4KB linear read spreads across CH0/RANK0's 32 banks (8 BG x "
                   "4 bank); first-touch cols MISS/ACT, throttled 4 per tFAW (heat "
                   "waves); next col to the same open rows = all HIT. tFAW is the gate.")

f.save("fig_16_heatmap.svg")
print("wrote fig_16_heatmap.svg")
