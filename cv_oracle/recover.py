"""V5 recall recovery: merge cv_oracle detections into a forward-pass data.csv.

This is the V5 step -- the replacement for the old re-plot->compare loop. It
reads the *source image* and the forward pass's own outputs, detects what the
forward pass should also contain, and merges in whatever the forward pass
missed. cv_oracle plays the recall role; the forward pass keeps the semantics.

INTEGRITY CONSTRAINT (hard): this step is GROUND-TRUTH-FREE. It must never open a
ground_truth file. The only inputs allowed are:
  - image.png                 (the figure; a GT-free input)
  - calibration.json          (reused MLLM Phase-2 calibration)
  - chart_metadata.json       (forward-pass series legend: colors + marker/line)
  - the forward pass data.csv  (what v4 emitted)

Match tolerances are derived from the calibration's data_range (the axis span),
NOT from any ground-truth distribution, so no GT leaks in through the back door.
``assert_gt_free`` enforces the rule at runtime.
"""

from __future__ import annotations

import csv
import json
import os

import cv2

from .calibration import Calibration
from .detect import blobs as B
from .detect.curves import curve_to_rows, trace_curve
from .detect.errbars import detect_error_bars
from .reconcile import load_points, reconcile
from .run import GT_FIELDS
from .separation import color_mask


def assert_gt_free(path: str) -> str:
    """Refuse to read anything that looks like ground truth."""
    base = os.path.basename(path).lower()
    if "ground_truth" in base or "groundtruth" in base:
        raise PermissionError(f"recover.py is ground-truth-free; refusing to read {path}")
    return path


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _is_achromatic(rgb: tuple[int, int, int], tol: int = 25) -> bool:
    r, g, b = rgb
    return max(abs(r - g), abs(g - b), abs(r - b)) <= tol


def _tolerances_from_calibration(cal_json: dict) -> tuple[float, float]:
    """2% of the axis span, from data_range (GT-free)."""
    dr = cal_json.get("data_range", {})
    x_tol = 0.02 * abs(dr.get("x_max", 1) - dr.get("x_min", 0)) or 1.0
    y_tol = 0.02 * abs(dr.get("y_max", 1) - dr.get("y_min", 0)) or 1.0
    return x_tol, y_tol


def detect_for_series(img, cal, entry: dict) -> tuple[str, list[dict]]:
    """Run the appropriate detector for one legend entry. Returns (bucket, rows)."""
    series = entry.get("series_id", "?")
    color = entry.get("color")
    rgb = _hex_to_rgb(color) if color else (0, 0, 0)

    if entry.get("line_style"):
        pts = trace_curve(img, cal, rgb, color_tol=60, x_step_px=4)
        return "curves", curve_to_rows(pts, series)

    # marker / points
    box = cal.plot_frame_box
    if _is_achromatic(rgb):
        # grayscale series: achromatic band + curve-cut bridge (el-94 path)
        mask = B.crop_mask_to_box(B.achromatic_band_mask(img, 182, 200, 8), box)
        mask = B.bridge_curve_cut(mask, ksize=5)
        blobs = B.detect_blobs(mask, min_diameter=5, max_diameter=12.5, max_aspect=2.0)
    else:
        mask = B.crop_mask_to_box(color_mask(img, rgb, tol=60), box)
        blobs = B.detect_blobs(mask, min_diameter=4, max_diameter=30, max_aspect=3.0)
    return "points", B.blobs_to_rows(blobs, cal, series)


def _bucket_of(row: dict) -> str:
    lt = (row.get("layer_type", "") or "").lower()
    if "line" in lt or "spline" in lt:
        return "curves"
    if "error" in lt or "errbar" in lt:
        return "errbars"
    return "points"


def recover_chart(
    image_path: str,
    calibration_path: str,
    metadata_path: str,
    v4_data_csv: str,
    out_csv: str,
    *,
    buckets: tuple[str, ...] = ("points",),
) -> dict:
    """Merge recovered misses into v4's data.csv -> v5 data.csv. GT-free.

    ``buckets`` selects which layers to recover. Default is points-only, which is
    the high-value, low-false-positive case (undercounts and dropped marker
    layers). Curve recovery only fires for a series whose curve the forward pass
    is *missing entirely* (it never densifies an existing curve). Error-bar
    recovery only fires where the forward pass already has error bars (so the
    detector augments a real layer instead of hallucinating one on a chart that
    has none). Both guards exist because the raw detectors are FP-prone without
    ground truth.

    Returns a per-bucket count of rows added.
    """
    for p in (image_path, calibration_path, metadata_path, v4_data_csv, out_csv):
        assert_gt_free(p)

    cal_json = json.load(open(calibration_path))
    cal = Calibration.from_calibration_json(cal_json)
    meta = json.load(open(metadata_path))
    x_tol, y_tol = _tolerances_from_calibration(cal_json)
    img = cv2.imread(image_path)

    v4_rows = list(csv.DictReader(open(v4_data_csv)))
    v4_by_bucket: dict[str, list[dict]] = {"points": [], "curves": [], "errbars": []}
    for r in v4_rows:
        v4_by_bucket[_bucket_of(r)].append(r)
    v4_has_errbars = len(v4_by_bucket["errbars"]) > 0

    # cv detections per declared series, only for buckets we intend to recover.
    cv_by_bucket: dict[str, list[dict]] = {"points": [], "curves": [], "errbars": []}
    point_seeds: list[dict] = []
    for entry in meta.get("series_legend", []):
        want = "curves" if entry.get("line_style") else "points"
        if want not in buckets and not (want == "points" and "errbars" in buckets):
            continue
        try:
            bucket, rows = detect_for_series(img, cal, entry)
        except Exception:
            continue
        if bucket == "points":
            point_seeds.extend(rows)
        cv_by_bucket[bucket].extend(rows)

    if "errbars" in buckets and v4_has_errbars and point_seeds:
        try:
            cv_by_bucket["errbars"].extend(detect_error_bars(img, cal, point_seeds))
        except Exception:
            pass

    added = {"points": 0, "curves": 0, "errbars": 0}
    merged_rows = list(v4_rows)

    # POINTS: point-level reconcile, merge the misses (recovers undercounts).
    if "points" in buckets:
        added["points"] = _merge_misses(cv_by_bucket["points"], v4_by_bucket["points"], merged_rows, x_tol, y_tol)

    # CURVES: only recover a curve whose series the forward pass is MISSING
    # entirely; never densify an existing curve.
    if "curves" in buckets and cv_by_bucket["curves"] and not v4_by_bucket["curves"]:
        merged_rows.extend(cv_by_bucket["curves"])
        added["curves"] = len(cv_by_bucket["curves"])

    # ERRBARS: only where the forward pass already has error bars.
    if "errbars" in buckets and v4_has_errbars:
        added["errbars"] = _merge_misses(cv_by_bucket["errbars"], v4_by_bucket["errbars"], merged_rows, x_tol, y_tol)

    _write_rows(merged_rows, out_csv)
    return {"added": added, "v4_rows": len(v4_rows), "v5_rows": len(merged_rows)}


def _merge_misses(cv_rows: list[dict], v4_rows: list[dict], merged_out: list[dict], x_tol: float, y_tol: float) -> int:
    """Append cv rows that don't match any v4 row (within tol). Returns count added."""
    cv_pts = [{"x": float(r["x"]), "y": float(r["y"]), "_row": r} for r in cv_rows if _is_number(r.get("x")) and _is_number(r.get("y"))]
    mllm_pts = [{"x": float(r["x"]), "y": float(r["y"])} for r in v4_rows if _is_number(r.get("x")) and _is_number(r.get("y"))]
    if not cv_pts:
        return 0
    report = reconcile([{"x": p["x"], "y": p["y"]} for p in cv_pts], mllm_pts, x_tol, y_tol)
    missed_keys = {(round(m["x"], 6), round(m["y"], 6)) for m in report["cv_found_not_in_mllm"]}
    added = 0
    for p in cv_pts:
        if (round(p["x"], 6), round(p["y"], 6)) in missed_keys:
            merged_out.append(p["_row"])
            added += 1
    return added


def _is_number(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _write_rows(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=GT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in GT_FIELDS})
