from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_61 — bank timestamp datapath v2 (user's vertical topology + all fixes):
#  GC 24b (+=gear) -> +phase_off -> GC_ph ; 6-wide const -> const_sel(op_code) -> tc_* ;
#  3 adders -> {bg,bank} write-route (one-hot WE + field mask) -> x32 {vld,ts} cells ;
#  compare GC[12:0]>=ts -> SET ; issue-decode -> RST (reset-dominant) ; can_cas ANDs vld.

CMP = "#2a8f86"
ISSUE = "#7a4fb0"
GREEN = "#3d8c40"

f = Fig(1180, 1180)
COLS = {"pre": 430, "cas": 660, "act": 890}


def addr(cx, cy, r=20):
    f.counter(cx, cy, r, "+", "")
    f.text(cx, cy + 4, "+", size=13, anchor="middle", bold=True)


f.text(40, 32, "Bank timestamp datapath v2  (all fixes)", size=15, mono=False, bold=True)

# ---------- bottom: grant + ctl ----------
f.block(40, 1090, 320, 56, "r0  GRANT", "{cmd, bank, bg, ph_off, row}")
f.block(430, 1090, 260, 56, "FEEDBACK_CTL", "cmd -> op_code")
f.line(360, 1118, 428, 1118, arrow=True)

# ---------- const store + select ----------
f.block(40, 980, 320, 70, "TIME_CONST_REGS (bank)",
        "6x8b: tRC tRCD tRAS tRTP tRP WR_TAIL")
f.text(48, 1062, "flat, all outputs wired (no read port); cfg/freq-FSM writable",
       size=8, mono=False, fill=MUTED)
f.logic(410, 975, 540, 80, "const_sel  (op_code)", "was bit_field_offset", top=True)
f.line(360, 1010, 408, 1010, arrow=True)               # const -> sel
f.path("M560 1090 V1057", arrow=True, stroke=MUTED)     # op_code up into sel
f.text(568, 1075, "op_code", size=8, mono=True, fill=MUTED)

# ---------- GC + phase_off ----------
f.block(40, 855, 320, 60, "global_counter_24b", "count <= count + gear")
f.text(48, 930, "compare low 13b GC[12:0]  .  wide GC[23:0] -> refresh",
       size=8, mono=False, fill=MUTED)
addr(410, 885)
f.line(360, 885, 388, 885, arrow=True)
f.text(430, 862, "+ph_off", size=8, mono=True, fill=MUTED)
f.line(410, 862, 410, 848, arrow=True)
f.text(415, 845, "phase_off", size=8, mono=True, fill=MUTED)
# GC_ph rail
f.path("M432 885 H980 V820", arrow=False, stroke=GREEN)
f.text(760, 878, "GC_ph -> all adders + (13b) all compares", size=8, mono=False, fill=GREEN)

# ---------- adders per field ----------
ADDY = 800
for k, cx in COLS.items():
    addr(cx, ADDY)
    f.line(cx, 975, cx, ADDY + 20, arrow=True)           # tc_* from const_sel up
    f.text(cx + 8, 950, f"tc_{k}", size=9, mono=True, fill=INK)
    f.line(980 if False else cx, 820, cx, ADDY + 20, arrow=False)  # GC_ph tap
# GC_ph vertical taps
for cx in COLS.values():
    f.line(cx - 40, 820, cx - 6, ADDY - 6, arrow=True, stroke=GREEN)

# ---------- write route ({bg,bank} WE + field mask) ----------
WY = 690
for k, cx in COLS.items():
    # DEMUX: narrow input (adder, bottom) -> wide output (N cells, top)
    f.path(f"M{cx-26} {WY+34} L{cx+26} {WY+34} L{cx+46} {WY} L{cx-46} {WY} Z",
           arrow=False, stroke=INK)
    f.line(cx, ADDY - 20, cx, WY + 34, arrow=True)        # adder sum up into demux
f.text(300, WY + 8, "{bg,bank} ->", size=9, mono=True, fill=ISSUE)
f.line(395, WY + 5, COLS["pre"] - 36, WY + 5, arrow=True, stroke=ISSUE)
f.text(150, WY + 60, "write DEMUX = 1 adder -> 1 of 32 (one-hot WE + field mask[cmd], bcast D)",
       size=8, mono=False, fill=ISSUE)

# ---------- cell arrays ----------
CY = 470
for k, cx in COLS.items():
    f.rect(cx - 26, CY, 52, 150, fill=PAPER, width=W_CELL)
    f.text(cx, CY + 70, "t*", size=11, anchor="middle", bold=True)
    f.text(cx, CY + 90, "vld", size=10, anchor="middle")
    f.line(cx, WY, cx, CY + 150, arrow=True)              # mux -> cell
    f.rect(cx + 40, CY + 10, 40, 130, fill=PAPER, width=1.0, stroke=FAINT)
    f.text(cx + 60, CY + 165, "....", size=12, anchor="middle", fill=MUTED)
f.text(985, CY + 20, "{vld, time_stamp}  x32 flops", size=9, mono=False, fill=MUTED)
f.text(985, CY + 38, "broadcast D, one-hot WE", size=8, mono=False, fill=MUTED)

# ---------- comparators ----------
GY = 380
for k, cx in COLS.items():
    f.counter(cx, GY, 22, ">=", "")
    f.line(cx, CY, cx, GY + 22, arrow=True)               # cell -> cmp
    f.text(cx - 44, GY + 4, "GC13", size=8, mono=True, fill=GREEN)
    f.line(cx - 60, GY, cx - 22, GY, arrow=True, stroke=GREEN)

# ---------- can flops ----------
KY = 230
labels = {"pre": "can_pre", "cas": "can_cas", "act": "can_act"}
for k, cx in COLS.items():
    f.rect(cx - 60, KY - 20, 120, 34, fill=FILL_NEW, width=W_CELL)
    f.text(cx, KY, labels[k], size=11, mono=True, anchor="middle")
    # SET from cmp
    f.line(cx + 10, GY - 22, cx + 10, KY + 14, arrow=True, stroke=CMP)
    f.text(cx + 15, 320, "set", size=8, fill=CMP)
    # RST from issue (reset-dominant, dashed loop)
    f.line(cx - 12, 640, cx - 12, KY + 14, arrow=True, stroke=ISSUE)
    f.text(cx - 34, 320, "rst", size=8, fill=ISSUE)
# can_cas vld AND
f.text(COLS["cas"] + 70, KY + 40, "can_cas.set &= vld (state==OPEN)",
       size=8, mono=True, fill=INK)
f.line(COLS["cas"] + 66, KY + 36, COLS["cas"] + 12, KY + 20, arrow=True, dashed=True)

# notes
f.text(40, 150, "RST = issue-decode (reset-dominant, beats coincident set).", size=9,
       mono=False, fill=ISSUE)
f.text(40, 168, "SET = GC[12:0] >= time_stamp (>=, never ==).", size=9, mono=False, fill=CMP)
f.text(40, 186, "2 control units / rank (CAS+ACT slots) -> 2 WE decodes, different banks.",
       size=9, mono=False, fill=MUTED)

f.caption(40, 1168,
          "GC 24b +=gear -> +phase_off -> GC_ph; const_sel routes 6 consts to tc_act/cas/pre by "
          "op_code; 3 adders -> {bg,bank} write-route (one-hot WE + field mask) into x32 {vld,ts} "
          "cells; each cell compares GC[12:0]>=ts -> SET, issue -> RST (reset-dominant). can_cas "
          "also ANDs vld(OPEN). Refresh reuses the wide GC[23:0].")

f.save("fig_61_bank_datapath_v2.svg")
print("wrote fig_61_bank_datapath_v2.svg")
