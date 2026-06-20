"""
Extract 7 country series with continuity-aware per-column tracing.

Strategy: For each series, build mask, then for each column take the median row
of the LARGEST connected run of mask rows in that column. Then post-process by
removing isolated outlier years (row jumps > 30 with no support nearby).
For the crossing region (1900-1950), also enforce continuity from previous year's row.
"""
import cv2
import numpy as np
import csv
import os
from collections import defaultdict

IMG_PATH = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/child-mortality/image.png"
OUT_DIR = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality"

img = cv2.imread(IMG_PATH)
H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

M_X, B_X = 2.443, -4230.6
M_Y, B_Y = -8.804286, 531.1905

def col_to_year(c): return (c - B_X) / M_X
def year_to_col(y): return M_X * y + B_X
def row_to_pct(r): return (r - B_Y) / M_Y
def pct_to_row(p): return M_Y * p + B_Y

LEFT_COL = int(round(year_to_col(1751)))
RIGHT_COL = int(round(year_to_col(2023)))
TOP_ROW = int(round(pct_to_row(50))) - 3
BOT_ROW = int(round(pct_to_row(0))) + 1

# Series: each with tight HSV bounds. Brazil and Sweden share hue range — distinguish by V (Brazil darker).
SERIES = [
    ("Ghana",          (130, 145,  60,  30, 230)),  # purple
    ("India",          ( 74,  84,  60,  30, 230)),  # olive green
    ("Brazil",         (102, 112, 180,  30, 130)),  # very dark navy
    ("United States",  (172, 180,  90,  30, 200)),  # maroon
    ("United Kingdom", ( 12,  20, 100,  30, 230)),  # tan
    ("France",         (  4,  10, 150,  30, 230)),  # bright red
    ("Sweden",         (105, 113,  90, 130, 230)),  # medium blue (lighter than Brazil)
]

def build_mask(hlo, hhi, smin, vmin, vmax):
    h = hsv[:,:,0]; s = hsv[:,:,1]; v = hsv[:,:,2]
    m = (h >= hlo) & (h <= hhi) & (s >= smin) & (v >= vmin) & (v <= vmax)
    out = np.zeros_like(m)
    out[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1] = m[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1]
    return out

def largest_run_center(mask_col):
    """Given a 1D bool array of mask rows in a column, return center of largest contiguous run."""
    rows = np.where(mask_col)[0]
    if len(rows) == 0:
        return None
    # Split into contiguous runs
    runs = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= 1:
            cur.append(r)
        else:
            runs.append(cur)
            cur = [r]
    runs.append(cur)
    # Sort by length, prefer longest
    runs.sort(key=lambda x: -len(x))
    best = runs[0]
    return float(np.mean(best))

def find_row_with_continuity(mask, col, prev_row, max_jump=40):
    """For a given column, find the line row closest to prev_row (within max_jump),
    otherwise fall back to largest run center."""
    col_mask = mask[:, col]
    rows = np.where(col_mask)[0]
    if len(rows) == 0:
        return None
    # Group into contiguous runs (gap <= 2)
    runs = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= 2:
            cur.append(r)
        else:
            runs.append(cur); cur = [r]
    runs.append(cur)
    # Compute (center, length) per run
    candidates = [(float(np.mean(run)), len(run)) for run in runs]
    if prev_row is None:
        # No previous -> longest run
        candidates.sort(key=lambda x: -x[1])
        return candidates[0][0]
    # Among candidates within max_jump, pick the longest; if none, fall back to longest globally
    near = [c for c in candidates if abs(c[0] - prev_row) <= max_jump]
    if near:
        near.sort(key=lambda x: -x[1])
        return near[0][0]
    # Fall back: longest globally
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]

# Compute per-year for each series using continuity
results = defaultdict(dict)
masks = {}
for name, (hlo, hhi, smin, vmin, vmax) in SERIES:
    masks[name] = build_mask(hlo, hhi, smin, vmin, vmax).astype(np.uint8)

# (Skip morphology — too aggressive on thin lines)

WINDOW = 1
for name, _ in SERIES:
    m = masks[name].astype(bool)
    prev_row = None
    # Two-pass: forward (gives prev_row for continuity), then we accept those.
    for year in range(1751, 2024):
        c_center = year_to_col(year)
        c_int = int(round(c_center))
        # Average over a tiny window for robustness
        c_lo = max(LEFT_COL, c_int - WINDOW)
        c_hi = min(RIGHT_COL, c_int + WINDOW)
        # Take the best continuity-row from each column, then median them
        rows_this_year = []
        for cc in range(c_lo, c_hi + 1):
            r = find_row_with_continuity(m, cc, prev_row, max_jump=50)
            if r is not None:
                rows_this_year.append(r)
        if not rows_this_year:
            continue
        med = float(np.median(rows_this_year))
        results[year][name] = med
        prev_row = med

# Convert rows to pct, write CSV
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
                pct = max(0.0, min(50.0, row_to_pct(results[year][name])))
                row.append(f"{pct:.3f}")
            else:
                row.append("")
        w.writerow(row)
print(f"Wrote {csv_path}")

# Coverage report
print("\n=== Coverage per series ===")
for s in SERIES:
    name = s[0]
    yrs = sorted([y for y in results if name in results[y]])
    if yrs:
        print(f"  {name}: {yrs[0]}-{yrs[-1]}, n={len(yrs)}")
    else:
        print(f"  {name}: NO DATA")
