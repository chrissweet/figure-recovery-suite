"""
Extract 7 country series from OWID child-mortality chart.
Uses per-column line trace with HSV color masks.
"""
import cv2
import numpy as np
import csv
import json
import os

IMG_PATH = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/child-mortality/image.png"
OUT_DIR = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality"

img = cv2.imread(IMG_PATH)
H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Calibration (from earlier analysis)
# x: linear, interior-tick fit. col = 2.443*year - 4230.6
# y: row = -8.804286*pct + 531.1905
M_X, B_X = 2.443, -4230.6
M_Y, B_Y = -8.804286, 531.1905

def col_to_year(c):
    return (c - B_X) / M_X

def year_to_col(y):
    return M_X * y + B_X

def row_to_pct(r):
    return (r - B_Y) / M_Y

def pct_to_row(p):
    return M_Y * p + B_Y

# Plot bounds (px)
LEFT_COL = max(46, int(round(year_to_col(1751))))   # ~47
RIGHT_COL = min(715, int(round(year_to_col(2023))))  # ~712
TOP_ROW = int(round(pct_to_row(50))) - 3  # ~88
BOT_ROW = int(round(pct_to_row(0))) + 1   # ~532

print(f"Plot bounds: cols [{LEFT_COL}, {RIGHT_COL}], rows [{TOP_ROW}, {BOT_ROW}]")

# Color definitions: (name, h_lo, h_hi, s_min, v_min, v_max, BGR_for_plot)
SERIES = [
    # Hue-disambiguated, narrow tolerances. Special handling: France (H=8) vs US (H=177) — both reddish
    ("Ghana",          130, 145,  60, 30, 230, (109,  62, 145)),   # purple
    ("India",           74,  84,  60, 30, 230, ( 44, 132, 101)),   # olive
    ("Brazil",         102, 112, 120, 30, 200, (  0,  41,  91)),   # navy
    ("United States",  172, 180,  90, 30, 200, (143,  61,  70)),   # maroon-red
    ("United Kingdom",  12,  20, 100, 30, 230, (153, 109,  57)),   # tan/orange
    ("France",           4,  10, 150, 30, 230, (177,  53,   7)),   # bright red
    ("Sweden",         105, 113,  90, 30, 230, ( 76, 106, 156)),   # medium blue
]

# Avoid overlap: Brazil (H=102-112) vs Sweden (H=105-113) overlap!
# Disambiguate by saturation/value: Brazil is much darker (V<~100) and very saturated (S>200);
# Sweden is lighter (V>~120) and moderately saturated (S~120-160).
# Re-tune:
SERIES = [
    ("Ghana",          130, 145,  60, 30, 230, (109,  62, 145)),
    ("India",           74,  84,  60, 30, 230, ( 44, 132, 101)),
    ("Brazil",         102, 112, 180, 30, 130, (  0,  41,  91)),   # very saturated AND dark
    ("United States",  172, 180,  90, 30, 200, (143,  61,  70)),
    ("United Kingdom",  12,  20, 100, 30, 230, (153, 109,  57)),
    ("France",           4,  10, 150, 30, 230, (177,  53,   7)),
    ("Sweden",         105, 113,  60, 130, 230, ( 76, 106, 156)),  # lighter
]

# Cut out the legend area (rightmost x>720 should not contribute, but
# also there are line-endpoint labels around x=720-740 in same colors)
# Restrict to plot columns: LEFT_COL..RIGHT_COL

def build_mask(h_lo, h_hi, s_min, v_min, v_max):
    h = hsv[:,:,0]
    s = hsv[:,:,1]
    v = hsv[:,:,2]
    m = (h >= h_lo) & (h <= h_hi) & (s >= s_min) & (v >= v_min) & (v <= v_max)
    # Restrict to plot region
    out = np.zeros_like(m)
    out[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1] = m[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1]
    return out

# For each series, build mask, then per-column take median row (line center).
# Output dict: {year: {series: pct}}, with year as int.
# Sample one column per year — pick the column closest to that year's center.

# We'll iterate years 1751..2023.
results = {y: {} for y in range(1751, 2024)}

# Pre-compute mask per series
masks = {}
for name, hlo, hhi, smin, vmin, vmax, _ in SERIES:
    masks[name] = build_mask(hlo, hhi, smin, vmin, vmax)
    print(f"{name}: mask pixels = {masks[name].sum()}")

# For each year, find the column nearest year and take median of mask rows in a small window
WINDOW = 1  # +/-1 col

for year in range(1751, 2024):
    c_center = year_to_col(year)
    c_int = int(round(c_center))
    c_lo = max(LEFT_COL, c_int - WINDOW)
    c_hi = min(RIGHT_COL, c_int + WINDOW)
    for name, *_, _ in SERIES:
        m = masks[name][:, c_lo:c_hi+1]
        rows = np.where(m.any(axis=1))[0]
        if len(rows) == 0:
            continue
        # Use median row of mask pixels in that band
        all_rows = []
        for cc in range(c_lo, c_hi+1):
            rr = np.where(masks[name][:, cc])[0]
            if len(rr):
                all_rows.extend(rr.tolist())
        if not all_rows:
            continue
        med_row = float(np.median(all_rows))
        pct = row_to_pct(med_row)
        # Clip to [0, 50]
        pct = max(0.0, min(50.0, pct))
        results[year][name] = round(pct, 3)

# Write CSV (year column + 7 series)
csv_path = os.path.join(OUT_DIR, "data.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    header = ["year"] + [s[0] for s in SERIES]
    w.writerow(header)
    for year in range(1751, 2024):
        row = [year]
        for s in SERIES:
            v = results[year].get(s[0], "")
            row.append(v if v == "" else f"{v:.3f}")
        w.writerow(row)
print(f"Wrote {csv_path}")

# Coverage report
print("\n=== Coverage per series (year ranges with data) ===")
for s in SERIES:
    name = s[0]
    years_with = sorted([y for y in results if name in results[y]])
    if years_with:
        print(f"  {name}: {years_with[0]}-{years_with[-1]}, n={len(years_with)}")
    else:
        print(f"  {name}: NO DATA")
