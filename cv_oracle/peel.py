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
from .prepare_canvas import prepare_canvas
from .recover import _is_number, detect_for_series

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
