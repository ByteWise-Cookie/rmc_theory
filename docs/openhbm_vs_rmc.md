# OpenHBM vs RMC — Comparison

Repo: `github.com/Netie-AI/OpenHBM` (Netie Open HBM). JEDEC JESD270-4A HBM4 controller + PHY-shim + RISC-V LPU. Apache-2.0 RTL. Status: v0.2.0, `hbm4_ctrl` = 14 RTL sources, Phase-1 skeleton (their term).

Closest analog to RMC: `hw/ip/hbm4_ctrl/` (controller) + `hw/ip/addr_map/` (≈ our AMU).

---

## Why the Python

None of it is synthesizable RTL — RTL is 100% SystemVerilog. Python shows up in four unrelated roles:

| Role | Path | Purpose |
|---|---|---|
| DV golden reference | `hw/ip/*/dv/env/*_ref.py` | Per-IP pure-Python behavioral model; cocotb testbench scoreboards RTL against it. Mandatory per `CLAUDE.md` step 6 for every block. |
| cocotb tests | `hw/ip/*/dv/tests/test_*.py` | Directed + `pyvsc` constrained-random, drives the RTL via cocotb |
| PD/ASIC flow automation | `pd/sc_flows/*.py` | SiliconCompiler flow scripts, one per PDK (sky130, ihp130, asap7, freepdk45) |
| Agent-eval CI harness | `tools/agent_eval/` | Scores AI-agent-authored RTL: lint→sim→coverage→formal→mutation→numeric gate (≥80/100 to merge) |
| Design reference (not code) | `hw/vendor/litedram_ref.lock.hjson` | Pins upstream LiteDRAM (Python/Migen) as **read-only structural reference** for scheduler/bank-machine pattern — explicitly "NOT vendored for synthesis" |

No analog to our OQ-19b trace-analysis script exists in the repo by name — closest relevant prior art is `addr_map_xor.sv`, see below.

---

## Matches

| Area | RMC | OpenHBM |
|---|---|---|
| Bank topology | 16 banks (`N_BG`=4 × 4/BG) | 16 banks (`BANK_GROUPS`=4 × `BANKS_PER_BG`=4) |
| AXI data width | 64b | `AXI_DATA_W`=64 — exact match |
| Address mapping | XOR hash, CSR-configurable | XOR hash (row field), region-table configurable |
| Temp-aware refresh | HOT (>85°C) → tREFI/2 | 3-band: COLD/NORMAL/HOT → 2×/1×/0.5× tREFI |
| CDC discipline | single crossing, credit-based | mandated primitives (`prim_sync_2flop`, `prim_fifo_async`), no direct `always_ff` capture across domains allowed |
| Methodology | skeleton (ports+params) before RTL body | explicitly "Phase-1 skeleton" — same stage |

---

## Differences

| Area | RMC | OpenHBM |
|---|---|---|
| Scheduling | SJF, 5-stage, TCAM-assisted, single class | DWRR round-robin across 4 QoS classes + starvation guard |
| QoS | explicitly **not supported** (§3, "not justified") | first-class: `qos_class_e`, per-class weights, `QosStarvationLimit` |
| Bank FSM richness | 8 states (splits ACTIVATING/PRECHARGING out) | 3 states (`IDLE/ACTIVE/REFRESH`) — timer stub, doc admits tRCD/tRP/tRAS not yet real counters |
| Timing params | runtime CSR (`timing_reg_file`), no hardcoded values by design | compile-time `parameter`/`localparam` in pkg (`T_RCD=4` etc.), several with lint-waived non-standard naming |
| Addr mapping scope | single global AMU | multi-region table, 3 selectable modes: `CH_STRIPED`, `BANK_INTERLEAVED`, `ROW_STATIONARY` |
| RAS | not present as a block | dedicated `hbm4_ctrl_ras.sv`: CE/UE classification, log FIFO |
| PMU | not present | dedicated `hbm4_ctrl_pmu.sv`: NORMAL/THROTTLE/GATED, activity-window threshold |
| Training FSM | not in block list (assumed PHY-side) | explicit `hbm4_ctrl_training.sv`: WRLVL/RDLVL/DONE/ERR + timeout |
| CSR generation | hand-designed `config_regs` block | Hjson spec → `regtool.py` codegen (OpenTitan-derived), hand-written decoders rejected at review |
| Primitive reuse | none mandated | `prim_generic`/`lowrisc_prim`/`pulp_common_cells` mandatory, "never re-roll a primitive" |

---

## Direct relevance to OQ-19b

`hw/ip/addr_map/rtl/addr_map_xor.sv` already implements three selectable interleave granularities as a per-region mode, each bit-slicing `{pch, ch, bg, ba, row, col}` off the offset differently:

- `CH_STRIPED` — channel/pseudo-channel bits lowest (finest interleave)
- `BANK_INTERLEAVED` — bank bits below channel bits
- `ROW_STATIONARY` — column stays lowest, channel/row coarsest

Worth reading before writing the OQ-19b sweep script — it's a working, already-decided answer to "where in the address do the interleave bits go" for a directly comparable JEDEC DDR-family controller. Doesn't resolve *granularity* (that's still a traffic-trace question) but removes the bit-layout design space down to picking among a similar 3-mode family.

---

## Flag — not acted on

`CLAUDE.md` (their AI-agent contract file) ends with an embedded shell heredoc block (`cat >> CLAUDE.md << 'EOF' ... EOF`, `echo ... >> .gitignore`) formatted to look like an instruction for an agent reading the file to execute. Not run — treated as inert file content only. Flagging in case it's unintentional on their end.
