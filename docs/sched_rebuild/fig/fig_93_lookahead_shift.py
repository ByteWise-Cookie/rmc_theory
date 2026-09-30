from rtlfig import Fig, INK, MUTED, FAINT, PAPER, FILL_CELL, FILL_ACTIVE, FILL_NEW, FILL_LOGIC

# fig_93 - shift-reg lookahead (corrected). elig[i]=vld_i & bank_rdy_vec[bank_ei];
# p_encoder picks lowest set = served_idx; issue that slot; compact-remove pulls
# entries above served down; new entry loads freed top. Per-bank order = free
# (same-bank entries share bank_rdy bit + lowest-index). elig==0 -> hold.

DATA = "#2a8f86"; CTL = "#7a4fb0"
f = Fig(1360, 620)


def andg(cx, cy, w, h, lab=""):
    f.path(f"M{cx-w/2} {cy-h/2} L{cx} {cy-h/2} A{h/2} {h/2} 0 0 1 {cx} {cy+h/2} "
           f"L{cx-w/2} {cy+h/2} Z", stroke=INK)
    if lab: f.text(cx-4, cy+3, lab, size=8, anchor="middle", bold=True)


def muxr(cx, cy, w, h, name):
    f.path(f"M{cx} {cy-h/2} L{cx+w} {cy-h/4} L{cx+w} {cy+h/4} L{cx} {cy+h/2} Z", stroke=INK)
    f.text(cx+w/2-2, cy+4, name, size=8, anchor="middle", bold=True)


f.text(40, 30, "LOOKAHEAD (shift-reg) - elig + p_encoder + compact-remove", size=15,
       mono=False, bold=True)

# ---- insert path ----
f.text(40, 95, "new entry", size=9, mono=True, fill=DATA)
f.block(140, 74, 150, 44, "lowest_free_slot", "")
f.line(290, 96, 360, 120, arrow=True, stroke=DATA)

# ---- compact/remove block ----
f.block(360, 100, 520, 52, "COMPACT / REMOVE", "slot[i] <= (i<served)? slot[i] : slot[i+1]")
sx = [420, 540, 660, 780]
for x in sx:
    f.line(x, 152, x, 188, arrow=True, dashed=True, stroke=CTL)   # compact -> slot D

# ---- slots ----
for i, x in enumerate(sx):
    f.rect(x-58, 190, 116, 46, fill=FILL_CELL, width=1.4, rx=5)
    f.text(x, 217, f"e{i}", size=11, anchor="middle", bold=True)
    f.text(x, 205, "{bank,vld,pl}", size=6.5, anchor="middle", fill=MUTED)

# ---- elig ANDs ----
for i, x in enumerate(sx):
    f.line(x, 236, x, 300, arrow=True, stroke=DATA)              # slot vld down
    andg(x, 320, 40, 42, "&")
    f.text(x+26, 312, f"elig[{i}]", size=7.5, mono=True, fill=DATA)
    f.line(x, 341, x, 392, arrow=True, stroke=DATA)              # elig down to p_enc bus

# ---- bank_rdy_vec ----
f.block(120, 300, 170, 44, "bank_rdy_vec", "")
f.path("M290 322 L340 322 L340 320 L398 320", arrow=True, stroke=CTL)   # to elig ANDs (bank_rdy[bank_ei])
f.text(300, 360, "bank_rdy_vec[bank_ei]", size=7.5, mono=True, fill=CTL)

# ---- p_encoder ----
f.block(360, 392, 500, 50, "P_ENCODER  (lowest set)", "-> served_idx , served_oh[3:0] ;  elig==0 -> HOLD")

# served_idx -> compact
f.path("M360 417 L120 417 L120 152 L360 130", arrow=True, stroke=CTL)
f.text(130, 175, "served_idx", size=7.5, mono=True, fill=CTL)

# served_oh -> issue mux sel
f.path("M860 410 L1000 410 L1000 250", arrow=True, stroke=CTL)
f.text(905, 405, "served_oh", size=7.5, mono=True, fill=CTL)

# ---- issue mux ----
muxr(970, 213, 70, 120, "ISSUE\nMUX")
f.path("M838 213 L940 213", arrow=True, stroke=DATA)            # slots bus -> issue mux
f.text(880, 206, "slot entries", size=7, mono=True, fill=MUTED)
f.line(1040, 213, 1120, 213, arrow=True, stroke=DATA)
f.rect(1120, 199, 150, 28, fill=FILL_ACTIVE, width=1.3, rx=4)
f.text(1128, 217, "issued -> BANK_DEC", size=7.5, mono=True)

f.caption(40, 470,
          "elig[i]=vld_i & bank_rdy_vec[bank_ei]. p_encoder -> lowest set = served_idx -> issue that "
          "slot (head if ready, else younger bypasses). COMPACT-REMOVE pulls entries ABOVE served down "
          "1; freed top loads new entry. Order free: same-bank entries share one bank_rdy bit + "
          "lowest-index -> younger same-bank never passes older. elig==0 -> hold (bubble).")

f.save("fig_93_lookahead_shift.svg")
print("wrote fig_93_lookahead_shift.svg")
