from rtlfig import Fig, MUTED, INK

# fig_sweep - CIF-view address-map sweep. 2 channels. One generator, 4 contact
# sheets (one per address-map policy). Each sheet sweeps burst 128B -> 4KB
# (P = 2,4,8,16,32,64 pkt of 64B). Each cell = 1 pkt; the number = the physical
# bank it lands in ({ch·bg·bank}, 0..63); the FILL = same-bank queue depth (how
# many earlier pkt in THIS burst already hit that same bank). green = first touch
# (= its ACT), reddening = piling behind an open bank. The tally on the right
# carries the ORDER metrics (banks touched, ch balance, back-to-back diff-BG).

# depth heat ramp (0 = cool first-touch/ACT .. 7+ = hot pileup), clamp at 7
RAMP = ["#cfe8c0", "#eaf0a0", "#ffe07a", "#ffc154",
        "#ff9a3c", "#f5722a", "#de4a1e", "#bd2414"]
def heat(d):
    i = min(d, 7)
    return RAMP[i], ("#ffffff" if i >= 5 else INK)

NCH, NBG, NBK = 2, 8, 4
NPHYS = NCH * NBG * NBK   # 64

# each map: (title, low->high field-order string, extract(n)->(ch,bg,bank), caption)
def m_col(n):   return (0, 0, 0)                      # col fills low 6 bits
def m_bank(n):  return ((n >> 5) & 1, (n >> 2) & 7, n & 3)
def m_bg(n):    return ((n >> 5) & 1, n & 7, (n >> 3) & 3)
def m_ch(n):    return (n & 1, (n >> 1) & 7, (n >> 4) & 3)
# PAIR: col_lsb at the very bottom -> pkt n,n+1 = SAME bank, 2 columns (row hit)
# before anything rotates. ch next, then bg, then bank. 2 CAS per ACT.
def m_pair(n):  return ((n >> 1) & 1, (n >> 2) & 7, (n >> 5) & 3)

MAPS = [
 ("fig_17_sweep_colfirst", "COL-first  (linear / BAD)",
  "byte6 | col(6) | bank2 | bg3 | ch1 | rank | row", m_col, False,
  "col in the low bits -> all 64 pkt hit ONE bank, same row: 1 ACT then 63 "
  "same-bank CAS SERIAL at tCCD_L=12 (RD) -> zero bank parallelism. Worst map."),
 ("fig_18_sweep_bankfirst", "BANK-first",
  "byte6 | bank2 | bg3 | ch1 | rank | col | row", m_bank, False,
  "bank low -> rotates 4 banks fast but HOLDS the same BG for 4 pkt -> "
  "back-to-back same-BG CAS at tCCD_L, weaker DQ pack than BG-first."),
 ("fig_19_sweep_bgfirst", "BG-first  (DQ-pack / my rec)",
  "byte6 | bg3 | bank2 | ch1 | rank | col | row", m_bg, False,
  "bg low -> every adjacent CAS is diff-BG -> packs at tCCD_S=8 = the DQ "
  "heartbeat. Best page-hit + DQ map."),
 ("fig_20_sweep_chfirst", "CH-first  (BW-max)",
  "byte6 | ch1 | bg3 | bank2 | rank | col | row", m_ch, False,
  "ch low -> alternates channel EVERY pkt -> both MC channels busy from pkt1 "
  "(cross-channel BW-max); bg rotates every 2 pkt."),
 ("fig_21_sweep_pair", "PAIR  (2-per-bank, row-hit reuse)",
  "byte6 | col_lsb1 | ch1 | bg3 | bank2 | rank | col_hi | row", m_pair, True,
  "col_lsb at the BOTTOM -> pkt n,n+1 hit the SAME bank/row (2 columns) before "
  "rotating: 1 ACT amortised over 2 CAS, 2nd = guaranteed HIT. ACT count HALVES "
  "(32 vs 64 @4KB) -> half the tFAW pressure. Cost: pair's 2nd CAS is same-BG "
  "-> tCCD_L=12 gap (and tCCD_L_WR=48 for writes -> DO NOT pair writes)."),
]

SIZES = [("128B", 2), ("256B", 4), ("512B", 8),
         ("1KB", 16), ("2KB", 32), ("4KB", 64)]

CW, CH = 27, 32
X0, Y0, PITCH = 172, 196, 46
TALLYX = X0 + 64 * CW + 18   # 1908

for fname, title, order, extract, pairmode, cap in MAPS:
    f = Fig(2320, 536)
    f.note(2310, 30, f"CIF address-map sweep  -  {title}", anchor="end")
    f.note(2310, 46, "2 channels  -  heat = same-bank queue depth", anchor="end")

    f.text(40, 74, "MAP (low->high above byte6):", size=12, mono=False, bold=True)
    f.text(300, 74, order, size=12, fill=INK)

    # ---- self-explaining legend strip ----
    f.text(40, 108, "EACH CELL", size=12, mono=False, bold=True)
    f.text(40, 126, "= 1 pkt (64B) = 1 CAS.  number = physical bank it lands in "
           "(0..63, <32=ch0  >=32=ch1).  left->right = program order (time).",
           size=11, mono=False, fill=INK)

    f.text(40, 150, "FILL = HEAT", size=12, mono=False, bold=True)
    lx = 150
    for d in range(8):
        f.rect(lx + d * 22, 140, 22, 14, fill=RAMP[d], stroke=INK, width=1.0)
    f.text(lx, 168, "0", size=10, mono=False, anchor="middle", fill=MUTED)
    f.text(lx + 8 * 22, 168, "7+", size=10, mono=False, anchor="middle", fill=MUTED)
    f.text(lx + 8 * 22 + 20, 150, "= how many earlier pkt already hit that SAME "
           "bank.  green = first touch (needs 1 ACT, then streams)  ...  "
           "red = piled behind an open bank (serial).", size=11, mono=False,
           fill=INK)

    f.text(40, 184, "READ IT:", size=12, mono=False, bold=True)
    if pairmode:
        f.rect(150, 173, 22, 14, fill="#7fc8bd", stroke=INK, width=1.0)
        f.text(178, 184, "= the planned 2nd-col ROW-HIT (GOOD, not a stall).   "
               "green = ACT, teal = its paired hit.   any RED here = unintended "
               "3rd+ pileup.", size=11, mono=False, fill=INK)
    else:
        f.text(150, 184, "whole row GREEN = burst spread over many banks = parallel "
               "= GOOD.    row REDDENS = crammed into few banks = serial = BAD.",
               size=11, mono=False, fill=INK)

    for i, (lbl, P) in enumerate(SIZES):
        y = Y0 + i * PITCH
        f.text(158, y + 20, lbl, size=13, anchor="end", bold=True)
        f.text(158, y + 34, f"{P} pkt", size=10, mono=False, anchor="end",
               fill=MUTED)
        seen = {}
        banks, chs = set(), set()
        last_bg, diffbg, pairs = {}, 0, 0   # per-channel diff-BG (DQ-pack metric)
        for n in range(P):
            ch, bg, bank = extract(n)
            phys = ch * 32 + bg * 4 + bank
            d = seen.get(phys, 0)
            seen[phys] = d + 1
            banks.add(phys); chs.add(ch)
            if ch in last_bg:
                pairs += 1
                if bg != last_bg[ch]:
                    diffbg += 1
            last_bg[ch] = bg
            if pairmode and d == 1:
                fill, tx = "#7fc8bd", INK      # planned 2nd-col row-hit = GOOD
            else:
                fill, tx = heat(d)
            x = X0 + n * CW
            f.rect(x, y, CW, CH, fill=fill, stroke=INK, width=1.1)
            f.text(x + CW / 2, y + CH / 2 + 4, str(phys), size=10,
                   anchor="middle", fill=tx, bold=(d == 0))
        B = len(banks); D = max(seen.values())
        f.text(TALLYX, y + 14, f"banks {B}/{NPHYS}   ch {len(chs)}   "
               f"max-depth {D}   ACT {B}", size=11, mono=False)
        f.text(TALLYX, y + 30, f"per-ch diff-BG {diffbg}/{pairs}   "
               f"(=DQ pack at tCCD_S; tFAW caps ACT 4/win/ch)", size=10,
               mono=False, fill=MUTED)

    f.caption(40, 516, cap)
    f.save(fname + ".svg")
    print("wrote", fname + ".svg")
