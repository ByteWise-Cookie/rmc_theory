from rtlfig import (Fig, MUTED, FILL_NEW, FILL_LOGIC, FILL_CELL, FILL_ACTIVE,
                    FAINT, INK, PAPER, W_CELL)

# fig_59 — BANK-level writeback, address-driven (user's structure).
# ONE encoded address {rank,bg,bank} does double duty: (1) RESET-decode clears the
# can_* SR flops at that bank, (2) WE-decode writes the 3 new timestamps into BANK_RF.
# CONST bank is picked by CMD type (router/case), NOT by address.

f = Fig(1560, 700)


def adder(cx, cy, sub):
    f.counter(cx, cy, 20, "+", sub)


f.text(40, 34, "BANK writeback - one address, reset + set  (ACT example)", size=15,
       mono=False, bold=True)
f.note(40, 54, "addr {r,bg,bank} = WHERE (reg WE + can_* reset).  cmd type = WHAT "
               "(const router -> adders).  Two selectors, both from the grant.")

# ---- grant -> addr encoder ----
f.block(40, 110, 150, 80, "ACT_GRANT", "{r,bg,bank,ph,row}")
f.logic(230, 110, 120, 80, "ADDR_ENC", "", top=True)
f.line(190, 150, 228, 150, arrow=True)
# address bus (thick) out of encoder
f.text(360, 128, "addr {r,bg,bank}", size=10, mono=True, bold=True)
f.path("M350 150 H430 V250", arrow=False, stroke=INK)          # down to reset+WE rail
f.line(350, 150, 430, 150, arrow=False)

# phase_off + GC
f.counter(95, 300, 30, "GC", "+=gear")
adder(210, 300, "ph_off")
f.line(125, 300, 188, 300, arrow=True)
f.line(210, 262, 210, 280, arrow=True)
f.text(216, 274, "phase_off", size=8, mono=True, fill=MUTED)
f.line(232, 300, 300, 300, arrow=False)
f.path("M300 300 V470", arrow=False, stroke=INK)
f.text(305, 292, "GC_ph -> adders + all GE", size=9, mono=False, fill=MUTED)

# ---- cmd -> router (case) -> const ----
f.block(40, 230, 150, 55, "op (cmd)", "from grant")
f.logic(230, 235, 150, 90, "ROUTER / case", "pick const triple", top=True)
f.line(190, 258, 228, 258, arrow=True)
f.block(40, 360, 150, 90, "BANK_CONST", "tRC tRCD tRAS ...")
f.path("M190 405 H210 V325", arrow=True, dashed=True, stroke=MUTED)
f.text(60, 470, "cfg / freq-FSM writable (flops)", size=8, mono=False, fill=MUTED)

# router outputs 3 consts to the 3 adders
AX = 560
brows = [(230, "tRC", "next_act"), (320, "tRCD", "next_cas"), (410, "tRAS", "next_pre")]
for (cy, cst, fld) in brows:
    # const from router
    f.path(f"M380 280 H{AX-70} V{cy} H{AX-18}", arrow=True, dashed=True, stroke=MUTED)
    f.text(AX - 66, cy - 6, cst, size=9, mono=True, fill=INK)
    # GC_ph from rail
    f.line(300, cy, AX - 20, cy, arrow=True)
    adder(AX, cy, "")
    f.text(AX, cy + 3, "+", size=13, anchor="middle", bold=True)

# ---- BANK_RF (write target, addressed) ----
RX = 700
f.rect(RX, 200, 175, 250, fill=FILL_CELL, width=W_CELL)
f.text(RX + 87, 224, "BANK_RF[bank]", size=11, anchor="middle", bold=True)
for j, fld in enumerate(["next_act (13b)", "next_cas (13b)", "next_pre (13b)"]):
    f.text(RX + 14, 270 + j * 55, fld, size=9, mono=True)
for j, (cy, cst, fld) in enumerate(brows):
    f.path(f"M{AX+20} {cy} H{RX-18} V{265+j*55} H{RX}", arrow=True)

# WE from addr
f.path("M430 250 H612 V210", arrow=True, dashed=True, stroke=MUTED)
f.text(620, 224, "WE = addr decode (write here)", size=8, mono=False, fill=MUTED)

# ---- GE -> SR -> can_* ----
GX, SX, CX = 960, 1050, 1140
tail = [(265, "can_act"), (320, "can_pre"), (375, "can_cas")]
# order fields to their can names
tail = [(265, "can_act"), (320, "can_cas"), (375, "can_pre")]
for (ty, nm) in tail:
    f.line(RX + 175, ty, GX - 27, ty, arrow=True)
    f.decision(GX, ty, 52, 26, "GE")
    f.line(GX + 26, ty, SX, ty, arrow=True)
    f.text(GX + 31, ty - 6, "S", size=8, fill=MUTED)
    f.rect(SX, ty - 14, 44, 28, fill=PAPER, width=W_CELL)
    f.text(SX + 22, ty + 4, "SR", size=10, anchor="middle", bold=True)
    f.line(SX + 44, ty, CX, ty, arrow=True)
    f.rect(CX, ty - 13, 140, 26, fill=FILL_NEW, width=W_CELL)
    f.text(CX + 70, ty + 4, nm, size=10, mono=True, anchor="middle")

# GC to all GE
f.path("M300 470 H960 V388", arrow=True, dashed=True, stroke=FAINT)
f.text(560, 482, "GC -> all GE (SET at GC >= next_*)", size=9, mono=False, fill=MUTED)

# RESET from addr into every SR (block now) — rail above the SR column
f.line(430, 250, 1072, 250, arrow=False, dashed=True, stroke=MUTED)
for ty in (265, 320, 375):
    f.path(f"M1072 250 V{ty-14}", arrow=True, dashed=True, stroke=MUTED)
f.text(700, 244, "RESET = addr decode (reset-dominant) -> the 3 SR flops", size=8,
       mono=False, fill=MUTED)

f.caption(40, 640,
          "One address {r,bg,bank} fans to BOTH the reg WE and the can_* RESET decode - block-now "
          "+ write-timestamp in one issue. CMD type (not address) routes {tRC,tRCD,tRAS} to the 3 "
          "adders; GC_ph + const = new next_*; GE re-sets can_* at GC >= next_*. Replicated per scope.")

f.save("fig_59_bank_writeback_addr.svg")
print("wrote fig_59_bank_writeback_addr.svg")
