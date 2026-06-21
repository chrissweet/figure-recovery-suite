#!/usr/bin/env python3
"""Update claims using the absdiff signal.

Pipeline:
  1. Render the bootstrap claim set to a pixel-replot.
  2. Compute |source - replot| within the plot frame; threshold per-pixel
     max-channel deviation > THRESH to get a disagreement mask.
  3. Connected-component the disagreement mask.
  4. For each CC, sample SOURCE mean color and REPLOT mean color; classify:
       - source has color, replot is white  -> MISSED -> add claim of source color
       - replot has color, source is white  -> EXTRA  -> drop nearest claim
       - both colored, different colors     -> COLOR MISMATCH -> drop + add
  5. Re-render, re-diff, compare residuals.

Color attribution is by direct sample at the CC centroid (matched against
the autotuned per-series target_bgr), not by autotuned-mask-then-search.
More robust than the binary-mask approach because we don't need a single
correct global tolerance.
"""
import csv
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "render"))
sys.path.insert(0, os.path.join(HERE, "..", "predicates"))
from pixel_replot import render
from color_tolerance import autotune as autotune_tolerances


THRESH = 30                  # per-pixel max-channel deviation to count
MIN_CC_AREA = 8
MAX_CC_AREA = 3000
MARKER_DIAMETER_PX = 12
ASPECT_ROUND = 1.8
DROP_RADIUS_PX = 8           # neighborhood for dropping a claim at an extra CC


def _data_to_pixel(value, m, b, scale):
    if scale == "log10":
        if value <= 0: return None
        return (np.log10(value) - b) / m
    return (value - b) / m


def _pixel_to_data(col, row, calibration):
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    xs = x_ax.get("scale", "linear"); ys = y_ax.get("scale", "linear")
    x = 10 ** (mx * col + bx) if xs == "log10" else mx * col + bx
    y = 10 ** (my * row + by) if ys == "log10" else my * row + by
    return float(x), float(y)


def _frame_mask(shape, calibration):
    H, W = shape[:2]
    pf = calibration["plot_frame_box"]
    m = np.zeros((H, W), dtype=bool)
    m[pf["top"]:pf["bottom"], pf["left"]:pf["right"]] = True
    legend = calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    if legend:
        t, b, l, r = legend[0], legend[1], legend[2], legend[3]
        m[int(t):int(b), int(l):int(r)] = False
    return m


def _nearest_series(bgr_pixel, tol_table):
    """Return series_id closest to bgr_pixel; require within tolerance."""
    best_sid, best_d = None, float("inf")
    for sid, info in tol_table.items():
        d = float(np.linalg.norm(
            np.array(bgr_pixel, dtype=np.int32) - info["target_bgr"].astype(np.int32)))
        if d < best_d and d <= info["tolerance"]:
            best_d = d; best_sid = sid
    return best_sid


def _series_marker_layer_pref(chart_metadata, sid):
    for spec in chart_metadata.get("series_legend", []):
        if spec.get("series_id") == sid:
            if spec.get("marker_shape"):
                return "Scatter Plot"
            if spec.get("line_style"):
                return "Line Graph"
            return "Scatter Plot"
    return "Scatter Plot"


def update_from_absdiff(rows, src, replot, calibration, chart_metadata,
                          tol_table):
    H, W = src.shape[:2]
    frame = _frame_mask((H, W), calibration)

    # Per-pixel disagreement
    diff = cv2.absdiff(src, replot)
    intensity = diff.max(axis=2)
    disagree = (intensity > THRESH) & frame

    # Connected components of disagreement
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
        disagree.astype(np.uint8), connectivity=8)

    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    xs = x_ax.get("scale", "linear"); ys = y_ax.get("scale", "linear")

    # Index claims by pixel position for fast nearest-search
    claim_index = []  # list of (col, row, idx_in_rows)
    for i, r in enumerate(rows):
        if r["layer_type"] not in ("Scatter Plot", "Grouped Column Chart"):
            continue
        col = _data_to_pixel(r["x"], mx, bx, xs)
        row = _data_to_pixel(r["y"], my, by, ys)
        if col is None or row is None: continue
        claim_index.append((int(col), int(row), i))

    drop_indices = set()
    additions = []
    log = {"missed_added": 0, "extra_dropped": 0,
            "color_mismatch_dropped": 0, "color_mismatch_added": 0,
            "skipped_unattributable": 0, "skipped_too_small": 0,
            "skipped_too_big": 0, "n_cc": int(n_lbl - 1)}

    for lbl in range(1, n_lbl):
        x_l, y_l, w_l, h_l, area = stats[lbl]
        if area < MIN_CC_AREA:
            log["skipped_too_small"] += 1; continue
        if area > MAX_CC_AREA:
            log["skipped_too_big"] += 1; continue

        cc_mask = (labels == lbl)
        src_mean = src[cc_mask].mean(axis=0)
        rep_mean = replot[cc_mask].mean(axis=0)
        src_is_data = src_mean.min() < 240
        rep_is_data = rep_mean.min() < 240
        cx = x_l + w_l // 2; cy = y_l + h_l // 2
        aspect = max(w_l, h_l) / max(1, min(w_l, h_l))

        if src_is_data and not rep_is_data:
            # MISSED — source has data, replot doesn't.
            sid = _nearest_series(src_mean, tol_table)
            if sid is None:
                log["skipped_unattributable"] += 1
                continue
            layer_pref = _series_marker_layer_pref(chart_metadata, sid)

            # Tall thin CC of a marker series -> cluster of overlapping markers
            if (aspect > ASPECT_ROUND and h_l > MARKER_DIAMETER_PX * 1.5
                    and layer_pref == "Scatter Plot"):
                n_markers = max(1, int(round(h_l / MARKER_DIAMETER_PX)))
                for i in range(n_markers):
                    yy = y_l + int((i + 0.5) * h_l / n_markers)
                    x_data, y_data = _pixel_to_data(cx, yy, calibration)
                    additions.append({"layer_idx": 0,
                                       "layer_type": "Scatter Plot",
                                       "series": sid,
                                       "x": x_data, "y": y_data})
                    log["missed_added"] += 1
            elif aspect > ASPECT_ROUND and w_l > MARKER_DIAMETER_PX * 1.5:
                # Elongated horizontally -> line sample
                x_data, y_data = _pixel_to_data(cx, cy, calibration)
                additions.append({"layer_idx": 0,
                                   "layer_type": "Line Graph",
                                   "series": sid,
                                   "x": x_data, "y": y_data})
                log["missed_added"] += 1
            else:
                # Round blob -> one marker (or line sample for line series)
                layer_type = ("Line Graph" if layer_pref == "Line Graph"
                               else "Scatter Plot")
                x_data, y_data = _pixel_to_data(cx, cy, calibration)
                additions.append({"layer_idx": 0, "layer_type": layer_type,
                                   "series": sid,
                                   "x": x_data, "y": y_data})
                log["missed_added"] += 1

        elif rep_is_data and not src_is_data:
            # EXTRA — replot has data, source doesn't.
            # Drop the nearest claim within DROP_RADIUS_PX.
            best_i, best_d = None, float("inf")
            for col_i, row_i, idx_in_rows in claim_index:
                if idx_in_rows in drop_indices: continue
                d = (col_i - cx) ** 2 + (row_i - cy) ** 2
                if d < best_d and d <= DROP_RADIUS_PX ** 2:
                    best_d = d; best_i = idx_in_rows
            if best_i is not None:
                drop_indices.add(best_i)
                log["extra_dropped"] += 1

        elif src_is_data and rep_is_data:
            # COLOR MISMATCH — both colored but disagree.
            # Drop the nearest claim, add the source-colored claim.
            best_i, best_d = None, float("inf")
            for col_i, row_i, idx_in_rows in claim_index:
                if idx_in_rows in drop_indices: continue
                d = (col_i - cx) ** 2 + (row_i - cy) ** 2
                if d < best_d and d <= DROP_RADIUS_PX ** 2:
                    best_d = d; best_i = idx_in_rows
            if best_i is not None:
                drop_indices.add(best_i)
                log["color_mismatch_dropped"] += 1
            sid_new = _nearest_series(src_mean, tol_table)
            if sid_new is not None:
                layer_type_new = ("Scatter Plot"
                                    if _series_marker_layer_pref(
                                          chart_metadata, sid_new) == "Scatter Plot"
                                    else "Line Graph")
                x_data, y_data = _pixel_to_data(cx, cy, calibration)
                additions.append({"layer_idx": 0,
                                   "layer_type": layer_type_new,
                                   "series": sid_new,
                                   "x": x_data, "y": y_data})
                log["color_mismatch_added"] += 1

    # Apply changes
    new_rows = [r for i, r in enumerate(rows) if i not in drop_indices]
    new_rows.extend(additions)
    log["claims_before"] = len(rows)
    log["claims_after"]  = len(new_rows)
    return new_rows, log


def main():
    bootstrap_dir = sys.argv[1]
    src_path = sys.argv[2]
    out_dir = sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    cal = json.load(open(os.path.join(bootstrap_dir, "calibration.json")))
    md  = json.load(open(os.path.join(bootstrap_dir, "chart_metadata.json")))
    rows0 = []
    with open(os.path.join(bootstrap_dir, "data.csv")) as f:
        for r in csv.DictReader(f):
            try:
                rows0.append({"layer_idx": int(r.get("layer_idx", "0") or 0),
                                "layer_type": r.get("layer_type", "Scatter Plot"),
                                "series": r.get("series", "default"),
                                "x": float(r["x"]), "y": float(r["y"])})
            except (KeyError, ValueError):
                continue

    src = cv2.imread(src_path)
    H, W = src.shape[:2]
    image_size = {"width": W, "height": H}

    rep0 = render(image_size, cal, md, rows0)
    cv2.imwrite(os.path.join(out_dir, "iter0_replot.png"), rep0)

    tol_table = autotune_tolerances(src, md, cal)
    rows1, log = update_from_absdiff(rows0, src, rep0, cal, md, tol_table)

    rep1 = render(image_size, cal, md, rows1)
    cv2.imwrite(os.path.join(out_dir, "iter1_replot.png"), rep1)

    with open(os.path.join(out_dir, "iter1_data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in rows1:
            w.writerow([r["layer_idx"], r["layer_type"], r["series"],
                          r["x"], r["y"]])

    # Quantify residuals
    frame = _frame_mask((H, W), cal)
    def residual_stats(rep):
        d = cv2.absdiff(src, rep).max(axis=2)[frame]
        return {"mean": float(d.mean()),
                "px_gt_30":  int((d > 30).sum()),
                "px_gt_60":  int((d > 60).sum()),
                "px_gt_120": int((d > 120).sum())}

    res0 = residual_stats(rep0)
    res1 = residual_stats(rep1)
    summary = {"update_log": log, "iter0_residual": res0,
                "iter1_residual": res1,
                "delta_px_gt_30":  res1["px_gt_30"]  - res0["px_gt_30"],
                "delta_px_gt_60":  res1["px_gt_60"]  - res0["px_gt_60"],
                "delta_px_gt_120": res1["px_gt_120"] - res0["px_gt_120"]}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Visual: source | iter0 absdiff | iter1 absdiff
    def render_diff(rep):
        d = cv2.absdiff(src, rep)
        out = d.copy()
        out[~frame] = (255, 255, 255)
        return out
    d0 = render_diff(rep0); d1 = render_diff(rep1)
    cv2.imwrite(os.path.join(out_dir, "iter0_absdiff.png"), d0)
    cv2.imwrite(os.path.join(out_dir, "iter1_absdiff.png"), d1)
    h = 360
    def sc(im, ht):
        return cv2.resize(im, (int(im.shape[1] * ht / im.shape[0]), ht),
                           interpolation=cv2.INTER_AREA)
    a, b, c = sc(src, h), sc(d0, h), sc(d1, h)
    gut = np.ones((h, 15, 3), dtype=np.uint8) * 255
    cv2.imwrite(os.path.join(out_dir, "before_after_absdiff.png"),
                 np.hstack([a, gut, b, gut, c]))

    # Console summary
    print("--- absdiff-driven single update on aedes el-100 ---")
    print(f"update log: {json.dumps(log, indent=2)}")
    print(f"\niter 0 residual: {json.dumps(res0, indent=2)}")
    print(f"iter 1 residual: {json.dumps(res1, indent=2)}")
    print(f"\ndelta px > 30  channels: {summary['delta_px_gt_30']:+d}")
    print(f"delta px > 60  channels: {summary['delta_px_gt_60']:+d}")
    print(f"delta px > 120 channels: {summary['delta_px_gt_120']:+d}")


if __name__ == "__main__":
    main()
