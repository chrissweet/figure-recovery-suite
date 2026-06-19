#!/usr/bin/env python3
"""Phase 4 close-the-loop reconstruction for synthetic-r4-1/02-simple-bar.

Replots the extracted bar tops in the same chart-type, axis range, color,
title and legend layout as the source. Saved alongside the source image
for visual comparison.
"""
import csv
import matplotlib.pyplot as plt

CSV = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/synthetic-r4-1/02-simple-bar/data.csv"
OUT_PNG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/synthetic-r4-1/02-simple-bar/replot.png"

CATEGORIES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
COLOR = "#2CA02C"  # tab:green, matched from legend swatch pixel sample

def main():
    xs, ys = [], []
    with open(CSV) as f:
        r = csv.DictReader(f)
        for row in r:
            xs.append(int(row["x"]))
            ys.append(float(row["y"]))

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
    ax.bar(xs, ys, color=COLOR, edgecolor="black", linewidth=1.0,
           label="Throughput", width=0.8)
    ax.set_xticks(range(6))
    ax.set_xticklabels(CATEGORIES)
    ax.set_xlabel("Pipeline stage")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("Synthetic #2 — single-series vertical bars")
    ax.set_ylim(0, 25)
    ax.set_yticks([0, 5, 10, 15, 20, 25])
    ax.grid(True, axis="y", linewidth=0.5, alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=100)
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
