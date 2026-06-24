#!/usr/bin/env python3
"""Forward-pass extraction for el-88 (grayscale-shape scatter, recipe §2b).

Three series share grayscale rendering, distinguished by marker SHAPE:
  24C -> filled black disk   (solid dark center,  center px ~0)
  27C -> filled gray square  (gray fill ~185, area ~140-152)
  30C -> open diamond        (gray fill ~190-220, area ~82-92, smaller)

Calibration reused from calibration.json (NOT re-derived).
Single extraction pass, no Phase-4 replot/iterate.
"""
import cv2, numpy as np, csv, json, os
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG  = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/aedes-aegypti-2014/charts/el-88/image.png"

cal = json.load(open(os.path.join(ROOT, "calibration.json")))
mx = cal["axis_calibration"]["x_axis"]["m"]; bx = cal["axis_calibration"]["x_axis"]["b"]
my = cal["axis_calibration"]["y_axis"]["m"]; by = cal["axis_calibration"]["y_axis"]["b"]
def col2x(c): return mx*c + bx
def row2y(r): return my*r + by

im = cv2.imread(IMG)
gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)

mask = (gray < 235).astype(np.uint8)
mask[:25,:]=0; mask[567:,:]=0; mask[:,:58]=0; mask[:,836:]=0   # frame interior, excl legend

n,lbl,stats,cent = cv2.connectedComponentsWithStats(mask, 8)

def centerval(cx, cy):
    cyi,cxi = int(round(cy)), int(round(cx))
    return gray[cyi-1:cyi+2, cxi-1:cxi+2].mean()

def classify(cx, cy, a):
    """Return series id for a single (non-merged) marker."""
    cv_ = centerval(cx, cy)
    if cv_ < 80:
        return "24C"           # solid black center
    return "27C" if a >= 112 else "30C"   # square larger, diamond smaller

rows = []  # (layer_idx, layer_type, series, x, y)

for i in range(1, n):
    x,y,w,h,a = stats[i]
    if a < 50:
        continue
    cx,cy = cent[i]
    # merged blob? markers are ~11-14 px; anything much bigger holds >=2 markers
    if w > 17 or h > 18 or a > 175:
        ys,xs = np.where(lbl[y:y+h, x:x+w] == i)
        pts = np.column_stack([xs+x, ys+y]).astype(np.float32)
        k = max(2, int(round(a / 125.0)))
        crit = (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        _, labels, centers = cv2.kmeans(pts, k, None, crit, 8, cv2.KMEANS_PP_CENTERS)
        for kk,(ccx,ccy) in enumerate(centers):
            sub_a = int((labels.ravel()==kk).sum())
            rows.append((classify(ccx, ccy, sub_a), ccx, ccy))
    else:
        rows.append((classify(cx, cy, a), cx, cy))

out_rows = []
for series, cx, cy in rows:
    out_rows.append((0, "Scatter Plot", series, round(col2x(cx),3), round(row2y(cy),3)))
out_rows.sort(key=lambda r: (r[2], r[3]))

out = os.path.join(ROOT, "data.csv")
with open(out, "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["layer_idx","layer_type","series","x","y"])
    for r in out_rows:
        wr.writerow(r)

c = Counter(r[2] for r in out_rows)
print("rows:", len(out_rows), dict(c))
