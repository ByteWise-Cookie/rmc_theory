from rtlfig import Fig, MUTED, INK, FILL_CELL, FILL_ACTIVE, FILL_NEW, FILL_LOGIC

# fig_22 - fills the empty bottom box of the per-bank sketch: BANK_ELIG =
# legality + stall generator. Three panels: (1) DRIVE LOGIC = the state-gated
# equations that make illegal commands unable to assert; (2) the BANK_ELIG box
# internals (1-hot cmd + occupancy/stall FSM + grant decode); (3) the LEGALITY
# TABLE (bank state x packet -> which rdy is legal, what is hard-blocked, stall).

GOOD = "#cfe8c0"
BAD  = "#f3c0b8"
WARN = "#ffe0a0"

f = Fig(2040, 1180)
f.note(2030, 30, "BANK_ELIG  -  per-bank legality + stall (fills the bottom box)",
       anchor="end")
f.note(2030, 46, "at most ONE rdy ever high: need_* are state-exclusive", anchor="end")

# ============================================================ PANEL 1: drive
f.text(40, 74, "1.  DRIVE LOGIC   (upstream, state-gated -> illegal cannot fire)",
       size=14, mono=False, bold=True)
f.rect(40, 88, 600, 470, fill=FILL_LOGIC, width=1.4)
eqs = [
 ("derive (only meaningful in OPEN):", None),
 ("row_hit  = vpkt & OPEN & !pre_pending & row==open_row", INK),
 ("row_miss = vpkt & OPEN & !pre_pending & row!=open_row", INK),
 ("", None),
 ("need_cas = row_hit", INK),
 ("need_pre = row_miss", INK),
 ("need_act = vpkt & IDLE", INK),
 ("", None),
 ("the 3 rdy  (need is state-exclusive):", None),
 ("cas_rdy  = need_cas & can_cas", "#2e7d32"),
 ("act_rdy  = need_act & can_act", "#2e7d32"),
 ("pre_rdy  = need_pre & can_pre", "#2e7d32"),
 ("", None),
 ("can_* come from the scoreboard (timing):", None),
 ("can_cas: tRCD-done,tCCD_S/L,tWTR/tRTW", MUTED),
 ("can_act: tRP,tRC,tRRD_S/L,tFAW", MUTED),
 ("can_pre: tRAS,tRTP,tWR", MUTED),
]
yy = 118
for s, c in eqs:
    if s == "":
        yy += 10; continue
    if c is None:
        f.text(60, yy, s, size=12, mono=False, bold=True, fill=INK)
    else:
        f.text(60, yy, s, size=13, mono=True, fill=c)
    yy += 24

# ============================================================ PANEL 2: the box
BX, BY, BW, BH = 40, 690, 600, 452
f.text(40, 610, "2.  BANK_ELIG BOX INTERNALS", size=14, mono=False, bold=True)
f.rect(BX, BY, BW, BH, width=1.8)
f.text(BX + BW - 8, BY + 18, "BANK_ELIG", size=13, anchor="end", fill=MUTED)

# 3 rdy inputs from the top
for i, (nm, x) in enumerate([("cas_rdy", 130), ("act_rdy", 250), ("pre_rdy", 370)]):
    f.line(x, BY - 26, x, BY + 10, arrow=True)
    f.text(x, BY - 32, nm, size=11, anchor="middle")
f.line(130, BY + 10, 370, BY + 10)          # bus into prio

# 1-hot / priority
f.logic(90, BY + 40, 300, 72, "PRIO 1-hot", "cas > act > pre  (safety; already excl.)",
        top=True)
f.line(240, BY + 112, 240, BY + 150, arrow=True)
f.text(252, BY + 138, "bank_cmd[1-hot], bank_go = OR(3 rdy)", size=10, mono=False,
       fill=MUTED)

# occupancy / stall FSM
f.logic(90, BY + 168, 300, 84, "OCC / STALL FSM",
        "occupied: set @ DMUX drain-in ; clr @ (grant & cmd==CAS)", top=True)
f.text(110, BY + 236, "bank_rdy = !occupied", size=12, bold=True)

# grant decode
f.logic(430, BY + 168, 150, 132, "GRANT", "decode", top=True)
f.text(505, BY + 214, "CAS: pop", size=11, anchor="middle")
f.text(505, BY + 232, "ACT: advance", size=11, anchor="middle")
f.text(505, BY + 250, "PRE: set", size=11, anchor="middle")
f.text(505, BY + 268, "pre_pending", size=11, anchor="middle")
f.line(430, BY + 210, 390, BY + 210, arrow=True)   # grant -> occ (pop)
f.line(505, BY + 168, 505, BY + 120, arrow=True)   # grant in from top-right
f.text(505, BY + 108, "grant  (BG/RANK arb)", size=10, mono=False, anchor="middle")

# outputs
# bank_go/cmd -> BG_ARB (right)
f.line(390, BY + 186, BX + BW, BY + 186, arrow=True)
f.text(BX + BW - 8, BY + 178, "bank_go, bank_cmd  ->  BG_ARB", size=11, anchor="end")
# bank_rdy -> up to DMUX (stall)
f.path(f"M90 {BY+236} L62 {BY+236} L62 {BY-46}", arrow=True, dashed=True,
       stroke="#c0392b")
f.text(72, BY + 150, "bank_rdy -> DMUX", size=11, fill="#c0392b")
f.text(72, BY + 166, "(low = STALL)", size=10, mono=False, fill="#c0392b")
# writeback state / pre_pending
f.path(f"M505 {BY+300} L505 {BY+330} L640 {BY+330}", arrow=True, dashed=True,
       stroke=MUTED)
f.text(632, BY + 322, "-> state / pre_pending  (FSM_TABLE writeback)", size=10,
       mono=False, anchor="end", fill=MUTED)

# back-pressure chain note
f.text(BX + 16, BY + BH - 44, "STALL CHAIN (1-deep cell, pop-on-CAS):", size=11,
       mono=False, bold=True)
f.text(BX + 16, BY + BH - 26, "bank busy / can_* low / mid PRE->ACT->CAS  =>  "
       "occupied stays  =>  bank_rdy=0", size=10, mono=False, fill=INK)
f.text(BX + 16, BY + BH - 10, "=>  lookahead -> WLR -> FIFO -> AR/AWREADY (only "
       "the addressed bank blocks)", size=10, mono=False, fill=INK)

# ============================================================ PANEL 3: table
TX, TY = 680, 88
f.text(TX, 74, "3.  LEGALITY TABLE   (bank state x incoming packet)", size=14,
       mono=False, bold=True)
cols = [("state", 190), ("packet", 150), ("rdy fires", 160),
        ("hard-blocked (forced 0)", 300), ("stall", 150)]
rows = [
 ("IDLE", "no row = miss", "act_rdy", "CAS (no row), PRE (nothing)", "drain@ACT", GOOD),
 ("ACTIVATING (tRCD)", "-", "none", "CAS(<tRCD), ACT, PRE", "STALL", WARN),
 ("OPEN", "hit", "cas_rdy", "ACT (re-open), PRE (needed row)", "drain@CAS", GOOD),
 ("OPEN", "miss", "pre_rdy", "CAS = WRONG ROW!, ACT (open)", "hold pkt", BAD),
 ("PRECHARGING (tRP)", "-", "none", "ACT(<tRP), CAS", "STALL", WARN),
 ("OPEN & pre_pending", "mid-seq", "none", "new admit blocked", "bank_rdy=0", WARN),
 ("REFING (gate_rfc)", "-", "none", "all", "STALL", WARN),
]
# header
x = TX
for nm, w in cols:
    f.rect(x, TY, w, 40, fill=FILL_ACTIVE, width=1.3)
    f.text(x + w / 2, TY + 25, nm, size=11, anchor="middle", bold=True)
    x += w
ry = TY + 40
RH = 52
for r in rows:
    vals, tint = r[:5], r[5]
    x = TX
    for (nm, w), v in zip(cols, vals):
        fill = tint if nm in ("rdy fires", "hard-blocked (forced 0)", "stall") else "none"
        # color-code: rdy-cell green tint, blocked red-ish, stall its own
        if nm == "rdy fires":
            fill = GOOD if v != "none" else "#eeeeee"
        elif nm == "hard-blocked (forced 0)":
            fill = BAD
        elif nm == "stall":
            fill = WARN if v in ("STALL", "hold pkt", "bank_rdy=0") else GOOD
        else:
            fill = "none"
        f.rect(x, ry, w, RH, fill=fill, width=1.1)
        f.text(x + w / 2, ry + RH / 2 + 4, v, size=10.5, mono=False,
               anchor="middle")
        x += w
    ry += RH

# illegal summary
IY = ry + 26
f.text(TX, IY, "HARD-BLOCKED IN HW (state gate, not can_* alone):", size=13,
       mono=False, bold=True)
ills = [
 "1. CAS unless (row_hit & OPEN & !pre_pending)  -> blocks WRONG-ROW read/write (silent corruption)",
 "2. ACT while OPEN (diff row, no PRE first)      -> tRAS / double-open",
 "3. PRE while state!=OPEN or < tRAS               -> nothing to close / tRAS",
 "4. any cmd during ACTIVATING/PRECHARGING/REFING  -> timing violation -> STALL",
]
iy = IY + 24
for s in ills:
    f.text(TX + 10, iy, s, size=12, mono=True, fill=INK)
    iy += 24

# rating box
RTX, RTY = TX, iy + 20
f.rect(RTX, RTY, 1300, 210, fill=FILL_NEW, width=1.6)
f.text(RTX + 14, RTY + 26, "RATING  -  8.5 / 10", size=15, mono=False, bold=True)
rate = [
 "+ Legality by CONSTRUCTION: state-exclusive need_* -> mutually-exclusive rdy -> an illegal cmd literally cannot assert. Not checked-after.",
 "+ Timing fully in can_* (scoreboard) -> ELIG is pure combinational select; clean legality/selection split.",
 "+ 1-deep cell + pop-on-CAS + occupied->bank_rdy = natural PER-BANK back-pressure, no global stall.",
 "+ Miss = explicit PRE->ACT->CAS with pre_pending fence -> no false state, matches JEDEC.",
 "-  pop-only-on-CAS holds the cell the whole ~tRP+tRCD (~80 CK) on a miss -> a HOT bank stalls its lane long (mitigated by spread map + lookahead).",
 "-  1-deep = stalled bank blocks lane head; relies on lookahead depth for MLP. No auto-precharge (RDA/WRA) yet = extra PRE bandwidth.",
]
ry2 = RTY + 48
for s in rate:
    f.text(RTX + 14, ry2, s, size=11, mono=False, fill=INK)
    ry2 += 22

f.caption(40, 1165, "BANK_ELIG turns state + need_* + can_* into the 3 mutually-"
                    "exclusive rdy and the bank_rdy stall; illegal transitions are "
                    "blocked by the state gate on need_*, and a stuck bank back-"
                    "pressures only its own lane via pop-on-CAS occupancy.")

f.save("fig_22_bank_elig.svg")
print("wrote fig_22_bank_elig.svg")
