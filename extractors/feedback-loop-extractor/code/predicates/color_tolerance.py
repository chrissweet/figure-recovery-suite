#!/usr/bin/env python3
"""Per-series color-tolerance auto-tune.

The fixed ±25 BGR tolerance breaks on real charts whose rendered colors
don't match the legend's nominal hex (e.g. el-100 27C is `#00FF00` in
chart_metadata but the actual rendered green is darker, so the mask
returns 0 pixels).

The fix: find the legend swatch in the source image, sample its pixels,
and set per-series tolerance to cover the observed variance.

Strategy:
  1. The legend's swatch positions aren't explicitly recorded, but we
     have `legend_exclusion_used_for_frame` (the legend bounding box)
     in calibration. Restrict the search to that box.
  2. For each series, mask the legend box for pixels NEAR (wide ±60
     tolerance) the nominal color, take the connected component, then
     measure that component's mean color and tolerance = the radius that
     covers 95 % of its pixels.
  3. Fall back to nominal hex + a wide default if the swatch isn't
     findable.

This is GT-free (everything comes from the source image and chart_metadata).
"""
import cv2
import numpy as np


def _hex_to_bgr(hex_str):
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return np.array([b, g, r], dtype=np.int32)


def autotune(image_bgr, chart_metadata, calibration,
              wide_search_tolerance=80, default_tolerance=35):
    """Return {series_id: {"target_bgr": np.array, "tolerance": float}}."""
    H, W = image_bgr.shape[:2]
    legend = calibration.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    if not legend:
        # No legend box — fall back to nominal hex + a wider default
        return {s["series_id"]: {
            "target_bgr": _hex_to_bgr(s.get("color", "#000000")),
            "tolerance": default_tolerance,
        } for s in chart_metadata.get("series_legend", [])
            if s.get("color", "").startswith("#")}

    if isinstance(legend, dict):
        t = int(legend.get("top", legend.get("row0", 0)))
        b = int(legend.get("bottom", legend.get("row1", H)))
        l = int(legend.get("left", legend.get("col0", 0)))
        r = int(legend.get("right", legend.get("col1", W)))
    else:
        t, b, l, r = (int(legend[0]), int(legend[1]),
                       int(legend[2]), int(legend[3]))
    t = max(0, t); b = min(H, b); l = max(0, l); r = min(W, r)
    if b <= t or r <= l:
        return {s["series_id"]: {
            "target_bgr": _hex_to_bgr(s.get("color", "#000000")),
            "tolerance": default_tolerance,
        } for s in chart_metadata.get("series_legend", [])
            if s.get("color", "").startswith("#")}

    legend_crop = image_bgr[t:b, l:r]
    out = {}
    for spec in chart_metadata.get("series_legend", []):
        sid = spec.get("series_id")
        hex_col = spec.get("color", "")
        if not sid or not hex_col.startswith("#"):
            continue
        nominal = _hex_to_bgr(hex_col)
        # Wide mask in the legend crop
        diff = legend_crop.astype(np.int32) - nominal
        dist = np.sqrt((diff * diff).sum(axis=2))
        mask = (dist <= wide_search_tolerance).astype(np.uint8)
        if mask.sum() < 4:
            # Swatch not found — fall back
            out[sid] = {"target_bgr": nominal,
                         "tolerance": default_tolerance}
            continue
        # Largest connected component within the wide mask = the swatch
        n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        if n_lbl <= 1:
            out[sid] = {"target_bgr": nominal,
                         "tolerance": default_tolerance}
            continue
        biggest = 1 + int(np.argmax(stats[1:, 4]))
        swatch_mask = (labels == biggest)
        swatch_pixels = legend_crop[swatch_mask]
        if len(swatch_pixels) < 4:
            out[sid] = {"target_bgr": nominal,
                         "tolerance": default_tolerance}
            continue
        # The mean color of the swatch is the actual rendered shade
        actual = swatch_pixels.mean(axis=0).astype(np.int32)
        # 95th-percentile distance from mean = tolerance that covers most
        # of the swatch's variation
        d = np.linalg.norm(swatch_pixels.astype(np.int32) - actual, axis=1)
        tol = float(np.percentile(d, 95)) + 8.0  # buffer for anti-aliasing
        # Floor to a sensible minimum so trivially-uniform swatches still
        # admit some variance in the plot area
        tol = max(tol, 18.0)
        out[sid] = {"target_bgr": actual, "tolerance": tol,
                     "source": "legend_swatch", "swatch_n_px": int(len(swatch_pixels))}
    return out
