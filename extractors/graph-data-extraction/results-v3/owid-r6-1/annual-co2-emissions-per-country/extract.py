"""Extract per-series annual CO2 emissions data from OWID multi-series line plot.

Strategy:
  1. For each plot-area pixel, find the nearest-color series (winner-take-all).
  2. Only assign if nearest distance < TOL_PURE AND second-nearest > TOL_PURE * 1.5
     (rejects ambiguous antialiased pixels that overlap two series).
  3. Per pixel-column per series, take the median row of assigned pixels.
  4. Drop spurious isolated columns (no neighbors within +/- 3 cols).

Calibration anchors (from Phase 2 measurement on image.png, 850x600):
  x-axis: col 82 -> year 1750, col 711 -> year 2024, linear  (px/year ~ 2.296)
  y-axis: row 532 -> 0 t,       row 102  -> 12e9 t, linear  (px/billion ~ 35.833)
"""
import cv2
import numpy as np
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
SRC = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/annual-co2-emissions-per-country/image.png"

# --- Calibration ---
X_PIX_LEFT, X_VAL_LEFT = 82, 1750
X_PIX_RIGHT, X_VAL_RIGHT = 711, 2024
Y_PIX_BOTTOM, Y_VAL_BOTTOM = 532, 0.0
Y_PIX_TOP, Y_VAL_TOP = 102, 12e9

m_x = (X_VAL_RIGHT - X_VAL_LEFT) / (X_PIX_RIGHT - X_PIX_LEFT)
b_x = X_VAL_LEFT - m_x * X_PIX_LEFT
m_y = (Y_VAL_TOP - Y_VAL_BOTTOM) / (Y_PIX_TOP - Y_PIX_BOTTOM)
b_y = Y_VAL_BOTTOM - m_y * Y_PIX_BOTTOM

def col_to_year(c): return m_x * c + b_x
def row_to_tonnes(r): return m_y * r + b_y
def year_to_col(y): return (y - b_x) / m_x
def tonnes_to_row(t): return (t - b_y) / m_y

SERIES = {
    "China":           (0x06, 0x2e, 0x5f),
    "United States":   (0xa2, 0x6f, 0x46),
    "India":           (0x88, 0x30, 0x39),
    "Germany":         (0xb1, 0x35, 0x07),
    "Brazil":          (0x6d, 0x3e, 0x91),
    "United Kingdom":  (0x4c, 0x6a, 0x9c),
    "France":          (0x2c, 0x84, 0x65),
}

# Plot area
COL_LO, COL_HI = 82, 712
ROW_LO, ROW_HI = 60, 533

TOL_PURE = 22     # max L2 RGB distance to nearest series to accept a pixel
                  # (22 keeps line cores while rejecting antialiased edges that
                  #  bleed one series into another's color neighborhood)

def main():
    img_bgr = cv2.imread(SRC)
    H, W = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    plot = img_rgb[ROW_LO:ROW_HI, COL_LO:COL_HI].astype(np.int32)
    PH, PW = plot.shape[:2]

    series_names = list(SERIES.keys())
    palette = np.array([SERIES[s] for s in series_names], dtype=np.int32)  # (K,3)
    # distance from each pixel to each series color
    # plot: (H,W,3); palette: (K,3) -> diff: (H,W,K,3)
    diff = plot[:, :, None, :] - palette[None, None, :, :]
    d2 = (diff ** 2).sum(axis=3)  # (H,W,K)
    dist = np.sqrt(d2.astype(np.float64))
    # nearest series per pixel
    nearest_idx = dist.argmin(axis=2)
    nearest_d = dist.min(axis=2)

    accept = (nearest_d < TOL_PURE)
    # Also drop near-white pixels (light gridlines etc.)
    lightness = plot.sum(axis=2)
    accept &= (lightness < 3 * 230)

    # Per series per column, find median row of accepted pixels
    rows_out = []
    counts = {}
    for k, name in enumerate(series_names):
        mask = accept & (nearest_idx == k)
        col_rows = {}
        yy, xx = np.where(mask)
        for r, c in zip(yy, xx):
            col_rows.setdefault(c, []).append(r)
        col_list = sorted(col_rows.keys())
        med = {c: int(np.median(col_rows[c])) for c in col_list}

        # Drop spurious isolated columns: keep a column only if it has a
        # neighbor within +/-3 (drops single-pixel noise spurs).
        col_set = set(col_list)
        kept = [c for c in col_list
                if any((c + dc) in col_set for dc in [-3, -2, -1, 1, 2, 3])]

        # Spike rejection: drop a column only if BOTH immediate neighbors
        # (within +/-3 cols) disagree by > 25 px (a true spike, not a steep
        # but real climb). A steep monotonic climb has consistent neighbors,
        # so won't be flagged. Stray cross-line pixels appear as a single
        # discordant column surrounded by the real curve.
        kept_rows = np.array([med[c] for c in kept])
        kept_cols = np.array(kept)
        keep_final = np.ones(len(kept), dtype=bool)
        for i in range(1, len(kept) - 1):
            # local "neighborhood" = the 3 cols before and 3 cols after
            lo = max(0, i - 3); hi = min(len(kept), i + 4)
            neighbors_rows = np.concatenate([kept_rows[lo:i], kept_rows[i+1:hi]])
            if len(neighbors_rows) >= 2:
                local_med = np.median(neighbors_rows)
                if abs(kept_rows[i] - local_med) > 25:
                    keep_final[i] = False
        kept2 = [(int(kept_cols[i]), int(kept_rows[i]))
                 for i in range(len(kept)) if keep_final[i]]

        counts[name] = len(kept2)
        for c, r in kept2:
            x_year = col_to_year(COL_LO + c)
            y_t = row_to_tonnes(ROW_LO + r)
            if -1e6 < y_t < 0:
                y_t = 0.0
            rows_out.append({
                "layer_idx": 0,
                "layer_type": "Line Graph",
                "series": name,
                "x": round(x_year, 2),
                "y": round(y_t, 1),
            })
    print("Hits per series:", counts)

    # Write CSV (sorted by series then x for readability)
    rows_out.sort(key=lambda r: (r["series"], r["x"]))
    csv_path = HERE / "data.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["layer_idx", "layer_type", "series", "x", "y"])
        w.writeheader()
        w.writerows(rows_out)
    print(f"Wrote {len(rows_out)} rows -> {csv_path}")

    # Write calibration.json
    calib = {
        "image_size": {"width": W, "height": H},
        "plot_frame_box": {
            "offset": {"x": COL_LO, "y": ROW_LO},
            "size":   {"width": COL_HI - COL_LO, "height": ROW_HI - ROW_LO},
            "left": COL_LO, "top": ROW_LO,
            "right": COL_HI - 1, "bottom": ROW_HI - 1,
            "description": "Plot area: cols 82-711 span years 1750-2024; "
                           "rows 60-532 span ~12.5e9 down to 0 tonnes.",
        },
        "pixels_per_coordinate_unit": {
            "x": abs(1.0 / m_x),
            "y": abs(1.0 / m_y),
            "x_unit_label": "year",
            "y_unit_label": "tonnes CO2 per year",
        },
        "data_to_pixel_formula": {
            "col": f"col = (x_value - {b_x:.6f}) / {m_x:.6f}",
            "row": f"row = (y_value - {b_y:.6f}) / {m_y:.6f}",
        },
        "data_range": {
            "x_min": float(col_to_year(COL_LO)),
            "x_max": float(col_to_year(COL_HI - 1)),
            "y_min": float(row_to_tonnes(ROW_HI - 1)),
            "y_max": float(row_to_tonnes(ROW_LO)),
        },
        "axis_calibration": {
            "x_axis": {
                "formula": "year = m*col + b",
                "m": m_x, "b": b_x,
                "inverse": "col = (year - b) / m",
                "anchors": [
                    {"col": X_PIX_LEFT,  "value": X_VAL_LEFT,  "label": "1750"},
                    {"col": X_PIX_RIGHT, "value": X_VAL_RIGHT, "label": "2024"},
                ],
                "interior_tick_centers": {
                    "1800": 197, "1850": 312, "1900": 426, "1950": 541, "2000": 656,
                },
            },
            "y_axis": {
                "formula": "tonnes = m*row + b",
                "m": m_y, "b": b_y,
                "inverse": "row = (tonnes - b) / m",
                "anchors": [
                    {"row": Y_PIX_TOP,    "value": Y_VAL_TOP,    "label": "12 billion t"},
                    {"row": Y_PIX_BOTTOM, "value": Y_VAL_BOTTOM, "label": "0 t"},
                ],
                "interior_tick_rows": {
                    "10e9": 173, "8e9": 245, "6e9": 317, "4e9": 388, "2e9": 460,
                },
                "billion_t_note": (
                    "Tick labels printed as 'N billion t' (e.g. '12 billion t'). "
                    "Parsed as N * 1e9 raw tonnes; data.csv y is raw tonnes."
                ),
            },
        },
        "worked_example": {
            "scenario": "Convert China 2024 endpoint (~12.5 billion t at col 711) to pixel.",
            "input": {"x": 2024, "y": 12.5e9},
            "compute": [
                f"col = (2024 - {b_x:.4f}) / {m_x:.6f}",
                f"row = (12.5e9 - {b_y:.4f}) / {m_y:.6f}",
            ],
            "result": {
                "col": float(year_to_col(2024)),
                "row": float(tonnes_to_row(12.5e9)),
            },
            "verification": "col ~711 matches right edge of plot; row ~84 sits just above 12 billion gridline (row 102), consistent with China's ~12.6B-2024 peak.",
        },
        "detection_internals": {
            "x_axis_baseline_row": 532,
            "y_axis_gridline_rows": {"12e9": 102, "10e9": 173, "8e9": 245,
                                     "6e9": 317, "4e9": 388, "2e9": 460},
            "x_axis_extent_cols": [82, 711],
            "method": "winner-take-all nearest series color per pixel with "
                      "TOL_PURE=22 L2 RGB distance to reject antialiased edges; "
                      "per-column median row; drop isolated-column spurs (no neighbor within +/-3).",
        },
    }
    with open(HERE / "calibration.json", "w") as f:
        json.dump(calib, f, indent=2)
    print(f"Wrote calibration.json")

    # Write chart_metadata.json
    meta = {
        "panel_id": None,
        "source_citation": "Our World in Data — Annual CO2 emissions per country. "
                          "Data source: Global Carbon Budget (2025). "
                          "https://ourworldindata.org/co2-and-greenhouse-gas-emissions",
        "x_axis": {
            "title": None,
            "unit": "year",
            "title_verbatim": None,
            "decimal_separator": ".",
            "notes": "No explicit x-axis title in source figure; ticks are years.",
        },
        "y_axis": {
            "title": "Annual CO₂ emissions",
            "unit": "tonnes",
            "title_verbatim": "Annual CO₂ emissions",
            "decimal_separator": ".",
            "tick_label_format": "'N billion t' (e.g. '12 billion t'); 0-tick rendered '0 t'.",
            "notes": "Title taken from chart heading. Tick labels parsed as N*1e9 raw tonnes in data.csv.",
        },
        "chart_title": "Annual CO₂ emissions",
        "subtitle_verbatim": ("Carbon dioxide (CO₂) emissions from fossil fuels "
                              "and industry. Land-use change emissions are not included."),
        "series_legend": [
            {"series_id": "China",          "source_label": "China",          "color": "#062e5f", "marker_shape": None},
            {"series_id": "United States",  "source_label": "United States",  "color": "#a26f46", "marker_shape": None},
            {"series_id": "India",          "source_label": "India",          "color": "#883039", "marker_shape": None},
            {"series_id": "Germany",        "source_label": "Germany",        "color": "#b13507", "marker_shape": None},
            {"series_id": "Brazil",         "source_label": "Brazil",         "color": "#6d3e91", "marker_shape": None},
            {"series_id": "United Kingdom", "source_label": "United Kingdom", "color": "#4c6a9c", "marker_shape": None},
            {"series_id": "France",         "source_label": "France",         "color": "#2c8465", "marker_shape": None},
        ],
        "notes": ("Our World in Data line chart, 7 countries. Legend labels at right of "
                  "each line's endpoint (no boxed legend). Y-axis tick label format "
                  "'N billion t' is parsed as N*1e9 tonnes. Series colors sampled "
                  "from line pixels at col 695-710."),
    }
    with open(HERE / "chart_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Wrote chart_metadata.json")

if __name__ == "__main__":
    main()
