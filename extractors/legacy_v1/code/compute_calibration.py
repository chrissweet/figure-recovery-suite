#!/usr/bin/env python3
"""
compute_calibration.py — per-chart calibration.json (schema v1.0)

Reconstructed from the inline Python heredoc that was run after extract_all.py
to populate every chart's calibration.json with the colleague-requested
schema: plot_frame_box.offset + size, pixels_per_coordinate_unit, closed-form
data_to_pixel_formula, worked_example.

Detects the plot frame by:
  - y-axis col = leftmost long vertical dark line (gray<180, longest run > 50% of image height),
    image-border cols (within 15 px of edge) excluded
  - x-axis row = bottommost long horizontal, same rule
  - top/right of plot frame = bbox of non-white pixels inside the L-quadrant
    (legend rect excluded), so bars past their tick centers and points past
    the topmost labeled tick are included

Inputs (per chart, hard-coded below): m_x, b_x, m_y, b_y from extract_all.py
axis calibrations plus the actual x_data_range / y_data_range and a
human-readable worked_example.

Outputs: calibration.json next to data.csv in extracted/.
"""
import cv2
import numpy as np
import json
import os

# In the legacy-v1 run, the corpus lived at
# paper-atomizer-eval/chart-extraction/charts/. After the move to
# figure-recovery-suite, the corpus is at corpora/aedes-aegypti-2014/charts/
# and extractor results at extractors/graph-data-extraction/results/
# aedes-aegypti-2014/. Set BASE/RESULTS to whichever layout you're targeting.
BASE = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite"
CORPUS = f"{BASE}/corpora/aedes-aegypti-2014/charts"
RESULTS = f"{BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014"


def longest_run_per_col(dark):
    H, W = dark.shape
    out = np.zeros(W, dtype=np.int32)
    for c in range(W):
        col = dark[:, c]
        run = best = 0
        for v in col:
            if v:
                run += 1; best = max(best, run)
            else:
                run = 0
        out[c] = best
    return out


def longest_run_per_row(dark):
    H, W = dark.shape
    out = np.zeros(H, dtype=np.int32)
    for r in range(H):
        row = dark[r, :]
        run = best = 0
        for v in row:
            if v:
                run += 1; best = max(best, run)
            else:
                run = 0
        out[r] = best
    return out


def group(idx, gap=8):
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


def detect_axes(img, border_margin=15):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    dark = (gray < 180).astype(np.uint8)
    v = [int(c) for c in np.where(longest_run_per_col(dark) > 0.50 * H)[0]
         if border_margin <= c <= W - border_margin]
    h = [int(r) for r in np.where(longest_run_per_row(dark) > 0.50 * W)[0]
         if border_margin <= r <= H - border_margin]
    return group(v), group(h)


def detect_plot_frame(img, y_axis_col, x_axis_row, legend_rect=None):
    """Returns (L, R, T, B) of the visible plot region. L = y_axis_col,
    B = x_axis_row; T and R are bbox of non-white pixels in the L-quadrant."""
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = gray < 240
    quadrant = np.zeros_like(mask, dtype=bool)
    quadrant[:x_axis_row + 1, y_axis_col:] = True
    if legend_rect is not None:
        r0, r1, c0, c1 = legend_rect
        quadrant[r0:r1, c0:c1] = False
    interior = mask & quadrant
    rows = np.where(interior.any(axis=1))[0]
    cols = np.where(interior.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    return y_axis_col, int(cols.max()), int(rows.min()), x_axis_row


# Per-chart configuration. m_x/b_x/m_y/b_y from extract_all.py.
# x_unit / y_unit are human-readable labels for pixels_per_coordinate_unit.
CHARTS = [
    # (id, m_x, b_x, m_y, b_y, x_range, y_range, x_unit, y_unit, legend_rect, worked_example)
    ("el-60-a", 0.033503, -3.224314, -0.002808, 1.216004, (1, 23), (0.0, 1.0),
     "pixels per day", "pixels per fraction-unit", (30, 120, 565, 620),
     {"scenario": "Top of the 27°C marker at day 6 (parous-female fraction 0.3611).",
      "x": 6, "y": 0.3611,
      "verification": "This (col, row) should land on the green 27°C square at x=6 days."}),
    ("el-60-b", 0.036176, 6.483232, -0.002446, 1.149266, (10, 35), (0.0, 1.0),
     "pixels per °C", "pixels per fraction-unit", None,
     {"scenario": "The 30°C marker (red diamond) at 30 °C, max parity rate 0.6455.",
      "x": 30, "y": 0.6455,
      "verification": "This (col, row) should land on the red 30°C diamond."}),
    ("el-62", 0.009983, 21.680537, -0.028829, 16.415132, (24, 30), (0.0, 16.0),
     "pixels per °C", "pixels per day", (20, 160, 680, 980),
     {"scenario": "Top of the 27°C GC1 bar (mean duration 7.485 days).",
      "x": 27, "y": 7.485,
      "verification": "This (col, row) should land on top of the dark-blue middle bar."}),
    ("el-75", 0.048465, -3.992979, -0.046192, 25.668679, (0, 40), (0.0, 25.0),
     "pixels per °C", "pixels per day", None,
     {"scenario": "The middle data point (27°C, mean GC 7.155 days).",
      "x": 27.039, "y": 7.155,
      "verification": "This (col, row) should land on the middle black marker."}),
    ("el-80", 0.009844, 22.084497, -0.147330, 89.915238, (24, 30), (0.0, 80.0),
     "pixels per °C", "pixels per egg", (20, 160, 600, 960),
     {"scenario": "Top of the 27°C GC2 bar (mean eggs/female 32.5).",
      "x": 27, "y": 32.5,
      "verification": "This (col, row) should land on top of the middle light-gray bar in the 27°C group."}),
    ("el-88", 0.064303, -3.614709, -0.001853, 1.053524, (0, 50), (0.0, 1.0),
     "pixels per day", "pixels per fraction-unit", (280, 400, 870, 980),
     {"scenario": "24°C filled-disk marker at day 14 (survival 0.5817).",
      "x": 14, "y": 0.5817,
      "verification": "This (col, row) should land on a black filled circle around mid-plot."}),
    ("el-94", 0.056547, -3.174709, -0.000097, 0.987312, (0, 50), (0.93, 0.98),
     "pixels per day", "pixels per probability-unit", (200, 470, 700, 960),
     {"scenario": "24°C filled-disk marker at day 20 (daily survival p = 0.9685).",
      "x": 20, "y": 0.9685,
      "verification": "This (col, row) should land on a black filled circle around day 20."}),
    ("el-100", 0.001318, -0.073362, -0.049080, 27.995901, (0, 1.0), (0.0, 20.0),
     "pixels per parity-rate-unit", "pixels per day", (150, 540, 760, 840),
     {"scenario": "27°C green-square marker at parity rate 0.471, life expectancy 21.0 days.",
      "x": 0.471, "y": 21.0,
      "verification": "This (col, row) should land on one of the green 27°C squares in the upper band."}),
]


def main():
    for (cid, mx, bx, my, by, (xmin, xmax), (ymin, ymax),
         x_unit, y_unit, legend, ex) in CHARTS:
        img_path = f"{CORPUS}/{cid}/image.png"
        out_path = f"{RESULTS}/{cid}/calibration.json"
        if not os.path.exists(img_path):
            print(f"skip {cid}: no image at {img_path}")
            continue
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        img = cv2.imread(img_path)
        H, W = img.shape[:2]
        v_groups, h_groups = detect_axes(img)
        px_xmin = (xmin - bx) / mx
        px_xmax = (xmax - bx) / mx
        px_ymin = (ymin - by) / my
        px_ymax = (ymax - by) / my
        d_left = int(round(min(px_xmin, px_xmax)))
        d_right = int(round(max(px_xmin, px_xmax)))
        d_top = int(round(min(px_ymin, px_ymax)))
        d_bot = int(round(max(px_ymin, px_ymax)))

        y_axis_col = v_groups[0] if v_groups else d_left
        x_axis_row = (min(h_groups, key=lambda r: abs(r - d_bot))
                      if h_groups else d_bot)
        frame = detect_plot_frame(img, y_axis_col, x_axis_row, legend)
        L, R, T, B = frame if frame else (y_axis_col, d_right, d_top, x_axis_row)

        wcol = round((ex["x"] - bx) / mx)
        wrow = round((ex["y"] - by) / my)

        cal = {
            "image": "image.png",
            "image_size": {"width": W, "height": H},
            "plot_frame_box": {
                "offset": {"x": L, "y": T},
                "size": {"width": R - L + 1, "height": B - T + 1},
                "left": L, "top": T, "right": R, "bottom": B,
                "description": (
                    "Pixel bounding box of the visible plot region in image.png. "
                    "Origin (0,0) is the top-left of the image; y grows downward. "
                    "Left = detected y-axis col; bottom = detected x-axis row; "
                    "top/right = bbox of non-white pixels inside the L-quadrant "
                    "(legend rect excluded)."
                ),
            },
            "pixels_per_coordinate_unit": {
                "x": round(abs(1 / mx), 4),
                "y": round(abs(1 / my), 4),
                "x_unit_label": x_unit,
                "y_unit_label": y_unit,
                "description": "Image pixels per unit of x or y in data coordinates.",
            },
            "data_to_pixel_formula": {
                "col": f"col = (x_value - {bx}) / {mx}",
                "row": f"row = (y_value - {by}) / {my}",
                "explanation": "Convert (x, y) data → (col, row) pixel coords in image.png.",
            },
            "data_range": {"x_min": xmin, "x_max": xmax,
                           "y_min": ymin, "y_max": ymax},
            "axis_calibration": {
                "x_axis": {"formula": f"value = {mx} * col + {bx}",
                           "m": mx, "b": bx,
                           "inverse": f"col = (value - {bx}) / {mx}"},
                "y_axis": {"formula": f"value = {my} * row + {by}",
                           "m": my, "b": by,
                           "inverse": f"row = (value - {by}) / {my}"},
            },
            "worked_example": {
                "scenario": ex["scenario"],
                "input": {"x": ex["x"], "y": ex["y"]},
                "compute": [
                    f"col = ({ex['x']} - {bx}) / {mx} = {round((ex['x'] - bx) / mx, 1)}",
                    f"row = ({ex['y']} - {by}) / {my} = {round((ex['y'] - by) / my, 1)}",
                ],
                "result": {"col": wcol, "row": wrow},
                "verification": ex["verification"],
            },
            "detection_internals": {
                "y_axis_col_detected": v_groups[0] if v_groups else None,
                "x_axis_row_detected": (min(h_groups, key=lambda r: abs(r - d_bot))
                                        if h_groups else None),
                "all_interior_v_lines": v_groups,
                "all_interior_h_lines": h_groups,
                "legend_exclusion_used_for_frame": legend,
                "rule": ("Long-run detection: longest contiguous run of pixels with "
                         "gray<180 exceeding 50% of image height/width. Outer "
                         "image-border lines (within 15 px of edge) excluded."),
            },
        }
        with open(out_path, "w") as f:
            json.dump(cal, f, indent=2)
        print(f"{cid}: {W}x{H} plot=({L},{T},{R},{B})")


if __name__ == "__main__":
    main()
