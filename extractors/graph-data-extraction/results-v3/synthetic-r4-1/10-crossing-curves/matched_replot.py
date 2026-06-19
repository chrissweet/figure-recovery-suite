#!/usr/bin/env python3
"""matched_replot.py — Phase-4 closing-the-loop reconstruction for
synthetic-r4-1 / 10-crossing-curves.

Reads data.csv next to this script and renders both series in
matplotlib's default C0 blue (#1f77b4), the same color the source
chart uses. The whole point of this chart is that *both* series are
the same color — the legend reads them by ordering (rising vs
falling). Trying to color them differently here would mask the
extractor stressor; we deliberately keep them identical.
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))


def load_series(csv_path):
    by_series = defaultdict(list)
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            by_series[row["series"]].append(
                (float(row["x"]), float(row["y"])))
    for s in by_series:
        by_series[s].sort()
    return by_series


def main():
    series = load_series(os.path.join(HERE, "data.csv"))
    fig, ax = plt.subplots(figsize=(7, 4.5))

    # Same color on purpose — that's the stressor this chart is designed to
    # probe. Legend distinguishes the two by name, not by color.
    color = "#1f77b4"
    for label, points in series.items():
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, color=color, linewidth=2, label=label)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_xlabel("Independent variable x")
    ax.set_ylabel("Response y")
    ax.set_title("Synthetic #10 — crossing curves, same color")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")

    out_path = os.path.join(HERE, "replot.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
