#!/usr/bin/env python3
"""el-94 calibration tick-grid drift (TDD step 2). y range 0.93-0.98."""
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


def group(idx, gap):
    if len(idx) == 0: return []
    g, c = [], [idx[0]]
    for x in idx[1:]:
        if x - c[-1] <= gap: c.append(x)
        else:
            g.append(int(np.mean(c))); c = [x]
    g.append(int(np.mean(c)))
    return g


def match_nearest(cal_positions, detected, max_dist):
    out, used = [], [False] * len(detected)
    for cp in cal_positions:
        best_d, best_i = max_dist + 1, None
        for i, dp in enumerate(detected):
            if used[i]: continue
            d = abs(dp - cp)
            if d < best_d: best_d, best_i = d, i
        if best_i is not None and best_d <= max_dist:
            used[best_i] = True
            out.append((cp, detected[best_i]))
        else:
            out.append((cp, None))
    return out


def main():
    with open(CAL) as f: cal = json.load(f)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    pf = cal["plot_frame_box"]
    left, bot = pf["left"], pf["bottom"]

    im = cv2.imread(IMG)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)

    labeled_x = [0, 10, 20, 30, 40, 50]
    # y labels: 0.93, 0.94, ..., 0.98 (every 0.01)
    labeled_y = [0.98, 0.97, 0.96, 0.95, 0.94, 0.93]

    xband = (gray[bot + 6: bot + 30, left - 5: pf["right"] + 5] < 100)
    xcent_local = group(np.where(xband.sum(axis=0) > 1)[0], 25)
    xcent = [c + (left - 5) for c in xcent_local]

    yband = (gray[:bot - 10, max(0, left - 50): max(1, left - 2)] < 100)
    ycent = group(np.where(yband.sum(axis=1) > 0)[0], 12)

    print(f"detected x centers ({len(xcent)}): {xcent}")
    print(f"detected y centers ({len(ycent)}): {ycent}")
    print()

    print("x-axis (drift_px)")
    x_drifts = []
    cal_x_cols = [(t - bx) / mx for t in labeled_x]
    for t, (c_cal, c_det) in zip(labeled_x, match_nearest(cal_x_cols, xcent, 25)):
        if c_det is None:
            print(f"  {t:>4} {c_cal:>9.2f} {'(none)':>14} -"); continue
        d = c_det - c_cal; x_drifts.append(d)
        print(f"  {t:>4} {c_cal:>9.2f} {c_det:>14d} {d:>+10.2f}")

    print()
    print("y-axis (drift_px)")
    y_drifts = []
    cal_y_rows = [(t - by) / my for t in labeled_y]
    for t, (r_cal, r_det) in zip(labeled_y, match_nearest(cal_y_rows, ycent, 15)):
        if r_det is None:
            print(f"  {t:>6.2f} {r_cal:>9.2f} {'(none)':>14} -"); continue
        d = r_det - r_cal; y_drifts.append(d)
        print(f"  {t:>6.2f} {r_cal:>9.2f} {r_det:>14d} {d:>+10.2f}")

    print()
    if x_drifts:
        print(f"  x drift: mean {np.mean(x_drifts):+.2f}  std {np.std(x_drifts):.2f} px")
    if y_drifts:
        print(f"  y drift: mean {np.mean(y_drifts):+.2f}  std {np.std(y_drifts):.2f} px")

    out = os.path.join(HERE, "drift.json")
    with open(out, "w") as f:
        json.dump({
            "x_drifts_px": [round(d, 2) for d in x_drifts],
            "y_drifts_px": [round(d, 2) for d in y_drifts],
        }, f, indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
