#!/usr/bin/env python3
"""Chart 8 — percent-axis x ticks AND scientific-notation y ticks.

Feature stressed: §2 tick label parsing. The recipe must handle
  - "12%" / "37.5%" — trailing percent sign, value is the prefix
  - "2.5e-3" or "2.5×10⁻³" — explicit scientific notation
  - matplotlib's offset notation: an OFFSET label like "1e7" floating
    above the axis, with the ticks themselves labeled as plain numbers
    that should be multiplied by the offset

This chart mixes all three.

Caveat: matplotlib's default offset format isn't always portable across
machines. We use ScalarFormatter with useMathText=False so the offset
label is plain "1e7" text.
"""
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_chart  # noqa: E402

SEED = 4258
CHART_ID = "08-percent-scinot-ticks"


def main():
    rng = np.random.default_rng(SEED)
    # x in [0, 1] (will display as %), y in ~[2e6, 9e6] (matplotlib will
    # offset to 1e7 and show tick labels as 0.2, 0.4, ...)
    n = 14
    x = np.linspace(0.05, 0.95, n)
    y = 1.5e6 + 8.0e6 * x ** 1.4 + rng.normal(0, 2e5, n)

    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=100)
    ax.plot(x, y, marker="o", color="C0", linestyle="-", markersize=5,
            linewidth=1.2, label="Throughput")

    ax.set_xlabel("Saturation fraction")
    ax.set_ylabel("Photon yield (cps)")
    ax.set_title("Synthetic #8 — percent x ticks + sci-notation y ticks")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.0e7)

    # X axis as percent
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0,
                                                            decimals=0))
    # Y axis with scientific notation — force the offset to show
    fmt = mticker.ScalarFormatter(useMathText=False)
    fmt.set_scientific(True)
    fmt.set_powerlimits((-2, 2))
    ax.yaxis.set_major_formatter(fmt)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    layers = [{
        "layer_idx": 0, "layer_type": "Line Graph",
        "series": "Throughput",
        "points": [(float(xi), float(yi)) for xi, yi in zip(x, y)],
    }]

    # Read back the actual tick labels matplotlib produced so the
    # metadata records exactly what the extractor will see.
    fig.canvas.draw()
    x_ticks = ax.get_xticks().tolist()
    y_ticks = ax.get_yticks().tolist()
    x_tick_labels = [t.get_text() for t in ax.get_xticklabels()]
    y_tick_labels = [t.get_text() for t in ax.get_yticklabels()]
    y_offset = ax.yaxis.get_offset_text().get_text()

    metadata = {
        "chart_id": CHART_ID,
        "feature_stressed": ("percent x-axis ticks (\"20%\", \"40%\", …) + "
                              "scientific-notation y-axis with an offset "
                              "label (e.g. \"1e7\" above the y axis)."),
        "chart_type": "line",
        "x_scale": "linear",
        "y_scale": "linear",
        "x_axis_title": "Saturation fraction",
        "y_axis_title": "Photon yield (cps)",
        "x_axis_unit": "%",
        "y_axis_unit": "cps",
        "decimal_separator": ".",
        "panel_id": None,
        "chart_title": "Synthetic #8 — percent x ticks + sci-notation y ticks",
        "series_legend": [{
            "series_id": "Throughput", "color": "#1f77b4",
            "marker_style": "filled_circle", "line_style": "solid",
            "source_label": "Throughput",
        }],
        "generator": __file__,
        "seed": SEED,
        "tick_test": {
            "x_ticks_data": x_ticks,
            "x_tick_labels_rendered": x_tick_labels,
            "x_label_parse": ("Strip trailing '%' and divide by 100 to "
                               "recover data value, OR (if x_axis_unit is "
                               "'%') leave the value as-is."),
            "y_ticks_data": y_ticks,
            "y_tick_labels_rendered": y_tick_labels,
            "y_offset_text": y_offset,
            "y_label_parse": ("Tick labels are plain numbers (e.g. \"2\", "
                               "\"4\", …) but the y-axis carries an offset "
                               "label such as \"1e6\" or \"1e7\" near the "
                               "top of the axis; the actual value at a "
                               "tick is `label_value × parse(offset)`."),
        },
    }
    chart_dir = write_chart(CHART_ID, ax, layers, metadata)
    print(f"wrote {chart_dir}  "
          f"(x-ticks pct: {x_tick_labels[:3]}…, y offset: '{y_offset}')")


if __name__ == "__main__":
    main()
