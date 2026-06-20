"""Matched replot for owid-r6-1 / life-expectancy.

Renders the extracted data.csv at the same pixel dimensions and approximate
visual style as the source image (850 x 600). Used as Phase-4 close-the-loop
verification per SKILL.md.
"""
import csv
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, 'data.csv')
SRC_IMG = '/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/life-expectancy/image.png'
OUT_PNG = os.path.join(HERE, 'replot.png')

# Series order and colors transcribed from chart_metadata.json (Phase 1)
SERIES_ORDER = ['Oceania', 'Europe', 'Americas', 'Asia', 'World', 'Africa']
COLORS = {
    'Oceania':  '#4C6A9C',
    'Europe':   '#9A5129',
    'Americas': '#C4523E',
    'Asia':     '#00847E',
    'World':    '#18470F',
    'Africa':   '#A2559C',
}

# Load extracted data
series = defaultdict(list)
with open(CSV_PATH) as f:
    r = csv.DictReader(f)
    for row in r:
        series[row['series']].append((int(row['x']), float(row['y'])))

# Render figure at 850x600 (same as source). dpi=100 -> 8.5 x 6.0 in.
fig = plt.figure(figsize=(8.5, 6.0), dpi=100)
ax = fig.add_axes([0.085, 0.10, 0.84, 0.75])  # leaves OWID-like margins

for name in SERIES_ORDER:
    pts = sorted(series[name])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=COLORS[name], linewidth=1.8, label=name)
    # End-of-line label (OWID style)
    if pts:
        ax.text(pts[-1][0] + 1.5, pts[-1][1], name, color=COLORS[name],
                fontsize=10, va='center', ha='left')

ax.set_xlim(1770, 2023)
ax.set_ylim(0, 80)
ax.set_xticks([1770, 1800, 1850, 1900, 1950, 2000, 2023])
ax.set_yticks(np.arange(0, 81, 10))
ax.set_yticklabels([f'{int(y)} years' for y in np.arange(0, 81, 10)])
ax.tick_params(axis='both', length=0, labelsize=9)
for s in ['top', 'right', 'left']:
    ax.spines[s].set_visible(False)
ax.spines['bottom'].set_color('#888888')
ax.grid(axis='y', linestyle='--', color='#cccccc', linewidth=0.6)
ax.set_axisbelow(True)

fig.suptitle('Life expectancy', x=0.085, y=0.96, ha='left', fontsize=15, fontweight='bold')
fig.text(0.085, 0.89,
         'Period life expectancy is the number of years the average person born in a certain year would live if they\n'
         'experienced the same chances of dying at each age as people did that year.',
         fontsize=8, color='#444444')

plt.savefig(OUT_PNG, dpi=100)
print(f'Wrote {OUT_PNG}')

# Quick visual side-by-side via composite (for inspection)
fig2, axes = plt.subplots(2, 1, figsize=(8.5, 12.0), dpi=100)
axes[0].imshow(mpimg.imread(SRC_IMG))
axes[0].set_title('source')
axes[0].axis('off')
axes[1].imshow(mpimg.imread(OUT_PNG))
axes[1].set_title('replot')
axes[1].axis('off')
side_path = os.path.join(HERE, 'side_by_side.png')
plt.savefig(side_path, dpi=80)
print(f'Wrote {side_path}')
