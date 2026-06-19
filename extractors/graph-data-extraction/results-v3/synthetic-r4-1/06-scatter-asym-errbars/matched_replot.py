"""Replot extracted data from data.csv with matched axes/colors and asymmetric error bars."""
import csv
import matplotlib.pyplot as plt
from collections import defaultdict
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV  = os.path.join(HERE, 'data.csv')
OUT  = os.path.join(HERE, 'replot.png')

# Load
markers = []          # list of (x, y) for centroids
caps = defaultdict(dict)  # idx -> {'y_upper':val,...}

scatter_idx = 0
for row in csv.DictReader(open(CSV)):
    if row['layer_type'] == 'Scatter Plot':
        markers.append((float(row['x']), float(row['y'])))
    elif row['layer_type'] == 'ErrorBarLayer':
        # cap rows are emitted in repeating groups of 4 in marker order
        pass

# Re-parse caps grouped by nearest marker x
cap_groups = []
i = 0
all_rows = list(csv.DictReader(open(CSV)))
err_rows = [r for r in all_rows if r['layer_type'] == 'ErrorBarLayer']
# they come in groups of 4 per marker
for g in range(0, len(err_rows), 4):
    grp = err_rows[g:g+4]
    d = {r['cap']: (float(r['x']), float(r['y'])) for r in grp}
    cap_groups.append(d)

assert len(markers) == len(cap_groups), 'marker / cap-group mismatch'

xs   = [m[0] for m in markers]
ys   = [m[1] for m in markers]
yerr_up = [cap_groups[i]['y_err_upper'][1] - ys[i] for i in range(len(markers))]
yerr_dn = [ys[i] - cap_groups[i]['y_err_lower'][1] for i in range(len(markers))]
xerr_rt = [cap_groups[i]['x_err_right'][0] - xs[i] for i in range(len(markers))]
xerr_lf = [xs[i] - cap_groups[i]['x_err_left'][0]  for i in range(len(markers))]

fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
ax.errorbar(
    xs, ys,
    xerr=[xerr_lf, xerr_rt],
    yerr=[yerr_dn, yerr_up],
    fmt='o', color='#1f77b4', ecolor='black',
    elinewidth=1, capsize=4, markersize=6,
    markeredgecolor='black', markeredgewidth=0.8,
    label='Measurement',
)
ax.set_xlim(0, 35)
ax.set_ylim(0, 35)
ax.set_xticks(range(0, 36, 5))
ax.set_yticks(range(0, 36, 5))
ax.set_xlabel('Drive current (mA)')
ax.set_ylabel('Photon count (×10³ / s)')
ax.set_title('Synthetic #6 — scatter with asymmetric x/y error bars')
ax.grid(True, linestyle='-', alpha=0.3)
ax.legend(loc='upper left')
fig.tight_layout()
fig.savefig(OUT, dpi=100)
print('wrote', OUT)
