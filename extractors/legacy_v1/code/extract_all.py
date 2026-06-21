#!/usr/bin/env python3
"""Pass-3: extract all 8 charts using the finalized skill methods.
Each chart's calibration, technique, and result are returned as a dict so
the report writer can render them.
"""
import cv2
import numpy as np
import csv
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

BASE = "/Users/csweet1/Documents/projects/CRS_research/paper-atomizer-eval/chart-extraction/charts"

results_summary = {}


def write_csv(folder, rows, header):
    out_dir = f"{BASE}/{folder}/extracted"
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/data.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def save_meta(folder, meta):
    out_dir = f"{BASE}/{folder}/extracted"
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/run3_meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)


def detect_filled(mask, ker=4, min_area=10):
    er = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (ker, ker)))
    n, _, stats, centroids = cv2.connectedComponentsWithStats(er, connectivity=8)
    pts = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < min_area:
            continue
        ar = max(w, h) / max(min(w, h), 1)
        if ar > 2.5:
            continue
        pts.append((centroids[i][0], centroids[i][1]))
    pts.sort()
    return pts


def column_runs(col):
    rows = np.where(col > 0)[0]
    if len(rows) == 0:
        return []
    runs, s, e = [], rows[0], rows[0]
    for r in rows[1:]:
        if r == e + 1:
            e = r
        else:
            runs.append((s, e))
            s, e = r, r
    runs.append((s, e))
    return runs


def subtract_curves(mask, thin_h=3, marker_span=(4, 13)):
    out = mask.copy()
    H, W = mask.shape
    lo, hi = marker_span
    for c in range(W):
        runs = column_runs(mask[:, c])
        for i, (s, e) in enumerate(runs):
            if e - s + 1 > thin_h:
                continue
            paired = False
            for j, (s2, e2) in enumerate(runs):
                if i == j or e2 - s2 + 1 > thin_h:
                    continue
                gap = max(s, s2) - min(e, e2)
                if lo <= gap <= hi:
                    paired = True
                    break
            if not paired:
                out[s:e + 1, c] = 0
    return out


# ========================================================================
# el-60-a — 3-color line plot with markers
# ========================================================================
def extract_el60a():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-60-a"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m_x, b_x = 0.033503, -3.224314
    m_y, b_y = -0.002808, 1.216004

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[10:432, 111:867] = 1
    mask_area[30:120, 565:620] = 0

    blue = cv2.inRange(hsv, (100, 100, 50), (130, 255, 255)) * mask_area
    green = cv2.inRange(hsv, (40, 60, 30), (85, 255, 220)) * mask_area
    red1 = cv2.inRange(hsv, (0, 100, 60), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 100, 60), (180, 255, 255))
    red = cv2.bitwise_or(red1, red2) * mask_area

    def detect(mask):
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        er = cv2.erode(mask, k)
        n, _, stats, cent = cv2.connectedComponentsWithStats(er, connectivity=8)
        pts = []
        for i in range(1, n):
            if stats[i, 4] < 30:
                continue
            cx, cy = cent[i]
            pts.append((m_x * cx + b_x, m_y * cy + b_y))
        pts.sort(key=lambda p: p[0])
        return [(round(x), round(y, 4)) for x, y in pts]

    series = {"24C": detect(blue), "27C": detect(green), "30C": detect(red)}
    rows = []
    for s, pts in series.items():
        for x, y in pts:
            rows.append((s, x, y))
    write_csv(folder, rows, ["series", "time_days", "percentage_parous_females"])

    fig, ax = plt.subplots(figsize=(9, 5.5))
    sty = {"24C": ("#1f6fd0", "o", "24°C"), "27C": ("#1e7e1e", "s", "27°C"), "30C": ("#d62020", "D", "30°C")}
    for s, pts in series.items():
        c, mk, lab = sty[s]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=c, marker=mk, label=lab, linewidth=2, markersize=8)
    ax.set_xlim(0.5, 23.5)
    ax.set_ylim(0, 1.0)
    ax.set_xticks(range(1, 24, 2))
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("Time after the blood-meal (days)")
    ax.set_ylabel("Percentage of parous females")
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=130)
    plt.close()

    meta = {
        "chart_type": "3-color line plot, markers at integer days",
        "calibration": {
            "x_axis": f"value = {m_x}·col + {b_x}",
            "y_axis": f"value = {m_y}·row + {b_y}",
        },
        "method": "§3a marker-on-line: HSV color mask + 5×5 erosion + CC centroid, snap x to integer day",
        "params": {"erode_kernel": "5×5", "min_area": 30},
        "legend_exclusion": "rows 30-120, cols 565-620",
        "counts": {s: len(p) for s, p in series.items()},
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-60-b — 3 markers + trend line, scatter
# ========================================================================
def extract_el60b():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-60-b"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m_x, b_x = 0.036176, 6.483232
    m_y, b_y = -0.002446, 1.149266

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:469, 100:864] = 1

    blue = cv2.inRange(hsv, (100, 100, 50), (130, 255, 255)) * mask_area
    green = cv2.inRange(hsv, (40, 60, 30), (85, 255, 220)) * mask_area
    red1 = cv2.inRange(hsv, (0, 100, 60), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 100, 60), (180, 255, 255))
    red = cv2.bitwise_or(red1, red2) * mask_area

    def detect(mask):
        n, _, stats, cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
        pts = []
        for i in range(1, n):
            if stats[i, 4] < 20:
                continue
            cx, cy = cent[i]
            pts.append((round(m_x * cx + b_x, 2), round(m_y * cy + b_y, 4)))
        return pts

    series = {"24C": detect(blue), "27C": detect(green), "30C": detect(red)}
    rows = [(s, x, y) for s, pts in series.items() for x, y in pts]
    write_csv(folder, rows, ["series", "temperature_C", "max_parity_rate"])

    sty = {"24C": ("#1f6fd0", "o"), "27C": ("#1e7e1e", "s"), "30C": ("#d62020", "D")}
    fig, ax = plt.subplots(figsize=(8, 5))
    for s, pts in series.items():
        c, mk = sty[s]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=c, marker=mk, s=80, label=s)
    ax.set_xlim(10, 35)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Temperatures (°C)")
    ax.set_ylabel("Maximum Parity Rate")
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "3-point scatter + black trend line",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": "§2 scatter: HSV color mask + CC centroid; trend line NOT extracted",
        "params": {"erode_kernel": "none", "min_area": 20},
        "counts": {s: len(p) for s, p in series.items()},
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-62 — grouped bar chart with error bars
# ========================================================================
def extract_el62():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-62"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m_x, b_x = 0.009983, 21.680537
    m_y, b_y = -0.028829, 16.415132

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:570, 84:980] = 1
    mask_area[20:160, 680:980] = 0

    gc1 = cv2.inRange(hsv, (95, 80, 30), (115, 255, 180)) * mask_area
    gc2 = cv2.inRange(hsv, (30, 80, 60), (60, 255, 200)) * mask_area
    gc3 = cv2.inRange(hsv, (0, 25, 150), (15, 110, 255)) * mask_area
    black = ((gray < 150) & (hsv[:, :, 1] < 80)).astype(np.uint8) * 255 * mask_area
    black[567:573, :] = 0
    black[20:160, 680:980] = 0
    black[574:610, :] = 0

    def detect_bars(mask, sname):
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        bars = []
        for i in range(1, n):
            x, y, w, h, a = stats[i]
            if a < 500:
                continue
            cx = int((x + x + w - 1) / 2)
            top = y
            bot = y + h - 1
            bars.append({"cx": cx, "top": top, "bot": bot, "w": w})
        bars.sort(key=lambda b: b["cx"])
        out = []
        for b in bars:
            cap_rows = []
            for r in range(20, b["top"] - 1):
                strip = black[r, b["cx"] - 12:b["cx"] + 13]
                run = mx = 0
                for v in strip:
                    if v > 0:
                        run += 1
                        mx = max(mx, run)
                    else:
                        run = 0
                if mx >= 3:
                    cap_rows.append(r)
            cap_rows = [r for r in cap_rows if b["top"] - r >= 5]
            y_hi_row = min(cap_rows) if cap_rows else b["top"]
            out.append({
                "series": sname,
                "temperature_C": round(m_x * b["cx"] + b_x, 2),
                "mean_duration": round(m_y * b["top"] + b_y, 2),
                "y_hi": round(m_y * y_hi_row + b_y, 2),
            })
        return out

    r1 = detect_bars(gc1, "GC1")
    r2 = detect_bars(gc2, "GC2")
    r3 = detect_bars(gc3, "GC3")
    rows = [(r["series"], r["temperature_C"], r["mean_duration"], r["mean_duration"], r["y_hi"]) for r in r1 + r2 + r3]
    write_csv(folder, rows, ["series", "temperature_C", "mean_duration_days", "y_lo", "y_hi"])

    width = 0.25
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (s, color) in enumerate([(r1, "#0a3a73"), (r2, "#7a8b3a"), (r3, "#d49b9b")]):
        xs, ys, yhi = [], [], []
        for t in [24, 27, 30]:
            m = [r for r in s if round(r["temperature_C"]) == t]
            if m:
                xs.append(t + (i - 1) * width)
                ys.append(m[0]["mean_duration"])
                yhi.append(max(0, m[0]["y_hi"] - m[0]["mean_duration"]))
        ax.bar(xs, ys, width=width, yerr=[[0] * len(yhi), yhi], color=color,
               label=["GC1", "GC2", "GC3"][i], capsize=4, edgecolor="black")
    ax.set_xticks([24, 27, 30])
    ax.set_xlabel("Temperatures (°C)")
    ax.set_ylabel("Duration of GC (days)")
    ax.set_ylim(0, 16)
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "grouped bar chart, error bars",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": "§4 bar fills via HSV; §4b upper error caps detected by horizontal black runs above bar top",
        "params": {"bar_min_area": 500, "cap_min_run": 3, "min_above_bar": 5},
        "counts": {"GC1": len(r1), "GC2": len(r2), "GC3": len(r3)},
        "note": "Lower error caps NOT extracted (occluded by bar fill).",
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-75 — 3 markers w/ error bars + trend
# ========================================================================
def extract_el75():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-75"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m_x, b_x = 0.048465, -3.992979
    m_y, b_y = -0.046192, 25.668679

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:556, 85:920] = 1
    black = ((gray < 100) & (hsv[:, :, 1] < 100)).astype(np.uint8) * 255 * mask_area

    er = cv2.erode(black, cv2.getStructuringElement(cv2.MORPH_RECT, (4, 4)))
    n, _, stats, cent = cv2.connectedComponentsWithStats(er, connectivity=8)
    pts = [(cent[i][0], cent[i][1], max(stats[i, 2], stats[i, 3])) for i in range(1, n) if stats[i, 4] >= 20]
    pts.sort()

    def walk(strip, c0, direction, gap):
        pos = c0
        last = c0
        while True:
            found = None
            for d in range(1, gap + 1):
                p = pos + direction * d
                if p < 0 or p >= len(strip):
                    break
                if strip[p] > 0:
                    found = p
                    break
            if found is None:
                break
            pos = found
            last = pos
        return last

    out = []
    for cx, cy, msize in pts:
        cxi, cyi = int(cx), int(cy)
        col_strip = black[:, max(0, cxi - 3):cxi + 4].max(axis=1)
        row_strip = black[max(0, cyi - 3):cyi + 4, :].max(axis=0)
        gap = 15
        y_top = walk(col_strip, cyi, -1, gap)
        y_bot = walk(col_strip, cyi, +1, gap)
        x_lo = walk(row_strip, cxi, -1, gap)
        x_hi = walk(row_strip, cxi, +1, gap)
        out.append({
            "x": round(m_x * cx + b_x, 2),
            "y": round(m_y * cy + b_y, 3),
            "x_lo": round(m_x * x_lo + b_x, 2),
            "x_hi": round(m_x * x_hi + b_x, 2),
            "y_lo": round(m_y * y_bot + b_y, 3),
            "y_hi": round(m_y * y_top + b_y, 3),
        })

    rows = [(i + 1, e["x"], e["y"], e["x_lo"], e["x_hi"], e["y_lo"], e["y_hi"]) for i, e in enumerate(out)]
    write_csv(folder, rows, ["point", "temperature_C", "mean_GC_duration", "x_lo", "x_hi", "y_lo", "y_hi"])

    xs = [e["x"] for e in out]
    ys = [e["y"] for e in out]
    xerr = [[e["x"] - e["x_lo"] for e in out], [e["x_hi"] - e["x"] for e in out]]
    yerr = [[e["y"] - e["y_lo"] for e in out], [e["y_hi"] - e["y"] for e in out]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(xs, ys, xerr=xerr, yerr=yerr, fmt="o", color="black", ecolor="black", capsize=4, markersize=8)
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 25)
    ax.set_xlabel("Temperatures (°C)")
    ax.set_ylabel("Mean Gonotrophic Cycle duration")
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "3 markers with x and y error bars + red trend line",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": "§2 scatter (markers) + §2a error bars (walk_with_gap, ±3 col/row strip, gap=15)",
        "counts": {"data points": len(out)},
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-80 — small grouped bar w/ stippled GC2
# ========================================================================
def extract_el80():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-80"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m_x, b_x = 0.009844, 22.084497
    m_y, b_y = -0.147330, 89.915238

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:611, 43:960] = 1
    mask_area[20:160, 600:960] = 0

    b, g_ch, r_ch = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    is_gray = (abs(b.astype(int) - g_ch.astype(int)) < 5) & (abs(g_ch.astype(int) - r_ch.astype(int)) < 5)
    gc1 = ((gray >= 100) & (gray <= 135) & is_gray).astype(np.uint8) * 255 * mask_area
    gc3 = ((gray >= 195) & (gray <= 225) & is_gray).astype(np.uint8) * 255 * mask_area
    gray_for_scan = gray.copy()
    gray_for_scan[mask_area == 0] = 255

    def find_bar_top(cx):
        for r in range(160, 600):
            strip = gray_for_scan[r, cx - 28:cx + 29]
            if (strip < 160).sum() >= 40:
                return r
        return None

    n, _, s1, _ = cv2.connectedComponentsWithStats(gc1, connectivity=8)
    gc1_cxs = sorted([int(s1[i, 0] + s1[i, 2] / 2) for i in range(1, n) if s1[i, 4] > 5000])
    bar_w = 67
    gc2_cxs = [c + bar_w + 1 for c in gc1_cxs]
    gc3_cxs_all = sorted(set(
        [int(s + stats3[i, 2] / 2) for i in range(1, n3) for stats3 in [None]] +
        [c + 2 * (bar_w + 1) for c in gc1_cxs if c > 600]
    )) if False else None
    # detected GC3 already:
    n3, _, s3, _ = cv2.connectedComponentsWithStats(gc3, connectivity=8)
    gc3_detected = sorted([int(s3[i, 0] + s3[i, 2] / 2) for i in range(1, n3) if s3[i, 4] > 5000])
    gc3_all = sorted(set(gc3_detected + [c + 2 * (bar_w + 1) for c in gc1_cxs if c > 600]))

    def detect(cxs):
        return [{"cx": cx, "top": find_bar_top(cx)} for cx in cxs if find_bar_top(cx) is not None]

    gc1_bars = detect(gc1_cxs)
    gc2_bars = detect(gc2_cxs)
    gc3_bars = detect(gc3_all)

    def report(name, bars):
        out = []
        for b in bars:
            x_d = m_x * b["cx"] + b_x
            y_d = m_y * b["top"] + b_y
            out.append({"series": name, "temperature_C": round(x_d, 2), "mean_eggs": round(y_d, 2)})
        return out

    r1 = report("GC1", gc1_bars)
    r2 = report("GC2", gc2_bars)
    r3 = report("GC3", gc3_bars)
    rows = [(r["series"], r["temperature_C"], r["mean_eggs"]) for r in r1 + r2 + r3]
    write_csv(folder, rows, ["series", "temperature_C", "mean_eggs_per_female"])

    width = 0.25
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (s, c) in enumerate([(r1, "#444"), (r2, "#bbb"), (r3, "#888")]):
        xs, ys = [], []
        for t in [24, 27, 30]:
            m = [r for r in s if round(r["temperature_C"]) == t]
            if m:
                ys.append(m[0]["mean_eggs"])
                xs.append(t + (i - 1) * width)
        ax.bar(xs, ys, width=width, color=c, label=["GC1", "GC2", "GC3"][i], edgecolor="black")
    ax.set_xticks([24, 27, 30])
    ax.set_xlabel("Temperatures (°C)")
    ax.set_ylabel("Mean number of eggs")
    ax.set_ylim(0, 80)
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "small grouped bar chart, stippled GC2 fill",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": "§4a bar top via dark outline (horizontal run ≥40 of gray<160 in cx±28 band); GC2 stippled fill detected by outline, not by interior CC",
        "params": {"outline_dark_thr": 160, "min_run": 40, "search_band": "cx±28"},
        "counts": {"GC1": len(r1), "GC2": len(r2), "GC3": len(r3)},
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-88 — grayscale 3-shape scatter
# ========================================================================
def extract_el88():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-88"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m_x, b_x = 0.064303, -3.614709
    m_y, b_y = -0.001853, 1.053524

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:568, 56:980] = 1
    mask_area[280:400, 870:980] = 0

    black = ((gray < 50) & (hsv[:, :, 1] < 50)).astype(np.uint8) * 255 * mask_area
    black_pts = detect_filled(black, ker=4, min_area=10)

    # el-88 has NO fit curves — skip §3b. Direct CC on the remainder.
    all_dark = ((gray < 200) & (hsv[:, :, 1] < 50)).astype(np.uint8) * 255 * mask_area
    remainder = all_dark.copy()
    remainder[black > 0] = 0

    n, _, stats, cent = cv2.connectedComponentsWithStats(remainder, connectivity=8)
    gray_pts, diamond_pts = [], []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if not (6 <= w <= 25 and 6 <= h <= 25):
            continue
        ar = max(w, h) / max(min(w, h), 1)
        if ar > 2.5:
            continue
        density = a / (w * h)
        cx, cy = cent[i]
        if density > 0.55 and a > 30:
            gray_pts.append((cx, cy))
        elif 0.15 < density < 0.5 and 12 <= a <= 90:
            diamond_pts.append((cx, cy))

    final_diamonds = []
    for cx, cy in diamond_pts:
        nb = any(abs(cx - bx) < 5 and abs(cy - by) < 5 for bx, by in black_pts)
        ng = any(abs(cx - gx) < 5 and abs(cy - gy) < 5 for gx, gy in gray_pts)
        if not nb and not ng:
            final_diamonds.append((cx, cy))

    def to_data(pts):
        return [(round(m_x * cx + b_x, 2), round(m_y * cy + b_y, 4)) for cx, cy in pts]

    series = {"24C": to_data(black_pts), "27C": to_data(gray_pts), "30C": to_data(final_diamonds)}
    rows = [(s, x, y) for s, pts in series.items() for x, y in pts]
    write_csv(folder, rows, ["series", "age_days", "survival_proportion"])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter([p[0] for p in series["24C"]], [p[1] for p in series["24C"]], c="black", marker="o", s=40, label="24°C")
    ax.scatter([p[0] for p in series["27C"]], [p[1] for p in series["27C"]], c="#888", marker="s", s=40, label="27°C")
    ax.scatter([p[0] for p in series["30C"]], [p[1] for p in series["30C"]],
               facecolors="none", edgecolors="black", marker="D", s=50, label="30°C")
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Age of females in days")
    ax.set_ylabel("Survival")
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "grayscale 3-shape scatter (filled disk / gray square / open diamond)",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": (
            "§2b grayscale-shape classifier: (1) detect 24°C disks via gray<50 + 4×4 erode + CC; "
            "(2) subtract disks from wider gray<200 mask (no fit-curve subtraction needed here); "
            "(3) CC classify by density (>0.55 + area>30 → square; 0.15-0.5 + area 12-90 → diamond); "
            "(4) dedup diamonds against disks/squares within 5px."
        ),
        "params": {"erode_kernel_for_disks": "4×4", "density_square": ">0.55", "density_diamond": "0.15-0.5"},
        "counts": {s: len(p) for s, p in series.items()},
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-94 — 3-series scatter + 3 fit curves (the hard one)
# ========================================================================
def extract_el94():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-94"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m_x, b_x = 0.056547, -3.174709
    m_y, b_y = -0.000097, 0.987312

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:590, 56:960] = 1
    mask_area[200:470, 700:960] = 0

    black = ((gray < 50) & (hsv[:, :, 1] < 50)).astype(np.uint8) * 255 * mask_area
    black_pts = detect_filled(black, ker=3, min_area=5)

    all_dark = ((gray < 200) & (hsv[:, :, 1] < 50)).astype(np.uint8) * 255 * mask_area
    remainder = all_dark.copy()
    remainder[black > 0] = 0
    cleaned = subtract_curves(remainder, thin_h=3, marker_span=(4, 13))

    n, _, stats, cent = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    gray_pts, diamond_pts = [], []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if not (5 <= w <= 25 and 5 <= h <= 25):
            continue
        ar = max(w, h) / max(min(w, h), 1)
        if ar > 2.5:
            continue
        density = a / (w * h)
        cx, cy = cent[i]
        if density > 0.55 and a > 25:
            gray_pts.append((cx, cy))
        elif 0.15 < density < 0.5 and 10 <= a <= 90:
            diamond_pts.append((cx, cy))

    final_diamonds = []
    for cx, cy in diamond_pts:
        nb = any(abs(cx - bx) < 5 and abs(cy - by) < 5 for bx, by in black_pts)
        ng = any(abs(cx - gx) < 5 and abs(cy - gy) < 5 for gx, gy in gray_pts)
        if not nb and not ng:
            final_diamonds.append((cx, cy))

    def to_data(pts):
        return [(round(m_x * cx + b_x, 2), round(m_y * cy + b_y, 4)) for cx, cy in pts]

    series = {"24C": to_data(black_pts), "27C": to_data(gray_pts), "30C": to_data(final_diamonds)}
    rows = [(s, x, y) for s, pts in series.items() for x, y in pts]
    write_csv(folder, rows, ["series", "age_days", "daily_survival_p"])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter([p[0] for p in series["24C"]], [p[1] for p in series["24C"]], c="black", marker="o", s=40, label="24°C")
    ax.scatter([p[0] for p in series["27C"]], [p[1] for p in series["27C"]], c="#888", marker="s", s=40, label="27°C")
    ax.scatter([p[0] for p in series["30C"]], [p[1] for p in series["30C"]],
               facecolors="none", edgecolors="black", marker="D", s=50, label="30°C")
    ax.set_xlim(0, 50)
    ax.set_ylim(0.93, 0.98)
    ax.set_xlabel("Age of females in days")
    ax.set_ylabel("Probability of daily survival p")
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "grayscale 3-shape scatter + 3 fit curves (same gray tones)",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": (
            "Same pipeline as el-88, but the fit-curve subtraction (§3b) is essential here: without it, "
            "the dotted curves register as phantom open markers. Known limitation: filled gray squares "
            "sitting on the solid 27°C fit curve fuse into elongated CCs and are still under-counted."
        ),
        "params": {"thin_h": 3, "marker_span": [4, 13]},
        "counts": {s: len(p) for s, p in series.items()},
        "known_undercount": "27°C squares on the solid 27°C fit curve.",
    }
    save_meta(folder, meta)
    return folder, meta


# ========================================================================
# el-100 — colored scatter + dashed fit lines
# ========================================================================
def extract_el100():
    folder = "e9d2f862-1273-47c2-a91f-95b0c6c6f8bd__el-100"
    img = cv2.imread(f"{BASE}/{folder}/image.png")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m_x, b_x = 0.001318, -0.073362
    m_y, b_y = -0.049080, 27.995901

    mask_area = np.zeros(img.shape[:2], dtype=np.uint8)
    mask_area[20:570, 56:840] = 1
    mask_area[150:540, 760:840] = 0

    blue = cv2.inRange(hsv, (100, 100, 50), (130, 255, 255)) * mask_area
    green = cv2.inRange(hsv, (40, 60, 30), (85, 255, 220)) * mask_area
    red1 = cv2.inRange(hsv, (0, 100, 60), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 100, 60), (180, 255, 255))
    red = cv2.bitwise_or(red1, red2) * mask_area

    def detect_markers(mask, single_area=80, kernel=4):
        er = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel, kernel)))
        n, labels, stats, cent = cv2.connectedComponentsWithStats(er, connectivity=8)
        blobs = []
        for i in range(1, n):
            x, y, w, h, a = stats[i]
            if a < 15:
                continue
            ar = max(w, h) / max(min(w, h), 1)
            if ar > 2.5:
                continue
            density = a / (w * h)
            if density < 0.25 and a > 200:
                continue
            n_est = max(1, round(a / (single_area * 0.5)))
            bbox_aspect = max(w, h) / max(min(w, h), 1)
            if n_est == 1 or bbox_aspect > 4 or density < 0.45:
                blobs.append((cent[i][0], cent[i][1]))
            else:
                ys, xs = np.where(labels == i)
                if len(xs) < n_est:
                    continue
                km = KMeans(n_clusters=n_est, random_state=0, n_init=4).fit(np.column_stack([xs, ys]))
                for c in km.cluster_centers_:
                    blobs.append((c[0], c[1]))
        blobs.sort()
        return [(round(m_x * cx + b_x, 3), round(m_y * cy + b_y, 2)) for cx, cy in blobs]

    series = {
        "24C": detect_markers(blue, 80, 4),
        "27C": detect_markers(green, 70, 4),
        "30C": detect_markers(red, 80, 3),
    }
    rows = [(s, x, y) for s, pts in series.items() for x, y in pts]
    write_csv(folder, rows, ["series", "parity_rate", "life_expectancy_50pct"])

    fig, ax = plt.subplots(figsize=(10, 6))
    sty = {"24C": ("#1f6fd0", "o"), "27C": ("#1e7e1e", "s"), "30C": ("#d62020", "D")}
    for s, pts in series.items():
        c, mk = sty[s]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=c, marker=mk, s=40, label=s)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 28)
    ax.set_xlabel("Parity rate")
    ax.set_ylabel("Life exp for 50% of females")
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{BASE}/{folder}/extracted/replot.png", dpi=120)
    plt.close()

    meta = {
        "chart_type": "3-color scatter + 3 dashed/solid fit lines in same colors",
        "calibration": {"x_axis": f"value = {m_x}·col + {b_x}", "y_axis": f"value = {m_y}·row + {b_y}"},
        "method": (
            "§2 scatter + aspect-ratio dashed-fragment filter (>2.5) + solid-line density+area filter "
            "(density<0.25 ∧ area>200 → line) + k-means split only when CC is square-ish and dense."
        ),
        "params": {
            "erode_kernel": {"blue": 4, "green": 4, "red": 3},
            "aspect_ratio_max": 2.5,
            "solid_line_density_max": 0.25,
            "solid_line_area_min": 200,
        },
        "counts": {s: len(p) for s, p in series.items()},
        "known_undercount": "Blue markers that sit on the dashed blue fit line classify as dash fragments.",
    }
    save_meta(folder, meta)
    return folder, meta


for fn in [extract_el60a, extract_el60b, extract_el62, extract_el75, extract_el80, extract_el88, extract_el94, extract_el100]:
    folder, meta = fn()
    name = folder.split("__")[-1]
    print(f"{name}: counts={meta['counts']}")
    results_summary[name] = meta
