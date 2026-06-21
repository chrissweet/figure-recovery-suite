#!/usr/bin/env python3
"""Per-series IoU between source image and pixel-replot data layer.

Primary convergence signal for the feedback-loop extractor. Computes, for
each series in chart_metadata.json:
  1. source_mask: pixels in image.png matching the series' legend color
     (within color_tolerance), restricted to plot_frame_box and excluding
     the legend exclusion box.
  2. replot_mask: pixels in replot_data_layer.png matching the same color,
     same restriction.
  3. IoU = |source_mask & replot_mask| / |source_mask | replot_mask|

The signal is meaningful BECAUSE the pixel-replot places data at the
calibration's exact pixel positions (no matplotlib autolayout drift).
Source-vs-replot IoU then directly measures: did our claims cover the
right pixels and only the right pixels?

Returns a dict {
  "per_series": {
    series_id: {
      "color_hex": str,
      "source_px": int, "replot_px": int,
      "intersection_px": int, "union_px": int,
      "iou": float,
    }, ...
  },
  "mean_iou": float,
  "weighted_iou": float,    # weighted by max(source_px, replot_px)
}
"""
import csv
import json
import os
import sys

import cv2
import numpy as np


def _hex_to_bgr(hex_str):
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return np.array([b, g, r], dtype=np.int32)


def _color_mask(img_bgr, target_bgr, tolerance):
    diff = img_bgr.astype(np.int32) - target_bgr
    return np.sqrt((diff * diff).sum(axis=2)) <= tolerance


def _plot_frame_mask(shape, plot_frame_box, legend_excl=None):
    H, W = shape[:2]
    mask = np.zeros((H, W), dtype=bool)
    pf = plot_frame_box
    mask[pf["top"]:pf["bottom"], pf["left"]:pf["right"]] = True
    if legend_excl:
        if isinstance(legend_excl, dict):
            t = legend_excl.get("top", legend_excl.get("row0"))
            b = legend_excl.get("bottom", legend_excl.get("row1"))
            l = legend_excl.get("left", legend_excl.get("col0"))
            r = legend_excl.get("right", legend_excl.get("col1"))
        else:
            t, b, l, r = legend_excl[0], legend_excl[1], legend_excl[2], legend_excl[3]
        if all(v is not None for v in (t, b, l, r)):
            mask[int(t):int(b), int(l):int(r)] = False
    return mask


def compute(source_path, replot_path, calibration, chart_metadata,
             color_tolerance=30):
    """Compute per-series IoU between source and replot data layer."""
    src = cv2.imread(source_path)
    rep = cv2.imread(replot_path)
    if src is None: raise FileNotFoundError(source_path)
    if rep is None: raise FileNotFoundError(replot_path)
    if src.shape != rep.shape:
        # Resize replot to match source so per-pixel comparison is valid.
        # In practice they should match (pixel_replot.render uses the source
        # dimensions), but defend in case dimensions drift.
        rep = cv2.resize(rep, (src.shape[1], src.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    pf = calibration["plot_frame_box"]
    legend_excl = calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    frame = _plot_frame_mask(src.shape, pf, legend_excl)

    out = {"per_series": {}, "mean_iou": 0.0, "weighted_iou": 0.0}
    sum_iou = 0.0
    n_series = 0
    weighted_num = 0.0
    weighted_den = 0.0

    for spec in chart_metadata.get("series_legend", []):
        sid = spec.get("series_id")
        hex_col = spec.get("color", "")
        if not sid or not hex_col.startswith("#"):
            continue
        target = _hex_to_bgr(hex_col)
        src_mask = _color_mask(src, target, color_tolerance) & frame
        rep_mask = _color_mask(rep, target, color_tolerance) & frame
        inter = int((src_mask & rep_mask).sum())
        union = int((src_mask | rep_mask).sum())
        iou = inter / max(1, union)
        src_px = int(src_mask.sum()); rep_px = int(rep_mask.sum())
        out["per_series"][sid] = {
            "color_hex": hex_col,
            "source_px": src_px, "replot_px": rep_px,
            "intersection_px": inter, "union_px": union,
            "iou": round(iou, 4),
        }
        sum_iou += iou
        n_series += 1
        w = max(src_px, rep_px)
        weighted_num += w * iou
        weighted_den += w

    out["mean_iou"]     = round(sum_iou / max(1, n_series), 4)
    out["weighted_iou"] = round(weighted_num / max(1, weighted_den), 4)
    return out


if __name__ == "__main__":
    # CLI: compare_iou.py <chart_results_dir> [<source_image_path>] [<replot_path>]
    chart_dir = sys.argv[1]
    source_path = sys.argv[2] if len(sys.argv) > 2 else None
    replot_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        chart_dir, "replot_data_layer.png")
    if source_path is None:
        parts = os.path.normpath(chart_dir).split(os.sep)
        if "results-v3" in parts:
            i = parts.index("results-v3")
            source_path = os.path.join(
                "corpora", parts[i + 1], "charts", parts[i + 2], "image.png")
    cal = json.load(open(os.path.join(chart_dir, "calibration.json")))
    md  = json.load(open(os.path.join(chart_dir, "chart_metadata.json")))
    rep = compute(source_path, replot_path, cal, md)
    print(json.dumps(rep, indent=2))
