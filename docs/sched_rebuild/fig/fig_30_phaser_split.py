from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_30 — phaser split: command-token domain vs CA-beat encoder.
# Invariant: commit/feedback is 1 token per command (no dup); the 2-cyc->2-beat
# expansion lives ONLY in the output encoder. No dedup hardware.

f = Fig(1200, 760)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=11, mono=False, anchor=anchor, fill=MUTED)


# ---------------- header ----------------
f.text(40, 38, "Phaser split - command tokens vs CA-beat encoder",
       size=15, mono=False, bold=True)
f.note(40, 58, "Commit path = 1 token per command (no duplicate). 2-cyc -> 2 "
               "beats expands ONLY in the output encoder. No dedup logic.")

# ---------------- arb winners -> packer ----------------
f.logic(50, 92, 200, 54, "ARB WINNERS", "cas/act/pre + maint", top=True)
f.line(252, 119, 296, 119, arrow=True)
f.logic(298, 88, 200, 62, "PHASE_PACKER", "place -> tokens", top=True)

# gear cfg reg (feeds encoder + GC timebase)
f.logic(860, 92, 160, 48, "gear cfg reg", "preset 1/2/4", top=True)
f.line(940, 140, 940, 342, arrow=True)
cnote(948, 250, "gear (slot mask + placement)")

# ---------------- token bundle ----------------
f.line(398, 150, 398, 186, arrow=True)
tb = f.block(298, 186, 300, 128, "TOKEN_BUNDLE")
f.text(314, 212, "cmd  bank  addr  ph  len", size=12, fill=MUTED)
f.text(314, 236, "CAS   b12   c..   0   2", size=12)
f.text(314, 258, "ACT   b07   r..   2   2", size=12)
f.text(314, 280, "PRE   b19   -    -   1", size=12)
cnote(314, 302, "one entry per command  (no dup)")

# split
f.path("M298 250 H190 V354", arrow=True)     # -> commit (left)
f.path("M598 250 H700 V342", arrow=True)      # -> encoder (right)

# ================= DOMAIN A : commit / feedback =================
f.text(150, 348, "COMMIT  -  1 per token", size=12, mono=False, bold=True)
f.line(190, 356, 190, 384, arrow=True)
f.line(120, 388, 500, 388, stroke=INK)        # commit rail
fsm = f.block(60, 412, 150, 52, "FSM_TABLE")
sb = f.block(232, 412, 178, 52, "SCOREBOARD", "next_* / dqFree")
raa = f.block(432, 412, 120, 52, "RAA_CTR")
for cx in (135, 321, 492):
    f.line(cx, 388, cx, 410, arrow=True, dashed=True)
cnote(60, 486, "one writeback per command - iterate tokens, no skip, no dedup")
cnote(60, 504, "(gear not needed here; GC += gear is the separate timebase)")

# ================= DOMAIN B : CA-beat encoder =================
enc = f.logic(700, 342, 320, 66, "CA_BEAT_ENCODER", "token -> 1 | 2 dfi beats",
              top=True)
# tail_pending self-loop (1:1 straddle)
f.path("M700 372 C660 372 660 408 700 400", arrow=True, dashed=True)
cnote(590, 392, "tail_pending")
cnote(590, 408, "(1:1 straddle)")

# phase-slot output (2-cyc ACT expanded to 2 beats @ph0,ph1)
labels = [("ph0", "cs0 a1", FILL_ACTIVE), ("ph1", "cs1 a2", FILL_ACTIVE),
          ("ph2", "NOP", PAPER), ("ph3", "NOP", PAPER)]
f.line(860, 408, 860, 470, arrow=True)
for i, (ph, txt, fill) in enumerate(labels):
    x = 700 + i * 80
    f.rect(x, 470, 76, 50, fill=fill, width=W_CELL,
           stroke=(FAINT if txt == "NOP" else INK))
    f.text(x + 38, 488, ph, size=11, anchor="middle", fill=MUTED)
    f.text(x + 38, 508, txt, size=12, anchor="middle",
           fill=(MUTED if txt == "NOP" else INK))
cnote(1030, 496, "2-cyc -> 2 beats:")
cnote(1030, 512, "dup ISOLATED here")
f.line(860, 522, 860, 558, arrow=True)
f.text(872, 552, "-> DFI CA (dfi_cs / dfi_address) -> PHY", size=12, mono=False)

f.caption(40, 712,
          "Two packer outputs: a token list (1 entry/command) drives commit + "
          "feedback with no duplicate;")
f.caption(40, 730,
          "the CA-beat encoder expands each token to 1-2 dfi phases (2-cyc = 2 "
          "beats) - the only place duplication exists. tail_pending holds beat2 into the next bundle at 1:1.")

f.save("fig_30_phaser_split.svg")
print("wrote fig_30_phaser_split.svg")
