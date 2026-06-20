#!/usr/bin/env python3
"""score_data.py - full-fidelity rubric for extracted scientific data.

Where `score.py` grades only scatter / bar points (and excludes trend lines
and fit curves from ground truth), this scorer grades every layer of
extracted data that the source chart contains:

  - **scatter / bar means**: pair-match within per-axis tolerance (same as
    score.py).
  - **trend lines / fit curves**: resample the prediction at GT x values via
    linear interpolation, then pair-match each GT (x, y) against the
    interpolated prediction within y_tol. GT x values outside the prediction's
    coverage range count as FN.
  - **error bars**: when GT carries error_y_plus / error_y_minus on a row,
    check that the matched extractor row has y_lo / y_hi within y_tol of
    GT's mean ± error_y_plus|minus. One TP per row when both bars match,
    one FN per row when either is missing or wrong.

The combined F1 is computed over the union of TP / FN / FP across all three
layer types. The per-layer F1 breakdown is also emitted in the output JSON.

The extractor's data lives in:

  - `data.csv` — scatter points or bar means; optional `y_lo` / `y_hi`
    columns for error bars.
  - Any other CSV in the chart dir (e.g. `trend_line.csv`, `fit_curves.csv`,
    `if_curves.csv`, `lines.csv`) — line / curve data, with at least an x
    and a y column and optionally a series column.

Usage:
    python3 scoring/score_data.py <corpus> <extractor> [--results-dir results-v2]
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
import numpy as np


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# --- Tolerance model (r6, refactored) ---
#
# Defaults are FRACTIONS of each chart's GT axis range, derived per-chart so
# the same numbers work across aedes / synthetic / owid without hand-curation.
#
# Per-chart overrides exist for two real cases:
#   - categorical x where 0-indexed vs 1-indexed group convention is ambiguous:
#     use a fixed absolute x_tol so a +/- 1 shift counts as a TP (synthetic 3,
#     synthetic 5, el-62, el-80).
#   - log-y or otherwise-large-dynamic-range axes where 2 % of axis range is
#     unhelpful (too lenient at small y, too tight at large y): switch to a
#     relative-error model |dy| / max(|gt|, eps) <= y_rel_tol.
#
# Everything else inherits the defaults.

DEFAULT_X_TOL_FRAC = 0.02   # 2 % of GT x-range
DEFAULT_Y_TOL_FRAC = 0.02   # 2 % of GT y-range
DEFAULT_Y_REL_TOL  = 0.01   # 1 % relative error for log-y overrides

TOL_OVERRIDES = {
    # Categorical x: 0-indexed vs 1-indexed group convention slack.
    "el-62":                   {"x_tol_abs": 1.5},
    "el-80":                   {"x_tol_abs": 1.5},
    "03-grouped-bar-errbars":  {"x_tol_abs": 1.5},
    "05-stacked-bar":          {"x_tol_abs": 1.5},
    # Log-y axes (or values that span many decades on a linear axis):
    # absolute fraction-of-range is too lenient at small y. Switch to
    # relative-error y matching.
    "04-log-y-line":           {"y_kind": "relative",
                                 "y_rel_tol": DEFAULT_Y_REL_TOL},
    "population":              {"y_kind": "relative",
                                 "y_rel_tol": DEFAULT_Y_REL_TOL},
    "annual-co2-emissions-per-country": {"y_kind": "relative",
                                          "y_rel_tol": DEFAULT_Y_REL_TOL},
}

# Floor for the relative-error denominator: pin against the chart's axis
# range so the relative test degrades gracefully at GT = 0 instead of blowing
# up. Set when tolerances are derived for a chart.
_REL_DENOM_FRAC = 0.001     # eps = max(|gt|, 0.1 % of y_range)

X_CANDIDATES = ["x", "time_days", "temperature_C", "age_days", "parity_rate"]
Y_CANDIDATES = ["y", "percentage_parous_females", "max_parity_rate",
                "mean_duration_days", "mean_GC_duration",
                "mean_eggs_per_female", "survival_proportion",
                "daily_survival_p", "life_expectancy_50pct"]
S_CANDIDATES = ["series", "point"]
ERR_LO_CANDIDATES = ["y_lo", "y_low", "yerr_lo", "y_err_lo"]
ERR_HI_CANDIDATES = ["y_hi", "y_high", "yerr_hi", "y_err_hi"]
ERR_SYM_CANDIDATES = ["yerr", "y_err"]


def canon(s):
    """Lowercase + strip non-alphanumeric for fuzzy series matching."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def find_col(header, candidates):
    for c in candidates:
        if c in header:
            return c
    return None


def _layer_bucket(layer):
    """Route a layer_type string into one of three buckets."""
    if "Line" in layer or "Spline" in layer:
        return "curves"
    if "Error" in layer or "ErrorBar" in layer or "errbar" in layer.lower():
        return "errbars"
    return "points"


def load_gt_split(gt_path):
    """Split GT rows by layer type into three buckets: points (scatter / bar
    tops), curves (line / spline / fit), and errbars (ErrorBarLayer rows).
    Returns (points, curves, errbars) — each a dict series -> list of dicts."""
    points = {}; curves = {}; errbars = {}
    with open(gt_path) as f:
        for r in csv.DictReader(f):
            try:
                x = float(r["x"]); y = float(r["y"])
            except (TypeError, ValueError):
                continue
            row = dict(r)
            row["_x"] = x; row["_y"] = y
            layer = (r.get("layer_type") or "").strip()
            series = (r.get("series") or "default").strip()
            bucket = _layer_bucket(layer)
            d = {"points": points, "curves": curves, "errbars": errbars}[bucket]
            d.setdefault(canon(series), []).append(row)
    for d in (points, curves, errbars):
        for k in d:
            d[k].sort(key=lambda rr: rr["_x"])
    return points, curves, errbars


def load_extractor_main(data_path):
    """Read data.csv. Returns (points, curves, errbars) — three dicts mapping
    series -> list of rows. Layered v3 schema (layer_idx, layer_type, …)
    routes Line Graph / Spline Chart rows to curves, ErrorBarLayer rows to
    errbars; everything else (or unlayered v1/v2 schemas) goes to points."""
    points, curves, errbars = {}, {}, {}
    if not os.path.exists(data_path):
        return points, curves, errbars
    with open(data_path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return points, curves, errbars
    header = rows[0].keys()
    xc = find_col(header, X_CANDIDATES)
    yc = find_col(header, Y_CANDIDATES)
    sc = find_col(header, S_CANDIDATES)
    lc = "layer_type" if "layer_type" in header else None
    lo_c = find_col(header, ERR_LO_CANDIDATES)
    hi_c = find_col(header, ERR_HI_CANDIDATES)
    sym_c = find_col(header, ERR_SYM_CANDIDATES)
    if xc is None or yc is None:
        return points, curves, errbars
    for r in rows:
        try:
            x = float(r[xc]); y = float(r[yc])
        except (TypeError, ValueError):
            continue
        s = canon(r.get(sc, "default") if sc else "default")
        row = {"_x": x, "_y": y}
        if lo_c and r.get(lo_c):
            try: row["_y_lo"] = float(r[lo_c])
            except ValueError: pass
        if hi_c and r.get(hi_c):
            try: row["_y_hi"] = float(r[hi_c])
            except ValueError: pass
        if sym_c and r.get(sym_c):
            try:
                e = float(r[sym_c])
                row["_y_lo"] = row.get("_y_lo", y - e)
                row["_y_hi"] = row.get("_y_hi", y + e)
            except ValueError: pass
        # Route by layer_type when present.
        layer = (r.get(lc) or "") if lc else ""
        bucket = _layer_bucket(layer)
        d = {"points": points, "curves": curves, "errbars": errbars}[bucket]
        d.setdefault(s, []).append(row)
    for d in (points, curves, errbars):
        for s in d:
            d[s].sort(key=lambda rr: rr["_x"])
    return points, curves, errbars


def load_extractor_curves(chart_dir):
    """Scan chart_dir for side-car CSVs (anything other than data.csv) and
    parse as curve points. Returns dict series -> sorted list of (x, y)."""
    out = {}
    pattern = os.path.join(chart_dir, "*.csv")
    for path in glob.glob(pattern):
        name = os.path.basename(path)
        if name in ("data.csv", "ground_truth.csv"):
            continue
        with open(path) as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        header = rows[0].keys()
        xc = find_col(header, ["x"] + X_CANDIDATES)
        yc = find_col(header, ["y"] + Y_CANDIDATES)
        sc = find_col(header, S_CANDIDATES)
        if xc is None or yc is None:
            continue
        default_series = canon(os.path.splitext(name)[0])
        for r in rows:
            try:
                x = float(r[xc]); y = float(r[yc])
            except (TypeError, ValueError):
                continue
            s = canon(r[sc]) if sc and r.get(sc) else default_series
            out.setdefault(s, []).append((x, y))
    for s in out:
        out[s].sort()
    return out


def map_series(mine_keys, gt_keys, chart_id):
    """Best-effort series mapping. Special-cases match score.py."""
    if chart_id == "el-60-b":
        gt_sorted = sorted(
            [(k, vs) for k, vs in gt_keys.items()],
            key=lambda kv: kv[1][0]["_x"] if kv[1] else 0,
        )
        order = ["24c", "27c", "30c"]
        return {mk: gt_sorted[order.index(mk)][0] for mk in mine_keys
                if mk in order and order.index(mk) < len(gt_sorted)}
    if chart_id == "el-75":
        return None  # caller pools all points
    # Pass 1: exact match wins outright.
    mapping = {}
    used_gt = set()
    for mk in mine_keys:
        if mk in gt_keys:
            mapping[mk] = mk
            used_gt.add(mk)
    # Pass 2: substring match, preferring longer GT keys (so "tunedjit"
    # picks "tunedjit" over "tuned"). Skip GT keys already claimed.
    for mk in mine_keys:
        if mk in mapping: continue
        candidates = [gk for gk in gt_keys
                       if gk not in used_gt and (mk in gk or gk in mk)]
        if candidates:
            gk = max(candidates, key=len)
            mapping[mk] = gk
            used_gt.add(gk)
    return mapping


def pair_points(mine_pts, gt_pts, x_tol, y_tols):
    """Greedy nearest-neighbor pair-match. Both inputs are list of (x, y).

    `y_tols` can be either:
      - scalar: same y_tol for every GT point (absolute mode), OR
      - callable: `y_tols(gy)` -> per-GT-point y_tol (relative mode)
    """
    used = [False] * len(mine_pts)
    pairs, fn = [], []
    for gx, gy in gt_pts:
        y_tol = y_tols(gy) if callable(y_tols) else y_tols
        if y_tol <= 0:
            fn.append((gx, gy)); continue
        best_d = float("inf"); best_i = None
        for i, (mx, my) in enumerate(mine_pts):
            if used[i]:
                continue
            d = max(abs(mx - gx) / x_tol, abs(my - gy) / y_tol)
            if d < best_d:
                best_d = d; best_i = i
        if best_i is not None and best_d <= 1.0:
            mx, my = mine_pts[best_i]
            used[best_i] = True
            pairs.append({"gt": (gx, gy), "mine": (mx, my)})
        else:
            fn.append((gx, gy))
    fp = [mine_pts[i] for i, u in enumerate(used) if not u]
    return len(pairs), len(fn), len(fp)


def derive_tolerances(chart_id, gt_pt, gt_cv, gt_eb):
    """Derive per-chart effective tolerances from GT axis ranges.

    Default is 2 % of GT axis range for both axes. Per-chart overrides:
      - `x_tol_abs`: fixed absolute x_tol (categorical-x convention slack)
      - `y_kind = "relative"`: switch y matching to relative-error
        `|dy| / max(|gy|, _REL_DENOM_FRAC * y_range) <= y_rel_tol`

    Returns dict with x_tol (scalar), y_tols (scalar or callable usable by
    pair_points), y_tol_curve(gy) (callable usable by score_curves_layer),
    kind, x_range, y_range, plus the human-readable y_tol_desc for telemetry.
    """
    all_y = []; all_x = []
    for d in (gt_pt, gt_cv, gt_eb):
        for rows in d.values():
            for r in rows:
                all_x.append(r["_x"]); all_y.append(r["_y"])
    if not all_x:
        return {"x_tol": 1.0, "y_tols": 0.05,
                "y_tol_curve": (lambda gy: 0.05),
                "kind": "fallback", "y_tol_desc": "fallback 0.05",
                "x_range": 0, "y_range": 0}
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    x_range = (x_max - x_min) if x_max > x_min else max(abs(x_max), 1.0)
    y_range = (y_max - y_min) if y_max > y_min else max(abs(y_max), 1.0)

    overrides = TOL_OVERRIDES.get(chart_id, {})

    x_tol = overrides.get("x_tol_abs") or (DEFAULT_X_TOL_FRAC * x_range)

    if overrides.get("y_kind") == "relative":
        rel = overrides.get("y_rel_tol", DEFAULT_Y_REL_TOL)
        eps = _REL_DENOM_FRAC * y_range
        def y_tol_fn(gy, _rel=rel, _eps=eps):
            return max(abs(gy), _eps) * _rel
        return {"x_tol": x_tol, "y_tols": y_tol_fn,
                "y_tol_curve": y_tol_fn, "kind": "relative",
                "y_rel_tol": rel,
                "y_tol_desc": (f"relative {rel*100:.1f}% (denom floor "
                                f"{eps:g})"),
                "x_range": x_range, "y_range": y_range}

    y_tol = overrides.get("y_tol_abs") or (DEFAULT_Y_TOL_FRAC * y_range)
    return {"x_tol": x_tol, "y_tols": y_tol,
            "y_tol_curve": (lambda gy, _y=y_tol: _y),
            "kind": "absolute", "y_tol_abs": y_tol,
            "y_tol_desc": f"abs {y_tol:g} ({DEFAULT_Y_TOL_FRAC*100:.1f}% of y_range {y_range:g})",
            "x_range": x_range, "y_range": y_range}


def score_points_layer(mine, gt, chart_id, x_tol, y_tols):
    """Score scatter / bar layer. `y_tols` per pair_points signature."""
    if chart_id == "el-75":
        # GT pools as "datapoints"; pool mine to match
        all_mine = []
        for vs in mine.values():
            for r in vs:
                all_mine.append((r["_x"], r["_y"]))
        gt_pooled = []
        for vs in gt.values():
            for r in vs:
                gt_pooled.append((r["_x"], r["_y"]))
        tp, fn, fp = pair_points(sorted(all_mine), sorted(gt_pooled),
                                  x_tol, y_tols)
        return {"tp": tp, "fn": fn, "fp": fp,
                "gt_n": len(gt_pooled), "mine_n": len(all_mine),
                "by_series": {}}
    mapping = map_series(mine, gt, chart_id) or {}
    by_series = {}
    tot_tp = tot_fn = tot_fp = 0
    tot_gt = tot_mine = 0
    for mk, m_rows in mine.items():
        gk = mapping.get(mk)
        if not gk or gk not in gt:
            tot_mine += len(m_rows)
            by_series[mk] = {"error": "no GT match", "mine_n": len(m_rows)}
            continue
        m_pts = [(r["_x"], r["_y"]) for r in m_rows]
        g_pts = [(r["_x"], r["_y"]) for r in gt[gk]]
        tp, fn, fp = pair_points(m_pts, g_pts, x_tol, y_tols)
        by_series[mk] = {"gt_label": gk, "tp": tp, "fn": fn, "fp": fp,
                          "gt_n": len(g_pts), "mine_n": len(m_pts)}
        tot_tp += tp; tot_fn += fn; tot_fp += fp
        tot_gt += len(g_pts); tot_mine += len(m_pts)
    # GT series that mine didn't even map to → all their points are FNs
    mapped_gt = set(mapping.values())
    for gk, g_rows in gt.items():
        if gk not in mapped_gt:
            tot_fn += len(g_rows)
            tot_gt += len(g_rows)
            by_series.setdefault(f"unmapped:{gk}",
                                  {"gt_label": gk, "tp": 0, "fn": len(g_rows),
                                   "fp": 0, "gt_n": len(g_rows), "mine_n": 0})
    return {"tp": tot_tp, "fn": tot_fn, "fp": tot_fp,
            "gt_n": tot_gt, "mine_n": tot_mine, "by_series": by_series}


_TEMP_TOKEN = re.compile(r"\d{2,3}c")


def _temp_key(s):
    """Extract the temperature token (e.g. '24c') if present, for fuzzy match."""
    m = _TEMP_TOKEN.search(s)
    return m.group(0) if m else None


def score_curves_layer(mine_curves, gt_curves, x_tol, y_tol_curve):
    """Resample each predicted curve at GT x values, pair-match within
    `y_tol_curve(gy)` (a callable so relative-error mode works per-point).
    GT points outside prediction's x coverage count as FN, with a small x_tol
    buffer to allow trend-line endpoint extrapolation. No FP from curves
    (extra prediction coverage is not penalised)."""
    if not gt_curves:
        return {"tp": 0, "fn": 0, "fp": 0, "gt_n": 0, "mine_n": 0,
                "by_series": {}}
    mapping = {}
    for mk in mine_curves:
        # 1. exact / substring
        for gk in gt_curves:
            if mk == gk or mk in gk or gk in mk:
                mapping[mk] = gk
                break
        if mk in mapping:
            continue
        # 2. shared temperature token (24c / 27c / 30c)
        mk_t = _temp_key(mk)
        if mk_t:
            for gk in gt_curves:
                if _temp_key(gk) == mk_t:
                    mapping[mk] = gk
                    break
        if mk in mapping:
            continue
        # 3. trend-line: single GT curve, match by name keyword
        if len(gt_curves) == 1 and ("trend" in mk or "line" in mk):
            mapping[mk] = next(iter(gt_curves))
    by_series = {}
    tot_tp = tot_fn = 0
    tot_gt = tot_mine = 0
    matched_gt = set()
    for mk, mpts in mine_curves.items():
        gk = mapping.get(mk)
        tot_mine += len(mpts)
        if not gk or gk not in gt_curves:
            by_series[mk] = {"error": "no GT curve match", "mine_n": len(mpts)}
            continue
        matched_gt.add(gk)
        g_pts = [(r["_x"], r["_y"]) for r in gt_curves[gk]]
        mxs = np.array([p[0] for p in mpts])
        mys = np.array([p[1] for p in mpts])
        order = np.argsort(mxs); mxs = mxs[order]; mys = mys[order]
        # Allow a small x_tol buffer for extrapolation past the visible line
        # extent (trend lines especially: my endpoints may be 1-2 px short of
        # GT's reported endpoints).
        x_lo = mxs[0] - x_tol
        x_hi = mxs[-1] + x_tol
        tp = fn = 0
        for gx, gy in g_pts:
            if gx < x_lo or gx > x_hi:
                fn += 1
                continue
            # np.interp clamps at endpoints, which is fine inside the buffer.
            y_pred = float(np.interp(gx, mxs, mys))
            if abs(y_pred - gy) <= y_tol_curve(gy):
                tp += 1
            else:
                fn += 1
        by_series[mk] = {"gt_label": gk, "tp": tp, "fn": fn, "fp": 0,
                          "gt_n": len(g_pts), "mine_n": len(mpts)}
        tot_tp += tp; tot_fn += fn; tot_gt += len(g_pts)
    # GT curves with no prediction
    for gk, g_rows in gt_curves.items():
        if gk not in matched_gt:
            tot_fn += len(g_rows); tot_gt += len(g_rows)
            by_series.setdefault(f"unmapped:{gk}",
                                  {"gt_label": gk, "tp": 0, "fn": len(g_rows),
                                   "fp": 0, "gt_n": len(g_rows), "mine_n": 0})
    return {"tp": tot_tp, "fn": tot_fn, "fp": 0,
            "gt_n": tot_gt, "mine_n": tot_mine, "by_series": by_series}


def score_errbars_layer(mine_pt, gt_pt, mine_eb, gt_eb,
                         chart_id, x_tol, y_tols):
    """Two schemas supported:

    A) **Legacy y_lo/y_hi columns** on point-like rows (aedes corpus). For
       each GT point-like row with error_y_plus/error_y_minus, check that
       the matched extractor row has y_lo / y_hi within y_tol of GT's
       expected lo/hi. One TP per row when BOTH bars match.

    B) **ErrorBarLayer rows** (synthetic corpus). Each cap is its own row at
       its data-space (x, y). Pool GT errbar rows and extractor errbar
       rows across all series (cap-direction names don't carry meaning to
       the pixel test) and pair-match by (x, y) within tolerance.

    The result aggregates TP/FN/FP from whichever schema fired (or both)."""

    tot_tp = tot_fn = tot_fp = 0
    tot_gt = tot_mine = 0
    by_series = {}

    # --- Schema B: ErrorBarLayer rows ---
    gt_eb_pts = []
    for vs in gt_eb.values():
        for r in vs: gt_eb_pts.append((r["_x"], r["_y"]))
    mine_eb_pts = []
    for vs in mine_eb.values():
        for r in vs: mine_eb_pts.append((r["_x"], r["_y"]))
    if gt_eb_pts or mine_eb_pts:
        tp, fn, fp = pair_points(sorted(mine_eb_pts), sorted(gt_eb_pts),
                                  x_tol, y_tols)
        tot_tp += tp; tot_fn += fn; tot_fp += fp
        tot_gt += len(gt_eb_pts); tot_mine += len(mine_eb_pts)
        by_series["errbar_caps_pooled"] = {
            "schema": "ErrorBarLayer", "tp": tp, "fn": fn, "fp": fp,
            "gt_n": len(gt_eb_pts), "mine_n": len(mine_eb_pts)}

    # --- Schema A: y_lo/y_hi columns on point rows ---
    gt_with_err = []
    for series, rows in gt_pt.items():
        for r in rows:
            ep = r.get("error_y_plus") or ""
            em = r.get("error_y_minus") or ""
            try:
                ep_v = float(ep); em_v = float(em)
            except ValueError:
                continue
            if ep_v <= 0 and em_v <= 0:
                continue
            gt_with_err.append((series, r["_x"], r["_y"], ep_v, em_v))
    if gt_with_err:
        mapping = map_series(mine_pt, gt_pt, chart_id) or {}
        gt_to_mine = {gk: mk for mk, gk in mapping.items()}
        for gseries, gx, gy, ep, em in gt_with_err:
            mk = gt_to_mine.get(gseries)
            matched = False
            # Resolve y_tol once per (gy, ep, em) — relative-mode callable
            # is evaluated at the bar's mean y.
            y_tol_here = y_tols(gy) if callable(y_tols) else y_tols
            if mk and mk in mine_pt:
                for r in mine_pt[mk]:
                    if abs(r["_x"] - gx) > x_tol: continue
                    if abs(r["_y"] - gy) > y_tol_here: continue
                    lo = r.get("_y_lo"); hi = r.get("_y_hi")
                    if lo is None or hi is None: break
                    exp_hi = gy + ep; exp_lo = gy - em
                    if abs(hi - exp_hi) <= y_tol_here and abs(lo - exp_lo) <= y_tol_here:
                        matched = True
                    tot_mine += 1
                    break
            tot_tp += int(matched)
            tot_fn += int(not matched)
            tot_gt += 1
            by_series.setdefault(gseries, {"schema": "y_lo/y_hi",
                                            "tp": 0, "fn": 0, "fp": 0})
            by_series[gseries]["tp" if matched else "fn"] += 1

    return {"tp": tot_tp, "fn": tot_fn, "fp": tot_fp,
            "gt_n": tot_gt, "mine_n": tot_mine, "by_series": by_series}


def f1_block(tp, fn, fp):
    p = tp / max(1, tp + fp)
    r = tp / max(1, tp + fn)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    j = tp / max(1, tp + fn + fp)
    return {"tp": tp, "fn": fn, "fp": fp,
            "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(f1, 4), "jaccard": round(j, 4)}


def score_chart(corpus_id, extractor, chart_id, results_dir, _legacy_tols=None):
    chart_dir = os.path.join(REPO_ROOT, "corpora", corpus_id, "charts", chart_id)
    extr_dir = os.path.join(REPO_ROOT, "extractors", extractor, results_dir,
                            corpus_id, chart_id)
    gt_path = os.path.join(chart_dir, "ground_truth.csv")
    data_path = os.path.join(extr_dir, "data.csv")
    if not os.path.exists(gt_path):
        return {"error": f"missing GT: {gt_path}"}
    if not os.path.isdir(extr_dir):
        return {"error": f"missing extractor dir: {extr_dir}"}
    gt_pt, gt_cv, gt_eb = load_gt_split(gt_path)
    spec = derive_tolerances(chart_id, gt_pt, gt_cv, gt_eb)
    x_tol = spec["x_tol"]
    y_tols = spec["y_tols"]
    y_tol_curve = spec["y_tol_curve"]
    mine_pt, mine_cv_layered, mine_eb = load_extractor_main(data_path)
    mine_cv_sidecar = load_extractor_curves(extr_dir)
    # Merge layered curves (from data.csv layer 1) with side-car curves.
    # Side-cars dominate if both define the same series.
    mine_curves = dict(mine_cv_layered)
    for s, pts in mine_cv_sidecar.items():
        mine_curves[s] = pts if s not in mine_curves else mine_curves[s] + [
            (p["_x"], p["_y"]) if isinstance(p, dict) else p for p in pts
        ]
    # Normalise mine_curves entries to list of (x, y) tuples
    norm_curves = {}
    for s, pts in mine_curves.items():
        norm_curves[s] = [(p["_x"], p["_y"]) if isinstance(p, dict) else p
                            for p in pts]
        norm_curves[s].sort()
    scatter = score_points_layer(mine_pt, gt_pt, chart_id, x_tol, y_tols)
    curves = score_curves_layer(norm_curves, gt_cv, x_tol, y_tol_curve)
    errbars = score_errbars_layer(mine_pt, gt_pt, mine_eb, gt_eb,
                                    chart_id, x_tol, y_tols)
    return {
        "x_tol": x_tol, "y_tol_kind": spec["kind"],
        "y_tol_desc": spec["y_tol_desc"],
        "x_range": spec["x_range"], "y_range": spec["y_range"],
        "scatter": {"summary": f1_block(scatter["tp"], scatter["fn"],
                                         scatter["fp"]),
                     "gt_n": scatter["gt_n"], "mine_n": scatter["mine_n"],
                     "by_series": scatter["by_series"]},
        "curves":  {"summary": f1_block(curves["tp"], curves["fn"],
                                         curves["fp"]),
                     "gt_n": curves["gt_n"], "mine_n": curves["mine_n"],
                     "by_series": curves["by_series"]},
        "errbars": {"summary": f1_block(errbars["tp"], errbars["fn"],
                                         errbars["fp"]),
                     "gt_n": errbars["gt_n"], "mine_n": errbars["mine_n"],
                     "by_series": errbars["by_series"]},
        "combined": f1_block(scatter["tp"] + curves["tp"] + errbars["tp"],
                              scatter["fn"] + curves["fn"] + errbars["fn"],
                              scatter["fp"] + curves["fp"] + errbars["fp"]),
    }


def list_charts(corpus_id):
    p = os.path.join(REPO_ROOT, "corpora", corpus_id, "charts")
    return sorted(d for d in os.listdir(p)
                  if os.path.isdir(os.path.join(p, d)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus")
    ap.add_argument("extractor")
    ap.add_argument("--results-dir", default="results-v2",
                    help="Results subdirectory under extractors/<name>/ "
                         "(default: results-v2)")
    args = ap.parse_args()
    charts = list_charts(args.corpus)
    out = {"corpus": args.corpus, "extractor": args.extractor,
           "results_dir": args.results_dir,
           "n_charts": len(charts), "charts": {}}
    cum = {"scatter": [0, 0, 0], "curves": [0, 0, 0], "errbars": [0, 0, 0]}
    for cid in charts:
        cs = score_chart(args.corpus, args.extractor, cid, args.results_dir)
        out["charts"][cid] = cs
        for layer in ("scatter", "curves", "errbars"):
            if layer in cs:
                s = cs[layer]["summary"]
                cum[layer][0] += s["tp"]; cum[layer][1] += s["fn"]; cum[layer][2] += s["fp"]
    out["totals"] = {
        "scatter":  f1_block(*cum["scatter"]),
        "curves":   f1_block(*cum["curves"]),
        "errbars":  f1_block(*cum["errbars"]),
        "combined": f1_block(cum["scatter"][0] + cum["curves"][0] + cum["errbars"][0],
                              cum["scatter"][1] + cum["curves"][1] + cum["errbars"][1],
                              cum["scatter"][2] + cum["curves"][2] + cum["errbars"][2]),
    }
    out_path = os.path.join(REPO_ROOT, "extractors", args.extractor,
                            args.results_dir, args.corpus, "scoring_data.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    t = out["totals"]
    print(f"=== {args.corpus} / {args.extractor} ({args.results_dir}) ===")
    print(f"            TP    FN    FP    P      R      F1     Jaccard")
    for layer in ("scatter", "curves", "errbars", "combined"):
        s = t[layer]
        print(f"  {layer:9s} {s['tp']:5d} {s['fn']:5d} {s['fp']:5d} "
              f" {s['precision']:.3f}  {s['recall']:.3f}  {s['f1']:.3f}  "
              f"{s['jaccard']:.3f}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
