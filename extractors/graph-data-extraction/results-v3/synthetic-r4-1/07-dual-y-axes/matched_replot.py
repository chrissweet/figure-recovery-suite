"""Matched re-plot for 07-dual-y-axes.

Reads the extracted data.csv and produces replot.png in a layout that mirrors
the source figure: dual y-axes, left blue solid-line drive current with circle
markers, right red dashed-line cell voltage with square markers.
"""
import csv
from pathlib import Path
import matplotlib.pyplot as plt

HERE = Path(__file__).parent

def load_csv(path):
    drive = []  # (x, y) on left axis
    cell = []   # (x, y) on right axis
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            x = float(row['x']); y = float(row['y'])
            if row['series'] == 'drive_current':
                drive.append((x, y))
            elif row['series'] == 'cell_voltage':
                cell.append((x, y))
    drive.sort(); cell.sort()
    return drive, cell

def main():
    drive, cell = load_csv(HERE / 'data.csv')
    fig, ax_left = plt.subplots(figsize=(7.5, 4.5), dpi=100)

    # Left axis: drive current
    xs_d = [p[0] for p in drive]
    ys_d = [p[1] for p in drive]
    ax_left.plot(xs_d, ys_d, '-o', color='#1f77b4',
                 markersize=5, linewidth=1.5,
                 label='Drive current (A)')
    ax_left.set_xlabel('Time (min)')
    ax_left.set_ylabel('Drive current (A)', color='#1f77b4')
    ax_left.tick_params(axis='y', labelcolor='#1f77b4')
    ax_left.set_xlim(0, 10)
    ax_left.set_ylim(0.3, 1.2)
    ax_left.grid(True, alpha=0.3)

    # Right axis: cell voltage
    ax_right = ax_left.twinx()
    xs_c = [p[0] for p in cell]
    ys_c = [p[1] for p in cell]
    ax_right.plot(xs_c, ys_c, '--s', color='#d62728',
                  markersize=5, linewidth=1.5,
                  label='Cell voltage (V)')
    ax_right.set_ylabel('Cell voltage (V)', color='#d62728')
    ax_right.tick_params(axis='y', labelcolor='#d62728')
    ax_right.set_ylim(7, 13)

    # Combined legend bottom-right inside plot area
    lines_l, labels_l = ax_left.get_legend_handles_labels()
    lines_r, labels_r = ax_right.get_legend_handles_labels()
    ax_left.legend(lines_l + lines_r, labels_l + labels_r,
                   loc='lower right', framealpha=0.9)

    fig.suptitle('Synthetic #7 — dual y-axes')
    fig.tight_layout()
    fig.savefig(HERE / 'replot.png', dpi=100, bbox_inches='tight')
    print(f"Wrote {HERE / 'replot.png'}")

if __name__ == '__main__':
    main()
