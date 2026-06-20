#!/usr/bin/env python3
"""matched_replot.py — render extracted data.csv onto the same pixel grid as
the source image and save replot.png alongside.

The replot is the close-the-loop test for Phase 4: it must overlay the source
in axis ranges, series colors, percent y-tick formatting, and (visually) the
shape of each curve. Run from this directory:

    python3 matched_replot.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).parent
META = json.load(open(HERE / "chart_metadata.json"))
CAL  = json.load(open(HERE / "calibration.json"))

# Colors keyed by series_id from chart_metadata.json
COLOR = {s["series_id"]: s["color"] for s in META["series_legend"]}
ORDER = [s["series_id"] for s in META["series_legend"]]

# Load data.csv (layered schema: layer_idx, layer_type, series, x, y)
rows = list(csv.DictReader(open(HERE / "data.csv")))
data = defaultdict(list)
for r in rows:
    data[r["series"]].append((float(r["x"]), float(r["y"])))
for k in data:
    data[k].sort()

# Source image is 850 x 600 px. Render at the same aspect for direct visual compare.
fig_w_in, fig_h_in = 8.50, 6.00
fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in), dpi=100)

for sid in ORDER:
    pts = data[sid]
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    ax.plot(xs, ys, "-o", color=COLOR[sid], linewidth=1.6, markersize=3, label=sid)

ax.set_xlim(2004.5, 2025.5)
ax.set_ylim(0, 100)
ax.set_yticks([0, 20, 40, 60, 80, 100])
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}%"))
ax.set_xticks([2005, 2010, 2015, 2020, 2025])
ax.grid(True, axis="y", linestyle="--", linewidth=0.5, color="#cccccc", alpha=0.7)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.tick_params(left=False)

# Labels at right endpoint, OWID style
for sid in ORDER:
    pts = data[sid]
    x_last, y_last = pts[-1]
    ax.text(x_last + 0.25, y_last, sid, color=COLOR[sid],
            va="center", ha="left", fontsize=8)

ax.set_title(META["chart_title"], loc="left", fontsize=13, fontweight="bold")
fig.text(0.06, 0.92, META.get("chart_subtitle", ""), fontsize=9, color="#444")
fig.text(0.06, 0.04,
         "Data source: " + META["source_citation"],
         fontsize=7, color="#444")

plt.subplots_adjust(left=0.07, right=0.70, top=0.88, bottom=0.10)
out = HERE / "replot.png"
fig.savefig(out, dpi=100)
print(f"wrote {out}")
