#!/usr/bin/env python3
"""
addr-map hash optimizer — CLI driver.

Usage pattern (cachesim/ripes style):
    config in -> sweep -> report out

Example:
    python3 main.py --addr-width 33 --ch 1 --subch 1 --rank 1 \\
        --bg 3 --bank 2 --row 17 --col 10 \\
        --traffic linear,strided,random,locality \\
        --n 50000 --outdir ./out
"""
import argparse
import os
import sys
import json
import pandas as pd

from config import make_config
from traffic import TrafficSpec
from sweep import run_sweep, best_per_metric, tradeoff_table
from report import plot_metric_by_traffic, plot_composite_ranking, plot_metric_heatmap


def parse_args():
    p = argparse.ArgumentParser(description="DDR address-map hash/placement optimizer")
    p.add_argument("--addr-width", type=int, required=True)
    p.add_argument("--ch", type=int, default=0, help="channel field width (bits)")
    p.add_argument("--subch", type=int, default=0, help="sub-channel field width (bits)")
    p.add_argument("--rank", type=int, default=0, help="rank field width (bits)")
    p.add_argument("--bg", type=int, default=0, help="bank group field width (bits)")
    p.add_argument("--bank", type=int, default=0, help="bank field width (bits)")
    p.add_argument("--row", type=int, default=0, help="row field width (bits)")
    p.add_argument("--col", type=int, default=0, help="column field width (bits)")
    p.add_argument("--beat-bytes", type=int, default=8)
    p.add_argument("--burst-len", type=int, default=16)
    p.add_argument("--density-bits", type=int, default=None,
                    help="optional: log2(device capacity in bytes), for a sanity check")

    p.add_argument("--traffic", type=str, default="linear,strided,random,locality",
                    help="comma list: linear,strided,random,locality,trace")
    p.add_argument("--trace-path", type=str, default=None)
    p.add_argument("--n", type=int, default=50_000, help="addresses per traffic run")
    p.add_argument("--stride", type=int, default=256, help="bytes, for strided traffic")
    p.add_argument("--working-set-kb", type=int, default=1024,
                    help="working set size (KB) for locality traffic")
    p.add_argument("--locality-p", type=float, default=0.9)
    p.add_argument("--seed", type=int, default=0)

    p.add_argument("--max-hash-variants", type=int, default=3,
                    help="XOR-hash variants tried per ordering (per hashable field)")
    p.add_argument("--max-orderings", type=int, default=None,
                    help="cap number of field orderings searched (None = all permutations)")
    p.add_argument("--window", type=int, default=32, help="parallelism sliding window size")

    p.add_argument("--outdir", type=str, default="./addrmap_out")
    p.add_argument("--no-plots", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    cfg = make_config(
        addr_width=args.addr_width,
        ch=args.ch, subch=args.subch, rank=args.rank,
        bg=args.bg, bank=args.bank, row=args.row, col=args.col,
        beat_bytes=args.beat_bytes, burst_len=args.burst_len,
        density_bits=args.density_bits,
    )

    n_fields = len(cfg.fields)
    print(f"config: addr_width={args.addr_width}b, offset_bits={cfg.offset_bits}, "
          f"fields={list(cfg.fields.keys())}")
    if n_fields > 7:
        print("warning: large field count -> ordering search space explodes (n!).")

    traffic_kinds = [t.strip() for t in args.traffic.split(",") if t.strip()]
    specs = []
    for kind in traffic_kinds:
        specs.append(TrafficSpec(
            name=kind, kind=kind, n=args.n, addr_width=args.addr_width,
            stride=args.stride, working_set_bytes=args.working_set_kb * 1024,
            locality_p=args.locality_p, seed=args.seed, trace_path=args.trace_path,
        ))

    print(f"running sweep: traffic={traffic_kinds}, n={args.n} addrs each")
    df = run_sweep(cfg, specs, max_hash_variants=args.max_hash_variants,
                    max_orderings=args.max_orderings, window=args.window,
                    verbose=not args.quiet)

    raw_path = os.path.join(args.outdir, "sweep_raw.csv")
    df.to_csv(raw_path, index=False)
    print(f"raw results -> {raw_path}")

    trade = tradeoff_table(df)
    trade_path = os.path.join(args.outdir, "tradeoff_table.csv")
    trade.to_csv(trade_path, index=False)
    print(f"tradeoff table -> {trade_path}")

    best = best_per_metric(df)
    best_path = os.path.join(args.outdir, "best_per_metric.csv")
    best.to_csv(best_path, index=False)
    print(f"best-per-metric -> {best_path}")

    print("\n=== TOP 5 PLACEMENTS (composite score) ===")
    print(trade.head(5).to_string(index=False))

    if not args.no_plots:
        for metric in ["row_hit_rate", "bank_conflict_rate", "avg_parallelism"]:
            path = plot_metric_by_traffic(df, metric, args.outdir)
            print(f"plot -> {path}")
        path = plot_composite_ranking(trade, args.outdir)
        print(f"plot -> {path}")
        path = plot_metric_heatmap(df, "row_hit_rate", args.outdir)
        print(f"plot -> {path}")
        path = plot_metric_heatmap(df, "bank_conflict_rate", args.outdir)
        print(f"plot -> {path}")

    summary = {
        "config": {
            "addr_width": args.addr_width, "offset_bits": cfg.offset_bits,
            "fields": {k: v.width for k, v in cfg.fields.items()},
        },
        "traffic": traffic_kinds,
        "n_placements_searched": df["placement"].nunique(),
        "n_total_runs": len(df),
        "best_overall": trade.iloc[0]["placement"] if len(trade) else None,
        "best_overall_score": float(trade.iloc[0]["composite_score"]) if len(trade) else None,
    }
    with open(os.path.join(args.outdir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsummary -> {os.path.join(args.outdir, 'summary.json')}")


if __name__ == "__main__":
    main()
