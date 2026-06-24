"""Deterministic plot-area normalization (calibrate-first STEP 2).

Given an image and its calibration, produce a "canvas": the same image with
everything that is NOT data whited out -- outside the plot frame, and the legend
box. This removes, before any extraction or detection runs, the two structural
false-positive sources we measured (legend swatches detected as points, axis
spines detected as error-bar caps).

Coordinates are preserved (the image is masked, not cropped), so the existing
calibration m/b still maps pixels<->data directly. The legend box is read from
calibration.json's detection_internals when present.
"""

from __future__ import annotations

import json

import cv2
import numpy as np

WHITE = 255


def _legend_box(cal: dict) -> dict | None:
    di = cal.get("detection_internals", {}) or {}
    lb = di.get("legend_exclusion_used_for_frame")
    if isinstance(lb, dict) and all(k in lb for k in ("left", "top", "right", "bottom")):
        return lb
    return None


def prepare_canvas(image_path: str, calibration_path: str, *, pad: int = 0) -> np.ndarray:
    """Return a BGR canvas: data region kept, everything else set to white.

    ``pad`` shrinks the kept frame inward by ``pad`` px on each side (handy to
    drop the axis spine pixels themselves).
    """
    img = cv2.imread(image_path)
    cal = json.load(open(calibration_path))
    h, w = img.shape[:2]
    fb = cal["plot_frame_box"]
    t, b = int(round(fb["top"])) + pad, int(round(fb["bottom"])) - pad
    l, r = int(round(fb["left"])) + pad, int(round(fb["right"])) - pad

    canvas = np.full_like(img, WHITE)
    t, b = max(0, t), min(h, b)
    l, r = max(0, l), min(w, r)
    canvas[t:b, l:r] = img[t:b, l:r]

    lb = _legend_box(cal)
    if lb:
        lt, lbm = int(round(lb["top"])), int(round(lb["bottom"]))
        ll, lr = int(round(lb["left"])), int(round(lb["right"]))
        canvas[max(0, lt):min(h, lbm), max(0, ll):min(w, lr)] = WHITE
    return canvas
