# ADEC — Address Decode / Map Unit (AMU)

**Phase 1, block 04.** First core block the packet hits after the ingress FIFO. Maps an
AXI byte address to the DRAM coordinate `{rank, bank-group, bank, row, column}` and
computes the sub-block byte offset. KB name: **AMU** (Address Map Unit). Combinational,
setup-time configurable, locked before `init_done`.

Grounded in KB §12 + §19 (address map) + mentor's `Attmem=offset[2:0]` / LSB-alignment.

---

## 0. Role

```
{addr, size} ──▶ [ hash ] ──▶ [ field extract ] ──▶ {rank, bg, bank, row, col}
                                                     + offset[2:0] (sub-block)
```

Turns a flat address into the DRAM geometry the scheduler schedules against. The **only**
policy here is the address-map (which address bits become which DRAM field) — everything
downstream (HZU/BQ/ARB) works in `{rank,bg,bank,row,col}` space.

**Why hashing matters:** bank/BG-address **diversity is the fuel** for datapath-busy
(block 00 I20/I23). If all traffic hits one bank, no BG rotation, no ACT/PRE hiding is
possible. The hash spreads accesses; the extract preserves locality where it counts.

---

## 1. Pipeline (combinational, 2 stages)

### Stage 1 — per-field XOR hash (opt-in)
```
hashed_addr[field] = raw_addr XOR (raw_addr >> xor_shift[field])   if hash_en[field]
                   = raw_addr                                       otherwise
```
A cheap XOR-fold that decorrelates a field's bits from sequential-stride patterns.

### Stage 2 — field extract from hashed_addr
Extract each field's bit range; **split fields** (non-contiguous bit ranges) supported for
channel interleave.

---

## 2. Field descriptor (6 fields: ch, rank, bg, bank, row, col)

| Sub-field | Width | Meaning |
|-----------|-------|---------|
| `src_msb_a` | 5 | upper segment MSB |
| `src_lsb_a` | 5 | upper segment LSB |
| `src_msb_b` | 5 | lower segment MSB (split only) |
| `src_lsb_b` | 5 | lower segment LSB (split only) |
| `split_en` | 1 | 1 = use both segments |
| `hash_en` | 1 | per-field XOR hash enable |
| `xor_shift` | 5 | per-field shift amount |

**Field assignment (locked, KB §12):**

| Field | `hash_en` | Rationale |
|-------|-----------|-----------|
| rank | 1 (MSB position) | spread across ranks; rank-switch penalty → push to MSB |
| ch | 1 | spread across channels |
| bg | 0 | **preserve locality** — row-hit rate is critical |
| bank | 0 | preserve locality |
| row | 0 | preserve locality |
| col | 0 | preserve locality; `split_en` used for ch interleave |

---

## 3. Sub-block offset / LSB alignment

From `size` (AXI `awsize`/`arsize` → 8/16/32/64/128 B) compute the aligned base + the
byte-lane offset within a BL16 (mentor's `Attmem = offset[2:0]` + `LSB alignment`):
```
offset[2:0] = f(size, addr[low])     # where in the burst the requested bytes sit
aligned_addr = addr with low bits masked to the BL16 boundary
```
This is where a sub-cacheline access's active byte lanes are placed for the write mask /
read extract. BL16 on the 32b subchannel = 64 B granule (block 00 / KB §3).

---

## 4. Baseline address map (32b, 4 GB — KB §19)

```
A[31:17] = Row    (ROW_BITS)
A[16:14] = BG     (BG_BITS=3, 8 bank groups)
A[13:12] = Bank   (BANK_BITS=2, 4 banks/BG)
A[11:2]  = Col    (COL_BITS=10)
A[1:0]   = Offset
Channel select = A[7]   (128 B interleave baseline)
```
BG/Bank bits fixed across configs. JEDEC ceiling 41b (8ch×8rank×64Gb); 46b with 3DS-8H.

### Multi-config profiles (KB §19)
| Config | Total | Addr | Ch | Rank | Row | Col |
|--------|-------|------|----|----|----|----|
| Desktop-S | 8 GB | 33b | 0 | 0 | 16 | 10 |
| Desktop-D | 16 GB | 34b | 1(A[7]) | 0 | 16 | 10 |
| Desktop-Q | 32 GB | 35b | 1 | 1(A[8]) | 16 | 10 |
| Workstation-D | 64 GB | 36b | 1 | 1 | 17 | 10 |
| Enterprise-8C | 1 TB | 40b | 3(A[9:7]) | 3 | 18 | 11 |
| JEDEC Max | 2 TB | 41b | 3 | 3 | 18 | 11 |
| 3DS-Max | 64 TB | 46b | 3 | 3+3(CID) | 18 | 11 |

> **N_RANKS 1→2 intent (block 00 C1):** the rank field must be non-empty for the 2-rank
> config; `RANK_BITS 0→1`. Address-map + pkg change deferred to RTL-go.

---

## 5. Interfaces (valid-credit downstream)

**CSR setup (init only, locked before `init_done`):** `amu_wr_en`, `amu_field_sel[3]`,
`amu_src_msb_a/lsb_a/msb_b/lsb_b[5]`, `amu_split_en`, `amu_hash_en`, `amu_xor_shift[5]`.

**Runtime (combinational):** `byte_addr[ADDR_WIDTH]`, `size` → `hashed_addr`, `ch`, `rank`,
`bg`, `bank`, `row`, `col`, `offset[2:0]`. Out to HZU (block 05) valid-credit.

---

## Open items (ADEC)

- **OQ-19b** channel interleave granularity — 4 KB (A[12]) / 8 KB (A[13]) / 16 KB (A[14]);
  needs the `addrmap` Python sweep + traffic trace. CSR-configurable at runtime.
- **OA-1** address-map policy sweep — the whole hash/extract assignment is a
  `tools/addrmap` optimization target (row-hit vs bank-conflict vs parallelism). Apply its
  best; ADEC just executes the descriptor.
- **OA-2** offset derivation for 128 B size vs 64 B BL16 granule — confirm alignment for
  the largest `size`.
