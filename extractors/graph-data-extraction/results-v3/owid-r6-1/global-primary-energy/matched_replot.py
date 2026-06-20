#!/usr/bin/env python3
"""Reproduce the recovered chart from data.csv as a matched stacked-area replot.

Reads the per-source raw values per year (approach b) and renders a stacked-area
chart with the same series ordering and approximate colors as the source.
"""

import csv
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

HERE = Path(__file__).resolve().parent
DATA_CSV = HERE / "data.csv"
OUT_PNG = HERE / "replot.png"

# Series order (bottom-to-top) and colors, matching the source figure legend.
SERIES_ORDER = [
    ("Traditional biomass", "#a9535d"),
    ("Coal",                "#9a9b9b"),
    ("Oil",                 "#5c80ba"),
    ("Gas",                 "#b875c8"),
    ("Nuclear",             "#d55153"),
    ("Hydropower",          "#90c0c4"),
    ("Wind",                "#6db486"),
    ("Solar",               "#c9a831"),
    ("Other renewables",    "#52a7ae"),
    ("Modern biofuels",     "#b0926e"),
]


def main():
    rows = []
    with DATA_CSV.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # Pivot: years x series
    years_sorted = sorted({int(r["x"]) for r in rows})
    by_series = {name: {} for name, _ in SERIES_ORDER}
    for r in rows:
        s = r["series"]
        if s in by_series:
            by_series[s][int(r["x"])] = float(r["y"])

    years_arr = np.array(years_sorted)
    stack_arrays = [
        np.array([by_series[n].get(y, 0.0) for y in years_sorted])
        for n, _ in SERIES_ORDER
    ]
    colors = [c for _, c in SERIES_ORDER]
    labels = [n for n, _ in SERIES_ORDER]

    fig, ax = plt.subplots(figsize=(8.5, 6.0), dpi=110)
    ax.stackplot(years_arr, *stack_arrays, labels=labels, colors=colors)
    ax.set_xlim(1800, 2024)
    ax.set_ylim(0, 180000)
    ax.set_xlabel("Year")
    ax.set_ylabel("TWh")
    ax.set_title("Global direct primary energy consumption (recovered)")
    ax.legend(loc="upper left", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=110)
    plt.close(fig)
    print(f"wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
