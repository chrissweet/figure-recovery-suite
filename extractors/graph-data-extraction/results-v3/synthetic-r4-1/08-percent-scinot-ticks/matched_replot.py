"""Matched-frame re-plot for 08-percent-scinot-ticks.

Reads data.csv, renders the same line chart with percent x-ticks and a 1e7
scientific-notation y-axis offset, saves replot.png.
"""
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

HERE = Path(__file__).resolve().parent

xs, ys = [], []
with open(HERE / "data.csv") as f:
    r = csv.DictReader(f)
    for row in r:
        xs.append(float(row["x"]))
        ys.append(float(row["y"]))

fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=100)
ax.plot(xs, ys, marker="o", linestyle="-", color="#1f77b4", label="Throughput")

# X axis: percent ticks at 0, 20, 40, 60, 80, 100 (fractions 0..1)
ax.set_xlim(0.0, 1.0)
ax.xaxis.set_major_locator(mticker.FixedLocator([0.0, 0.2, 0.4, 0.6, 0.8, 1.0]))
ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
ax.set_xlabel("Saturation fraction")

# Y axis: real cps values with sci-notation offset (1e7)
ax.set_ylim(0.0, 1.0e7)
ax.yaxis.set_major_locator(mticker.FixedLocator([0.0, 2e6, 4e6, 6e6, 8e6, 1e7]))
ax.ticklabel_format(style="sci", axis="y", scilimits=(7, 7))
ax.set_ylabel("Photon yield (cps)")

ax.set_title("Synthetic #8 — percent x ticks + sci-notation y ticks")
ax.grid(True, linewidth=0.5, alpha=0.4)
ax.legend(loc="upper left")

fig.tight_layout()
fig.savefig(HERE / "replot.png", dpi=100)
print(f"wrote {HERE/'replot.png'}")
