#!/usr/bin/env python3
"""Apply diff-driven update to a claim set.

Workflow:
  1. Compute the source-only (RED) and replot-only (GREEN) masks within the
     plot frame (excluding the legend exclusion box).
  2. For each existing marker claim: if its rendered pixel sits inside a
     replot-only (GREEN) connected component, drop the claim. The diff is
     directly saying "we put a marker here but the source has no data."
  3. For each source-only (RED) connected component: triage by area + shape.
     - Tiny (area < min): ignore (noise).
     - Marker-sized roughly-square (aspect <= aspect_round): add ONE marker
       at the centroid, attribute to nearest series by source pixel color.
     - Elongated (aspect > aspect_round): split into multiple marker
       candidates spaced along the long axis. This handles the case of
       overlapping markers stacked vertically (el-100 parity-0.35 cluster)
       where the merged CC is tall and thin but represents N markers.
     - Big and elongated AND matches a line series' color: add a few
       line samples.
  4. Return updated rows.

GT is never touched. All signals come from source image + current claim set.
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
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")
    x = 10 ** (mx * col + bx) if x_scale == "log10" else mx * col + bx
    y = 10 ** (my * row + by) if y_scale == "log10" else my * row + by
    return float(x), float(y)


def _compute_diff_masks(src, replot, plot_frame_box, legend_excl):
    H, W = src.shape[:2]
    mask = np.zeros((H, W), dtype=bool)
    pf = plot_frame_box
    mask[pf["top"]:pf["bottom"], pf["left"]:pf["right"]] = True
    if legend_excl:
        t, b, l, r = (legend_excl[0], legend_excl[1],
                      legend_excl[2], legend_excl[3])
        mask[int(t):int(b), int(l):int(r)] = False
    # 'Data' = non-white pixel
    src_data = (src.min(axis=2) < 240) & mask
    rep_data = (replot.min(axis=2) < 240) & mask
    return src_data & ~rep_data, rep_data & ~src_data, mask  # missed, extra, frame


def _nearest_series_color(bgr_pixel, tol_table):
    """Return series_id closest to bgr_pixel in BGR distance, or None if no
    series is within its tolerance."""
    best, best_d = None, float("inf")
    for sid, info in tol_table.items():
        target = info["target_bgr"]
        d = float(np.linalg.norm(np.array(bgr_pixel, dtype=np.int32) -
                                   target.astype(np.int32)))
        if d < best_d and d <= info["tolerance"]:
            best_d = d; best = sid
    return best


def _series_marker_layer_pref(chart_metadata, sid):
    """Return whether this series is primarily marker (Scatter Plot) or line."""
    for spec in chart_metadata.get("series_legend", []):
        if spec.get("series_id") == sid:
            if spec.get("marker_shape"):
                return "Scatter Plot"
            if spec.get("line_style"):
                return "Line Graph"
            return "Scatter Plot"
    return "Scatter Plot"


def update_claims(rows, src, replot, calibration, chart_metadata,
                    min_marker_area=8, max_cc_area=2000,
                    aspect_round=1.8, marker_diameter_px=12,
                    drop_threshold_px=10):
    """Returns (new_rows, update_log)."""
    pf = calibration["plot_frame_box"]
    legend_excl = calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    missed_mask, extra_mask, frame_mask = _compute_diff_masks(
        src, replot, pf, legend_excl)

    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")

    # Auto-tune per-series colors (for attributing red CCs)
    tol_table = autotune_tolerances(src, chart_metadata, calibration)

    # Step 1: drop claims whose rendered pixel sits inside an "extra" CC
    n_dropped = 0
    new_rows = []
    for r in rows:
        # Only consider marker-type claims for dropping (line claims are
        # complicated to drop one at a time; defer)
        if r["layer_type"] not in ("Scatter Plot", "Grouped Column Chart"):
            new_rows.append(r)
            continue
        col = _data_to_pixel(r["x"], mx, bx, x_scale)
        row = _data_to_pixel(r["y"], my, by, y_scale)
        if col is None or row is None:
            new_rows.append(r)
            continue
        c = int(col); rr = int(row)
        H, W = src.shape[:2]
        if not (0 <= c < W and 0 <= rr < H):
            new_rows.append(r)
            continue
        # Count "extra-mask" pixels in a small window around the rendered px
        c0 = max(0, c - drop_threshold_px); c1 = min(W, c + drop_threshold_px + 1)
        r0 = max(0, rr - drop_threshold_px); r1 = min(H, rr + drop_threshold_px + 1)
        extra_count = int(extra_mask[r0:r1, c0:c1].sum())
        if extra_count >= 5:
            n_dropped += 1
        else:
            new_rows.append(r)

    # Step 2: add new claims from "missed" CCs
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
        missed_mask.astype(np.uint8), connectivity=8)
    n_added_marker = 0
    n_added_line   = 0
    n_skipped_noattr = 0
    for lbl in range(1, n_lbl):
        x_l, y_l, w_l, h_l, area = stats[lbl]
        if area < min_marker_area: continue
        if area > max_cc_area:     continue
        aspect = max(w_l, h_l) / max(1, min(w_l, h_l))
        cx = x_l + w_l // 2; cy = y_l + h_l // 2

        # Get the dominant color in the CC by sampling its centroid
        sample = src[cy, cx]
        sid = _nearest_series_color(sample, tol_table)
        if sid is None:
            n_skipped_noattr += 1
            continue
        layer_pref = _series_marker_layer_pref(chart_metadata, sid)

        if aspect > aspect_round and h_l > marker_diameter_px * 1.5:
            # Tall thin column — possibly a cluster of overlapping markers
            # OR a piece of line. If the series is primarily a marker series,
            # split into N markers spaced by marker_diameter_px.
            if layer_pref == "Scatter Plot":
                n_markers = max(1, int(round(h_l / marker_diameter_px)))
                for i in range(n_markers):
                    yy = y_l + int((i + 0.5) * h_l / n_markers)
                    x_data, y_data = _pixel_to_data(cx, yy, calibration)
                    new_rows.append({"layer_idx": 0,
                                      "layer_type": "Scatter Plot",
                                      "series": sid,
                                      "x": x_data, "y": y_data})
                    n_added_marker += 1
            else:
                # Line series — add a single line sample at the centroid
                x_data, y_data = _pixel_to_data(cx, cy, calibration)
                new_rows.append({"layer_idx": 0, "layer_type": "Line Graph",
                                  "series": sid, "x": x_data, "y": y_data})
                n_added_line += 1
        elif aspect > aspect_round and w_l > marker_diameter_px * 1.5:
            # Wide thin row — probably a horizontal line segment; add sample
            x_data, y_data = _pixel_to_data(cx, cy, calibration)
            new_rows.append({"layer_idx": 0, "layer_type": "Line Graph",
                              "series": sid, "x": x_data, "y": y_data})
            n_added_line += 1
        else:
            # Roundish blob — add one marker
            x_data, y_data = _pixel_to_data(cx, cy, calibration)
            new_rows.append({"layer_idx": 0,
                              "layer_type": "Scatter Plot",
                              "series": sid, "x": x_data, "y": y_data})
            n_added_marker += 1

    log = {
        "dropped_marker_claims": n_dropped,
        "added_marker_claims":   n_added_marker,
        "added_line_samples":    n_added_line,
        "skipped_no_color_match": n_skipped_noattr,
        "missed_px_before": int(missed_mask.sum()),
        "extra_px_before":  int(extra_mask.sum()),
    }
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

    # Iteration 0: render bootstrap
    rep0 = render(image_size, cal, md, rows0)
    cv2.imwrite(os.path.join(out_dir, "iter0_replot.png"), rep0)

    # Iteration 0 diff
    pf = cal["plot_frame_box"]
    legend_excl = cal.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    missed0, extra0, _ = _compute_diff_masks(src, rep0, pf, legend_excl)

    # Apply the diff-driven update
    rows1, log = update_claims(rows0, src, rep0, cal, md)

    # Iteration 1: render updated, re-diff
    rep1 = render(image_size, cal, md, rows1)
    cv2.imwrite(os.path.join(out_dir, "iter1_replot.png"), rep1)
    missed1, extra1, _ = _compute_diff_masks(src, rep1, pf, legend_excl)

    # Write updated data
    with open(os.path.join(out_dir, "iter1_data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in rows1:
            w.writerow([r["layer_idx"], r["layer_type"], r["series"],
                          r["x"], r["y"]])

    summary = {
        "iter0_claims": len(rows0),
        "iter1_claims": len(rows1),
        "update_log":   log,
        "iter0_missed_px": int(missed0.sum()),
        "iter0_extra_px":  int(extra0.sum()),
        "iter1_missed_px": int(missed1.sum()),
        "iter1_extra_px":  int(extra1.sum()),
        "missed_delta":    int(missed1.sum() - missed0.sum()),
        "extra_delta":     int(extra1.sum() - extra0.sum()),
    }
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Compose diff images for both iterations
    def render_diff(missed, extra, H, W):
        out = np.full((H, W, 3), 255, dtype=np.uint8)
        # Note: agree mask isn't shown to keep visual cleaner
        out[missed] = (0, 0, 220)
        out[extra]  = (0, 220, 0)
        return out

    diff0 = render_diff(missed0, extra0, H, W)
    diff1 = render_diff(missed1, extra1, H, W)
    cv2.imwrite(os.path.join(out_dir, "iter0_diff.png"), diff0)
    cv2.imwrite(os.path.join(out_dir, "iter1_diff.png"), diff1)

    # Side-by-side: source | iter0 diff | iter1 diff
    h = 380
    def sc(im, ht):
        return cv2.resize(im, (int(im.shape[1] * ht / im.shape[0]), ht),
                           interpolation=cv2.INTER_AREA)
    a = sc(src, h); b = sc(diff0, h); c = sc(diff1, h)
    gut = np.ones((h, 15, 3), dtype=np.uint8) * 255
    cv2.imwrite(os.path.join(out_dir, "before_after_diff.png"),
                 np.hstack([a, gut, b, gut, c]))

    print("\n--- Diff-driven single update on aedes el-100 ---")
    print(f"  iter 0 claims: {summary['iter0_claims']}")
    print(f"  update log:    {json.dumps(log, indent=4)}")
    print(f"  iter 1 claims: {summary['iter1_claims']}")
    print(f"")
    print(f"  iter 0 MISSED (source-only) px: {summary['iter0_missed_px']:>6}")
    print(f"  iter 1 MISSED (source-only) px: {summary['iter1_missed_px']:>6}  "
            f"delta = {summary['missed_delta']:+d}")
    print(f"  iter 0 EXTRA  (replot-only) px: {summary['iter0_extra_px']:>6}")
    print(f"  iter 1 EXTRA  (replot-only) px: {summary['iter1_extra_px']:>6}  "
            f"delta = {summary['extra_delta']:+d}")
    print(f"\nOutputs in {out_dir}/")


if __name__ == "__main__":
    main()
