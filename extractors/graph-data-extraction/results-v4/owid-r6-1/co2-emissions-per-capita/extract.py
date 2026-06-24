#!/usr/bin/env python3
"""Forward-pass line trace for owid co2-emissions-per-capita.
Per-series LAB-color-distance, winner-take-all per pixel with purity check,
then per-column median row of each series's owned pixels -> data coords.
Reuses provided calibration; no refit, no Phase-4 iteration."""
import csv, json, os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/co2-emissions-per-capita/image.png"
img = cv2.imread(IMG)  # BGR
H, W = img.shape[:2]

cal = json.load(open(os.path.join(HERE, "calibration.json")))
meta = json.load(open(os.path.join(HERE, "chart_metadata.json")))
pf = cal["plot_frame_box"]
xax = cal["axis_calibration"]["x_axis"]
yax = cal["axis_calibration"]["y_axis"]
L, R, T, B = pf["left"], pf["right"], pf["top"], pf["bottom"]


def col_to_year(col):
    return xax["b"] + (col - 44) * xax["m"]


def row_to_t(row):
    # tonnes = 25.0 - (row - 109)*0.06219
    return 25.0 - (row - 109) * 0.06219


def hex_to_bgr(h):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return np.uint8([[[b, g, r]]])


series = meta["series_legend"]
# series colors in LAB
lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
ser_lab = []
for s in series:
    bgr = hex_to_bgr(s["color"])
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)[0, 0]
    ser_lab.append(lab)
ser_lab = np.array(ser_lab)  # (N,3)
N = len(series)

# Restrict to plot frame. Also build a "is colored stroke" mask: exclude
# near-grey/near-white background and gridlines.
sub = lab_img[T:B + 1, L:R + 1]  # (h,w,3)
h, w = sub.shape[:2]
# BGR sub for saturation-ish background test
bgr_sub = img[T:B + 1, L:R + 1].astype(np.float32)
mx = bgr_sub.max(axis=2)
mn = bgr_sub.min(axis=2)
chroma = mx - mn
# foreground: enough color separation OR sufficiently dark (some lines dark navy)
fg = (chroma > 18) & (mx < 245)

# distance from each pixel to each series color
flat = sub.reshape(-1, 3)
# (P,N) distances
d = np.zeros((flat.shape[0], N), dtype=np.float32)
for i in range(N):
    diff = flat - ser_lab[i]
    d[:, i] = np.sqrt((diff * diff).sum(axis=1))
nearest = d.argmin(axis=1)
nd = d.min(axis=1)
# second nearest for purity
d2 = d.copy()
d2[np.arange(d.shape[0]), nearest] = np.inf
second = d2.min(axis=1)

MAXDIST = 34.0      # accept only if close enough to a legend color
PURITY = 1.15       # second-nearest must be > 1.15x nearest

ok = (nd < MAXDIST) & (second > PURITY * nd)
ok = ok.reshape(h, w) & fg
nearest = nearest.reshape(h, w)

rows_out = []
per_series_counts = {}
for i, s in enumerate(series):
    name = s["series_id"]
    pts = []
    own = (nearest == i) & ok
    for cx in range(w):
        rr = np.where(own[:, cx])[0]
        if len(rr) == 0:
            continue
        # column may contain the line plus stray; take median row
        row_med = int(np.median(rr))
        col = L + cx
        row = T + row_med
        year = col_to_year(col)
        t = row_to_t(row)
        pts.append((year, t))
    per_series_counts[name] = len(pts)
    for (year, t) in pts:
        rows_out.append((0, "Line Graph", name, round(year, 2), round(t, 4)))

out = os.path.join(HERE, "data.csv")
with open(out, "w", newline="") as f:
    wcsv = csv.writer(f)
    wcsv.writerow(["layer_idx", "layer_type", "series", "x", "y"])
    wcsv.writerows(rows_out)

print("total rows:", len(rows_out))
for k, v in per_series_counts.items():
    print(f"  {k}: {v}")
