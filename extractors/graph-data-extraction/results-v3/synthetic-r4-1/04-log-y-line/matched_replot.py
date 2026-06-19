#!/usr/bin/env python3
"""Phase-4 close-the-loop reconstruction of synthetic-r4-1 / 04-log-y-line.

Loads the extracted data.csv, plots it with matplotlib using a log10
y-axis matching the source figure, and saves replot.png next to this file.
"""
from pathlib import Path
import csv
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
CSV = HERE / "data.csv"

series = {}
with CSV.open() as f:
    r = csv.DictReader(f)
    for row in r:
        s = row["series"]
        series.setdefault(s, ([], []))
        series[s][0].append(float(row["x"]))
        series[s][1].append(float(row["y"]))

fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
styles = {
    "Exponential": dict(color="#d62728", linestyle="-",
                        label="Exponential: 100 e^(-0.5 t)"),
    "Power law":   dict(color="#9467bd", linestyle="--",
                        label="Power law: 500 / t^1.6"),
}
for name, (xs, ys) in series.items():
    st = styles.get(name, {})
    ax.plot(xs, ys, linewidth=2, **st)

ax.set_yscale("log")
ax.set_xlim(0, 10)
ax.set_ylim(1e-1, 1e3)
ax.set_xlabel("Time t (s)")
ax.set_ylabel("Signal magnitude (log scale)")
ax.set_title("Synthetic #04 — log-y line plot")
ax.grid(True, which="both", linestyle="-", linewidth=0.5, alpha=0.3)
ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(HERE / "replot.png", dpi=100)
print(f"wrote {HERE / 'replot.png'}")
