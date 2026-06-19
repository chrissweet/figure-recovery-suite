#!/usr/bin/env python3
"""Chart 3 — grouped bar chart with error bars.

Feature stressed: the bar_top + error_cap predicate combination that
the per-element verifier flagged on el-62 (0.64 PASS) and el-80 (0.43
PASS). On those real charts, the bar_top predicate used col = (x − bx) / mx,
i.e. it assumed one bar at each x. For grouped bars, each group's k
bars are offset by ±(k/2 · bar_width) from the group's x. The extractor
must recover the per-bar offset to land on the correct column for the
bar_top probe.

Layout: 5 groups (Q1-Q5), 3 series per group (Baseline / Tuned / Tuned+JIT),
visible error bars (asymmetric) on every bar. The error bars are a
secondary stress: the cap predicate needs to find the upper and lower
horizontal cap of each error bar, which means searching ABOVE the bar
top (not from the marker as in scatter plots).
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4254
CHART_ID = "03-grouped-bar-errbars"


def main():
    rng = np.random.default_rng(SEED)
    groups = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    series_names = ["Baseline", "Tuned", "Tuned+JIT"]
    # Hand-picked so each group has visible spread
    values = np.array([
        [42.0, 58.0, 71.0],   # Q1
        [45.0, 63.0, 78.0],   # Q2
        [49.0, 67.0, 82.0],   # Q3
        [51.0, 70.0, 85.0],   # Q4
        [54.0, 74.0, 89.0],   # Q5
    ])
    # Asymmetric error bars: lower, upper
    yerr_lower = np.array([
        [3.0, 4.5, 5.5], [3.2, 4.8, 5.8], [3.5, 5.0, 6.0],
        [3.7, 5.2, 6.2], [4.0, 5.5, 6.5],
    ])
    yerr_upper = np.array([
        [2.5, 3.5, 4.0], [2.7, 3.8, 4.2], [3.0, 4.0, 4.5],
        [3.2, 4.2, 4.8], [3.5, 4.5, 5.0],
    ])

    n_series = len(series_names)
    bar_width = 0.25
    x_positions = np.arange(len(groups))

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=100)
    colors = ["C0", "C1", "C2"]
    bar_centers = []
    for si, name in enumerate(series_names):
        offset = (si - (n_series - 1) / 2) * bar_width
        centers = x_positions + offset
        bar_centers.append(centers.tolist())
        ax.bar(centers, values[:, si], width=bar_width, color=colors[si],
               edgecolor="black", linewidth=0.7, label=name,
               yerr=[yerr_lower[:, si], yerr_upper[:, si]],
               error_kw={"ecolor": "black", "capsize": 4, "elinewidth": 0.9})
    ax.set_xticks(x_positions)
    ax.set_xticklabels(groups)
    ax.set_xlabel("Benchmark window")
    ax.set_ylabel("Throughput (kops/s)")
    ax.set_title("Synthetic #3 — grouped bars, asymmetric error bars")
    ax.set_ylim(0, 110)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()

    layers = []
    for si, name in enumerate(series_names):
        pts = [(float(bar_centers[si][gi]), float(values[gi, si]))
                for gi in range(len(groups))]
        layers.append({
            "layer_idx": 0, "layer_type": "Grouped Column Chart",
            "series": name, "points": pts,
        })
        # Upper error caps: x at bar center, y at value + yerr_upper
        upper_pts = [(float(bar_centers[si][gi]),
                       float(values[gi, si] + yerr_upper[gi, si]))
                      for gi in range(len(groups))]
        layers.append({
            "layer_idx": 1, "layer_type": "ErrorBarLayer",
            "series": f"{name}_err_upper", "points": upper_pts,
        })
        # Lower error caps
        lower_pts = [(float(bar_centers[si][gi]),
                       float(values[gi, si] - yerr_lower[gi, si]))
                      for gi in range(len(groups))]
        layers.append({
            "layer_idx": 1, "layer_type": "ErrorBarLayer",
            "series": f"{name}_err_lower", "points": lower_pts,
        })

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": ("grouped bars (multi-bar-per-x position) + "
                              "asymmetric error caps. Directly mirrors the "
                              "el-62 / el-80 verifier failures."),
        "chart_type": "grouped_bar",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Benchmark window",
        "y_axis_title": "Throughput (kops/s)",
        "x_axis_unit": None,
        "y_axis_unit": "kops/s",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #3 — grouped bars, asymmetric error bars",
        "x_categories": groups,
        "bar_width": float(bar_width),
        "n_series_per_group": n_series,
        "series_offsets": [(si - (n_series - 1) / 2) * bar_width
                            for si in range(n_series)],
        "series_legend": [
            {"series_id": series_names[0], "color": "#1f77b4",
             "fill_style": "solid", "source_label": "Baseline"},
            {"series_id": series_names[1], "color": "#ff7f0e",
             "fill_style": "solid", "source_label": "Tuned"},
            {"series_id": series_names[2], "color": "#2ca02c",
             "fill_style": "solid", "source_label": "Tuned+JIT"},
        ],
        "generator": __file__,
        "seed": SEED,
        "bar_top_test": (
            "For each (bar_center_x, value) in GT, "
            "col = (bar_center_x − bx) / mx must land within ε of the "
            "topmost stroke row inside the bar's column span. "
            "If the extractor uses col = (group_index − bx) / mx instead, "
            "ALL three series collapse to the same column at each group's "
            "center, and the predicate will pick whichever bar happens to "
            "be at that column. This is the el-62/el-80 failure mode."),
        "error_cap_test": (
            "Each upper cap should be at row = (value + yerr_upper − by) / my "
            "centered at the bar's column. Lower caps mirror at "
            "(value − yerr_lower − by) / my. Cap width ≈ 4 px (capsize=4)."),
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  "
          f"({len(groups)} groups × {n_series} series, with error bars)")


if __name__ == "__main__":
    main()
