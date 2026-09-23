from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_64 — CH/DQ (global) scope, x1. dqFree = GC + BL/2 (one DQ bus); caFree = CA bus.
# No address / no demux (single reg). LAST_CAS state feeds rank-turnaround + L3.
# PARKED: cross-rank tRTRS + MRR/ZQ DQ-sharing = the L3/DQ handler (not this adder).

CMP = "#2a8f86"; ISSUE = "#7a4fb0"; GREEN = "#3d8c40"
f = Fig(1300, 900)


def adder(cx, cy, r=20):
    f.counter(cx, cy, r, "+", "")
    f.text(cx, cy + 4, "+", size=13, anchor="middle", bold=True)


f.text(40, 32, "CH / DQ (global) timestamp - x1 (one DQ bus, one CA bus)", size=15,
       mono=False, bold=True)
f.text(40, 150, "x1 => NO address, NO write-demux - single reg, WE = any CAS (either rank).",
       size=9, mono=False, fill=INK)
f.text(40, 168, "dqFree = pure same-dir occupancy (BL/2). Flip penalty (tWTR/tRTW) lives at "
        "RANK (fig_63); cross-rank tRTRS + MRR/ZQ sharing at L3 = the parked DQ handler.",
        size=9, mono=False, fill=MUTED)

DQ, CA = 430, 760

# grant / ctl
f.block(40, 800, 300, 54, "CAS issue", "{dir, rank, bg} (RD/WR/MRR/ZQ)")
f.block(410, 800, 240, 54, "op -> const_sel", "BL/2 (or ZQ-busy)")
f.line(340, 827, 408, 827, arrow=True)

# GC + phase
f.block(40, 690, 300, 54, "global_counter_24b", "shared; compare low 13b")
adder(400, 716)
f.line(340, 716, 378, 716, arrow=True)
f.text(404, 694, "+ph_off", size=8, mono=True, fill=MUTED)
f.path("M422 716 H1180 V560", arrow=False, stroke=GREEN)
f.text(650, 708, "GC_ph -> adders + (13b) compares", size=8, fill=GREEN)

# dqFree + caFree adders
adder(DQ, 600)
f.line(DQ, 800, DQ, 620, arrow=True)
f.text(DQ + 8, 770, "BL/2 (=8)", size=8, mono=True, fill=INK)
f.line(DQ - 40, 560, DQ - 6, 586, arrow=True, stroke=GREEN)

adder(CA, 600)
f.text(CA + 8, 640, "CA occ", size=8, mono=True, fill=INK)
f.line(CA - 40, 560, CA - 6, 586, arrow=True, stroke=GREEN)

# single regs (x1)
for cx, nm in [(DQ, "dqFree"), (CA, "caFree")]:
    f.rect(cx - 45, 470, 90, 70, fill=FILL_CELL, width=W_CELL)
    f.text(cx, 512, nm, size=11, anchor="middle", bold=True)
    f.text(cx + 60, 505, "x1", size=9, fill=MUTED)
    f.line(cx, 580, cx, 540, arrow=True)

# comparators + cans
for cx, nm in [(DQ, "can_cas_dq"), (CA, "can_ca")]:
    f.counter(cx, 400, 21, ">=", "")
    f.line(cx, 470, cx, 421, arrow=True)
    f.text(cx - 42, 404, "GC13", size=8, mono=True, fill=GREEN)
    f.line(cx - 58, 400, cx - 21, 400, arrow=True, stroke=GREEN)
    f.rect(cx - 62, 270, 124, 32, fill=FILL_NEW, width=W_CELL)
    f.text(cx, 290, nm, size=10, mono=True, anchor="middle")
    f.line(cx + 10, 379, cx + 10, 302, arrow=True, stroke=CMP)
    f.text(cx + 14, 350, "set", size=8, fill=CMP)
    f.line(cx - 12, 379, cx - 12, 302, arrow=True, stroke=ISSUE)
    f.text(cx - 30, 350, "rst", size=8, fill=ISSUE)

# LAST_CAS state
f.rect(950, 470, 220, 90, fill=FILL_ACTIVE, width=W_CELL)
f.text(1060, 494, "LAST_CAS (bus state)", size=11, anchor="middle", bold=True)
f.text(962, 518, "dir  rank  bg  ts", size=9, mono=True)
f.line(DQ, 505, 948, 505, arrow=True, dashed=True, stroke=MUTED)
f.text(1060, 585, "-> rank turnaround (fig_63) + L3 tRTRS", size=8, mono=False, fill=MUTED)
f.line(1060, 570, 1060, 560, arrow=True, dashed=True, stroke=MUTED)

# parked handler note
f.rect(950, 640, 300, 90, fill=PAPER, width=1.4, stroke=MUTED)
f.text(1100, 664, "L3 / DQ HANDLER  (PARKED)", size=10, anchor="middle", bold=True,
       fill=MUTED)
f.text(962, 686, "cross-rank tRTRS on rank hop", size=8, mono=True, fill=MUTED)
f.text(962, 702, "turnaround (from RANK scope)", size=8, mono=True, fill=MUTED)
f.text(962, 718, "MRR / ZQ also grab DQ", size=8, mono=True, fill=MUTED)

f.text(40, 210, "RST = issue-decode (reset-dominant).  SET = GC[12:0] >= dqFree/caFree.",
       size=9, mono=False, fill=INK)

f.caption(40, 872,
          "One DQ bus + one CA bus -> single dqFree/caFree regs (x1, no address). Any CAS "
          "(either rank, 1/cycle) stamps dqFree = GC_ph + BL/2; can_cas_dq = GC >= dqFree. "
          "LAST_CAS records {dir,rank,bg,ts} for the rank turnaround gate and the L3 cross-rank "
          "tRTRS pick. dqFree is same-dir occupancy only; flip + rank-hop + MRR/ZQ = parked handler.")

f.save("fig_64_ch_dq_datapath.svg")
print("wrote fig_64_ch_dq_datapath.svg")
