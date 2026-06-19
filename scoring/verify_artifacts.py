#!/usr/bin/env python3
"""verify_artifacts.py — per-element image-matching verifier.

Implements the methodology decided in `Decision-Pixel-Frame-Verification-2026-06-18`
and exercised in ad-hoc form across the three TDD passes (el-60-a, el-88, el-94).
For each chart in an extractor's results dir, this script:

  1. Derives the list of per-element ARTIFACTS the extractor has committed to,
     by walking calibration.json (frame, axes, ticks, legend), data.csv
     (markers, line samples, bar tops, error caps), and chart_metadata.json
     (series legend → color masks).
  2. Runs a per-type PREDICATE that checks whether the artifact's claimed
     pixel position is consistent with what image.png actually shows there,
     within a per-type EPSILON tolerance.
  3. Emits `verification.json` summarising pass/fail per artifact + per type.
  4. Renders `verify_overlay.png`: every artifact drawn on a copy of
     image.png, colored green for pass and red for fail.

Exit code: 0 if every artifact in every chart passed, 1 otherwise.

Usage:
    python3 scoring/verify_artifacts.py <results_root>

  e.g. python3 scoring/verify_artifacts.py extractors/graph-data-extraction/results-v3

Optional flags:
    --chart <id>     verify only the named chart
    --warn-only      print failures but exit 0
    --no-overlay     skip rendering verify_overlay.png
"""
import argparse
import csv
import json
import os
import sys
import cv2
import numpy as np


# Per-element epsilon table (task 16).
# These are the tolerances each predicate uses when checking whether an
# artifact's claimed pixel position matches the source image. Chosen from
# the three TDD-pass measurements: calibration drift was ≤ 1.7 px std across
# charts (so 2-3 px for axis-like artifacts); marker glyph-presence found
# all markers within 1.5 px (so 3 px is permissive enough); bar tops and
# error caps were measured to ≈ 2 px in the el-80 work.
EPSILON_PX = {
    "frame_box":       2,    # plot frame rectangle
    "axis_line":       2,    # the y/x axis stroke
    "tick_center":     5,    # tick label centroid (text bbox is ~10 px wide)
    "legend_box":     15,    # legend bounding box (recorded box is often tight)
    "marker_centroid": 3,    # scatter / bar marker centroid
    "line_endpoint":  10,    # trend-line endpoints (lines can be drawn past)
    "line_sample":     3,    # per-column curve sample
    "bar_top":         2,    # top edge of a bar fill
    "error_cap":       3,    # horizontal cap of an error bar
}


# ---------- Artifact derivation ----------

def derive_artifacts(chart_dir):
    """Read calibration.json, data.csv (layered), chart_metadata.json and
    return a list of per-element artifacts with id, type, position, and
    metadata. Each artifact will then be passed to its type's predicate.
    """
    arts = []
    cal_path = os.path.join(chart_dir, "calibration.json")
    data_path = os.path.join(chart_dir, "data.csv")
    md_path = os.path.join(chart_dir, "chart_metadata.json")
    if not os.path.exists(cal_path) or not os.path.exists(data_path):
        return None, "missing calibration.json or data.csv"
    with open(cal_path) as f:
        cal = json.load(f)
    md = {}
    if os.path.exists(md_path):
        with open(md_path) as f:
            md = json.load(f)

    pf = cal["plot_frame_box"]
    de = cal.get("data_extent_box", pf)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]

    # 1. Frame box.
    arts.append({"type": "frame_box", "id": "main",
                  "left": pf["left"], "top": pf["top"],
                  "right": pf["right"], "bottom": pf["bottom"]})

    # 2. Axis lines (vertical y-axis at frame.left, horizontal x-axis at frame.bottom).
    arts.append({"type": "axis_line", "id": "y_axis",
                  "orientation": "vertical", "fixed": pf["left"],
                  "extent": [pf["top"], pf["bottom"]]})
    arts.append({"type": "axis_line", "id": "x_axis",
                  "orientation": "horizontal", "fixed": pf["bottom"],
                  "extent": [pf["left"], pf["right"]]})

    # 3. Legend box (when calibration recorded one).
    legend = cal.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    if legend:
        arts.append({"type": "legend_box", "id": "main",
                      "top": legend[0], "bottom": legend[1],
                      "left": legend[2], "right": legend[3]})

    # 4. Tick centers — predict from labeled tick values.
    # X ticks: read from data range; we assume integer / readable major ticks.
    dr = cal["data_range"]
    # Use 5-6 evenly spaced ticks by default
    def axis_ticks(lo, hi):
        if lo is None or hi is None:
            return []
        span = hi - lo
        if span <= 0:
            return []
        # Pick a step that gives ~5-8 ticks
        for step in (1, 2, 5, 10, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5):
            n = int(span / step) + 1
            if 4 <= n <= 10:
                start = step * round(lo / step)
                return [start + i * step for i in range(n) if lo <= start + i * step <= hi]
        return [lo, hi]

    # Tick label centroids sit ~14-22 px outside the axis. Use a wider
    # window in the predicate rather than guessing the exact offset — the
    # epsilon for tick_center already accounts for this.
    x_label_row = pf["bottom"] + 18
    y_label_col = pf["left"] - 30
    for tv in axis_ticks(dr.get("x_min"), dr.get("x_max")):
        col = (tv - bx) / mx
        arts.append({"type": "tick_center", "id": f"x_{tv}", "axis": "x",
                      "col": int(col), "row": x_label_row,
                      "value": round(tv, 4)})
    for tv in axis_ticks(dr.get("y_min"), dr.get("y_max")):
        row = (tv - by) / my
        arts.append({"type": "tick_center", "id": f"y_{tv}", "axis": "y",
                      "col": y_label_col, "row": int(row),
                      "value": round(tv, 4)})

    # 5. Markers, lines, bars from data.csv layered schema.
    with open(data_path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return arts, None
    header = rows[0].keys()
    lc = "layer_type" if "layer_type" in header else None
    xc = next((c for c in ("x", "time_days", "temperature_C", "age_days",
                            "parity_rate") if c in header), None)
    yc = next((c for c in ("y", "percentage_parous_females", "max_parity_rate",
                            "mean_duration_days", "mean_GC_duration",
                            "mean_eggs_per_female", "survival_proportion",
                            "daily_survival_p", "life_expectancy_50pct")
                if c in header), None)
    sc = next((c for c in ("series", "point") if c in header), None)
    lo_c = next((c for c in ("y_lo", "yerr_lo") if c in header), None)
    hi_c = next((c for c in ("y_hi", "yerr_hi") if c in header), None)
    if xc is None or yc is None:
        return arts, None

    # Per-series color lookup from chart_metadata.json
    series_colors = {}
    for s in md.get("series_legend", []):
        sid = s.get("series_id", "")
        if "color" in s and isinstance(s["color"], str) and s["color"].startswith("#"):
            try:
                h = s["color"].lstrip("#")
                rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                series_colors[sid] = rgb
            except ValueError:
                pass

    line_pts_by_series = {}
    for r in rows:
        try:
            x = float(r[xc]); y = float(r[yc])
        except (TypeError, ValueError):
            continue
        col = (x - bx) / mx; row = (y - by) / my
        series = r.get(sc, "default") if sc else "default"
        layer = (r.get(lc) or "Scatter Plot") if lc else "Scatter Plot"
        if "Line" in layer or "Spline" in layer:
            line_pts_by_series.setdefault(series, []).append((col, row, x, y))
            continue
        # Scatter Plot or Grouped Column Chart → marker_centroid / bar_top
        if "Column" in layer or "Bar" in layer:
            arts.append({"type": "bar_top", "id": f"{series}_{x}",
                          "series": series, "x": x, "y": y,
                          "col": int(col), "row": int(row),
                          "color": series_colors.get(series)})
            # Optional error caps
            if lo_c and r.get(lo_c) and hi_c and r.get(hi_c):
                try:
                    y_lo = float(r[lo_c]); y_hi = float(r[hi_c])
                    row_lo = (y_lo - by) / my
                    row_hi = (y_hi - by) / my
                    arts.append({"type": "error_cap", "id": f"{series}_{x}_upper",
                                  "series": series, "x": x, "y": y_hi,
                                  "col": int(col), "row": int(row_hi),
                                  "side": "upper"})
                    arts.append({"type": "error_cap", "id": f"{series}_{x}_lower",
                                  "series": series, "x": x, "y": y_lo,
                                  "col": int(col), "row": int(row_lo),
                                  "side": "lower"})
                except ValueError:
                    pass
        else:
            arts.append({"type": "marker_centroid", "id": f"{series}_{x}_{y}",
                          "series": series, "x": x, "y": y,
                          "col": int(col), "row": int(row),
                          "color": series_colors.get(series)})

    # 6. Line graphs / spline curves → endpoints + interior samples.
    for series, pts in line_pts_by_series.items():
        pts.sort()
        # Endpoints
        for tag, (col, row, x, y) in [("left", pts[0]), ("right", pts[-1])]:
            arts.append({"type": "line_endpoint",
                          "id": f"{series}_{tag}",
                          "series": series, "x": x, "y": y,
                          "col": int(col), "row": int(row),
                          "color": series_colors.get(series)})
        # A few mid samples (skip endpoints already covered)
        if len(pts) > 4:
            for i in range(1, 5):
                k = int(i * len(pts) / 5)
                col, row, x, y = pts[k]
                arts.append({"type": "line_sample",
                              "id": f"{series}_mid_{i}",
                              "series": series, "x": x, "y": y,
                              "col": int(col), "row": int(row),
                              "color": series_colors.get(series)})
    return arts, None


# ---------- Predicates ----------

def in_image(col, row, H, W):
    return 0 <= col < W and 0 <= row < H


def check_frame_box(img, art, eps):
    """A frame_box passes if at least one of its four edges has continuous
    dark coverage. Some charts only draw axis lines (left + bottom) — the
    top and right edges may be dotted, light, or absent.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    l, t, r, b = art["left"], art["top"], art["right"], art["bottom"]
    def edge_dark_fraction(coords):
        d = 0; n = 0
        for c, rr in coords:
            for delta in range(-eps, eps + 1):
                if in_image(c + delta if abs(delta) > 0 else c, rr, H, W):
                    ok = False
                    for dc in range(-eps, eps + 1):
                        for dr in range(-eps, eps + 1):
                            if (in_image(c + dc, rr + dr, H, W) and
                                    gray[rr + dr, c + dc] < 150):
                                ok = True; break
                        if ok: break
                    n += 1
                    if ok: d += 1
                    break
        return d / max(1, n), n
    edges = {}
    edges["top"]    = edge_dark_fraction([(c, t) for c in range(max(0, l), min(W, r + 1), 2)])
    edges["bottom"] = edge_dark_fraction([(c, b) for c in range(max(0, l), min(W, r + 1), 2)])
    edges["left"]   = edge_dark_fraction([(l, rr) for rr in range(max(0, t), min(H, b + 1), 2)])
    edges["right"]  = edge_dark_fraction([(r, rr) for rr in range(max(0, t), min(H, b + 1), 2)])
    fracs = {k: round(v[0], 3) for k, v in edges.items()}
    # Pass if at least 2 of 4 edges have ≥ 70 % coverage (typical: left+bottom).
    n_good = sum(1 for f in fracs.values() if f >= 0.7)
    return n_good >= 2, {"edges": fracs, "n_good_edges": n_good}


def check_axis_line(img, art, eps):
    """An axis_line passes if the stroke at its fixed coord has dark pixels."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    f = art["fixed"]; e0, e1 = art["extent"]
    n_dark = 0; n_total = 0
    if art["orientation"] == "vertical":
        for r in range(max(0, e0), min(H, e1 + 1)):
            best_dark = False
            for d in range(-eps, eps + 1):
                c = f + d
                if in_image(c, r, H, W) and gray[r, c] < 150:
                    best_dark = True; break
            n_total += 1
            if best_dark:
                n_dark += 1
    else:
        for c in range(max(0, e0), min(W, e1 + 1)):
            best_dark = False
            for d in range(-eps, eps + 1):
                rr = f + d
                if in_image(c, rr, H, W) and gray[rr, c] < 150:
                    best_dark = True; break
            n_total += 1
            if best_dark:
                n_dark += 1
    frac = n_dark / max(1, n_total)
    return frac > 0.7, {"axis_dark_fraction": round(frac, 3)}


def check_tick_center(img, art, eps):
    """A tick_center passes if there's a dark text cluster within a wider
    label-text window of the claimed (col, row). The vertical band is
    intentionally tall because the exact label row varies by font and the
    predictor cannot guess it precisely; the centroid column should be
    near the prediction."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    c, r = art["col"], art["row"]
    half_c = max(eps, 12)
    half_r = 18  # full text-band height ≈ 36 px
    c0 = max(0, c - half_c); c1 = min(W, c + half_c + 1)
    r0 = max(0, r - half_r); r1 = min(H, r + half_r + 1)
    if c0 >= c1 or r0 >= r1:
        return False, {"reason": "out of image"}
    band = gray[r0:r1, c0:c1]
    dark = (band < 100).sum()
    return dark >= 8, {"dark_pixels": int(dark)}


def check_legend_box(img, art, eps):
    """A legend_box passes if the box mostly contains non-data pixels (text or
    swatches), not the chart's data ink. We approximate by checking that the
    box interior has some dark text content but isn't dominated by series
    colors filling the whole region."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    t, b, l, r = art["top"], art["bottom"], art["left"], art["right"]
    box = gray[max(0, t):min(H, b + 1), max(0, l):min(W, r + 1)]
    if box.size == 0:
        return False, {"reason": "empty box"}
    white_frac = (box > 220).sum() / box.size
    dark_frac = (box < 100).sum() / box.size
    # Legend interior should be mostly white with some dark text/swatches.
    return 0.4 < white_frac and 0.02 < dark_frac < 0.40, {
        "white_frac": round(float(white_frac), 3),
        "dark_frac": round(float(dark_frac), 3),
    }


def check_marker_centroid(img, art, eps):
    """A marker_centroid passes if there's a marker glyph in a window around
    the claimed pixel position."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, W = gray.shape
    c, r = art["col"], art["row"]
    half = max(eps, 5)
    c0 = max(0, c - half); c1 = min(W, c + half + 1)
    r0 = max(0, r - half); r1 = min(H, r + half + 1)
    if c0 >= c1 or r0 >= r1:
        return False, {"reason": "out of image"}
    win = gray[r0:r1, c0:c1]
    sat = hsv[r0:r1, c0:c1, 1]
    dark = ((win < 50) & (sat < 50)).sum()
    gray_sq = ((win >= 60) & (win <= 210) & (sat < 50)).sum()
    colored = (sat > 80).sum()
    glyph_px = int(dark + gray_sq + colored)
    if glyph_px < 6:
        return False, {"glyph_px": glyph_px, "reason": "window background"}
    return True, {"glyph_px": glyph_px}


def check_line_endpoint(img, art, eps):
    """A line_endpoint passes if the source has a stroke at the claimed
    (col, row), within a wider epsilon to absorb endpoint imprecision."""
    return check_line_sample(img, art, eps)


def check_line_sample(img, art, eps):
    """A line_sample passes if the source has a dark / series-colored stroke
    within ±eps of (col, row)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    c, r = art["col"], art["row"]
    half = max(eps, 3)
    c0 = max(0, c - half); c1 = min(W, c + half + 1)
    r0 = max(0, r - half); r1 = min(H, r + half + 1)
    if c0 >= c1 or r0 >= r1:
        return False, {"reason": "out of image"}
    win = gray[r0:r1, c0:c1]
    n_dark = int((win < 120).sum())
    return n_dark >= 3, {"dark_in_window": n_dark}


def check_bar_top(img, art, eps):
    """A bar_top passes if a horizontal transition (light → dark/colored)
    occurs at row ±eps within a small horizontal band centred on col."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    c, r = art["col"], art["row"]
    band_half = 15
    c0 = max(0, c - band_half); c1 = min(W, c + band_half + 1)
    # Sample 3 rows above and 3 below; difference in mean brightness should
    # be large at the bar top.
    if not (eps + 3 < r < H - eps - 3):
        return False, {"reason": "row out of range"}
    above = gray[r - eps - 3: r - eps, c0:c1].mean()
    below = gray[r + eps: r + eps + 3, c0:c1].mean()
    delta = float(above - below)
    return delta > 25, {"transition_delta": round(delta, 1)}


def check_error_cap(img, art, eps):
    """An error_cap passes if a short horizontal dark run exists at row ±eps
    in a narrow column band around col."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    c, r = art["col"], art["row"]
    band_w = 12
    c0 = max(0, c - band_w); c1 = min(W, c + band_w + 1)
    best_run = 0
    for d in range(-eps, eps + 1):
        rr = r + d
        if not in_image(c0, rr, H, W):
            continue
        strip = gray[rr, c0:c1]
        run = max_run = 0
        for v in strip:
            if v < 120:
                run += 1; max_run = max(max_run, run)
            else:
                run = 0
        best_run = max(best_run, max_run)
    return best_run >= 4, {"max_horizontal_dark_run": int(best_run)}


PREDICATES = {
    "frame_box":       check_frame_box,
    "axis_line":       check_axis_line,
    "tick_center":     check_tick_center,
    "legend_box":      check_legend_box,
    "marker_centroid": check_marker_centroid,
    "line_endpoint":   check_line_endpoint,
    "line_sample":     check_line_sample,
    "bar_top":         check_bar_top,
    "error_cap":       check_error_cap,
}


# ---------- Overlay ----------

OVERLAY_COLOR_PASS = (0, 200, 0)
OVERLAY_COLOR_FAIL = (0, 0, 220)


def draw_overlay(img, results):
    out = img.copy()
    for r in results:
        if "_skip" in r:
            continue
        color = OVERLAY_COLOR_PASS if r["pass"] else OVERLAY_COLOR_FAIL
        t = r["type"]
        if t == "frame_box":
            cv2.rectangle(out,
                          (r["left"], r["top"]),
                          (r["right"], r["bottom"]),
                          color, 1)
        elif t == "axis_line":
            if r["orientation"] == "vertical":
                cv2.line(out, (r["fixed"], r["extent"][0]),
                          (r["fixed"], r["extent"][1]), color, 1)
            else:
                cv2.line(out, (r["extent"][0], r["fixed"]),
                          (r["extent"][1], r["fixed"]), color, 1)
        elif t == "legend_box":
            cv2.rectangle(out,
                          (r["left"], r["top"]),
                          (r["right"], r["bottom"]),
                          color, 1)
        elif t in ("tick_center", "marker_centroid", "line_endpoint",
                    "line_sample", "bar_top", "error_cap"):
            cv2.circle(out, (r["col"], r["row"]), 4, color, 1)
            cv2.drawMarker(out, (r["col"], r["row"]), color,
                            markerType=cv2.MARKER_CROSS, markerSize=8,
                            thickness=1)
    return out


# ---------- Driver ----------

def verify_chart(chart_dir, render_overlay=True):
    img_path_candidates = [
        os.path.join(chart_dir, "image.png"),  # if extractor copied it
    ]
    # otherwise, derive from corpus location
    cal_path = os.path.join(chart_dir, "calibration.json")
    if not os.path.exists(cal_path):
        return {"error": "no calibration.json"}
    img = None
    for c in img_path_candidates:
        if os.path.exists(c):
            img = cv2.imread(c); break
    if img is None:
        # Walk up to find the corpus image; expects path
        # extractors/<extr>/results-N/<corpus>/<chart>/
        parts = chart_dir.rstrip("/").split("/")
        if "extractors" in parts:
            ei = parts.index("extractors")
            corpus = parts[ei + 3]; chart = parts[ei + 4]
            repo = "/".join(parts[:ei])
            img_path = os.path.join(repo, "corpora", corpus, "charts", chart,
                                     "image.png")
            if os.path.exists(img_path):
                img = cv2.imread(img_path)
    if img is None:
        return {"error": "no image.png found"}

    arts, err = derive_artifacts(chart_dir)
    if err:
        return {"error": err}

    results = []
    for art in arts:
        t = art["type"]
        eps = EPSILON_PX.get(t, 5)
        pred = PREDICATES.get(t)
        if pred is None:
            results.append({**art, "_skip": True, "reason": "no predicate"})
            continue
        try:
            ok, info = pred(img, art, eps)
        except Exception as e:
            results.append({**art, "pass": False, "epsilon_px": eps,
                             "error": str(e)})
            continue
        rec = {**art, "pass": bool(ok), "epsilon_px": eps, "info": info}
        results.append(rec)

    # Summary by type
    by_type = {}
    for r in results:
        if r.get("_skip"): continue
        t = r["type"]
        if t not in by_type:
            by_type[t] = {"pass": 0, "fail": 0}
        by_type[t]["pass" if r.get("pass") else "fail"] += 1
    total_pass = sum(v["pass"] for v in by_type.values())
    total_fail = sum(v["fail"] for v in by_type.values())

    out_json = {
        "n_artifacts": len(arts),
        "summary": {"pass": total_pass, "fail": total_fail, "by_type": by_type},
        "epsilon_px": EPSILON_PX,
        "results": results,
    }
    with open(os.path.join(chart_dir, "verification.json"), "w") as f:
        json.dump(out_json, f, indent=2, default=str)

    if render_overlay:
        overlay = draw_overlay(img, results)
        cv2.imwrite(os.path.join(chart_dir, "verify_overlay.png"), overlay)

    return out_json


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("results_root")
    ap.add_argument("--chart", default=None)
    ap.add_argument("--warn-only", action="store_true")
    ap.add_argument("--no-overlay", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.results_root)
    if not os.path.isdir(root):
        print(f"Not a directory: {root}", file=sys.stderr); sys.exit(2)

    chart_dirs = []
    for corpus in sorted(os.listdir(root)):
        cp = os.path.join(root, corpus)
        if not os.path.isdir(cp): continue
        for chart in sorted(os.listdir(cp)):
            if args.chart and chart != args.chart:
                continue
            cd = os.path.join(cp, chart)
            if os.path.isdir(cd):
                chart_dirs.append((corpus, chart, cd))
    if not chart_dirs:
        print(f"No chart dirs under {root}", file=sys.stderr); sys.exit(2)

    print(f"Per-element artifact verifier over {root}")
    print(f"{'corpus':<25} {'chart':<12} "
          f"{'frame':>6} {'axis':>6} {'tick':>6} {'leg':>5} {'marker':>7} "
          f"{'line':>6} {'bar':>5} {'cap':>5} {'total':>6}")
    print("-" * 100)
    grand_pass = grand_fail = 0
    for corpus, chart, cd in chart_dirs:
        res = verify_chart(cd, render_overlay=not args.no_overlay)
        if "error" in res:
            print(f"{corpus:<25} {chart:<12} ERROR  {res['error']}")
            continue
        by = res["summary"]["by_type"]
        def fmt(t):
            if t not in by: return "-"
            return f"{by[t]['pass']}/{by[t]['pass']+by[t]['fail']}"
        total_pass = res["summary"]["pass"]
        total_fail = res["summary"]["fail"]
        grand_pass += total_pass; grand_fail += total_fail
        print(f"{corpus:<25} {chart:<12} "
              f"{fmt('frame_box'):>6} "
              f"{fmt('axis_line'):>6} "
              f"{fmt('tick_center'):>6} "
              f"{fmt('legend_box'):>5} "
              f"{fmt('marker_centroid'):>7} "
              f"{fmt('line_endpoint') + '+' + fmt('line_sample').split('/')[0]:>6} "
              f"{fmt('bar_top'):>5} "
              f"{fmt('error_cap'):>5} "
              f"{total_pass}/{total_pass + total_fail}")
    print("-" * 100)
    print(f"GRAND  pass={grand_pass}  fail={grand_fail}  "
          f"rate={grand_pass / max(1, grand_pass + grand_fail):.3f}")
    if grand_fail and not args.warn_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
