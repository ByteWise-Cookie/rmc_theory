# Micro-op encoding — the tagged command that rides the arb tree

**Phase-2 rebuild.** One fixed-width, `enc`-tagged **micro-op** is the single object that travels the
whole forward path. `enc` (the command type) rides **every arb level** — each level applies the
timing check for *its* scope keyed by `enc` (and direction) — and reaches the packer, where `enc`
decodes the CA fields and decides whether the data engine arms. The operand is a **tagged union**:
ACT's `row` and CAS's `{col, sram, rob}` never coexist in one micro-op, so they share the same bit
slots. Companion to STAGE 12 (arb tree) and STAGE 13 (back-end). Figure: `fig/fig_15_microop`.

---

## 1. Why one tagged micro-op

The arb tree already narrows a winner hierarchically (`CMD_ARB → BGB_ARB → BG_ARB → RANK_ARB`). Rather
than carry per-command payloads on separate buses, **one fixed-width micro-op** rides the same selects.
Two facts make it cheap:

- **Only one command per bank per pass**, and for a given bank ACT and CAS are *different* passes
  (miss climbs as PRE, then ACT, then — as a hit — CAS). So a single micro-op never needs both `row`
  and `{col,sram}` at once → **overlap them in a union**.
- **`enc` is the discriminant everywhere.** Every level reads `enc` to pick the timing constraint for
  its scope; the packer reads `enc` to lay the CA fields and to gate the data-engine arm. One tag,
  reused at every stage.

---

## 2. Micro-op format (fixed width)

| field | bits | meaning |
|---|---|---|
| `enc` | 2 | command type — the union discriminant (§3) |
| `dir` | 1 | R/W, meaningful for `enc==CAS` (selects tWTR/tRTW/tCCD_L_WR vs read deltas) |
| `idx` | 6 | grant identity `{rank(1), bg(3), bank(2)}` (N_RANKS=2) — who won |
| `operand` | 27 | **tagged union**, interpreted by `enc` (§4) |
| | **≈36 b** | total per micro-op lane |

`idx` is the resolved winner assembled from the level selects (bank from L1, bg from L2, rank from L3),
so the packer needs no separate address lookup.

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

## 6. Lanes — one micro-op is not enough for a bundle

At gear 1:4 the packer fills a bundle that can hold **1 CAS + 1 ACT + fill PRE** to *different* banks
in one mc_clk (STAGE 5). A single micro-op lane carries one command per cycle, so it would serialize
the bundle and kill phase-fill. Two options:

- **N parallel lanes**, `N = max commands per bundle ≈ 3` (CAS, ACT, PRE) — each lane the identical
  micro-op format, produced by the tree's top winners.
- **One lane + packer gather** — emit one micro-op per sub-cycle and let the packer assemble the bundle
  across the 4 CK of the mc_clk.

Either way the **format** is shared; only the number of concurrent slots changes.

---

## 7. Width summary

```
micro-op = enc(2) + dir(1) + idx(6) + operand-union(27)  ≈ 36 b / lane
operand-union width  = max( ACT row 18 , CAS {col10+sram9+rob8}=27 , PRE 0 ) = 27
bundle bus           = N_lanes × 36 b   (N ≈ 3)
```

The union saves the `row` bits from ever being a separate field — they live in the CAS slot's low
bits and are only read when `enc==ACT`. Combined with `open_row`-at-admit (STAGE 12 refinement, `row`
is not stored per-packet at all — it is read from `open_row` when an ACT wins), the forward path
carries **one tagged 36-bit micro-op per lane**, `enc`-decoded identically at every stage.
