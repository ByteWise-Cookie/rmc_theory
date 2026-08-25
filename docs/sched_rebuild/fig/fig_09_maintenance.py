from rtlfig import Fig, MUTED, FILL_LOGIC, FILL_CELL

# fig_09 — Maintenance Engine: peer command source, override-injects into packer.
# Invariant: ME never issues CAS; refresh is REFsb-preferred, opportunistic +
# debt-forced; INIT owns init_done. One shared block, per-rank refresh timers.

SB = "#7a5cb8"
f = Fig(1340, 800)

f.note(1330, 34, "Maintenance Engine  -  one shared block", anchor="end")
f.note(1330, 50, "per-rank refresh timers  (x N_RANKS = 2)", anchor="end")

# ---------------- sub-engines (left) ----------------
f.logic(70, 96, 320, 74, "INIT engine  (boot FSM)", top=True)
f.text(88, 138, "RESET -> CK -> MRW train -> ZQCL", size=11)
f.text(88, 156, "-> PHY handoff -> latch init_done", size=11)

f.logic(70, 196, 320, 156, "REFRESH engine  (per rank)", top=True)
for i, ln in enumerate([
        "tREFI down-ctr -> refresh debt (max 8)",
        "REFsb  BA round-robin 0..3",
        "   (ba=k refreshes bank k in all 8 BG)",
        "opportunistic pull-in / debt-forced",
        "REFab fallback when whole rank idle"]):
    f.text(88, 240 + i * 21, ln, size=11 if i != 2 else 10,
           mono=(i != 2), fill=(MUTED if i == 2 else "#000000"))

f.logic(70, 378, 320, 40, "RFM   (stub)", "RAA > RAAMMT -> rfm_req")
f.logic(70, 430, 320, 40, "ZQ    (stub)", "long-interval ZQCS / ZQCL")
f.logic(70, 482, 320, 40, "MRW   (stub)", "runtime MR writes")

# ---------------- priority mux ----------------
mx = f.mux(500, 250, 250, 66, "inject_prio")
f.text(625, 300, "init > ref_urgent > rfm >", size=10, mono=False,
       anchor="middle", fill=MUTED)
f.text(625, 314, "ref_due > zq > mrw", size=10, mono=False, anchor="middle",
       fill=MUTED)
for y in (133, 250, 398, 450, 502):
    f.line(392, y, 498 if y < 250 else 500, min(max(y, 252), 314), arrow=True)

# ---------------- inject into packer ----------------
f.line(625, 316, 625, 372, arrow=True)
f.text(640, 350, "maint_cmd {type, rank, ba}", size=10, fill=MUTED)
f.logic(505, 372, 240, 50, "packer override slot", "fig_05  -  never CAS")
f.line(625, 422, 625, 470, arrow=True)
f.text(625, 492, "->  packer  ->  DFI", size=12, mono=False, anchor="middle")

# ---------------- coordination outputs (right) ----------------
f.line(750, 130, 1000, 130, arrow=True)
f.text(1010, 126, "init_done -> DFI mux (fig_01)", size=11, mono=False)

f.line(392, 250, 1000, 250, arrow=True, stroke=SB)
f.text(1010, 246, "REF_pending -> bank FSMs (fig_03)", size=11, mono=False,
       fill=SB)

f.line(392, 286, 1000, 286, arrow=True, stroke=SB)
f.text(1010, 282, "gate_rfc[rank] -> scoreboard (fig_04)", size=11, mono=False,
       fill=SB)

f.line(1000, 398, 392, 398, arrow=True, stroke=SB)
f.text(1010, 394, "raa_count <- scoreboard", size=11, mono=False, fill=SB)

# refresh handshake sequence (bottom)
f.rect(70, 590, 900, 120, fill=FILL_CELL, width=1.4)
f.text(520, 614, "refresh handshake", size=12, anchor="middle", bold=True)
for i, ln in enumerate([
        "ref due -> set REF_pending on the 8 target banks",
        "-> scheduler stops new CAS, drains + precharges them",
        "-> ME injects PRE(sb) then REFsb   ->  banks go REFING(tRFCsb)",
        "-> gate_rfc blocks issue until timer clears; other 24 banks keep feeding DQ"]):
    f.text(94, 644 + i * 20, ln, size=11)

f.caption(40, 780, "ME is a peer command source: it never issues CAS, injects "
                   "into the packer with override priority, and drives refresh "
                   "REFsb-first (opportunistic, debt-forced) so the rank keeps "
                   "feeding DQ. INIT owns init_done.")

f.save("fig_09_maintenance.svg")
print("wrote fig_09_maintenance.svg")
