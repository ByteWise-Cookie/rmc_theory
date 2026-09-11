from rtlfig import Fig, MUTED, FILL_CELL, FILL_ACTIVE, FILL_NEW

# fig_14 - RAW same-line hazard timeline. Top = the bug (MC reorders R ahead of
# an older same-line W -> stale read). Bottom = the fix (CIF holds the read
# request until the write retires). Invariant: same-line ordering is a CIF
# request-wise stall, never an MC packet-wise check.

BAD = "#c0392b"
OK  = "#2e7d32"

f = Fig(1180, 660)
f.note(1170, 30, "RAW same-line hazard  -  program order: W(X) then R(X)",
       anchor="end")

X0, STEP, NT = 200, 96, 9

def axis(y):
    f.line(X0 - 20, y, X0 + (NT - 1) * STEP + 40, y, stroke=MUTED)
    for i in range(NT):
        x = X0 + i * STEP
        f.line(x, y - 4, x, y + 4, stroke=MUTED)
        f.text(x, y - 10, f"t{i}", size=11, mono=False, anchor="middle",
               fill=MUTED)

def ev(cyc, y, label, span=1, fill=FILL_CELL, stroke=None):
    x = X0 + cyc * STEP - 40
    w = 80 + (span - 1) * STEP
    f.rect(x, y, w, 40, fill=fill, width=1.6, **({"stroke": stroke} if stroke else {}))
    f.text(x + w / 2, y + 24, label, size=10, mono=False, anchor="middle")

# ================= TOP: the bug =================
f.text(40, 78, "WITHOUT ordering  -  MC reorders freely", size=13,
       mono=False, bold=True, fill=BAD)
axis(112)
f.text(150, 150, "WRITE", size=11, mono=False, anchor="end", fill=MUTED)
f.text(150, 216, "READ", size=11, mono=False, anchor="end", fill=MUTED)

ev(0, 130, "W(X) admit", fill=FILL_ACTIVE)
ev(8, 130, "CAS-W (late)", fill=FILL_CELL)

ev(1, 196, "R(X) admit", fill=FILL_ACTIVE)
ev(3, 196, "RD issue", fill=FILL_ACTIVE)
ev(4, 196, "RD ret: STALE", fill=FILL_NEW, stroke=BAD)

f.text(360, 262, "WLR reads-first batch floats R(X) ahead of the older W(X)",
       size=10, mono=False, anchor="middle", fill=BAD)
f.text(X0 + 4 * STEP, 244, "DRAM still holds OLD line X", size=9, mono=False,
       anchor="middle", fill=BAD)

# ================= BOTTOM: the fix =================
f.text(40, 360, "WITH CIF hold  -  request-wise stall", size=13,
       mono=False, bold=True, fill=OK)
axis(394)
f.text(150, 432, "WRITE", size=11, mono=False, anchor="end", fill=MUTED)
f.text(150, 498, "READ", size=11, mono=False, anchor="end", fill=MUTED)

ev(0, 412, "W(X) admit", fill=FILL_ACTIVE)
ev(2, 412, "CAS-W issue", fill=FILL_ACTIVE)
ev(5, 412, "W retire", fill=FILL_CELL, stroke=OK)

ev(1, 478, "R(X) HELD  (ARREADY low, at CIF)", span=4, fill=FILL_CELL, stroke=OK)
ev(6, 478, "RD issue", fill=FILL_ACTIVE)
ev(7, 478, "RD ret: FRESH", fill=FILL_NEW, stroke=OK)

# release edge: W retire -> release read
f.path("M{} 452 L{} 470".format(X0 + 5 * STEP, X0 + 5 * STEP), arrow=True,
       dashed=True, stroke=OK)
f.text(X0 + 5 * STEP + 6, 466, "completion tag -> release", size=9, mono=False,
       fill=OK)

f.caption(40, 640, "Same-line ordering is a CIF request-wise stall (hold the AXI "
                   "read until the write retires), NOT an MC packet-wise check - "
                   "post-hash the MC has no line view. Overlaps are rare, so the "
                   "coarse hold costs ~nothing.")

f.save("fig_14_raw_timeline.svg")
print("wrote fig_14_raw_timeline.svg")
