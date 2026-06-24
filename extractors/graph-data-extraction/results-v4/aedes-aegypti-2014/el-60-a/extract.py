#!/usr/bin/env python3
import numpy as np, cv2, csv

IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/aedes-aegypti-2014/charts/el-60-a/image.png"
OUT = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v4/aedes-aegypti-2014/el-60-a/data.csv"

# calibration (reuse, do not refit)
mx, bx = 0.033503, -3.224314   # value = mx*col + bx
my, by = -0.002808, 1.216004   # value = my*row + by
def col2x(c): return mx*c + bx
def row2y(r): return my*r + by

# plot frame box (restrict detection)
FL, FR, FT, FB = 111, 869, 6, 432
# legend exclusion (rows 30-120, cols 565-660 per metadata)
LEG = (30, 130, 560, 870)

im = cv2.imread(IMG)
hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
H, W = im.shape[:2]

# series: (id, marker layer_type, hsv_lo, hsv_hi)
series = [
    ("24C", [((100,80,40),(135,255,255))]),   # blue
    ("27C", [((40,80,40),(90,255,255))]),      # green
    ("30C", [((0,80,40),(12,255,255))]),       # red lower
]
# red also wraps high hue
red_hi = ((168,80,40),(180,255,255))

def make_mask(ranges):
    m = np.zeros((H,W), np.uint8)
    for lo,hi in ranges:
        m |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    # restrict to frame
    box = np.zeros((H,W), np.uint8)
    box[FT:FB, FL:FR] = 255
    m &= box
    # remove legend
    m[LEG[0]:LEG[1], LEG[2]:LEG[3]] = 0
    return m

rows_out = []
for sid, ranges in series:
    rr = list(ranges)
    if sid == "30C":
        rr = rr + [red_hi]
    mask = make_mask(rr)
    # erode line away to isolate markers (line ~3px, kernel 5)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    core = cv2.erode(mask, k)
    n, lbl, stats, cent = cv2.connectedComponentsWithStats(core, 8)
    pts = []
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        if a < 25:
            continue
        cx, cy = cent[i]
        pts.append((cx, cy, a))
    pts.sort(key=lambda p: p[0])
    print(f"{sid}: mask={int((mask>0).sum())} core={int((core>0).sum())} markers={len(pts)}")
    for cx, cy, a in pts:
        x = round(col2x(cx))   # snap x to integer day
        y = row2y(cy)
        rows_out.append(("0", "Line Graph", sid, x, round(y,4), int(a), round(cx,1), round(cy,1)))

# Also emit Line Graph type per the visual (markers connected by lines).
# layer_type per skill: markers at integer x with connector -> Line Graph.

with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["layer_idx","layer_type","series","x","y"])
    for r in rows_out:
        w.writerow([r[0], r[1], r[2], r[3], r[4]])

print(f"wrote {len(rows_out)} rows")
# debug print
for r in rows_out:
    print(r[2], r[3], r[4], "area", r[5], "px", r[6], r[7])
