"""Section 3b: x-step + spline curve tracing.

WebPlotDigitizer's xStepWithInterpolation technique: scan the curve column by
column, take the (intensity-weighted) mean foreground row per column, then fit a
cubic spline and resample. The spline both smooths per-column noise and bridges
gaps in dashed / dotted curves, which is exactly what the el-94 / el-100 fit
curves need (they are dashed/solid/dotted same-color lines the forward pass
dropped entirely).

Tracing happens in pixel space; conversion to data coordinates (including a
log-y axis) is deferred to the calibration so the spline sees a smooth function.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline

from ..separation import color_mask, remove_grid


def _column_means(mask: np.ndarray, box: dict) -> tuple[np.ndarray, np.ndarray]:
    """Mean foreground row per column inside the frame.

    Returns (cols, rows) for columns that contain any foreground pixel.
    """
    t, b = int(box["top"]), int(box["bottom"])
    l, r = int(box["left"]), int(box["right"])
    cols, rows = [], []
    for col in range(l, r):
        ys = np.where(mask[t:b, col] > 0)[0]
        if ys.size:
            cols.append(col)
            rows.append(t + float(ys.mean()))
    return np.array(cols, dtype=float), np.array(rows, dtype=float)


def trace_curve(
    img_bgr: np.ndarray,
    calibration,
    rgb: tuple[int, int, int],
    *,
    color_tol: float = 60.0,
    x_step_px: int = 4,
    drop_grid: bool = True,
    log_x: bool = False,
    log_y: bool = False,
) -> list[tuple[float, float]]:
    """Trace one color-isolated curve into (x, y) data points.

    The returned points are resampled at ``x_step_px`` pixel spacing across the
    curve's pixel coverage via a cubic spline (so dashed gaps are bridged).
    """
    box = calibration.plot_frame_box
    mask = color_mask(img_bgr, rgb, tol=color_tol)
    out = np.zeros_like(mask)
    t, b, l, r = int(box["top"]), int(box["bottom"]), int(box["left"]), int(box["right"])
    out[t:b, l:r] = mask[t:b, l:r]
    if drop_grid:
        out = remove_grid(out, box)

    cols, rows = _column_means(out, box)
    if cols.size < 2:
        return []

    spline = CubicSpline(cols, rows)
    sample_cols = np.arange(cols.min(), cols.max() + 1, x_step_px, dtype=float)
    sample_rows = spline(sample_cols)

    # Calibration owns the (possibly log) pixel->data mapping.
    cal = calibration
    if log_x or log_y:
        cal.x.log = log_x
        cal.y.log = log_y
    points = [cal.pixel_to_data(c, rr) for c, rr in zip(sample_cols, sample_rows)]
    points.sort()
    return points


def curve_to_rows(points: list[tuple[float, float]], series: str, layer_type: str = "Line Graph", layer_idx: int = 1) -> list[dict]:
    return [
        {"layer_idx": layer_idx, "layer_type": layer_type, "series": series, "x": round(x, 6), "y": round(y, 6)}
        for x, y in points
    ]
