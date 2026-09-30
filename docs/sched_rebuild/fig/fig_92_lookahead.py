from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_CELL, FILL_ACTIVE, FILL_NEW, FILL_LOGIC

# fig_92 - lookahead: compacting queue + parallel probe + prio_enc + bypass mux.
# New entry loads lowest-free slot; all slots probed vs bank_rdy in parallel;
# prio_enc picks lowest eligible; bypass mux forwards input->out when window
# empty (0-cyc). Depth 4 = reorder window, NOT pipeline latency.

DATA = "#2a8f86"; CTL = "#7a4fb0"
f = Fig(1400, 540)


def mux(cx, cy, w, h, name):
    f.path(f"M{cx} {cy-h/2} L{cx+w} {cy-h/4} L{cx+w} {cy+h/4} L{cx} {cy+h/2} Z", stroke=INK)
    f.text(cx+w/2-2, cy+4, name, size=8, anchor="middle", bold=True)


def port(x, y, name, fill=PAPER):
    f.rect(x, y-14, 150, 28, fill=fill, width=1.3, rx=4)
    f.text(x+8, y+4, name, size=8.5, mono=True)


f.text(40, 30, "LOOKAHEAD  -  compacting queue + parallel prio_enc + bypass mux", size=15,
       mono=False, bold=True)

# ---- input ----
f.text(40, 300, "in {rob_index, phy_adr, op} + vld", size=8.5, mono=True, fill=DATA)
f.line(300, 305, 340, 305, arrow=True, stroke=DATA)

# ---- load ----
f.block(150, 270, 150, 70, "LOAD", "lowest-free slot")
f.line(300, 300, 340, 130, arrow=True, stroke=DATA)   # load into slots

# ---- slots (compacting queue) ----
sy = [110, 168, 226, 284]
lbl = ["e0 (head/oldest)", "e1", "e2", "e3 (newest)"]
for y, t in zip(sy, lbl):
    f.rect(340, y-22, 150, 44, fill=FILL_CELL, width=1.4, rx=5)
    f.text(415, y+3, t, size=8.5, mono=True, anchor="middle")
    f.line(490, y, 560, y, arrow=True, stroke=DATA)   # slot -> probe

# ---- bank_rdy ----
f.text(430, 60, "bank_rdy[N_BANKS]", size=8.5, mono=True, fill=CTL)
f.line(560, 64, 620, 90, arrow=True, stroke=CTL)

# ---- probe + elig ----
f.block(560, 90, 130, 220, "PROBE", "elig[3:0]")
# ---- bank_cmp ----
f.line(690, 200, 720, 200, arrow=True, stroke=DATA)
f.block(720, 90, 130, 220, "BANK_CMP", "masked_elig")
# ---- prio_enc ----
f.line(850, 200, 890, 200, arrow=True, stroke=DATA)
f.block(890, 150, 120, 100, "PRIO_ENC", "lowest elig -> sel_oh")

# ---- head mux (select slot entry) ----
mux(1060, 200, 70, 150, "HEAD\nMUX")
# slots bus into head mux
f.path("M490 130 L520 130 L520 200 L1060 200", arrow=True, stroke=DATA)
f.text(700, 344, "slot entries (bus) -> HEAD_MUX", size=8, mono=True, fill=MUTED)
# sel from prio_enc
f.path("M950 250 L950 300 L1085 300 L1085 240", arrow=True, stroke=CTL)
f.text(958, 296, "sel_oh", size=8, mono=True, fill=CTL)
# compact feedback
f.path("M910 250 L910 420 L415 420 L415 306", arrow=True, dashed=True, stroke=CTL)
f.text(560, 434, "compact / shift on select", size=8, mono=True, fill=CTL)

# ---- bypass mux ----
mux(1180, 300, 70, 130, "BYPASS")
f.line(1130, 200, 1160, 270, arrow=True, stroke=DATA)          # head_entry -> bypass in0
f.text(1120, 250, "head", size=7.5, mono=True, fill=DATA)
f.path("M300 305 L330 460 L1150 460 L1160 330", arrow=True, stroke=DATA)  # input bypass path
f.text(700, 474, "input bypass (window empty -> 0-cyc)", size=8, mono=True, fill=DATA)
f.text(1120, 380, "window_empty", size=7.5, mono=True, fill=CTL)
f.line(1180, 380, 1200, 335, arrow=True, stroke=CTL)          # sel = window_empty

# ---- out ----
f.line(1250, 300, 1290, 300, arrow=True, stroke=DATA)
port(1250, 300, "", FILL_ACTIVE)
f.text(1258, 304, "-> BANK_DEC", size=8, mono=True)

f.caption(40, 512,
          "Depth 4 = reorder window, NOT latency. New entry -> lowest-free slot; all slots probed vs "
          "bank_rdy in parallel; bank_cmp holds per-bank order; prio_enc picks lowest eligible. BYPASS "
          "forwards input->out when window empty (0-cyc); else 1-cyc.")

f.save("fig_92_lookahead.svg")
print("wrote fig_92_lookahead.svg")
