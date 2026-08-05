#!/usr/bin/env python3
"""Per-type scoring: apply the graph-type-appropriate metric, not uniform TP/FN.

Rationale (see wiki Analysis-Graph-Type-Characterization-2026-08-05): position
TP/FN is right for separable markers but misleads on other types. This routes by
chart type and reports the metric that actually measures success:

  separable scatter  -> position P/R/F1        (score_data scatter layer)
  dense/overlapping  -> count ratio + density-grid correlation  (positions are
                        inherently ambiguous; score the DISTRIBUTION)
  line / curve       -> curve fidelity          (score_data curves layer)
  bar                -> bar-value F1 + error-bar completeness

Reuses score_data.py for the per-layer P/R/F1 (its per-series matching and
categorical / log tolerance models); adds the density metric it lacks. The
extraction data.csv may be a plain (series,x,y); layer_type is inferred from the
chart type so score_data can route it.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_data import score_chart  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DENSE_MARKER_COUNT = 80  # GT scatter count above which markers likely overlap -> density metric


def _chart_type(corpus: str, chart: str) -> str:
    for p in (f"corpora/{corpus}/charts/{chart}/metadata.json",
              f"extractors/graph-data-extraction/results-v4/{corpus}/{chart}/chart_metadata.json"):
        fp = os.path.join(REPO, p)
        if os.path.exists(fp):
            ct = (json.load(open(fp)).get("chart_type") or "").lower()
            if ct:
                return ct
    return "scatter"


def _infer_layer(series: str, chart_type: str) -> str:
    s = series.lower()
    if "line" in chart_type or "spline" in chart_type:
        return "Line Graph"
    if "bar" in chart_type:
        return "Bar Chart"
    if s.startswith("p_curve") or s.startswith("if") or "curve" in s or "fit" in s:
        return "Spline Chart"
    return "Scatter Plot"


def _gt_scatter(corpus: str, chart: str):
    pts = []
    gp = os.path.join(REPO, f"corpora/{corpus}/charts/{chart}/ground_truth.csv")
    for r in csv.DictReader(open(gp)):
        if "Scatter" in r.get("layer_type", ""):
            try:
                pts.append((float(r["x"]), float(r["y"])))
            except (ValueError, KeyError):
                pass
    return pts


def _density(ext_pts, gt_pts, nb=12):
    if not gt_pts:
        return None
    xs = [p[0] for p in gt_pts]; ys = [p[1] for p in gt_pts]
    xe = np.linspace(min(xs), max(xs), nb + 1); ye = np.linspace(min(ys), max(ys), nb + 1)

    def hist(pts):
        h, _, _ = np.histogram2d([p[0] for p in pts], [p[1] for p in pts], bins=[xe, ye])
        return h.flatten()
    hg, he = hist(gt_pts), hist(ext_pts)
    r = float(np.corrcoef(hg, he)[0, 1]) if hg.std() and he.std() else 0.0
    return {"count_ratio": round(len(ext_pts) / max(1, len(gt_pts)), 2),
            "density_corr": round(r, 2), "ext_n": len(ext_pts), "gt_n": len(gt_pts)}


def _stage(corpus: str, chart: str, ext_csv: str, chart_type: str) -> str:
    d = os.path.join(REPO, "extractors", "_pertype_tmp", chart, corpus, chart)
    os.makedirs(d, exist_ok=True)
    rows = list(csv.DictReader(open(ext_csv)))
    fields = rows[0].keys() if rows else []
    have_err = any(c in fields for c in ("y_lo", "y_hi"))
    with open(os.path.join(d, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y", "y_lo", "y_hi"])
        for r in rows:
            w.writerow([0, _infer_layer(r.get("series", ""), chart_type), r.get("series", ""),
                        r.get("x"), r.get("y"), r.get("y_lo", ""), r.get("y_hi", "")])
    return "_pertype_tmp"


def per_type_score(corpus: str, chart: str, ext_csv: str) -> dict:
    ct = _chart_type(corpus, chart)
    extractor = _stage(corpus, chart, ext_csv, ct)
    try:
        cs = score_chart(corpus, extractor, chart, chart)
    finally:
        shutil.rmtree(os.path.join(REPO, "extractors", "_pertype_tmp"), ignore_errors=True)

    def layer(name):
        return (cs.get(name) or {}).get("summary", {})

    ext_pts = [(float(r["x"]), float(r["y"])) for r in csv.DictReader(open(ext_csv))
               if r.get("x") and r.get("y")]
    gt_sc = _gt_scatter(corpus, chart)
    out = {"chart": chart, "chart_type": ct, "metrics": {}}

    if "line" in ct or "spline" in ct:
        s = layer("curves")
        out["primary"] = "curve_fidelity"
        out["metrics"]["curve_fidelity"] = {"F1": s.get("f1"), "R": s.get("recall"), "P": s.get("precision")}
    elif "bar" in ct:
        s = layer("scatter")
        err = layer("errbars")
        out["primary"] = "bar_value"
        out["metrics"]["bar_value"] = {"F1": s.get("f1"), "R": s.get("recall"), "P": s.get("precision")}
        out["metrics"]["errbar_completeness"] = {"gt_errbars": err.get("gt_n", 0), "extracted": err.get("mine_n", 0)}
    else:  # scatter
        dens = _density(ext_pts, gt_sc)
        pos = layer("scatter")
        out["metrics"]["position"] = {"F1": pos.get("f1"), "R": pos.get("recall"), "P": pos.get("precision")}
        out["metrics"]["density"] = dens
        out["primary"] = "density" if (dens and dens["gt_n"] > DENSE_MARKER_COUNT) else "position"
    return out


if __name__ == "__main__":
    corpus, chart, ext = sys.argv[1], sys.argv[2], sys.argv[3]
    print(json.dumps(per_type_score(corpus, chart, ext), indent=1))
