#!/usr/bin/env python3
"""Re-extract el-60-b: 3 scatter points + black trend line."""
import csv
import json
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG = os.path.join(REPO, "corpora", "aedes-aegypti-2014", "charts", "el-60-b", "image.png")
CAL = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                   "aedes-aegypti-2014", "el-60-b", "calibration.json")


def px_to_data(cal, col, row):
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    return mx * col + bx, my * row + by


def data_to_px(cal, x, y):
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    return int((x - bx) / mx), int((y - by) / my)


def extract_trend_line(img, cal):
    """Detect the black trend line: black mask, exclude markers, fit line."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Black: low saturation AND low value (V < 80, S can be anything)
    # But to avoid axis text we restrict to inside the plot frame.
    pf = cal["plot_frame_box"]
    left, top, right, bot = pf["left"], pf["top"], pf["right"], pf["bottom"]
    # Use the data extent box so we exclude frame border / axis labels.
    de = cal["data_extent_box"]
    left = max(left + 2, de["left"] + 2)
    right = min(right - 2, de["right"] - 2)
    top = max(top + 2, de["top"] + 2)
    bot = min(bot - 2, de["bottom"] - 2)

    plot = img[top:bot, left:right]
    plot_hsv = hsv[top:bot, left:right]

    # Black mask: low value, low saturation
    v = plot_hsv[:, :, 2]
    s = plot_hsv[:, :, 1]
    black = (v < 90) & (s < 80)

    # Remove the three colored markers by also masking out their colored pixels'
    # neighborhoods. We approximate: detect blue, green, red, then dilate.
    h_ch = plot_hsv[:, :, 0]
    blue = ((h_ch >= 100) & (h_ch <= 130) & (s > 80) & (v > 60))
    green = ((h_ch >= 35) & (h_ch <= 85) & (s > 80) & (v > 60))
    red = (((h_ch <= 10) | (h_ch >= 170)) & (s > 80) & (v > 60))
    colored = (blue | green | red).astype(np.uint8) * 255
    colored = cv2.dilate(colored, np.ones((9, 9), np.uint8), iterations=1)
    black = black & (colored == 0)

    # Skeletonize so each line column has a single y.
    bm = black.astype(np.uint8) * 255
    # Open with thin kernel to drop noise dots
    bm = cv2.morphologyEx(bm, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    # For each column, take the median row of black pixels (robust to noise).
    cols = []
    rows = []
    for c in range(bm.shape[1]):
        ys = np.where(bm[:, c] > 0)[0]
        if len(ys) == 0:
            continue
        # Skip columns with way too many black pixels (likely text/axis label).
        if len(ys) > 30:
            continue
        cols.append(c)
        rows.append(np.median(ys))
    cols = np.array(cols)
    rows = np.array(rows)

    if len(cols) < 20:
        raise RuntimeError(f"Not enough black-line pixels found: {len(cols)}")

    # Linear fit
    m, b = np.polyfit(cols, rows, 1)
    # Restrict to the visible line span (where actual pixels exist)
    c0 = int(cols.min())
    c1 = int(cols.max())
    r0 = m * c0 + b
    r1 = m * c1 + b
    # Back to image coords
    col0_img = c0 + left
    col1_img = c1 + left
    row0_img = r0 + top
    row1_img = r1 + top
    x0, y0 = px_to_data(cal, col0_img, row0_img)
    x1, y1 = px_to_data(cal, col1_img, row1_img)
    return (x0, y0), (x1, y1)


def main():
    img = cv2.imread(IMG)
    with open(CAL) as f:
        cal = json.load(f)

    # Scatter: snap to integer x. y from original CSV but recomputed sub-pixel.
    # Use existing extracted values from results, but snap x.
    scatter = [
        ("Series 1", 24.0, 0.3592, "circle", "#0000FF"),
        ("Series 2", 27.0, 0.7078, "square", "#008000"),
        ("Series 3", 30.0, 0.6429, "diamond", "#FF0000"),
    ]

    (x0, y0), (x1, y1) = extract_trend_line(img, cal)
    print(f"Trend line endpoints: ({x0:.3f}, {y0:.3f}) -> ({x1:.3f}, {y1:.3f})")

    # Write data.csv with scatter (in extractor's flat schema) — scoring reads x,y,series.
    data_path = os.path.join(HERE, "data.csv")
    with open(data_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for series, x, y, _mt, _c in scatter:
            w.writerow([f"{int(x)}C", x, y])

    # Write trend line for replot rendering, kept out of data.csv to avoid scoring
    # contamination.
    line_path = os.path.join(HERE, "trend_line.csv")
    with open(line_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x", "y"])
        w.writerow([x0, y0])
        w.writerow([x1, y1])

    # Replot
    fig, ax = plt.subplots(figsize=(8.7, 5.6), dpi=100)
    for series, x, y, mt, color in scatter:
        markers = {"circle": "o", "square": "s", "diamond": "D"}
        ax.scatter([x], [y], marker=markers[mt], c=color,
                   s=140, edgecolors="black", linewidths=0.5, zorder=3)
    # Trend line (extends across full x range to mimic original)
    ax.plot([x0, x1], [y0, y1], color="black", lw=1.5, zorder=2)

    ax.set_xlim(10, 35)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Temperatures (°C)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Maximum Parity Rate", fontsize=12, fontweight="bold")
    ax.set_xticks([10, 15, 20, 25, 30, 35])
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0", "0,2", "0,4", "0,6", "0,8", "1"])
    # No legend — original has no legend region
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_color("#999")
    plt.tight_layout()
    out = os.path.join(HERE, "replot.png")
    plt.savefig(out, dpi=100, bbox_inches="tight")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
