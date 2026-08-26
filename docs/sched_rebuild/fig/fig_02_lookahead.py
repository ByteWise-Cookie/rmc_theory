from rtlfig import Fig, MUTED, FILL_ACTIVE, FAINT

# fig_02 — combined-path lookahead / bank-stall bypass.
# Invariant: a younger entry to a READY bank bypasses a stalled e0;
# bank_cmp keeps per-bank order by killing a younger same-bank entry.

f = Fig(1000, 760)

# ---------------- req in at tail, head drains at e0 ----------------
f.text(470, 70, "combined path in", size=12, mono=False, anchor="middle")
f.line(425, 78, 425, 116, arrow=True)

# ---------------- 4-entry shift register (e0 = head/oldest) ----------------
# scenario shown: e0 bank stalled, e1 (diff ready bank) selected this cycle.
cx = f.cells(110, 118, 4, 90, 54, ["e0", "e1", "e2", "e3"],
             fills=[FAINT, FILL_ACTIVE, None, None])
f.ptr_in(cx[0], 96, 116, "head")
f.text(cx[0], 190, "bank stalled", size=10, mono=False, anchor="middle", fill=MUTED)
f.text(cx[1], 190, "selected", size=10, mono=False, anchor="middle", fill=MUTED)

# ---------------- per-entry probe vs bank_rdy ----------------
for c in cx:
    f.line(c, 172, c, 214, arrow=True)
    f.logic(c - 42, 214, 84, 48, "probe", "bank stall")

# bank_rdy bus from the scoreboard into every probe
f.line(960, 238, cx[3] + 44, 238, arrow=True)
f.slash(720, 238, "bank_rdy[31:0]")
f.text(720, 226, "from scoreboard  ->  all probes", size=10, mono=False,
       anchor="middle", fill=MUTED)

# ---------------- bank_cmp: pairwise order guard ----------------
for c in cx:
    f.line(c, 262, c, 306, arrow=True)
f.text(cx[3] + 70, 288, "elig[3:0] + bank[k]", size=10, mono=False, fill=MUTED)
f.logic(90, 306, 410, 58, "bank_cmp",
        "6 pairs  -  kill elig[k] if bank[k] == an older entry's bank")

# ---------------- prio_enc -> head mux ----------------
f.line(250, 364, 250, 410, arrow=True)
f.text(262, 388, "elig[3:0] masked", size=10, mono=False, fill=MUTED)
f.logic(130, 410, 240, 50, "prio_enc", "lowest eligible wins")

f.line(250, 460, 250, 512, arrow=True)
f.text(262, 488, "sel", size=12)
mx = f.mux(150, 512, 200, 52, "head_mux")

# entry data tapped from the shift reg into the mux
f.path("M556 145 L650 145 L650 500 L250 500 L250 512", arrow=True)
f.text(560, 137, "entry data", size=10, mono=False, fill=MUTED)

# ---------------- head mux out -> per-bank decoder ----------------
f.line(250, 564, 250, 606, arrow=True)
f.slash(250, 585, "REQ_W")
f.text(264, 585, "{rob_index, phy_adr, op, valid_gated}", size=10, fill=MUTED)

f.logic(100, 606, 300, 54, "per_bank_decoder", "5b  ->  1-of-32  (8 BG x 4 banks)")
f.line(250, 660, 250, 704, arrow=True)
f.text(250, 726, "->  per-bank paths (stage 3)", size=12, mono=False, anchor="middle")

# ---------------- shift-at-sel feedback ----------------
f.path("M250 435 L60 435 L60 106 L108 106", arrow=True, dashed=True)
f.text(66, 300, "shift at sel", size=10, mono=False, fill=MUTED)

f.caption(40, 748, "A younger entry to a ready bank bypasses a stalled e0; "
                   "bank_cmp keeps per-bank order by killing a younger "
                   "same-bank entry.")

f.save("fig_02_lookahead.svg")
print("wrote fig_02_lookahead.svg")
