from rtlfig import Fig, MUTED, FILL_ACTIVE

# fig_01 — ingress: per-rank split bp-FIFOs -> rank_arb (outer) -> wlr_sel (inner).
# Invariant: R and W stay split through rank_arb; wlr_sel is the single merge point.

f = Fig(1040, 600)

# ---------------- rank grouping labels ----------------
f.note(250, 52, "rank 0", anchor="middle")
f.note(780, 52, "rank 1", anchor="middle")

# ---------------- per-rank split bp-FIFOs (depth 16), rd | wr side by side ----
def fifo(x, name, payload):
    f.cells(x, 92, 3, 44, 46)                  # 3 cells shown of 16
    f.text(x, 82, name, size=12)
    cxc = x + 66
    for i, ln in enumerate(payload):
        f.text(cxc, 158 + 14 * i, ln, size=10, mono=False,
               anchor="middle", fill=MUTED)
    return cxc                                 # cell-row centre x

# rank 0
rd0 = fifo(70,  "rd_req_bp_fifo[0]", ["{rob_index,", "rd_phy_adr}"])
wr0 = fifo(250, "wr_req_bp_fifo[0]", ["{rob_index, wr_phy_adr,", "wr_data_prt}"])
# rank 1
rd1 = fifo(600, "rd_req_bp_fifo[1]", ["{rob_index,", "rd_phy_adr}"])
wr1 = fifo(780, "wr_req_bp_fifo[1]", ["{rob_index, wr_phy_adr,", "wr_data_prt}"])

f.text(430, 82, "x16 (BP_FIFO_DEPTH)", size=11, mono=False, fill=MUTED)
f.note(958, 110, "x N_RANKS", anchor="start")

# ---------------- rank_arb (outer) ----------------
for x in (rd0, rd1, wr0, wr1):                  # four split streams down
    f.line(x, 138, x, 250, arrow=True)

ra = f.logic(100, 250, 820, 60, "rank_arb",
             "outer: pick live rank  -  selected rank's rd & wr BOTH pass")

# ---------------- rank_arb -> two split lanes -> wlr_sel ----------------
f.line(480, 310, 480, 382, arrow=True)
f.slash(480, 348, "REQ_W")
f.text(468, 336, "rd_sel", size=12, anchor="end")

f.line(580, 310, 580, 382, arrow=True)
f.slash(580, 348, "REQ_W")
f.text(592, 336, "wr_sel", size=12)

wm = f.mux(430, 382, 200, 52, "wlr_sel", sel="rd/wr_select")

# ---------------- turnaround_ctrl drives the select ----------------
tc = f.logic(70, 384, 250, 60, "turnaround_ctrl",
             "full/partial_full  =>  rd/wr_select")
f.line(322, 412, 424, 412, arrow=True)          # select into wlr_sel (left)

# status flags feeding turnaround_ctrl (from fifo left edges)
f.line(185, 196, 185, 384, arrow=True, dashed=True)
f.slash(185, 300)
f.text(197, 300, "full, partial_full[.]", size=10, mono=False, fill=MUTED)

# ---------------- combined path out ----------------
f.line(530, 434, 530, 520, arrow=True)
f.slash(530, 480, "REQ_W")
f.text(544, 486, "{rob_index, phy_adr, op}", size=11, fill=MUTED)
f.text(530, 542, "->  to lookahead (stage 2)", size=12, mono=False,
       anchor="middle")

f.caption(40, 578, "R and W stay split through rank_arb; wlr_sel is the single "
                   "point they merge to one combined path.")

f.save("fig_01_ingress.svg")
print("wrote fig_01_ingress.svg")
