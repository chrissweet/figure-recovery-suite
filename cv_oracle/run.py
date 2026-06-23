"""CLI / orchestration: image + calibration -> cv_oracle.csv detections.

Thin-slice scope: colored-scatter detection. Reads an image and the forward
pass's calibration.json, separates each series by color, detects blobs, converts
to data coordinates, and writes a ground-truth-schema CSV the existing scorer
can consume directly.
"""

from __future__ import annotations

import csv

import cv2

from .calibration import Calibration
from .detect import blobs as B
from .separation import color_mask

GT_FIELDS = ["layer_idx", "layer_type", "series", "x", "y"]


def detect_scatter(
    image_path: str,
    calibration_path: str,
    series_colors: dict[str, tuple[int, int, int]],
    *,
    color_tol: float = 60.0,
    min_diameter: float = 4.0,
    max_diameter: float = 30.0,
    max_aspect: float = 3.0,
    log_x: bool = False,
    log_y: bool = False,
) -> list[dict]:
    """Detect scatter markers for each named series -> GT-schema rows."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    cal = Calibration.from_calibration_file(calibration_path, log_x=log_x, log_y=log_y)
    box = cal.plot_frame_box
    rows: list[dict] = []
    for series, rgb in series_colors.items():
        mask = B.crop_mask_to_box(color_mask(img, rgb, tol=color_tol), box)
        blobs = B.detect_blobs(
            mask, min_diameter=min_diameter, max_diameter=max_diameter, max_aspect=max_aspect
        )
        rows.extend(B.blobs_to_rows(blobs, cal, series))
    return rows


def detect_fused_markers(
    image_path: str,
    calibration_path: str,
    series: str,
    *,
    band_lo: int = 182,
    band_hi: int = 200,
    achroma_tol: int = 8,
    close_ksize: int = 5,
    min_diameter: float = 5.0,
    max_diameter: float = 12.5,
    max_aspect: float = 2.0,
) -> list[dict]:
    """Recover gray markers that fuse with a same-region curve (el-94 case).

    Pipeline: tight achromatic core band (marker fill, not the anti-alias halo)
    -> crop to frame -> bridge the curve cut (vertical morphological close) ->
    blob detect. This lifts el-94's 27 degC squares from 9/25 to 24/25.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    cal = Calibration.from_calibration_file(calibration_path)
    mask = B.crop_mask_to_box(B.achromatic_band_mask(img, band_lo, band_hi, achroma_tol), cal.plot_frame_box)
    mask = B.bridge_curve_cut(mask, ksize=close_ksize)
    blobs = B.detect_blobs(mask, min_diameter=min_diameter, max_diameter=max_diameter, max_aspect=max_aspect)
    return B.blobs_to_rows(blobs, cal, series)


def write_rows_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=GT_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in GT_FIELDS})
