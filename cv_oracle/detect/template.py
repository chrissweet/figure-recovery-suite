"""Template-matching marker detection (WebPlotDigitizer's primary tool).

WPD finds markers from ONE human-clicked exemplar: extract its glyph as a binary
template, slide it over the image, score each location by overlap, keep the peaks.
This is the same idea with the seed taken automatically -- the most isolated,
median-sized blob of a series colour becomes the template -- so it is a single-
pass marker FINDER, not a recovery gate.

Why it beats blob/CC detection on our hard charts: the match score is a shape
discriminator. A solid dark region or a half-erased ring scores low; a glyph the
right shape and size scores high. So it separates same-colour-different-shape
series (square vs diamond), survives a curve cutting through a marker (partial
overlap still peaks), and gives every detection a confidence for thresholding.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..separation import color_mask
from .blobs import achromatic_band_mask, crop_mask_to_box


def series_mask(img_bgr, rgb, box, *, achromatic: bool, color_tol: float = 60.0) -> np.ndarray:
    if achromatic:
        # grayscale series are separated by INTENSITY, not hue: pick a band
        # around the series' brightness (dark disks / mid-gray squares).
        inten = sum(rgb) / 3.0
        if inten < 100:
            lo, hi = 0, 95
        elif inten > 215:
            lo, hi = 150, 215  # near-white fill; weak (overlaps background)
        else:
            lo, hi = int(inten) - 28, int(inten) + 28
        m = achromatic_band_mask(img_bgr, max(0, lo), min(255, hi), 18)
    else:
        m = color_mask(img_bgr, rgb, tol=color_tol)
    return crop_mask_to_box(m, box)


def auto_seed(mask: np.ndarray, *, min_d: float = 4.0, max_d: float = 18.0, max_aspect: float = 1.5):
    """Pick a clean, median-sized blob and return its binary glyph as a template."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cands = []
    for i in range(1, n):
        a = int(stats[i, cv2.CC_STAT_AREA])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        dia = 2.0 * np.sqrt(a / np.pi)
        if dia < min_d or dia > max_d:
            continue
        if max(w, h) / max(1, min(w, h)) > max_aspect:
            continue
        l, t = int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP])
        cands.append((a, i, l, t, w, h))
    if not cands:
        return None
    cands.sort()  # by area; take the median (representative, not a noise speck or merge)
    a, i, l, t, w, h = cands[len(cands) // 2]
    return (labels[t:t + h, l:l + w] == i).astype(np.uint8)


def match(mask: np.ndarray, template: np.ndarray, *, score_thresh: float = 0.6, max_excess: float = 1.6):
    """Overlap template match + non-max suppression.

    Score = |template ∩ window| / |template| (WPD's measure). A location is kept
    when the overlap clears ``score_thresh`` AND the window is not far denser than
    the template (``max_excess``), which rejects solid blobs / dense crossings.
    """
    th, tw = template.shape
    if th < 2 or tw < 2:
        return []
    m = (mask > 0).astype(np.float32)
    area = float(template.sum())
    if area < 2:
        return []
    overlap = cv2.matchTemplate(m, template.astype(np.float32), cv2.TM_CCORR)  # |∩|
    window_fg = cv2.matchTemplate(m, np.ones_like(template, np.float32), cv2.TM_CCORR)  # |sample|
    score = overlap / area
    ok = (score >= score_thresh) & (window_fg <= max_excess * area)
    ys, xs = np.where(ok)
    cands = sorted(((float(score[y, x]), x + tw / 2.0, y + th / 2.0) for y, x in zip(ys, xs)), reverse=True)
    # NMS: drop any peak within ~70% of the template size of a stronger peak.
    rx, ry = 0.7 * tw, 0.7 * th
    keep = []
    for s, cx, cy in cands:
        if all(abs(cx - kx) > rx or abs(cy - ky) > ry for kx, ky in keep):
            keep.append((cx, cy))
    return keep


def detect_markers_template(img_bgr, calibration, rgb, *, achromatic: bool, score_thresh: float = 0.6, color_tol: float = 60.0):
    """All markers of a series, found by seeded template match. Returns data coords."""
    mask = series_mask(img_bgr, rgb, calibration.plot_frame_box, achromatic=achromatic, color_tol=color_tol)
    template = auto_seed(mask)
    if template is None:
        return []
    return [calibration.pixel_to_data(cx, cy) for cx, cy in match(mask, template, score_thresh=score_thresh)]
