#!/usr/bin/env python3
"""Chart 04 — log-y line plot.

Feature stressed: log axes. The existing calibration recipe assumes
linear y. On a log10 y-axis, tick labels (10, 100, 1000, …) sit at
equal pixel intervals, but the data values they represent are not
equally spaced. A linear least-squares fit through (pixel, value)
pairs will be visibly off.

This chart's ground_truth_calibration.json records
`y_axis.scale = "log10"` so a recipe / verifier that respects the
field gets the right answer; one that ignores it gets a measurable
linear-fit error.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4243
CHART_ID = "04-log-y-line"


def main():
    rng = np.random.default_rng(SEED)
    # Two series: an exponential decay y = a * exp(-k*x), and a power law
    # y = a * x^p. Both span 3 decades on the y axis.
    x = np.linspace(0.5, 10, 60)
    series_specs = [
        {"name": "exp_decay",
         "label": "Exponential: 100 e^(-0.5 t)",
         "color": "C3", "linestyle": "-",
         "y": 100 * np.exp(-0.5 * x)},
        {"name": "power_law",
         "label": "Power law: 500 / t^1.6",
         "color": "C4", "linestyle": "--",
         "y": 500 / (x ** 1.6)},
    ]

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    for spec in series_specs:
        ax.plot(x, spec["y"], color=spec["color"],
                linestyle=spec["linestyle"], linewidth=1.8,
                label=spec["label"])
    ax.set_yscale("log")
    ax.set_xlabel("Time t (s)")
    ax.set_ylabel("Signal magnitude (log scale)")
    ax.set_title("Synthetic #04 — log-y line plot")
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0.1, 1000)
    ax.legend(loc="upper right", frameon=True)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()

    layers = []
    for spec in series_specs:
        pts = [(round(float(xv), 4), round(float(yv), 4))
                for xv, yv in zip(x, spec["y"])]
        layers.append({
            "layer_idx": 0, "layer_type": "Line Graph",
            "series": spec["name"], "points": pts,
        })
    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": "log axes (y log10)",
        "chart_type": "line",
        "x_scale": "linear",
        "y_scale": "log10",
        "x_axis_title": "Time t (s)",
        "y_axis_title": "Signal magnitude",
        "x_axis_unit": "s",
        "y_axis_unit": None,
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #04 — log-y line plot",
        "series_legend": [
            {"series_id": s["name"], "color": s["color"],
             "line_style": s["linestyle"],
             "source_label": s["label"]}
            for s in series_specs
        ],
        "generator": __file__,
        "seed": SEED,
        "verifier_notes": (
            "The existing extractor recipe and the verifier's tick_center "
            "/ axis_line predicates assume linear axes. On log y, the y "
            "tick label centres sit at EQUAL pixel spacing (because the "
            "labels are 0.1, 1, 10, 100, 1000) but the values they "
            "represent are NOT equally spaced. A linear calibration fit "
            "through (pixel, value) pairs misreads the axis by ~30-100 % "
            "per tick. This is the harness's first real stress test."
        ),
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}")


if __name__ == "__main__":
    main()
