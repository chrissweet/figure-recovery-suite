#!/usr/bin/env python3
"""Re-plot the extracted stacked-bar data and save replot.png.

This is the Phase-4 close-the-loop test for chart 05-stacked-bar.
Re-rendered with matplotlib to roughly match the source figure.
"""
import csv
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV  = HERE / "data.csv"

categories = ["Web", "API", "Worker", "Cron", "DB"]
segments   = ["CPU", "Memory", "IO_Wait"]
colors     = {"CPU": "#1F77B4", "Memory": "#FF7F0E", "IO_Wait": "#2CA02C"}
labels     = {"CPU": "CPU",     "Memory": "Memory",  "IO_Wait": "IO Wait"}

# Load value rows
values = {seg: {cat: None for cat in categories} for seg in segments}
with CSV.open() as f:
    reader = csv.DictReader(f)
    for r in reader:
        s = r["series"]
        if s.endswith("_value"):
            seg = s[:-len("_value")]
            values[seg][r["category"]] = float(r["y"])

x = np.arange(len(categories))
fig, ax = plt.subplots(figsize=(7, 4.5))
bottom = np.zeros(len(categories))
for seg in segments:
    heights = np.array([values[seg][c] for c in categories])
    ax.bar(x, heights, bottom=bottom, width=0.6,
           color=colors[seg], edgecolor="black", linewidth=0.8,
           label=labels[seg])
    bottom = bottom + heights

ax.set_xticks(x)
ax.set_xticklabels(categories)
ax.set_xlabel("Service")
ax.set_ylabel("Utilisation (% of node)")
ax.set_title("Synthetic #5 — stacked bars")
ax.set_ylim(0, 100)
ax.set_yticks([0, 20, 40, 60, 80, 100])
ax.yaxis.grid(True, color="#DDDDDD", linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(loc="upper left")

fig.tight_layout()
out = HERE / "replot.png"
fig.savefig(out, dpi=100)
print("saved", out)
