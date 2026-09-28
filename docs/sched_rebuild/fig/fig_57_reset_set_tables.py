from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    INK, PAPER, W_CELL)

# fig_57 — two companion tables for the timestamp doc:
#   (A) RESET on issue  — which can_* SR flops CLEAR (block now)
#   (B) SET at deadline — which next_* is stamped (GC+const); its can_* re-SETs at expiry
# Same cell = same gate, two views: A says "cleared", B says "re-armed with this const".

X = [50, 150, 470, 700, 980]
W = [100, 320, 230, 280, 240]
COLS = ["issued", "BANK", "BG", "RANK", "CH / DQ"]


def cell(f, x, y, w, h, lines, fill=PAPER):
    f.rect(x, y, w, h, fill=fill, width=W_CELL)
    for i, ln in enumerate(lines):
        f.text(x + 9, y + 20 + i * 15, ln, size=9, mono=True,
               fill=(MUTED if ln in ("-", "span BGs", "debt--") else INK))


def header(f, y):
    for i, lab in enumerate(COLS):
        f.rect(X[i], y, W[i], 30, fill=FILL_ACTIVE if i else PAPER, width=W_CELL)
        f.text(X[i] + W[i] / 2, y + 20, lab, size=11, mono=False, anchor="middle",
               bold=(i > 0))
    return y + 30


def table(f, y, title, sub, rows):
    f.text(X[0], y, title, size=14, mono=False, bold=True)
    f.text(X[0], y + 18, sub, size=10, mono=False, fill=MUTED)
    yy = header(f, y + 30)
    for name, fill, b, g, r, c in rows:
        h = 20 + max(len(b), len(g), len(r), len(c)) * 15 + 6
        f.rect(X[0], yy, W[0], h, fill=fill, width=W_CELL)
        f.text(X[0] + W[0] / 2, yy + h / 2 + 4, name, size=11, anchor="middle", bold=True)
        cell(f, X[1], yy, W[1], h, b)
        cell(f, X[2], yy, W[2], h, g)
        cell(f, X[3], yy, W[3], h, r)
        cell(f, X[4], yy, W[4], h, c)
        yy += h
    return yy


FD = FILL_NEW      # demand
FC = FILL_CELL     # cas
FM = FILL_LOGIC    # maint

# ---- Table A : RESET ----
RESET = [
    ("ACT", FD, ["can_act, can_cas,", "can_pre   x1 bank"], ["can_act_bgs", "  x1 BG"],
     ["can_act_bgd +", "faw->can_act_rank", "  x1 rank"], ["-"]),
    ("RD", FC, ["can_pre   x1 bank"], ["can_cas_bgs", "  x1 BG"],
     ["can_wr   x1 rank"], ["can_cas_dq", "  x1 ch"]),
    ("WR", FC, ["can_pre   x1 bank"], ["can_cas_bgs", "  x1 BG"],
     ["can_rd   x1 rank"], ["can_cas_dq", "  x1 ch"]),
    ("PRE", FD, ["can_act;", "can_cas(state)  x1 bank"], ["-"],
     ["can_pre   x1 rank"], ["-"]),
    ("REFsb", FM, ["can_act/cas/pre", "  x8 bank (gate_rfc)"], ["span BGs"],
     ["debt--"], ["-"]),
    ("REFab", FM, ["-"], ["-"], ["gate_rfc:can_a/c/p", "  x1 rank"], ["-"]),
    ("RFMsb", FM, ["can_a/c/p (gate_rfm)", "  x8 bank, RAA--"], ["span BGs"],
     ["-"], ["-"]),
    ("RFMab", FM, ["-"], ["-"], ["gate_rfm   x1 rank"], ["-"]),
    ("ZQ", FM, ["-"], ["-"], ["gate_zq   x1 rank"], ["can_cas_dq", "  x1 ch"]),
    ("MRW", FM, ["-"], ["-"], ["gate_mr(tMRD)", "  x1 rank"], ["-"]),
    ("MRR", FM, ["-"], ["-"], ["gate_mr; dir=R", "  x1 rank"], ["can_cas_dq", "  x1 ch"]),
]

# ---- Table B : SET / timestamp (can_* re-armed with next_*, same x-scope as A) ----
SET = [
    ("ACT", FD, ["can_act(tRC 117),", "can_cas(tRCD 40),", "can_pre(tRAS 77)  x1 bank"],
     ["can_act_bgs", "  (tRRD_L 12)  x1 BG"],
     ["can_act_bgd(tRRD_S 8),", "faw(tFAW 32)  x1 rank"], ["-"]),
    ("RD", FC, ["can_pre(tRTP 18)  x1 bank"], ["can_cas_bgs", "  (tCCD_L 12)  x1 BG"],
     ["can_wr(tRTW 12)  x1 rank"], ["can_cas_dq", "  (+BL/2=8)  x1 ch"]),
    ("WR", FC, ["can_pre", "  (CWL+BL/2+tWR=118)", "  x1 bank"],
     ["can_cas_bgs", "  (tCCD_L_WR 48)  x1 BG"],
     ["can_rd", "  (CWL+BL/2+tWTR 70/52)", "  x1 rank"], ["can_cas_dq", "  (+8)  x1 ch"]),
    ("PRE", FD, ["can_act(tRP 40)  x1 bank"], ["-"], ["can_pre(tPPD 2)  x1 rank"], ["-"]),
    ("REFsb", FM, ["gate_rfc rel", "  +tRFCsb 312   x8 bank"], ["span BGs"],
     ["debt--"], ["-"]),
    ("REFab", FM, ["-"], ["-"], ["gate_rfc rel +tRFC1 708", "  x1 rank"], ["-"]),
    ("RFMsb", FM, ["gate_rfm rel", "  +tRFM   x8 bank"], ["span BGs"],
     ["RAA -= RAAIMT"], ["-"]),
    ("RFMab", FM, ["-"], ["-"], ["gate_rfm rel +tRFM  x1 rank"], ["-"]),
    ("ZQ", FM, ["-"], ["-"], ["gate_zq rel +tZQCAL,", "latch +tZQLAT 30  x1 rank"],
     ["can_cas_dq  x1 ch"]),
    ("MRW", FM, ["-"], ["-"], ["gate_mr rel +tMRD 16,", "live +tMOD 36  x1 rank"], ["-"]),
    ("MRR", FM, ["-"], ["-"], ["gate_mr +tMRD 16  x1 rank"],
     ["can_cas_dq(+8)  x1 ch"]),
]

# ---- lay out both stacked ----
# measure total height first
f = Fig(1240, 1560)
f.text(40, 34, "Timestamp path - RESET table + SET table (companion pair)", size=15,
       mono=False, bold=True)

y = table(f, 70, "A.  RESET on issue  (can_* cleared -> block now)",
          "issue-decode clears the SR flop. count = SR flops written: x1 bank / x1 BG / "
          "x1 rank / x1 ch  (x8 = the 8 REF/RFM targets).", RESET)

y += 44
yend = table(f, y, "B.  SET at deadline  (can_* re-armed; next_* = GC + const)",
      "same gates as A, same x-scope. GE comparator SETs can_* when GC >= next_*. const in CK.",
      SET)

f.caption(40, yend + 30,
          "A and B are one list from two sides: every gate RESET in A is re-SET in B via its "
          "next_* = GC+const. RESET = which flops clear on issue; SET = the deadline each re-arms with.")

f.save("fig_57_reset_set_tables.svg")
print("wrote fig_57_reset_set_tables.svg")
