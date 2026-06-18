#!/usr/bin/env python3
"""Re-extract el-100: relaxed blue marker filter + 3 IF curves + drop phantom green.

Two-pass blue extraction:
  1. erode kernel 3x3 → big well-separated markers (the trail at low x).
  2. erode kernel 2x2 on the residual + AR ≤ 1.4 → small markers buried in the
     dense column on the dashed blue fit line.
Candidates within 4 px of each other are merged to a single centroid.
Markers are restricted to x ≤ 0.40 (the visible 24 °C scatter span); beyond
that, only the dashed fit line continues so anything outside is a fragment.

27 °C and 30 °C scatter preserved from the prior extraction (they were not
flagged as undercount in the audit). Three IF curves are traced as before.
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


def y_to_row(cal, y):
    return int((y - cal["axis_calibration"]["y_axis"]["b"]) / cal["axis_calibration"]["y_axis"]["m"])


def extract_blue_markers(img, cal):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    blue = (h >= 100) & (h <= 130) & (s > 80) & (v > 60)
    bm = blue.astype(np.uint8) * 255
    bm[:, 700:] = 0  # legend swatch exclusion
    # Pass 1: aggressive erode for well-separated markers
    ek3 = cv2.erode(bm, np.ones((3, 3), np.uint8), iterations=1)
    n1, _, st1, c1 = cv2.connectedComponentsWithStats(ek3, 8)
    cands = []
    for i in range(1, n1):
        s_ = st1[i]
        w_, h_, a = s_[cv2.CC_STAT_WIDTH], s_[cv2.CC_STAT_HEIGHT], s_[cv2.CC_STAT_AREA]
        ar = max(w_, h_) / max(1, min(w_, h_))
        if a < 8 or ar > 2.0:
            continue
        cands.append((c1[i][0], c1[i][1], a))
    # Pass 2: residual with smaller erode for dash-buried markers
    claimed = np.zeros_like(bm)
    for cx_, cy_, _ in cands:
        cv2.circle(claimed, (int(cx_), int(cy_)), 6, 255, -1)
    ek2 = cv2.erode(bm, np.ones((2, 2), np.uint8), iterations=1)
    resid = cv2.bitwise_and(ek2, cv2.bitwise_not(claimed))
    n2, _, st2, c2 = cv2.connectedComponentsWithStats(resid, 8)
    for i in range(1, n2):
        s_ = st2[i]
        w_, h_, a = s_[cv2.CC_STAT_WIDTH], s_[cv2.CC_STAT_HEIGHT], s_[cv2.CC_STAT_AREA]
        ar = max(w_, h_) / max(1, min(w_, h_))
        if a < 6 or ar > 1.4:
            continue
        cands.append((c2[i][0], c2[i][1], a))

    # Dedup: if two centroids are within 4 px, keep the larger area one.
    cands.sort(key=lambda t: -t[2])
    kept = []
    for cx_, cy_, a in cands:
        if any(((cx_ - kx) ** 2 + (cy_ - ky) ** 2) ** 0.5 < 4 for kx, ky, _ in kept):
            continue
        kept.append((cx_, cy_, a))

    # Restrict to x ≤ 0.40 (24 °C scatter span; dashed line continues past).
    out = []
    for cx_, cy_, a in kept:
        x = col_to_x(cal, cx_)
        if x > 0.40:
            continue
        y = row_to_y(cal, cy_)
        out.append((x, y))
    out.sort()
    return out


def trace_color_curve(img, cal, color_name, marker_positions):
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
    pf = cal["plot_frame_box"]
    left = pf["left"] + 5; right = pf["right"] - 5
    top = pf["top"] + 5; bot = pf["bottom"] - 5
    mu = mask.astype(np.uint8)
    mu[:, 700:] = 0
    for x, y in marker_positions:
        cv2.circle(mu, (x_to_col(cal, x), y_to_row(cal, y)), 7, 0, -1)
    pts = []
    for c in range(left, right):
        ys = np.where(mu[top:bot, c])[0]
        if len(ys) == 0 or len(ys) > 60:
            continue
        pts.append((col_to_x(cal, c), row_to_y(cal, float(np.median(ys)) + top)))
    pts.sort()
    out = pts[::6]
    if pts and out[-1] != pts[-1]:
        out.append(pts[-1])
    return out


def load_prior_scatter(series_filter=None):
    rows = []
    with open(PRIOR_DATA) as f:
        for r in csv.DictReader(f):
            if series_filter and r["series"] not in series_filter:
                continue
            rows.append((r["series"], float(r["parity_rate"]),
                         float(r["life_expectancy_50pct"])))
    return rows


def main():
    img = cv2.imread(IMG)
    with open(CAL) as f:
        cal = json.load(f)

    # Blue markers (re-extracted with relaxed filter)
    blue_pts = extract_blue_markers(img, cal)
    print(f"  24C (blue) markers re-extracted: {len(blue_pts)}")

    # 27 °C and 30 °C: preserve from prior, drop phantom green at (0.6452, 0.248)
    other = []
    for s, x, y in load_prior_scatter(series_filter=("27C", "30C")):
        if s == "27C" and abs(x - 0.6452) < 0.005 and y < 1.0:
            print(f"  dropping phantom: {s} ({x}, {y})")
            continue
        other.append((s, x, y))

    scatter = [("24C", x, y) for x, y in blue_pts] + other

    # Curve tracing uses all marker positions to mask out
    all_marker_pos = [(x, y) for s, x, y in scatter]
    curves = {}
    for series, color in [("24C", "blue"), ("27C", "green"), ("30C", "red")]:
        curves[series] = trace_color_curve(img, cal, color, all_marker_pos)
        print(f"  {series} ({color}) curve: {len(curves[series])} points")

    with open(os.path.join(HERE, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for s, x, y in scatter:
            w.writerow([s, x, y])

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
                   edgecolors="black", linewidths=0.4, zorder=3, **style[series])
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
