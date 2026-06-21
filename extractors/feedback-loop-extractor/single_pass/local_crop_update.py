#!/usr/bin/env python3
"""Local-crop per-CC analysis (sub-region absdiff update v2).

For each disagreement CC:
  1. Crop both source and replot to the CC's bounding box + padding.
  2. Save side_by_side crop to disk so the per-region diagnosis is
     inspectable (and could in principle be fed to a vision-LLM subagent
     for per-region adjudication; for now we do simple local pixel analysis).
  3. Within the LOCAL CROP, sample the most-saturated source pixel and the
     most-saturated replot pixel - those are the actual rendered colors
     for the local series, no autotune required.
  4. Attribute by NEAREST series hex in chart_metadata.series_legend
     (no tolerance gate; pick the closest). Because the local sample IS the
     rendered color, "closest" is meaningful - there's no global brittleness.
  5. Classify the CC by source / replot color presence:
       src colored, rep ~white -> ADD claim of source series
       rep colored, src ~white -> DROP nearest claim of replot series
       both colored -> if same series -> minor position/shape mismatch
                       if different -> DROP rep series + ADD src series

The key change vs subregion_update.py is that color attribution happens
LOCALLY (per-CC source pixel against the full legend) without needing
a global autotuned tolerance table.
"""
import csv
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "render"))
from pixel_replot import render


THRESH_DIFF = 30
MIN_CC_AREA = 6
MAX_CC_AREA = 4000
CROP_PADDING = 8
MARKER_DIAMETER_PX = 12
ASPECT_ROUND = 1.8
DROP_RADIUS_PX = 12
SATURATION_FLOOR = 40


def _hex_to_bgr(hex_str):
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return np.array([b, g, r], dtype=np.int32)


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


def _most_saturated(crop_bgr):
    H, W = crop_bgr.shape[:2]
    if H == 0 or W == 0: return None
    sat = 255 - crop_bgr.min(axis=2)
    idx_flat = int(np.argmax(sat))
    r_i = idx_flat // W; c_i = idx_flat % W
    bgr = crop_bgr[r_i, c_i]
    if (255 - int(bgr.min())) < SATURATION_FLOOR:
        return None
    return bgr


def _nearest_series_unconditional(bgr_pixel, series_legend):
    best, best_d = None, float("inf")
    for spec in series_legend:
        hex_col = spec.get("color", "")
        if not hex_col.startswith("#"): continue
        tgt = _hex_to_bgr(hex_col)
        d = float(np.linalg.norm(np.array(bgr_pixel, dtype=np.int32) - tgt))
        if d < best_d:
            best_d = d; best = spec
    return best, best_d


def _layer_pref(spec):
    if spec.get("marker_shape"): return "Scatter Plot"
    if spec.get("line_style"):   return "Line Graph"
    return "Scatter Plot"


def update_via_local_crops(rows, src, rep, calibration, chart_metadata,
                              crops_out_dir=None):
    H, W = src.shape[:2]
    frame = _frame_mask((H, W), calibration)
    diff_int = cv2.absdiff(src, rep).max(axis=2)
    disagree = (diff_int > THRESH_DIFF) & frame
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
        disagree.astype(np.uint8), connectivity=8)

    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    xs = x_ax.get("scale", "linear"); ys = y_ax.get("scale", "linear")

    series_legend = chart_metadata.get("series_legend", [])

    claim_index = []
    for i, r in enumerate(rows):
        if r["layer_type"] not in ("Scatter Plot", "Grouped Column Chart"):
            continue
        col = _data_to_pixel(r["x"], mx, bx, xs)
        row = _data_to_pixel(r["y"], my, by, ys)
        if col is None or row is None: continue
        claim_index.append((int(col), int(row), i, r["series"]))

    drop_indices = set()
    additions = []
    log = {"n_cc": int(n_lbl - 1), "skipped_size": 0,
            "ADD_src_only": 0, "DROP_rep_only": 0,
            "DROP_mismatch": 0, "ADD_mismatch": 0,
            "AGREE_same_series": 0,
            "no_source_signal": 0, "no_replot_signal_for_drop": 0}

    if crops_out_dir:
        os.makedirs(crops_out_dir, exist_ok=True)

    for lbl in range(1, n_lbl):
        x_l, y_l, w_l, h_l, area = stats[lbl]
        if area < MIN_CC_AREA or area > MAX_CC_AREA:
            log["skipped_size"] += 1
            continue
        c0 = max(0, x_l - CROP_PADDING); c1 = min(W, x_l + w_l + CROP_PADDING)
        r0 = max(0, y_l - CROP_PADDING); r1 = min(H, y_l + h_l + CROP_PADDING)
        src_crop = src[r0:r1, c0:c1]; rep_crop = rep[r0:r1, c0:c1]
        src_sample = _most_saturated(src_crop)
        rep_sample = _most_saturated(rep_crop)
        cx = x_l + w_l // 2; cy = y_l + h_l // 2
        aspect = max(w_l, h_l) / max(1, min(w_l, h_l))

        if crops_out_dir:
            sh, sw = src_crop.shape[:2]
            gut = np.ones((sh, 4, 3), dtype=np.uint8) * 255
            sxs = np.hstack([src_crop, gut, rep_crop])
            if sh < 30:
                sxs = cv2.resize(sxs, (sxs.shape[1] * 4, sxs.shape[0] * 4),
                                   interpolation=cv2.INTER_NEAREST)
            cv2.imwrite(os.path.join(crops_out_dir,
                                        f"cc{lbl:03d}_a{int(area)}_{cx}_{cy}.png"), sxs)

        src_present = src_sample is not None
        rep_present = rep_sample is not None

        if src_present and not rep_present:
            spec, _ = _nearest_series_unconditional(src_sample, series_legend)
            if spec is None: log["no_source_signal"] += 1; continue
            sid = spec["series_id"]; pref = _layer_pref(spec)
            if (aspect > ASPECT_ROUND and h_l > MARKER_DIAMETER_PX * 1.5
                    and pref == "Scatter Plot"):
                n = max(1, int(round(h_l / MARKER_DIAMETER_PX)))
                for i in range(n):
                    yy = y_l + int((i + 0.5) * h_l / n)
                    x_d, y_d = _pixel_to_data(cx, yy, calibration)
                    additions.append({"layer_idx": 0,
                                       "layer_type": "Scatter Plot",
                                       "series": sid, "x": x_d, "y": y_d})
                log["ADD_src_only"] += n
            else:
                lt = "Line Graph" if pref == "Line Graph" else "Scatter Plot"
                x_d, y_d = _pixel_to_data(cx, cy, calibration)
                additions.append({"layer_idx": 0, "layer_type": lt,
                                   "series": sid, "x": x_d, "y": y_d})
                log["ADD_src_only"] += 1

        elif rep_present and not src_present:
            best_i, best_d = None, float("inf")
            for col_i, row_i, idx, _sid in claim_index:
                if idx in drop_indices: continue
                d = (col_i - cx) ** 2 + (row_i - cy) ** 2
                if d < best_d and d <= DROP_RADIUS_PX ** 2:
                    best_d = d; best_i = idx
            if best_i is not None:
                drop_indices.add(best_i); log["DROP_rep_only"] += 1
            else:
                log["no_replot_signal_for_drop"] += 1

        elif src_present and rep_present:
            spec_src, _ = _nearest_series_unconditional(src_sample, series_legend)
            spec_rep, _ = _nearest_series_unconditional(rep_sample, series_legend)
            same = (spec_src and spec_rep
                      and spec_src["series_id"] == spec_rep["series_id"])
            if same:
                log["AGREE_same_series"] += 1; continue
            if spec_rep:
                best_i, best_d = None, float("inf")
                for col_i, row_i, idx, sid_cl in claim_index:
                    if idx in drop_indices: continue
                    if sid_cl != spec_rep["series_id"]: continue
                    d = (col_i - cx) ** 2 + (row_i - cy) ** 2
                    if d < best_d and d <= DROP_RADIUS_PX ** 2:
                        best_d = d; best_i = idx
                if best_i is not None:
                    drop_indices.add(best_i); log["DROP_mismatch"] += 1
            if spec_src:
                sid = spec_src["series_id"]; pref = _layer_pref(spec_src)
                lt = "Line Graph" if pref == "Line Graph" else "Scatter Plot"
                x_d, y_d = _pixel_to_data(cx, cy, calibration)
                additions.append({"layer_idx": 0, "layer_type": lt,
                                   "series": sid, "x": x_d, "y": y_d})
                log["ADD_mismatch"] += 1

    new_rows = [r for i, r in enumerate(rows) if i not in drop_indices]
    new_rows.extend(additions)
    log["claims_before"] = len(rows); log["claims_after"] = len(new_rows)
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

    rows1, log = update_via_local_crops(rows0, src, rep0, cal, md,
                                            crops_out_dir=os.path.join(out_dir, "crops"))
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
                "px_gt_30": int((d > 30).sum()),
                "px_gt_60": int((d > 60).sum()),
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
        d = cv2.absdiff(src, rep); out = d.copy(); out[~frame] = (255, 255, 255)
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

    print("--- local-crop per-CC absdiff update on aedes el-100 ---")
    print("log:")
    for k, v in log.items(): print(f"  {k}: {v}")
    print()
    print(f"residual >30 : iter0={res0['px_gt_30']:>6}  iter1={res1['px_gt_30']:>6}  delta={summary['delta_px_gt_30']:+d}")
    print(f"residual >60 : iter0={res0['px_gt_60']:>6}  iter1={res1['px_gt_60']:>6}  delta={summary['delta_px_gt_60']:+d}")
    print(f"residual >120: iter0={res0['px_gt_120']:>6}  iter1={res1['px_gt_120']:>6}  delta={summary['delta_px_gt_120']:+d}")
    print(f"mean         : iter0={res0['mean']:>6}  iter1={res1['mean']:>6}")
    print(f"crops -> {os.path.join(out_dir, 'crops')}/")


if __name__ == "__main__":
    main()
