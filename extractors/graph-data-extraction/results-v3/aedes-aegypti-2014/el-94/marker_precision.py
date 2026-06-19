#!/usr/bin/env python3
"""el-94 marker-precision test (TDD step 3, glyph-presence variant).

For each data.csv row, check if a marker glyph sits in a window around the
predicted (col, row). Flag legend hits and rows outside data range.

el-94 is the corpus's audit failure case: 27°C scatter Recall = 0.56
because gray squares fuse with the solid 27°C fit curve. Step 1's overlay
made the missed squares visible; here we measure the precision of the
markers that DID get extracted.
"""
import csv
import json
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-94", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "data.csv")


def check_glyph_at(gray, hsv, col, row, half=7):
    h, w = gray.shape
    c0 = max(0, int(col) - half); c1 = min(w, int(col) + half + 1)
    r0 = max(0, int(row) - half); r1 = min(h, int(row) + half + 1)
    win = gray[r0:r1, c0:c1]
    sat = hsv[r0:r1, c0:c1, 1]
    dark = ((win < 50) & (sat < 50))
    gray_sq = ((win >= 60) & (win <= 210) & (sat < 50))
    glyph = dark | gray_sq
    n_dark = int(dark.sum()); n_gray = int(gray_sq.sum())
    n_glyph = int(glyph.sum())
    if n_glyph < 6:
        return ("none", 0.0, 0.0, n_dark, n_gray)
    ys, xs = np.where(glyph)
    cx = xs.mean() + c0; cy = ys.mean() + r0
    return ("marker", cx - col, cy - row, n_dark, n_gray)


def main():
    with open(CAL) as f: cal = json.load(f)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    dr = cal["data_range"]
    legend = cal["detection_internals"].get("legend_exclusion_used_for_frame")
    ly0, ly1, lx0, lx1 = (legend if legend else (-1, -1, -1, -1))

    im = cv2.imread(IMG)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)

    per_series = {}
    flagged = []
    with open(DATA) as f:
        for r in csv.DictReader(f):
            series = r["series"]
            x = float(r["age_days"]); y = float(r["daily_survival_p"])
            col = (x - bx) / mx; row = (y - by) / my
            kind, dx, dy, n_dark, n_gray = check_glyph_at(gray, hsv, col, row)
            in_range = (dr["x_min"] <= x <= dr["x_max"] and
                        dr["y_min"] <= y <= dr["y_max"])
            in_legend = (ly0 <= row <= ly1 and lx0 <= col <= lx1) if legend else False
            rec = {"x": x, "y": y, "col_pred": round(col, 2),
                    "row_pred": round(row, 2), "found_glyph": kind == "marker",
                    "drift_col_px": round(dx, 2), "drift_row_px": round(dy, 2),
                    "drift_x_days": round(dx * mx, 3),
                    "drift_y_frac": round(dy * my, 5),
                    "n_dark_px": n_dark, "n_gray_px": n_gray,
                    "in_data_range": in_range, "in_legend_box": in_legend}
            per_series.setdefault(series, []).append(rec)
            if not in_range or in_legend:
                flagged.append((series, x, y, col, row, in_legend))

    print(f"{'series':<6} {'n_pred':>7} {'real':>5} {'legend':>7} "
          f"{'offrange':>9} {'mean_drift':>11} {'max_drift':>10}")
    for series in ("24C", "27C", "30C"):
        recs = per_series.get(series, [])
        real = [r for r in recs if r["in_data_range"] and not r["in_legend_box"]]
        leg  = [r for r in recs if r["in_legend_box"]]
        off  = [r for r in recs if not r["in_data_range"] and not r["in_legend_box"]]
        if real:
            ds = [(r["drift_col_px"] ** 2 + r["drift_row_px"] ** 2) ** 0.5
                   for r in real]
            mean_d = float(np.mean(ds)); max_d = float(max(ds))
        else:
            mean_d, max_d = 0.0, 0.0
        print(f"{series:<6} {len(recs):>7d} {len(real):>5d} {len(leg):>7d} "
              f"{len(off):>9d} {mean_d:>11.2f} {max_d:>10.2f}")

    print()
    print("Rows flagged as legend / off-range:")
    if not flagged:
        print("  (none)")
    for series, x, y, col, row, in_leg in flagged:
        tag = "LEGEND" if in_leg else "OFF-RANGE"
        print(f"  {tag:<10} {series} ({x}, {y}) → col={col:.1f} row={row:.1f}")

    print()
    print("Matched rows with drift > 2 px:")
    any_drift = False
    for series in ("24C", "27C", "30C"):
        for r in per_series.get(series, []):
            if not r["found_glyph"]: continue
            d = (r["drift_col_px"] ** 2 + r["drift_row_px"] ** 2) ** 0.5
            if d > 2.0:
                any_drift = True
                print(f"  {series} ({r['x']}, {r['y']}): drift {d:.2f} px")
    if not any_drift:
        print("  (none)")

    out = os.path.join(HERE, "marker_precision.json")
    with open(out, "w") as f:
        json.dump(per_series, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
