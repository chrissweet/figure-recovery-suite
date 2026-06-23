"""Section 5: ground-truth-free, corpus-wide recall gate.

Hermetic ablations cover the three statuses; a real-corpus check pins the
findings the gate surfaces on results-v3 (gaps the headline F1 does not isolate).
"""

import json
import os

from cv_oracle.gate import audit_chart, audit_results_root
from cv_oracle.run import write_rows_csv
from cv_oracle.tests.conftest import repo_path


def _make_chart(tmp_path, legend, rows):
    d = os.path.join(tmp_path, "chart")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "chart_metadata.json"), "w") as fh:
        json.dump({"series_legend": legend}, fh)
    write_rows_csv(rows, os.path.join(d, "data.csv"))
    return d


def test_pass_when_declared_layers_present(tmp_path):
    d = _make_chart(
        tmp_path,
        [{"series_id": "A", "marker_shape": "circle"}],
        [{"layer_idx": 0, "layer_type": "Scatter Plot", "series": "A", "x": 1, "y": 2}],
    )
    assert audit_chart(d)["status"] == "PASS"


def test_fail_when_declared_layer_absent(tmp_path):
    # Legend declares a line, data.csv has only (typed) scatter -> real gap.
    d = _make_chart(
        tmp_path,
        [{"series_id": "fit", "line_style": "solid"}],
        [{"layer_idx": 0, "layer_type": "Scatter Plot", "series": "A", "x": 1, "y": 2}],
    )
    res = audit_chart(d)
    assert res["status"] == "FAIL"
    assert res["missing_layers"] == ["curves"]


def test_ambiguous_when_untyped_rows_could_cover_it(tmp_path):
    # Legend declares a line; rows exist but are untyped -> not a hard fail.
    d = _make_chart(
        tmp_path,
        [{"series_id": "fit", "line_style": "solid"}],
        [{"layer_idx": "", "layer_type": "", "series": "fit", "x": 1, "y": 2}],
    )
    res = audit_chart(d)
    assert res["status"] == "AMBIGUOUS"
    assert res["untyped_rows"] == 1


def test_missing_metadata_is_not_assessed(tmp_path):
    d = os.path.join(tmp_path, "chart")
    os.makedirs(d)
    write_rows_csv([{"layer_idx": 0, "layer_type": "Scatter Plot", "series": "A", "x": 1, "y": 2}],
                   os.path.join(d, "data.csv"))
    assert audit_chart(d)["status"] == "NOT_ASSESSED"


def test_real_corpus_findings_on_v3():
    """Pin the GT-free gaps the gate surfaces on results-v3 (documents them)."""
    root = repo_path("extractors", "graph-data-extraction", "results-v3")
    report = audit_results_root(root)
    t = report["totals"]
    assert t["charts"] == sum(
        t[k] for k in ("pass", "fail", "ambiguous", "not_assessed", "missing_data")
    )
    aedes = report["corpora"]["aedes-aegypti-2014"]
    assert all(c["status"] == "PASS" for c in aedes.values())  # patched corpus is clean
    owid = report["corpora"]["owid-r6-1"]
    assert owid["life-expectancy"]["status"] == "FAIL"          # declared markers, emitted lines
    assert owid["child-mortality"]["status"] == "AMBIGUOUS"     # curve data present but untyped
    syn = report["corpora"]["synthetic-r4-1"]
    assert syn["07-dual-y-axes"]["status"] == "FAIL"
