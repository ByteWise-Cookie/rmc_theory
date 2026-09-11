from rtlfig import Fig, MUTED, INK, FILL_CELL, FILL_ACTIVE, FILL_LOGIC

# fig_24 - PRE lane, one-hot end to end. No encoder, no decoder, no shift reg.
# Banks drive a one-hot pre_rdy vector; mask off in-flight; isolate the two
# lowest set bits (x & -x, twice); revalidate live; hand to the phaser over a
# backpressured valid/ready. grant IS the one-hot, straight back to the cell.
# Invariant this figure exists to show: VALID is free-running, READY gates.

f = Fig(1440, 620)

f.note(1430, 30, "PRE lane  -  mask + find-first-two, one-hot end to end",
       anchor="end")
f.text(30, 46, "PRE lane   (one-hot, no encoder / decoder / shift reg)", size=15,
       mono=False, bold=True)
f.text(30, 66, "banks drive one-hot pre_rdy; pick the 2 lowest set bits; the grant "
       "one-hot goes straight to the cell.  Max 2 PRE / bundle (tPPD=2).",
       size=11, mono=False, fill=MUTED)

# ---- blocks (left -> right dataflow) --------------------------------------
mask  = f.logic(250, 205, 175, 118, "AND_MASK",
                sub="elig = pre_rdy & ~inflight")
ff2   = f.logic(495, 205, 210, 118, "FIND_FIRST_2",
                sub="p0=e&-e ; m1=e&~p0 ; p1=m1&-m1")
reval = f.logic(775, 205, 175, 118, "REVALIDATE", sub="& pre_rdy (live)")

phas  = f.block(1180, 185, 180, 175, "phase_packer")
f.text(1270, 250, "place", size=13, anchor="middle", mono=False, fill=INK)
f.text(1270, 272, "@ph0 , @ph2", size=12, anchor="middle")
f.text(1270, 300, "tPPD=2", size=11, anchor="middle", mono=False, fill=MUTED)
f.text(1270, 318, "2 diff banks", size=11, anchor="middle", mono=False, fill=MUTED)

# ---- inflight register (the ONLY state in the lane) ------------------------
f.cells(250, 430, 1, 175, 58, ["inflight  x32"])
f.text(337, 502, "the only flop in the lane", size=11, mono=False,
       anchor="middle", fill=MUTED)

# ---- primary input ---------------------------------------------------------
f.port_in(60, mask, 264, "pre_rdy", bus=True, width="x32")
f.text(70, 300, "one-hot / bank  (from cells)", size=11, mono=False, fill=MUTED)

# ---- straight-through dataflow --------------------------------------------
f.line(mask.r + 2, 264, ff2.l - 2, 264, arrow=True)
f.line(ff2.r + 2, 264, reval.l - 2, 264, arrow=True)
f.text(600, 340, "x & -x  =  isolate lowest set bit (blsi = priority find-first)",
       size=11, mono=False, fill=MUTED, anchor="middle")

# ---- REVAL -> phaser : the two picked PREs + the handshake ------------------
f.line(reval.r + 2, 232, phas.l - 2, 232, arrow=True)
f.text(reval.r + 8, 224, "preA (one-hot)", size=11, mono=False)
f.line(reval.r + 2, 292, phas.l - 2, 292, arrow=True)
f.text(reval.r + 8, 284, "preB (one-hot)", size=11, mono=False)
f.text(reval.r + 8, 210, "VALID = |elig   (free-running)", size=11, mono=False,
       fill="#2e7d32", bold=True)
f.line(phas.l - 2, 340, reval.r + 2, 340, arrow=True, dashed=True)
f.text(reval.r + 8, 356, "READY  (phaser: slot free)", size=11, mono=False,
       fill="#c0392b", bold=True)

# ---- inflight read : ~inflight into the mask (dashed feedback) --------------
f.line(337, 430, 337, mask.b + 2, arrow=True, dashed=True)
f.text(347, 400, "~inflight", size=11, mono=False, fill=MUTED)

# ---- inflight write : set on grant (from transfer), clear on pop -----------
f.path("M1180 348 L1180 552 L612 552 L612 488", arrow=True, dashed=True)
f.text(600, 574, "granted (preA|preB on transfer)  ->  set inflight   "
       "(clear on cell pop)", size=11, mono=False, fill=MUTED, anchor="middle")
f.text(63, 460, "pop clears", size=11, mono=False, fill=MUTED)
f.line(150, 459, 248, 459, arrow=True, dashed=True)

# ---- the invariant, stated -------------------------------------------------
f.text(30, 602, "grant one-hot = the pick.  no encode / decode.  find-first-two "
       "is combinational -> 2 PRE in one clk, no shift, no load penalty.",
       size=11, mono=False, bold=True, fill=INK)

f.caption(30, 618, "PRE lane: elig = pre_rdy & ~inflight ; p0=e&-e, p1=(e&~p0)&-(..) "
                   "; revalidate live ; phaser pulls <=2/bundle over a backpressured "
                   "valid/ready - PRE waits via held VALID, never by gating VALID on "
                   "READY.")

f.save("fig_24_pre_lane.svg")
print("wrote fig_24_pre_lane.svg")
