import json

els = []
eid = 1

def nid():
    global eid
    i = f"id-{eid}"
    eid += 1
    return i

def block(x, y, w, h, lines, bg, fg, fs, stroke):
    rid = nid()
    els.append({
        "id": rid, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "backgroundColor": bg, "strokeColor": stroke,
        "fillStyle": "solid", "strokeWidth": 2,
        "roughness": 0, "opacity": 100,
        "roundness": {"type": 3}, "version": 1,
        "isDeleted": False, "groupIds": [],
        "boundElements": [], "updated": 1,
        "link": None, "locked": False,
    })
    if isinstance(lines, str):
        lines = lines.split('\n')
    lh = fs * 1.35
    total = len(lines) * lh
    sy = y + (h - total) / 2
    for i, ln in enumerate(lines):
        els.append({
            "id": nid(), "type": "text",
            "x": x + 4, "y": sy + i * lh,
            "width": w - 8, "height": lh,
            "text": ln, "fontSize": fs,
            "fontFamily": 3, "textAlign": "center",
            "verticalAlign": "top",
            "strokeColor": fg, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1,
            "roughness": 0, "opacity": 100, "version": 1,
            "isDeleted": False, "groupIds": [],
            "boundElements": [], "updated": 1,
            "link": None, "locked": False,
            "containerId": None, "originalText": ln,
            "lineHeight": 1.25, "baseline": fs,
        })

def lbl(x, y, text, color, size=9):
    els.append({
        "id": nid(), "type": "text",
        "x": x, "y": y, "width": 400, "height": size*1.4,
        "text": text, "fontSize": size,
        "fontFamily": 3, "textAlign": "left",
        "verticalAlign": "top",
        "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1,
        "roughness": 0, "opacity": 100, "version": 1,
        "isDeleted": False, "groupIds": [],
        "boundElements": [], "updated": 1,
        "link": None, "locked": False,
        "containerId": None, "originalText": text,
        "lineHeight": 1.25, "baseline": size,
    })

def domain(x, y, w, h, label, stroke, bg):
    block(x, y, w, h, "", bg, stroke, 10, stroke)
    lbl(x+10, y+8, label, stroke, 10)

def arrow(pts, label="", color="#a6e3a1", lw=1.5):
    if len(pts) < 2: return
    x0, y0 = pts[0]
    rel = [[p[0]-x0, p[1]-y0] for p in pts]
    els.append({
        "id": nid(), "type": "arrow",
        "x": x0, "y": y0,
        "width": abs(rel[-1][0]), "height": abs(rel[-1][1]),
        "points": rel,
        "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": lw,
        "roughness": 0, "opacity": 85,
        "startArrowhead": None, "endArrowhead": "arrow",
        "version": 1, "isDeleted": False, "groupIds": [],
        "boundElements": [], "updated": 1,
        "link": None, "locked": False,
    })
    if label:
        mx = (pts[0][0]+pts[-1][0])/2
        my = (pts[0][1]+pts[-1][1])/2
        lbl(mx+3, my-11, label, color, 8)

# ═══════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════
S_AXI="#cba6f7"; B_AXI="#100a1e"
S_CIF="#89b4fa"; B_CIF="#080e20"
S_MC ="#89dceb"; B_MC ="#04060e"
S_FSM="#f38ba8"; B_FSM="#12040e"
S_ME ="#fab387"; B_ME ="#120c04"
S_SCH="#a6e3a1"; B_SCH="#040e04"
S_DFI="#f9e2af"; B_DFI="#10100a"
S_BUF="#cba6f7"; S_TCAM="#f38ba8"
FG="#cdd6f4"; GY="#6c7086"

# ═══════════════════════════════════════════════
# DIMENSIONS
# ═══════════════════════════════════════════════
BW=200  # block width
BH=90   # block height standard
TH=170  # table height (FSM tables)
MH=100  # ME sub-FSM height

# ── Column left edges ──
XA  = 30      # AXI
XC  = 280     # CIF
XB  = 560     # MC buffers / TCAM
XW  = 840     # MC watermark / RAW
XS  = 1130    # Scheduler
XF  = 1460    # FSM tables
XM  = 1760    # Maintenance Engine
XD  = 2060    # DFI / PHY

# ── Routing lanes (vertical hairlines between cols) ──
LA = XC - 20   # AXI→CIF
LC = XB - 20   # CIF→BUF
LB = XW - 20   # BUF→WAT
LW = XS - 20   # WAT→SCH
LS = XF - 20   # SCH→FSM
LF = XM - 20   # FSM→ME
LM = XD - 20   # ME→DFI

# ── Horizontal routing rows ──
GC_ROW = 45      # GC bus (top)
TOP_ME = 35      # ME→Scheduler bypass (above domains)
BOT1   = 980     # bottom lane 1 (resp path)
BOT2   = 995     # bottom lane 2 (credit returns)

# ═══════════════════════════════════════════════
# DOMAIN BACKGROUNDS
# ═══════════════════════════════════════════════
domain(XA-15, 60, 240, 960, "AXI DOMAIN",                   S_AXI, B_AXI)
domain(XC-15, 60, 250, 960, "CIF  (AXI CLK)",               S_CIF, B_CIF)
domain(XB-15, 60, 1050,960, "MC CORE  (MC CLK)  ——  all intra-MC = valid-credit", S_MC, B_MC)
domain(XS-15, 80, 310, 920, "SCHEDULER",                     S_SCH, "#030a03")
domain(XF-15, 80, 280, 920, "FSM TABLES",                    S_FSM, "#0a0208")
domain(XM-15, 60, 270, 960, "MAINTENANCE ENGINE  (6 sub-FSMs)", S_ME, B_ME)
domain(XD-15, 60, 250, 960, "DFI / PHY",                    S_DFI, B_DFI)

# ═══════════════════════════════════════════════
# AXI
# ═══════════════════════════════════════════════
block(XA+15, 100, BW, BH, ["AXI Masters","(N_CLIENTS)"], B_AXI, FG, 10, S_AXI)
block(XA+15, 220, BW, BH, ["AXI Interconnect"], B_AXI, FG, 10, S_AXI)

# ═══════════════════════════════════════════════
# CIF
# ═══════════════════════════════════════════════
block(XC+15, 100, BW, BH, ["AXI Write Port","valid-ready"], B_CIF, FG, 10, S_CIF)
block(XC+15, 210, BW, BH, ["AXI Read Port","valid-ready"],  B_CIF, FG, 10, S_CIF)
block(XC+15, 320, BW, BH, ["AMU","XOR hash + field extract","rank=MSB hashed, bg/bank/row/col raw"], B_CIF, FG, 9, S_CIF)
block(XC+15, 430, BW, BH, ["Burst Splitter","S1: row boundary","S2: BL alignment"], B_CIF, FG, 9, S_CIF)
block(XC+15, 540, BW, BH, ["ROB","{AXID, seqnum}"], B_CIF, FG, 10, S_CIF)
block(XC+15, 650, BW, BH, ["Merge Logic","fragment reassembly"], B_CIF, FG, 10, S_CIF)
block(XC+15, 780, BW, BH, ["Async REQ FIFO","CIF → MC","credit-based push","valid-credit read"], B_CIF, FG, 9, S_CIF)
block(XC+15, 890, BW, BH, ["Async RESP FIFO","MC → CIF","credit-based push","valid-credit read"], B_CIF, FG, 9, S_CIF)

# ═══════════════════════════════════════════════
# MC BUFFERS / TCAM column
# ═══════════════════════════════════════════════
block(XB+15, 100, BW, BH, ["Write Data Buffer","SRAM, index-addressed","NOT a FIFO"], B_MC, FG, 9, S_BUF)
block(XB+15, 210, BW, BH, ["WR_TCAM","search: {BG,bank,row,col}","no valid/ts in entry","gated by WR_status.valid"], B_MC, FG, 8, S_TCAM)
block(XB+15, 330, BW, BH, ["RD_TCAM","search: {BG,bank} ternary","row/col carried not matched","gated by RD_status.valid"], B_MC, FG, 8, S_TCAM)
block(XB+15, 450, BW, BH, ["WR Status Reg","[N_WR_ENTRIES]","valid | status | age","Owner: WR WM Mgr  Sched: RO"], B_MC, FG, 8, S_BUF)
block(XB+15, 570, BW, BH, ["RD Status Reg","[N_RD_ENTRIES]","valid | status | age | merge_pending","Owner: RD WM Mgr  Sched: RO"], B_MC, FG, 8, S_BUF)
block(XB+15, 690, BW, BH, ["Global Cycle Counter","GC_WIDTH free-running","never resets except SOFT_RESET"], B_MC, FG, 9, S_MC)
block(XB+15, 800, BW, BH, ["timing_reg_file","param_id → nCK value","cmd → timing_update_vector"], B_MC, FG, 9, S_MC)

# ═══════════════════════════════════════════════
# MC WATERMARK / RAW column
# ═══════════════════════════════════════════════
block(XW+15, 100, BW, BH, ["WR Watermark Mgr","Owns: WR_TCAM + WR_status_reg","Scheduler: READ ONLY"], B_MC, FG, 9, S_BUF)
block(XW+15, 220, BW, BH, ["RD Watermark Mgr","Owns: RD_TCAM + RD_status_reg","Scheduler: READ ONLY"], B_MC, FG, 9, S_BUF)
block(XW+15, 350, BW, BH, ["RAW Bypass Manager","Stage A: WR_TCAM exact match","Stage B: mask coverage check","hit valid: wr_age <= rd_age"], B_MC, FG, 8, S_TCAM)
block(XW+15, 470, BW, BH, ["Merge Unit","64×2:1 mux per byte","WDB + DRAM at return time","zero stall on partial hit"], B_MC, FG, 8, S_TCAM)
block(XW+15, 580, BW, BH, ["Hold-Forward 2-deep","src0 = RAW bypass","src1 = DRAM return","3rd collision impossible"], B_MC, FG, 9, S_BUF)
block(XW+15, 690, BW, BH, ["Bank Partition Ctrl","partition_reg | window_ctr","rd_mask | wr_mask","WINDOW_SIZE = 2×tREFI (CSR)"], B_MC, FG, 8, S_SCH)
block(XW+15, 800, BW, BH, ["Write Data Path","WL align | CRC | DFI timing"], B_MC, FG, 10, S_MC)
block(XW+15, 900, BW, BH, ["Read Data Path","latency ctr | cap FIFO | ECC","MRR sideband → MR_Poll FSM"], B_MC, FG, 9, S_MC)

# ═══════════════════════════════════════════════
# SCHEDULER
# ═══════════════════════════════════════════════
block(XS+15, 100, BW+60, BH, ["Stage 0  —  Maintenance Override","ref_urgent > ref_due > rfm_req > zq_due","bypass Stages 1-3 → Stage 4"], B_SCH, FG, 9, S_SCH)
block(XS+15, 215, BW+60, BH, ["Stage 1  —  TCAM Search","RD_TCAM + WR_TCAM hit_bitmap","metadata per bank  |  gated by status.valid"], B_SCH, FG, 9, S_SCH)
block(XS+15, 330, BW+60, BH, ["Stage 2  —  can_* Gate Check + SJF Cost","reads registered can_* flags only (no subtractor)","partition mask  |  speculative ACT detect"], B_SCH, FG, 9, S_SCH)
block(XS+15, 450, BW+60, 100, ["Stage 3  —  SJF Winner Selection","priority: S0-override > starved-miss > hit-set > miss-set","starvation: age >= THR + entry_idx (1 fires/cycle)","RD_STARVATION=12480  WR_STARVATION=37440"], B_SCH, FG, 9, S_SCH)
block(XS+15, 575, BW+60, BH, ["Stage 4  —  Cmd Emission + Writebacks","→ DFI via ME DFI mux","→ Per-Bank / Global Timing / Per-Rank tables"], B_SCH, FG, 9, S_SCH)
block(XS+15, 690, BW+60, BH, ["NOP Cycle Priority","1.  Opportunity REFsb","2.  Speculative prefetch ACT","3.  WR partition drain"], B_SCH, FG, 9, S_SCH)
block(XS+15, 800, BW+60, BH, ["Bank Pipeline + Partition Policy","ACT→diff BG→ACT→CAS  (tRRD_S < tRRD_L)","RD half / WR half  rotate WINDOW_SIZE","no tRTW or tWTR within partition window"], B_SCH, FG, 8, S_SCH)

# ═══════════════════════════════════════════════
# FSM TABLES
# ═══════════════════════════════════════════════
block(XF+15, 100, BW+40, TH, ["Per-Bank FSM Table","[N_RANKS × 16]","─────────────────","state (3b)  |  row_open","next_cas / next_pre","next_act / next_ref","can_cas / can_pre","can_act / can_ref  ← registered","ref_pending"], B_FSM, FG, 8, S_FSM)
block(XF+15, 290, BW+40, TH, ["Per-Rank FSM Table","[N_RANKS]","─────────────────","state (3b)  |  gate_rfc  |  gate_zq","ref_credits  |  raa[16]","next_* / can_* (all 4)","last_TUF  |  next_poll_gc","last_refsb_gc[32]"], B_FSM, FG, 8, S_FSM)
block(XF+15, 480, BW+40, TH, ["Global Timing Table","[1 instance]","─────────────────","next_act/cas_any","faw_window[FAW_DEPTH]","next_act/cas/wtr per BG","next_act/cas per rank","can_* for all  ← registered"], B_FSM, FG, 8, S_FSM)
block(XF+15, 675, BW+40, BH, ["Bank Act Counter","[N_RANKS × 16]","count  |  dirty"], B_FSM, FG, 9, S_FSM)
block(XF+15, 800, BW+40, BH, ["Error Handler","scheduler_err + DFI alerts","dfi_alert_n monitor"], B_FSM, FG, 9, S_FSM)

# ═══════════════════════════════════════════════
# MAINTENANCE ENGINE
# ═══════════════════════════════════════════════
block(XM+15, 100, BW, MH, ["1.  Init FSM","16 states  DDR5 POR","MRW / ZQCAL / TRAINING","owns DFI until init_done"], B_ME, FG, 8, S_ME)
block(XM+15, 220, BW, MH, ["2.  Refresh FSM","6 states  leaky-bucket","REFab / REFsb / FGR","Opportunity REFsb on NOP","last_refsb_gc[32] watchdog"], B_ME, FG, 8, S_ME)
block(XM+15, 345, BW, MH, ["3.  ZQcal FSM","7 states  per-rank","MPC ZQCAL Start → Latch","gate_zq during calibration"], B_ME, FG, 8, S_ME)
block(XM+15, 465, BW, MH, ["4.  RFM FSM","6 states","RAA[rank][bank] counters","+1 per ACT  -RAADec per REF","raa <= RAAIMT → RFM"], B_ME, FG, 8, S_ME)
block(XM+15, 585, BW, MH, ["5.  Power Mgmt FSM","10 states  PD + SR branches","PD entry: bank_act.count==0","SR: system-level trigger"], B_ME, FG, 8, S_ME)
block(XM+15, 705, BW, MH, ["6.  MR_Poll FSM","6 states","Periodic MR4 TUF read","TUF=1 → tREFI / 2  (>85°C)","MRR sideband from Rd Data Path"], B_ME, FG, 8, S_ME)
block(XM+15, 840, BW, BH, ["DFI Output Mux","init_done=0  →  Init FSM drives DFI","init_done=1  →  Scheduler drives DFI","one-way latch"], B_ME, FG, 8, S_ME)

# ═══════════════════════════════════════════════
# DFI / PHY
# ═══════════════════════════════════════════════
block(XD+15, 520, BW, BH, ["DDR PHY","DFI 5.2"], B_DFI, FG, 11, S_DFI)
block(XD+15, 650, BW, BH, ["DDR5 DRAM"], B_DFI, FG, 11, S_DFI)

# ═══════════════════════════════════════════════
# ARROWS — strict orthogonal, grouped by function
# ═══════════════════════════════════════════════
SW2 = XS+15+BW+60+15   # right edge of scheduler blocks
FW2 = XF+15+BW+40+15   # right edge of FSM table blocks

# ── A: AXI chain ────────────────────────────────────────────────
arrow([[XA+115,190],[XA+115,220]], "", S_AXI)
arrow([[XA+115,310],[LA,310],[LA,145],[XC+15,145]], "AXI4 valid-ready", S_AXI, 2)
arrow([[XA+115,310],[LA,310],[LA,255],[XC+15,255]], "", S_AXI, 2)

# ── B: CIF internal chain ───────────────────────────────────────
arrow([[XC+115,190],[XC+115,210]], "", S_CIF)
arrow([[XC+115,300],[XC+115,320]], "", S_CIF)
arrow([[XC+115,410],[XC+115,430]], "", S_CIF)
arrow([[XC+115,520],[XC+115,540]], "", S_CIF)
arrow([[XC+115,630],[XC+115,650]], "", S_CIF)
arrow([[XC+115,740],[XC+115,780]], "valid-credit", S_CIF)

# ── C: Async REQ FIFO → WR Watermark Mgr (credit-based CDC) ────
# goes right via y=780 midpoint lane
arrow([[XC+215,825],[LC,825],[LC,145],[XW+15,145]], "credit-based CDC  →", S_DFI, 2)

# ── D: WR Watermark Mgr → WR_TCAM + WR_status ──────────────────
# goes left from WR WM
arrow([[XW+15,145],[LB,145],[LB,255],[XB+215,255]], "", S_BUF)
arrow([[XW+15,150],[LB-5,150],[LB-5,495],[XB+215,495]], "", S_BUF)

# ── E: RD Watermark Mgr → RD_TCAM + RD_status ──────────────────
arrow([[XW+15,265],[LB-10,265],[LB-10,375],[XB+215,375]], "", S_BUF)
arrow([[XW+15,260],[LB-15,260],[LB-15,615],[XB+215,615]], "", S_BUF)

# ── F: WR_TCAM → RAW Bypass (hit vector) ────────────────────────
arrow([[XB+215,255],[LB+5,255],[LB+5,395],[XW+15,395]], "hit vector", S_TCAM)

# ── G: RD_TCAM → Stage 1 (TCAM hit bitmap) ──────────────────────
# horizontal at y=375 → right to scheduler
arrow([[XB+215,375],[LW,375],[LW,260],[XS+15,260]], "hit_bitmap + meta  →  S1", S_SCH, 2)

# WR_TCAM also goes to Stage 1
arrow([[XB+215,260],[LW-8,260],[LW-8,240],[XS+15,240]], "", S_SCH)

# ── H: Status age → Stage 3 (read-only, dedicated lane) ─────────
arrow([[XB+215,495],[LW-16,495],[LW-16,475],[XS+15,475]], "WR age → S3", GY)
arrow([[XB+215,615],[LW-24,615],[LW-24,490],[XS+15,490]], "RD age → S3", GY)

# ── I: Bank Act Counter → Stage 2 ───────────────────────────────
arrow([[XB+215,735],[LW-32,735],[LW-32,370],[XS+15,370]], "count → S2", GY)

# ── J: Bank Act Counter → ME Refresh (argmin for REFsb) ─────────
arrow([[XB+215,735],[LF,735],[LF,265],[XM+15,265]], "count → argmin", S_ME)

# ── K: GC bus — horizontal at GC_ROW ────────────────────────────
# GC → FSM tables (main consumer)
arrow([[XB+115,690],[XB+115,GC_ROW],[XF+115,GC_ROW],[XF+115,100]], "gc (GC_WIDTH)", S_MC, 2)

# ── L: timing_reg → Stage 4 ─────────────────────────────────────
arrow([[XB+215,845],[LW-40,845],[LW-40,620],[XS+15,620]], "timing params → S4", S_MC)

# ── M: RAW → Merge Unit ─────────────────────────────────────────
arrow([[XW+115,440],[XW+115,470]], "", S_TCAM)

# ── N: Merge → Hold-Forward ─────────────────────────────────────
arrow([[XW+115,560],[XW+115,580]], "", S_BUF)

# ── O: Hold-Forward → Resp FIFO (goes left via bottom lane) ─────
arrow([[XW+115,670],[XW+115,BOT1],[LC-5,BOT1],[LC-5,935],[XC+215,935]], "resp packet", S_BUF, 2)

# ── P: Resp FIFO → CIF output ───────────────────────────────────
arrow([[XC+115,890],[XC+115,870]], "valid-credit ↑", S_CIF)

# ── Q: Credit returns (CDC, dedicated lanes) ─────────────────────
# REQ credit return: MC→CIF  (y=BOT2 lane)
arrow([[XW+15,145],[LC-10,145],[LC-10,BOT2],[XC+215,BOT2],[XC+215,825]], "credit_return MC→CIF", S_DFI)
# RESP credit return: CIF→MC
arrow([[XC+215,945],[LC-15,945],[LC-15,BOT2+10],[XW+15,BOT2+10],[XW+15,670]], "credit_return CIF→MC", S_DFI)

# ── R: Bank Partition → Stage 2 ─────────────────────────────────
arrow([[XW+215,735],[LW-48,735],[LW-48,375],[XS+15,375]], "rd/wr mask → S2", S_SCH)

# ── S: Scheduler stage chain (vertical) ─────────────────────────
arrow([[XS+145,190],[XS+145,215]], "", S_SCH)
arrow([[XS+145,305],[XS+145,330]], "", S_SCH)
arrow([[XS+145,420],[XS+145,450]], "", S_SCH)
arrow([[XS+145,550],[XS+145,575]], "", S_SCH)

# ── T: Stage 4 writebacks → FSM tables (right lanes) ────────────
# S4 → Per-Bank FSM
arrow([[SW2,615],[LS,615],[LS,185],[XF+15,185]], "state,next_*,row_open", S_FSM, 2)
# S4 → Global Timing
arrow([[SW2,620],[LS-8,620],[LS-8,565],[XF+15,565]], "next_*_any,bg,rank,faw", S_FSM, 2)
# S4 → Per-Rank (raa_inc_en)
arrow([[SW2,625],[LS-16,625],[LS-16,375],[XF+15,375]], "raa_inc_en", S_ME)

# S4 status → back to status regs (ISSUED)
arrow([[XS+15,610],[LW-56,610],[LW-56,495],[XB+215,495]], "status → ISSUED", GY)

# ── U: FSM tables → Stage 2 (can_* read) — left lanes ───────────
# Per-Bank can_* → Stage 2
arrow([[XF+15,185],[LS-5,185],[LS-5,365],[SW2,365]], "can_cas/pre/act/ref → S2", S_FSM, 2)
# Global Timing can_* → Stage 2
arrow([[XF+15,565],[LS-13,565],[LS-13,380],[SW2,380]], "can_*_any/bg/rank/faw → S2", S_FSM, 2)
# Per-Rank gate_rfc/zq → Stage 0
arrow([[XF+15,375],[LS-20,375],[LS-20,145],[SW2,145]], "gate_rfc/zq → S0", S_ME)

# ── V: ME → Stage 0 (top bypass lane) ───────────────────────────
arrow([[XM+115,265],[LF,265],[LF,TOP_ME],[XS+115,TOP_ME],[XS+115,100]], "ref_urgent/due  zq_due  rfm_req  →  S0", S_ME, 2)

# ── W: ME → Per-Bank FSM (ref_pending) ──────────────────────────
arrow([[XM+15,265],[LF-8,265],[LF-8,185],[FW2,185]], "ref_pending set/clr", S_ME)

# ── X: ME → Per-Rank FSM ─────────────────────────────────────────
arrow([[XM+15,380],[FW2,380]], "gate_rfc/zq  ref_credits\nnext_trefi  last_TUF", S_ME)

# ── Y: Sched ack → ME ────────────────────────────────────────────
arrow([[SW2,610],[LF-16,610],[LF-16,265],[XM+15,265]], "sched_ack", S_SCH)

# ── Z: Stage 4 → DFI mux ─────────────────────────────────────────
arrow([[SW2,620],[LF-24,620],[LF-24,885],[XM+15,885]], "sched_dfi_*", S_DFI, 2)

# ── AA: DFI mux → PHY ────────────────────────────────────────────
arrow([[XM+215,885],[LM,885],[LM,565],[XD+15,565]], "DFI 5.2 cmds", S_DFI, 2)

# ── AB: Init FSM → DFI mux (inside ME, vertical) ─────────────────
arrow([[XM+115,200],[XM+115,840]], "init_dfi_*", S_ME)

# ── AC: Write Data Path → PHY ────────────────────────────────────
arrow([[XW+215,845],[LM-8,845],[LM-8,575],[XD+15,575]], "wrdata/en/mask", S_DFI)

# ── AD: PHY → Read Data Path (rddata_valid) ──────────────────────
arrow([[XD+15,590],[LM-16,590],[LM-16,945],[XW+115,945],[XW+115,990],[XW+115,900]], "rddata_valid ←", S_DFI)

# ── AE: DRAM return → Hold-Forward ───────────────────────────────
arrow([[XW+115,900],[XW+115,670]], "DRAM return ↑", S_BUF)

# ── AF: Read Data Path → MR_Poll sideband ────────────────────────
arrow([[XW+215,945],[LF-32,945],[LF-32,750],[XM+15,750]], "MRR sideband", S_ME)

# ── AG: Stage 4 → Write/Read Data Paths ──────────────────────────
arrow([[XS+15,610],[LW-64,610],[LW-64,845],[XW+215,845]], "wr cmd → WDP", S_MC)
arrow([[XS+15,615],[LW-72,615],[LW-72,945],[XW+15,945]], "rd cmd → RDP", S_MC)

# ── AH: PHY → DRAM ───────────────────────────────────────────────
arrow([[XD+115,610],[XD+115,650]], "", S_DFI, 2)

# ── AI: Error handler → alert ────────────────────────────────────
arrow([[XF+215,845],[LM-24,845],[LM-24,590],[XD+15,590]], "dfi_alert_n", S_FSM)

# ═══════════════════════════════════════════════
# LEGEND
# ═══════════════════════════════════════════════
LY = 1010
lbl(30,  LY,    "SIGNAL KEY:", FG, 10)
lbl(30,  LY+18, "━━  AXI valid-ready",            S_AXI, 9)
lbl(220, LY+18, "━━  valid-credit (intra-MC)",    S_SCH, 9)
lbl(450, LY+18, "━━  credit-based CDC",           S_DFI, 9)
lbl(650, LY+18, "━━  FSM table writeback",        S_FSM, 9)
lbl(870, LY+18, "━━  ME signals",                 S_ME,  9)
lbl(1060,LY+18, "━━  read-only / metadata",       GY,    9)
lbl(30,  LY+34, "NOP priority:  1. Opportunity REFsb   2. Speculative prefetch ACT   3. WR partition drain   4. true NOP", GY, 9)
lbl(30,  LY+48, "RMC v1.9.8  ——  all widths parameterized  ——  ME: 6 sub-FSMs  ——  Bank Partition RD/WR  ——  can_* registered flags", GY, 9)

# ═══════════════════════════════════════════════
doc = {
    "type": "excalidraw", "version": 2,
    "source": "rmc-v1.9.8",
    "elements": els,
    "appState": {
        "gridSize": 20,
        "viewBackgroundColor": "#05050c",
    },
    "files": {}
}

with open('RMC_Architecture_v10.excalidraw', 'w') as f:
    json.dump(doc, f, indent=2)

print(f"generated {len(els)} elements")
