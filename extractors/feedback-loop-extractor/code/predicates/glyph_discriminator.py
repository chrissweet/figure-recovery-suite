#!/usr/bin/env python3
"""Predicate B — Glyph-vs-line discriminator.

For each marker_centroid claim in data.csv, take a small crop around the
claimed pixel and score whether the local region is a real marker (isolated
blob, aspect ratio ~1, surrounded by background) or a fragment of a
continuous stroke (extends along an axis past the crop boundary).

Closes the over-counting gap that scoring/verify_artifacts.py
check_marker_centroid cannot detect: the existing predicate accepts any
dark pixel at the claimed position, so dashed-fit-line fragments and
legend swatches pass as if they were real markers.

Usage:
    from glyph_discriminator import score
    report = score(image_path, calibration, chart_metadata, data_rows)

Returns a dict {
    "per_claim": [
        {
            "series": str,
            "x": float, "y": float,
            "col": int, "row": int,
            "blob_area": int,
            "aspect": float,
            "fill_density": float,
            "extends_horizontally": bool,
            "extends_vertically": bool,
            "verdict": "marker" | "line-fragment" | "legend-swatch" | "uncertain",
            "drop": bool,
        }, ...
    ],
    "summary": {
        "n_claims": int, "n_dropped": int,
        "by_verdict": {verdict: count, ...},
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


def _data_to_pixel(value, m, b, scale):
    if scale == "log10":
        if value <= 0: return None
        return (np.log10(value) - b) / m
    return (value - b) / m


def _score_one(img_bgr, col, row, target_bgr, color_tolerance,
                crop_half=8, extension_check_half=20):
    """Score one marker claim. Returns dict with shape stats + verdict."""
    H, W = img_bgr.shape[:2]
    c, r = int(col), int(row)
    c0 = max(0, c - crop_half); c1 = min(W, c + crop_half + 1)
    r0 = max(0, r - crop_half); r1 = min(H, r + crop_half + 1)
    if c0 >= c1 or r0 >= r1:
        return {"blob_area": 0, "aspect": 0.0, "fill_density": 0.0,
                "extends_horizontally": False, "extends_vertically": False,
                "verdict": "uncertain", "reason": "out-of-image"}

    crop = img_bgr[r0:r1, c0:c1]
    crop_diff = crop.astype(np.int32) - target_bgr
    crop_dist = np.sqrt((crop_diff * crop_diff).sum(axis=2))
    crop_mask = (crop_dist <= color_tolerance).astype(np.uint8) * 255

    # Find the blob containing or nearest to the centre
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(crop_mask,
                                                                 connectivity=8)
    if n_lbl <= 1:
        return {"blob_area": 0, "aspect": 0.0, "fill_density": 0.0,
                "extends_horizontally": False, "extends_vertically": False,
                "verdict": "uncertain", "reason": "no-blob"}
    center_lbl = labels[c - c0 if 0 <= c - c0 < labels.shape[1]
                         else labels.shape[1] // 2,
                         # actually: row,col indexing
                         ] if False else None
    cy_local = min(max(r - r0, 0), labels.shape[0] - 1)
    cx_local = min(max(c - c0, 0), labels.shape[1] - 1)
    center_lbl = labels[cy_local, cx_local]
    if center_lbl == 0:
        # Pick the largest blob in the crop (fallback)
        areas = stats[1:, 4]
        if len(areas) == 0:
            return {"blob_area": 0, "aspect": 0.0, "fill_density": 0.0,
                    "extends_horizontally": False, "extends_vertically": False,
                    "verdict": "uncertain", "reason": "centre-not-on-blob"}
        center_lbl = 1 + int(np.argmax(areas))
    x_l, y_l, w_l, h_l, area = stats[center_lbl]
    aspect = max(w_l, h_l) / max(1, min(w_l, h_l))
    fill_density = area / max(1, w_l * h_l)

    # Extension check: does the same-color mask extend significantly past
    # the crop boundary along the horizontal or vertical axis?
    rc0 = max(0, c - extension_check_half); rc1 = min(W, c + extension_check_half + 1)
    rr0 = max(0, r - extension_check_half); rr1 = min(H, r + extension_check_half + 1)
    big = img_bgr[rr0:rr1, rc0:rc1]
    big_diff = big.astype(np.int32) - target_bgr
    big_dist = np.sqrt((big_diff * big_diff).sum(axis=2))
    big_mask = (big_dist <= color_tolerance).astype(np.uint8)
    H_big, W_big = big_mask.shape
    cy_big = r - rr0; cx_big = c - rc0
    # Horizontal extension: fraction of the row band (cy_big +/- 2) that's set
    row_band = big_mask[max(0, cy_big - 2):min(H_big, cy_big + 3), :]
    h_frac = row_band.sum() / max(1, row_band.size)
    col_band = big_mask[:, max(0, cx_big - 2):min(W_big, cx_big + 3)]
    v_frac = col_band.sum() / max(1, col_band.size)
    extends_horizontally = h_frac >= 0.35
    extends_vertically   = v_frac >= 0.35

    # Verdict
    if extends_horizontally and not extends_vertically:
        verdict = "line-fragment"  # horizontal stroke (a dashed/solid line)
    elif extends_vertically and not extends_horizontally:
        verdict = "line-fragment"  # vertical stroke (e.g. error-bar arm)
    elif aspect > 2.5:
        verdict = "line-fragment"  # elongated blob along one axis
    elif area < 6:
        verdict = "uncertain"
    else:
        verdict = "marker"

    return {"blob_area": int(area), "aspect": round(float(aspect), 2),
            "fill_density": round(float(fill_density), 2),
            "extends_horizontally": bool(extends_horizontally),
            "extends_vertically": bool(extends_vertically),
            "h_frac": round(float(h_frac), 3),
            "v_frac": round(float(v_frac), 3),
            "verdict": verdict}


def score(image_path, calibration, chart_metadata, data_rows,
           color_tolerance=25, legend_box=None):
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise FileNotFoundError(image_path)
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax.get("m"), x_ax.get("b")
    my, by = y_ax.get("m"), y_ax.get("b")
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")

    legend = legend_box or calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    legend_box_box = None
    if legend:
        if isinstance(legend, dict):
            t = legend.get("top", legend.get("row0"))
            b = legend.get("bottom", legend.get("row1"))
            l = legend.get("left", legend.get("col0"))
            r = legend.get("right", legend.get("col1"))
        else:
            t, b, l, r = legend[0], legend[1], legend[2], legend[3]
        if all(v is not None for v in (t, b, l, r)):
            legend_box_box = (int(t), int(b), int(l), int(r))

    series_color = {}
    for spec in chart_metadata.get("series_legend", []):
        sid = spec.get("series_id")
        color = spec.get("color", "")
        if sid and color.startswith("#"):
            series_color[sid] = _hex_to_bgr(color)

    per_claim = []
    by_verdict = {}
    n_drop = 0
    for r in data_rows:
        if r["layer_type"] not in ("Scatter Plot", "Grouped Column Chart"):
            continue
        sid = r["series"]
        target = series_color.get(sid)
        if target is None:
            continue
        col = _data_to_pixel(r["x"], mx, bx, x_scale)
        row = _data_to_pixel(r["y"], my, by, y_scale)
        if col is None or row is None:
            continue
        s = _score_one(img_bgr, col, row, target, color_tolerance)
        # Legend-swatch verdict overrides: if the claim lands inside the
        # legend box, mark it as such regardless of shape.
        if legend_box_box:
            t, b, l, r_ = legend_box_box
            if t <= row <= b and l <= col <= r_:
                s["verdict"] = "legend-swatch"
        verdict = s["verdict"]
        s["series"] = sid; s["x"] = r["x"]; s["y"] = r["y"]
        s["col"] = int(col); s["row"] = int(row)
        s["drop"] = verdict in ("line-fragment", "legend-swatch")
        if s["drop"]:
            n_drop += 1
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        per_claim.append(s)

    return {"per_claim": per_claim,
            "summary": {"n_claims": len(per_claim), "n_dropped": n_drop,
                         "by_verdict": by_verdict}}


if __name__ == "__main__":
    import csv
    chart_dir = sys.argv[1]
    img_path = sys.argv[2] if len(sys.argv) > 2 else None
    if img_path is None:
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
    rep = score(img_path, cal, md, rows)
    print(json.dumps(rep["summary"], indent=2))
    print(f"({len(rep['per_claim'])} per-claim records suppressed for brevity)")
