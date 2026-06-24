"""Peel-and-recheck recovery (the subtractive close-the-loop).

Instead of rendering the extraction and diffing (re-plot -> compare, which needs
a pixel-faithful render matplotlib cannot give), this ERASES what the forward
pass extracted from the canvas and detects what is LEFT. Residual ink of a
series' colour is, by construction, what the forward pass MISSED.

    source - extraction  ~=  empty   <=>   no misses   (GT-free recall signal)

It is self-limiting: if the forward pass got everything, the residual is empty
and nothing is added. Unlike the reconcile-merge (recover.py), correctly
extracted markers are physically removed, so the residual detector cannot
re-emit them as false positives, and small localisation mismatches are absorbed
by the erase patch rather than producing phantom "misses".
"""

from __future__ import annotations

import csv
import json

import cv2
import numpy as np

from .calibration import Calibration
from .detect.curves import curve_to_rows, trace_curve
from .prepare_canvas import prepare_canvas
from .recover import _hex_to_rgb, _is_number, detect_for_series

WHITE = 255


def subtract_points(canvas: np.ndarray, pixel_points: list[tuple[float, float]], radius: int = 7) -> np.ndarray:
    """Paint a white disk over each (col,row) -> erase extracted markers."""
    out = canvas.copy()
    for col, row in pixel_points:
        cv2.circle(out, (int(round(col)), int(round(row))), radius, (WHITE, WHITE, WHITE), -1)
    return out


def _point_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        lt = (r.get("layer_type", "") or "").lower()
        if "line" in lt or "spline" in lt or "error" in lt or "errbar" in lt:
            continue
        if _is_number(r.get("x")) and _is_number(r.get("y")):
            out.append(r)
    return out


def peel_recover_points(
    image_path: str,
    calibration_path: str,
    metadata_path: str,
    v4_data_csv: str,
    *,
    erase_radius: int = 7,
    pad: int = 2,
) -> list[dict]:
    """Return the point rows the forward pass missed, found by peeling.

    Erases every forward-pass marker from a normalized canvas, then runs the
    per-series detector on the residual. Whatever it finds is a miss.
    """
    cal = Calibration.from_calibration_file(calibration_path)
    meta = json.load(open(metadata_path))
    canvas = prepare_canvas(image_path, calibration_path, pad=pad)

    v4_rows = list(csv.DictReader(open(v4_data_csv)))
    v4_pts = _point_rows(v4_rows)
    pix = [cal.data_to_pixel(float(r["x"]), float(r["y"])) for r in v4_pts]
    residual = subtract_points(canvas, pix, radius=erase_radius)

    # Detect each declared marker series on the residual; whatever survives the
    # subtraction is a miss.
    misses: list[dict] = []
    for entry in meta.get("series_legend", []):
        if not entry.get("marker_shape"):
            continue
        try:
            bucket, rows = detect_for_series(residual, cal, entry)
        except Exception:
            continue
        if bucket == "points":
            misses.extend(rows)
    return misses


def subtract_curves(canvas: np.ndarray, polylines_px: list[list[tuple[float, float]]], thickness: int = 5) -> np.ndarray:
    """Paint white along each forward-pass curve polyline -> erase it."""
    out = canvas.copy()
    for poly in polylines_px:
        if len(poly) < 2:
            continue
        pts = np.array([[int(round(c)), int(round(r))] for c, r in poly], dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [pts], isClosed=False, color=(WHITE, WHITE, WHITE), thickness=thickness)
    return out


def peel_recover_curves(
    image_path: str,
    calibration_path: str,
    metadata_path: str,
    v4_data_csv: str,
    *,
    erase_thickness: int = 6,
    pad: int = 2,
) -> list[dict]:
    """Return curve points the forward pass missed, found by peeling.

    Erases the forward pass's traced curves from the canvas, then re-traces each
    declared line series on the residual -- recovering truncated tails and
    mis-located stretches the forward pass did not cover. Curve FP is 0 in the
    scorer, so the only effect is added coverage. Recovered rows carry the
    chart_metadata series id (the same id the v4 agent was given).
    """
    cal = Calibration.from_calibration_file(calibration_path)
    meta = json.load(open(metadata_path))
    canvas = prepare_canvas(image_path, calibration_path, pad=pad)

    # Erase the forward pass's curve polylines (grouped by series).
    v4_rows = list(csv.DictReader(open(v4_data_csv)))
    by_series: dict[str, list[tuple[float, float]]] = {}
    for r in v4_rows:
        lt = (r.get("layer_type", "") or "").lower()
        if ("line" in lt or "spline" in lt) and _is_number(r.get("x")) and _is_number(r.get("y")):
            by_series.setdefault(r.get("series", ""), []).append((float(r["x"]), float(r["y"])))
    polylines = []
    for pts in by_series.values():
        pts.sort()
        polylines.append([cal.data_to_pixel(x, y) for x, y in pts])
    residual = subtract_curves(canvas, polylines, thickness=erase_thickness)

    # Per-series x-coverage of the forward pass, so we only EXTEND (never
    # interleave): merging cv points inside v4's covered range corrupts the
    # scorer's per-series interpolation and destroys true positives. Outside it,
    # added coverage can only recover truncated tails.
    v4_xrange = {s: (min(x for x, _ in pts), max(x for x, _ in pts)) for s, pts in by_series.items()}

    recovered: list[dict] = []
    for entry in meta.get("series_legend", []):
        if not entry.get("line_style") or not entry.get("color"):
            continue
        sid = entry.get("series_id", "?")
        try:
            pts = trace_curve(residual, cal, _hex_to_rgb(entry["color"]), color_tol=60, x_step_px=4)
        except Exception:
            continue
        if len(pts) < 4:
            continue
        rng = v4_xrange.get(sid)
        if rng is None:
            keep = pts  # forward pass has no curve for this series -> add all
        else:
            lo, hi = rng
            keep = [(x, y) for x, y in pts if x < lo or x > hi]  # tails only
        if keep:
            recovered.extend(curve_to_rows(keep, sid))
    return recovered
