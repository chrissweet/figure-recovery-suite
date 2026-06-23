"""Section 5: a ground-truth-free, corpus-wide recall gate.

The scorer needs ground truth, which a fine-tuning corpus will not have. This
gate instead checks each chart's forward-pass output against evidence the
forward pass itself produced from the image:

  - chart_metadata.json's `series_legend` declares which series the forward pass
    identified, and whether each is a line (`line_style`) or a marker
    (`marker_shape`). That gives the EXPECTED layer buckets with no ground truth.
  - data.csv is what the forward pass actually emitted.

A chart FAILS the gate when it declares a layer it did not emit -- exactly the
documented el-94 / el-100 failure ("three fit curves ... NOT extracted" in the
metadata, shipped anyway). This is the close-the-loop check that catches missing
recall before fine-tuning, across the whole corpus at once.

Limitation, stated plainly: error bars are not declared in series_legend, so
layer-presence cannot assert them. Use the pixel error-bar detector
(cv_oracle.detect.errbars) and reconcile.missing_layers for that.
"""

from __future__ import annotations

import csv
import json
import os

from .reconcile import ERR_COL_CANDIDATES


def expected_buckets(metadata: dict) -> set[str]:
    """Layer buckets the forward pass's own legend says should be present."""
    buckets: set[str] = set()
    for entry in metadata.get("series_legend", []):
        if entry.get("line_style"):
            buckets.add("curves")
        if entry.get("marker_shape"):
            buckets.add("points")
    return buckets


def scan_layers(data_csv: str) -> tuple[set[str], int]:
    """Return (typed buckets present, count of untyped rows) in a data.csv.

    Untyped rows (empty layer_type) are tracked separately rather than defaulted
    to 'points': a line chart whose rows are simply not classified would
    otherwise look like it is missing its curve layer. Error columns on any row
    still count as error bars (the aedes schema).
    """
    typed: set[str] = set()
    untyped = 0
    with open(data_csv) as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        err_cols = [c for c in ERR_COL_CANDIDATES if c in header]
        for row in reader:
            if any((row.get(c) or "") != "" for c in err_cols):
                typed.add("errbars")
            lt = (row.get("layer_type", "") or "").strip().lower()
            if not lt:
                untyped += 1
            elif "line" in lt or "spline" in lt:
                typed.add("curves")
            elif "error" in lt or "errbar" in lt:
                typed.add("errbars")
            else:
                typed.add("points")
    return typed, untyped


def audit_chart(chart_dir: str) -> dict:
    """Assess one chart directory (must contain data.csv; chart_metadata.json
    enables the layer-presence check).

    Status:
      - PASS: every declared layer is present (typed).
      - FAIL: a declared layer is absent and there are no untyped rows that
        could be it -> a genuine declared-but-not-emitted gap.
      - AMBIGUOUS: a declared layer is absent but untyped rows exist that may
        cover it (the forward pass emitted data without classifying its layer).
    """
    data_path = os.path.join(chart_dir, "data.csv")
    meta_path = os.path.join(chart_dir, "chart_metadata.json")
    if not os.path.exists(data_path):
        return {"status": "MISSING_DATA"}
    if not os.path.exists(meta_path):
        return {"status": "NOT_ASSESSED", "reason": "no chart_metadata.json"}
    expected = expected_buckets(json.load(open(meta_path)))
    present, untyped = scan_layers(data_path)
    missing = sorted(expected - present)
    if not missing:
        status = "PASS"
    elif untyped > 0:
        status = "AMBIGUOUS"
    else:
        status = "FAIL"
    return {
        "status": status,
        "expected": sorted(expected),
        "present": sorted(present),
        "missing_layers": missing,
        "untyped_rows": untyped,
    }


def audit_results_root(results_root: str) -> dict:
    """Audit every <corpus>/<chart> under a results root (e.g.
    extractors/graph-data-extraction/results-v3)."""
    corpora = {}
    totals = {"charts": 0, "pass": 0, "fail": 0, "ambiguous": 0, "not_assessed": 0, "missing_data": 0}
    for corpus in sorted(_subdirs(results_root)):
        corpus_dir = os.path.join(results_root, corpus)
        charts = {}
        for chart in sorted(_subdirs(corpus_dir)):
            res = audit_chart(os.path.join(corpus_dir, chart))
            charts[chart] = res
            totals["charts"] += 1
            totals[_tally_key(res["status"])] += 1
        corpora[corpus] = charts
    return {"results_root": results_root, "totals": totals, "corpora": corpora}


def _tally_key(status: str) -> str:
    return {
        "PASS": "pass", "FAIL": "fail", "AMBIGUOUS": "ambiguous",
        "NOT_ASSESSED": "not_assessed", "MISSING_DATA": "missing_data",
    }[status]


def _subdirs(path: str) -> list[str]:
    if not os.path.isdir(path):
        return []
    return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
