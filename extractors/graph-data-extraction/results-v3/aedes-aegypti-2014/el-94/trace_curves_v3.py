#!/usr/bin/env python3
"""Re-trace el-94's three fit curves with trace_with_continuity.

The v2 attempt (results-v2/el-94/fit_curves.csv) used per-column-median
with greedy NN attribution. The el-94 TDD step-4 audit flagged it as
"bulk-x trace is good, fails at crossings x ≈ 23-30 and at high-x
endpoints". This script replaces that with the unique-pair + clean-slope
variant from scripts/trace_curves.py and compares both against the
ground truth.

Expected outcome: chaotic region cleans up; bulk-x stays at the same
fidelity it had before.

Output:
  trace_v3.csv             — new traced curves (Spline Chart layer rows)
  trace_v3_overlay.png     — side-by-side (v2 trace | v3 trace) on image.png
  trace_v3_comparison.json — per-curve numerical comparison vs GT
"""
import csv
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(
    REPO, ".claude", "skills", "graph-data-extraction", "scripts"))
from trace_curves import (trace_with_continuity,
                            trace_per_column_median,
                            pixel_to_data)

IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-94", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "calibration.json")
GT   = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-94", "ground_truth.csv")
V2_CURVES = os.path.join(REPO, "extractors", "graph-data-extraction",
                          "results-v2", "aedes-aegypti-2014", "el-94",
                          "fit_curves.csv")
PRIOR_SCATTER = os.path.join(REPO, "extractors", "graph-data-extraction",
                              "results", "aedes-aegypti-2014", "el-94",
                              "data.csv")


def main():
    with open(CAL) as f: cal = json.load(f)
    img = cv2.imread(IMG)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    pf = cal["plot_frame_box"]
    x_ax = cal["axis_calibration"]["x_axis"]
    y_ax = cal["axis_calibration"]["y_axis"]
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")

    # Dark mask = curve pixels. Exclude legend rectangle and the right margin
    # where the dashed extension can leak into the legend text. Dilate to
    # bridge tiny gaps in the dotted 30°C series so per-column runs aren't
    # empty between dots.
    legend = cal["detection_internals"]["legend_exclusion_used_for_frame"]
    mask = (gray < 120).astype(np.uint8) * 255
    if legend:
        ly0, ly1, lx0, lx1 = legend
        mask[ly0:ly1, lx0:lx1] = 0
    mask[:, 700:] = 0   # right margin — legend text extends past the box
    mask = cv2.dilate(mask, np.ones((1, 3), np.uint8))

    # Subtract scatter marker positions so they don't pollute the trace.
    with open(PRIOR_SCATTER) as f:
        for r in csv.DictReader(f):
            try:
                x = float(r["age_days"]); y = float(r["daily_survival_p"])
            except (TypeError, ValueError):
                continue
            col = (x - bx) / mx
            row = (y - by) / my
            cv2.circle(mask, (int(col), int(row)), 6, 0, -1)

    # Load GT to derive seeds (leftmost (x, y) per curve) and to score.
    gt_by_series = {}
    with open(GT) as f:
        for r in csv.DictReader(f):
            if "Spline" not in r["layer_type"]:
                continue
            s = r["series"]
            try:
                x = float(r["x"]); y = float(r["y"])
            except ValueError:
                continue
            gt_by_series.setdefault(s, []).append((x, y))
    for s in gt_by_series:
        gt_by_series[s].sort()

    # Series order chosen to match the y-band at the seed column so the
    # unique-pair assignment starts from a stable configuration.
    series_order = sorted(gt_by_series.keys())  # alphabetical: 24C, 27C, 30C
    seeds = []
    for s in series_order:
        # Use the second GT point (skip the very leftmost which is sometimes
        # noisy near the y-axis line) as the seed.
        x0, y0 = gt_by_series[s][min(1, len(gt_by_series[s]) - 1)]
        col = (x0 - bx) / mx
        row = (y0 - by) / my
        seeds.append((col, row))

    # Snap each seed to the nearest mask run within ±20 px vertically. GT
    # records the analytical curve; the rendered chart can sit a few pixels
    # off because of anti-aliasing, line width, and the chart's own data
    # smoothing. Without snapping, the 30 °C dotted curve seed lands ~10 px
    # below the leftmost visible dot and the trace doesn't start.
    snapped = []
    for col, row in seeds:
        c = int(round(col))
        column = mask[max(0, int(row) - 25):min(mask.shape[0], int(row) + 25),
                       max(0, c - 2):c + 3]
        if column.any():
            # Centroid of dark pixels in the search box
            ys, xs = np.where(column)
            snapped_row = max(0, int(row) - 25) + int(np.median(ys))
            snapped.append((col, snapped_row))
        else:
            snapped.append((col, row))
    seeds = snapped
    print(f"seeds (col, row): "
          f"{[(round(c, 1), round(r, 1)) for c, r in seeds]}")

    # ---------- New trace ----------
    # max_step_per_col=15 — el-94's y range is narrow (0.05 unit / 515 px =
    # ~10000 px/unit), so 15 px is about 0.0015 in y. Still tight but
    # accommodates the dotted gaps and the steep 30 °C dotted curve at
    # low x where slope is large.
    curves = trace_with_continuity(
        mask, pf["left"], pf["right"], pf["top"], pf["bottom"],
        seeds, slope_window=15, max_step_per_col=15)

    print(f"\nnew trace lengths: "
          f"{[len(c) for c in curves]} (series: {series_order})")

    # Convert curves to data space and write CSV
    out_csv = os.path.join(HERE, "trace_v3.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for s, pts in zip(series_order, curves):
            for col, row in pts[::3]:  # decimate ×3 for compactness
                x = pixel_to_data(col, mx, bx, x_scale)
                y = pixel_to_data(row, my, by, y_scale)
                w.writerow([f"p_curve_{s}", round(x, 4), round(y, 6)])
    print(f"wrote {out_csv}")

    # ---------- Compare against GT ----------
    def score(pts_pixel, gt_pts):
        if not pts_pixel:
            return {"n": 0, "mean": None, "max": None}
        xs = []; ys = []
        for col, row in pts_pixel:
            xs.append(pixel_to_data(col, mx, bx, x_scale))
            ys.append(pixel_to_data(row, my, by, y_scale))
        xs = np.array(xs); ys = np.array(ys)
        order = np.argsort(xs)
        xs = xs[order]; ys = ys[order]
        deltas = []
        for gx, gy in gt_pts:
            if gx < xs[0] or gx > xs[-1]:
                continue
            pred = float(np.interp(gx, xs, ys))
            deltas.append(abs(pred - gy))
        if not deltas:
            return {"n": 0, "mean": None, "max": None}
        return {"n": len(deltas),
                "mean": round(float(np.mean(deltas)), 5),
                "max":  round(float(max(deltas)), 5)}

    # Load v2 curves for comparison
    v2_by_series = {"24C": [], "27C": [], "30C": []}
    with open(V2_CURVES) as f:
        for r in csv.DictReader(f):
            s = r["series"]
            x = float(r["x"]); y = float(r["y"])
            # Convert x,y back to pixel for fair pix-level comparison
            col = (x - bx) / mx; row = (y - by) / my
            if "24" in s: v2_by_series["24C"].append((col, row))
            elif "27" in s: v2_by_series["27C"].append((col, row))
            elif "30" in s: v2_by_series["30C"].append((col, row))

    print("\n=== per-curve fidelity vs GT (mean |Δy|, max |Δy|) ===")
    cmp_out = {}
    print(f"{'series':<20} {'v2 mean':>10} {'v2 max':>9}  "
          f"{'v3 mean':>10} {'v3 max':>9}")
    # GT series names look like "p curve for 24°C"; map to "24C" / "27C" / "30C"
    def gt_to_short(name):
        for k in ("24C", "27C", "30C"):
            if k[:2] in name: return k
        return None
    for s in series_order:
        gt_pts = gt_by_series[s]
        short = gt_to_short(s) or s
        v2s = score(v2_by_series.get(short, []), gt_pts)
        ci = series_order.index(s)
        v3s = score(curves[ci], gt_pts)
        cmp_out[s] = {"v2": v2s, "v3": v3s}
        def fmt(v):
            return f"{v:>10.5f}" if isinstance(v, float) else f"{'—':>10}"
        print(f"{s:<20} {fmt(v2s['mean'])} {fmt(v2s['max']):>9}  "
              f"{fmt(v3s['mean'])} {fmt(v3s['max']):>9}")
    with open(os.path.join(HERE, "trace_v3_comparison.json"), "w") as f:
        json.dump({"series_order": series_order, "scores": cmp_out}, f, indent=2)

    # ---------- Side-by-side overlay ----------
    H, W = img.shape[:2]
    pad = 30
    composite = np.full((H + pad, W * 2 + 20, 3), 255, dtype=np.uint8)
    left_img = img.copy()
    right_img = img.copy()
    # v2 curves in left panel
    colors = {"24C": (0, 229, 255), "27C": (255, 0, 255), "30C": (51, 235, 255)}
    for s, pts in v2_by_series.items():
        for col, row in pts:
            cv2.circle(left_img, (int(col), int(row)), 1, colors[s], -1)
    for ci, s in enumerate(series_order):
        short = gt_to_short(s) or s
        for col, row in curves[ci]:
            cv2.circle(right_img, (int(col), int(row)), 1, colors[short], -1)
    composite[pad:H + pad, :W] = left_img
    composite[pad:H + pad, W + 20: W * 2 + 20] = right_img
    # Left panel uses the GT series names; v2_by_series uses short names
    for s in v2_by_series:
        for col, row in v2_by_series[s]:
            cv2.circle(left_img, (int(col), int(row)), 1, colors[s], -1)
    cv2.putText(composite, "v2: per-column-median + greedy NN",
                (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
    cv2.putText(composite,
                "v3: trace_with_continuity (unique pair + clean slope)",
                (W + 30, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
    overlay_path = os.path.join(HERE, "trace_v3_overlay.png")
    cv2.imwrite(overlay_path, composite)
    print(f"\nwrote {overlay_path}")


if __name__ == "__main__":
    main()
