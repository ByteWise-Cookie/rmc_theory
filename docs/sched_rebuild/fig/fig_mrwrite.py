from rtlfig import Fig, MUTED, FILL_LOGIC, FILL_NEW, FILL_CELL, FAINT, INK, W_CELL, Rect

BW, BH = 155, 48


def box(f, x, y, name, fill=FILL_LOGIC, dashed=False):
    f.rect(x, y, BW, BH, fill=fill, width=W_CELL, rx=8, dashed=dashed)
    f.text(x + BW / 2, y + BH / 2 + 5, name, size=10, anchor="middle")


# ============ fig_45 — MR_Write state diagram (9 states, 2 optional) ============
def state_fig():
    states = [
        ("IDLE", "init_done", False), ("WAIT_REQ", "mr_wr_req", False),
        ("GATE_CHECK", "gate_pwr==0 & idle?", False),
        ("ISSUE_MRW", "sched_ack", False), ("WAIT_tMRD", "T_MRD", False),
        ("VERIFY_MRR", "arb grant+ack", True), ("WAIT_RDDATA", "mrr_data_valid", True),
        ("CHECK_MATCH", "cmp -> mr_wr_error", True),
        ("APPLY_TIMING", "commit staged", True), ("DONE", "-> IDLE", False),
    ]
    dx = 176
    W = 60 + len(states) * dx
    f = Fig(W, 360)
    f.text(40, 40, "MR_WRITE FSM (9 states; dashed = conditional)", size=15,
           mono=False, bold=True)
    f.note(40, 60, "software MR write via CSR. VERIFY_MRR..CHECK_MATCH run if "
                   "VERIFY|AFFECTS_TIMING; APPLY_TIMING runs if AFFECTS_TIMING.")
    y = 180
    xs = []
    for i, (nm, lbl, cond) in enumerate(states):
        x = 60 + i * dx
        xs.append(x)
        fill = FILL_NEW if i == 0 else (FILL_CELL if nm == "DONE" else FILL_LOGIC)
        box(f, x, y, nm, fill, dashed=cond)
        if i > 0:
            f.line(xs[i - 1] + BW, y + BH / 2, x, y + BH / 2, arrow=True)
            f.text((xs[i - 1] + BW + x) / 2, y + BH / 2 - 8, states[i - 1][1],
                   size=8, mono=False, anchor="middle", fill=MUTED)
    # skip arcs (above)
    f.path(f"M{xs[4]+BW/2} {y} C{xs[4]+BW/2} 110 {xs[9]+BW/2} 110 {xs[9]+BW/2} {y}",
           arrow=True, dashed=True)
    f.text((xs[4] + xs[9]) / 2 + BW / 2, 104, "!VERIFY & !AFFECTS_TIMING (skip)",
           size=9, mono=False, anchor="middle", fill=MUTED)
    f.path(f"M{xs[7]+BW/2} {y} C{xs[7]+BW/2} 138 {xs[9]+BW/2} 138 {xs[9]+BW/2} {y}",
           arrow=True, dashed=True)
    f.text((xs[7] + xs[9]) / 2 + BW / 2, 132, "!AFFECTS_TIMING (skip apply)",
           size=9, mono=False, anchor="middle", fill=MUTED)
    # back to IDLE
    f.path(f"M{xs[9]+BW/2} {y+BH} V300 H{xs[0]+BW/2} V{y+BH}", arrow=True, dashed=True)
    f.text((xs[0] + xs[9]) / 2, 314, "DONE -> IDLE", size=9, mono=False,
           anchor="middle", fill=MUTED)
    f.save("fig_45_mrwrite.svg")
    print("wrote fig_45_mrwrite.svg")


# ============ fig_46 — MR_Write block logic ============
def block_fig():
    ins = ["init_done", "mr_wr_req (CSR pulse)",
           "MR_WR_* fields (CSR req)",
           "gate_pwr[rank]", "bank_act_count", "gc / T_MRD", "sched_ack",
           "mrr_* (sideband, arb-tagged)",
           "mrr_slot_grant_write (arbiter)"]
    outs = ["mr_write_req (Stage-0 bypass)", "me_cmd{valid,type=MRW,rank}",
            "mr_wr_addr / mr_wr_data -> dfi", "set/clr gate_mr[rank]",
            "timing_apply_en -> timing_reg_file", "mr_wr_busy / done / error",
            "MR-read-arbiter request"]
    logic = ["1 outstanding SW MR write (per-request CSR fields)",
             "GATE_CHECK: gate_pwr==0 & (REQUIRE_IDLE ? banks idle)",
             "ISSUE via Stage-0 -> gate_mr for T_MRD",
             "opt VERIFY: MRR read-back, CHECK_MATCH -> mr_wr_error",
             "opt APPLY_TIMING: commit staged value (single-entry)",
             "shares MR Read Arbiter with MR_Poll"]
    n = max(len(ins), len(outs))
    BX, BBW = 340, 360
    y0, dy = 150, 38
    bh = max(n * dy + 24, len(logic) * 20 + 70)
    W, H = 1040, 120 + bh + 60
    f = Fig(W, H)
    f.text(40, 40, "MR_WRITE FSM - block logic", size=15, mono=False, bold=True)
    f.note(40, 60, "inputs left -> block (internal logic) -> outputs right.")
    f.rect(BX, 120, BBW, bh, fill=FILL_NEW, width=W_CELL)
    b = Rect(BX, 120, BBW, bh)
    f.text(b.cx, 142, "MR_WRITE FSM", size=13, anchor="middle", bold=True)
    for i, ln in enumerate(logic):
        f.text(BX + 12, 168 + i * 20, ln, size=10, mono=False, fill=MUTED)
    for i, nm in enumerate(ins):
        f.port_in(40, b, y0 + i * dy, nm)
    for i, nm in enumerate(outs):
        f.port_out(b, W - 40, y0 + i * dy, nm)
    f.save("fig_46_mrwrite_blk.svg")
    print("wrote fig_46_mrwrite_blk.svg")


state_fig()
block_fig()
