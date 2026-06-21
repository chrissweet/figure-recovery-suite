#!/usr/bin/env python3
"""Count-balancing single iteration.

For each series color, measure source pixel count vs replot pixel count
within the plot frame. When the replot has too much ink for a color, drop
existing marker claims of that color, preferring claims whose local
replot-only residual is highest. When the replot has too little ink, note
the deficit (no add this iteration — drops first).

Color detection: BGR distance for colors where nominal hex finds source
pixels; HSV-hue fallback for colors where nominal hex returns 0 (covers
the el-100 27C green case where the actual rendered green is far from
#00FF00).
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


BGR_TOL = 60
DROP_NEIGHBORHOOD = 8           # px window around a claim for "local rep-only" score
PX_PER_MARKER = 113             # approx pixels per filled circle (radius 6)
COUNT_TOLERANCE_PX = 80         # don't bother adjusting if within this


def _hex_to_bgr(hex_str):
    h = hex_str.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)],
                     dtype=np.int32)


def _hex_to_hue(hex_str):
    """Return HSV hue (0-179 OpenCV scale) of the hex color."""
    bgr = _hex_to_bgr(hex_str).astype(np.uint8).reshape(1, 1, 3)
    return int(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0, 0])


def _data_to_pixel(value, m, b, scale):
    if scale == "log10":
        if value <= 0: return None
        return (np.log10(value) - b) / m
    return (value - b) / m


def _frame_mask(shape, calibration):
    H, W = shape[:2]
    pf = calibration["plot_frame_box"]
    m = np.zeros((H, W), dtype=bool)
    m[pf["top"]:pf["bottom"], pf["left"]:pf["right"]] = True
    legend = calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    if legend:
        t, b, l, r = legend; m[int(t):int(b), int(l):int(r)] = False
    return m


def _color_mask_bgr(img, target_bgr, tol):
    d = np.linalg.norm(img.astype(np.int32) - target_bgr, axis=2)
    return d <= tol


def _color_mask_hue(img, hue_target, hue_tol=15, sat_min=40, val_max=240):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H_ch = hsv[..., 0]; S_ch = hsv[..., 1]; V_ch = hsv[..., 2]
    # Hue is circular but for greens (around 60) wrap-around is rare; use linear
    hue_ok = np.abs(H_ch.astype(np.int32) - hue_target) <= hue_tol
    return hue_ok & (S_ch >= sat_min) & (V_ch <= val_max)


def measure(img, frame, series_legend):
    """Per-series pixel count using BGR; HSV fallback when BGR returns 0."""
    out = {}
    for spec in series_legend:
        sid = spec.get("series_id"); hexc = spec.get("color", "")
        if not sid or not hexc.startswith("#"): continue
        target = _hex_to_bgr(hexc)
        bgr_mask = _color_mask_bgr(img, target, BGR_TOL) & frame
        bgr_count = int(bgr_mask.sum())
        if bgr_count >= 20:
            out[sid] = {"method": "bgr", "px": bgr_count, "mask_count": bgr_count}
        else:
            hue = _hex_to_hue(hexc)
            hsv_mask = _color_mask_hue(img, hue) & frame
            hsv_count = int(hsv_mask.sum())
            out[sid] = {"method": "hsv", "px": hsv_count,
                          "hue_target": hue, "mask_count": hsv_count}
    return out


def update_via_count_balancing(rows, src, rep, calibration, chart_metadata):
    H, W = src.shape[:2]
    frame = _frame_mask((H, W), calibration)
    series_legend = chart_metadata.get("series_legend", [])

    # Per-series counts on source and replot
    src_counts = measure(src, frame, series_legend)
    rep_counts = measure(rep, frame, series_legend)

    # Per-color "rep-only" residual mask = replot has color, source doesn't
    # (we re-use the source/replot color masks to compute this)
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    xs = x_ax.get("scale", "linear"); ys = y_ax.get("scale", "linear")

    # For each series ID that maps to a marker layer, group existing claims
    # so we can rank-and-drop per series.
    series_to_marker_claims = {}
    series_to_layer_pref = {}
    for spec in series_legend:
        sid = spec.get("series_id")
        if not sid: continue
        if spec.get("marker_shape"):
            series_to_layer_pref[sid] = "Scatter Plot"
        else:
            series_to_layer_pref[sid] = "Line Graph"

    for i, r in enumerate(rows):
        sid = r["series"]
        if r["layer_type"] not in ("Scatter Plot", "Grouped Column Chart"):
            continue
        col = _data_to_pixel(r["x"], mx, bx, xs)
        row = _data_to_pixel(r["y"], my, by, ys)
        if col is None or row is None: continue
        series_to_marker_claims.setdefault(sid, []).append(
            (i, int(col), int(row)))

    # Per-pixel rep-only mask for each series color, used to rank drops
    drop_indices = set()
    plan = {}
    for spec in series_legend:
        sid = spec.get("series_id")
        if not sid: continue
        hexc = spec.get("color", "")
        target = _hex_to_bgr(hexc)
        src_color_mask = _color_mask_bgr(src, target, BGR_TOL) & frame
        rep_color_mask = _color_mask_bgr(rep, target, BGR_TOL) & frame
        rep_only = rep_color_mask & ~src_color_mask

        src_px = src_counts.get(sid, {"px": 0})["px"]
        rep_px = rep_counts.get(sid, {"px": 0})["px"]
        excess = rep_px - src_px

        action = "none"; dropped = 0
        if excess > COUNT_TOLERANCE_PX and sid in series_to_marker_claims:
            # Rank marker claims of this series by local rep-only score,
            # drop until excess is within tolerance OR no more claims
            scored = []
            for idx, c, r_ in series_to_marker_claims[sid]:
                c0 = max(0, c - DROP_NEIGHBORHOOD); c1 = min(W, c + DROP_NEIGHBORHOOD + 1)
                r0 = max(0, r_ - DROP_NEIGHBORHOOD); r1 = min(H, r_ + DROP_NEIGHBORHOOD + 1)
                score = int(rep_only[r0:r1, c0:c1].sum())
                scored.append((score, idx))
            # Highest score = most "extra" in local neighborhood = best candidate to drop
            scored.sort(reverse=True)
            n_to_drop = min(len(scored),
                              max(1, int(round(excess / PX_PER_MARKER))))
            for score, idx in scored[:n_to_drop]:
                if score <= 0: break  # don't drop claims with no local evidence
                drop_indices.add(idx); dropped += 1
            action = f"drop_{dropped}"
        elif -excess > COUNT_TOLERANCE_PX:
            # Replot under-inks; we COULD propose adds here, but skip in this
            # iteration to keep the loop simple. Just note the deficit.
            action = "deficit_noted"

        plan[sid] = {"src_px": src_px, "rep_px": rep_px, "excess_px": excess,
                       "claims_available": len(series_to_marker_claims.get(sid, [])),
                       "action": action, "dropped": dropped,
                       "src_method": src_counts.get(sid, {}).get("method"),
                       "rep_method": rep_counts.get(sid, {}).get("method")}

    new_rows = [r for i, r in enumerate(rows) if i not in drop_indices]
    return new_rows, {"plan": plan, "claims_before": len(rows),
                         "claims_after": len(new_rows),
                         "total_dropped": len(drop_indices)}


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

    src = cv2.imread(src_path); H, W = src.shape[:2]
    image_size = {"width": W, "height": H}
    rep0 = render(image_size, cal, md, rows0)
    cv2.imwrite(os.path.join(out_dir, "iter0_replot.png"), rep0)

    rows1, info = update_via_count_balancing(rows0, src, rep0, cal, md)
    rep1 = render(image_size, cal, md, rows1)
    cv2.imwrite(os.path.join(out_dir, "iter1_replot.png"), rep1)

    with open(os.path.join(out_dir, "iter1_data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in rows1:
            w.writerow([r["layer_idx"], r["layer_type"], r["series"],
                          r["x"], r["y"]])

    # Re-measure after the update
    frame = _frame_mask((H, W), cal)
    after_counts = measure(rep1, frame, md.get("series_legend", []))

    # Update plan with post-iteration rep counts so we can see the effect
    for sid, p in info["plan"].items():
        p["rep_px_after"] = after_counts.get(sid, {}).get("px", 0)
        p["excess_after"] = p["rep_px_after"] - p["src_px"]

    # Residual (max-channel absdiff > thresholds)
    def stats(rep):
        d = cv2.absdiff(src, rep).max(axis=2)[frame]
        return {"mean": round(float(d.mean()), 3),
                "px_gt_30": int((d > 30).sum()),
                "px_gt_60": int((d > 60).sum()),
                "px_gt_120": int((d > 120).sum())}
    res0 = stats(rep0); res1 = stats(rep1)
    info["iter0_residual"] = res0; info["iter1_residual"] = res1
    info["delta_px_gt_30"]  = res1["px_gt_30"]  - res0["px_gt_30"]
    info["delta_px_gt_60"]  = res1["px_gt_60"]  - res0["px_gt_60"]
    info["delta_px_gt_120"] = res1["px_gt_120"] - res0["px_gt_120"]

    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(info, f, indent=2)

    # Before/after absdiff visual
    def render_diff(rep):
        d = cv2.absdiff(src, rep); o = d.copy(); o[~frame] = (255, 255, 255)
        return o
    d0 = render_diff(rep0); d1 = render_diff(rep1)
    h = 360
    def sc(im, ht):
        return cv2.resize(im, (int(im.shape[1] * ht / im.shape[0]), ht),
                           interpolation=cv2.INTER_AREA)
    a, b, c = sc(src, h), sc(d0, h), sc(d1, h)
    gut = np.ones((h, 15, 3), dtype=np.uint8) * 255
    cv2.imwrite(os.path.join(out_dir, "before_after_absdiff.png"),
                 np.hstack([a, gut, b, gut, c]))

    print("--- count-balancing single iteration on aedes el-100 ---\n")
    print(f"{'series':<8} {'src_px':>7} {'rep_px':>7} {'excess':>7}  {'after_px':>8} {'after_excess':>13}  action")
    for sid, p in info["plan"].items():
        print(f"{sid:<8} {p['src_px']:>7} {p['rep_px']:>7} {p['excess_px']:>+7}  "
              f"{p['rep_px_after']:>8} {p['excess_after']:>+13}  {p['action']}")
    print(f"\nclaims: {info['claims_before']} -> {info['claims_after']} ({info['total_dropped']} dropped)")
    print(f"\nresidual >30 : iter0={res0['px_gt_30']:>6}  iter1={res1['px_gt_30']:>6}  delta={info['delta_px_gt_30']:+d}")
    print(f"residual >60 : iter0={res0['px_gt_60']:>6}  iter1={res1['px_gt_60']:>6}  delta={info['delta_px_gt_60']:+d}")
    print(f"residual >120: iter0={res0['px_gt_120']:>6}  iter1={res1['px_gt_120']:>6}  delta={info['delta_px_gt_120']:+d}")
    print(f"mean         : iter0={res0['mean']:>6}  iter1={res1['mean']:>6}")


if __name__ == "__main__":
    main()
