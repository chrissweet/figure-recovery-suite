#!/usr/bin/env python3
"""Chart 5 — stacked bar chart.

Feature stressed: segment boundary detection. Unlike the grouped case,
all segments share one column. The extractor needs to walk that column
from the top down and detect color *changes* to recover per-segment y
values.

GT records, per series, (x_center, cumulative_top) — i.e. the row of
the segment's UPPER edge in data space. The lowest segment's upper edge
is its value; the next segment's upper edge is value0 + value1; etc.
This matches how stacked-bar y values are usually read off charts.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4255
CHART_ID = "05-stacked-bar"


def main():
    categories = ["Web", "API", "Worker", "Cron", "DB"]
    series_specs = [
        {"name": "CPU",     "values": [22.0, 31.0, 45.0, 18.0, 28.0],
         "color": "C0"},
        {"name": "Memory",  "values": [15.0, 22.0, 28.0, 12.0, 35.0],
         "color": "C1"},
        {"name": "IO Wait", "values": [ 8.0, 12.0, 18.0,  5.0, 22.0],
         "color": "C2"},
    ]
    x_positions = np.arange(len(categories))

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    bottoms = np.zeros(len(categories))
    cumulative_tops = []
    for spec in series_specs:
        vals = np.array(spec["values"])
        ax.bar(x_positions, vals, bottom=bottoms, width=0.6,
               color=spec["color"], edgecolor="black", linewidth=0.6,
               label=spec["name"])
        bottoms = bottoms + vals
        cumulative_tops.append(bottoms.copy())

    ax.set_xticks(x_positions)
    ax.set_xticklabels(categories)
    ax.set_xlabel("Service")
    ax.set_ylabel("Utilisation (% of node)")
    ax.set_title("Synthetic #5 — stacked bars")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()

    # Two GT layers:
    #   layer 0: per-segment value (what the chart "means")
    #   layer 1: per-segment cumulative top (what the extractor measures
    #            directly off the rendered chart)
    layers = []
    for si, spec in enumerate(series_specs):
        seg_pts = [(float(xp), float(v))
                    for xp, v in zip(x_positions, spec["values"])]
        layers.append({
            "layer_idx": 0, "layer_type": "Grouped Column Chart",
            "series": f"{spec['name']}_value", "points": seg_pts,
        })
        top_pts = [(float(xp), float(ct))
                    for xp, ct in zip(x_positions, cumulative_tops[si])]
        layers.append({
            "layer_idx": 1, "layer_type": "StackedSegmentLayer",
            "series": f"{spec['name']}_cum_top", "points": top_pts,
        })

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": ("stacked bar segment boundaries. Extractor "
                              "must walk each bar column and detect color "
                              "changes to recover per-segment values."),
        "chart_type": "stacked_bar",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Service",
        "y_axis_title": "Utilisation (% of node)",
        "x_axis_unit": "% of node",
        "y_axis_unit": "%",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #5 — stacked bars",
        "x_categories": categories,
        "bar_width": 0.6,
        "series_order_bottom_to_top": [s["name"] for s in series_specs],
        "series_legend": [
            {"series_id": s["name"], "color": c, "fill_style": "solid",
             "source_label": s["name"]}
            for s, c in zip(series_specs,
                             ["#1f77b4", "#ff7f0e", "#2ca02c"])
        ],
        "generator": __file__,
        "seed": SEED,
        "boundary_test": ("For each x and each segment k, the cumulative_top "
                           "in GT layer 1 should match the row of the "
                           "color-change boundary at that column (within ε). "
                           "Per-segment values are the differences."),
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  "
          f"({len(categories)} bars × {len(series_specs)} segments)")


if __name__ == "__main__":
    main()
