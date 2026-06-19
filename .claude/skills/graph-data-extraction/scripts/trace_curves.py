#!/usr/bin/env python3
"""trace_curves.py — implementation of the §3 line/curve trace, in two
flavours so a caller can compare them:

  - `trace_per_column_median(mask, …)`   — the original §3 recipe trace.
    Per column, take the median row of mask pixels. Picks the right answer
    on well-separated curves and the wrong answer at crossings.

  - `trace_with_continuity(mask, seeds, …)` — the §3 addition documented in
    extraction_recipes.md after the el-94 TDD pass. Seeded at known
    starting rows, tracks each curve's trajectory across columns, prefers
    the run whose row matches the predicted-from-slope trajectory. Handles
    curve crossings: both curves can claim the same merged run when their
    predictions land at it.

Both are pure Python + numpy; they take a binary `mask` of stroke pixels
inside the plot region and return data-space (x, y) lists per curve, given
a calibration's m, b for each axis (and scale).

Validated 2026-06-19 on synthetic-r4-1 chart #10 (two same-color crossing
lines). The naive median trace produces a visible "V" shape at the
crossing because the wrong run wins; trace_with_continuity follows each
curve through the crossing cleanly.

Usage example at the bottom (`if __name__ == "__main__":`) runs both
traces on a chart dir and reports per-curve mean drift vs ground truth.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Optional

import cv2
import numpy as np


# ---------- Pixel-row run analysis ----------

def column_runs(col_mask):
    """For a 1-D boolean column, return list of run centres (mean row of
    each contiguous True stretch)."""
    rr = np.where(col_mask > 0)[0]
    if len(rr) == 0:
        return []
    runs = []
    cur = [rr[0]]
    for r in rr[1:]:
        if r == cur[-1] + 1:
            cur.append(r)
        else:
            runs.append(int(np.mean(cur))); cur = [r]
    runs.append(int(np.mean(cur)))
    return runs


# ---------- Trace primitives ----------

def trace_per_column_median(mask, plot_left, plot_right, plot_top, plot_bot):
    """The original §3 recipe trace. Returns a single list of (col, row) —
    no per-curve attribution. Good as a baseline."""
    pts = []
    for c in range(plot_left + 1, plot_right - 1):
        col = mask[plot_top:plot_bot, c]
        rr = np.where(col > 0)[0]
        if len(rr) > 0:
            pts.append((c, plot_top + int(np.median(rr))))
    return pts


def trace_with_continuity(mask, plot_left, plot_right, plot_top, plot_bot,
                          seeds, slope_window=10, max_step_per_col=30):
    """Trajectory-tracking trace with unique pairwise assignment.

    seeds: list of (col0, row0) — the starting (col, row) of each curve at
           the leftmost meaningful column. In practice these come from
           the legend swatch positions, or from manual inspection of an
           unambiguous column where the curves are well-separated.

    slope_window: how many trailing points to average the local slope over.
                  Larger window resists slope corruption when curves merge.

    max_step_per_col: bound on how far a curve's row may move from its
                     prediction before we treat the run as not-this-curve.

    Assignment policy (the el-94 / synthetic-r4-1 crossing-curves lesson):
      - If `len(runs) >= len(curves)`, solve for the UNIQUE assignment
        that minimises total absolute deviation from predictions. For
        N=2 this is a 2-permutation pick. Each curve gets its own run.
      - If `len(runs) < len(curves)`, the curves are visually merged at
        this column. Each curve takes the nearest run AND we skip the
        slope update for that step (the merged-zone rows would corrupt
        the trajectory).

    Returns: list of curves, each curve a list of (col, row, *was_merged).
    The third element is True for columns where the algorithm marked the
    point as merged (informational; not used by callers).
    """
    curves = [[(int(c), int(r))] for c, r in seeds]
    # Track each curve's last NON-MERGED point for slope calculation
    last_clean = list(curves[0:])  # references to lists; will track
    last_clean_idx = [0] * len(seeds)  # index into curves[ci] of last clean
    # Each curve only takes assignments from its own seed column onwards.
    # If a curve's seed is at col 116 and the trace starts at col 92, the
    # curve must not accept runs at cols 92-115 (the curve does not exist
    # there). Tested on el-94's 30 °C dotted curve, which starts much later
    # in x than 24 °C and 27 °C: without this guard, bogus pre-seed
    # assignments corrupted the trajectory immediately.
    seed_cols = [int(s[0]) for s in seeds]

    n = len(seeds)
    for c in range(int(min(s[0] for s in seeds)) + 1, plot_right - 1):
        col = mask[plot_top:plot_bot, c]
        runs = [plot_top + r for r in column_runs(col)]
        if not runs:
            continue

        # Predict each curve's next row from its LAST CLEAN trajectory.
        preds = []
        for ci, curve in enumerate(curves):
            clean_end = last_clean_idx[ci]
            # Slope from a window of clean points ending at clean_end
            clean_window = curve[max(0, clean_end - slope_window + 1):
                                  clean_end + 1]
            if len(clean_window) >= 2:
                dc = clean_window[-1][0] - clean_window[0][0]
                dr = clean_window[-1][1] - clean_window[0][1]
                slope = dr / max(1, dc)
            else:
                slope = 0.0
            last_col, last_row = curve[-1][0], curve[-1][1]
            preds.append(last_row + slope * (c - last_col))

        # Which curves are eligible at this column? Only those whose seed
        # col is at or before `c`.
        active = [ci for ci in range(n) if seed_cols[ci] <= c]
        if not active:
            continue

        if len(runs) >= len(active):
            # Unique assignment — pick the permutation that minimises
            # total |pred - run|. For 2 active curves, just compare the
            # two perms.
            if len(active) == 2 and len(runs) >= 2:
                ci0, ci1 = active
                run_choices = sorted(set(runs))
                best_cost, best_assign = float("inf"), None
                for ra in run_choices:
                    for rb in run_choices:
                        if ra == rb: continue
                        cost = abs(preds[ci0] - ra) + abs(preds[ci1] - rb)
                        if cost < best_cost:
                            best_cost, best_assign = cost, (ra, rb)
                if best_assign:
                    for ci, r in zip(active, best_assign):
                        if abs(preds[ci] - r) <= max_step_per_col:
                            curves[ci].append((c, int(r)))
                            last_clean_idx[ci] = len(curves[ci]) - 1
            else:
                # General greedy (acceptable for one active or three+)
                used = [False] * len(runs)
                for ci in active:
                    best, best_j = max_step_per_col + 1, None
                    for j, rr in enumerate(runs):
                        if used[j]: continue
                        d = abs(rr - preds[ci])
                        if d < best:
                            best, best_j = d, j
                    if best_j is not None:
                        used[best_j] = True
                        curves[ci].append((c, int(runs[best_j])))
                        last_clean_idx[ci] = len(curves[ci]) - 1
        else:
            # Merged column: each active curve takes the nearest single
            # run, but we do NOT advance last_clean_idx — the slope window
            # stays pinned to pre-merge data.
            for ci in active:
                best, best_run = max_step_per_col + 1, None
                for rr in runs:
                    d = abs(rr - preds[ci])
                    if d < best:
                        best, best_run = d, rr
                if best_run is not None:
                    curves[ci].append((c, int(best_run)))
                    # NOTE: do not update last_clean_idx
    return curves


# ---------- Scale-aware pixel→data conversion ----------

def pixel_to_data(pixel, m, b, scale):
    """Inverse of data_to_pixel from the verifier.

    Linear:  value = m·pixel + b.
    Log10:   value = 10**(m·pixel + b).
    """
    v = m * pixel + b
    return float(10 ** v) if scale == "log10" else float(v)


# ---------- Test harness against a chart dir ----------

def _build_blue_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([100, 80, 50]),
                        np.array([130, 255, 255]))
    return mask


def _resample_at_x(curve, x_target_list, m_x, b_x, m_y, b_y,
                   x_scale, y_scale):
    """Convert a list of (col, row) to data (x, y); resample at x_target_list."""
    if not curve:
        return [None] * len(x_target_list)
    # Convert each col to data x, each row to data y
    pts_data = []
    for col, row in curve:
        x = pixel_to_data(col, m_x, b_x, x_scale)
        y = pixel_to_data(row, m_y, b_y, y_scale)
        pts_data.append((x, y))
    pts_data.sort()
    xs = np.array([p[0] for p in pts_data])
    ys = np.array([p[1] for p in pts_data])
    out = []
    for xt in x_target_list:
        if xt < xs[0] or xt > xs[-1]:
            out.append(None)
        else:
            out.append(float(np.interp(xt, xs, ys)))
    return out


def run_test(chart_dir, mask_builder=_build_blue_mask):
    """Trace a synthetic chart with both algorithms, score each against GT."""
    with open(os.path.join(chart_dir, "ground_truth_calibration.json")) as f:
        cal = json.load(f)
    with open(os.path.join(chart_dir, "ground_truth.csv")) as f:
        gt_rows = list(csv.DictReader(f))
    img = cv2.imread(os.path.join(chart_dir, "image.png"))
    pf = cal["plot_frame_box"]
    x_ax = cal["axis_calibration"]["x_axis"]
    y_ax = cal["axis_calibration"]["y_axis"]
    mask = mask_builder(img)

    # Determine seed points: leftmost column where each GT curve has a value.
    by_series = {}
    for r in gt_rows:
        if "Line" in r["layer_type"] or "Spline" in r["layer_type"]:
            by_series.setdefault(r["series"], []).append((float(r["x"]),
                                                            float(r["y"])))
    for s in by_series:
        by_series[s].sort()
    series_order = sorted(by_series.keys())

    # Seeds: for each series, the leftmost GT (x, y) → (col, row)
    seeds = []
    for s in series_order:
        x0, y0 = by_series[s][0]
        mx, bx_ = x_ax["m"], x_ax["b"]
        my, by_ = y_ax["m"], y_ax["b"]
        x_scale = x_ax.get("scale", "linear")
        y_scale = y_ax.get("scale", "linear")
        # data → pixel (linear here; log10 case left for future)
        v_x = np.log10(x0) if x_scale == "log10" else x0
        v_y = np.log10(y0) if y_scale == "log10" else y0
        col = (v_x - bx_) / mx
        row = (v_y - by_) / my
        seeds.append((col, row))

    # Median trace (no per-curve attribution)
    median_pts = trace_per_column_median(
        mask, pf["left"], pf["right"], pf["top"], pf["bottom"])

    # Continuity trace
    cont_curves = trace_with_continuity(
        mask, pf["left"], pf["right"], pf["top"], pf["bottom"], seeds)

    # Resample each at GT x values and report mean |Δy|
    print(f"\n=== {os.path.basename(chart_dir)} ===")
    print(f"GT curves: {series_order}")
    print(f"seeds (col, row): {[(round(c, 1), round(r, 1)) for c, r in seeds]}")
    print()

    # Median: a single trace pretending to be both — show how off it is from
    # each GT.
    print("trace_per_column_median (single trace, no attribution):")
    median_data = [(pixel_to_data(c, x_ax["m"], x_ax["b"],
                                   x_ax.get("scale", "linear")),
                    pixel_to_data(r, y_ax["m"], y_ax["b"],
                                   y_ax.get("scale", "linear")))
                   for c, r in median_pts]
    median_data.sort()
    for s in series_order:
        gt_xs = [p[0] for p in by_series[s]]
        gt_ys = [p[1] for p in by_series[s]]
        xs = np.array([p[0] for p in median_data])
        ys = np.array([p[1] for p in median_data])
        pred = [float(np.interp(gx, xs, ys)) for gx in gt_xs]
        deltas = [abs(p - g) for p, g in zip(pred, gt_ys)]
        print(f"  vs {s}: n={len(deltas)}, "
              f"mean |Δy|={np.mean(deltas):.3f}, "
              f"max |Δy|={max(deltas):.3f}")

    print()
    print("trace_with_continuity (per-curve attribution):")
    for ci, s in enumerate(series_order):
        gt_xs = [p[0] for p in by_series[s]]
        gt_ys = [p[1] for p in by_series[s]]
        pred = _resample_at_x(cont_curves[ci], gt_xs, x_ax["m"], x_ax["b"],
                                y_ax["m"], y_ax["b"],
                                x_ax.get("scale", "linear"),
                                y_ax.get("scale", "linear"))
        deltas = [abs(p - g) for p, g in zip(pred, gt_ys) if p is not None]
        if not deltas:
            print(f"  vs {s}: NO COVERAGE")
            continue
        print(f"  vs {s}: n={len(deltas)}, "
              f"mean |Δy|={np.mean(deltas):.3f}, "
              f"max |Δy|={max(deltas):.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chart_dir")
    args = ap.parse_args()
    run_test(args.chart_dir)


if __name__ == "__main__":
    main()
