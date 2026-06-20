#!/usr/bin/env python3
"""Extract stacked-area data from the OWID 'Global direct primary energy consumption' chart.

Approach (b): emit per-source raw values per year as `Line Graph` rows.

Method:
  - Calibrate axes from tick-label centers and plot-frame edges.
  - For each integer x column inside the plot frame, classify each row pixel to
    the nearest of the 10 series colors (in RGB Euclidean distance).
  - The band thickness (pixel count) per series at that column, multiplied by
    the y units-per-pixel, gives that series' value at that year.
  - Top-of-stack rows that are anti-aliased between thin series are assigned to
    the nearest dominant color; for the thin top stripes (modern biofuels,
    other renewables, solar) the assignment is approximate.

Output:
  - data.csv (layered schema: layer_idx, layer_type, series, x, y)
  - calibration.json
  - chart_metadata.json
  - replot.png (matplotlib reconstruction)
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")


# ----- Paths -----
IMG_PATH = Path(
    "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/"
    "corpora/owid-r6-1/charts/global-primary-energy/image.png"
)
OUT_DIR = Path(
    "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/"
    "extractors/graph-data-extraction/results-v3/owid-r6-1/global-primary-energy"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ----- Calibration -----
# Plot-frame edges identified from the red biomass baseline (rows 505-510):
PLOT_LEFT_COL = 101
PLOT_RIGHT_COL = 693
# Y tick row centers (top->bottom, label values 180000..0 in 20000-step):
Y_TICK_ROWS = [109, 154, 198, 243, 288, 332, 377, 422, 466, 512]
Y_TICK_VALS = [180000, 160000, 140000, 120000, 100000, 80000, 60000, 40000, 20000, 0]

# X axis: 1800 at col 101, 2024 at col 693 (plot-frame edges).
X_LEFT_VAL = 1800
X_RIGHT_VAL = 2024

# Series colors (RGB), bottom-to-top of stack:
SERIES = [
    ("Traditional biomass", (169, 83, 93)),
    ("Coal",                (154, 155, 155)),
    ("Oil",                 (92, 128, 186)),
    ("Gas",                 (184, 117, 200)),
    ("Nuclear",             (213, 81, 83)),
    ("Hydropower",          (144, 192, 196)),
    ("Wind",                (109, 180, 134)),
    ("Solar",               (201, 168, 49)),
    ("Other renewables",    (82, 167, 174)),
    ("Modern biofuels",     (176, 146, 110)),
]

WHITE = (255, 255, 255)


def fit_linear(xs, ys):
    m, b = np.polyfit(xs, ys, 1)
    return float(m), float(b)


def main():
    img = np.array(Image.open(IMG_PATH).convert("RGB"))
    H, W, _ = img.shape

    # Y calibration: value = my * row + by
    my, by = fit_linear(Y_TICK_ROWS, Y_TICK_VALS)
    # X calibration: x = mx * col + bx  using plot-frame edges
    mx = (X_RIGHT_VAL - X_LEFT_VAL) / (PLOT_RIGHT_COL - PLOT_LEFT_COL)
    bx = X_LEFT_VAL - mx * PLOT_LEFT_COL

    twh_per_pixel = abs(my)  # |dvalue / drow|

    series_colors = np.array([c for _, c in SERIES], dtype=np.int32)  # (10,3)
    series_names = [n for n, _ in SERIES]
    white = np.array(WHITE, dtype=np.int32)

    # Plot interior row range: from row of y=180000 (~109) down to row of y=0 (~512)
    # but the stack uses rows up to ~514 (anti-alias). We use 110..513 inclusive.
    row_top = 110
    row_bot = 513  # inclusive

    # Per-column extraction loop
    years = []
    per_series_values = {n: [] for n in series_names}

    for col in range(PLOT_LEFT_COL, PLOT_RIGHT_COL + 1):
        year = mx * col + bx
        years.append(year)

        col_pixels = img[row_top:row_bot + 1, col, :].astype(np.int32)  # (N, 3)

        # Classify each pixel: nearest among (10 series colors) + white.
        # Compute squared distances to all 11 anchors.
        anchors = np.vstack([series_colors, white[None, :]])  # (11, 3)
        # (N,1,3) - (1,11,3) -> (N,11,3)
        d = ((col_pixels[:, None, :] - anchors[None, :, :]) ** 2).sum(axis=2)  # (N,11)
        labels = d.argmin(axis=1)  # 0..10 (10 = white)

        # Count pixels per series in this column.
        counts = np.zeros(len(SERIES), dtype=np.int64)
        for k in range(len(SERIES)):
            counts[k] = int((labels == k).sum())

        for k, name in enumerate(series_names):
            per_series_values[name].append(counts[k] * twh_per_pixel)

    years = np.array(years)

    # Resample to integer years 1800..2024 inclusive
    target_years = np.arange(X_LEFT_VAL, X_RIGHT_VAL + 1)
    out_data = {"year": target_years}
    for name in series_names:
        vals = np.array(per_series_values[name])
        # interpolate at target_years from (years, vals)
        out_data[name] = np.interp(target_years, years, vals)

    # ----- Write data.csv (layered schema, approach b) -----
    csv_path = OUT_DIR / "data.csv"
    with csv_path.open("w") as f:
        f.write("layer_idx,layer_type,series,x,y\n")
        for li, name in enumerate(series_names):
            for yr, v in zip(target_years, out_data[name]):
                # Round to nearest TWh (10s) — extraction precision ~ 1 px = ~447 TWh
                f.write(f"{li},Line Graph,{name},{int(yr)},{round(float(v), 1)}\n")
    print(f"wrote {csv_path}")

    # ----- Write calibration.json -----
    cal = {
        "image_size": {"width": int(W), "height": int(H)},
        "plot_frame_box": {
            "offset": {"x": PLOT_LEFT_COL, "y": Y_TICK_ROWS[0]},
            "size": {
                "width": PLOT_RIGHT_COL - PLOT_LEFT_COL,
                "height": Y_TICK_ROWS[-1] - Y_TICK_ROWS[0],
            },
            "left": PLOT_LEFT_COL,
            "top": Y_TICK_ROWS[0],
            "right": PLOT_RIGHT_COL,
            "bottom": Y_TICK_ROWS[-1],
            "description": (
                "Plot frame inferred from the bounding columns of the "
                "Traditional-biomass baseline strip (cols 101-693) and the "
                "y-tick label centers (rows 109..512)."
            ),
        },
        "pixels_per_coordinate_unit": {
            "x": 1.0 / mx,
            "y": 1.0 / abs(my),
            "x_unit_label": "year",
            "y_unit_label": "TWh",
        },
        "data_to_pixel_formula": {
            "col": f"col = (x_value - {bx:.6f}) / {mx:.6f}",
            "row": f"row = (y_value - {by:.6f}) / {my:.6f}",
        },
        "data_range": {
            "x_min": X_LEFT_VAL,
            "x_max": X_RIGHT_VAL,
            "y_min": 0,
            "y_max": 180000,
        },
        "axis_calibration": {
            "x_axis": {
                "formula": "x_value = mx * col + bx",
                "m": mx,
                "b": bx,
                "inverse": "col = (x_value - bx) / mx",
            },
            "y_axis": {
                "formula": "y_value = my * row + by",
                "m": my,
                "b": by,
                "inverse": "row = (y_value - by) / my",
            },
        },
        "worked_example": {
            "scenario": "Recover pixel column for year 2000 and pixel row for y=100000 TWh.",
            "input": {"x": 2000, "y": 100000},
            "compute": [
                f"col = (2000 - {bx:.4f}) / {mx:.6f} = {(2000 - bx) / mx:.2f}",
                f"row = (100000 - {by:.4f}) / {my:.6f} = {(100000 - by) / my:.2f}",
            ],
            "result": {
                "col": round((2000 - bx) / mx, 2),
                "row": round((100000 - by) / my, 2),
            },
            "verification": (
                "Expected col ~630 (label '2000' center) and row ~288 "
                "(label '100,000 TWh' center). Recovered values match."
            ),
        },
        "detection_internals": {
            "y_tick_rows": Y_TICK_ROWS,
            "y_tick_values": Y_TICK_VALS,
            "x_anchors": {
                "left_col": PLOT_LEFT_COL,
                "left_value": X_LEFT_VAL,
                "right_col": PLOT_RIGHT_COL,
                "right_value": X_RIGHT_VAL,
                "rule": (
                    "Used plot-frame edges as x anchors; "
                    "Traditional biomass color (169,83,93) extends from col 101 "
                    "to col 693 along its baseline row."
                ),
            },
        },
    }
    (OUT_DIR / "calibration.json").write_text(json.dumps(cal, indent=2))
    print("wrote calibration.json")

    # ----- Write chart_metadata.json -----
    meta = {
        "panel_id": None,
        "source_citation": (
            "Our World in Data; Energy Institute - Statistical Review of "
            "World Energy (2025); Smil (2017)."
        ),
        "x_axis": {
            "title": None,
            "unit": "year",
            "title_verbatim": None,
            "decimal_separator": ".",
        },
        "y_axis": {
            "title": None,
            "unit": "TWh",
            "title_verbatim": None,
            "decimal_separator": ".",
        },
        "series_legend": [
            {"series_id": s, "source_label": s,
             "color": "#{:02x}{:02x}{:02x}".format(*c),
             "marker_shape": None}
            for s, c in SERIES
        ],
        "chart_title": "Global direct primary energy consumption",
        "subtitle": (
            "Energy consumption is measured in terawatt-hours, in terms of "
            "direct primary energy. This means that fossil fuels include the "
            "energy lost due to inefficiencies in energy production."
        ),
        "notes": (
            "Stacked area chart, 10 energy sources stacked bottom-to-top in "
            "this order: Traditional biomass, Coal, Oil, Gas, Nuclear, "
            "Hydropower, Wind, Solar, Other renewables, Modern biofuels. "
            "Legend labels on the right side outside the plot area. "
            "Data approach (b): per-source raw values per year (not cumulative "
            "tops), each emitted as a Line Graph row. Values were recovered by "
            "color-classifying each column's pixels to the nearest series color "
            "and counting band thicknesses; thin top stripes (Modern biofuels, "
            "Other renewables, Solar) have lower confidence due to anti-aliasing."
        ),
    }
    (OUT_DIR / "chart_metadata.json").write_text(json.dumps(meta, indent=2))
    print("wrote chart_metadata.json")

    # ----- Build replot (stacked area) -----
    fig, ax = plt.subplots(figsize=(8.5, 6.0), dpi=100)
    stack_arrays = [out_data[n] for n in series_names]
    colors = ["#{:02x}{:02x}{:02x}".format(*c) for _, c in SERIES]
    ax.stackplot(target_years, *stack_arrays, labels=series_names, colors=colors)
    ax.set_xlim(1800, 2024)
    ax.set_ylim(0, 180000)
    ax.set_xlabel("Year")
    ax.set_ylabel("TWh")
    ax.set_title("Global direct primary energy consumption (recovered)")
    ax.legend(loc="upper left", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "replot.png", dpi=110)
    plt.close(fig)
    print("wrote replot.png")

    # ----- Sanity print -----
    print("\nSample totals:")
    for yr in [1800, 1900, 1950, 2000, 2024]:
        idx = int(yr - X_LEFT_VAL)
        tot = sum(out_data[n][idx] for n in series_names)
        print(f"  year {yr}: total = {tot:.0f} TWh")


if __name__ == "__main__":
    main()
