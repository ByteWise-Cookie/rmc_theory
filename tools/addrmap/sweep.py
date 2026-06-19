"""
Sweep engine: config in -> all placements x all traffic -> metrics out.
This is the "sim core" — like cachesim's sweep mode.
"""
import time
import numpy as np
import pandas as pd
from dataclasses import asdict
from typing import List, Dict, Optional

from config import MCConfig
from placement import generate_placements, Placement
from traffic import TrafficSpec, generate
from metrics import evaluate, Metrics


def run_sweep(
    cfg: MCConfig,
    traffic_specs: List[TrafficSpec],
    max_hash_variants: int = 3,
    max_orderings: Optional[int] = None,
    window: int = 32,
    verbose: bool = True,
) -> pd.DataFrame:
    placements = generate_placements(cfg, max_hash_variants=max_hash_variants,
                                      max_orderings=max_orderings)
    rows = []
    t0 = time.time()
    total_runs = len(placements) * len(traffic_specs)
    run_i = 0

    # cache generated traffic per spec name (avoid regen per placement)
    traffic_cache = {}
    for spec in traffic_specs:
        traffic_cache[spec.name] = generate(spec)

    for placement in placements:
        for spec in traffic_specs:
            addrs = traffic_cache[spec.name]
            m = evaluate(placement, addrs, window=window)
            rows.append({
                "placement": placement.name,
                "order": "-".join(placement.order),
                "traffic": spec.name,
                "traffic_kind": spec.kind,
                **asdict(m),
            })
            run_i += 1
            if verbose and run_i % max(1, total_runs // 10) == 0:
                pct = 100 * run_i / total_runs
                print(f"  sweep {run_i}/{total_runs} ({pct:.0f}%) "
                      f"[{time.time()-t0:.1f}s elapsed]")

    df = pd.DataFrame(rows)
    if verbose:
        print(f"sweep done: {total_runs} runs in {time.time()-t0:.1f}s")
    return df


def best_per_metric(df: pd.DataFrame, traffic: Optional[str] = None) -> pd.DataFrame:
    """Best placement per metric, optionally filtered to one traffic pattern."""
    d = df if traffic is None else df[df["traffic"] == traffic]
    metrics_higher_better = ["row_hit_rate", "avg_parallelism"]
    metrics_lower_better = ["row_miss_rate", "bank_conflict_rate",
                             "ch_balance_std", "subch_balance_std",
                             "rank_balance_std", "bg_balance_std",
                             "bank_balance_std"]
    out = []
    for m in metrics_higher_better:
        if m in d.columns:
            best = d.loc[d[m].idxmax()]
            out.append({"metric": m, "best_placement": best["placement"],
                        "traffic": best["traffic"], "value": best[m]})
    for m in metrics_lower_better:
        if m in d.columns:
            best = d.loc[d[m].idxmin()]
            out.append({"metric": m, "best_placement": best["placement"],
                        "traffic": best["traffic"], "value": best[m]})
    return pd.DataFrame(out)


def tradeoff_table(df: pd.DataFrame) -> pd.DataFrame:
    """Average each metric across all traffic patterns, per placement —
    a single-number tradeoff summary."""
    agg = df.groupby("placement").agg({
        "row_hit_rate": "mean",
        "row_miss_rate": "mean",
        "bank_conflict_rate": "mean",
        "ch_balance_std": "mean",
        "subch_balance_std": "mean",
        "rank_balance_std": "mean",
        "bg_balance_std": "mean",
        "bank_balance_std": "mean",
        "avg_parallelism": "mean",
    }).reset_index()
    # composite score: reward hit rate + parallelism, penalize conflicts + imbalance
    agg["composite_score"] = (
        agg["row_hit_rate"] * 2.0
        + agg["avg_parallelism"] * 0.1
        - agg["bank_conflict_rate"] * 1.5
        - agg["bg_balance_std"] * 0.5
        - agg["bank_balance_std"] * 0.5
    )
    return agg.sort_values("composite_score", ascending=False).reset_index(drop=True)
