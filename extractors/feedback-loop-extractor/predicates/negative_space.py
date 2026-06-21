#!/usr/bin/env python3
"""Predicate A — Negative-space coverage check.

For each series in chart_metadata.json, build a color mask over the source
image using the legend swatch RGB, subtract the regions explained by current
claims in data.csv, and run connected-component detection over what is left.
Each residual component is a candidate the current extraction MISSED.

The point of this predicate is closing the "things we missed" gap that the
existing scoring/verify_artifacts.py predicates cannot detect — they iterate
extractor claims, never source-image positions that lack a claim.

Usage:
    from negative_space import scan
    report = scan(image_path, calibration, chart_metadata, data_rows)

Returns a dict {
    "per_series": {
        series_id: {
            "claims": int,                  # how many extractor claims this series has
            "source_components": int,       # how many CCs in the source for this color
            "unclaimed": [
                {"col": int, "row": int, "area": int, "aspect": float, "triage": str}, ...
            ],
        }, ...
    },
    "summary": {
        "total_unclaimed_likely_marker": int,
        "total_unclaimed_likely_other":  int,
    }
}
"""
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
    """Boolean mask of pixels within `tolerance` BGR distance of target."""
    diff = img_bgr.astype(np.int32) - target_bgr
    dist = np.sqrt((diff * diff).sum(axis=2))
    return dist <= tolerance


def _claimed_mask(shape, claims_for_series_by_layer, mx, bx, my, by,
                   x_scale, y_scale, marker_radius_px, line_thickness_px):
    """Build a boolean mask of pixels claimed by the extractor for this
    series. Per-layer-type claim model:

    - Scatter Plot / Grouped Column Chart: disk of marker_radius_px around
      each (col, row).
    - Line Graph / Spline Chart: a thick POLYLINE of line_thickness_px
      between the sorted (col, row) samples. (Earlier bug: line samples
      were treated as marker disks, leaving 99 % of the line trace
      "unclaimed" — every line pixel showed up as a missed marker.)

    `claims_for_series_by_layer` is a dict {layer_type: [(x, y), ...]}.
    """
    H, W = shape[:2]
    mask = np.zeros((H, W), dtype=np.uint8)

    def to_px(x, y):
        if x_scale == "log10":
            if x <= 0: return None
            col = (np.log10(x) - bx) / mx
        else:
            col = (x - bx) / mx
        if y_scale == "log10":
            if y <= 0: return None
            row = (np.log10(y) - by) / my
        else:
            row = (y - by) / my
        if not (0 <= col < W and 0 <= row < H):
            return None
        return int(col), int(row)

    for layer, pts in claims_for_series_by_layer.items():
        if "Line" in layer or "Spline" in layer:
            # Sort by x, build polyline, draw thick stroke
            sorted_pts = sorted(pts, key=lambda p: p[0])
            pix = []
            for x, y in sorted_pts:
                p = to_px(x, y)
                if p is not None: pix.append(p)
            if len(pix) >= 2:
                np_pts = np.array([pix], dtype=np.int32)
                cv2.polylines(mask, np_pts, isClosed=False, color=1,
                               thickness=line_thickness_px)
        else:
            for x, y in pts:
                p = to_px(x, y)
                if p is None: continue
                cv2.circle(mask, p, marker_radius_px, 1, -1)
    return mask.astype(bool)


def _triage(area, aspect, marker_area_range=(8, 200), aspect_max_marker=2.0):
    """Classify a residual CC into likely-marker / likely-line-fragment /
    likely-noise based on area and aspect ratio."""
    if area < marker_area_range[0]:
        return "likely-noise"
    if area > marker_area_range[1]:
        return "likely-other"  # large blob; might be a swatch / text
    if aspect > aspect_max_marker:
        return "likely-line-fragment"
    return "likely-marker"


def scan(image_path, calibration, chart_metadata, data_rows,
          color_tolerance=25, claim_radius_px=6, line_thickness_px=4,
          marker_area_range=(8, 200), aspect_max_marker=2.0):
    """Run the negative-space check. See module docstring for shape of return."""
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise FileNotFoundError(image_path)
    H, W = img_bgr.shape[:2]

    pf = calibration["plot_frame_box"]
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax.get("m"), x_ax.get("b")
    my, by = y_ax.get("m"), y_ax.get("b")
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")

    # Restrict everything to the plot frame so axis labels / titles can't be
    # mistaken for missing markers.
    frame_mask = np.zeros((H, W), dtype=bool)
    frame_mask[pf["top"]:pf["bottom"], pf["left"]:pf["right"]] = True

    # Mask out the legend exclusion box, if any — swatches there look like
    # markers but are not data.
    legend = calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    if legend:
        if isinstance(legend, dict):
            t = legend.get("top", legend.get("row0"))
            b = legend.get("bottom", legend.get("row1"))
            l = legend.get("left", legend.get("col0"))
            r = legend.get("right", legend.get("col1"))
        else:
            t, b, l, r = legend[0], legend[1], legend[2], legend[3]
        if all(v is not None for v in (t, b, l, r)):
            frame_mask[int(t):int(b), int(l):int(r)] = False

    per_series = {}
    summary_marker = 0
    summary_other = 0

    for spec in chart_metadata.get("series_legend", []):
        sid = spec.get("series_id")
        color = spec.get("color", "")
        if not sid or not color.startswith("#"):
            continue
        target = _hex_to_bgr(color)

        # Source pixels that look like this series' color
        color_mask = _color_mask(img_bgr, target, color_tolerance) & frame_mask

        # Pixels claimed by the extractor for this series, by layer type
        claims_by_layer = {}
        n_claims_total = 0
        for r in data_rows:
            if r["series"] != sid: continue
            claims_by_layer.setdefault(r["layer_type"], []).append(
                (r["x"], r["y"]))
            n_claims_total += 1
        claimed = _claimed_mask(img_bgr.shape, claims_by_layer,
                                  mx, bx, my, by, x_scale, y_scale,
                                  claim_radius_px, line_thickness_px)

        # What remains is unclaimed source-image content of this color
        residual = (color_mask & ~claimed).astype(np.uint8) * 255

        # Connected components on the residual
        n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(residual,
                                                                     connectivity=8)
        unclaimed = []
        for lbl in range(1, n_lbl):
            x_l, y_l, w_l, h_l, area_l = stats[lbl]
            if area_l < 3:  # discard sub-pixel noise
                continue
            aspect = max(w_l, h_l) / max(1, min(w_l, h_l))
            cx = int(x_l + w_l / 2); cy = int(y_l + h_l / 2)
            triage = _triage(int(area_l), float(aspect),
                              marker_area_range, aspect_max_marker)
            unclaimed.append({"col": cx, "row": cy,
                               "area": int(area_l), "aspect": round(aspect, 2),
                               "triage": triage})

        # Source CC total for this color (within frame, before subtraction)
        full_mask = (color_mask).astype(np.uint8) * 255
        n_lbl_full, _, _, _ = cv2.connectedComponentsWithStats(full_mask,
                                                                 connectivity=8)
        per_series[sid] = {
            "claims": n_claims_total,
            "source_components": int(n_lbl_full - 1),  # minus background
            "unclaimed": unclaimed,
        }
        summary_marker += sum(1 for u in unclaimed if u["triage"] == "likely-marker")
        summary_other  += sum(1 for u in unclaimed if u["triage"] != "likely-marker")

    return {"per_series": per_series,
            "summary": {"total_unclaimed_likely_marker": summary_marker,
                         "total_unclaimed_likely_other":  summary_other}}


if __name__ == "__main__":
    import csv
    if len(sys.argv) < 2:
        print("usage: negative_space.py <chart_dir>")
        sys.exit(1)
    chart_dir = sys.argv[1]
    # chart_dir holds calibration.json, chart_metadata.json, data.csv;
    # image.png is at corpora/.../charts/<chart>/image.png — derive from
    # chart_dir if the user passes the extractor's results dir directly.
    img_path = sys.argv[2] if len(sys.argv) > 2 else None
    if img_path is None:
        # Heuristic: chart_dir like extractors/.../results-v3/<corpus>/<chart>/
        parts = os.path.normpath(chart_dir).split(os.sep)
        if "results-v3" in parts:
            i = parts.index("results-v3")
            corpus = parts[i + 1]; chart = parts[i + 2]
            img_path = os.path.join(
                "corpora", corpus, "charts", chart, "image.png")
    cal = json.load(open(os.path.join(chart_dir, "calibration.json")))
    md = json.load(open(os.path.join(chart_dir, "chart_metadata.json")))
    rows = []
    with open(os.path.join(chart_dir, "data.csv")) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"layer_idx": r.get("layer_idx", "0"),
                              "layer_type": r.get("layer_type", "Scatter Plot"),
                              "series": r.get("series", "default"),
                              "x": float(r["x"]), "y": float(r["y"])})
            except (KeyError, ValueError):
                continue
    rep = scan(img_path, cal, md, rows)
    print(json.dumps(rep, indent=2))
