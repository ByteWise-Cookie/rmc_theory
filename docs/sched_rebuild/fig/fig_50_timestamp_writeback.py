from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_50 — timestamp writeback map: on issuing a cmd, which next_* deadline it
# writes and at which scope (bank / BG / rank / global-DQ). next_* = GC + const;
# can_* later checks GC >= next_*. DDR5-4800B CK.

f = Fig(1280, 1020)


def cell(x, y, w, h, lines, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    for i, ln in enumerate(lines):
        f.text(x + 10, y + 22 + i * 17, ln, size=10, mono=True,
               fill=(MUTED if ln.startswith(" ") or ln == "-" else INK))


f.text(40, 38, "Timestamp writeback - on issue, which next_* is written, where",
       size=15, mono=False, bold=True)
f.note(40, 58, "ALL commands. Demand (cas/act/pre) + maintenance/config (ref/rfm/zq/mrw/mrr). "
               "Each issue writes next_* = GC + const into a scope reg; can_* gates GC >= next_*.")

# columns
X = [50, 150, 440, 690, 1010]
W = [100, 290, 250, 320, 230]
labels = ["issued", "BANK", "BG", "RANK", "GLOBAL / DQ"]
HY = 92
for i, lab in enumerate(labels):
    f.rect(X[i], HY, W[i], 34, fill=FILL_ACTIVE if i else PAPER, width=W_CELL)
    f.text(X[i] + W[i] / 2, HY + 22, lab, size=12, mono=False, anchor="middle",
           bold=(i > 0))

ROWS = [
    ("ACT", FILL_NEW,
     ["->ACT  tRC=117", "->CAS  tRCD=40", "->PRE  tRAS=77"],
     ["->ACT  tRRD_L=12"],
     ["->ACT  tRRD_S=8", "faw_ts push (tFAW=32)"],
     ["-"]),
    ("RD", FILL_CELL,
     ["->PRE  tRTP=18"],
     ["->CAS  tCCD_L=12"],
     ["->WR  tRTW=12", "last_cas_dir=R"],
     ["dqFree +BL/2=8", "last_cas_{ts,rank,bg}", "tRTRS (x-rank)"]),
    ("WR", FILL_CELL,
     ["->PRE  CWL+BL/2+tWR=118"],
     ["->CAS  tCCD_L_WR=48"],
     ["->RD  CWL+BL/2+tWTR", "   L=70 / S=52", "last_cas_dir=W"],
     ["dqFree +BL/2=8", "last_cas_{ts,rank,bg}"]),
    ("PRE", FILL_LOGIC,
     ["->ACT  tRP=40", "(PREab: ALL banks; PREsb: 8)"],
     ["-"],
     ["->PRE  tPPD=2 (diff bank)"],
     ["-"]),
    ("REFsb", FILL_ACTIVE,
     ["gate_rfc/REFING", "  +tRFCsb=312 (8 targets)"],
     ["targets span BGs"],
     ["debt--"],
     ["-"]),
    ("REFab", FILL_ACTIVE,
     ["-"],
     ["-"],
     ["gate_rfc ALL banks", "  +tRFC1=708 ; debt--"],
     ["-"]),
    ("RFM", FILL_ACTIVE,
     ["gate_rfm +tRFM (targets)", "RAA -= RAAIMT"],
     ["RFMsb spans BGs"],
     ["(RFMab: whole rank)"],
     ["-"]),
    ("ZQ", FILL_ACTIVE,
     ["-"],
     ["-"],
     ["gate_zq +tZQCAL", "  then LATCH +tZQLAT=30"],
     ["DQ driver busy (cal)"]),
    ("MRW", FILL_ACTIVE,
     ["-"],
     ["-"],
     ["gate_mr +tMRD=16", "  setting live +tMOD=36 (device)"],
     ["blocks issue in tMRD"]),
    ("MRR", FILL_ACTIVE,
     ["-"],
     ["-"],
     ["dir=R (DQ read)"],
     ["dqFree +BL/2=8", "sideband return (no gate)"]),
]

y = HY + 34
for name, fill, bank, bg, rank, glob in ROWS:
    h = 22 + max(len(bank), len(bg), len(rank), len(glob)) * 17 + 8
    f.rect(X[0], y, W[0], h, fill=fill, width=W_CELL)
    f.text(X[0] + W[0] / 2, y + h / 2 + 4, name, size=13, anchor="middle", bold=True)
    cell(X[1], y, W[1], h, bank)
    cell(X[2], y, W[2], h, bg)
    cell(X[3], y, W[3], h, rank)
    cell(X[4], y, W[4], h, glob)
    y += h

# ---------------- notes ----------------
ny = y + 26
f.text(40, ny, "reading it:", size=13, mono=False, bold=True)
f.note(40, ny + 22, "Each issued cmd stamps `next_x = GC + const` into the scope reg for "
                    "the relationship it constrains. A later cmd is legal when GC >= its next_x.")
f.note(40, ny + 42, "Same value, different scope: CAS->CAS diff-BG = tCCD_S=8 = dqFree (GLOBAL); "
                    "CAS->CAS same-BG = tCCD_L/L_WR (BG). Use whichever scope the pair falls in.")
f.note(40, ny + 62, "Cross-bank constraints are WRITTEN into the shared scope reg at issue (stage 6): "
                    "e.g. ACT writes the BG's next_act (tRRD_L) that all 4 banks read.")
f.note(40, ny + 82, "tFAW = rolling 4-ACT window per rank (faw_ts[4]); WR->RD tWTR measured from "
                    "end of write burst (L=same-BG 24, S=diff-BG 6); turnaround REPLACES dqFree at a flip.")

f.caption(40, ny + 118,
          "The timestamp path = this writeback. On each of the <=3 issued cmds (+ref), stamp "
          "next_* at bank/BG/rank/global per the table; comparators turn next_* into the can_* "
          "gates the arb reads. ref writes gate_rfc (a +tRFCsb timestamp) - it's in this path too.")

f.save("fig_50_timestamp_writeback.svg")
print("wrote fig_50_timestamp_writeback.svg")
