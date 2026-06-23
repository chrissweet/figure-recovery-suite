"""Section 3a: blob (scatter-point/marker) detection.

Connected-component labelling on a color-separated mask, filtered by blob
diameter and shape (WebPlotDigitizer's blob-detector technique: area ->
diameter = 2*sqrt(area/pi); reject out-of-range; report centroid + a scatter
of the second moment). This runs directly on the source image, blind to any
forward-pass output, so its centroid count is an independent recall signal.

The mask helpers separate foreground by color. ``achromatic_band_mask`` isolates
gray fills (e.g. the el-94 27 degC squares at RGB ~190) from black markers/curves
(~0-40) and white diamonds (~255) without needing the true legend color.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Blob:
    col: float
    row: float
    area: int
    diameter: float
    aspect: float  # bbox max(w,h)/min(w,h); ~1 for a marker, >2 for a line fragment
    second_moment: float


def achromatic_band_mask(img_bgr: np.ndarray, lo: int, hi: int, achroma_tol: int = 25) -> np.ndarray:
    """Pixels that are near-gray (R~=G~=B) with intensity in [lo, hi].

    Returns a uint8 mask (0/255). Black (<lo) and white (>hi) are excluded, as
    are saturated colors (channel spread > achroma_tol).
    """
    b, g, r = (img_bgr[:, :, i].astype(np.int16) for i in range(3))
    spread = np.maximum(np.maximum(np.abs(r - g), np.abs(g - b)), np.abs(r - b))
    intensity = img_bgr.mean(axis=2)
    mask = (spread <= achroma_tol) & (intensity >= lo) & (intensity <= hi)
    return (mask.astype(np.uint8)) * 255


def crop_mask_to_box(mask: np.ndarray, box: dict | None) -> np.ndarray:
    """Zero out everything outside a plot_frame_box (keeps in-frame pixels)."""
    if not box:
        return mask
    out = np.zeros_like(mask)
    t, b = int(box["top"]), int(box["bottom"])
    l, r = int(box["left"]), int(box["right"])
    out[t:b, l:r] = mask[t:b, l:r]
    return out


def bridge_curve_cut(mask: np.ndarray, ksize: int = 5) -> np.ndarray:
    """Bridge a thin curve cutting vertically through a marker.

    Curve-subtraction for fused markers (e.g. el-94's 27 degC gray squares sit on
    the black solid fit curve, which cuts each square into two halves so
    connected-components fragments it). A morphological close with a tall 1xksize
    kernel rejoins the halves across the ~1-2px black line without merging
    horizontally separated neighbours.

    Empirically this beat tracer-targeted bridging on el-94 (24/25 vs 23/25, and
    higher precision): a blind vertical close cannot connect markers that are
    only separated horizontally, whereas painting along a traced curve does.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, ksize))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def detect_blobs(
    mask: np.ndarray,
    *,
    min_diameter: float = 3.0,
    max_diameter: float = 40.0,
    max_aspect: float = 4.0,
    connectivity: int = 8,
) -> list[Blob]:
    """Connected components on ``mask`` -> filtered list of :class:`Blob`.

    Filters: blob diameter in [min_diameter, max_diameter] and bbox aspect ratio
    <= max_aspect (rejects long thin strokes that are line fragments, not
    markers).
    """
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=connectivity)
    blobs: list[Blob] = []
    for i in range(1, n):  # 0 is background
        area = int(stats[i, cv2.CC_STAT_AREA])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        dia = 2.0 * np.sqrt(area / np.pi)
        if dia < min_diameter or dia > max_diameter:
            continue
        aspect = max(w, h) / max(1, min(w, h))
        if aspect > max_aspect:
            continue
        cx, cy = centroids[i]
        ys, xs = np.where(labels == i)
        second_moment = float(np.mean((xs - cx) ** 2 + (ys - cy) ** 2)) if len(xs) else 0.0
        blobs.append(
            Blob(
                col=float(cx),
                row=float(cy),
                area=area,
                diameter=float(dia),
                aspect=float(aspect),
                second_moment=second_moment,
            )
        )
    return blobs


def blobs_to_rows(blobs: list[Blob], calibration, series: str, layer_type: str = "Scatter Plot", layer_idx: int = 0) -> list[dict]:
    """Convert blob pixel centroids to ground-truth-schema data rows."""
    rows = []
    for blob in blobs:
        x, y = calibration.pixel_to_data(blob.col, blob.row)
        rows.append(
            {
                "layer_idx": layer_idx,
                "layer_type": layer_type,
                "series": series,
                "x": round(x, 6),
                "y": round(y, 6),
            }
        )
    return rows
