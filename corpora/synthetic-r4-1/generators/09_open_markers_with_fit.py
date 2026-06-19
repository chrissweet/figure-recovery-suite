#!/usr/bin/env python3
"""Chart 9 — open markers fused with same-color solid fit curve.

Feature stressed: §3b curve subtraction in the hardest case. The fit
curve runs through every marker; the markers are *open* (hollow) circles
in the same color as the curve, so a naive black-and-white mask + CC
sees each marker as the curve's stroke "dipping" into a ring shape and
leaves it as a single fused blob.

The §3b recipe addresses this with per-column thin-run subtraction +
paired-edge preservation: a thin run on a marker preserves the top and
bottom rim, gets the middle stroke removed. This chart is the test:

  - 12 open circles, blue (matplotlib C0)
  - solid blue regression line through them
  - both at linewidth ≈ markeredgewidth so the predicate has to actually
    work the geometric test, not lean on color
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4259
CHART_ID = "09-open-markers-with-fit"


def main():
    rng = np.random.default_rng(SEED)
    n = 12
    x = np.linspace(0.5, 9.5, n)
    true_slope = 1.8
    true_intercept = 4.0
    y = true_intercept + true_slope * x + rng.normal(0, 0.5, n)

    # Fit a line through the data and evaluate it on a dense grid
    slope, intercept = np.polyfit(x, y, 1)
    x_dense = np.linspace(0, 10, 200)
    y_fit = intercept + slope * x_dense

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    ax.plot(x_dense, y_fit, color="C0", linestyle="-", linewidth=1.4,
            label=f"Linear fit (slope={slope:.2f}, intercept={intercept:.2f})")
    ax.plot(x, y, marker="o", markerfacecolor="white",
            markeredgecolor="C0", markeredgewidth=1.4, markersize=8,
            linestyle="None", label="Measurement")
    ax.set_xlabel("Independent x")
    ax.set_ylabel("Response y")
    ax.set_title("Synthetic #9 — open circles fused with same-color fit line")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 30)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    layers = [
        {"layer_idx": 0, "layer_type": "Scatter Plot",
         "series": "Measurement",
         "points": [(float(xi), float(yi)) for xi, yi in zip(x, y)]},
        {"layer_idx": 1, "layer_type": "Line Graph",
         "series": "Linear fit",
         "points": [(float(xd), float(yd))
                     for xd, yd in zip(x_dense[::10], y_fit[::10])]},
    ]

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": ("open markers fused with a same-color solid "
                              "fit curve through every point. §3b "
                              "per-column thin-run subtraction with "
                              "paired-edge preservation is the test."),
        "chart_type": "scatter_with_fit",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Independent x",
        "y_axis_title": "Response y",
        "x_axis_unit": None,
        "y_axis_unit": None,
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #9 — open circles fused with same-color fit line",
        "fit_params": {"slope": float(slope), "intercept": float(intercept)},
        "series_legend": [
            {"series_id": "Measurement", "color": "#1f77b4",
             "marker_style": "open_circle",
             "marker_edge_color": "#1f77b4",
             "source_label": "Measurement"},
            {"series_id": "Linear fit", "color": "#1f77b4",
             "line_style": "solid",
             "source_label": "Linear fit"},
        ],
        "generator": __file__,
        "seed": SEED,
        "subtraction_test": (
            "A naive `mask = (gray < 120) & color_match` will fuse every "
            "marker with the fit line — the fit line passes through the "
            "marker centroid and connects the top arc to the bottom arc. "
            "After §3b column-wise thin-run subtraction with paired-edge "
            "preservation, the markers should survive as ring-shaped CCs "
            "and the fit line should be removed."),
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  "
          f"({n} open markers + same-color fit line, "
          f"slope={slope:.2f})")


if __name__ == "__main__":
    main()
