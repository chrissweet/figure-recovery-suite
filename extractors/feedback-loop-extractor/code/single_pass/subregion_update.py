#!/usr/bin/env python3
"""Per-CC sub-region absdiff update.

Improvement over absdiff_update.py: instead of classifying each
disagreement CC by its MEAN colors, decompose every disagreement pixel
into one of three categories and CC each category separately:

  src_only = source non-white AND replot is white       -> ADD claim
  rep_only = source is white AND replot non-white       -> DROP nearest claim
  mismatch = source non-white AND replot non-white      -> DROP + ADD

Each sub-mask is connected-componented independently, so add and drop
actions operate on the right pixel subsets even when they sit near each
other (which is exactly the el-100 pattern: missed markers stacked next
to existing claims, near a line trace that has extras).

Color attribution within a sub-mask CC: use the MOST SATURATED pixel
(furthest from white), not the CC mean, because anti-aliased borders
bias the mean toward white.
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


THRESH_DATA = 240            # pixel is "data" iff any channel < this
THRESH_DIFF = 30             # absdiff intensity to count as disagreement
MIN_CC_AREA = 6
MAX_CC_AREA = 3000
MARKER_DIAMETER_PX = 12
ASPECT_ROUND = 1.8
DROP_RADIUS_PX = 10


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


def _most_saturated_pixel(img_bgr, cc_mask):
    """Within cc_mask, find the pixel with the strongest color signal
    (furthest from white). Returns its BGR value."""
    H, W = img_bgr.shape[:2]
    # saturation proxy = 255 - min channel value (white -> 0, deep color -> 255)
    sat = 255 - img_bgr.min(axis=2)
    sat_masked = np.where(cc_mask, sat, -1)
    idx_flat = int(np.argmax(sat_masked))
    r_idx = idx_flat // W; c_idx = idx_flat % W
    return img_bgr[r_idx, c_idx], (c_idx, r_idx)


def _nearest_series(bgr_pixel, tol_table):
    best, best_d = None, float("inf")
    for sid, info in tol_table.items():
        d = float(np.linalg.norm(
            np.array(bgr_pixel, dtype=np.int32)
            - info["target_bgr"].astype(np.int32)))
        if d < best_d and d <= info["tolerance"]:
            best_d = d; best = sid
    return best


def _layer_pref(chart_metadata, sid):
    for spec in chart_metadata.get("series_legend", []):
        if spec.get("series_id") == sid:
            if spec.get("marker_shape"): return "Scatter Plot"
            if spec.get("line_style"):   return "Line Graph"
            return "Scatter Plot"
    return "Scatter Plot"


def _add_proposals_from_cc(stats_lbl, cc_mask, src, calibration,
                              chart_metadata, tol_table):
    """One sub-region CC -> 0, 1, or N additions."""
    x_l, y_l, w_l, h_l, area = stats_lbl
    if area < MIN_CC_AREA or area > MAX_CC_AREA:
        return []
    sat_bgr, (sx, sy) = _most_saturated_pixel(src, cc_mask)
    sid = _nearest_series(sat_bgr, tol_table)
    if sid is None:
        return []
    layer_pref = _layer_pref(chart_metadata, sid)
    aspect = max(w_l, h_l) / max(1, min(w_l, h_l))
    cx = x_l + w_l // 2; cy = y_l + h_l // 2
    out = []

    if (aspect > ASPECT_ROUND and h_l > MARKER_DIAMETER_PX * 1.5
            and layer_pref == "Scatter Plot"):
        # Tall thin marker-series CC = overlapping markers stacked vertically.
        n = max(1, int(round(h_l / MARKER_DIAMETER_PX)))
        for i in range(n):
            yy = y_l + int((i + 0.5) * h_l / n)
            x_d, y_d = _pixel_to_data(cx, yy, calibration)
            out.append({"layer_idx": 0, "layer_type": "Scatter Plot",
                          "series": sid, "x": x_d, "y": y_d})
    elif aspect > ASPECT_ROUND and w_l > MARKER_DIAMETER_PX * 1.5:
        # Wide thin = line segment
        x_d, y_d = _pixel_to_data(cx, cy, calibration)
        out.append({"layer_idx": 0, "layer_type": "Line Graph",
                      "series": sid, "x": x_d, "y": y_d})
    else:
        layer_type = ("Line Graph" if layer_pref == "Line Graph"
                       else "Scatter Plot")
        x_d, y_d = _pixel_to_data(cx, cy, calibration)
        out.append({"layer_idx": 0, "layer_type": layer_type,
                      "series": sid, "x": x_d, "y": y_d})
    return out


def update_from_subregions(rows, src, replot, calibration, chart_metadata,
                              tol_table):
    H, W = src.shape[:2]
    frame = _frame_mask((H, W), calibration)

    src_is_data = (src.min(axis=2) < THRESH_DATA) & frame
    rep_is_data = (replot.min(axis=2) < THRESH_DATA) & frame
    diff_int    = cv2.absdiff(src, replot).max(axis=2)
    disagree    = (diff_int > THRESH_DIFF) & frame

    src_only_mask = src_is_data & ~rep_is_data & disagree
    rep_only_mask = ~src_is_data & rep_is_data & disagree
    mismatch_mask = src_is_data & rep_is_data & disagree

    # Pixel-position index of marker-type claims for nearest-search drops
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    xs = x_ax.get("scale", "linear"); ys = y_ax.get("scale", "linear")
    claim_index = []
    for i, r in enumerate(rows):
        if r["layer_type"] not in ("Scatter Plot", "Grouped Column Chart"):
            continue
        col = _data_to_pixel(r["x"], mx, bx, xs)
        row = _data_to_pixel(r["y"], my, by, ys)
        if col is None or row is None: continue
        claim_index.append((int(col), int(row), i))

    drop_indices = set()
    additions = []
    log = {"src_only_cc": 0, "rep_only_cc": 0, "mismatch_cc": 0,
            "added_from_src_only": 0, "dropped_from_rep_only": 0,
            "dropped_from_mismatch": 0, "added_from_mismatch": 0,
            "skipped_too_small": 0, "skipped_too_big": 0,
            "skipped_unattributable": 0}

    # ---- src_only sub-mask: ADD ----
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
        src_only_mask.astype(np.uint8), connectivity=8)
    for lbl in range(1, n_lbl):
        x_l, y_l, w_l, h_l, area = stats[lbl]
        if area < MIN_CC_AREA: log["skipped_too_small"] += 1; continue
        if area > MAX_CC_AREA: log["skipped_too_big"] += 1; continue
        cc_mask = (labels == lbl)
        log["src_only_cc"] += 1
        new = _add_proposals_from_cc(stats[lbl], cc_mask, src,
                                       calibration, chart_metadata, tol_table)
        if not new: log["skipped_unattributable"] += 1
        else:
            additions.extend(new)
            log["added_from_src_only"] += len(new)

    # ---- rep_only sub-mask: DROP nearest claim ----
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
        rep_only_mask.astype(np.uint8), connectivity=8)
    for lbl in range(1, n_lbl):
        x_l, y_l, w_l, h_l, area = stats[lbl]
        if area < MIN_CC_AREA: log["skipped_too_small"] += 1; continue
        if area > MAX_CC_AREA: log["skipped_too_big"] += 1; continue
        log["rep_only_cc"] += 1
        cx = x_l + w_l // 2; cy = y_l + h_l // 2
        best_i, best_d = None, float("inf")
        for col_i, row_i, idx_in_rows in claim_index:
            if idx_in_rows in drop_indices: continue
            d = (col_i - cx) ** 2 + (row_i - cy) ** 2
            if d < best_d and d <= DROP_RADIUS_PX ** 2:
                best_d = d; best_i = idx_in_rows
        if best_i is not None:
            drop_indices.add(best_i)
            log["dropped_from_rep_only"] += 1

    # ---- mismatch sub-mask: DROP + ADD with source's color ----
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
        mismatch_mask.astype(np.uint8), connectivity=8)
    for lbl in range(1, n_lbl):
        x_l, y_l, w_l, h_l, area = stats[lbl]
        if area < MIN_CC_AREA: log["skipped_too_small"] += 1; continue
        if area > MAX_CC_AREA: log["skipped_too_big"] += 1; continue
        cc_mask = (labels == lbl)
        log["mismatch_cc"] += 1
        cx = x_l + w_l // 2; cy = y_l + h_l // 2
        # Drop nearest existing claim
        best_i, best_d = None, float("inf")
        for col_i, row_i, idx_in_rows in claim_index:
            if idx_in_rows in drop_indices: continue
            d = (col_i - cx) ** 2 + (row_i - cy) ** 2
            if d < best_d and d <= DROP_RADIUS_PX ** 2:
                best_d = d; best_i = idx_in_rows
        if best_i is not None:
            drop_indices.add(best_i)
            log["dropped_from_mismatch"] += 1
        # Add re-attributed claim using saturated source color
        new = _add_proposals_from_cc(stats[lbl], cc_mask, src,
                                       calibration, chart_metadata, tol_table)
        if new:
            additions.extend(new)
            log["added_from_mismatch"] += len(new)

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
    rows1, log = update_from_subregions(rows0, src, rep0, cal, md, tol_table)

    rep1 = render(image_size, cal, md, rows1)
    cv2.imwrite(os.path.join(out_dir, "iter1_replot.png"), rep1)

    with open(os.path.join(out_dir, "iter1_data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in rows1:
            w.writerow([r["layer_idx"], r["layer_type"], r["series"],
                          r["x"], r["y"]])

    frame = _frame_mask((H, W), cal)
    def residual_stats(rep):
        d = cv2.absdiff(src, rep).max(axis=2)[frame]
        return {"mean": round(float(d.mean()), 3),
                "px_gt_30":  int((d > 30).sum()),
                "px_gt_60":  int((d > 60).sum()),
                "px_gt_120": int((d > 120).sum())}

    res0 = residual_stats(rep0); res1 = residual_stats(rep1)
    summary = {"update_log": log, "iter0_residual": res0,
                "iter1_residual": res1,
                "delta_px_gt_30":  res1["px_gt_30"]  - res0["px_gt_30"],
                "delta_px_gt_60":  res1["px_gt_60"]  - res0["px_gt_60"],
                "delta_px_gt_120": res1["px_gt_120"] - res0["px_gt_120"]}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    def render_diff(rep):
        d = cv2.absdiff(src, rep)
        out = d.copy(); out[~frame] = (255, 255, 255)
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

    print("--- sub-region absdiff update on aedes el-100 ---")
    print(f"update log:")
    for k, v in log.items():
        print(f"  {k}: {v}")
    print()
    print(f"residual at threshold 30 : iter0={res0['px_gt_30']:>6}  iter1={res1['px_gt_30']:>6}  delta={summary['delta_px_gt_30']:+d}")
    print(f"residual at threshold 60 : iter0={res0['px_gt_60']:>6}  iter1={res1['px_gt_60']:>6}  delta={summary['delta_px_gt_60']:+d}")
    print(f"residual at threshold 120: iter0={res0['px_gt_120']:>6}  iter1={res1['px_gt_120']:>6}  delta={summary['delta_px_gt_120']:+d}")
    print(f"mean residual            : iter0={res0['mean']:>6}  iter1={res1['mean']:>6}")


if __name__ == "__main__":
    main()
