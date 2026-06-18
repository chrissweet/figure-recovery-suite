#!/usr/bin/env python3
"""Re-extract el-62: mirror lower error caps + snap x to categorical + long-form legend.

Bar tops and upper caps come from the prior extraction (already correct).
The fix: when the lower error cap is occluded by the bar fill, mirror the
upper-cap distance to produce symmetric error bars and tag each row with a
`mirrored_lower_cap` provenance flag.
"""
import csv
import os
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
PRIOR = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                     "aedes-aegypti-2014", "el-62", "data.csv")


def main():
    bars = []
    with open(PRIOR) as f:
        for row in csv.DictReader(f):
            series = row["series"]
            x_raw = float(row["temperature_C"])
            mean = float(row["mean_duration_days"])
            y_hi = float(row["y_hi"])
            # Snap x to nearest categorical tick
            x = min((24, 27, 30), key=lambda t: abs(t - x_raw))
            yerr = y_hi - mean
            bars.append((series, x, mean, yerr))

    # data.csv with mirrored lower cap
    with open(os.path.join(HERE, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y", "y_lo", "y_hi", "provenance"])
        for series, x, mean, yerr in bars:
            y_lo = mean - yerr
            y_hi = mean + yerr
            w.writerow([series, x, mean, round(y_lo, 3), round(y_hi, 3),
                        "mirrored_lower_cap"])

    # Replot
    fig, ax = plt.subplots(figsize=(11.0, 6.6), dpi=100)
    xs = [24, 27, 30]
    series_order = ["GC1", "GC2", "GC3"]
    colors = {"GC1": "#2c3e7a", "GC2": "#7a9438", "GC3": "#d9a3a3"}
    long_labels = {
        "GC1": "Mean duration of GC1",
        "GC2": "Mean duration of GC2",
        "GC3": "Mean duration of GC3",
    }
    rows_by = {(s, x): (m, e) for s, x, m, e in bars}
    width = 0.27
    for i, series in enumerate(series_order):
        means, errs, positions = [], [], []
        for j, x in enumerate(xs):
            if (series, x) in rows_by:
                m, e = rows_by[(series, x)]
                means.append(m); errs.append(e); positions.append(j + (i - 1) * width)
        ax.bar(positions, means, width=width, color=colors[series],
               edgecolor="black", linewidth=0.6,
               yerr=errs, error_kw={"ecolor": "black", "elinewidth": 0.9,
                                     "capsize": 4, "capthick": 0.9},
               label=long_labels[series])
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlabel("Temperatures (°C)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Duration of GC (days)", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 16)
    ax.set_yticks([0, 4, 8, 12, 16])
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.grid(False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, "replot.png"), dpi=100, bbox_inches="tight")


if __name__ == "__main__":
    main()
