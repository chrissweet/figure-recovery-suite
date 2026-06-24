"""V5 recall recovery: GT-free guarantee + conservative-merge behavior.

Uses the existing results-v3 chart dirs as a stand-in for v4 (forward-pass
output), since v4 is produced later by the workflow. The point here is to lock
the recovery LOGIC: never read ground truth, never hallucinate error bars on a
chart that has none, never densify an existing curve, and do recover missed
points.
"""

import os
import tempfile

import pytest

from cv_oracle.recover import assert_gt_free, recover_chart
from cv_oracle.tests.conftest import repo_path


def _chart(corpus, chart):
    cd = repo_path("corpora", corpus, "charts", chart)
    ed = repo_path("extractors", "graph-data-extraction", "results-v3", corpus, chart)
    return {
        "image": cd + "/image.png",
        "calibration": ed + "/calibration.json",
        "metadata": ed + "/chart_metadata.json",
        "data": ed + "/data.csv",
    }


def _run(corpus, chart, buckets):
    f = _chart(corpus, chart)
    out = os.path.join(tempfile.mkdtemp(), "data.csv")
    return recover_chart(f["image"], f["calibration"], f["metadata"], f["data"], out, buckets=buckets)


def test_gt_free_guard_rejects_ground_truth_paths():
    with pytest.raises(PermissionError):
        assert_gt_free("corpora/x/charts/y/ground_truth.csv")
    with pytest.raises(PermissionError):
        assert_gt_free("/abs/path/ground_truth_calibration.json")
    # a normal path is fine
    assert assert_gt_free("results-v4/x/data.csv").endswith("data.csv")


def test_recover_chart_refuses_gt_input():
    f = _chart("synthetic-r4-1", "01-linear-scatter")
    with pytest.raises(PermissionError):
        # passing a ground_truth file where data.csv is expected must be refused
        recover_chart(f["image"], f["calibration"], f["metadata"],
                      repo_path("corpora", "synthetic-r4-1", "charts", "01-linear-scatter", "ground_truth.csv"),
                      "/tmp/out.csv")


def test_no_errbar_hallucination_on_chart_without_errbars():
    # 01-linear-scatter has no error bars; even asking for errbars must add none
    # (v4 has no errbar layer, so recovery is skipped rather than invented).
    rep = _run("synthetic-r4-1", "01-linear-scatter", ("points", "curves", "errbars"))
    assert rep["added"]["errbars"] == 0


def test_no_curve_densify_when_curve_present():
    # el-94's forward pass already has curves; recovery must not densify them.
    rep = _run("aedes-aegypti-2014", "el-94", ("points", "curves"))
    assert rep["added"]["curves"] == 0


def test_recovers_missed_points():
    # life-expectancy's forward pass emitted lines and dropped the marker points;
    # point recovery should add some.
    rep = _run("owid-r6-1", "life-expectancy", ("points",))
    assert rep["added"]["points"] > 0
    assert rep["v5_rows"] > rep["v4_rows"]


def test_preserves_v4_columns_like_y_lo_y_hi():
    # el-62 carries y_lo/y_hi error-bar columns; the rewrite must not drop them.
    import csv as _csv

    f = _chart("aedes-aegypti-2014", "el-62")
    src_cols = set(_csv.DictReader(open(f["data"])).fieldnames or [])
    out = os.path.join(tempfile.mkdtemp(), "data.csv")
    recover_chart(f["image"], f["calibration"], f["metadata"], f["data"], out, buckets=("points",))
    out_cols = set(_csv.DictReader(open(out)).fieldnames or [])
    assert src_cols <= out_cols, f"dropped columns: {src_cols - out_cols}"


def test_gated_mode_skips_present_layers():
    # el-94's forward pass already has points and curves (gate PASS), so gated
    # recovery must add nothing (it only fills declared-but-dropped layers).
    rep = _run_gated("aedes-aegypti-2014", "el-94")
    assert sum(rep["added"].values()) == 0


def _run_gated(corpus, chart):
    f = _chart(corpus, chart)
    out = os.path.join(tempfile.mkdtemp(), "data.csv")
    return recover_chart(f["image"], f["calibration"], f["metadata"], f["data"], out, gated=True)
