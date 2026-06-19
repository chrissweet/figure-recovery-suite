#!/usr/bin/env python3
"""
matched_replot.py - reconstruct the original chart from the extracted CSV
and save replot.png. Use this as the Phase-4 close-the-loop visual.
"""
import csv, os
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, 'data.csv')
OUT_PATH = os.path.join(HERE, 'replot.png')

scatter_x, scatter_y = [], []
line_x, line_y = [], []
with open(CSV_PATH) as f:
    r = csv.DictReader(f)
    for row in r:
        x = float(row['x']); y = float(row['y'])
        if row['layer_type'] == 'Scatter Plot':
            scatter_x.append(x); scatter_y.append(y)
        elif row['layer_type'] == 'Line Graph':
            line_x.append(x); line_y.append(y)

BLUE = '#1f77b4'
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
ax.plot(line_x, line_y, color=BLUE, linewidth=1.5,
        label='Linear fit (slope=1.76, intercept=4.00)')
ax.scatter(scatter_x, scatter_y, marker='o',
           facecolors='none', edgecolors=BLUE, s=60, linewidths=1.5,
           label='Measurement')
ax.set_xlim(0, 10)
ax.set_ylim(0, 30)
ax.set_xlabel('Independent x')
ax.set_ylabel('Response y')
ax.set_title('Synthetic #9 - open circles fused with same-color fit line')
ax.grid(True, color='lightgray', linewidth=0.5)
ax.legend(loc='upper left')
fig.tight_layout()
fig.savefig(OUT_PATH, dpi=100)
print(f'wrote {OUT_PATH}')
