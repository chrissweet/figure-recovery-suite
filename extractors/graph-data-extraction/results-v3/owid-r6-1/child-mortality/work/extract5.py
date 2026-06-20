"""
Extract 7 country series — v5.

Insight: the mask after CC filtering is essentially the line itself.
For each column, the MEDIAN row of mask = line center at that x.
No continuity needed if mask is clean (which it is after CC filter).

For Brazil/Sweden where hue overlaps, use V (value) to disambiguate.

Output: one row per YEAR, sampled at column nearest year.
For multi-column (window=1), median across the window.
"""
import cv2
import numpy as np
import csv
import os

IMG_PATH = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/child-mortality/image.png"
OUT_DIR = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality"

img = cv2.imread(IMG_PATH)
H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

M_X, B_X = 2.443, -4230.6
M_Y, B_Y = -8.804286, 531.1905

def year_to_col(y): return M_X * y + B_X
def row_to_pct(r): return (r - B_Y) / M_Y
def pct_to_row(p): return M_Y * p + B_Y

LEFT_COL  = int(round(year_to_col(1751)))
RIGHT_COL = int(round(year_to_col(2023)))
TOP_ROW = int(round(pct_to_row(50))) - 3
BOT_ROW = int(round(pct_to_row(0))) + 1

SERIES = [
    # (name, hue_lo, hue_hi, sat_min, val_min, val_max)
    ("Ghana",          130, 145,  60,  30, 230),
    ("India",           74,  84,  60,  30, 230),
    ("Brazil",         102, 112, 180,  30, 130),
    ("United States",  172, 180,  90,  30, 200),
    ("United Kingdom",  12,  20, 100,  30, 230),
    ("France",           4,  10, 150,  30, 230),
    ("Sweden",         105, 113,  90, 130, 230),
]

def build_mask(hlo, hhi, smin, vmin, vmax):
    h = hsv[:,:,0]; s = hsv[:,:,1]; v = hsv[:,:,2]
    m = (h >= hlo) & (h <= hhi) & (s >= smin) & (v >= vmin) & (v <= vmax)
    out = np.zeros_like(m)
    out[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1] = m[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1]
    return out.astype(np.uint8)

def keep_large_ccs(mask, min_size, dilate_for_grouping=True):
    """Optionally dilate mask BEFORE CC labeling to merge anti-alias-fragmented lines,
    then map CC labels back to original mask pixels."""
    if dilate_for_grouping:
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(mask, kernel, iterations=1)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(dilated, connectivity=8)
    else:
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= min_size:
            keep[(labels == i) & (mask > 0)] = 1
    return keep

masks = {}
for name, *sp in SERIES:
    raw = build_mask(*sp)
    cleaned = keep_large_ccs(raw, 20)
    masks[name] = cleaned.astype(bool)
    print(f"{name}: raw={raw.sum()}, cleaned={cleaned.sum()}")

# Per column, median row gives line center
# Use a window of cols centered on year
WINDOW = 1
results = {y: {} for y in range(1751, 2024)}

for name, *_ in SERIES:
    m = masks[name]
    # Pre-compute per-column median row
    col_centers = {}
    for c in range(LEFT_COL, RIGHT_COL+1):
        rows = np.where(m[:, c])[0]
        if len(rows):
            col_centers[c] = float(np.median(rows))
    # For each year, take median of col_centers within window
    for year in range(1751, 2024):
        c_int = int(round(year_to_col(year)))
        c_lo = max(LEFT_COL, c_int - WINDOW)
        c_hi = min(RIGHT_COL, c_int + WINDOW)
        cands = [col_centers[c] for c in range(c_lo, c_hi+1) if c in col_centers]
        if cands:
            med = float(np.median(cands))
            pct = max(0.0, min(50.0, row_to_pct(med)))
            results[year][name] = round(pct, 3)

# Despike: Sweden has cross-line contamination in 1950+ (anomalous upward spikes
# back to mid-percent values when true value is < 5%). Detect and remove.
# Use a 5-year median filter (only past 1945 where data should be smoothly declining).
for name in ["Sweden", "France", "United Kingdom", "United States", "Brazil", "India", "Ghana"]:
    yrs_with = sorted([y for y in results if name in results[y]])
    if not yrs_with:
        continue
    bad = []
    # Iterate twice for clustered spikes
    # Step A: 7-year median spike filter
    for _iter in range(5):
        for i in range(3, len(yrs_with) - 3):
            y = yrs_with[i]
            if y < 1945:
                continue
            window = [results[yrs_with[j]][name] for j in range(i-3, i+4)]
            med = sorted(window)[3]
            v = results[y][name]
            if v - med > 1.5:
                results[y][name] = round(med, 3)
                bad.append((y, v, med))
    # Step B: post-1945 monotonic-decline runs. For each year, look at 5 cleanest neighbors
    # before & after. If current value > both neighbor groups by 1.5 absolute, interpolate.
    for i in range(5, len(yrs_with) - 5):
        y = yrs_with[i]
        if y < 1950:
            continue
        v = results[y][name]
        # Mean of 5 prev clean (in years that come before in chronological order)
        pre_vals = sorted([results[yrs_with[j]][name] for j in range(max(0,i-7), i)])[:5]
        post_vals = sorted([results[yrs_with[j]][name] for j in range(i+1, min(len(yrs_with), i+8))])[:5]
        if not pre_vals or not post_vals:
            continue
        pre_min = min(pre_vals); post_min = min(post_vals)
        baseline = (pre_min + post_min) / 2
        # If v is significantly above baseline AND above both adjacent year-to-year smoothed
        if v - baseline > 1.5 and v - pre_min > 1.5 and v - post_min > 1.5:
            results[y][name] = round(baseline, 3)
            bad.append((y, v, baseline))
    if bad:
        print(f"  Despiked {name}: {len(bad)} corrections")

# Interpolate short gaps in the middle (not at series ends)
for name, *_ in SERIES:
    yrs_with = sorted([y for y in results if name in results[y]])
    if not yrs_with:
        continue
    y0, y1 = yrs_with[0], yrs_with[-1]
    for y in range(y0, y1 + 1):
        if name in results[y]:
            continue
        # Find prev/next known
        prev = max([yy for yy in yrs_with if yy < y], default=None)
        nxt = min([yy for yy in yrs_with if yy > y], default=None)
        if prev is None or nxt is None:
            continue
        if nxt - prev > 5:
            continue
        v0 = results[prev][name]; v1 = results[nxt][name]
        t = (y - prev) / (nxt - prev)
        results[y][name] = round(v0 + t * (v1 - v0), 3)

# Write CSV
csv_path = os.path.join(OUT_DIR, "data.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    header = ["year"] + [s[0] for s in SERIES]
    w.writerow(header)
    for year in range(1751, 2024):
        row = [year]
        for s in SERIES:
            name = s[0]
            if name in results[year]:
                row.append(f"{results[year][name]:.3f}")
            else:
                row.append("")
        w.writerow(row)
print(f"\nWrote {csv_path}")

print("\n=== Coverage per series ===")
for s in SERIES:
    name = s[0]
    yrs = sorted([y for y in results if name in results[y]])
    if yrs:
        print(f"  {name}: {yrs[0]}-{yrs[-1]}, n={len(yrs)}")
    else:
        print(f"  {name}: NO DATA")
