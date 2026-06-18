#!/usr/bin/env python3
"""
score.py - score an extractor's results against a corpus's ground truth.

Usage:
    python3 scoring/score.py <corpus_id> <extractor_name> [--tolerances cfg.json]

Reads:
    corpora/<corpus_id>/charts/<chart-id>/ground_truth.csv
    extractors/<extractor_name>/results/<corpus_id>/<chart-id>/data.csv

Writes:
    extractors/<extractor_name>/results/<corpus_id>/scoring.json

Matching: each predicted point is paired with the nearest unmatched
ground-truth point using Chebyshev distance normalized by per-axis
tolerances. A pair is accepted iff |Δx| ≤ x_tol AND |Δy| ≤ y_tol.

Reports per series:
    TP, FN, FP, precision, recall, F1, mean |Δx|, mean |Δy|

And corpus totals:
    overall precision, recall, F1, Jaccard
    plus distance-to-epsilon distribution (median, 90th pct, fraction within ε/2)

Per-axis tolerances per chart default to ~2% of axis span, with widened
x_tol for grouped bar charts where the bar's visual centroid sits offset
from the group-center tick. Override via --tolerances FILE (JSON keyed by
chart id with `{x_tol, y_tol}` entries).
"""
import argparse
import csv
import json
import os
import sys
import numpy as np


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Default tolerances per chart. Override via --tolerances FILE if needed.
DEFAULT_TOLS = {
    # aedes-aegypti-2014
    "el-60-a":  {"x_tol": 1.0,  "y_tol": 0.03},
    "el-60-b":  {"x_tol": 1.0,  "y_tol": 0.05},
    "el-62":    {"x_tol": 1.5,  "y_tol": 0.5},   # grouped bar: widened x_tol
    "el-75":    {"x_tol": 1.0,  "y_tol": 0.5},
    "el-80":    {"x_tol": 1.5,  "y_tol": 2.0},   # grouped bar: widened x_tol
    "el-88":    {"x_tol": 1.0,  "y_tol": 0.03},
    "el-94":    {"x_tol": 1.0,  "y_tol": 0.003},
    "el-100":   {"x_tol": 0.03, "y_tol": 1.0},
}

# Per-chart column hints. If extractors output a different schema, override here
# or in a future config file.
GT_COLS = {"x": "x", "y": "y", "series": "series"}
EXTRACTOR_COL_HINTS = [
    # (x_col_candidates, y_col_candidates, series_col_candidates)
    (["x", "time_days", "temperature_C", "age_days", "parity_rate"],
     ["y", "percentage_parous_females", "max_parity_rate", "mean_duration_days",
      "mean_GC_duration", "mean_eggs_per_female", "survival_proportion",
      "daily_survival_p", "life_expectancy_50pct"],
     ["series", "point"]),
]

# Excluded ground-truth series substrings (trend lines, fit curves)
GT_EXCLUDES = {
    "el-60-b": ("Trend",),
    "el-75":   ("Trend",),
    "el-94":   ("curve",),
    "el-100":  ("IF",),
}


def canon(s):
    return s.replace("°C", "").replace(" ", "").lower()


def find_col(header, candidates):
    for c in candidates:
        if c in header:
            return c
    return None


def load_csv(path, x_candidates, y_candidates, s_candidates, exclude=()):
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {}
    header = rows[0].keys()
    xc = find_col(header, x_candidates)
    yc = find_col(header, y_candidates)
    sc = find_col(header, s_candidates)
    if xc is None or yc is None:
        raise RuntimeError(f"could not find x/y columns in {path} "
                           f"(header={list(header)})")
    by_series = {}
    for r in rows:
        s_val = r.get(sc, "") if sc else "default"
        if any(e in s_val for e in exclude):
            continue
        try:
            x = float(r[xc])
            y = float(r[yc])
        except (TypeError, ValueError):
            continue
        s = canon(s_val) if sc else "all"
        by_series.setdefault(s, []).append((x, y))
    for s in by_series:
        by_series[s].sort()
    return by_series


def match(mine_pts, gt_pts, x_tol, y_tol):
    """Greedy nearest-neighbor match using Chebyshev distance / tolerance."""
    used = [False] * len(mine_pts)
    pairs, fn = [], []
    for gx, gy in gt_pts:
        best_d = float("inf")
        best_i = None
        for i, (mx, my) in enumerate(mine_pts):
            if used[i]:
                continue
            d = max(abs(mx - gx) / x_tol, abs(my - gy) / y_tol)
            if d < best_d:
                best_d = d
                best_i = i
        if best_i is not None and best_d <= 1.0:
            mx, my = mine_pts[best_i]
            used[best_i] = True
            pairs.append({"gt": (gx, gy), "mine": (mx, my),
                          "dx": mx - gx, "dy": my - gy, "d_norm": best_d})
        else:
            fn.append((gx, gy))
    fp = [mine_pts[i] for i, u in enumerate(used) if not u]
    return pairs, fn, fp


def map_series(mine_keys, gt_keys, chart_id):
    """Best-effort series mapping. Special-cases for known label mismatches."""
    # el-60-b: GT uses "Series 1/2/3"; map mine 24/27/30 by index in GT x order.
    # el-75: GT pools as "Data Points"; pool mine too.
    return None  # caller must handle special cases by chart id


def score_chart(corpus_id, extractor, chart_id, tols, repo_root=REPO_ROOT):
    chart_dir = os.path.join(repo_root, "corpora", corpus_id, "charts", chart_id)
    extr_dir = os.path.join(repo_root, "extractors", extractor, "results",
                            corpus_id, chart_id)
    gt_path = os.path.join(chart_dir, "ground_truth.csv")
    mine_path = os.path.join(extr_dir, "data.csv")
    if not os.path.exists(gt_path):
        return {"error": f"missing ground truth: {gt_path}"}
    if not os.path.exists(mine_path):
        return {"error": f"missing extractor output: {mine_path}"}

    xc, yc, sc = EXTRACTOR_COL_HINTS[0]
    gt = load_csv(gt_path, ["x"], ["y"], ["series"],
                  exclude=GT_EXCLUDES.get(chart_id, ()))
    mine = load_csv(mine_path, xc, yc, sc)

    # Special cases for label-mismatch corpora
    if chart_id == "el-60-b":
        # GT: series1/2/3 by index; mine: 24c/27c/30c
        gt_sorted = sorted(gt.items(), key=lambda kv: kv[1][0][0])  # by first x
        order = ["24c", "27c", "30c"]
        mapping = {}
        for mk in mine:
            if mk in order:
                mapping[mk] = gt_sorted[order.index(mk)][0]
    elif chart_id == "el-75":
        # GT pooled as "datapoints"; pool mine
        all_mine = [p for v in mine.values() for p in v]
        mine = {"datapoints": sorted(all_mine)}
        mapping = {"datapoints": "datapoints"}
    else:
        mapping = {}
        for mk in mine:
            for gk in gt:
                if mk == gk or mk in gk or gk in mk:
                    mapping[mk] = gk
                    break

    x_tol = tols.get(chart_id, {"x_tol": 1.0, "y_tol": 0.05})["x_tol"]
    y_tol = tols.get(chart_id, {"x_tol": 1.0, "y_tol": 0.05})["y_tol"]

    series_results = {}
    for mk, m_pts in mine.items():
        gk = mapping.get(mk)
        if not gk:
            series_results[mk] = {"error": "no GT match", "mine_n": len(m_pts)}
            continue
        g_pts = gt[gk]
        pairs, fn, fp = match(m_pts, g_pts, x_tol, y_tol)
        tp = len(pairs)
        p = tp / max(1, tp + len(fp))
        r = tp / max(1, tp + len(fn))
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        mean_dx = float(np.mean([abs(pp["dx"]) for pp in pairs])) if pairs else 0
        mean_dy = float(np.mean([abs(pp["dy"]) for pp in pairs])) if pairs else 0
        series_results[mk] = {
            "gt_label": gk,
            "tp": tp, "fn": len(fn), "fp": len(fp),
            "mine_n": len(m_pts), "gt_n": len(g_pts),
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "mean_abs_dx": round(mean_dx, 4),
            "mean_abs_dy": round(mean_dy, 4),
            "pair_distances_normalized": [round(pp["d_norm"], 3) for pp in pairs],
        }
    return {"x_tol": x_tol, "y_tol": y_tol, "series": series_results}


def list_charts(corpus_id, repo_root=REPO_ROOT):
    p = os.path.join(repo_root, "corpora", corpus_id, "charts")
    if not os.path.isdir(p):
        return []
    return sorted(d for d in os.listdir(p)
                  if os.path.isdir(os.path.join(p, d)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus")
    ap.add_argument("extractor")
    ap.add_argument("--tolerances", default=None,
                    help="JSON file overriding per-chart tolerances "
                         "(keyed by chart id with {x_tol, y_tol}).")
    args = ap.parse_args()

    tols = dict(DEFAULT_TOLS)
    if args.tolerances:
        with open(args.tolerances) as f:
            tols.update(json.load(f))

    charts = list_charts(args.corpus)
    if not charts:
        print(f"No charts found at corpora/{args.corpus}/charts/", file=sys.stderr)
        sys.exit(1)

    out = {"corpus": args.corpus, "extractor": args.extractor,
           "n_charts": len(charts), "charts": {}}
    total_tp = total_fn = total_fp = 0
    all_dnorm = []
    for cid in charts:
        cs = score_chart(args.corpus, args.extractor, cid, tols)
        out["charts"][cid] = cs
        for sd in cs.get("series", {}).values():
            if "tp" in sd:
                total_tp += sd["tp"]
                total_fn += sd["fn"]
                total_fp += sd["fp"]
                all_dnorm.extend(sd["pair_distances_normalized"])

    total_gt = total_tp + total_fn
    total_pred = total_tp + total_fp
    out["totals"] = {
        "tp": total_tp, "fn": total_fn, "fp": total_fp,
        "gt_points": total_gt, "predicted_points": total_pred,
        "precision": round(total_tp / max(1, total_pred), 4),
        "recall":    round(total_tp / max(1, total_gt), 4),
        "f1":        round(2 * total_tp / max(1, 2 * total_tp + total_fp + total_fn), 4),
        "jaccard":   round(total_tp / max(1, total_gt + total_fp), 4),
    }
    if all_dnorm:
        d = np.array(all_dnorm)
        out["totals"]["matched_pair_normalized_distance"] = {
            "median": round(float(np.median(d)), 3),
            "mean":   round(float(np.mean(d)), 3),
            "p90":    round(float(np.percentile(d, 90)), 3),
            "max":    round(float(np.max(d)), 3),
            "fraction_within_eps_over_2": round(float((d <= 0.5).sum() / len(d)), 3),
        }

    out_path = os.path.join(REPO_ROOT, "extractors", args.extractor, "results",
                            args.corpus, "scoring.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    t = out["totals"]
    print(f"=== {args.corpus} / {args.extractor} ===")
    print(f"Charts:    {len(charts)}")
    print(f"GT points: {t['gt_points']}    Predicted: {t['predicted_points']}")
    print(f"TP: {t['tp']}   FN: {t['fn']}   FP: {t['fp']}")
    print(f"Precision: {t['precision']:.3f}")
    print(f"Recall:    {t['recall']:.3f}")
    print(f"F1:        {t['f1']:.3f}")
    print(f"Jaccard:   {t['jaccard']:.3f}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
