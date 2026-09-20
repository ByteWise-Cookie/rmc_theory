from rtlfig import Fig, MUTED, FILL_LOGIC, FILL_NEW, FAINT, INK, W_CELL


def draw_block(fname, title, ins, outs, logic, fill=FILL_LOGIC):
    n = max(len(ins), len(outs))
    BX, BW = 330, 340
    y0, dy = 150, 38
    bh = max(n * dy + 24, len(logic) * 20 + 70)
    W = 1000
    H = 120 + bh + 70
    f = Fig(W, H)
    f.text(40, 40, title, size=15, mono=False, bold=True)
    f.note(40, 60, "inputs left -> block (internal logic) -> outputs right.")
    blk = f.rect(BX, 120, BW, bh, fill=fill, width=W_CELL)
    from rtlfig import Rect
    b = Rect(BX, 120, BW, bh)
    f.text(b.cx, 120 + 22, title.split(" - ")[0].split(" (")[0], size=13,
           anchor="middle", bold=True)
    for i, ln in enumerate(logic):
        f.text(BX + 14, 120 + 50 + i * 20, ln, size=10, mono=False, fill=MUTED)
    for i, nm in enumerate(ins):
        f.port_in(40, b, y0 + i * dy, nm)
    for i, nm in enumerate(outs):
        f.port_out(b, W - 40, y0 + i * dy, nm)
    f.save(fname)
    print("wrote", fname)


# fig_39 REFRESH
draw_block("fig_39_refresh_blk.svg", "REFRESH FSM - block logic",
    ["gc", "next_trefi_out", "ref_credits_out", "bank_act_count", "all_idle",
     "sched_ack", "REF_MODE (CSR)"],
    ["ref_urgent", "ref_due", "me_cmd{valid,type,rank,bg,bank}",
     "set/clr_gate_rfc", "inc/dec_ref_credits", "update_next_trefi",
     "set/clr_ref_pending"],
    ["leaky bucket: +1/tREFI, -1/issued", "ref_urgent@8 credits, ref_due normal",
     "target = argmin(bank_act_count) + watchdog", "WAIT_BANKS_IDLE = drain",
     "REFsb / REFab per REF_MODE"])

# fig_40 ZQCAL
draw_block("fig_40_zqcal_blk.svg", "ZQCAL FSM - block logic",
    ["gc", "next_zqcs_out", "all_idle", "sched_ack"],
    ["zq_due", "me_cmd{valid,type,rank}", "set/clr_gate_zq", "update_next_zqcs"],
    ["next_zqcs compare -> zq_due", "2-step: START -> tZQCAL -> LATCH -> tZQLAT",
     "gate_zq gates the whole rank", "MPC-encoded ZQCAL"])

# fig_41 RFM
draw_block("fig_41_rfm_blk.svg", "RFM FSM - block logic",
    ["gc", "raa_out[rank][bank]", "RAAIMT (CSR)", "sched_ack",
     "raa_inc_en (from commit)"],
    ["rfm_req[rank][bank]", "me_cmd{valid,type,rank,bg,bank}",
     "raa_dec_en / raa_dec_val"],
    ["per-bank RAA: +raa_inc (ACT), -raa_dec_val (ref/rfm)",
     "RAA >= RAAIMT -> rfm_req", "issue RFMsb / RFMab", "row-hammer safety"])

# fig_42 POWER
draw_block("fig_42_power_blk.svg", "POWER_MGMT FSM - block logic",
    ["gc", "all_idle", "bank_act_count", "pd_en (CSR)", "sr_entry", "sr_exit",
     "can_xp_out", "can_xs_out", "sched_ack"],
    ["me_cmd{valid,type,rank}", "update_next_xp", "update_next_xs",
     "rank_state_update"],
    ["PD entry gate: all_idle & pd_en", "SR entry: sr_entry / exit: sr_exit",
     "CKE control (dfi_cke)", "T_XP / T_XS / T_DLLK timers",
     "rank_state_update broadcast to bank FSM"])

# fig_43 MR_POLL
draw_block("fig_43_mrpoll_blk.svg", "MR_POLL FSM - block logic",
    ["gc", "mrr_data_valid (sideband)", "mrr_data[8]", "mrr_rank",
     "MRR_POLL_INTERVAL (CSR)"],
    ["me_cmd{valid,type=MRR,mr=4,rank}", "update_next_poll_gc", "last_TUF",
     "tREFI_adjust -> REFRESH"],
    ["poll: gc >= next_poll_gc (32xtREFI)", "issue MRR to MR4",
     "PARSE_TUF from response", "TUF=1 (>85C) -> tREFI/2"], fill=FILL_NEW)

# fig_44 INIT
draw_block("fig_44_init_blk.svg", "INIT FSM - block logic",
    ["clk", "rst_n", "INIT_KICK (CSR)", "TRAIN_EN (CSR)", "gc",
     "timing_reg_vals (tINIT1..tDLLK)"],
    ["dfi_address[13:0]", "dfi_cs_n[1:0]", "dfi_act_n",
     "dfi_wrdata[127:0] (MRW)", "dfi_wrdata_en", "init_done (latch)",
     "global_state_req[2:0]"],
    ["16-state DDR5 power-on sequence", "tINIT1..tDLLK timers",
     "drives DFI RAW (pre-scheduler, DFI mux)", "init_done = one-way latch",
     "-> releases scheduler"], fill=FILL_NEW)
