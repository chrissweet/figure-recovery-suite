#!/usr/bin/env python3
"""Re-plot the extracted Life-expectancy-vs-GDP scatter using calibration
and data.csv, save replot.png next to this script. Used as the Phase-4
close-the-loop visual check for the owid-r6-1 chart.

Matches the source chart's:
  - log10 x-axis from $1,000 to $100,000
  - linear y-axis from 20 to 80 years
  - 6 continent colors (sampled from legend swatches in image.png)
  - single marker size (population encoding is not extracted)
"""
import csv
import os
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
DATA_CSV = os.path.join(HERE, "data.csv")
OUT_PNG = os.path.join(HERE, "replot.png")

CONTINENT_COLORS = {
    "North America": "#ea8b7b",
    "South America": "#a05961",
    "Africa":        "#b577b0",
    "Europe":        "#7088b0",
    "Asia":          "#339d98",
    "Oceania":       "#60bbc8",
}

# Group rows by series
by_series = {k: {"x": [], "y": []} for k in CONTINENT_COLORS}
with open(DATA_CSV) as f:
    rdr = csv.DictReader(f)
    for r in rdr:
        s = r["series"]
        by_series.setdefault(s, {"x": [], "y": []})
        by_series[s]["x"].append(float(r["x"]))
        by_series[s]["y"].append(float(r["y"]))

fig, ax = plt.subplots(figsize=(8.5, 6.0), dpi=100)
for s, pts in by_series.items():
    if not pts["x"]:
        continue
    ax.scatter(pts["x"], pts["y"],
               s=40,
               c=CONTINENT_COLORS.get(s, "#888888"),
               alpha=0.75,
               edgecolors="white",
               linewidths=0.5,
               label=s)

ax.set_xscale("log")
ax.set_xlim(1000, 100000)
ax.set_ylim(20, 80)
ax.set_xticks([1000, 2000, 5000, 10000, 20000, 50000, 100000])
ax.set_xticklabels(["$1,000", "$2,000", "$5,000", "$10,000",
                    "$20,000", "$50,000", "$100,000"])
ax.set_yticks([20, 30, 40, 50, 60, 70, 80])
ax.set_yticklabels([f"{v} years" for v in [20, 30, 40, 50, 60, 70, 80]])
ax.set_xlabel("GDP per capita (international-$ in 2011 prices; "
              "plotted on a logarithmic axis)")
ax.set_ylabel("Life expectancy at birth")
ax.set_title("Life expectancy vs. GDP per capita, 2022 (re-plot from extraction)")
ax.grid(True, linestyle="--", alpha=0.4)
ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
fig.tight_layout()
fig.savefig(OUT_PNG, dpi=100)
print(f"Wrote {OUT_PNG}")
