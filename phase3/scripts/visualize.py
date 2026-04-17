#!/usr/bin/env python3
"""
Phase 3b: Visualize feature distributions of normal DoH vs DoH tunneling.

Produces:
    - feature_distributions.png : 5x5 grid of per-feature histograms
    - feature_summary.txt       : per-feature mean/median/std for each class
    - correlation_heatmap.png   : feature correlation matrix

Usage:
    python3 visualize.py \\
        --csv /opt/phase3-results/features.csv \\
        --output-dir /opt/phase3-results/plots
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

FEATURES_25 = [
    "num_packets", "num_bytes", "bytes_up", "bytes_down", "bytes_ratio",
    "packets_per_sec", "bytes_per_sec", "packets_per_sec_up", "packets_per_sec_down",
    "size_mean", "size_std", "size_median", "size_min", "size_max", "size_p90",
    "iat_mean", "iat_std", "iat_median", "iat_max", "iat_min",
    "direction_changes", "longest_up_run", "longest_down_run",
    "burst_count", "max_burst_size",
]

CLASS_LABELS = {0: "normal DoH", 1: "DoH tunnel"}
CLASS_COLORS = {0: "#2E86AB", 1: "#E63946"}


def plot_feature_grid(df, out_path):
    ncols = 5
    nrows = int(np.ceil(len(FEATURES_25) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
    axes = axes.flatten()

    for ax, feature in zip(axes, FEATURES_25):
        for label, group in df.groupby("label"):
            values = group[feature].dropna().values
            if len(values) == 0:
                continue
            ax.hist(
                values, bins=25, alpha=0.55,
                color=CLASS_COLORS[label],
                label=CLASS_LABELS[label],
                density=True,
            )
        ax.set_title(feature, fontsize=10)
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(True, alpha=0.3)

    # Hide any unused axes
    for ax in axes[len(FEATURES_25):]:
        ax.axis("off")

    # Single legend for the whole figure
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=11,
               bbox_to_anchor=(0.5, 1.01))
    fig.suptitle("Phase 3b: Feature distributions — normal DoH vs DoH tunneling",
                 fontsize=14, y=1.03)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def write_summary(df, out_path):
    lines = []
    lines.append("Phase 3b: Per-feature summary statistics")
    lines.append("=" * 78)
    header = f"{'feature':<22} {'class':<12} {'mean':>12} {'median':>12} {'std':>12}"
    lines.append(header)
    lines.append("-" * 78)
    for feature in FEATURES_25:
        for label, group in df.groupby("label"):
            vals = group[feature].dropna()
            lines.append(
                f"{feature:<22} {CLASS_LABELS[label]:<12} "
                f"{vals.mean():>12.3f} {vals.median():>12.3f} {vals.std():>12.3f}"
            )
        lines.append("-" * 78)
    Path(out_path).write_text("\n".join(lines) + "\n")
    print(f"  wrote {out_path}")


def plot_correlation(df, out_path):
    corr = df[FEATURES_25].corr()
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(
        corr, cmap="coolwarm", center=0, square=True,
        cbar_kws={"shrink": 0.7}, linewidths=0.5, ax=ax,
        xticklabels=FEATURES_25, yticklabels=FEATURES_25,
    )
    ax.set_title("Feature correlation matrix (both classes combined)", fontsize=13)
    plt.xticks(rotation=75, ha="right", fontsize=9)
    plt.yticks(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def plot_top_separating_features(df, out_path, top_n=6):
    """Pick features with the largest normalized mean difference between classes."""
    normal = df[df["label"] == 0]
    tunnel = df[df["label"] == 1]

    scores = {}
    for f in FEATURES_25:
        n_mean = normal[f].mean()
        t_mean = tunnel[f].mean()
        pooled_std = df[f].std()
        if pooled_std > 0:
            scores[f] = abs(n_mean - t_mean) / pooled_std

    top = sorted(scores.items(), key=lambda kv: -kv[1])[:top_n]
    print("  Top separating features (normalized mean-diff):")
    for f, s in top:
        print(f"     {f:<22} {s:.2f}")

    ncols = 3
    nrows = int(np.ceil(top_n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows))
    axes = axes.flatten() if top_n > 1 else [axes]
    for ax, (feature, score) in zip(axes, top):
        for label, group in df.groupby("label"):
            vals = group[feature].dropna().values
            ax.hist(
                vals, bins=25, alpha=0.6,
                color=CLASS_COLORS[label], label=CLASS_LABELS[label],
                density=True,
            )
        ax.set_title(f"{feature}  (separation={score:.2f})", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Top features by class separation", fontsize=14, y=1.01)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def main():
    p = argparse.ArgumentParser(description="Phase 3b visualization")
    p.add_argument("--csv", required=True, help="features CSV from extract-features.py")
    p.add_argument("--output-dir", required=True, help="directory for plots / summary")
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    print(f"Loaded {len(df)} rows from {args.csv}")
    print(f"  label distribution: {df['label'].value_counts().to_dict()}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_feature_grid(df, out_dir / "feature_distributions.png")
    plot_top_separating_features(df, out_dir / "top_separating_features.png")
    plot_correlation(df, out_dir / "correlation_heatmap.png")
    write_summary(df, out_dir / "feature_summary.txt")

    print()
    print("Visualization done.")


if __name__ == "__main__":
    main()
