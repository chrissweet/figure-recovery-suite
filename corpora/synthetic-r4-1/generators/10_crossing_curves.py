#!/usr/bin/env python3
"""Chart 10 — two smooth curves in the SAME color that cross.

Feature stressed: §3 line/curve trace at a crossing. The per-column-median
trace from the original §3 recipe picks the median row across all stroke
pixels in a column. At the crossing it's ambiguous; just before and after
the crossing it picks the WRONG curve (whichever has its mask pixel in
between the two). The §3 recipe addition `trace_with_continuity()` is
spec'd but not implemented — this chart is the test case.

Curve A: y = 1.5 + 0.3·x + 0.04·x²   (rising, slight curvature)
Curve B: y = 8 − 0.5·x                (falling, linear)
They cross once around x ≈ 6.8, y ≈ 4.6.

Both drawn in the SAME color (matplotlib C0, blue) and same linestyle
(solid). A per-column-median trace will be visibly wrong at the
crossing; a continuity-tracking trace should follow each curve through.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4252
CHART_ID = "10-crossing-curves"


def main():
    x = np.linspace(0, 10, 80)
    series_specs = [
        {"name": "rising", "y": 1.5 + 0.3 * x + 0.04 * x ** 2,
         "label": "Series A (rising)"},
        {"name": "falling", "y": 8 - 0.5 * x,
         "label": "Series B (falling)"},
    ]

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    for spec in series_specs:
        ax.plot(x, spec["y"], color="C0", linestyle="-", linewidth=1.8,
                label=spec["label"])
    ax.set_xlabel("Independent variable x")
    ax.set_ylabel("Response y")
    ax.set_title("Synthetic #10 — crossing curves, same color")
    ax.set_xlim(-0.2, 10.2)
    ax.set_ylim(0, 10)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    layers = []
    for spec in series_specs:
        pts = [(round(float(xv), 4), round(float(yv), 4))
                for xv, yv in zip(x, spec["y"])]
        layers.append({
            "layer_idx": 0, "layer_type": "Line Graph",
            "series": spec["name"], "points": pts,
        })

    # Locate the crossing analytically (1.5+0.3x+0.04x² = 8-0.5x →
    # 0.04x² + 0.8x − 6.5 = 0)
    a, b, c = 0.04, 0.8, -6.5
    disc = (b * b - 4 * a * c) ** 0.5
    x_cross = (-b + disc) / (2 * a)
    y_cross = 1.5 + 0.3 * x_cross + 0.04 * x_cross ** 2

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": "two same-color curves crossing once",
        "chart_type": "line",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Independent variable x",
        "y_axis_title": "Response y",
        "x_axis_unit": None,
        "y_axis_unit": None,
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #10 — crossing curves, same color",
        "series_legend": [
            {"series_id": s["name"], "color": "#1f77b4",
             "line_style": "solid", "source_label": s["label"]}
            for s in series_specs
        ],
        "generator": __file__,
        "seed": SEED,
        "crossing": {
            "x": round(float(x_cross), 4),
            "y": round(float(y_cross), 4),
            "note": ("Single intersection. Per-column-median trace from "
                      "the original §3 recipe will visibly mis-attribute "
                      "in the ~0.5-unit x neighbourhood of the crossing; "
                      "trace_with_continuity() (seeded at the leftmost "
                      "column, tracked by trajectory slope) should follow "
                      "each curve through."),
        },
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  (crossing at x≈{x_cross:.2f}, y≈{y_cross:.2f})")


if __name__ == "__main__":
    main()
