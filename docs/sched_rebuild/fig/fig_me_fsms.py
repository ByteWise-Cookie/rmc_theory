import math
from rtlfig import Fig, MUTED, FILL_LOGIC, FILL_NEW, FILL_CELL, FAINT, INK, W_CELL

# fig_33..38 — state diagrams for the six ME sub-FSMs (states lifted from
# rmc_knowledge_base / v1.9.10). One figure per FSM.

BW, BH, DX, DY, X0, Y0 = 158, 48, 210, 120, 60, 120


def box(f, x, y, name, fill=FILL_LOGIC):
    f.rect(x, y, BW, BH, fill=fill, width=W_CELL, rx=8)
    f.text(x + BW / 2, y + BH / 2 + 5, name, size=11, anchor="middle")


def fsm_linear(fname, title, states, cols=4, back=True, favicon=None):
    n = len(states)
    rows = math.ceil(n / cols)
    W = X0 + cols * DX + 20
    H = Y0 + rows * DY + 90
    f = Fig(W, H)
    f.text(40, 40, title, size=15, mono=False, bold=True)
    f.note(40, 60, "state -> state, arrow label = exit condition. dashed = loop back.")
    pos = []
    for i in range(n):
        r = i // cols
        c = i % cols
        col = c if r % 2 == 0 else (cols - 1 - c)
        x = X0 + col * DX
        y = Y0 + r * DY
        pos.append((x, y))
        fill = FILL_NEW if i == 0 else (FILL_CELL if i == n - 1 else FILL_LOGIC)
        box(f, x, y, states[i][0], fill)
    for i in range(n - 1):
        (x0, y0), (x1, y1) = pos[i], pos[i + 1]
        lbl = states[i][1]
        if y0 == y1:
            if x1 > x0:
                f.line(x0 + BW, y0 + BH / 2, x1, y1 + BH / 2, arrow=True)
                f.text((x0 + BW + x1) / 2, y0 + BH / 2 - 8, lbl, size=9,
                       mono=False, anchor="middle", fill=MUTED)
            else:
                f.line(x0, y0 + BH / 2, x1 + BW, y1 + BH / 2, arrow=True)
                f.text((x0 + x1 + BW) / 2, y0 + BH / 2 - 8, lbl, size=9,
                       mono=False, anchor="middle", fill=MUTED)
        else:
            f.line(x0 + BW / 2, y0 + BH, x1 + BW / 2, y1, arrow=True)
            f.text(x0 + BW / 2 + 8, (y0 + BH + y1) / 2 + 3, lbl, size=9,
                   mono=False, anchor="start", fill=MUTED)
    if back:
        (xl, yl) = pos[-1]
        (xf, yf) = pos[0]
        # dashed loop under everything back to state 0
        yb = Y0 + rows * DY - DY + BH + 40
        f.path(f"M{xl+BW/2} {yl+BH} V{yb} H{xf+BW/2} V{yf+BH}",
               arrow=True, dashed=True)
        f.text((xl + xf) / 2, yb + 14, states[-1][1] + "  -> loop", size=9,
               mono=False, anchor="middle", fill=MUTED)
    f.save(fname)
    print("wrote", fname)


# ---- fig_33 INIT (16) ----
fsm_linear("fig_33_init.svg", "INIT FSM (16 states) - DDR5 power-on sequence", [
    ("IDLE", "INIT_KICK"), ("ASSERT_RESET", "tINIT1 200us"),
    ("CS_PRE_DEASSERT", "tINIT2 10ns"), ("CS_POST_DEASSERT", "tINIT3 4ms"),
    ("ODT_SETTLE", "tINIT4 2us"), ("NOP_BURST", "tINIT5 3nCK"),
    ("WAIT_XPR", "tXPR"), ("MPC_DLL_DIVIDER", "issued"),
    ("MPC_DLL_RESET", "issued"), ("ZQCAL_START", "issued"),
    ("WAIT_tZQCAL", "1us"), ("ZQCAL_LATCH", "issued"),
    ("WAIT_tZQLAT", "30nCK"), ("MRW_BURST", "all MRs"),
    ("TRAINING", "TRAIN_EN"), ("DONE", "init_done (latch)"),
], cols=4, back=False)

# ---- fig_34 REFRESH (6) ----
fsm_linear("fig_34_refresh.svg", "REFRESH FSM (6 states)", [
    ("IDLE", "credit due"), ("REF_DUE", "target picked"),
    ("WAIT_BANKS_IDLE", "banks drained"), ("ISSUE_REF", "REFsb/ab sent"),
    ("WAIT_tRFC", "tRFC done"), ("DONE", "credit--"),
], cols=4)

# ---- fig_35 RFM (6) ----
fsm_linear("fig_35_rfm.svg", "RFM FSM (6 states) - row-hammer", [
    ("IDLE", "enable"), ("MONITOR_RAA", "RAA >= RAAIMT"),
    ("RFM_REQUEST", "rfm_req"), ("WAIT_ISSUE", "sched_ack"),
    ("WAIT_tRFM", "tRFM done"), ("UPDATE_RAA", "RAA -= RAAIMT"),
], cols=4)

# ---- fig_36 ZQCAL (7) ----
fsm_linear("fig_36_zqcal.svg", "ZQCAL FSM (7 states) - impedance cal", [
    ("IDLE", "zqcs due"), ("WAIT_IDLE", "bus idle"),
    ("ISSUE_ZQCAL_START", "sent"), ("WAIT_tZQCAL", "1us"),
    ("ISSUE_ZQCAL_LATCH", "sent"), ("WAIT_tZQLAT", "30nCK"),
    ("DONE", "next_zqcs++"),
], cols=4)

# ---- fig_37 MR_POLL (6) ----
fsm_linear("fig_37_mrpoll.svg", "MR_POLL FSM (6 states) - MR4 thermal", [
    ("IDLE", "start"), ("WAIT_INTERVAL", "gc>=next_poll"),
    ("REQUEST_MRR", "sched_ack"), ("WAIT_RDDATA", "mrr_data_valid"),
    ("PARSE_TUF", "TUF bit"), ("UPDATE_TREFI", "TUF=1 -> tREFI/2"),
], cols=4)


# ---- fig_38 POWER_MGMT (10) - branched ----
def fsm_power():
    f = Fig(1120, 780)
    f.text(40, 40, "POWER_MGMT FSM (10 states) - PD + SR branches", size=15,
           mono=False, bold=True)
    f.note(40, 60, "NORMAL branches to power-down (left) or self-refresh (right); "
                   "both return to NORMAL. arrow label = exit condition.")
    box(f, 461, 110, "NORMAL", FILL_NEW)          # x 461..619, center 540
    PDX, SRX = 250, 730

    def chain(x, entry_from_left, states):
        for i, (nm, lbl) in enumerate(states):
            y = 210 + i * 108
            box(f, x, y, nm)
            if i > 0:
                f.line(x + BW / 2, y - 108 + BH, x + BW / 2, y, arrow=True)
                f.text(x + BW / 2 + 8, y - 44, states[i - 1][1], size=9,
                       mono=False, anchor="start", fill=MUTED)
        return 210 + (len(states) - 1) * 108           # last-box y

    # PD entry + branch
    f.path(f"M500 158 V184 H{PDX+BW/2} V210", arrow=True)
    f.text(360, 178, "PD entry", size=9, mono=False, anchor="middle", fill=MUTED)
    pd_last = chain(PDX, True, [
        ("PD_ENTRY_CHECK", "all idle & pd_en"), ("PRECHARGE_PD", "cke<-0"),
        ("PDX_WAIT", "wake; gc>=+T_XP")])
    box(f, 40, 318, "ACTIVE_PD")
    f.text(140, 310, "(reserved, unreachable)", size=9, mono=False,
           anchor="middle", fill=MUTED)
    f.path(f"M{PDX} 342 H198", arrow=True, dashed=True)
    # PD return
    f.path(f"M{PDX+BW/2} {pd_last+BH} V700 H520 V158", arrow=True, dashed=True)
    f.text(400, 692, "PDX_WAIT exit -> NORMAL", size=9, mono=False, fill=MUTED)

    # SR entry + branch
    f.path(f"M580 158 V184 H{SRX+BW/2} V210", arrow=True)
    f.text(700, 178, "SR entry", size=9, mono=False, anchor="middle", fill=MUTED)
    sr_last = chain(SRX, False, [
        ("SR_ENTRY", "sr_entry; cke<-0"), ("WAIT_tCKSRE", "T_CKSRE"),
        ("SELF_REFRESHING", "sr_exit"), ("SR_EXIT", "cke<-1"),
        ("WAIT_tXS_tDLLK", "gc>=+T_XS+T_DLLK")])
    f.path(f"M{SRX+BW/2} {sr_last+BH} V720 H580 V158", arrow=True, dashed=True)
    f.text(660, 712, "WAIT_tXS_tDLLK -> NORMAL", size=9, mono=False, fill=MUTED)

    f.save("fig_38_power.svg")
    print("wrote fig_38_power.svg")


fsm_power()
