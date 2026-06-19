#!/usr/bin/env python3
"""Marker-precision test for el-60-a.

For each marker the extractor reports in data.csv:
  - predicted pixel position = (x, y) → calibration → (col_pred, row_pred)
  - actual pixel position    = nearest connected-component centroid of the
                                series' color mask in image.png (the "truth"
                                position of the visual marker)
  - drift_px                 = (col_pred − col_truth, row_pred − row_truth)
  - drift_data               = same drift converted to (Δx days, Δy fraction)

This isolates marker-detection drift from calibration drift (which step 2
verified is small: ±3 px in x, sub-pixel in y). Any larger drift here means
the extractor mis-located the marker centroid, not that calibration moved.

We also re-detect source markers fresh (color mask + CC + centroid) and
overlay them as small magenta '+' marks; deviations show as pred-ring vs
truth-+ offsets.
"""
import csv
import json
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-60-a", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-60-a", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-60-a", "data.csv")


SERIES_HSV = {
    # NOTE: V_max raised to 255 because this Excel-style chart uses pure
    # primary colors (BGR (255,0,0) → HSV (120,255,255)); the matplotlib
    # default mask in extraction_recipes.md caps V at 220 and misses these.
    "24C": dict(lo=(100, 80, 40), hi=(135, 255, 255), erode=5),   # blue
    "27C": dict(lo=(35, 60, 50),  hi=(85, 255, 255), erode=5),    # green
    "30C": dict(lo=(0, 100, 80),  hi=(10, 255, 255), erode=5),    # red
    # red wraps; we'll OR in the upper-hue red band manually
}


def detect_centroids(im, series):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    spec = SERIES_HSV[series]
    lo, hi = np.array(spec["lo"]), np.array(spec["hi"])
    mask = cv2.inRange(hsv, lo, hi)
    if series == "30C":
        mask |= cv2.inRange(hsv, np.array([170, 100, 80]),
                                  np.array([180, 255, 255]))
    # Wipe out the legend swatch area (rows 30-120, cols 565-660 per
    # calibration's legend_exclusion_used_for_frame, widened slightly)
    mask[20:135, 555:665] = 0
    # Erode away connector lines so markers stand alone
    k = cv2.getStructuringElement(cv2.MORPH_RECT,
                                  (spec["erode"], spec["erode"]))
    core = cv2.erode(mask, k)
    n, _, stats, cent = cv2.connectedComponentsWithStats(core, 8)
    pts = []
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        if a < 20:
            continue
        pts.append((float(cent[i][0]), float(cent[i][1]), int(a)))
    return pts


def main():
    with open(CAL) as f:
        cal = json.load(f)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]

    im = cv2.imread(IMG)

    # Predicted pixel positions from data.csv
    predicted = {"24C": [], "27C": [], "30C": []}
    with open(DATA) as f:
        for r in csv.DictReader(f):
            x = float(r["time_days"]); y = float(r["percentage_parous_females"])
            col = (x - bx) / mx
            row = (y - by) / my
            predicted[r["series"]].append((col, row, x, y))

    # Source centroids
    truth = {s: detect_centroids(im, s) for s in predicted}

    per_series = {}
    for series in ("24C", "27C", "30C"):
        preds = predicted[series]
        cents = truth[series]
        # Greedy nearest-neighbor pairing within radius 12 px
        used = [False] * len(cents)
        rows = []
        for col_p, row_p, x, y in preds:
            best_d, best_i = 12.0, None
            for i, (cx, cy, _) in enumerate(cents):
                if used[i]:
                    continue
                d = ((cx - col_p) ** 2 + (cy - row_p) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_i = d, i
            if best_i is None:
                rows.append({"x": x, "y": y, "col_pred": round(col_p, 2),
                              "row_pred": round(row_p, 2),
                              "matched": False})
                continue
            cx, cy, _ = cents[best_i]; used[best_i] = True
            dc = col_p - cx; dr = row_p - cy
            rows.append({
                "x": x, "y": y,
                "col_pred": round(col_p, 2), "row_pred": round(row_p, 2),
                "col_truth": round(cx, 2), "row_truth": round(cy, 2),
                "drift_col_px": round(dc, 2), "drift_row_px": round(dr, 2),
                "drift_x_days": round(dc * mx, 3),
                "drift_y_frac": round(dr * my, 4),
                "matched": True,
            })
        unmatched_truth = [(cx, cy, a)
                            for (cx, cy, a), u in zip(cents, used) if not u]
        per_series[series] = {"matched": rows,
                               "unmatched_source_centroids": unmatched_truth}

    # Print
    print(f"{'series':<6} {'x':>5} {'y':>6} {'col_pred':>9} {'col_truth':>10} "
          f"{'row_pred':>9} {'row_truth':>10} {'drift_px':>10} {'Δx(d)':>8}")
    for series in ("24C", "27C", "30C"):
        for r in per_series[series]["matched"]:
            if r["matched"]:
                d = (r["drift_col_px"] ** 2 + r["drift_row_px"] ** 2) ** 0.5
                print(f"{series:<6} {r['x']:>5} {r['y']:>6} "
                      f"{r['col_pred']:>9.2f} {r['col_truth']:>10.2f} "
                      f"{r['row_pred']:>9.2f} {r['row_truth']:>10.2f} "
                      f"{d:>10.2f} {r['drift_x_days']:>+8.3f}")
            else:
                print(f"{series:<6} {r['x']:>5} {r['y']:>6} "
                      f"{r['col_pred']:>9.2f} {'(no match)':>10} - - - -")
        un = per_series[series]["unmatched_source_centroids"]
        if un:
            print(f"  -- {len(un)} source centroids without a predicted match:")
            for cx, cy, a in un:
                print(f"     col={cx:.1f} row={cy:.1f} area={a}")

    # Summary
    print()
    print("Drift summary (matched pairs only):")
    for series in ("24C", "27C", "30C"):
        m = [r for r in per_series[series]["matched"] if r["matched"]]
        if not m:
            print(f"  {series}: no matches"); continue
        dcs = [r["drift_col_px"] for r in m]
        drs = [r["drift_row_px"] for r in m]
        ds  = [(c * c + r * r) ** 0.5 for c, r in zip(dcs, drs)]
        print(f"  {series}: n={len(m)}, |drift| mean={np.mean(ds):.2f} px "
              f"max={max(ds):.2f} px, Δcol mean={np.mean(dcs):+.2f} "
              f"Δrow mean={np.mean(drs):+.2f}")

    out = os.path.join(HERE, "marker_precision.json")
    with open(out, "w") as f:
        json.dump({"per_series": per_series}, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
