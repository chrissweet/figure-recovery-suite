#!/usr/bin/env python3
"""
score_vs_groundtruth.py — score legacy v1 extractor outputs against ground truth.

Greedy nearest-neighbor matching with Chebyshev distance normalized by
per-axis tolerances. Acceptance: |Δx| ≤ x_tol AND |Δy| ≤ y_tol.

This is the script that produced the headline TP=220 / FN=31 / FP=19 /
F1=0.898 numbers reported in docs/aedes-2014_eval_r3.pdf. The canonical
version of this scorer now lives at scoring/score.py at the repo root
and is generalized to accept any corpus and any extractor; this copy is
the legacy-v1 snapshot at the time those numbers were computed.

Per-chart tolerances are ~2 % of axis span; el-62 and el-80 (grouped bar
charts) use x_tol = 1.5 °C to absorb the bar-within-group visual offset.

Series-name special cases:
  el-60-b: GT uses "Series 1/2/3"; map mine 24c/27c/30c by x order.
  el-75:   GT pools as "Data Points"; pool mine too.
  el-94:   exclude GT series containing "curve" (fit-curve points).
  el-100:  exclude GT series containing "IF" (fit-line points).
"""
import csv
import json
import numpy as np

BASE = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite"
CORPUS = f"{BASE}/corpora/aedes-aegypti-2014/charts"
RESULTS = f"{BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014"

# (folder/chart_id, x_col, y_col, series_col, gt_exclude, x_tol, y_tol)
CHARTS = [
    ("el-60-a",  "time_days",      "percentage_parous_females", "series", (),         1.0,  0.03),
    ("el-60-b",  "temperature_C",  "max_parity_rate",           "series", ("Trend",), 1.0,  0.05),
    ("el-62",    "temperature_C",  "mean_duration_days",        "series", (),         1.5,  0.5),   # grouped bar
    ("el-75",    "temperature_C",  "mean_GC_duration",          "point",  ("Trend",), 1.0,  0.5),
    ("el-80",    "temperature_C",  "mean_eggs_per_female",      "series", (),         1.5,  2.0),   # grouped bar
    ("el-88",    "age_days",       "survival_proportion",       "series", (),         1.0,  0.03),
    ("el-94",    "age_days",       "daily_survival_p",          "series", ("curve",), 1.0,  0.003),
    ("el-100",   "parity_rate",    "life_expectancy_50pct",     "series", ("IF",),    0.03, 1.0),
]


def canon(s):
    return s.replace("°C", "").replace(" ", "").lower()


def match(mine_pts, gt_pts, x_tol, y_tol):
    used = [False] * len(mine_pts)
    pairs, fn = [], []
    for gx, gy in gt_pts:
        best_d = float("inf"); best_i = None
        for i, (mx, my) in enumerate(mine_pts):
            if used[i]: continue
            d = max(abs(mx - gx) / x_tol, abs(my - gy) / y_tol)
            if d < best_d: best_d = d; best_i = i
        if best_i is not None and best_d <= 1.0:
            mx, my = mine_pts[best_i]
            used[best_i] = True
            pairs.append({"gt": (gx, gy), "mine": (mx, my),
                          "d_norm": best_d, "dx": mx - gx, "dy": my - gy})
        else:
            fn.append((gx, gy))
    fp = [mine_pts[i] for i, u in enumerate(used) if not u]
    return pairs, fn, fp


def load_csv(path, x_col, y_col, s_col, exclude_substrs):
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                s = canon(r[s_col])
                if any(e in r[s_col] for e in exclude_substrs):
                    continue
                out.setdefault(s, []).append((float(r[x_col]), float(r[y_col])))
            except (KeyError, ValueError):
                pass
    for s in out: out[s].sort()
    return out


def main():
    all_scores = {}
    total_tp = total_fn = total_fp = 0
    all_dnorm = []

    for (cid, x_col, y_col, s_col, ex_substrs, x_tol, y_tol) in CHARTS:
        mine = load_csv(f"{RESULTS}/{cid}/data.csv", x_col, y_col, s_col, ())
        gt = load_csv(f"{CORPUS}/{cid}/ground_truth.csv", "x", "y", "series", ex_substrs)

        # Series-name special cases
        if cid == "el-60-b":
            gt_sorted = sorted(gt.items(), key=lambda kv: kv[1][0][0])
            order = ["24c", "27c", "30c"]
            mapping = {mk: gt_sorted[order.index(mk)][0] for mk in mine if mk in order}
        elif cid == "el-75":
            all_mine = [p for v in mine.values() for p in v]
            mine = {"datapoints": sorted(all_mine)}
            mapping = {"datapoints": "datapoints"}
        else:
            mapping = {}
            for mk in mine:
                for gk in gt:
                    if mk == gk or mk in gk or gk in mk:
                        mapping[mk] = gk; break

        chart_score = {"x_tol": x_tol, "y_tol": y_tol, "series": {}}
        for mk, m_pts in mine.items():
            gk = mapping.get(mk)
            if not gk: continue
            pairs, fn, fp = match(m_pts, gt[gk], x_tol, y_tol)
            tp = len(pairs)
            total_tp += tp; total_fn += len(fn); total_fp += len(fp)
            all_dnorm.extend([p["d_norm"] for p in pairs])
            p = tp / max(1, tp + len(fp))
            r = tp / max(1, tp + len(fn))
            f1 = 2 * p * r / (p + r) if (p + r) else 0
            chart_score["series"][mk] = {
                "gt_label": gk, "tp": tp, "fn": len(fn), "fp": len(fp),
                "mine_n": len(m_pts), "gt_n": len(gt[gk]),
                "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
                "mean_abs_dx": round(float(np.mean([abs(pp["dx"]) for pp in pairs])) if pairs else 0, 4),
                "mean_abs_dy": round(float(np.mean([abs(pp["dy"]) for pp in pairs])) if pairs else 0, 4),
            }
        all_scores[cid] = chart_score

    totals = {"tp": total_tp, "fn": total_fn, "fp": total_fp,
              "gt_points": total_tp + total_fn,
              "predicted_points": total_tp + total_fp,
              "precision": round(total_tp / max(1, total_tp + total_fp), 4),
              "recall":    round(total_tp / max(1, total_tp + total_fn), 4),
              "f1":        round(2 * total_tp / max(1, 2 * total_tp + total_fp + total_fn), 4),
              "jaccard":   round(total_tp / max(1, total_tp + total_fn + total_fp), 4)}
    if all_dnorm:
        d = np.array(all_dnorm)
        totals["matched_pair_normalized_distance"] = {
            "median": round(float(np.median(d)), 3),
            "mean":   round(float(np.mean(d)), 3),
            "p90":    round(float(np.percentile(d, 90)), 3),
            "max":    round(float(np.max(d)), 3),
            "fraction_within_eps_over_2": round(float((d <= 0.5).sum() / len(d)), 3),
        }

    out = {"corpus": "aedes-aegypti-2014",
           "extractor": "graph-data-extraction (legacy-v1)",
           "charts": all_scores, "totals": totals}
    out_path = f"{RESULTS}/scoring_legacy_v1.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"TP={total_tp}  FN={total_fn}  FP={total_fp}")
    print(f"Precision={totals['precision']:.3f}  Recall={totals['recall']:.3f}  F1={totals['f1']:.3f}  Jaccard={totals['jaccard']:.3f}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
