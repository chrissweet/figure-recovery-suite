#!/usr/bin/env python3
"""Pixel-level data-layer renderer (NO matplotlib).

Renders the extracted data ONTO a blank canvas at the exact pixel dimensions
of the source image, using the calibration's data_to_pixel mapping to place
each artifact at the precise pixel position the extractor's calibration
implies. Comparison-grade output: every pixel position is reproducible from
calibration + data alone, no autolayout, no font rendering, no margin guesses.

This is the pixel-precise side of the precision boundary named in
`fluffy-conjuring-salamander.md`:
  - Data IN the plot region (markers, lines, bars) -> pixel-exact (this file)
  - Chrome (titles, labels, legend)                -> loose (separate file)

The contrast with the prior matplotlib-based renderer: matplotlib's
`tight_layout` and chrome-driven margins make the inner plot area's pixel
position non-deterministic. That breaks pixel-level comparison. Drawing
directly to (col, row) via cv2 primitives removes that uncertainty.

Usage:
    from pixel_replot import render
    canvas = render(image_size, calibration, chart_metadata, data_rows)
    cv2.imwrite("replot_data_layer.png", canvas)
"""
import csv
import json
import os
import sys

import cv2
import numpy as np


def _hex_to_bgr(hex_str):
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (int(b), int(g), int(r))


def _data_to_pixel(value, m, b, scale):
    if scale == "log10":
        if value <= 0: return None
        return (np.log10(value) - b) / m
    return (value - b) / m


_MARKER_SHAPE = {
    "filled circle":  "o_fill",
    "filled square":  "s_fill",
    "filled diamond": "d_fill",
    "open circle":    "o_open",
    "open square":    "s_open",
    "open diamond":   "d_open",
}


def _draw_marker(canvas, col, row, color_bgr, shape_key, size=6):
    """Draw a marker at (col, row) with the given shape and color."""
    c, r = int(col), int(row)
    if shape_key in ("o_fill", "o_open"):
        cv2.circle(canvas, (c, r), size,  color_bgr,
                    thickness=-1 if shape_key == "o_fill" else 1,
                    lineType=cv2.LINE_AA)
    elif shape_key in ("s_fill", "s_open"):
        tl = (c - size, r - size); br = (c + size, r + size)
        cv2.rectangle(canvas, tl, br, color_bgr,
                       thickness=-1 if shape_key == "s_fill" else 1,
                       lineType=cv2.LINE_AA)
    elif shape_key in ("d_fill", "d_open"):
        pts = np.array([[c, r - size], [c + size, r],
                          [c, r + size], [c - size, r]], dtype=np.int32)
        if shape_key == "d_fill":
            cv2.fillPoly(canvas, [pts], color_bgr, lineType=cv2.LINE_AA)
        else:
            cv2.polylines(canvas, [pts], isClosed=True, color=color_bgr,
                           thickness=1, lineType=cv2.LINE_AA)
    else:  # default to filled circle
        cv2.circle(canvas, (c, r), size, color_bgr, -1, cv2.LINE_AA)


def _line_style_to_dash(style):
    """Return (dash_on_px, dash_off_px) for matplotlib-style names."""
    return {
        "solid":   (None, None),
        "dashed":  (6, 4),
        "dotted":  (2, 3),
        "dashdot": (6, 3),
    }.get(style, (None, None))


def _draw_dashed_polyline(canvas, pts_xy, color, thickness, dash_on, dash_off):
    """cv2 doesn't have a built-in dashed polyline; emulate by sampling the
    polyline path at dash_on / dash_off increments."""
    if len(pts_xy) < 2:
        return
    pts = np.array(pts_xy, dtype=np.float64)
    # Cumulative arc length
    seg_lens = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    if seg_lens.sum() == 0:
        return
    cum = np.concatenate([[0], np.cumsum(seg_lens)])
    total = cum[-1]

    def point_at(s):
        """Interpolate the polyline at arc length s."""
        if s <= 0: return pts[0]
        if s >= total: return pts[-1]
        i = int(np.searchsorted(cum, s) - 1)
        i = max(0, min(i, len(seg_lens) - 1))
        t = (s - cum[i]) / max(1e-9, seg_lens[i])
        return pts[i] + t * (pts[i + 1] - pts[i])

    s = 0.0
    while s < total:
        s_end = min(s + dash_on, total)
        p0 = point_at(s); p1 = point_at(s_end)
        cv2.line(canvas, (int(p0[0]), int(p0[1])),
                  (int(p1[0]), int(p1[1])), color, thickness, cv2.LINE_AA)
        s = s_end + dash_off


def _draw_line(canvas, pts_xy, color_bgr, line_style, thickness=2):
    """Draw a (possibly dashed) polyline through pts_xy = [(col,row), ...]."""
    if len(pts_xy) < 2:
        return
    dash_on, dash_off = _line_style_to_dash(line_style)
    if dash_on is None:
        np_pts = np.array([pts_xy], dtype=np.int32)
        cv2.polylines(canvas, np_pts, isClosed=False, color=color_bgr,
                       thickness=thickness, lineType=cv2.LINE_AA)
    else:
        _draw_dashed_polyline(canvas, pts_xy, color_bgr, thickness,
                                dash_on, dash_off)


def render(image_size, calibration, chart_metadata, data_rows,
            marker_size=6, line_thickness=2, bar_color_fallback=(80, 80, 80)):
    """Render the data layer.

    Args:
      image_size: dict with width / height keys (the source's exact pixel dims)
      calibration: dict from calibration.json (axis_calibration, plot_frame_box)
      chart_metadata: dict from chart_metadata.json (series_legend)
      data_rows: list of dicts with layer_type, series, x, y

    Returns:
      H x W x 3 uint8 numpy array, white background, data drawn at calibrated
      pixel positions.
    """
    W = int(image_size["width"]); H = int(image_size["height"])
    canvas = np.full((H, W, 3), 255, dtype=np.uint8)

    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax.get("m"), x_ax.get("b")
    my, by = y_ax.get("m"), y_ax.get("b")
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")

    pf = calibration["plot_frame_box"]
    baseline_row = int(pf["bottom"])  # x-axis y-position for bar bases

    # Per-series style from chart_metadata
    style = {}
    for spec in chart_metadata.get("series_legend", []):
        sid = spec.get("series_id")
        if not sid: continue
        color_hex = spec.get("color", "#666666")
        bgr = _hex_to_bgr(color_hex) if color_hex.startswith("#") else (102, 102, 102)
        shape_str = spec.get("marker_shape", "filled circle")
        shape_key = _MARKER_SHAPE.get(shape_str, "o_fill")
        line_style = spec.get("line_style", "solid")
        style[sid] = {"color": bgr, "shape": shape_key,
                       "line_style": line_style}

    # Group rows by (series, layer_type) so line layers get connected polylines
    by_sl = {}
    for r in data_rows:
        by_sl.setdefault((r["series"], r["layer_type"]), []).append(r)

    for (sid, layer), pts in by_sl.items():
        st = style.get(sid, {"color": (102, 102, 102),
                              "shape": "o_fill", "line_style": "solid"})
        if "Scatter" in layer:
            for r in pts:
                col = _data_to_pixel(r["x"], mx, bx, x_scale)
                row = _data_to_pixel(r["y"], my, by, y_scale)
                if col is None or row is None: continue
                if not (0 <= col < W and 0 <= row < H): continue
                _draw_marker(canvas, col, row, st["color"],
                              st["shape"], marker_size)
        elif "Column" in layer or "Bar" in layer:
            # Bar tops: claim (x, y) is the bar top; draw a thin rectangle
            # from baseline_row up to row. Width is a small constant; the
            # source's true bar width isn't in the calibration, but the bar
            # POSITION (col_center) and TOP (row) are.
            bar_half_w = 6
            for r in pts:
                col = _data_to_pixel(r["x"], mx, bx, x_scale)
                row = _data_to_pixel(r["y"], my, by, y_scale)
                if col is None or row is None: continue
                tl = (int(col - bar_half_w), int(row))
                br = (int(col + bar_half_w), baseline_row)
                cv2.rectangle(canvas, tl, br, st["color"], -1,
                               lineType=cv2.LINE_AA)
        elif "Line" in layer or "Spline" in layer:
            # Sort by x, build a polyline of (col, row) pixel coords
            pts_sorted = sorted(pts, key=lambda r: r["x"])
            pix = []
            for r in pts_sorted:
                col = _data_to_pixel(r["x"], mx, bx, x_scale)
                row = _data_to_pixel(r["y"], my, by, y_scale)
                if col is None or row is None: continue
                if not (0 <= col < W and 0 <= row < H): continue
                pix.append((col, row))
            if len(pix) >= 2:
                _draw_line(canvas, pix, st["color"], st["line_style"],
                            line_thickness)
        elif "ErrorBar" in layer:
            # Each row is one cap at (x, y). Render as a short horizontal
            # tick (4 px each side).
            for r in pts:
                col = _data_to_pixel(r["x"], mx, bx, x_scale)
                row = _data_to_pixel(r["y"], my, by, y_scale)
                if col is None or row is None: continue
                cv2.line(canvas, (int(col - 4), int(row)),
                          (int(col + 4), int(row)), st["color"], 1,
                          cv2.LINE_AA)
        elif "StackedSegment" in layer:
            # Horizontal stroke at the segment boundary y
            for r in pts:
                col = _data_to_pixel(r["x"], mx, bx, x_scale)
                row = _data_to_pixel(r["y"], my, by, y_scale)
                if col is None or row is None: continue
                cv2.line(canvas, (int(col - 8), int(row)),
                          (int(col + 8), int(row)), st["color"], 2,
                          cv2.LINE_AA)
    return canvas


if __name__ == "__main__":
    chart_dir = sys.argv[1]
    image_path = sys.argv[2] if len(sys.argv) > 2 else None
    out_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        chart_dir, "replot_data_layer.png")
    if image_path is None:
        parts = os.path.normpath(chart_dir).split(os.sep)
        if "results-v3" in parts:
            i = parts.index("results-v3")
            image_path = os.path.join(
                "corpora", parts[i + 1], "charts", parts[i + 2], "image.png")
    cal = json.load(open(os.path.join(chart_dir, "calibration.json")))
    md  = json.load(open(os.path.join(chart_dir, "chart_metadata.json")))
    rows = []
    with open(os.path.join(chart_dir, "data.csv")) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"layer_idx": int(r.get("layer_idx", "0") or 0),
                              "layer_type": r.get("layer_type", "Scatter Plot"),
                              "series": r.get("series", "default"),
                              "x": float(r["x"]), "y": float(r["y"])})
            except (KeyError, ValueError):
                continue
    img = cv2.imread(image_path)
    H, W = img.shape[:2]
    out = render({"width": W, "height": H}, cal, md, rows)
    cv2.imwrite(out_path, out)
    print(f"wrote {out_path} ({W} x {H})")
