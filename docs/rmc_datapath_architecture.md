# RMC Datapath Architecture

**Status: architecture / specification document. NOT an RTL implementation. No RTL exists for
this block yet — RTL lives in the separate `rmc` repository and starts only after this
document is reviewed and frozen.**

Authoritative sources (scheduler-rebuild, current over any older fabric/datapath doc):

- `docs/sched_rebuild/fig/fig_mcc_block.py` (+ `.svg`) — MC-core master floorplan
- `docs/sched_rebuild/fig/fig_06_datapath.py` — RL/WL streaming: accumulator + splitter
- `docs/sched_rebuild/fig/fig_05_packer.py` — phase packer
- `docs/sched_rebuild/fig/fig_07_l0_rank.py`, `fig_08_rank_funnel.py` — L0–L3 arb structure
- `docs/sched_rebuild/fig/fig_01_ingress.py`, `fig_00_top.py` — ingress + top-level assembly
- `docs/sched_rebuild/cif_quick_ref.tex` — CIF-side block quick reference (WD_SRAM/RD_SRAM
  ownership, packet forms)

Older pre-rebuild documents (`docs/sched_rebuild/01_dfi_exchange_fabric.md`,
`docs/sched_rebuild/11_mc_core_architecture.md`, `docs/sched_rebuild/tex/rmc_mc_core_rebuild.tex`)
describe an earlier "DFI exchange fabric" (FAB) block with MCC-local pack/unpack, CDC, and
buffering. That model is **superseded** by the WD_SRAM/RD_SRAM-owned-by-CIF model below and is
not used as a source of truth here except where noted for contrast.

---

## 1. Purpose and Scope

The scheduler rebuild (commits `6512220`, `217d8e7`, `d83f774`, `295ffc1`, `6308047`) froze the
request/arbitration side of MC-core (L0 cell FSMs through L3 inter-rank arbitration and the
phase packer) but left the **datapath** — the block that actually moves write data out to DRAM
and read data back — documented only as a pair of figures (`fig_06_datapath.py`,
and its embedding in `fig_mcc_block.py`) with no accompanying prose spec.

This document is that missing prose spec. It defines, at architecture/contract level:

- what the datapath receives from the phase packer at CAS-commit,
- the write flow (WD_SRAM → serialize → DFI),
- the read flow (DFI → deserialize → RD_SRAM),
- who owns which SRAM and where the clock-domain-crossing (CDC) boundary is,
- what is timing-model-complete versus still open (numeric latencies, exact signal
  semantics).

This is **not** an RTL implementation and does not choose module boundaries, register names,
or exact cycle-level timing beyond what the authoritative figures already show. It exists so
the datapath can be reviewed and frozen before RTL is written, in the `rmc` repository.

---

## 2. Position in the Scheduler-Rebuild Architecture

Per `fig_00_top.py` / `fig_07_l0_rank.py` / `fig_08_rank_funnel.py` / `fig_mcc_block.py`, the
scheduling hierarchy is:

```
L0 (per-cell CAM + FSM + eligibility, one cell per {rank, bank})
  -> L1 BG_ARB       (per rank, per bank-group: 4 banks -> 1, x8 BG)
  -> L2 RANK_ARB      (per rank: 8 BG winners -> 1 rank winner)
  -> L3 INTER_RANK_ARB (across ranks, weighted by tRTRS: the ONLY rank arbiter)
  -> PHASE_PACKER      (gear 1:N bundle fill, FSM-commit)
  -> datapath / DFI     (THIS DOCUMENT)
```

L0–L2 are instanced once per rank (`fig_08_rank_funnel.py`: "the decoder→L2 path is ONE rank
subtree ... instanced x N_RANKS"); L3 is the single point where rank winners are merged. The
phase packer is shared across all ranks and sits between L3 and the datapath.

**What the datapath receives from the phase packer:** a single per-phase-bundle command
stream (`fig_05_packer.py`: "N phases → DFI cmd (`dfi_address`/`cs` per phase)") plus, at the
moment a CAS is committed into that bundle, the CAS-commit handoff described in §3. The
datapath does not participate in scheduling decisions (bank/BG/rank legality, timing
eligibility) — all of that is resolved upstream by L0–L3 and the scoreboard. The datapath's job
starts only once a CAS has already been legally issued.

---

## 3. Datapath Interface / CAS Commit

`fig_06_datapath.py` draws the handoff from the phase packer explicitly:

```
from packer @ CAS-commit:  { op, tag, sram_addr }
```

- **`op`** — selects the WR or RD path inside the datapath (`fig_06_datapath.py` routes on
  `if RD` / `if WR`).
- **`tag`** — carried through the datapath for completion/response correlation. The concrete
  instantiation of `tag` is `rob_index` (`cif_quick_ref.tex`: `PKT_FORM_R`/`PKT_FORM_W` build
  packets keyed by `rob_index`; `CH_R_RESP_AFIFO`/`CH_W_RESP_AFIFO` carry
  `{rob_index, pkt_num, status}` back to CIF). The datapath treats `tag` opaquely — it does not
  interpret it, only threads it through to completion.
- **`sram_addr`** — the concrete meaning depends on `op`:
  - **WR:** `sram_addr = wd_slot`, a write-data slot inside CIF-owned `WD_SRAM` that already
    holds the 512-bit line to be written.
  - **RD:** `sram_addr = dbuf_addr`, the destination slot inside CIF-owned `RD_SRAM` where the
    datapath must write the 512-bit line once it has been assembled from DRAM.

**The datapath does not own allocation of `wd_slot`/`dbuf_addr`.** Allocation and lifetime of
these slots is a CIF-side concern (`WR_SRAM_MGR` allocates a per-burst slot-vector on arrival
and frees per packet on completion; `RD_SRAM_MGR` allocates a contiguous `dbuf` range at ROB
allocation and frees it on merge/drain — `cif_quick_ref.tex`). The datapath only ever consumes
an address it was handed.

No numeric width is asserted for `op`, `tag`, or `sram_addr` beyond what is shown in the
figures — exact bit widths are OPEN (see §12).

---

## 4. Write Datapath

End-to-end write flow (`fig_06_datapath.py`, bottom half; mirrored in `fig_mcc_block.py`):

```
phase-packer CAS-commit {op=WR, tag, sram_addr=wd_slot}
  -> WL_line (write delay/launch line, depth = CWL)
  -> fire @ slot 0  ("launch")
  -> WD_SRAM read: 1 x 512b read @ wd_slot
  -> write_burst_splitter ("WR_SPLIT + WL_LAUNCH" in fig_mcc_block): 512b -> serialize
  -> dfi_wrdata (DFI write data bus)
  -> last beat driven -> wr_done (self-timed, no ack)
```

**Write delay/launch (`WL_line`):** a depth-`CWL` shift structure (drawn as a row of cells in
`fig_06_datapath.py`) that holds `{wd_slot}` and advances one slot per cycle from the moment of
CAS-commit. "**Launch**" is the event when the entry reaches slot 0 ("fire @ slot 0") — that is
the cycle the datapath actually performs the `WD_SRAM` read and hands the line to the burst
splitter. The delay line's job is purely to align the WD_SRAM read / DFI drive with the write
CAS latency (`CWL`) after the command was issued; it carries no data itself, only the slot
address needed to launch.

### 4.1 WD_SRAM

- **CIF owns `WD_SRAM`** (`cif_quick_ref.tex`: "write data buffer — Holds write beats; MCC
  reads them at `wd_slot` to drive DFI"). MCC consumes it only through the defined interface —
  a 512-bit read at `wd_slot` — and does not manage its allocation or contents.
- `cif_quick_ref.tex` explicitly documents `RD_SRAM` as "dual-domain (MC + CIF ports)"; it does
  **not** repeat that phrase for `WD_SRAM`. Since CIF's write-admission path populates
  `WD_SRAM` and MCC's write datapath reads it, some cross-domain access arrangement is
  necessarily present, but the exact implementation (true dual-port memory, single-port with
  arbitration, a synchronizer stage, etc.) is **not specified** for `WD_SRAM` by any inspected
  source — treat it as OPEN rather than assumed identical to `RD_SRAM`'s documented form
  (§12).
- MCC performs **one 512-bit line read per packet** (`fig_06_datapath.py` invariant: "One 512b
  SRAM access per packet"). One line = one BL16 burst's worth of write data (§4.2).
- **There is no MCC-local bulk write-data buffer.** The 512-bit line read out of `WD_SRAM` goes
  directly into the burst splitter for serialization — it is not staged in an MCC-owned FIFO or
  RAM first.
- **There is no MCC-local write-data CDC FIFO.** This is the explicit point of departure from
  the older FAB model (§6), which described gray-pointer async FIFOs for write data inside the
  MCC/FAB block. In the current architecture, the only write-data-holding memory is CIF-owned
  `WD_SRAM`; MCC transports only the `wd_slot` address.

### 4.2 BL16 @ 1:4 Gear

Per `fig_mcc_block.py`: the channel is a **32-bit DDR5 sub-channel** (`"MC-core - one channel
(32-bit DDR5 sub-channel)"`).

- **DQ width** = 32 bits (one DDR5 sub-channel).
- **BL16** = 16 × 32 bits = **512 bits** per burst — this matches the 512-bit line size
  documented for both `WD_SRAM` and `RD_SRAM` (`fig_06_datapath.py`: "512b / line" on both
  SRAMs, and the explicit label "SRAM side - 512b wide, ratio-agnostic").
- **1:4 gear** = 4 DFI phases per `mc_clk` cycle (`fig_05_packer.py`: "phase bundle @ 1:4
  (1 mc_clk = 4 CK = 4 phases)").
- `fig_06_datapath.py` labels the DFI-side data rate as **2×gear beats per `mc_clk`** ("DFI
  side - 2\*gear beats / mc_clk"). At gear 1:4 that is 2×4 = **8 beats per `mc_clk`**. The
  figures do not decompose this rate into a specific phases-to-beats mapping — see the OPEN
  item below.
- **mc_clk cycles per BL16 transfer:** 16 beats total ÷ 8 beats/`mc_clk` = **2 `mc_clk` cycles**
  for one full BL16 burst at gear 1:4. This is a direct arithmetic consequence of the two
  documented facts above (BL16 = 16 beats; DFI side = 2×gear beats/`mc_clk`), not an invented
  parameter.

**OPEN:** the exact bit-to-phase / bit-to-beat ordering (i.e., which bits of the 512-bit
`WD_SRAM`/`RD_SRAM` line map to which phase and which beat-within-phase) is not defined by any
authoritative source inspected. `fig_06_datapath.py` only asserts that the accumulator/splitter
are "the ONLY blocks that know the gear ratio" and that the SRAM side stays "ratio-agnostic" —
it does not show the mapping itself. Do not assume a particular ordering (e.g. beat-0 = LSBs)
without further source material.

### 4.3 DFI Write Interface

The only DFI write-side terminology present in the authoritative sources is:

- **`dfi_wrdata`** — the DFI write data bus, width annotated as "2\*gear" beats/`mc_clk`
  (`fig_06_datapath.py`, `fig_mcc_block.py`).
- **`dfi_address` / `cs`** (per phase) — the DFI command bus driven by the phase packer
  (`fig_05_packer.py`: "→ DFI cmd (`dfi_address`/cs per phase)").

**OPEN:** no write-data-enable/valid signal (e.g. a `dfi_wrdata_en`-style qualifier) is named
in any of the authoritative scheduler-rebuild figures. The only write-timing/launch concept
documented is the `WL_line`/"launch" mechanism in §4 above, and completion is explicitly
**self-timed** (`fig_06_datapath.py`: "last beat driven → `wr_done` (self-timed, no ack)") —
i.e. the datapath does not wait for a DFI-side acknowledgment of write completion; it declares
`wr_done` once it knows (from its own launch timing) that the last beat has been driven. Do not
introduce a new signal name for the write-data enable/valid line — the exact signal, if one
exists, is unspecified by these sources. (The older, superseded FAB spec used terms like
`t_phy_wrlat`/`t_phy_wrdata` for PHY-side write timing parameters; those are not confirmed to
carry over to this architecture — see §6, §12.)

---

## 5. Read Datapath

End-to-end read flow (`fig_06_datapath.py`, top half; mirrored in `fig_mcc_block.py`):

```
phase-packer CAS-commit {op=RD, tag, sram_addr=dbuf_addr}
  -> RL_line (read delay/launch line, depth = CL), carrying {rob_index, dbuf_addr}
  -> fire @ slot 0  ("launch")
  -> read_accumulator ("RD_CAP + RD_ACCUM" in fig_mcc_block): deserialize -> gather 64B
       consuming dfi_rddata (2*gear beats/mc_clk)
  -> 1 x 512b write @ dbuf_addr into RD_SRAM
  -> last beat committed -> rd_done
```

### 5.1 Read timing / RL_line

`RL_line` is a depth-`CL` shift structure, directly analogous to `WL_line` for writes, but it
carries `{rob_index, dbuf_addr}` (the tag plus the destination address) rather than just an
address — because on the read side the datapath must still know *which* outstanding read a
given return corresponds to and *where* to deposit the assembled line. It advances one slot per
cycle from CAS-commit and "fires" at slot 0, i.e. `CL` cycles after the CAS was committed, arming
the read accumulator with the `dbuf_addr` it should write to once a full line has been gathered.
This is the datapath's outstanding-read tracker: its depth (`CL`) bounds how many reads can be
in flight through this structure at once (see §9).

### 5.2 DFI Read Capture

The only DFI read-side terminology present in the authoritative sources is:

- **`dfi_rddata`** — the DFI read data bus, width annotated as "2\*gear" beats/`mc_clk`
  (`fig_06_datapath.py`), feeding the `read_accumulator`.
- `fig_mcc_block.py` additionally annotates the arrow into `RD_CAP + RD_ACCUM` as
  `"dfi_rddata (RL later)"`, i.e. the accumulator consumes `dfi_rddata` and the `RL_line`'s
  fire event supplies the destination context ("later" — after the `CL`-cycle delay) rather
  than being carried alongside the data itself.

**OPEN:** no read-data-valid signal (e.g. a `dfi_rddata_valid`-style qualifier) is named in any
authoritative scheduler-rebuild figure. It is not specified whether the accumulator relies on
the `RL_line` timing alone to know when valid beats are arriving, or whether a separate DFI
valid/enable signal gates capture. Do not invent a specific signal name for this.

### 5.3 BL16 Accumulation

The `read_accumulator` ("deserialize → gather 64B") collects `dfi_rddata` at 2×gear = 8
beats/`mc_clk` (gear 1:4, §4.2) until a full 512-bit (64-byte) BL16 line has been assembled —
2 `mc_clk` cycles, by the same arithmetic as §4.2. It then
performs a single 512-bit write into `RD_SRAM` at `dbuf_addr` (`fig_06_datapath.py`: "1 x 512b
write @ dbuf_addr"). As with the write side, the exact bit/beat ordering within the assembled
512-bit line is OPEN (§4.2, §12).

### 5.4 RD_SRAM

MCC writes the completed 512-bit burst to CIF-owned `RD_SRAM` at `dbuf_addr`
(`cif_quick_ref.tex`: "`RD_SRAM`: read data buffer — 512b/line store; MCC writes returned read
data here at `dbuf_addr`. Dual-domain (MC + CIF ports)."). As with `WD_SRAM`, there is no
MCC-local bulk read-data buffer or CDC FIFO — the assembled line goes directly into
CIF-owned `RD_SRAM`.

---

## 6. SRAM Ownership and CDC

- **`WD_SRAM` and `RD_SRAM` are CIF-owned memories.** CIF allocates and manages their contents
  (`WR_SRAM_MGR`, `RD_SRAM_MGR` in `cif_quick_ref.tex`); MCC only reads `WD_SRAM` (at
  `wd_slot`) and writes `RD_SRAM` (at `dbuf_addr`). `cif_quick_ref.tex` documents `RD_SRAM`
  explicitly as "dual-domain (MC + CIF ports)"; it does not use that phrase for `WD_SRAM`, and
  the exact port/CDC implementation of `WD_SRAM` is not specified — see §4.1 and §12.
- **Bulk data does not travel through MCC FIFOs.** MCC transports descriptors/tags/addresses
  (`{op, tag, sram_addr}` at CAS-commit; `{rob_index, dbuf_addr}` through `RL_line`;
  `{wd_slot}` through `WL_line`) — not bulk write or read data.
- This supersedes the older fabric-local model (`docs/sched_rebuild/01_dfi_exchange_fabric.md`,
  `docs/sched_rebuild/tex/rmc_mc_core_rebuild.tex`), which described a "DFI exchange fabric"
  (FAB) block owning pack/unpack logic plus its own gray-pointer async CDC FIFOs for command,
  write-data, and read-data ("CDC: gray-ptr async FIFOs (command/wrdata/rddata) + 2-flop
  handshake syncs"). In the current, authoritative scheduler-rebuild architecture, bulk
  write/read data lives only in CIF-owned SRAM; there is no MCC/FAB-local data-bearing CDC
  FIFO. Treat any reference to that older buffer model as historical context only.

**Remaining architectural assumption (explicitly flagged, not resolved here):** CIF must
ensure the write data is actually present in `WD_SRAM` before MCC's `WL_line` fires and attempts
to read the corresponding `wd_slot`. None of the inspected authoritative sources define the
synchronization mechanism that guarantees this ordering (e.g. whether admission into the
scheduler is gated on a CIF-side "data ready" signal, whether there's a minimum delay baked
into the pipeline, or something else). **This is OPEN — do not assume a mechanism.** See §12.

---

## 7. Timing / Latency Model

**Architecturally specified** (from `fig_06_datapath.py`):

- A CAS-commit from the phase packer arms either `WL_line` (WR) or `RL_line` (RD).
- `WL_line` has depth `CWL`; `RL_line` has depth `CL`. Both are symbolic depths tied to the
  DRAM write/read CAS latency parameters, not fixed numeric values.
- The line "fires" at slot 0, which is the point where the SRAM access (`WD_SRAM` read, or the
  `RD_SRAM` write after accumulation) and the corresponding DFI activity are triggered.
- Completion is asserted at the last beat: `wr_done` on the last beat driven (self-timed, no
  ack), `rd_done` on the last beat committed into `RD_SRAM`.

**OPEN — numeric values and additional latency components** (do not choose values for these):

- The numeric values of `CL` and `CWL` themselves (JEDEC/speed-bin dependent) are not set in
  these documents.
- Whether `WL_line`/`RL_line` depth already includes any additional PHY-side latency (analogous
  to DFI `t_phy_wrlat`/`t_phy_rdlat` in the DFI 5.2 spec, or the `t_phy_wrdata`, `t_rddata_en`
  terms used in the older, superseded FAB chapter) or whether such PHY latency must be added on
  top of `CWL`/`CL` is not stated anywhere in the current authoritative sources.
- The access latency of the `WD_SRAM` read / `RD_SRAM` write itself (i.e., how many cycles pass
  between "fire @ slot 0" and the data actually being available/committed) is not specified.
- The exact cycle-level alignment between "fire @ slot 0" and the first `dfi_wrdata`/
  `dfi_rddata` beat is shown as a direct connection in the figures but no cycle count is given.

---

## 8. Completion and Response Flow

- **`wr_done`** — asserted when the write datapath has driven the last beat of the burst. This
  is **self-timed**: there is no acknowledgment from DRAM/PHY that confirms the write
  succeeded; `wr_done` reflects only that the datapath has finished driving `dfi_wrdata`
  (`fig_06_datapath.py`).
- **`rd_done`** — asserted when the read datapath has committed the last beat of the assembled
  line into `RD_SRAM`.
- Both feed a shared **`COMPLETION`** block (`fig_mcc_block.py`: "COMPLETION — `rd_done` |
  `wr_done`"), which in turn feeds an async completion FIFO back toward CIF
  (`fig_mcc_block.py`: `R/W_RESP_AFIFO`; labeled "completion → CIF (async)").
- On the CIF side, the corresponding async FIFOs are named `CH_R_RESP_AFIFO` /
  `CH_W_RESP_AFIFO` and carry `{rob_index, pkt_num, status}` (`cif_quick_ref.tex`) — i.e. the
  `tag` from §3 (`rob_index`) is what correlates a completion back to the original request.

No new completion interface name is introduced here; this section only describes the existing
`wr_done`/`rd_done` → `COMPLETION` → async-FIFO → CIF path as drawn.

---

## 9. Backpressure / Outstanding Requests

What is established by the authoritative sources:

- `WL_line`/`RL_line` are depth-`CWL`/depth-`CL` shift structures, which inherently bound how
  many write/read commits can be "in flight" through the delay line at once to that depth.
- The phase packer itself enforces "≤ 1 CAS / 8 CK" on the shared DQ bus and alternates CAS
  bank-groups when ≥2 BGs are live (`fig_05_packer.py`), which spaces same-direction CAS
  commits at least 8 CK apart at the point they're issued.

What is **OPEN** (not established by the inspected sources — do not assume):

- Whether the datapath itself exposes any ready/valid handshake toward the phase packer (the
  figures show a direct CAS-commit connection, not an explicit handshake).
- Whether the datapath ever applies its own scheduler-side backpressure/gating distinct from
  the upstream `RD_BP_FIFO`/`WR_BP_FIFO` admission-level backpressure shown in
  `fig_mcc_block.py`'s ingress side (those FIFOs gate request *admission*, not datapath
  execution).
- Whether multiple read bursts may be in flight through the single `read_accumulator`
  simultaneously, or whether the accumulator processes one burst at a time. `fig_06_datapath.py`
  draws exactly one `read_accumulator` instance and states it is "the ONLY block that knows the
  gear ratio" for reads, which is consistent with either a single-burst-at-a-time design or a
  pipelined one — the figures do not disambiguate.
- What assumption (if any) makes a single accumulator instance sufficient — e.g. whether it
  relies on the packer's "≤1 CAS/8CK" DQ spacing rule to guarantee returning bursts never
  overlap in time. This is a plausible explanation given the packer invariant, but it is not
  stated as a design rationale anywhere in the inspected sources, so it is listed here as an
  open assumption rather than an established fact.

---

## 10. Reset

None of the inspected authoritative sources (`fig_06_datapath.py`, `fig_mcc_block.py`, and the
rest of the scheduler-rebuild figure set) show a reset signal or describe reset behavior for
the datapath. This entire section is therefore **OPEN**.

What can be said only as a logical consequence of the structures described above (not as
documented reset behavior):

- Delay-line occupancy/valid state (`WL_line`, `RL_line`) would need to be cleared to avoid
  spurious launches on stale entries.
- Accumulator/serializer partial-transfer state (`read_accumulator`, `write_burst_splitter`)
  would need to be cleared to avoid a stale in-progress burst continuing across reset.
- In-flight `tag`/address state riding the delay lines would need to be discarded.
- Any completion-pulse state (`wr_done`/`rd_done`, and the `COMPLETION` block) would need to be
  cleared to avoid a spurious completion firing.

**Do not treat the above as specified.** The reset scope, polarity, synchronicity, and whether
it is per-datapath or system-wide are all undocumented. **`WD_SRAM`/`RD_SRAM` contents are not
claimed to be reset** — nothing in the authoritative sources states that SRAM contents are
cleared on reset, and since these SRAMs are CIF-owned, any reset behavior for their contents
would be a CIF-side decision in any case.

---

## 11. End-to-End Example

Symbolic only — `CWL`, `CL`, and per-stage SRAM/PHY latencies are OPEN (§7, §12), so no
concrete cycle counts are given beyond the ones that are directly derivable from documented
facts (the 2-`mc_clk` BL16 transfer at gear 1:4, from §4.2/§5.3).

**One write**, tag `T0`, `wd_slot = S0`:

1. `mc_clk` cycle 0: L3 issues the CAS for this write; phase packer commits it into the current
   phase bundle and emits `{op=WR, tag=T0, sram_addr=S0}` to the datapath.
2. `{S0}` enters `WL_line` at the top slot; it shifts one slot per `mc_clk` cycle.
3. After `CWL` cycles, `{S0}` reaches slot 0 and fires ("launch"): the datapath performs
   `1 x 512b read @ wd_slot=S0` from `WD_SRAM`.
4. `write_burst_splitter` serializes the 512-bit line onto `dfi_wrdata` at 2×gear = 8 beats per
   `mc_clk` (gear 1:4); the full BL16 burst is driven over 2 `mc_clk` cycles.
5. On the last beat driven, the datapath asserts `wr_done` for tag `T0` (self-timed — no DRAM
   acknowledgment is involved).
6. `wr_done` reaches `COMPLETION`, which pushes `{rob_index=T0, ..., status}` into the
   write-response async FIFO toward CIF.

**One read**, tag `T1`, `dbuf_addr = D0`:

1. `mc_clk` cycle 0: L3 issues the CAS for this read; phase packer commits it and emits
   `{op=RD, tag=T1, sram_addr=D0}` to the datapath.
2. `{rob_index=T1, dbuf_addr=D0}` enters `RL_line` at the top slot; it shifts one slot per
   `mc_clk` cycle.
3. After `CL` cycles, the entry reaches slot 0 and fires: the `read_accumulator` is armed with
   destination `dbuf_addr=D0` and begins capturing `dfi_rddata` beats.
4. At 2×gear = 8 beats per `mc_clk` (gear 1:4), the accumulator gathers a full 512-bit / 64-byte
   BL16 line over 2 `mc_clk` cycles.
5. The accumulator performs `1 x 512b write @ dbuf_addr=D0` into `RD_SRAM`, then asserts
   `rd_done` for tag `T1`.
6. `rd_done` reaches `COMPLETION`, which pushes `{rob_index=T1, ..., status}` into the
   read-response async FIFO toward CIF.

---

## 12. Open Questions

These are the only items marked OPEN in this document. Anything not listed here that is stated
in the body above is drawn directly from `fig_06_datapath.py`, `fig_mcc_block.py`,
`fig_05_packer.py`, or `cif_quick_ref.tex`. Split into two groups: items that change the
*architecture* (interface shape, handshakes, instance counts) and so should be settled before
this document is treated as frozen, versus items that are *parameters or low-level details*
which don't change the architecture described above and can be resolved later, during RTL
work, without revisiting this document.

### 12.1 Architectural decisions — resolve before freeze

1. Relationship between `CWL`/`CL` (as `WL_line`/`RL_line` depth) and additional PHY-side
   launch/capture latency (DFI 5.2-style `t_phy_wrlat`/`t_phy_rdlat`, or the older
   `t_phy_wrdata`/`t_rddata_en` terms from the now-superseded FAB chapter) — is PHY latency
   already folded into the line depth, or does the datapath need an additional stage to add it
   separately? This changes the pipeline structure, not just a number.
2. Exact bit-to-phase / bit-to-beat ordering within a 512-bit BL16 line (§4.2, §5.3) — not
   defined by any inspected source. This defines part of the accumulator/splitter's contract,
   not just an implementation choice.
3. Exact DFI write-data-enable/valid and read-data-valid signal names and semantics (§4.3,
   §5.2) — only `dfi_wrdata`, `dfi_rddata`, and `dfi_address`/`cs` are named; no
   enable/valid/strobe signal is documented. This is part of the datapath's external interface.
4. The CIF-side mechanism that guarantees write data is present in `WD_SRAM` before MCC's
   `WL_line` fires and reads `wd_slot` (§6), and — closely related — the exact cross-domain /
   port implementation of `WD_SRAM` itself, which `cif_quick_ref.tex` does not specify the way
   it does for `RD_SRAM` ("dual-domain (MC + CIF ports)") (§4.1). Both are cross-boundary
   protocol questions, not values to be filled in later.
5. Whether the single `read_accumulator` (and single `write_burst_splitter`) can/must handle
   more than one burst in flight at a time, and whether the packer's "≤1 CAS/8CK" DQ-bus rule
   is the (implicit, undocumented) reason a single instance suffices (§9). Determines whether
   one instance of each is architecturally sufficient or more are needed.
6. Whether the datapath exposes any explicit ready/valid handshake toward the phase packer, or
   whether CAS-commit is assumed always-accepted given upstream scheduling already guaranteed
   legality (§9). Changes whether the CAS-commit interface needs a backpressure signal at all.

### 12.2 Parameters / details — may be resolved during RTL implementation

1. Exact numeric values of `CWL`/`CL` (or their JEDEC-parameter equivalents) — not set anywhere
   in the current authoritative sources. Does not change the architecture in §4/§5, only its
   timing.
2. `WD_SRAM`/`RD_SRAM` access latency itself (cycles from "fire @ slot 0" to data
   available/committed) — not specified. A timing budget item once the SRAM macro is chosen.
3. Reset scope, polarity, and synchronicity for datapath state (§10) — entirely undocumented.
   The *state that needs clearing* is already reasoned out in §10; the exact reset scheme is a
   standard RTL convention decision.

---

## 13. Architecture Contract for Future RTL

This section freezes the *architecture* described above — the interface, ownership, and
behavioral contract — for review. It does not freeze implementation details; the items marked
OPEN throughout this document, and organized in §12, remain to be resolved before or during
RTL work in the `rmc` repository. A future RTL implementation of this datapath must satisfy:

- **Input from phase packer:** accept `{op, tag, sram_addr}` at CAS-commit, one per issued CAS.
  `tag` is opaque and threaded through unmodified to completion. `sram_addr` is `wd_slot` for
  WR, `dbuf_addr` for RD.
- **WR behavior:** on CAS-commit for a write, arm a depth-`CWL` delay line carrying `wd_slot`;
  on launch, perform exactly one 512-bit read of `WD_SRAM` at `wd_slot`, serialize it onto
  `dfi_wrdata` at 2×gear beats/`mc_clk`, and assert `wr_done` (self-timed, no PHY
  acknowledgment) when the last beat has been driven.
- **RD behavior:** on CAS-commit for a read, arm a depth-`CL` delay line carrying
  `{tag, dbuf_addr}`; on launch, begin capturing `dfi_rddata` at 2×gear beats/`mc_clk`;
  once a full 512-bit line has been accumulated, perform exactly one 512-bit write of
  `RD_SRAM` at `dbuf_addr`, and assert `rd_done`.
- **WD_SRAM/RD_SRAM ownership:** both are CIF-owned memories, consumed by MCC only through the
  defined interface (a 512-bit read at `wd_slot`, a 512-bit write at `dbuf_addr`). `RD_SRAM` is
  documented as dual-domain (MC + CIF ports); `WD_SRAM`'s exact cross-domain implementation is
  OPEN and must be confirmed with CIF before/during RTL (§4.1, §12). The RTL must not
  introduce an MCC-local bulk data buffer or CDC FIFO for write or read data — the only
  data-bearing memory access from the datapath is the single 512-bit `WD_SRAM` read per write
  packet and the single 512-bit `RD_SRAM` write per read packet.
- **BL16 @ 1:4 geometry:** DQ width 32 bits; BL16 = 512 bits = one SRAM line; at gear 1:4,
  2×gear = 8 beats/`mc_clk`, so one BL16 burst spans 2 `mc_clk` cycles. The accumulator and
  splitter are the only blocks aware of the gear ratio; the SRAM-facing side of the datapath
  must stay gear-agnostic (always a single 512-bit access per packet).
- **DFI interfaces:** drive `dfi_wrdata` for writes, consume `dfi_rddata` for reads; drive
  `dfi_address`/`cs` per phase is the phase packer's responsibility, not this datapath's.
- **Completion behavior:** assert `wr_done`/`rd_done` per §8, feed a shared completion path
  that forwards `{tag, status}` (concretely `{rob_index, pkt_num, status}`) to CIF via an async
  FIFO.
- **Reset behavior:** must clear delay-line occupancy, accumulator/serializer in-progress
  state, and any pending completion pulses. Exact reset scheme is OPEN (§10, §12.2) — a
  parameter/detail item, resolvable during RTL, not an architectural blocker.
- **Explicit OPEN items:** §12.1's six items are architectural decisions that should be settled
  before this contract is treated as review-frozen (do not guess at them here). §12.2's three
  items are parameters/details (numeric `CWL`/`CL`, `WD_SRAM`/`RD_SRAM` access latency, reset
  scheme) that do not change the architecture above and may be resolved during RTL work,
  against JEDEC/DFI 5.2 spec and CIF-side design as needed.
