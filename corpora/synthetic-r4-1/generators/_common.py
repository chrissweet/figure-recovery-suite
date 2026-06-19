"""Shared helpers for the synthetic-r4-1 generators.

The two important utilities here:
  - `calibration_from_axes()` — given a matplotlib `Axes`, return the
    exact pixel ↔ data calibration the harness records as GT
  - `write_chart()` — write the four-file output (image.png, ground_truth.csv,
    ground_truth_calibration.json, metadata.json) per generator
"""
from __future__ import annotations

import csv
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CHARTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "charts")


def data_to_image_px(ax, x_data, y_data):
    """Convert a data-space (x, y) to image-space (col, row) pixels.

    matplotlib's display transform gives (px_x, px_y_from_bottom). The image
    we save has y growing downward, so we flip: row = H − px_y_from_bottom.
    """
    fig = ax.figure
    H = fig.canvas.get_width_height()[1]
    px = ax.transData.transform([(x_data, y_data)])[0]
    col = float(px[0])
    row = float(H - px[1])
    return col, row


def calibration_from_axes(ax, image_path, x_scale="linear", y_scale="linear"):
    """Derive the calibration JSON from a fully-drawn matplotlib Axes.

    For linear scales:  value = m·pixel + b.
    For log10 scales:   value = 10**(m·pixel + b).
    Records `scale` on each axis so the recipe / verifier can branch on it.
    """
    fig = ax.figure
    W, H = fig.canvas.get_width_height()
    # Two data-space anchor points per axis, picked from the visible range
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    if x_scale == "log10":
        x_sample_a, x_sample_b = max(x0, 1e-9), x1
    else:
        x_sample_a, x_sample_b = x0, x1
    if y_scale == "log10":
        y_sample_a, y_sample_b = max(y0, 1e-9), y1
    else:
        y_sample_a, y_sample_b = y0, y1
    # Pixel coords for each anchor
    col_a, row_y0 = data_to_image_px(ax, x_sample_a, y_sample_a)
    col_b, row_y1 = data_to_image_px(ax, x_sample_b, y_sample_b)

    def fit_axis(p0, p1, v0, v1, scale):
        if scale == "log10":
            v0_t = math.log10(v0); v1_t = math.log10(v1)
        else:
            v0_t, v1_t = v0, v1
        m = (v1_t - v0_t) / (p1 - p0)
        b = v0_t - m * p0
        return m, b

    mx, bx = fit_axis(col_a, col_b, x_sample_a, x_sample_b, x_scale)
    my, by = fit_axis(row_y0, row_y1, y_sample_a, y_sample_b, y_scale)

    # Plot frame box (axes bounding box in image pixels)
    bbox = ax.get_window_extent(fig.canvas.get_renderer())
    pf_left = int(round(bbox.x0))
    pf_right = int(round(bbox.x1))
    pf_top = int(round(H - bbox.y1))
    pf_bottom = int(round(H - bbox.y0))

    def axis_block(m, b, scale, unit_label):
        if scale == "log10":
            formula = f"value = 10**({m:.6f}·pixel + {b:.6f})"
            inverse = f"pixel = (log10(value) - {b:.6f}) / {m:.6f}"
        else:
            formula = f"value = {m:.6f}·pixel + {b:.6f}"
            inverse = f"pixel = (value - {b:.6f}) / {m:.6f}"
        return {
            "scale": scale,
            "formula": formula,
            "m": round(m, 8),
            "b": round(b, 8),
            "inverse": inverse,
            "unit_label": unit_label,
        }

    cal = {
        "image": os.path.basename(image_path),
        "image_size": {"width": int(W), "height": int(H)},
        "plot_frame_box": {
            "offset": {"x": pf_left, "y": pf_top},
            "size": {"width": pf_right - pf_left,
                      "height": pf_bottom - pf_top},
            "left": pf_left, "top": pf_top,
            "right": pf_right, "bottom": pf_bottom,
            "description": "Plot region in image pixel coords. Derived "
                            "directly from matplotlib's axes bbox.",
        },
        "data_range": {
            "x_min": float(x0), "x_max": float(x1),
            "y_min": float(y0), "y_max": float(y1),
        },
        "axis_calibration": {
            "x_axis": axis_block(mx, bx, x_scale,
                                  f"pixels per {x_scale} x-unit"),
            "y_axis": axis_block(my, by, y_scale,
                                  f"pixels per {y_scale} y-unit"),
        },
        "detection_internals": {
            "y_axis_col_detected": pf_left,
            "x_axis_row_detected": pf_bottom,
            "source": "synthetic (matplotlib transforms)",
        },
        "data_extent_box": {
            "left": pf_left, "right": pf_right,
            "top": pf_top, "bottom": pf_bottom,
            "width": pf_right - pf_left,
            "height": pf_bottom - pf_top,
        },
    }
    return cal


def write_chart(chart_id, ax, layers, metadata):
    """Persist image.png + ground_truth.csv + ground_truth_calibration.json
    + metadata.json for one chart.

    `layers`: list of dicts {layer_idx, layer_type, series, points: [(x, y)]}
    `metadata`: free-form dict; merged into the on-disk metadata.json.
    """
    chart_dir = os.path.join(CHARTS_DIR, chart_id)
    os.makedirs(chart_dir, exist_ok=True)
    fig = ax.figure
    image_path = os.path.join(chart_dir, "image.png")
    fig.canvas.draw()  # ensure transforms are settled
    # Build calibration BEFORE savefig so the bbox reflects the on-screen layout
    cal = calibration_from_axes(
        ax, image_path,
        x_scale=metadata.get("x_scale", "linear"),
        y_scale=metadata.get("y_scale", "linear"),
    )
    fig.savefig(image_path, dpi=fig.dpi, bbox_inches=None)
    plt.close(fig)

    with open(os.path.join(chart_dir, "ground_truth.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for layer in layers:
            for x, y in layer["points"]:
                w.writerow([layer["layer_idx"], layer["layer_type"],
                             layer["series"], x, y])

    with open(os.path.join(chart_dir, "ground_truth_calibration.json"),
              "w") as f:
        json.dump(cal, f, indent=2)

    with open(os.path.join(chart_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    return chart_dir
