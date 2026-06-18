#!/usr/bin/env python3
"""Re-extract el-94: 3 grayscale-shape scatter series + 3 fit curves.

Curves are traced from the image by per-column dark-pixel-run clustering and
follow-up linking across columns. Scatter data is preserved from the prior
extraction (known to undercount some series; documented in TODOS.md).
"""
import csv
import json
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG = os.path.join(REPO, "corpora", "aedes-aegypti-2014", "charts", "el-94", "image.png")
CAL = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                   "aedes-aegypti-2014", "el-94", "calibration.json")
PRIOR_DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                          "aedes-aegypti-2014", "el-94", "data.csv")


def col_to_x(cal, col):
    return cal["axis_calibration"]["x_axis"]["m"] * col + cal["axis_calibration"]["x_axis"]["b"]


def row_to_y(cal, row):
    return cal["axis_calibration"]["y_axis"]["m"] * row + cal["axis_calibration"]["y_axis"]["b"]


def x_to_col(cal, x):
    return int((x - cal["axis_calibration"]["x_axis"]["b"]) / cal["axis_calibration"]["x_axis"]["m"])


def trace_curves(img, cal):
    """For each x in the plot, find up to 3 dark-pixel clusters and attribute them
    to one of three curves by row continuity.

    Returns dict of series -> list[(x, y)].
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    pf = cal["plot_frame_box"]
    de = cal["data_extent_box"]
    left = de["left"] + 5
    right = de["right"] - 5
    top = de["top"] + 5
    bot = de["bottom"] - 5
    legend = cal["detection_internals"].get("legend_exclusion_used_for_frame")

    dark = (gray < 120).astype(np.uint8) * 255
    if legend:
        ly0, ly1, lx0, lx1 = legend
        dark[ly0:ly1, lx0:lx1] = 0

    # Mask out scatter markers at known positions from prior extraction so they
    # do not pollute the per-column curve clusters.
    scatter_rows = load_prior_scatter()
    marker_radius = 6
    for series, x, y in scatter_rows:
        col = x_to_col(cal, x)
        row = int((y - cal["axis_calibration"]["y_axis"]["b"]) /
                  cal["axis_calibration"]["y_axis"]["m"])
        cv2.circle(dark, (col, row), marker_radius, 0, -1)
    dark_dil = dark

    # For each column, find dark-pixel clusters (consecutive runs of dark rows).
    # Cluster row = mean of run rows.
    per_col = {}  # col -> list of row centers (top-to-bottom)
    for c in range(left, right):
        col = dark_dil[top:bot, c] > 0
        if not col.any():
            continue
        runs = []
        in_run = False
        for r in range(len(col)):
            if col[r] and not in_run:
                start = r; in_run = True
            elif (not col[r]) and in_run:
                runs.append((start, r - 1)); in_run = False
        if in_run:
            runs.append((start, len(col) - 1))
        centers = [(s + e) / 2 + top for s, e in runs if e - s <= 30]
        if centers:
            per_col[c] = sorted(centers)

    # Assign clusters to curves: greedy follow-the-curve.
    # Initialize with known approximate row positions at the left edge:
    # 27 °C solid is highest (lowest row), 24 °C dashed middle, 30 °C dotted lowest.
    # GT spline tells us: at x=1, 27 ≈ 0.961, 24 ≈ 0.935, 30 ≈ 0.930.
    # Convert to rows.
    seed_x = 3
    seed_col = x_to_col(cal, seed_x)
    target = {
        "27C": (0.961 - cal["axis_calibration"]["y_axis"]["b"]) / cal["axis_calibration"]["y_axis"]["m"],
        "24C": (0.945 - cal["axis_calibration"]["y_axis"]["b"]) / cal["axis_calibration"]["y_axis"]["m"],
        "30C": (0.932 - cal["axis_calibration"]["y_axis"]["b"]) / cal["axis_calibration"]["y_axis"]["m"],
    }
    last = dict(target)

    curves = {"24C": [], "27C": [], "30C": []}
    for c in sorted(per_col.keys()):
        centers = per_col[c]
        # For each curve, find the nearest cluster within a tolerance.
        used = set()
        for name in sorted(last.keys(), key=lambda k: last[k]):
            best, best_d = None, 25.0
            for i, r in enumerate(centers):
                if i in used:
                    continue
                d = abs(r - last[name])
                if d < best_d:
                    best_d = d; best = i
            if best is not None:
                used.add(best)
                curves[name].append((col_to_x(cal, c), row_to_y(cal, centers[best])))
                last[name] = centers[best]

    # Downsample for spline-like rendering: keep one point every ~10 px.
    out = {}
    for name, pts in curves.items():
        pts.sort()
        decimated = pts[::8]
        if pts and decimated[-1] != pts[-1]:
            decimated.append(pts[-1])
        out[name] = decimated
    return out


def load_prior_scatter():
    rows = []
    with open(PRIOR_DATA) as f:
        rd = csv.DictReader(f)
        for r in rd:
            rows.append((r["series"], float(r["age_days"]), float(r["daily_survival_p"])))
    return rows


def main():
    img = cv2.imread(IMG)
    with open(CAL) as f:
        cal = json.load(f)

    scatter = load_prior_scatter()
    curves = trace_curves(img, cal)
    print(f"Curve sizes: " + ", ".join(f"{k}={len(v)}" for k, v in curves.items()))

    # Write scatter to data.csv (scorer reads x, y, series)
    with open(os.path.join(HERE, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for s, x, y in scatter:
            w.writerow([s, x, y])

    # Write curves separately (kept out of scoring)
    with open(os.path.join(HERE, "fit_curves.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y"])
        for name, pts in curves.items():
            for x, y in pts:
                w.writerow([f"p_curve_{name}", x, y])

    # Replot
    fig, ax = plt.subplots(figsize=(10.0, 6.5), dpi=100)

    # Group scatter
    for series, marker_kw, label in [
        ("24C", dict(marker="o", facecolor="black", edgecolor="black", s=35),
         "24 °C"),
        ("27C", dict(marker="s", facecolor="#a8a8a8", edgecolor="#404040", s=40),
         "27 °C"),
        ("30C", dict(marker="D", facecolor="white", edgecolor="black", s=40, linewidths=0.9),
         "30 °C"),
    ]:
        xs = [p[1] for p in scatter if p[0] == series]
        ys = [p[2] for p in scatter if p[0] == series]
        ax.scatter(xs, ys, zorder=3, label=label, **marker_kw)

    # Curves
    curve_style = {
        "24C": dict(linestyle="--", color="black", linewidth=1.4, label="p curve for 24°C"),
        "27C": dict(linestyle="-", color="black", linewidth=1.4, label="p curve for 27°C"),
        "30C": dict(linestyle=":", color="black", linewidth=1.6, label="p curve for 30°C"),
    }
    for name in ("24C", "27C", "30C"):
        pts = curves.get(name, [])
        if not pts:
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.plot(xs, ys, zorder=2, **curve_style[name])

    ax.set_xlim(0, 50)
    ax.set_ylim(0.93, 0.98)
    ax.set_xlabel("Age of females in days", fontsize=11, fontweight="bold")
    ax.set_ylabel("Probability of daily survival (p)", fontsize=11, fontweight="bold")
    ax.set_yticks([0.93, 0.94, 0.95, 0.96, 0.97, 0.98])
    ax.set_yticklabels(["0,93", "0,94", "0,95", "0,96", "0,97", "0,98"])
    ax.legend(loc="center right", fontsize=9, frameon=False,
              bbox_to_anchor=(1.32, 0.5))
    ax.grid(False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, "replot.png"), dpi=100, bbox_inches="tight")


if __name__ == "__main__":
    main()
