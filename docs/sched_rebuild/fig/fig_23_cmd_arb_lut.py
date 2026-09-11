from rtlfig import Fig, MUTED, INK, FILL_ACTIVE

# fig_23 - CMD_ARB lookup table, meant to paste beside the CMD_ARB (tier-1) block.
# One row per {bank state x packet x pre_pending}; columns give the gate, the
# command that FIRES downstream to BGB_ARB, what happens if the gate is low, and
# the transitions that are HARD-BLOCKED (can never assert). One look, full answer.

GRN  = "#cfe8c0"   # fires a real command
AMB  = "#ffe0a0"   # wait / stall (bank_go=0, bank_rdy low)
RED  = "#f3c0b8"   # illegal, forced 0

f = Fig(1500, 760)
f.note(1490, 30, "CMD_ARB lookup  -  legal / illegal / what fires downstream",
       anchor="end")
f.text(30, 58, "CMD_ARB decision table   (tier-1, per bank)", size=15,
       mono=False, bold=True)
f.text(30, 78, "at most ONE bank_cmd fires (need_* are state-exclusive).  "
       "FIRE = {bank_go=1, bank_cmd} -> BGB_ARB.   WAIT/STALL = bank_go=0, "
       "bank_rdy low = back-pressure.", size=11, mono=False, fill=MUTED)

cols = [("bank state", 150), ("packet vs open_row", 150), ("pre_pend", 78),
        ("need", 108), ("gate  (can_* required)", 320),
        ("FIRE  -> BGB_ARB", 214), ("gate low", 118),
        ("ILLEGAL here (forced 0)", 272)]

# row = (state, pkt, pp, need, gate, fire, low, illegal)
rows = [
 ("IDLE", "no open row", "0", "need_act",
  "can_act: tRP · tRC · tRRD_S/L · tFAW[4]",
  "ACT  (open_row<-row)", "WAIT", "CAS (no row) · PRE (nothing)"),
 ("ACTIVATING", "- (tRCD running)", "0", "-",
  "tRCD not elapsed",
  "NOP / STALL", "STALL", "CAS(<tRCD) · ACT · PRE"),
 ("OPEN", "HIT  (row ==)", "0", "need_cas",
  "can_cas: tCCD_S/L · dir tWTR/tRTW · tCCD_L_WR",
  "CAS  (col, arms data)", "WAIT", "ACT (re-open) · PRE (needed row)"),
 ("OPEN", "MISS  (row !=)", "0", "need_pre",
  "can_pre: tRAS · tRTP · tWR",
  "PRE  (sets pre_pending)", "WAIT", "CAS = WRONG ROW! · ACT (row open)"),
 ("OPEN", "MISS", "1", "- (PRE in flight)",
  "await PRE commit",
  "NOP -> PRECHARGING", "hold", "CAS · ACT · new admit"),
 ("PRECHARGING", "- (tRP running)", "1->0", "-",
  "tRP not elapsed",
  "NOP / STALL", "STALL", "ACT(<tRP) · CAS"),
 ("IDLE (post-PRE)", "act_path held", "0", "need_act",
  "can_act: tRP-done · tRRD · tFAW[4]",
  "ACT", "WAIT", "CAS · PRE"),
 ("OPEN (post-ACT)", "now HIT", "0", "need_cas",
  "can_cas: tRCD-done · tCCD · dir",
  "CAS", "WAIT", "ACT · PRE"),
 ("REFING", "- (gate_rfc)", "-", "-",
  "gate_rfc high (bank locked)",
  "NOP / STALL", "STALL", "ALL"),
 ("any", "MAINT due", "-", "ref_pending",
  "ME override priority (init>ref_urgent>..)",
  "REF ; FSM->IDLE", "-", "CAS suppressed · open_row lost"),
]

X0, Y0, RH = 30, 96, 44
# header
x = X0
for nm, w in cols:
    f.rect(x, Y0, w, 32, fill=FILL_ACTIVE, width=1.3)
    f.text(x + w / 2, Y0 + 21, nm, size=11, anchor="middle", bold=True)
    x += w
ry = Y0 + 32
for r in rows:
    x = X0
    for (nm, w), v in zip(cols, r):
        if nm.startswith("FIRE"):
            fill = AMB if ("NOP" in v or "STALL" in v) else GRN
        elif nm.startswith("ILLEGAL"):
            fill = RED
        elif nm == "gate low":
            fill = AMB if v in ("WAIT", "STALL", "hold") else "none"
        else:
            fill = "none"
        f.rect(x, ry, w, RH, fill=fill, width=1.0)
        sz = 10 if (nm.startswith("gate") and len(v) > 30) else 10.5
        f.text(x + w / 2, ry + RH / 2 + 4, v, size=sz, mono=False,
               anchor="middle")
        x += w
    ry += RH

# legend
ly = ry + 26
for lbl, col, tx in [("FIRE", GRN, "real cmd to BGB_ARB (bank_go=1)"),
                     ("WAIT/STALL", AMB, "bank_go=0, bank_rdy low = back-pressure"),
                     ("ILLEGAL", RED, "state gate forces rdy=0 - can never assert")]:
    f.rect(X0, ly, 22, 16, fill=col, stroke=INK, width=1.0)
    f.text(X0 + 30, ly + 13, f"{lbl}", size=11, mono=False, bold=True)
    f.text(X0 + 140, ly + 13, tx, size=11, mono=False, fill=MUTED)
    ly += 24

f.text(X0, ly + 14, "KEY GUARD:  CAS fires ONLY on (HIT & OPEN & !pre_pending) - "
       "a MISS never emits CAS -> no wrong-row read/write (silent corruption).",
       size=11, mono=False, bold=True, fill="#c0392b")
f.text(X0, ly + 34, "MISS path = PRE -> (tRP) -> ACT -> (tRCD) -> CAS ; cell "
       "occupied (bank_rdy=0) the whole sequence, only that bank's lane stalls.",
       size=11, mono=False, fill=INK)
f.text(X0, ly + 54, "ROW-CLOSE:  PRE / REF close the row -> MUST write FSM "
       "(state->IDLE, valid=0).  CAS is ROWLESS -> state is the ONLY guard ; a "
       "refresh-invalidated hit re-qualifies to MISS -> re-ACT.",
       size=11, mono=False, bold=True, fill="#c0392b")

f.caption(30, 748, "CMD_ARB: index by {bank state, packet vs open_row, "
                   "pre_pending} -> the gate says wait-or-go, the FIRE column is "
                   "the single bank_cmd sent to BGB_ARB, the ILLEGAL column is "
                   "blocked by construction (state-gated need_*).")

f.save("fig_23_cmd_arb_lut.svg")
print("wrote fig_23_cmd_arb_lut.svg")
