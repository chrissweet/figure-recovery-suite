import cv2, numpy as np, csv, json

IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/share-of-individuals-using-the-internet/image.png"
OUT = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v4/owid-r6-1/share-of-individuals-using-the-internet/data.csv"

# calibration
mx, bx = 0.03907825428057995, 2002.6512716473371
my, by = -0.23849992889695482, 121.74872860983392
def col2x(c): return mx*c + bx
def row2y(r): return my*r + by
def x2col(x): return (x - bx)/mx

# plot frame
L,T,R,B = 60,16,833,512

# legend labels sit to the right of line endpoints near right edge; restrict x to <= ~ x2col(2025.5)
img = cv2.imread(IMG)
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.int32)

series = [
  ("North America (WB)",                  (0x6d,0x3e,0x91)),
  ("Europe and Central Asia (WB)",        (0xb1,0x35,0x07)),
  ("East Asia and Pacific (WB)",          (0x4c,0x6a,0x9c)),
  ("Latin America and Caribbean (WB)",    (0x99,0x6d,0x39)),
  ("World",                               (0xa2,0x55,0x9c)),
  ("South Asia (WB)",                     (0x88,0x30,0x39)),
  ("MENA, Afghanistan and Pakistan (WB)", (0x2c,0x84,0x65)),
  ("Sub-Saharan Africa (WB)",             (0x00,0x29,0x5b)),
]
names = [s[0] for s in series]
cols_ref = np.array([s[1] for s in series], dtype=np.int32)

# x range of data: years 2005..2025. Right legend text begins right after each endpoint.
# Limit detection to interior columns up to year 2025.7 to avoid legend text.
x_lo_col = int(round(x2col(2004.0)))
x_hi_col = int(round(x2col(2025.7)))
x_lo_col = max(x_lo_col, L)
x_hi_col = min(x_hi_col, R)

# Build per-pixel nearest-color label with a max-distance gate and saturation/whiteness gate.
sub = img[T:B, x_lo_col:x_hi_col, :]  # rows T..B, cols offset
h,w,_ = sub.shape

# whiteness/gray gate: skip near-white and near-gray (gridlines ~ light gray)
rgb = sub.reshape(-1,3)
maxc = rgb.max(1); minc = rgb.min(1)
sat = maxc - minc
notwhite = (maxc < 235)
colorful = (sat > 25)
mask_pix = notwhite & colorful

# nearest ref color
d = np.linalg.norm(rgb[:,None,:].astype(np.float32) - cols_ref[None,:,:].astype(np.float32), axis=2)
nearest = d.argmin(1)
nearest_dist = d.min(1)
gate = mask_pix & (nearest_dist < 60)

labels = np.full(rgb.shape[0], -1, dtype=np.int32)
labels[gate] = nearest[gate]
labels = labels.reshape(h,w)

# For each series, for each integer year, take median row of matching pixels within a +/- window of the year column
rows_out = []
years = list(range(2005, 2026))
for si,(name,_) in enumerate(series):
    ys = []
    for yr in years:
        c = x2col(yr)
        cc = int(round(c)) - x_lo_col  # index into sub
        if cc < 0 or cc >= w:
            continue
        win = 3
        lo = max(0, cc-win); hi = min(w, cc+win+1)
        band = labels[:, lo:hi]
        rr = np.where(band == si)[0]
        if len(rr) == 0:
            ys.append((yr, None)); continue
        med_row = np.median(rr) + T
        yval = row2y(med_row)
        ys.append((yr, yval))
    rows_out.append((name, ys))

# interpolate occluded (None) interior points linearly across years; record count
import numpy as _np
final = []
for name, ys in rows_out:
    yrs = _np.array([p[0] for p in ys], float)
    vals = _np.array([_np.nan if p[1] is None else p[1] for p in ys], float)
    good = ~_np.isnan(vals)
    if good.sum() >= 2:
        vals_i = _np.interp(yrs, yrs[good], vals[good])
    else:
        vals_i = vals
    for i,yr in enumerate(ys):
        v = vals_i[i]
        if _np.isnan(v): continue
        final.append((name, yr[0], float(v), bool(good[i])))

with open(OUT,"w",newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["layer_idx","layer_type","series","x","y"])
    for si,(name,_) in enumerate(series):
        for name2, yr, v, g in final:
            if name2 != name: continue
            wr.writerow([si, "Line Graph", name, yr, round(v,3)])

# report
print("series, n_detected, n_interp")
for si,(name, ys) in enumerate(rows_out):
    nd = sum(1 for p in ys if p[1] is not None)
    ni = sum(1 for p in ys if p[1] is None)
    print(f"{si}\t{name}\t{nd}\t{ni}")
