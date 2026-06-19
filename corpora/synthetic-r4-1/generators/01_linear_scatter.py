#!/usr/bin/env python3
"""Chart 01 — linear-axes scatter, default matplotlib palette.

Feature stressed: baseline / harness sanity. If this doesn't round-trip,
none of the others will.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4242
CHART_ID = "01-linear-scatter"


def main():
    rng = np.random.default_rng(SEED)
    series_specs = [
        {"name": "A", "color": "C0", "marker": "o",
         "n": 15, "x_range": (0, 10), "y_intercept": 2.0, "slope": 0.8},
        {"name": "B", "color": "C1", "marker": "s",
         "n": 12, "x_range": (0, 10), "y_intercept": 4.0, "slope": 0.3},
        {"name": "C", "color": "C2", "marker": "D",
         "n": 10, "x_range": (0, 10), "y_intercept": 6.0, "slope": -0.2},
    ]
    series_pts = {}
    for spec in series_specs:
        xs = rng.uniform(*spec["x_range"], spec["n"])
        ys = spec["y_intercept"] + spec["slope"] * xs + rng.normal(
            0, 0.5, spec["n"])
        pts = [(round(float(x), 4), round(float(y), 4))
                for x, y in sorted(zip(xs, ys))]
        series_pts[spec["name"]] = pts

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    for spec in series_specs:
        xs = [p[0] for p in series_pts[spec["name"]]]
        ys = [p[1] for p in series_pts[spec["name"]]]
        ax.scatter(xs, ys, c=spec["color"], marker=spec["marker"],
                   s=50, edgecolors="black", linewidths=0.5,
                   label=f"Series {spec['name']}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Concentration (mol/L)")
    ax.set_title("Synthetic #01 — linear scatter")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0, 12)
    ax.legend(loc="upper right", frameon=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    layers = [
        {"layer_idx": 0, "layer_type": "Scatter Plot", "series": s["name"],
         "points": series_pts[s["name"]]} for s in series_specs
    ]
    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": "baseline / harness sanity",
        "chart_type": "scatter",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Time (s)",
        "y_axis_title": "Concentration (mol/L)",
        "x_axis_unit": "s",
        "y_axis_unit": "mol/L",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #01 — linear scatter",
        "series_legend": [
            {"series_id": s["name"], "color": s["color"],
             "marker_shape": s["marker"],
             "source_label": f"Series {s['name']}"}
            for s in series_specs
        ],
        "generator": __file__,
        "seed": SEED,
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}")


if __name__ == "__main__":
    main()
