#!/usr/bin/env python3
"""
matched_replot.py — Phase 4 reconstruction for synthetic-r4-1/01-linear-scatter.

Reads the extracted data.csv and re-renders the chart in a matplotlib frame
matched to the source image: same title, axis labels, ticks, ranges, default
matplotlib palette (C0/C1/C2), and marker shapes (circle/square/diamond).

Usage:
    python3 matched_replot.py [output.png]
"""
import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CSV = HERE / "data.csv"

SERIES_STYLE = {
    "Series A": {"color": "C0", "marker": "o"},
    "Series B": {"color": "C1", "marker": "s"},
    "Series C": {"color": "C2", "marker": "D"},
}


def load() -> dict[str, list[tuple[float, float]]]:
    pts: dict[str, list[tuple[float, float]]] = {}
    with CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            s = row["series"]
            pts.setdefault(s, []).append((float(row["x"]), float(row["y"])))
    return pts


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "replot.png"
    pts = load()

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name, style in SERIES_STYLE.items():
        if name not in pts:
            continue
        xs = [p[0] for p in pts[name]]
        ys = [p[1] for p in pts[name]]
        ax.scatter(
            xs,
            ys,
            c=style["color"],
            marker=style["marker"],
            label=name,
            edgecolors="black",
            linewidths=0.5,
            s=50,
        )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Concentration (mol/L)")
    ax.set_title("Synthetic #01 — linear scatter")
    ax.set_xlim(-0.6, 10.6)
    ax.set_ylim(0, 12)
    ax.set_xticks([0, 2, 4, 6, 8, 10])
    ax.set_yticks([0, 2, 4, 6, 8, 10, 12])
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(out, dpi=100)
    plt.close()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
