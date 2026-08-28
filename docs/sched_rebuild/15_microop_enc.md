# Micro-op encoding — the tagged command that rides the arb tree

**Phase-2 rebuild.** The command that travels the arb tree is **not** the full payload — that would
push ~36 b through every level for nothing. Only the tiny tag `{enc(2), dir(1)}` rides the levels
(it is all a level needs to pick which timing constraint applies), alongside the grant. The
**operand stays parked in the winning cell** and is pulled **once, at the packer**, by the grant
`idx`. The full micro-op is therefore *assembled at the packer*: `enc/dir` from the tree + operand
from the cell. Companion to STAGE 12 (arb tree) and STAGE 13 (back-end). Figure: `fig/fig_15_microop`.

---

## 1. What rides the tree vs what stays put

The arb tree narrows a winner hierarchically (`CMD_ARB → BGB_ARB → BG_ARB → RANK_ARB`). Carrying the
27-b operand up all four levels is wasted width — a level never reads the operand, only the tag.

- **Rides the tree (3 b):** `{enc, dir}`. Each level reads `enc` (and `dir`) to select which
  scope-timing/`can_*` applies — nothing more. The grant one-hot narrows `idx` as it climbs.
- **Stays in the cell:** the operand. Parked in `BANK_REQ_REG` (and `row` in `open_row`, per the
  STAGE 12 `open_row`-at-admit refinement — not stored per-packet at all).
- **Assembled at the packer:** `idx` (the resolved winner) selects the operand out of the winning
  cell via the staged mux; `enc` decodes the CA fields and gates the data-engine arm.

The operand is still a **tagged union** when read — ACT's `row` and CAS's `{col, sram, rob}` never
coexist for one command (miss climbs as PRE, then ACT, then — as a hit — CAS), so they share slots.
But that union lives in the cell / at the packer read, **not on a bus climbing the tree.**

---

## 2. Assembled micro-op (at the packer — NOT a bus up the tree)

This is the object the packer builds and hands to the DFI CA/data stage. It exists only here; the
tree never carries the wide form.

| field | bits | rides the tree? | source |
|---|---|---|---|
| `enc` | 2 | **yes** | FSM state (need_pre/act/cas) — the union discriminant (§3) |
| `dir` | 1 | **yes** | R/W; selects tWTR/tRTW/tCCD_L_WR vs read deltas (only `enc==CAS`) |
| `idx` | 6 | **as the grant** | resolved winner `{rank(1), bg(3), bank(2)}` — narrowed by the level selects |
| `operand` | 27 | **no** | pulled from the winning cell by `idx` at the packer — **tagged union** (§4) |
| | **≈36 b** | | assembled only at the packer output |

Up the tree the payload is just **`{enc, dir}` (3 b) + the grant one-hot**. `idx` (from the grant)
then selects the operand out of the cell — no separate address lookup, no wide bus climbing four levels.

---

## 3. `enc` values

| `enc` | cmd | 2-cyc? | operand used | data engine |
|---|---|---|---|---|
| `00` | `PRE` | 1-cyc | — (idx only) | none |
| `01` | `ACT` | 2-cyc | `row` | none |
| `10` | `CAS` | 2-cyc | `{col, sram, rob}` (+`dir`) | **arms** RD/WL line |
| `11` | `REF` / `NOP` | 1-cyc | — (or `ba` for REFsb) | none |

(`REF` is injected by the maintenance engine as the same micro-op format — override priority — so it
rides the identical path and timing checks.)

---

## 4. Union operand (`enc` reinterprets the 27-bit slot)

| `enc` | operand layout (within the 27-bit slot) | width used |
|---|---|---|
| `PRE` | — | 0 |
| `ACT` | `row[17:0]` | 18 |
| `CAS` | `col[9:0]` · `sram_addr[8:0]` · `rob_index[7:0]` | 27 |
| `REF` | `ba[1:0]` (REFsb) or — (REFab) | ≤2 |

The union width is set by the **widest** member, `CAS = 27 b` — **not** `row`. `row` fits inside the
same slot. `sram_addr` is `dbuf_addr` (read) or `wd_slot` (write); it is the **only** field the data
engine consumes, and only when `enc==CAS`.

---

## 5. `enc` at every level — the per-scope timing role

`enc` (with `dir`) selects **which** timing constraint each level enforces. Deadlines are written into
the scoreboard at issue (STAGE 6); each level filters its candidates by the `enc`-appropriate `can_*`.

| level | scope | timing keyed by `enc`(+`dir`) |
|---|---|---|
| `CMD_ARB` (L0) | same bank | `enc` chosen from FSM state. `PRE`→tRAS/tRTP/tWR · `ACT`→tRC · `CAS`→tCCD_L(sb) |
| `BGB_ARB` (L1) | bank-in-BG | hit-bias for `enc==CAS`; age for `ACT` |
| `BG_ARB` (L2) | BG-in-rank | `CAS`→tCCD_S/tCCD_L + diff-`last_cas_bg` bonus · `ACT`→tRRD_S/tRRD_L |
| `RANK_ARB` (L3) | across ranks | `CAS`+`dir`→tWTR/tRTW/tCCD_L_WR/tRTRS · `ACT`→tFAW/tRRD · tRTRS on rank hop |
| `PHASE_PACKER` | CA + data | `enc`→CA field decode (ACT drives `row`, CAS drives `col`, PRE drives `bank`) + **arm data engine iff `enc==CAS`** |

The diff-BG (`tCCD_S`) preference lives only at L2 and only for `CAS` — the DQ-packing lever. Direction
(`dir`) matters only where R/W turnaround costs differ (L3, and tCCD_L_WR at L2).

---

## 6. Bundle slots — only at the packer output

At gear 1:4 the packer fills a bundle of **1 CAS + 1 ACT + fill PRE** to *different* banks in one
mc_clk (STAGE 5). This is a concern **only at the assembled-micro-op stage** (packer → DFI), not up
the tree — the tree just narrows grants. Two options for the packer:

- **N assembled slots**, `N = max commands per bundle ≈ 3` (CAS, ACT, PRE) — each a full ~36-b
  micro-op read out from its winning cell.
- **One slot + gather** — assemble one micro-op per sub-cycle and pack the bundle across the 4 CK.

Either way the wide form exists only here; the four arb levels never carry more than `{enc, dir}` +
the grant.

Either way the **format** is shared; only the number of concurrent slots changes.

---

## 7. Width summary

```
UP THE TREE (×4 levels):  {enc(2), dir(1)} + grant one-hot        = 3 b + grant
AT THE PACKER (assembled): enc(2)+dir(1)+idx(6)+operand-union(27) ≈ 36 b / slot
operand-union width      = max( ACT row 18 , CAS {col10+sram9+rob8}=27 , PRE 0 ) = 27
bundle (packer output)   = N_slots × 36 b   (N ≈ 3)      ← wide form lives ONLY here
```

The waste avoided: the 27-b operand is **not** dragged through four arb levels — only the 3-b tag is,
and the operand is fetched once by the grant at the packer. The union then keeps `row` from being a
separate stored field (it shares the CAS slot, and per `open_row`-at-admit is read from `open_row`,
not stored per-packet). Net: **3 b on the tree, one ~36-b micro-op assembled at the packer.**
