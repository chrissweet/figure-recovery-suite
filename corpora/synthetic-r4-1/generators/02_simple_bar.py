#!/usr/bin/env python3
"""Chart 2 — single-series vertical bar chart.

Feature stressed: §3a/§3b bar detection. One bar per categorical x; the
extractor must:
  1. Find the colored bar rectangles
  2. Locate each bar's top edge (row of the highest stroke pixel within
     the bar's column range)
  3. Convert (col_center, row_top) -> (x_value, y_value) via calibration

This is the baseline. Chart #3 will stress the multi-bar-per-x grouped
case the el-62/el-80 verifier flagged.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import data_to_image_px, write_chart  # noqa: E402

SEED = 4253
CHART_ID = "02-simple-bar"


def main():
    categories = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
    rng = np.random.default_rng(SEED)
    values = [12.4, 18.7, 9.2, 22.5, 15.1, 7.8]

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    x_positions = np.arange(len(categories))
    ax.bar(x_positions, values, width=0.65, color="C2",
           edgecolor="black", linewidth=0.8, label="Throughput")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(categories)
    ax.set_xlabel("Pipeline stage")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("Synthetic #2 — single-series vertical bars")
    ax.set_ylim(0, 25)
    ax.legend(loc="upper right", frameon=True)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()

    layers = [{
        "layer_idx": 0,
        "layer_type": "Grouped Column Chart",
        "series": "Throughput",
        "points": [(float(xp), float(v)) for xp, v in zip(x_positions, values)],
    }]

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": "single-series vertical bar chart, "
                            "baseline for bar_top predicate",
        "chart_type": "bar",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Pipeline stage",
        "y_axis_title": "Throughput (req/s)",
        "x_axis_unit": None,
        "y_axis_unit": "req/s",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #2 — single-series vertical bars",
        "x_categories": categories,
        "bar_width": 0.65,
        "series_legend": [{
            "series_id": "Throughput",
            "color": "#2ca02c",
            "fill_style": "solid",
            "edge_color": "#000000",
            "source_label": "Throughput",
        }],
        "generator": __file__,
        "seed": SEED,
        "bar_top_test": ("For each (x_position, value) in GT, the predicate "
                          "(value − by) / my should land within ε of the "
                          "topmost stroke row inside the bar's column span "
                          "[col_center − bar_width_px/2, col_center + "
                          "bar_width_px/2]."),
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  ({len(categories)} bars)")


if __name__ == "__main__":
    main()
