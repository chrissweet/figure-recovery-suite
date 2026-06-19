#!/usr/bin/env python3
"""Chart 6 — scatter plot with asymmetric error bars (both x and y).

Feature stressed: §4 error-cap detection in the scatter context. Each
marker has four caps (upper-y, lower-y, left-x, right-x); the cap
length is per-point asymmetric. The extractor must:
  1. Find marker centroid (filled circles, blue)
  2. Walk the column upward from the marker until the upper y-cap
     (small horizontal stroke)
  3. Walk downward until the lower y-cap
  4. Walk left from the marker for the left x-cap, right for the right
     x-cap

This stresses recipe §4 in the two ways the aedes corpus mostly didn't:
asymmetric caps (upper ≠ lower) and x-error bars (every aedes chart
only had y-error bars).
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4256
CHART_ID = "06-scatter-asym-errbars"


def main():
    rng = np.random.default_rng(SEED)
    n = 8
    x = np.linspace(2, 30, n)
    y = 5 + 0.7 * x + rng.normal(0, 1.2, n)
    # Asymmetric error: lower != upper. Larger errors at higher x.
    xerr_lo = 0.5 + 0.05 * x
    xerr_hi = 0.3 + 0.04 * x
    yerr_lo = 1.0 + 0.05 * x
    yerr_hi = 0.6 + 0.03 * x

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    ax.errorbar(x, y,
                xerr=[xerr_lo, xerr_hi],
                yerr=[yerr_lo, yerr_hi],
                fmt="o", color="C0", markersize=7, markeredgecolor="black",
                markeredgewidth=0.7, ecolor="black", capsize=4,
                elinewidth=0.9, label="Measurement")
    ax.set_xlabel("Drive current (mA)")
    ax.set_ylabel("Photon count (×10³ / s)")
    ax.set_title("Synthetic #6 — scatter with asymmetric x/y error bars")
    ax.set_xlim(0, 35)
    ax.set_ylim(0, 35)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    layers = [
        {
            "layer_idx": 0, "layer_type": "Scatter Plot",
            "series": "Measurement",
            "points": [(float(xi), float(yi)) for xi, yi in zip(x, y)],
        },
        # x error caps (left and right)
        {
            "layer_idx": 1, "layer_type": "ErrorBarLayer",
            "series": "x_err_left",
            "points": [(float(xi - xl), float(yi))
                        for xi, yi, xl in zip(x, y, xerr_lo)],
        },
        {
            "layer_idx": 1, "layer_type": "ErrorBarLayer",
            "series": "x_err_right",
            "points": [(float(xi + xh), float(yi))
                        for xi, yi, xh in zip(x, y, xerr_hi)],
        },
        # y error caps (upper and lower)
        {
            "layer_idx": 1, "layer_type": "ErrorBarLayer",
            "series": "y_err_upper",
            "points": [(float(xi), float(yi + yh))
                        for xi, yi, yh in zip(x, y, yerr_hi)],
        },
        {
            "layer_idx": 1, "layer_type": "ErrorBarLayer",
            "series": "y_err_lower",
            "points": [(float(xi), float(yi - yl))
                        for xi, yi, yl in zip(x, y, yerr_lo)],
        },
    ]

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": ("asymmetric x AND y error bars on every point. "
                              "Stress for §4 cap detection (both axes, "
                              "lower≠upper)."),
        "chart_type": "scatter_errbars",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Drive current (mA)",
        "y_axis_title": "Photon count (×10³ / s)",
        "x_axis_unit": "mA",
        "y_axis_unit": "x10^3 / s",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #6 — scatter with asymmetric x/y error bars",
        "series_legend": [{
            "series_id": "Measurement", "color": "#1f77b4",
            "marker_style": "filled_circle",
            "source_label": "Measurement",
        }],
        "generator": __file__,
        "seed": SEED,
        "cap_test": ("For each i: marker centroid at (x[i], y[i]); "
                      "four caps at (x[i]-xerr_lo[i], y[i]), "
                      "(x[i]+xerr_hi[i], y[i]), (x[i], y[i]+yerr_hi[i]), "
                      "(x[i], y[i]-yerr_lo[i]). All visible (capsize=4)."),
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  ({n} points, asym caps on both axes)")


if __name__ == "__main__":
    main()
