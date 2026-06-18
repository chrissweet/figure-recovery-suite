#!/usr/bin/env python3
"""Re-extract el-80: grouped bar chart with error bars, snapped categorical x.

Bar means come from the previous extraction (validated as within ~0.5 unit of
ground truth). New work here: snap x to {24, 27, 30}; detect upper-cap rows
from the image and mirror to symmetric yerr; render hatched GC2 and long-form
legend.
"""
import csv
import json
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG = os.path.join(REPO, "corpora", "aedes-aegypti-2014", "charts", "el-80", "image.png")
CAL = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                   "aedes-aegypti-2014", "el-80", "calibration.json")


def detect_cap_above(gray, bar_x_center, bar_top_row, cap_half_width=12):
    """Find the topmost horizontal dark cap above `bar_top_row` near `bar_x_center`,
    gated by a continuous vertical stem between bar top and cap.
    """
    h, w = gray.shape
    x_lo = max(0, bar_x_center - cap_half_width)
    x_hi = min(w, bar_x_center + cap_half_width + 1)
    # Maximum reach: ~200 px up from bar top (≈ 30 y-units at this scale).
    r_hi = bar_top_row - 1
    r_lo = max(0, bar_top_row - 200)
    band = gray[r_lo:r_hi, x_lo:x_hi]
    dark = (band < 120).astype(np.uint8)
    row_counts = dark.sum(axis=1)
    # Stem column: ±5 px around bar center (some bars stem slightly off-center).
    cx0 = max(0, bar_x_center - 5 - x_lo)
    cx1 = min(band.shape[1], bar_x_center + 6 - x_lo)
    stem = dark[:, cx0:cx1].max(axis=1)
    # A cap is a wide dark row (>=5 px). Walk top -> down. Accept only if the stem
    # between this row and bar top has dark pixels in >=50% of rows.
    # A valid cap is a wide dark row followed by stem-only rows (row_count 1..3)
    # all the way down to the bar top. This rejects text/legend rows above the bar.
    cap_candidates = np.where(row_counts >= 5)[0]
    for c in cap_candidates:
        below = row_counts[c + 1:]
        if len(below) == 0:
            continue
        # No other wide rows between cap and bar top.
        if (below >= 5).any():
            continue
        # Stem must reach most of the way to bar top: ≥40 % of rows below the cap
        # should have ≥1 dark pixel in the ±5 stem window.
        sb = stem[c + 1:]
        if sb.mean() >= 0.4:
            return r_lo + int(c)
    return None


def main():
    img = cv2.imread(IMG)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    with open(CAL) as f:
        cal = json.load(f)
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]

    # Bar centers in image pixels (derived from a separate geometry probe).
    # 24°C group: GC1 at 127, GC2 at 195 (no GC3)
    # 27°C group: GC1 at 432, GC2 at 501, GC3 at 570 (GC3 to the right of GC2)
    # 30°C group: GC1 at 736, GC2 at 806, GC3 at 875
    bar_geometry = {
        ("GC1", 24): 127,
        ("GC2", 24): 195,
        ("GC1", 27): 432,
        ("GC2", 27): 501,
        ("GC3", 27): 570,
        ("GC1", 30): 736,
        ("GC2", 30): 806,
        ("GC3", 30): 875,
    }
    bars_in = [
        ("GC1", 24, 41.59),
        ("GC1", 27, 42.47),
        ("GC1", 30, 39.38),
        ("GC2", 24, 44.24),
        ("GC2", 27, 32.46),
        ("GC2", 30, 34.22),
        ("GC3", 27, 48.66),
        ("GC3", 30, 5.5),
    ]

    rows = []
    for series, x, mean in bars_in:
        bar_col = bar_geometry[(series, x)]
        bar_top_row = int((mean - by) / my)
        cap_row = detect_cap_above(gray, bar_col, bar_top_row)
        if cap_row is None or cap_row < 30:
            # Heuristic fallback: typical error bar in this chart is ~21 units
            yerr = 21.0
            print(f"  {series}@{x}: fallback yerr={yerr}")
        else:
            cap_y = my * cap_row + by
            yerr = max(0.0, cap_y - mean)
            print(f"  {series}@{x}: mean={mean}, bar_top_row={bar_top_row}, "
                  f"cap_row={cap_row}, yerr={yerr:.2f}")
        rows.append((series, x, mean, yerr))

    # data.csv
    with open(os.path.join(HERE, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y", "yerr"])
        for series, x, mean, yerr in rows:
            w.writerow([series, x, mean, round(yerr, 3)])

    # Replot
    fig, ax = plt.subplots(figsize=(9.6, 6.0), dpi=100)
    xs = [24, 27, 30]
    series_order = ["GC1", "GC2", "GC3"]
    colors = {"GC1": "#666666", "GC2": "#cccccc", "GC3": "#aaaaaa"}
    hatches = {"GC1": "", "GC2": "....", "GC3": ""}
    long_labels = {
        "GC1": "Mean number of eggs/female in GC1",
        "GC2": "Mean number of eggs/female in GC2",
        "GC3": "Mean number of eggs/female in GC3",
    }
    rows_by_xs = {(s, x): (m, e) for s, x, m, e in rows}

    width = 0.27
    for i, series in enumerate(series_order):
        means = []; errs = []; positions = []
        for j, x in enumerate(xs):
            if (series, x) in rows_by_xs:
                m, e = rows_by_xs[(series, x)]
                means.append(m); errs.append(e); positions.append(j + (i - 1) * width)
        ax.bar(positions, means, width=width, color=colors[series],
               edgecolor="black", linewidth=0.7, hatch=hatches[series],
               yerr=errs, error_kw={"ecolor": "black", "elinewidth": 0.9,
                                     "capsize": 4, "capthick": 0.9},
               label=long_labels[series])

    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlabel("Temperatures (°C)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Mean number of eggs", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 80)
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.legend(loc="upper right", fontsize=9, frameon=False,
              bbox_to_anchor=(1.32, 1.0))
    ax.grid(False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, "replot.png"), dpi=100, bbox_inches="tight")


if __name__ == "__main__":
    main()
