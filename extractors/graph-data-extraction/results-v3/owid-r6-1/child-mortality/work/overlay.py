"""Per-element pixel overlay validation: draw extracted points back onto image.png."""
import cv2
import numpy as np
import csv
import os

IMG_PATH = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/child-mortality/image.png"
CSV_PATH = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality/data.csv"
OUT = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality/overlay.png"

# Same calibration
M_X, B_X = 2.443, -4230.6
M_Y, B_Y = -8.804286, 531.1905

img = cv2.imread(IMG_PATH)
overlay = img.copy()

# Per-series color (BGR for drawing) — bright contrast colors for overlay
COLORS_BGR = {
    "Ghana":          (255, 0, 255),    # magenta
    "India":          (0, 255, 0),      # green
    "Brazil":         (255, 255, 0),    # cyan
    "United States":  (0, 0, 0),        # black
    "United Kingdom": (0, 255, 255),    # yellow
    "France":         (0, 0, 255),      # red
    "Sweden":         (255, 0, 0),      # blue (BGR blue)
}

# Read CSV
data = {}
years = []
with open(CSV_PATH) as f:
    rdr = csv.reader(f)
    header = next(rdr)
    for c in header[1:]: data[c] = {}
    for row in rdr:
        y = int(row[0])
        years.append(y)
        for c, v in zip(header[1:], row[1:]):
            if v: data[c][y] = float(v)

# Draw each extracted point as small dot
for name in data:
    color = COLORS_BGR[name]
    for y, pct in data[name].items():
        col = int(round(M_X * y + B_X))
        row = int(round(M_Y * pct + B_Y))
        # Draw 1-px dot
        cv2.circle(overlay, (col, row), 1, color, -1)

# Blend
blended = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)
cv2.imwrite(OUT, blended)
print(f"wrote {OUT}")

# Compute per-series mean pixel error: for each extracted point, find nearest mask pixel of the same series
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
SERIES_HSV = {
    "Ghana":          (130, 145,  60,  30, 230),
    "India":          ( 74,  84,  60,  30, 230),
    "Brazil":         (102, 112, 180,  30, 130),
    "United States":  (172, 180,  90,  30, 200),
    "United Kingdom": ( 12,  20, 100,  30, 230),
    "France":         (  4,  10, 150,  30, 230),
    "Sweden":         (105, 113,  90, 130, 230),
}
print("\n=== Per-series pixel-overlay validation ===")
for name, (hlo, hhi, smin, vmin, vmax) in SERIES_HSV.items():
    h = hsv[:,:,0]; s = hsv[:,:,1]; v = hsv[:,:,2]
    m = (h >= hlo) & (h <= hhi) & (s >= smin) & (v >= vmin) & (v <= vmax)
    errs = []
    for y, pct in data[name].items():
        col = int(round(M_X * y + B_X))
        row = int(round(M_Y * pct + B_Y))
        # Find nearest mask-true pixel in ±10-row window in this column
        if not (0 <= col < img.shape[1]):
            continue
        col_mask = m[:, col]
        rows_here = np.where(col_mask)[0]
        if len(rows_here) == 0:
            continue
        err = min(abs(rr - row) for rr in rows_here)
        errs.append(err)
    if errs:
        print(f"  {name}: n={len(errs)}, mean err = {np.mean(errs):.2f} px, max = {max(errs)} px")
