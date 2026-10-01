from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_CELL, FILL_ACTIVE, FILL_NEW, FILL_LOGIC

# fig_94 - lookahead final. Fixed-head demote: new entry -> e0; stalled head
# demoted e0->e1 (older piles to higher index). ready[i]=ei_vld & bank_rdy[ei_bank].
# Binary highest-index priority encoder -> sel[1:0] + pop. One fixed 4:1 mux pops
# slot[sel] (oldest-ready wins over fresh e0). Compact on pop.

DATA = "#2a8f86"; CTL = "#7a4fb0"
f = Fig(1340, 600)


def andg(cx, cy, w, h, lab=""):
    f.path(f"M{cx-w/2} {cy-h/2} L{cx} {cy-h/2} A{h/2} {h/2} 0 0 1 {cx} {cy+h/2} "
           f"L{cx-w/2} {cy+h/2} Z", stroke=INK)
    if lab: f.text(cx-4, cy+3, lab, size=8, anchor="middle", bold=True)


def muxr(cx, cy, w, h, name):
    f.path(f"M{cx} {cy-h/2} L{cx+w} {cy-h/4} L{cx+w} {cy+h/4} L{cx} {cy+h/2} Z", stroke=INK)
    f.text(cx+w/2-2, cy+4, name, size=8, anchor="middle", bold=True)


f.text(40, 30, "LOOKAHEAD (final) - fixed 4:1 mux + binary highest-idx p-enc + demote",
       size=15, mono=False, bold=True)

# ---- new entry -> e0 ----
f.text(560, 95, "new entry -> e0 (on pop / demote)", size=9, mono=True, fill=DATA)
f.line(820, 100, 820, 158, arrow=True, stroke=DATA)

# ---- slots : e3 e2 e1 e0 (higher idx = older) ----
sx = [380, 520, 660, 800]
names = ["e3 (oldest)", "e2", "e1", "e0 (head)"]
for x, nm in zip(sx, names):
    f.rect(x-62, 160, 124, 46, fill=FILL_CELL, width=1.4, rx=5)
    f.text(x, 187, nm, size=9, anchor="middle", bold=True)
# demote e0->e1 (stall)
f.path("M742 183 L720 140 L545 140 L525 160", arrow=True, dashed=True, stroke=CTL)
f.text(600, 134, "demote e0->e1 on stall (older piles up)", size=8, mono=True, fill=CTL)

# ---- bank_rdy_vec ----
f.block(120, 290, 170, 44, "bank_rdy_vec", "")
f.line(290, 312, 340, 312, arrow=True, stroke=CTL)
f.text(150, 356, "bank_rdy_vec[ei_bank]", size=7.5, mono=True, fill=CTL)

# ---- ready ANDs ----
for i, x in enumerate(sx):
    ridx = 3 - i  # leftmost = e3 = ready[3]
    f.line(x, 206, x, 290, arrow=True, stroke=DATA)      # slot vld down
    andg(x, 312, 42, 42, "&")
    f.text(x+28, 304, f"ready[{ridx}]", size=7.5, mono=True, fill=DATA)
    f.line(x, 333, x, 382, arrow=True, stroke=DATA)      # -> p_enc

# ---- binary priority encoder ----
f.block(340, 382, 520, 52, "P_ENCODER (highest idx)", "")
f.text(350, 452, "sel[1]=r3|r2 ;  sel[0]=r3|(r1&~r2) ;  pop=|ready", size=9, mono=True, fill=CTL)

# sel/pop -> mux
f.path("M860 408 L1000 408 L1000 235", arrow=True, stroke=CTL)
f.text(905, 403, "sel[1:0], pop", size=7.5, mono=True, fill=CTL)

# ---- fixed 4:1 mux ----
muxr(960, 183, 80, 120, "4:1 MUX\nslot[sel]")
f.path("M862 183 L930 183", arrow=True, stroke=DATA)     # slots bus -> mux
f.text(885, 176, "e0..e3", size=7, mono=True, fill=MUTED)
f.line(1040, 183, 1120, 183, arrow=True, stroke=DATA)
f.rect(1120, 169, 160, 28, fill=FILL_ACTIVE, width=1.3, rx=4)
f.text(1128, 187, "issued -> BANK_DEC", size=7.5, mono=True)

f.caption(40, 500,
          "ready[i]=ei_vld & bank_rdy_vec[ei_bank]. Binary p-enc picks HIGHEST set idx (oldest; demote "
          "pushes stalled heads up) -> sel[1:0]; pop=|ready. One fixed 4:1 mux pops slot[sel] -> freed "
          "stalled ei beats fresh e0. On pop: compact (newer shift up, e0<-new). On e0-stall: demote "
          "e0->e1, e0<-new. Order free (same-bank share bank_rdy + highest-idx); age-cap vs starve.")

f.save("fig_94_lookahead_final.svg")
print("wrote fig_94_lookahead_final.svg")
