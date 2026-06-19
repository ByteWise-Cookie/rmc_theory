"""
Report graphs: per-traffic-type comparisons across placements.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os


def plot_metric_by_traffic(df: pd.DataFrame, metric: str, outdir: str,
                            top_n: int = 12) -> str:
    """Bar chart: metric value per placement, grouped by traffic type."""
    traffics = df["traffic"].unique()
    fig, axes = plt.subplots(len(traffics), 1, figsize=(10, 3.2 * len(traffics)),
                              squeeze=False)
    for i, traffic in enumerate(traffics):
        ax = axes[i][0]
        d = df[df["traffic"] == traffic].sort_values(metric, ascending=False).head(top_n)
        ax.bar(d["placement"], d[metric], color="#2E6DA4")
        ax.set_title(f"{metric} — traffic: {traffic}", fontsize=10)
        ax.set_ylabel(metric, fontsize=9)
        ax.tick_params(axis="x", rotation=75, labelsize=7)
    fig.tight_layout()
    path = os.path.join(outdir, f"metric_{metric}.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_composite_ranking(tradeoff_df: pd.DataFrame, outdir: str, top_n: int = 15) -> str:
    d = tradeoff_df.head(top_n)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(d["placement"][::-1], d["composite_score"][::-1], color="#2A9D8F")
    ax.set_xlabel("composite score (higher = better)")
    ax.set_title("Top placements — composite score across all traffic types")
    fig.tight_layout()
    path = os.path.join(outdir, "composite_ranking.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_metric_heatmap(df: pd.DataFrame, metric: str, outdir: str,
                         top_n_placements: int = 20) -> str:
    """Placement x traffic heatmap for one metric."""
    pivot = df.pivot_table(index="placement", columns="traffic", values=metric, aggfunc="mean")
    # order by mean
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
    pivot = pivot.head(top_n_placements)
    fig, ax = plt.subplots(figsize=(8, max(4, 0.35 * len(pivot))))
    im = ax.imshow(pivot.values, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=7)
    ax.set_title(f"{metric} heatmap (placement x traffic)")
    fig.colorbar(im, ax=ax, shrink=0.7)
    fig.tight_layout()
    path = os.path.join(outdir, f"heatmap_{metric}.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path
