#!/usr/bin/env python3
"""Score the results-v2 outputs against the same ground truth.

Lifts score_chart from scoring/score.py but redirects extr_dir to results-v2.
"""
import json
import os
import sys
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scoring"))
import score as S  # noqa: E402


def score_chart_v2(corpus, extractor, chart, tols):
    chart_dir = os.path.join(REPO, "corpora", corpus, "charts", chart)
    extr_dir = os.path.join(REPO, "extractors", extractor, "results-v2",
                            corpus, chart)
    gt_path = os.path.join(chart_dir, "ground_truth.csv")
    mine_path = os.path.join(extr_dir, "data.csv")
    if not os.path.exists(mine_path):
        return {"error": f"missing extractor output: {mine_path}"}
    xc, yc, sc = S.EXTRACTOR_COL_HINTS[0]
    gt = S.load_csv(gt_path, ["x"], ["y"], ["series"],
                    exclude=S.GT_EXCLUDES.get(chart, ()))
    mine = S.load_csv(mine_path, xc, yc, sc)

    if chart == "el-60-b":
        gt_sorted = sorted(gt.items(), key=lambda kv: kv[1][0][0])
        order = ["24c", "27c", "30c"]
        mapping = {}
        for mk in mine:
            if mk in order:
                mapping[mk] = gt_sorted[order.index(mk)][0]
    elif chart == "el-75":
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

    x_tol = tols.get(chart, {"x_tol": 1.0, "y_tol": 0.05})["x_tol"]
    y_tol = tols.get(chart, {"x_tol": 1.0, "y_tol": 0.05})["y_tol"]
    series_results = {}
    for mk, m_pts in mine.items():
        gk = mapping.get(mk)
        if not gk:
            series_results[mk] = {"error": "no GT match", "mine_n": len(m_pts)}
            continue
        g_pts = gt[gk]
        pairs, fn, fp = S.match(m_pts, g_pts, x_tol, y_tol)
        tp = len(pairs)
        p = tp / max(1, tp + len(fp))
        r = tp / max(1, tp + len(fn))
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        series_results[mk] = {
            "gt_label": gk,
            "tp": tp, "fn": len(fn), "fp": len(fp),
            "mine_n": len(m_pts), "gt_n": len(g_pts),
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "pair_distances_normalized": [round(pp["d_norm"], 3) for pp in pairs],
        }
    return {"x_tol": x_tol, "y_tol": y_tol, "series": series_results}


def main():
    corpus = "aedes-aegypti-2014"
    extractor = "graph-data-extraction"
    charts = S.list_charts(corpus)
    out = {"corpus": corpus, "extractor": extractor + "-v2",
           "n_charts": len(charts), "charts": {}}
    total_tp = total_fn = total_fp = 0
    all_dnorm = []
    for cid in charts:
        cs = score_chart_v2(corpus, extractor, cid, S.DEFAULT_TOLS)
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
    out_path = os.path.join(REPO, "extractors", extractor, "results-v2",
                            corpus, "scoring.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    t = out["totals"]
    print(f"=== {corpus} / {extractor} (results-v2) ===")
    print(f"GT points: {t['gt_points']}    Predicted: {t['predicted_points']}")
    print(f"TP: {t['tp']}   FN: {t['fn']}   FP: {t['fp']}")
    print(f"Precision: {t['precision']:.3f}")
    print(f"Recall:    {t['recall']:.3f}")
    print(f"F1:        {t['f1']:.3f}")
    print(f"Jaccard:   {t['jaccard']:.3f}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
