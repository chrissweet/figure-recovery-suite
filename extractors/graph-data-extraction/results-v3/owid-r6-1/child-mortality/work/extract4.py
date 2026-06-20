"""
Extract 7 country series using:
1. Per-series HSV mask
2. Restrict mask to its LARGEST connected component(s) by total length — drops anti-alias spurs
3. Per column: median row of mask in 1-col window
4. Stitch with continuity for crossings
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

LEFT_COL  = int(round(year_to_col(1751)))
RIGHT_COL = int(round(year_to_col(2023)))
TOP_ROW = int(round(pct_to_row(50))) - 3
BOT_ROW = int(round(pct_to_row(0))) + 1

SERIES = [
    ("Ghana",          (130, 145,  60,  30, 230)),
    ("India",          ( 74,  84,  60,  30, 230)),
    ("Brazil",         (102, 112, 180,  30, 130)),
    ("United States",  (172, 180,  90,  30, 200)),
    ("United Kingdom", ( 12,  20, 100,  30, 230)),
    ("France",         (  4,  10, 150,  30, 230)),
    ("Sweden",         (105, 113,  90, 130, 230)),
]

def build_mask(hlo, hhi, smin, vmin, vmax):
    h = hsv[:,:,0]; s = hsv[:,:,1]; v = hsv[:,:,2]
    m = (h >= hlo) & (h <= hhi) & (s >= smin) & (v >= vmin) & (v <= vmax)
    out = np.zeros_like(m)
    out[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1] = m[TOP_ROW:BOT_ROW+1, LEFT_COL:RIGHT_COL+1]
    return out.astype(np.uint8)

def keep_main_components(mask, min_size=20):
    """Keep only connected components above min_size; drop tiny noise CCs."""
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= min_size:
            keep[labels == i] = 1
    return keep

masks = {}
for name, sp in SERIES:
    raw = build_mask(*sp)
    cleaned = keep_main_components(raw, min_size=20)
    masks[name] = cleaned.astype(bool)
    print(f"{name}: raw px={raw.sum()}, after CC>=20 px={cleaned.sum()}")

# Per-column tracing with continuity
def runs_in_col(mask_col, gap=2):
    rows = np.where(mask_col)[0]
    if len(rows) == 0:
        return []
    runs = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= gap:
            cur.append(r)
        else:
            runs.append(cur); cur = [r]
    runs.append(cur)
    return [(float(np.mean(rr)), len(rr)) for rr in runs]

def pick_row(runs, prev_row, max_jump_near, fallback_jump):
    if not runs:
        return None
    if prev_row is None:
        runs.sort(key=lambda x: -x[1])
        return runs[0][0]
    near = [r for r in runs if abs(r[0] - prev_row) <= max_jump_near]
    if near:
        near.sort(key=lambda x: -x[1])
        return near[0][0]
    far = [r for r in runs if abs(r[0] - prev_row) <= fallback_jump]
    if far:
        far.sort(key=lambda x: -x[1])
        return far[0][0]
    return None

WINDOW = 1
raw_rows = {name: {} for name, _ in SERIES}

# Per-series parameters: Sweden's early noise is high; others smoother
PARAMS = {
    "Sweden":          (15, 100),  # tight near; loose fallback for noisy spikes
    "France":          (25, 80),
    "United Kingdom":  (20, 60),
    "India":           (15, 50),
    "Ghana":           (15, 50),
    "Brazil":          (15, 50),
    "United States":   (20, 60),
}

for name, _ in SERIES:
    m = masks[name]
    mj_near, mj_far = PARAMS[name]
    prev = None
    for year in range(1751, 2024):
        c_int = int(round(year_to_col(year)))
        c_lo = max(LEFT_COL, c_int - WINDOW)
        c_hi = min(RIGHT_COL, c_int + WINDOW)
        cands = []
        for cc in range(c_lo, c_hi + 1):
            r = pick_row(runs_in_col(m[:, cc]), prev, mj_near, mj_far)
            if r is not None:
                cands.append(r)
        if cands:
            med = float(np.median(cands))
            raw_rows[name][year] = med
            prev = med
        # else: leave gap, keep prev for continuity

# Backward pass for start-of-series
for name, _ in SERIES:
    m = masks[name]
    mj_near, mj_far = PARAMS[name]
    yrs = sorted(raw_rows[name].keys())
    if not yrs:
        continue
    prev = raw_rows[name][yrs[0]]
    for year in range(yrs[0] - 1, 1750, -1):
        c_int = int(round(year_to_col(year)))
        c_lo = max(LEFT_COL, c_int - WINDOW)
        c_hi = min(RIGHT_COL, c_int + WINDOW)
        cands = []
        for cc in range(c_lo, c_hi + 1):
            r = pick_row(runs_in_col(m[:, cc]), prev, mj_near, mj_far)
            if r is not None:
                cands.append(r)
        if cands:
            med = float(np.median(cands))
            raw_rows[name][year] = med
            prev = med
        else:
            break

# Interpolate small gaps (<= 5 years)
filled_rows = {name: dict(raw_rows[name]) for name in raw_rows}
for name in raw_rows:
    yrs = sorted(raw_rows[name].keys())
    if not yrs:
        continue
    for y in range(yrs[0], yrs[-1] + 1):
        if y in raw_rows[name]:
            continue
        prev_y = max([yy for yy in yrs if yy < y], default=None)
        next_y = min([yy for yy in yrs if yy > y], default=None)
        if prev_y is None or next_y is None:
            continue
        if next_y - prev_y > 5:
            continue
        v0 = raw_rows[name][prev_y]; v1 = raw_rows[name][next_y]
        t = (y - prev_y) / (next_y - prev_y)
        filled_rows[name][y] = v0 + t * (v1 - v0)

csv_path = os.path.join(OUT_DIR, "data.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    header = ["year"] + [s[0] for s in SERIES]
    w.writerow(header)
    for year in range(1751, 2024):
        row = [year]
        for s in SERIES:
            name = s[0]
            if year in filled_rows[name]:
                pct = max(0.0, min(50.0, row_to_pct(filled_rows[name][year])))
                row.append(f"{pct:.3f}")
            else:
                row.append("")
        w.writerow(row)
print(f"Wrote {csv_path}")

print("\n=== Coverage per series ===")
for s in SERIES:
    name = s[0]
    yrs = sorted(filled_rows[name].keys())
    if yrs:
        n_interp = len([y for y in yrs if y not in raw_rows[name]])
        print(f"  {name}: {yrs[0]}-{yrs[-1]}, n={len(yrs)} (interp={n_interp})")
    else:
        print(f"  {name}: NO DATA")
