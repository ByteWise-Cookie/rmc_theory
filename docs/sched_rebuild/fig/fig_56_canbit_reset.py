from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_56 — which can_* RESET on issue (mirror of fig_50 writeback).
# Each stamped next_* RESETS its can_* (block now); comparator re-SETS at deadline.
# Reset hits the SCOPE gate (bank entry / BG gate / rank gate).

f = Fig(1280, 560)


def cell(x, y, w, h, lines, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    for i, ln in enumerate(lines):
        f.text(x + 10, y + 22 + i * 17, ln, size=10, mono=True,
               fill=(MUTED if ln == "-" else INK))


f.text(40, 38, "can_* RESET on issue - which SR flops clear (mirror of fig_50)",
       size=15, mono=False, bold=True)
f.note(40, 58, "On issue, each stamped next_* RESETS its can_* to 0 (block now); the GE "
               "comparator re-SETS it when the deadline passes. Reset hits the scope gate.")

X = [50, 150, 470, 720, 1010]
W = [100, 320, 250, 290, 230]
HY = 92
for i, lab in enumerate(["issued", "BANK", "BG", "RANK", "GLOBAL / DQ"]):
    f.rect(X[i], HY, W[i], 34, fill=FILL_ACTIVE if i else PAPER, width=W_CELL)
    f.text(X[i] + W[i] / 2, HY + 22, lab, size=12, mono=False, anchor="middle",
           bold=(i > 0))

ROWS = [
    ("ACT", FILL_NEW,
     ["can_act, can_cas, can_pre", "  (this bank)"],
     ["can_act_bgs", "  (whole BG)"],
     ["can_act_bgd (tRRD_S)", "faw -> can_act_rank"],
     ["-"]),
    ("RD", FILL_CELL,
     ["can_pre"],
     ["can_cas_bgs (tCCD_L)"],
     ["can_wr  (turnaround)"],
     ["can_cas_dq (dqFree)"]),
    ("WR", FILL_CELL,
     ["can_pre"],
     ["can_cas_bgs (tCCD_L_WR)"],
     ["can_rd  (turnaround)"],
     ["can_cas_dq (dqFree)"]),
    ("PRE", FILL_LOGIC,
     ["can_act (tRP)", "can_cas (state: row closed)"],
     ["-"],
     ["can_pre (tPPD, diff bank)"],
     ["-"]),
    ("REF", FILL_LOGIC,
     ["can_act/cas/pre", "  (8 targets, gate_rfc)"],
     ["targets span BGs"],
     ["-"],
     ["-"]),
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

ny = y + 24
f.note(40, ny, "1:1 with fig_50: every next_* stamped -> its can_* reset. Scope matters - "
               "resetting can_act_bgs blocks the WHOLE bank-group's ACTs; can_*_dq / turn are rank/global.")
f.note(40, ny + 20, "PRE also clears can_cas of its bank via STATE (row closed -> not OPEN), not a "
                    "timestamp. REF's gate_rfc blocks ALL three on the 8 target banks until tRFCsb.")
f.note(40, ny + 40, "Same-rank ACT + RD (rcas) example: ACT resets {can_act/cas/pre[b], "
                    "can_act_bgs[g], can_act_bgd}; RD resets {can_pre[b], can_cas_bgs[g], can_wr, can_cas_dq}.")

f.save("fig_56_canbit_reset.svg")
print("wrote fig_56_canbit_reset.svg")
