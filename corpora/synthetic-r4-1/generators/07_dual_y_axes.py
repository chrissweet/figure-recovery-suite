#!/usr/bin/env python3
"""Chart 7 — dual y-axes (twin axes, one series per axis).

Feature stressed: §2 axis calibration when the chart has TWO y-axes
with different scales / labels / units. The recipe currently assumes
one y-axis; on a twin-axis chart it has to:
  1. Detect both axes (left and right tick columns)
  2. Calibrate them independently
  3. Associate each series with the correct axis (via legend color
     match + axis-line color, or via the legend's axis annotation)

Series A (blue) reads against the left axis (current, A); Series B
(red) reads against the right axis (voltage, V). The two scales are
deliberately mis-aligned so that mis-assigning a series to the wrong
axis produces wildly wrong numbers, easy to flag.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import data_to_image_px, calibration_from_axes, write_chart  # noqa: E402
import json
import csv

SEED = 4257
CHART_ID = "07-dual-y-axes"


def main():
    rng = np.random.default_rng(SEED)
    x = np.linspace(0, 10, 24)
    a = 0.4 + 0.06 * x + rng.normal(0, 0.015, len(x))
    v = 12.0 - 0.4 * x + rng.normal(0, 0.18, len(x))

    fig, ax1 = plt.subplots(figsize=(7.5, 4.5), dpi=100)
    color_a = "C0"
    color_v = "C3"
    p1 = ax1.plot(x, a, color=color_a, marker="o", linestyle="-",
                  markersize=4, linewidth=1.4, label="Drive current (A)")
    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel("Drive current (A)", color=color_a)
    ax1.tick_params(axis="y", labelcolor=color_a)
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0.3, 1.2)

    ax2 = ax1.twinx()
    p2 = ax2.plot(x, v, color=color_v, marker="s", linestyle="--",
                  markersize=4, linewidth=1.4, label="Cell voltage (V)")
    ax2.set_ylabel("Cell voltage (V)", color=color_v)
    ax2.tick_params(axis="y", labelcolor=color_v)
    ax2.set_ylim(7, 13)

    handles = p1 + p2
    labels = [h.get_label() for h in handles]
    ax1.legend(handles, labels, loc="lower right", frameon=True)
    ax1.set_title("Synthetic #7 — dual y-axes")
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()

    chart_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "charts", CHART_ID)
    os.makedirs(chart_dir, exist_ok=True)
    image_path = os.path.join(chart_dir, "image.png")
    fig.canvas.draw()

    cal_left  = calibration_from_axes(ax1, image_path,
                                       x_scale="linear", y_scale="linear")
    cal_right = calibration_from_axes(ax2, image_path,
                                       x_scale="linear", y_scale="linear")

    cal = {
        "image": cal_left["image"],
        "image_size": cal_left["image_size"],
        "plot_frame_box": cal_left["plot_frame_box"],
        "data_range": {
            "x_min": cal_left["data_range"]["x_min"],
            "x_max": cal_left["data_range"]["x_max"],
            "y_min_left":  cal_left["data_range"]["y_min"],
            "y_max_left":  cal_left["data_range"]["y_max"],
            "y_min_right": cal_right["data_range"]["y_min"],
            "y_max_right": cal_right["data_range"]["y_max"],
        },
        "axis_calibration": {
            "x_axis":        cal_left["axis_calibration"]["x_axis"],
            "y_axis_left":   cal_left["axis_calibration"]["y_axis"],
            "y_axis_right":  cal_right["axis_calibration"]["y_axis"],
        },
        "detection_internals": {
            "y_axis_col_detected_left":  cal_left["plot_frame_box"]["left"],
            "y_axis_col_detected_right": cal_left["plot_frame_box"]["right"],
            "x_axis_row_detected":       cal_left["plot_frame_box"]["bottom"],
            "source": "synthetic (matplotlib transforms, two axes)",
        },
        "data_extent_box": cal_left["data_extent_box"],
    }

    fig.savefig(image_path, dpi=fig.dpi, bbox_inches=None)
    plt.close(fig)

    layers = [
        {"layer_idx": 0, "layer_type": "Line Graph",
         "series": "Drive current (A)",
         "points": [(float(xi), float(ai)) for xi, ai in zip(x, a)],
         "axis": "left"},
        {"layer_idx": 0, "layer_type": "Line Graph",
         "series": "Cell voltage (V)",
         "points": [(float(xi), float(vi)) for xi, vi in zip(x, v)],
         "axis": "right"},
    ]
    with open(os.path.join(chart_dir, "ground_truth.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y", "axis"])
        for layer in layers:
            for xv, yv in layer["points"]:
                w.writerow([layer["layer_idx"], layer["layer_type"],
                             layer["series"], xv, yv, layer["axis"]])

    with open(os.path.join(chart_dir, "ground_truth_calibration.json"),
              "w") as f:
        json.dump(cal, f, indent=2)

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": ("dual y-axes (twin axes). Each series binds "
                              "to a specific axis; mis-assignment produces "
                              "wildly wrong numbers."),
        "chart_type": "dual_y_line",
        "x_scale": "linear",
        "y_scale_left": "linear",
        "y_scale_right": "linear",
        "x_axis_title": "Time (min)",
        "y_axis_title_left": "Drive current (A)",
        "y_axis_title_right": "Cell voltage (V)",
        "x_axis_unit": "min",
        "y_axis_unit_left": "A",
        "y_axis_unit_right": "V",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #7 — dual y-axes",
        "series_legend": [
            {"series_id": "Drive current (A)", "color": "#1f77b4",
             "marker_style": "filled_circle", "line_style": "solid",
             "axis": "left", "source_label": "Drive current (A)"},
            {"series_id": "Cell voltage (V)", "color": "#d62728",
             "marker_style": "filled_square", "line_style": "dashed",
             "axis": "right", "source_label": "Cell voltage (V)"},
        ],
        "generator": __file__,
        "seed": SEED,
        "axis_assignment_test": (
            "Each series' (x, y) must be calibrated with the correct y "
            "axis (left for current, right for voltage). The legend marker "
            "colors match the axis tick label colors, which is the primary "
            "signal for the assignment."),
    }
    with open(os.path.join(chart_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"wrote {chart_dir}  (dual y-axes, 2 series)")


if __name__ == "__main__":
    main()
