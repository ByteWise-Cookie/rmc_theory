# addrmap-tool

Address-map (DRAM address hashing) optimizer and sweep engine for a memory controller. Sweeps address-field placements against synthetic traffic patterns and ranks them by DRAM-efficiency metrics — row-hit rate, bank-conflict rate, average parallelism.

Modeled after cachesim/Ripes-style sweep tools: `config in → all placements × all traffic → metrics out`.

## Modules

| File | Role |
|---|---|
| `main.py` | CLI driver / entry point |
| `sweep.py` | Sweep engine (sim core) |
| `placement.py` | Address-field placement generation |
| `traffic.py` | Traffic pattern generators (linear, strided, random, locality) |
| `metrics.py` | DRAM-efficiency metrics |
| `report.py` | Plots + ranking tables |
| `config.py` | Configuration |

## Usage

```
python main.py --addr-width <bits> \
  --ch 0 --subch 0 --rank 0 --bg 2 --bank 2 --row 16 --col 10 \
  --beat-bytes 8 --burst-len 16 \
  --traffic linear,strided,random,locality \
  --n 50000 --stride 256 --working-set-kb 1024
```

Address-field widths (`--ch/--subch/--rank/--bg/--bank/--row/--col`) define the address map under test. Traffic knobs (`--n`, `--stride`, `--working-set-kb`) shape the synthetic access streams.

## Output

Results land in a run directory (see `demo_run/` for an example):

- `sweep_raw.csv` — every placement × traffic result
- `best_per_metric.csv`, `composite_ranking.png` — rankings
- `tradeoff_table.csv`, `summary.json` — summary
- `heatmap_*.png`, `metric_*.png` — per-metric plots

## Related

`RMC_block_io_map.md` — RMC block-level I/O port map (reference doc kept alongside).
