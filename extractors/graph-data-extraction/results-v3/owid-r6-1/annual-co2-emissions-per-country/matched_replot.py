"""Re-plot extracted data and overlay vs source image for Phase-4 verification.

Produces:
  replot.png         : standalone re-render of the seven series
  overlay.png        : side-by-side source vs re-plot
"""
import csv
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

HERE = Path(__file__).parent
SRC_IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/annual-co2-emissions-per-country/image.png"

SERIES_COLOR = {
    "China":           "#062e5f",
    "United States":   "#a26f46",
    "India":           "#883039",
    "Germany":         "#b13507",
    "Brazil":          "#6d3e91",
    "United Kingdom":  "#4c6a9c",
    "France":          "#2c8465",
}

def load_csv():
    series = {}
    with open(HERE / "data.csv") as f:
        for row in csv.DictReader(f):
            s = row["series"]
            series.setdefault(s, []).append((float(row["x"]), float(row["y"])))
    # Sort each series by x for clean line plotting
    for s in series:
        series[s] = sorted(series[s], key=lambda p: p[0])
    return series

def make_replot(series, out_path):
    fig, ax = plt.subplots(figsize=(8.5, 6.0), dpi=100)
    for s, pts in series.items():
        x = np.array([p[0] for p in pts])
        y = np.array([p[1] for p in pts]) / 1e9
        ax.plot(x, y, color=SERIES_COLOR[s], linewidth=1.4, label=s)
        # Place label at endpoint
        ax.annotate(s, xy=(x[-1], y[-1]), xytext=(4, 0),
                    textcoords="offset points", color=SERIES_COLOR[s],
                    fontsize=8, va="center")
    ax.set_xlim(1750, 2030)
    ax.set_ylim(0, 13)
    ax.set_ylabel("Annual CO₂ emissions (billion t)")
    ax.set_title("Annual CO₂ emissions  [re-plot of extracted data]")
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)

def make_overlay(out_path):
    src = mpimg.imread(SRC_IMG)
    rep = mpimg.imread(HERE / "replot.png")
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    axes[0].imshow(src); axes[0].set_title("source"); axes[0].axis("off")
    axes[1].imshow(rep); axes[1].set_title("re-plot"); axes[1].axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)

def main():
    series = load_csv()
    make_replot(series, HERE / "replot.png")
    make_overlay(HERE / "overlay.png")
    print("Re-plot written; counts per series:")
    for s, pts in series.items():
        x_first, x_last = pts[0][0], pts[-1][0]
        y_last = pts[-1][1] / 1e9
        print(f"  {s:18s} n={len(pts):4d}  x=[{x_first:.1f}..{x_last:.1f}]  y(last)={y_last:.2f}B")

if __name__ == "__main__":
    main()
