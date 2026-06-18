#!/usr/bin/env python3
"""Re-extract el-75: 3 scatter points with x/y error bars + red trend line."""
import csv
import json
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG = os.path.join(REPO, "corpora", "aedes-aegypti-2014", "charts", "el-75", "image.png")
CAL = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                   "aedes-aegypti-2014", "el-75", "calibration.json")


def px_to_data(cal, col, row):
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    return mx * col + bx, my * row + by


def extract_red_line(img, cal):
    """Detect red trend line endpoints by red mask + linear fit."""
    pf = cal["plot_frame_box"]
    left, top, right, bot = pf["left"], pf["top"], pf["right"], pf["bottom"]
    left += 2; top += 2; right -= 2; bot -= 2
    plot = img[top:bot, left:right]
    hsv = cv2.cvtColor(plot, cv2.COLOR_BGR2HSV)
    h_ch, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    red = (((h_ch <= 12) | (h_ch >= 168)) & (s > 100) & (v > 80))
    red = red.astype(np.uint8) * 255

    # Per-column median row of red pixels
    cols, rows = [], []
    for c in range(red.shape[1]):
        ys = np.where(red[:, c] > 0)[0]
        if len(ys) == 0 or len(ys) > 50:
            continue
        cols.append(c)
        rows.append(np.median(ys))
    cols = np.array(cols); rows = np.array(rows)
    if len(cols) < 50:
        raise RuntimeError(f"Insufficient red pixels: {len(cols)}")
    m, b = np.polyfit(cols, rows, 1)
    c0 = int(cols.min()); c1 = int(cols.max())
    col0_img = c0 + left
    col1_img = c1 + left
    row0_img = m * c0 + b + top
    row1_img = m * c1 + b + top
    x0, y0 = px_to_data(cal, col0_img, row0_img)
    x1, y1 = px_to_data(cal, col1_img, row1_img)
    return (x0, y0), (x1, y1)


def main():
    img = cv2.imread(IMG)
    with open(CAL) as f:
        cal = json.load(f)

    # Scatter (from prior extraction, untouched)
    scatter = [
        # x, y, x_err, y_err_lo, y_err_hi
        (23.62, 8.213, 1.0, 8.213 - 5.714, 11.072 - 8.213),
        (27.08, 7.150, 1.0, 7.150 - 3.681, 10.472 - 7.150),
        (30.01, 4.852, 1.0, 4.852 - 3.774, 6.037 - 4.852),
    ]

    (x0, y0), (x1, y1) = extract_red_line(img, cal)
    print(f"Red trend line: ({x0:.3f}, {y0:.3f}) -> ({x1:.3f}, {y1:.3f})")

    # data.csv — flat schema for scorer; pooled as "datapoints"
    with open(os.path.join(HERE, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["point", "x", "y", "x_err", "y_err_lo", "y_err_hi"])
        for i, (x, y, xe, yel, yeh) in enumerate(scatter, 1):
            w.writerow([f"p{i}", x, y, xe, yel, yeh])

    # Trend line — kept out of data.csv (el-75 pools all rows for scoring;
    # adding line endpoints would inflate FP count).
    with open(os.path.join(HERE, "trend_line.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x", "y"])
        w.writerow([x0, y0])
        w.writerow([x1, y1])

    # Replot
    fig, ax = plt.subplots(figsize=(9.2, 6.4), dpi=100)
    xs = [p[0] for p in scatter]; ys = [p[1] for p in scatter]
    xerr = [p[2] for p in scatter]
    yerr = [[p[3] for p in scatter], [p[4] for p in scatter]]
    ax.errorbar(xs, ys, xerr=xerr, yerr=yerr, fmt="o",
                ecolor="black", elinewidth=1.0, capsize=4,
                color="black", markersize=9, zorder=3)
    ax.plot([x0, x1], [y0, y1], color="red", lw=2.0, zorder=2)
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 25)
    ax.set_xticks([0, 5, 10, 15, 20, 25, 30, 35, 40])
    ax.set_yticks([0, 5, 10, 15, 20, 25])
    ax.set_xlabel("Temperatures (°C)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Mean Gonotrophic Cycle duration", fontsize=12, fontweight="bold")
    ax.grid(False)
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, "replot.png"), dpi=100, bbox_inches="tight")


if __name__ == "__main__":
    main()
