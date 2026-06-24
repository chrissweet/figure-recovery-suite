#!/usr/bin/env python3
"""Forward-pass (Phases 1-3) extraction for 03-grouped-bar-errbars.
Reuses provided calibration.json; no refit, no Phase-4 iteration."""
import cv2, numpy as np, json, csv, os

ROOT = os.path.dirname(os.path.abspath(__file__))
img = cv2.imread(os.path.join(ROOT, "..", "..", "..", "..", "..",
        "corpora", "synthetic-r4-1", "charts", "03-grouped-bar-errbars", "image.png"))
cal = json.load(open(os.path.join(ROOT, "calibration.json")))

m_y = cal["axis_calibration"]["y_axis"]["m"]
b_y = cal["axis_calibration"]["y_axis"]["b"]
def row2y(r): return m_y * r + b_y

# group tick cols and category indices (0-indexed per schema convention)
tick_cols = cal["detection_internals"]["x_ticks"]["tick_px_cols"]  # 5 groups
bx = cal["axis_calibration"]["x_axis"]["m"]; bxb = cal["axis_calibration"]["x_axis"]["b"]
def col2x(c): return bx * c + bxb  # category-index space (Q1=1..Q5=5)

bi = cal["detection_internals"]["bar_extraction"]
series_bgr = bi["series_BGR_colors"]
bar_centers = bi["bar_centers_px_per_series"]

fb = cal["plot_frame_box"]
L, R, T, B = fb["left"], fb["right"], fb["top"], fb["bottom"]
legend = cal["detection_internals"]["error_caps"]["legend_mask_px_box"]
lr0, lr1 = legend["rows"]; lc0, lc1 = legend["cols"]

def bar_top_row(bgr, cx):
    """topmost colored row within +/-16px column band of bar center, inside frame, outside legend."""
    tol = 18
    band = img[T:B, int(cx-16):int(cx+17)].astype(int)
    target = np.array(bgr)
    mask = (np.abs(band - target).max(axis=2) <= tol)
    rows = np.where(mask.any(axis=1))[0]
    if len(rows) == 0: return None
    # exclude legend rows (translate to frame-relative)
    for r in rows:
        rr = r + T
        cols = np.where(mask[r])[0] + int(cx-16)
        if lr0 <= rr <= lr1 and ((cols >= lc0) & (cols <= lc1)).any():
            continue
        return rr
    return rows[0] + T

def error_caps(cx, bar_top):
    """dark horizontal cap rows in band cx+/-10; upper=topmost above bar_top, lower=bottommost below."""
    c0, c1 = int(cx-11), int(cx+12)
    band = img[T:B, c0:c1]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    dark = gray < 80
    dark_count = dark.sum(axis=1)
    cand = []
    rows = np.where(dark_count >= 7)[0]
    # group by gap<=2
    if len(rows):
        grp = [[rows[0]]]
        for r in rows[1:]:
            if r - grp[-1][-1] <= 2: grp[-1].append(r)
            else: grp.append([r])
        for g in grp:
            rr = int(np.mean(g)) + T
            # skip frame/gridline rows and legend band
            if rr <= T+2 or rr >= B-2: continue
            cols = np.where(dark[g[0]])[0] + c0
            if lr0 <= rr <= lr1: continue
            cand.append(rr)
    upper = [r for r in cand if r < bar_top - 2]
    lower = [r for r in cand if r > bar_top + 2]
    up = min(upper) if upper else None       # topmost above
    lo = max(lower) if lower else None        # bottommost below (within fill)
    return up, lo

rows_out = []
series_list = ["Baseline", "Tuned", "Tuned+JIT"]
for li, s in enumerate(series_list):
    bgr = series_bgr[s]
    for gi in range(5):
        cx = bar_centers[s][gi]
        tip = bar_top_row(bgr, cx)
        if tip is None: continue
        xval = col2x(cx)
        yval = row2y(tip)
        rows_out.append([li, "Bar Chart", s, round(xval, 4), round(yval, 3), "", ""])
        up, lo = error_caps(cx, tip)
        if up is not None:
            rows_out.append([3, "ErrorBarLayer", s + "_y_err_upper", round(xval,4), round(row2y(up),3), "", ""])
        if lo is not None:
            rows_out.append([3, "ErrorBarLayer", s + "_y_err_lower", round(xval,4), round(row2y(lo),3), "", ""])

out = os.path.join(ROOT, "data.csv")
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["layer_idx","layer_type","series","x","y","y_lo","y_hi"])
    w.writerows(rows_out)
print("wrote", len(rows_out), "rows")
for r in rows_out: print(r)
