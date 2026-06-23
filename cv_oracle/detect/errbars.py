"""Section 3c: error-bar cap/whisker detection.

Error bars are whiskers (a thin stem) ending in short perpendicular caps. Given a
data point, the cap positions are the extent of the whisker color along the
point's column (y-error: upper/lower caps) and row (x-error: left/right caps).
We read those extents from a near-black mask in a small window around each
marker, so the caps come straight off the source pixels.

Output follows the ErrorBarLayer schema (one row per cap endpoint, in data
coordinates), which scoring/score_data.py pools and pair-matches as points.
"""

from __future__ import annotations

import numpy as np

from ..separation import color_mask


def _extent(mask_line: np.ndarray, center: int, min_reach: int) -> tuple[int, int] | None:
    """Indices of the foreground extent on a 1-D slice, or None if it does not
    reach ``min_reach`` pixels beyond ``center`` on at least one side."""
    idx = np.where(mask_line > 0)[0]
    if idx.size == 0:
        return None
    lo, hi = int(idx.min()), int(idx.max())
    if (center - lo) < min_reach and (hi - center) < min_reach:
        return None  # too short to be a whisker (probably just the marker)
    return lo, hi


def detect_error_bars(
    img_bgr: np.ndarray,
    calibration,
    markers: list[dict],
    *,
    whisker_rgb: tuple[int, int, int] = (0, 0, 0),
    color_tol: float = 90.0,
    search_px: int = 30,
    min_reach: int = 4,
    detect_x: bool = True,
    detect_y: bool = True,
) -> list[dict]:
    """For each marker, read its error-bar caps -> ErrorBarLayer rows.

    ``markers`` are GT-schema rows (x, y in data coords). Emits up to four caps
    per marker: y_err_upper / y_err_lower (vertical whisker) and
    x_err_left / x_err_right (horizontal whisker).
    """
    mask = color_mask(img_bgr, whisker_rgb, tol=color_tol)
    h, w = mask.shape
    rows: list[dict] = []
    for m in markers:
        mc, mr = calibration.data_to_pixel(m["x"], m["y"])
        mc, mr = int(round(mc)), int(round(mr))
        if not (0 <= mc < w and 0 <= mr < h):
            continue

        if detect_y:
            top = max(0, mr - search_px)
            col_slice = mask[top : min(h, mr + search_px), mc]
            ext = _extent(col_slice, mr - top, min_reach)
            if ext:
                y_up = calibration.pixel_to_data(mc, top + ext[0])[1]
                y_lo = calibration.pixel_to_data(mc, top + ext[1])[1]
                rows.append(_cap("y_err_upper", m["x"], y_up))
                rows.append(_cap("y_err_lower", m["x"], y_lo))

        if detect_x:
            left = max(0, mc - search_px)
            row_slice = mask[mr, left : min(w, mc + search_px)]
            ext = _extent(row_slice, mc - left, min_reach)
            if ext:
                x_left = calibration.pixel_to_data(left + ext[0], mr)[0]
                x_right = calibration.pixel_to_data(left + ext[1], mr)[0]
                rows.append(_cap("x_err_left", x_left, m["y"]))
                rows.append(_cap("x_err_right", x_right, m["y"]))
    return rows


def _cap(series: str, x: float, y: float) -> dict:
    return {"layer_idx": 1, "layer_type": "ErrorBarLayer", "series": series, "x": round(x, 6), "y": round(y, 6)}
