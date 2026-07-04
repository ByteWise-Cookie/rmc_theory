# RMC RTL Skeleton — Block Manifest

Baseline: handoff v1.9.8, §5 block list. All stubs: SystemVerilog, ports only, `// TODO: implement` body, import `rmc_pkg::*`.

## Status

- **29 / 31** internal blocks stubbed
- **Not stubbed:** Per-Rank FSM Table (§9B), Global Timing Table (§9C)
- **Out of RTL scope:** DDR PHY (#32), DDR5 DRAM (#33) — DFI boundary only

## Package

`rtl/pkg/rmc_pkg.sv` — all §2 params + typedefs (`bank_state_e`, `rank_state_e`, `req_status_e`, `wr_status_t`, `rd_status_t`, `bank_fsm_t`). Every stub imports this; no other file defines a param.

## Block Map

| # | Block | File | Interface style |
|---|---|---|---|
| 1 | AXI Write Port | `cif/axi_wr_port.sv` | valid-ready (AXI4) |
| 2 | AXI Read Port | `cif/axi_rd_port.sv` | valid-ready (AXI4) |
| 3 | AMU | `cif/amu.sv` | combinational |
| 4 | Burst Splitter | `cif/burst_splitter.sv` | valid-credit |
| 5 | ROB | `cif/rob.sv` | indexed alloc/retire |
| 6 | Merge Logic | `cif/merge_logic.sv` | valid-credit |
| 7 | Async REQ FIFO | `cif/async_req_fifo.sv` | credit-push write / valid-credit read (CDC) |
| 8 | Async RESP FIFO | `cif/async_resp_fifo.sv` | credit-push write / valid-credit read (CDC) |
| 9 | Write Data Buffer | `mc_core/wdb.sv` | indexed SRAM r/w |
| 10 | WR_TCAM | `mc_core/wr_tcam.sv` | combinational search + indexed write |
| 11 | RD_TCAM | `mc_core/rd_tcam.sv` | combinational search + indexed write |
| 12 | WR Status Reg | `mc_core/wr_status_reg.sv` | indexed r/w |
| 13 | RD Status Reg | `mc_core/rd_status_reg.sv` | indexed r/w |
| 14 | WR Watermark Mgr | `mc_core/wr_watermark_mgr.sv` | req/gnt alloc + indexed retire |
| 15 | RD Watermark Mgr | `mc_core/rd_watermark_mgr.sv` | req/gnt alloc + indexed retire |
| 16 | RAW Bypass Mgr | `mc_core/raw_bypass_mgr.sv` | combinational |
| 17 | Merge Unit | `mc_core/merge_unit.sv` | combinational |
| 18 | Hold-Forward 2-deep | `mc_core/hold_forward.sv` | 2-src valid arbitration |
| 19 | Bank Activity Ctr | `mc_core/bank_activity_ctr.sv` | indexed counters |
| 20 | Global Cycle Counter | `mc_core/gc_counter.sv` | free-running, no handshake |
| 21 | timing_reg_file | `mc_core/timing_reg_file.sv` | CSR write, multi-port read |
| 22 | Scheduler | `mc_core/scheduler.sv` | 5-stage pipeline, internal |
| 23 | Bank Partition Ctrl | `mc_core/bank_partition_ctrl.sv` | internal state |
| 24 | Per-Bank FSM Table | `mc_core/per_bank_fsm_table.sv` | indexed r/w |
| 25 | Per-Rank FSM Table | — | **not created** |
| 26 | Global Timing Table | — | **not created** |
| 27 | Maintenance Engine | `mc_core/maintenance_engine.sv` | internal FSM + DFI mux |
| 28 | Write Data Path | `mc_core/write_data_path.sv` | streaming → DFI |
| 29 | Read Data Path | `mc_core/read_data_path.sv` | streaming ← DFI |
| 30 | Error Handler | `mc_core/error_handler.sv` | monitor |
| 31 | Config Registers | `mc_core/config_regs.sv` | AXI4-Lite CSR |
| — | Top | `top/rmc_top.sv` | instantiates all above, ports unconnected |

## Known Gaps

- `req_data` / `wr_data` on both async FIFOs and AXI ports are raw `logic`, not struct-typed — needs a packed `req_t`/`resp_t` once field list is final
- `N_WR_ENTRIES` defaults to 64 in `rmc_pkg.sv` — unresolved vs 96 (§3 conflict, flows into `wr_tcam`, `wr_status_reg` sizing)
- `rmc_top.sv`: all 24 instances present, zero ports wired (`/* TODO connect */`)
- No FSM bodies anywhere — every stub is port-list only

## Suggested Next Order

1. Resolve `N_WR_ENTRIES`, starvation-threshold, undefined-width items (prior review notes)
2. Add `per_rank_fsm_table.sv`, `global_timing_table.sv`
3. Define `req_t`/`resp_t` structs, replace raw `logic` FIFO payloads
4. Fill lowest-dependency bodies first: `gc_counter` → `per_bank_fsm_table` → `wr_tcam`/`rd_tcam` → `scheduler`
