"""
matched_replot.py — Phase-4 reconstruction of synthetic-r4-1/03-grouped-bar-errbars.

Reads data.csv (layered schema) + chart_metadata.json and renders a matplotlib
figure that should be visually congruent with the source image.png.

Usage:
    python3 matched_replot.py
Writes replot.png next to itself.
"""
from __future__ import annotations
import csv, json, os
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "chart_metadata.json")) as f:
    META = json.load(f)

with open(os.path.join(HERE, "data.csv")) as f:
    ROWS = list(csv.DictReader(f))

# Group rows by series for bars and for error caps.
series_order = [s["series_id"] for s in META["series_legend"]]
series_color = {s["series_id"]: s["color"] for s in META["series_legend"]}
categories   = META["x_categories"]
N_CATS       = len(categories)
N_SER        = len(series_order)

# Bar tops: layer_idx == 0
bar_x      = defaultdict(list)   # series -> list of x
bar_y      = defaultdict(list)   # series -> list of y
# Error caps: layer_idx == 1, two rows per bar (upper, lower) in interleaved order
cap_upper  = defaultdict(list)
cap_lower  = defaultdict(list)
cap_x_seen = defaultdict(list)

for r in ROWS:
    s = r["series"]
    x = float(r["x"]); y = float(r["y"])
    if r["layer_idx"] == "0":
        bar_x[s].append(x)
        bar_y[s].append(y)
    else:  # ErrorBarLayer
        # Two rows per bar: first row = upper cap (y > bar_y), second = lower cap.
        # Use the per-x running pair logic.
        cap_x_seen[s].append(x)

# Re-parse error caps grouped by (series, x_rounded): two y values; max is upper, min is lower.
errs = defaultdict(lambda: defaultdict(list))
for r in ROWS:
    if r["layer_idx"] != "1":
        continue
    s = r["series"]
    x = round(float(r["x"]), 3)
    errs[s][x].append(float(r["y"]))

err_up = defaultdict(list)
err_lo = defaultdict(list)
for s in series_order:
    for x, y in zip(bar_x[s], bar_y[s]):
        ys = errs[s][round(x, 3)]
        if len(ys) >= 2:
            up = max(ys); lo = min(ys)
            err_up[s].append(up - y)
            err_lo[s].append(y - lo)
        else:
            err_up[s].append(0.0); err_lo[s].append(0.0)

# Render. The chart's x bars are positioned at (group_tick + offset). Match matplotlib's
# typical grouped-bar layout: bar_width and per-series offset = (i - (N-1)/2) * bar_width.
fig, ax = plt.subplots(figsize=(8, 4.5))
GROUP_TICKS = np.arange(1, N_CATS + 1)   # 1..5
BAR_WIDTH   = 33.0 / 136.8                # px / px-per-x-unit -> data units ~0.241

for i, s in enumerate(series_order):
    offset = (i - (N_SER - 1) / 2.0) * BAR_WIDTH
    xs = GROUP_TICKS + offset
    ys = np.array(bar_y[s])
    eu = np.array(err_up[s])
    el = np.array(err_lo[s])
    ax.bar(xs, ys, BAR_WIDTH, color=series_color[s], label=s, edgecolor="black", linewidth=0.5)
    ax.errorbar(xs, ys, yerr=np.vstack([el, eu]), fmt="none",
                ecolor="black", capsize=4, capthick=1.2, elinewidth=1.0)

ax.set_xticks(GROUP_TICKS)
ax.set_xticklabels(categories)
ax.set_xlabel(META["x_axis"]["title_verbatim"])
ax.set_ylabel(META["y_axis"]["title_verbatim"])
ax.set_title(META["chart_title"])
ax.set_ylim(0, 105)
ax.set_axisbelow(True)
ax.grid(True, axis="y", linewidth=0.5, alpha=0.4)
ax.legend(loc="upper left")
fig.tight_layout()
out = os.path.join(HERE, "replot.png")
fig.savefig(out, dpi=100)
print(f"wrote {out}")
