from rtlfig import (Fig, MUTED, FILL_NEW, FILL_ACTIVE, FILL_LOGIC, FAINT, INK,
                    W_CELL)

# fig_31 — ME (7 FSMs) emits SINGLE-BIT flags on ONE shared cmd interface;
# demand raises cas/act/pre. The SCHEDULER ranks all together (no ME-internal
# select). INIT alone is the hard override (DFI mux). MRR result via RD_CAP
# sideband, split by the MR Read Arbiter.

f = Fig(1240, 790)


def cnote(x, y, s, anchor="start"):
    f.text(x, y, s, size=10, mono=False, anchor=anchor, fill=MUTED)


f.text(40, 38, "ME single-bit flags (one shared interface) + demand -> scheduler",
       size=15, mono=False, bold=True)
f.note(40, 58, "7 FSMs live in ONE ME block; it emits single-bit flags on the shared "
               "cmd interface (like demand). Scheduler ranks all. INIT = only hard override.")

# ---------------- ME container + 7 FSMs ----------------
f.rect(40, 92, 290, 470, width=W_CELL)
f.text(325, 84, "MAINTENANCE ENGINE", size=12, anchor="end", fill=MUTED)
FSMS = [
    ("INIT (16)", "power-on -> init_done", True),
    ("REFRESH (6)", "leaky bucket", False),
    ("RFM (6)", "RAA >= RAAIMT", False),
    ("ZQCAL (7)", "tZQCS -> MPC", False),
    ("MR_POLL (6)", "MR4 temp", False),
    ("MR_WRITE (9)", "CSR MRW +verify", False),
    ("POWER_MGMT (10)", "PD / SR", False),
]
fy = []
for i, (nm, sub, is_init) in enumerate(FSMS):
    y = 126 + i * 61
    fy.append(y)
    fill = FILL_NEW if is_init else FILL_LOGIC
    f.rect(55, y, 255, 46, fill=fill, width=W_CELL, rx=6)
    f.text(182, y + 19, nm, size=12, anchor="middle", bold=True)
    f.text(182, y + 35, sub, size=9, mono=False, anchor="middle", fill=MUTED)

# ---------------- ONE shared flag bus out ----------------
f.line(330, 330, 558, 330, arrow=True)
f.slash(444, 330)
cnote(340, 322, "single-bit flags (shared cmd interface):")
cnote(340, 350, "ref_urgent, ref_due, rfm_req, zq_due, mrr, mrw + me_cmd")

# ---------------- demand lanes (top, into scheduler) ----------------
f.rect(560, 118, 320, 52, fill=FILL_ACTIVE, width=W_CELL)
f.text(720, 140, "DEMAND  cas / act / pre -> L3", size=13, anchor="middle")
f.text(720, 157, "per-bank class winners", size=10, mono=False, anchor="middle", fill=MUTED)
f.line(720, 170, 720, 206, arrow=True)
cnote(730, 192, "demand")

# ---------------- scheduler ----------------
f.logic(560, 206, 320, 214, "SCHEDULER  (arb + packer)", top=True)
f.text(720, 268, "ranks flags + demand together:", size=11, mono=False,
       anchor="middle", fill=MUTED)
f.text(720, 296, "ref_urgent > ref_due > rfm > zq", size=12, mono=False, anchor="middle")
f.text(720, 320, "vs  cas / act / pre  (demand)", size=12, mono=False, anchor="middle")
f.text(720, 356, "flags = soft priority", size=11, mono=False,
       anchor="middle", fill=MUTED)
f.text(720, 386, "(no ME-internal priority-select)", size=10, mono=False,
       anchor="middle", fill=MUTED)
# sched_ack back to ME
f.path("M560 400 C500 400 420 440 332 440", arrow=True, dashed=True)
cnote(360, 456, "sched_ack -> ME")

# ---------------- INIT -> DFI mux (only hard override) ----------------
f.path("M182 126 V102 H1010 V266", arrow=True)
cnote(600, 96, "INIT drives DFI till init_done (one-way) - the ONLY hard override")
f.logic(935, 266, 150, 80, "DFI_MUX", "sel = init_done", top=True)
f.line(880, 306, 933, 306, arrow=True)
f.line(1010, 348, 1010, 390, arrow=True)
f.text(1021, 382, "-> DFI / PHY / DRAM", size=12, mono=False)
cnote(900, 236, "ME writes scoreboard: gate_rfc/zq/mr, RAA, tREFI")

# ---------------- RD_CAP sideband + MR Read Arbiter ----------------
f.logic(560, 600, 320, 54, "RD_CAP", "read capture", top=True)
f.path("M1010 348 V626 H882", arrow=True, dashed=True)
cnote(1021, 500, "DRAM read")
f.logic(380, 590, 170, 50, "MR_READ_ARB", "grants 1: POLL | WRITE", top=True)
f.path("M560 626 H465 V642", arrow=True, dashed=True)
cnote(400, 664, "{mrr_data, valid, rank, requester} sideband (NOT resp FIFO)")
# arbiter -> MR_POLL (idx4) and MR_WRITE (idx5), tagged by requester
f.path(f"M380 606 H345 V{fy[4]+23} H312", arrow=True, dashed=True)
f.path(f"M380 620 H360 V{fy[5]+23} H312", arrow=True, dashed=True)

f.caption(40, 766,
          "The ME is one block: its 7 FSMs share a single-bit flag interface into the "
          "scheduler, exactly like demand cmds. Scheduler ranks flags+demand together "
          "(flags = soft priority). INIT alone is a hard override (DFI mux). MR_POLL + "
          "MR_WRITE share the MR Read Arbiter; mrr_requester routes the sideband result.")

f.save("fig_31_maint_engine.svg")
print("wrote fig_31_maint_engine.svg")
