#!/usr/bin/env python3
"""
write_calibration.py - emit a calibration.json that captures the plot
geometry of a digitized chart: image size, the rectangle enclosing the
axes and plot ('plot_frame_box' with offset and size), the per-axis
pixels-per-coordinate-unit ratios, the closed-form data-to-pixel formulas,
and a worked example so a colleague can verify the math visually.

The plot frame box is bounded by the DETECTED y-axis column (left) and
x-axis row (bottom), plus the bounding box of non-white pixels inside the
L-shaped axis quadrant (top, right). This captures data points that
extend past the labeled-tick range and bar groups that sit past their
tick centers — useful for grouped bar charts where matplotlib insets the
data inside the y-axis line.

Schema (v1.0):
    image: str
    image_size: {width, height}
    plot_frame_box:
        offset: {x, y}                 # top-left of plot in image coords
        size:   {width, height}
        left, top, right, bottom       # absolute pixel coords (redundant w/ offset/size)
        description: str
    pixels_per_coordinate_unit:
        x: float                       # |1 / m_x|
        y: float                       # |1 / m_y|
        x_unit_label, y_unit_label: str
    data_to_pixel_formula:
        col: "col = (x_value - b_x) / m_x"
        row: "row = (y_value - b_y) / m_y"
    data_range: {x_min, x_max, y_min, y_max}
    axis_calibration:
        x_axis: {formula, m, b, inverse}
        y_axis: {formula, m, b, inverse}
    worked_example:
        scenario: str
        input: {x, y}
        compute: [str, str]
        result: {col, row}
        verification: str
    detection_internals:
        y_axis_col_detected, x_axis_row_detected
        all_interior_v_lines, all_interior_h_lines
        rule: str

Use as a script:
    python3 write_calibration.py IMAGE.png OUT.json \\
        --x-axis-cal m b --y-axis-cal m b \\
        --x-data-range XMIN XMAX --y-data-range YMIN YMAX \\
        [--x-unit-label LABEL] [--y-unit-label LABEL] \\
        [--worked-example SCENARIO X Y VERIFICATION]

Or as a module:
    from write_calibration import write_calibration
    write_calibration(image_path, out_path,
                      x_axis=(mx, bx), y_axis=(my, by),
                      x_data_range=(xmin, xmax), y_data_range=(ymin, ymax),
                      x_unit_label="pixels per °C", y_unit_label="pixels per day",
                      worked_example={"scenario": "...", "x": 27, "y": 7.485,
                                       "verification": "..."})
"""
import argparse
import json
import sys
import numpy as np
import cv2


def _longest_run_per_col(dark):
    H, W = dark.shape
    out = np.zeros(W, dtype=np.int32)
    for c in range(W):
        col = dark[:, c]
        run = best = 0
        for v in col:
            if v: run += 1; best = max(best, run)
            else: run = 0
        out[c] = best
    return out


def _longest_run_per_row(dark):
    H, W = dark.shape
    out = np.zeros(H, dtype=np.int32)
    for r in range(H):
        row = dark[r, :]
        run = best = 0
        for v in row:
            if v: run += 1; best = max(best, run)
            else: run = 0
        out[r] = best
    return out


def _group(idx, gap=8):
    if len(idx) == 0:
        return []
    g, c = [], [idx[0]]
    for x in idx[1:]:
        if x - c[-1] <= gap:
            c.append(x)
        else:
            g.append(int(np.mean(c))); c = [x]
    g.append(int(np.mean(c)))
    return g


def detect_axes(img, border_margin=15, dark_thr=180, line_density=0.50):
    """Detect plot-frame axis lines by longest-contiguous-run analysis.

    Returns (v_groups, h_groups): grouped column / row positions of long
    dark vertical / horizontal lines in the image interior (image borders
    within border_margin px excluded).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    H, W = gray.shape
    dark = (gray < dark_thr).astype(np.uint8)
    cr = _longest_run_per_col(dark)
    rr = _longest_run_per_row(dark)
    v = [int(c) for c in np.where(cr > line_density * H)[0]
         if border_margin <= c <= W - border_margin]
    h = [int(r) for r in np.where(rr > line_density * W)[0]
         if border_margin <= r <= H - border_margin]
    return _group(v), _group(h)


def _detect_plot_frame_from_content(img, y_axis_col, x_axis_row, legend_exclusion=None):
    """Bbox of non-white pixels inside the L-shaped axis quadrant. Keeps the
    detected left = y_axis_col and bottom = x_axis_row; extends top and right
    to wherever the data actually sits (past tick centers, past topmost label,
    etc.)."""
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    mask = gray < 240
    quadrant = np.zeros_like(mask, dtype=bool)
    quadrant[:x_axis_row + 1, y_axis_col:] = True
    if legend_exclusion is not None:
        r0, r1, c0, c1 = legend_exclusion
        quadrant[r0:r1, c0:c1] = False
    interior = mask & quadrant
    rows = np.where(interior.any(axis=1))[0]
    cols = np.where(interior.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    top, bot = int(rows.min()), int(rows.max())
    left, right = int(cols.min()), int(cols.max())
    return (y_axis_col, right, top, x_axis_row)  # L,R,T,B; L and B clamped to detected axes


def write_calibration(image_path, out_path, x_axis, y_axis,
                      x_data_range, y_data_range,
                      x_unit_label="x-units", y_unit_label="y-units",
                      worked_example=None, legend_exclusion=None):
    """Emit calibration.json next to an extraction's data.csv.

    worked_example: optional dict {"scenario": str, "x": float, "y": float,
                                    "verification": str}. If None, a default
                                    is generated using a midpoint of the data range.
    legend_exclusion: optional (row0, row1, col0, col1) rectangle to skip when
                     computing the plot frame's top/right from content.
    """
    mx, bx = x_axis
    my, by = y_axis
    xmin, xmax = x_data_range
    ymin, ymax = y_data_range

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    H, W = img.shape[:2]
    v_groups, h_groups = detect_axes(img)

    # Tick-extent box from calibration
    px_xmin = (xmin - bx) / mx
    px_xmax = (xmax - bx) / mx
    px_ymin = (ymin - by) / my
    px_ymax = (ymax - by) / my
    d_left = int(round(min(px_xmin, px_xmax)))
    d_right = int(round(max(px_xmin, px_xmax)))
    d_top = int(round(min(px_ymin, px_ymax)))
    d_bot = int(round(max(px_ymin, px_ymax)))

    y_axis_col = v_groups[0] if v_groups else d_left
    x_axis_row = min(h_groups, key=lambda r: abs(r - d_bot)) if h_groups else d_bot

    # Plot frame from content extent inside L-quadrant
    frame = _detect_plot_frame_from_content(img, y_axis_col, x_axis_row, legend_exclusion)
    if frame is None:
        L, R, T, B = y_axis_col, d_right, d_top, x_axis_row
    else:
        L, R, T, B = frame

    pw = R - L + 1
    ph = B - T + 1

    if worked_example is None:
        wx = (xmin + xmax) / 2
        wy = (ymin + ymax) / 2
        worked_example = {
            "scenario": f"Midpoint of the data range (x={wx}, y={wy}).",
            "x": wx, "y": wy,
            "verification": f"This (col, row) should land near the center of the plot frame.",
        }
    wx, wy = worked_example["x"], worked_example["y"]
    wcol = round((wx - bx) / mx)
    wrow = round((wy - by) / my)

    cal = {
        "image": image_path.rsplit('/', 1)[-1],
        "image_size": {"width": W, "height": H},
        "plot_frame_box": {
            "offset": {"x": L, "y": T},
            "size":   {"width": pw, "height": ph},
            "left":   L, "top": T, "right": R, "bottom": B,
            "description": (
                "Pixel bounding box of the visible plot region in image. "
                "Origin (0,0) is the top-left of the image; y grows downward. "
                "'offset' is the top-left corner of the box in image coordinates; "
                "'size' is its width and height in pixels. Detected by finding the "
                "y-axis line (left), x-axis line (bottom), and the bounding box of "
                "non-white pixels inside the L-shaped quadrant (top, right)."
            ),
        },
        "pixels_per_coordinate_unit": {
            "x": round(abs(1 / mx), 4),
            "y": round(abs(1 / my), 4),
            "x_unit_label": x_unit_label,
            "y_unit_label": y_unit_label,
            "description": "How many image pixels equal one unit of x or y in data coordinates.",
        },
        "data_to_pixel_formula": {
            "col": f"col = (x_value - {bx}) / {mx}",
            "row": f"row = (y_value - {by}) / {my}",
            "explanation": (
                "Convert any (x, y) data coordinate to a (col, row) pixel coordinate "
                "in image.png. Derived from the linear axis calibration fit during extraction."
            ),
        },
        "data_range": {"x_min": xmin, "x_max": xmax, "y_min": ymin, "y_max": ymax},
        "axis_calibration": {
            "x_axis": {"formula": f"value = {mx} * col + {bx}", "m": mx, "b": bx,
                       "inverse": f"col = (value - {bx}) / {mx}"},
            "y_axis": {"formula": f"value = {my} * row + {by}", "m": my, "b": by,
                       "inverse": f"row = (value - {by}) / {my}"},
        },
        "worked_example": {
            "scenario": worked_example["scenario"],
            "input":    {"x": wx, "y": wy},
            "compute":  [
                f"col = ({wx} - {bx}) / {mx} = {round((wx - bx) / mx, 1)}",
                f"row = ({wy} - {by}) / {my} = {round((wy - by) / my, 1)}",
            ],
            "result": {"col": wcol, "row": wrow},
            "verification": worked_example.get("verification", ""),
        },
        "detection_internals": {
            "y_axis_col_detected": v_groups[0] if v_groups else None,
            "x_axis_row_detected": (min(h_groups, key=lambda r: abs(r - d_bot)) if h_groups else None),
            "all_interior_v_lines": v_groups,
            "all_interior_h_lines": h_groups,
            "legend_exclusion_used_for_frame": legend_exclusion,
            "rule": (
                "Long-run detection: longest contiguous run of pixels with gray<180 "
                "exceeding 50% of image height/width. Outer image-border lines "
                "(within 15 px of edge) excluded."
            ),
        },
    }
    with open(out_path, "w") as f:
        json.dump(cal, f, indent=2)
    return cal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--x-axis-cal", type=float, nargs=2, metavar=("m", "b"), required=True)
    ap.add_argument("--y-axis-cal", type=float, nargs=2, metavar=("m", "b"), required=True)
    ap.add_argument("--x-data-range", type=float, nargs=2, metavar=("XMIN", "XMAX"), required=True)
    ap.add_argument("--y-data-range", type=float, nargs=2, metavar=("YMIN", "YMAX"), required=True)
    ap.add_argument("--x-unit-label", default="x-units")
    ap.add_argument("--y-unit-label", default="y-units")
    ap.add_argument("--legend-exclusion", type=int, nargs=4, metavar=("ROW0", "ROW1", "COL0", "COL1"),
                    help="Rectangle to exclude when computing the plot-frame top/right from content.")
    args = ap.parse_args()

    cal = write_calibration(
        args.image, args.out,
        tuple(args.x_axis_cal), tuple(args.y_axis_cal),
        tuple(args.x_data_range), tuple(args.y_data_range),
        x_unit_label=args.x_unit_label,
        y_unit_label=args.y_unit_label,
        legend_exclusion=tuple(args.legend_exclusion) if args.legend_exclusion else None,
    )
    pf = cal["plot_frame_box"]
    px = cal["pixels_per_coordinate_unit"]
    print(f"wrote {args.out}")
    print(f"  image:      {cal['image_size']['width']}x{cal['image_size']['height']}")
    print(f"  plot_frame: offset=({pf['offset']['x']},{pf['offset']['y']}) "
          f"size={pf['size']['width']}x{pf['size']['height']}")
    print(f"  px/x={px['x']} {px['x_unit_label']}, px/y={px['y']} {px['y_unit_label']}")


if __name__ == "__main__":
    main()
