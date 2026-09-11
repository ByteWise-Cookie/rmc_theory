from rtlfig import (Fig, MUTED, FILL_ACTIVE, FILL_NEW, FILL_CELL,
                    FILL_LOGIC, FAINT, INK, PAPER, W_CELL)

# fig_28 — every command's READY path to the scheduler.
# Two domains: DEMAND (cas/act/pre) through the per-bank arb tree; MAINTENANCE
# (ref/rfm/zq/mrw/mrr/init) bypass the tree and override-inject at the phaser.
# Invariant: demand = fair selection in the tree; maint = priority override.

f = Fig(1200, 1000)
RED = "#c0392b"


def cell(x, y, s, size=11, bold=False, fill=INK, mono=False):
    f.text(x, y, s, size=size, mono=mono, bold=bold, fill=fill)


# ---------------- header ----------------
cell(40, 38, "Every command's ready-path to the scheduler", 15, True)
f.note(40, 58, "DEMAND (cas/act/pre) go through the per-bank arb tree; everything "
               "else is engine-sourced and override-injects at the phaser.")

# ---------------- table ----------------
CX = [55, 250, 420, 600, 760, 1000]   # column x
hy = 96
for x, h in zip(CX, ["COMMAND", "ready signal", "source", "scope",
                     "path to scheduler", "gate"]):
    cell(x, hy, h, 12, True)
f.line(40, 106, 1160, 106, stroke=FAINT)

ROWS = [
    ("group", "DEMAND  -  packet-sourced, per-bank contention  ->  arb tree"),
    ("RD / WR / MWR", "cas_rdy", "cas_path cell", "bank",
     "tree -> cas lane -> L3", "can_cas & dqFree", False),
    ("ACT", "act_rdy", "act_path cell", "bank",
     "tree -> act lane -> L3", "can_act", False),
    ("PRE  (demand)", "pre_rdy", "act_path head", "bank",
     "tree -> pre lane -> L3", "can_pre (tRAS/tRTP/tWR)", False),
    ("group", "MAINTENANCE / CONFIG  -  engine-sourced, rank/device scope  ->  override inject (NO tree)"),
    ("REFsb / REFab", "ref_rdy", "REFRESH eng (per rank)", "8-bank / rank",
     "inject override", "gate_rfc; sets REF_pending", True),
    ("PREsb / PREab", "(ref substep)", "REFRESH eng", "8-bank / rank",
     "rides ref handshake (drain)", "-", True),
    ("RFM", "rfm_rdy", "RFM eng (per rank)", "BG / rank",
     "inject override", "raa_count >= thresh", True),
    ("ZQCAL", "zq_rdy", "ZQ eng", "rank / channel",
     "inject override (solo)", "tZQ ; caFree", True),
    ("MRW", "mrw_rdy", "MRW eng", "device",
     "inject override (solo)", "caFree", True),
    ("MRR", "mrr_rdy", "MRR eng", "device (DQ)",
     "inject override (solo)", "dqFree  (uses DQ!)", True),
    ("INIT", "init_rdy", "INIT FSM", "device",
     "drives DFI mux till init_done", "init_done handoff", True),
    ("MPC / SRE.SRX / PDE.PDX", "state", "power FSM", "rank / device",
     "DFI state / inject", "-", True),
]

y = 126
for r in ROWS:
    if r[0] == "group":
        cell(48, y + 4, r[1], 12, True, MUTED)
        f.line(40, y + 12, 1160, y + 12, stroke=FAINT)
        y += 32
        continue
    name, rdy, src, scope, path, gate, maint = r
    cell(CX[0], y, name, 12, mono=True)
    cell(CX[1], y, rdy, 12, mono=True, fill=(MUTED if rdy.startswith("(") or rdy == "state" else INK))
    cell(CX[2], y, src, 11, fill=MUTED)
    cell(CX[3], y, scope, 11, fill=MUTED)
    cell(CX[4], y, path, 11, fill=(RED if "override" in path else INK))
    cell(CX[5], y, gate, 11, fill=MUTED)
    y += 32

# ================= schematic (2 domains -> phaser) =================
sy = y + 20
f.line(40, sy - 8, 1160, sy - 8, stroke=FAINT)
cell(48, sy + 6, "the two domains merge at the phaser", 12, True)

# --- DEMAND block ---
db = f.logic(60, sy + 24, 380, 150, "DEMAND", top=True)
cell(78, sy + 62, "cas_rdy  act_rdy  pre_rdy", 11, mono=True)
f.line(250, sy + 72, 250, sy + 90, arrow=True)
f.logic(110, sy + 90, 280, 42, "per-bank arb tree", "CMD > BGB > BG > RANK")
f.line(250, sy + 132, 250, sy + 150, arrow=True)
cell(250 - 90, sy + 166, "best_cas/act/pre[r]  ->  L3", 11, mono=True)

# --- MAINT block ---
mb = f.logic(620, sy + 24, 480, 150, "MAINTENANCE", top=True)
cell(638, sy + 60, "init/ref/rfm/zq/mrw/mrr _rdy", 11, mono=True)
f.line(760, sy + 70, 760, sy + 90, arrow=True)
f.logic(640, sy + 90, 440, 42, "PRIORITY_SELECT",
        "init > ref_urgent > rfm > ref_due > zq > mrw/mrr")
f.line(860, sy + 132, 860, sy + 150, arrow=True)
cell(860 - 70, sy + 166, "maint_cmd (OVERRIDE)", 11, mono=True, fill=RED)

# --- PHASER ---
py = sy + 190
pb = f.logic(360, py, 420, 54, "PHASE PACKER", "override > demand : maint preempts, demand spills")
f.path(f"M250 {sy+178} V{py-8} H430 V{py}", arrow=True)   # demand into phaser
f.path(f"M860 {sy+178} V{py-8} H710 V{py}", arrow=True)   # maint into phaser
f.line(570, py + 54, 570, py + 80, arrow=True)
cell(570 + 12, py + 74, "->  DFI / PHY / DRAM", 12)

f.caption(40, py + 108,
          "Demand = fair selection through the per-bank tree. Maintenance bypasses "
          "the tree, priority-selects one winner, override-injects at the phaser.")
f.caption(40, py + 126,
          "Same skeleton for all maint cmds; MRR still pays dqFree, refresh sets gate_rfc.")

f.save("fig_28_ready_paths.svg")
print("wrote fig_28_ready_paths.svg")
