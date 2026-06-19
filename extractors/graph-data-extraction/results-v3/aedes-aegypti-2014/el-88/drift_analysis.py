#!/usr/bin/env python3
"""el-88 calibration tick-grid drift analysis (TDD step 2).

Same procedure as el-60-a: detect source tick label centers in the bands
just outside the plot frame, pair each labeled tick value to the nearest
detected center, report drift in pixels per tick.
"""
import json
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-88", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-88", "calibration.json")


def group(idx, gap):
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


def match_nearest(cal_positions, detected, max_dist):
    out = []; used = [False] * len(detected)
    for cp in cal_positions:
        best_d, best_i = max_dist + 1, None
        for i, dp in enumerate(detected):
            if used[i]: continue
            d = abs(dp - cp)
            if d < best_d:
                best_d, best_i = d, i
        if best_i is not None and best_d <= max_dist:
            used[best_i] = True
            out.append((cp, detected[best_i]))
        else:
            out.append((cp, None))
    return out


def main():
    with open(CAL) as f:
        cal = json.load(f)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    pf = cal["plot_frame_box"]
    left, bot = pf["left"], pf["bottom"]

    im = cv2.imread(IMG)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape

    # X labels are at 0, 10, 20, 30, 40, 50 (every 10 days)
    labeled_x = [0, 10, 20, 30, 40, 50]
    # Y labels: 0,00 / 0,20 / 0,40 / 0,60 / 0,80 / 1,00 (every 0.20)
    labeled_y = [1.00, 0.80, 0.60, 0.40, 0.20, 0.00]

    xband = (gray[bot + 6: bot + 30, left - 5: pf["right"] + 5] < 100)
    xcent_local = group(np.where(xband.sum(axis=0) > 1)[0], 25)
    xcent = [c + (left - 5) for c in xcent_local]

    yband = (gray[:bot - 10, max(0, left - 50): max(1, left - 2)] < 100)
    ycent = group(np.where(yband.sum(axis=1) > 0)[0], 12)

    print(f"detected x tick centers ({len(xcent)}): {xcent}")
    print(f"detected y tick centers ({len(ycent)}): {ycent}")
    print()

    print("x-axis (drift_px = detected − calibration)")
    print(f"  {'tick':>6} {'cal_col':>9} {'detected_col':>14} {'drift_px':>10}")
    x_drifts = []
    cal_x_cols = [(t - bx) / mx for t in labeled_x]
    for t, (c_cal, c_det) in zip(labeled_x, match_nearest(cal_x_cols, xcent, 20)):
        if c_det is None:
            print(f"  {t:>6} {c_cal:>9.2f} {'(none)':>14} {'-':>10}")
            continue
        d = c_det - c_cal; x_drifts.append(d)
        print(f"  {t:>6} {c_cal:>9.2f} {c_det:>14d} {d:>+10.2f}")

    print()
    print("y-axis (drift_px = detected − calibration)")
    print(f"  {'tick':>6} {'cal_row':>9} {'detected_row':>14} {'drift_px':>10}")
    y_drifts = []
    cal_y_rows = [(t - by) / my for t in labeled_y]
    for t, (r_cal, r_det) in zip(labeled_y, match_nearest(cal_y_rows, ycent, 12)):
        if r_det is None:
            print(f"  {t:>6.2f} {r_cal:>9.2f} {'(none)':>14} {'-':>10}")
            continue
        d = r_det - r_cal; y_drifts.append(d)
        print(f"  {t:>6.2f} {r_cal:>9.2f} {r_det:>14d} {d:>+10.2f}")

    print()
    print("Summary")
    if x_drifts:
        print(f"  x drift: min {min(x_drifts):+.2f}  max {max(x_drifts):+.2f}  "
              f"mean {np.mean(x_drifts):+.2f}  std {np.std(x_drifts):.2f} px")
    if y_drifts:
        print(f"  y drift: min {min(y_drifts):+.2f}  max {max(y_drifts):+.2f}  "
              f"mean {np.mean(y_drifts):+.2f}  std {np.std(y_drifts):.2f} px")

    out = os.path.join(HERE, "drift.json")
    with open(out, "w") as f:
        json.dump({
            "x_ticks_expected": labeled_x,
            "x_ticks_detected_centers": xcent,
            "x_drifts_px": [round(d, 2) for d in x_drifts],
            "y_ticks_expected": labeled_y,
            "y_ticks_detected_centers": ycent,
            "y_drifts_px": [round(d, 2) for d in y_drifts],
        }, f, indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
