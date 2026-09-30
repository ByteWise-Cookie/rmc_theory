from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_CELL, FILL_ACTIVE, FILL_NEW, FILL_LOGIC

# fig_90 - read valid contiguity. cycle_valid = AND of active-phase valids
# (inactive lanes masked to 1). run_valid <= run_valid & cycle_valid (reset 1
# at burst_start). Any bubble (a cycle with a phase valid low) drops run_valid
# -> read_done blocked. read_done = run_valid & (cnt==0).

DAT = "#2a8f86"; CTL = "#7a4fb0"
f = Fig(1180, 560)


def andgate(cx, cy, w, h, label, sub=""):
    # D-shaped AND
    f.path(f"M{cx-w/2} {cy-h/2} L{cx} {cy-h/2} "
           f"A{h/2} {h/2} 0 0 1 {cx} {cy+h/2} L{cx-w/2} {cy+h/2} Z", stroke=INK)
    f.text(cx-6, cy+4, label, size=13, anchor="middle", bold=True)
    if sub:
        f.text(cx+w/2+8, cy+4, sub, size=9, mono=True, fill=DAT)


def port(x, y, name, fill=PAPER):
    f.rect(x, y-13, 150, 26, fill=fill, width=1.3, rx=4)
    f.text(x+8, y+4, name, size=9, mono=True)


f.text(40, 30, "Read valid contiguity  (no-bubble guarantee)", size=15, mono=False, bold=True)

# ---- phase valid inputs ----
vy = [110, 146, 182, 218]
for i, y in enumerate(vy):
    f.text(46, y+4, f"dfi_rddata_valid_p{i}", size=9, mono=True, fill=DAT)
    f.line(210, y, 250, y, arrow=True, stroke=DAT)

# ---- mask by gear ----
f.block(250, 96, 150, 140, "MASK by gear", "inactive lane -> 1")
f.text(300, 78, "gear", size=9, mono=True, fill=CTL)
f.line(325, 82, 325, 96, arrow=True, stroke=CTL)
for y in vy:
    f.line(400, y, 470, y, arrow=True, stroke=DAT)
f.text(410, 250, "masked_valid[3:0]", size=8, mono=True, fill=MUTED)

# ---- AND reduce -> cycle_valid ----
andgate(510, 165, 66, 150, "&")
f.line(548, 165, 635, 165, arrow=True, stroke=DAT)
f.text(556, 158, "cycle_valid", size=8, mono=True, fill=DAT)

# ---- run AND + run_valid FF ----
andgate(675, 175, 60, 80, "&")
f.line(705, 175, 770, 175, arrow=True, stroke=INK)          # -> run_valid FF D
f.block(770, 150, 150, 52, "run_valid FF", "load=1 @burst_start")
f.text(700, 130, "burst_start", size=8, mono=True, fill=CTL)
f.line(760, 134, 800, 150, arrow=True, stroke=CTL)          # burst_start -> FF (load 1)
# feedback bus: Q -> down -> split to runAND + DONE
f.path("M920 176 L965 176 L965 300 L635 300", arrow=False, dashed=True, stroke=CTL)
f.line(635, 300, 655, 205, arrow=True, dashed=True, stroke=CTL)   # -> runAND lower input
f.text(700, 296, "run_valid (feedback)", size=8, mono=True, fill=CTL)

# ---- done AND ----
andgate(675, 400, 60, 80, "&")
f.line(635, 300, 635, 380, arrow=True, stroke=CTL)          # run_valid -> DONE top input
f.text(560, 372, "run_valid", size=8, mono=True, fill=CTL)
f.text(560, 430, "cnt==0", size=9, mono=True, fill=CTL)
f.line(600, 428, 648, 418, arrow=True, stroke=CTL)          # cnt==0 -> DONE lower input
f.line(705, 400, 900, 400, arrow=True, stroke=INK)
f.text(712, 393, "read_done", size=8, mono=True, fill=DAT)
port(900, 400, "read_done", FILL_ACTIVE)

# ---- notes ----
f.rect(40, 470, 1100, 74, fill=PAPER, width=1.3, stroke=INK)
f.text(56, 492, "cycle_valid = AND of ACTIVE-phase valids (gear masks inactive lanes to 1): "
       "1:1=vp0 ; 1:2=vp0&vp1 ; 1:4=vp0&..&vp3.", size=9, mono=True, fill=DAT)
f.text(56, 512, "run_valid <= run_valid & cycle_valid ; reset to 1 at burst_start. A bubble (any "
       "active-cycle valid low) drops run_valid.", size=9, mono=True, fill=CTL)
f.text(56, 532, "read_done = run_valid & (cnt==0). Bubble -> run_valid=0 -> read_done blocked "
       "(flag as read error). Contiguous -> done.", size=9, mono=True, fill=INK)

f.save("fig_90_rd_valid_contig.svg")
print("wrote fig_90_rd_valid_contig.svg")
