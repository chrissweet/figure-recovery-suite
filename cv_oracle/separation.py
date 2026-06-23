"""Section 2: color separation + grid removal.

Foreground separation by color distance (WebPlotDigitizer's color-analysis
technique: Euclidean RGB distance to a target, with a tolerance ~120) and a
grid-line remover that drops rows/columns whose foreground density exceeds a
fraction of the axis span (WPD's grid-detection technique, default 10%).

These run on the source image and feed the detectors; nothing here knows about
the forward pass.
"""

from __future__ import annotations

import cv2
import numpy as np


def color_mask(img_bgr: np.ndarray, rgb: tuple[int, int, int], tol: float = 120.0) -> np.ndarray:
    """Mask of pixels within Euclidean ``tol`` of target ``rgb`` (R,G,B order)."""
    r, g, b = rgb
    target = np.array([b, g, r], dtype=np.float32)  # image is BGR
    dist = np.linalg.norm(img_bgr.astype(np.float32) - target, axis=2)
    return ((dist <= tol).astype(np.uint8)) * 255


def remove_grid(mask: np.ndarray, box: dict, frac: float = 0.10) -> np.ndarray:
    """Zero rows/cols whose in-frame foreground density exceeds ``frac`` of span.

    A gridline lights up a whole row or column; a data series does not. Returns
    a copy of ``mask`` with such lines cleared (WPD's 10% density rule).
    """
    out = mask.copy()
    t, b = int(box["top"]), int(box["bottom"])
    l, r = int(box["left"]), int(box["right"])
    sub = out[t:b, l:r] > 0
    h, w = sub.shape
    col_density = sub.sum(axis=0) / max(1, h)
    row_density = sub.sum(axis=1) / max(1, w)
    for ci, d in enumerate(col_density):
        if d > frac:
            out[t:b, l + ci] = 0
    for ri, d in enumerate(row_density):
        if d > frac:
            out[t + ri, l:r] = 0
    return out
