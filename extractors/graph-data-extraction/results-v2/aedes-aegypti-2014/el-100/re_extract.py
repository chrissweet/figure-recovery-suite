#!/usr/bin/env python3
"""Re-extract el-100: 3 colored scatter series + 3 IF curves.

Scatter from prior extraction (filtered to drop the (0.6452, 0.248) phantom
green) plus three IF curves traced from the image by per-column color masks
(blue dashed, green solid, red dotted).
"""
import csv
import json
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG = os.path.join(REPO, "corpora", "aedes-aegypti-2014", "charts", "el-100", "image.png")
CAL = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                   "aedes-aegypti-2014", "el-100", "calibration.json")
PRIOR_DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                          "aedes-aegypti-2014", "el-100", "data.csv")


def col_to_x(cal, col):
    return cal["axis_calibration"]["x_axis"]["m"] * col + cal["axis_calibration"]["x_axis"]["b"]


def row_to_y(cal, row):
    return cal["axis_calibration"]["y_axis"]["m"] * row + cal["axis_calibration"]["y_axis"]["b"]


def x_to_col(cal, x):
    return int((x - cal["axis_calibration"]["x_axis"]["b"]) / cal["axis_calibration"]["x_axis"]["m"])


def trace_color_curve(img, cal, color_name):
    """For one color mask, per-column median row → curve points."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h_ch, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    if color_name == "blue":
        mask = (h_ch >= 100) & (h_ch <= 130) & (s > 80) & (v > 60)
    elif color_name == "green":
        mask = (h_ch >= 35) & (h_ch <= 80) & (s > 80) & (v > 60)
    elif color_name == "red":
        mask = (((h_ch <= 10) | (h_ch >= 170)) & (s > 80) & (v > 60))
    else:
        raise ValueError(color_name)

    # Use the full plot frame (data may extend past the data-extent box, e.g. the
    # 27 °C squares at y ≈ 24-25 sit above the labeled tick range y=20).
    pf = cal["plot_frame_box"]
    legend = cal["detection_internals"].get("legend_exclusion_used_for_frame")
    left = pf["left"] + 5; right = pf["right"] - 5
    top = pf["top"] + 5; bot = pf["bottom"] - 5
    mask_u8 = mask.astype(np.uint8)
    # Wide exclusion: legend swatches + labels run along the right margin past
    # the calibration legend box. Anything right of col 700 is legend territory.
    mask_u8[:, 700:] = 0

    rows_to_mask = load_prior_scatter()
    for series, x, y in rows_to_mask:
        col = x_to_col(cal, x)
        rrow = int((y - cal["axis_calibration"]["y_axis"]["b"]) /
                   cal["axis_calibration"]["y_axis"]["m"])
        cv2.circle(mask_u8, (col, rrow), 7, 0, -1)

    pts = []
    for c in range(left, right):
        ys = np.where(mask_u8[top:bot, c])[0]
        if len(ys) == 0 or len(ys) > 60:
            continue
        r = float(np.median(ys)) + top
        pts.append((col_to_x(cal, c), row_to_y(cal, r)))
    pts.sort()
    # Decimate
    out = pts[::6]
    if pts and out[-1] != pts[-1]:
        out.append(pts[-1])
    return out


def load_prior_scatter():
    rows = []
    with open(PRIOR_DATA) as f:
        rd = csv.DictReader(f)
        for r in rd:
            rows.append((r["series"], float(r["parity_rate"]),
                         float(r["life_expectancy_50pct"])))
    return rows


def main():
    img = cv2.imread(IMG)
    with open(CAL) as f:
        cal = json.load(f)

    # Filter scatter: drop the phantom green at (0.6452, 0.248).
    scatter = []
    for s, x, y in load_prior_scatter():
        if s == "27C" and abs(x - 0.6452) < 0.005 and y < 1.0:
            print(f"  dropping phantom: {s} ({x}, {y})")
            continue
        scatter.append((s, x, y))

    # Trace each curve by its color
    curves = {}
    for series, color in [("24C", "blue"), ("27C", "green"), ("30C", "red")]:
        curves[series] = trace_color_curve(img, cal, color)
        print(f"  {series} ({color}) curve: {len(curves[series])} points")

    # Write data.csv (scatter only — scoring ignores layer_idx)
    with open(os.path.join(HERE, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for s, x, y in scatter:
            w.writerow([s, x, y])

    # Curves to separate file (kept out of scorer)
    with open(os.path.join(HERE, "if_curves.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for series, pts in curves.items():
            for x, y in pts:
                w.writerow([f"IF_{series}", x, y])

    # Replot
    fig, ax = plt.subplots(figsize=(10.0, 6.6), dpi=100)
    style = {
        "24C": dict(color="#1f77ff", marker="o"),
        "27C": dict(color="#208c20", marker="s"),
        "30C": dict(color="#dc2828", marker="D"),
    }
    line_style = {
        "24C": dict(linestyle="--", color="#1f77ff", linewidth=1.6, label="IF for 24°C"),
        "27C": dict(linestyle="-", color="#208c20", linewidth=1.6, label="IF for 27°C"),
        "30C": dict(linestyle=":", color="#dc2828", linewidth=1.8, label="IF for 30°C"),
    }
    for series in ("24C", "27C", "30C"):
        xs = [p[1] for p in scatter if p[0] == series]
        ys = [p[2] for p in scatter if p[0] == series]
        ax.scatter(xs, ys, s=42, label=f"{series.replace('C', '')}°C",
                   edgecolors="black", linewidths=0.4, zorder=3,
                   **style[series])
        pts = curves.get(series, [])
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], zorder=2,
                    **line_style[series])

    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 28)
    ax.set_xticks(np.arange(0, 1.01, 0.1))
    ax.set_xticklabels([f"{v:.2f}".replace(".", ",") for v in np.arange(0, 1.01, 0.1)])
    ax.set_yticks([0, 10, 20])
    ax.set_yticklabels(["0,0", "10,0", "20,0"])
    ax.set_xlabel("Parity rate", fontsize=11, fontweight="bold")
    ax.set_title("Expectation of l'infective life for 50% of females",
                 fontsize=11, fontweight="bold", loc="left", x=0.02, y=0.94)
    ax.legend(loc="center right", fontsize=9, frameon=False,
              bbox_to_anchor=(1.32, 0.5))
    ax.grid(False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, "replot.png"), dpi=100, bbox_inches="tight")


if __name__ == "__main__":
    main()
