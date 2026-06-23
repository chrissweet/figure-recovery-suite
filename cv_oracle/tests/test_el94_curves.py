"""el-94 fit curves: the oracle flags the missing curve LAYER in v1/v2.

Honest scoping (measured at build time):
  - v1/v2 have 0 fit-curve rows (the audit's "three fit curves missing").
  - v3 has the curves (forward pass traced them, curves F1 0.83 / recall 0.71).
  - Deterministic CV re-tracing of three crossing, same-color, dashed/dotted
    curves at the 0.001 y-tolerance UNDERPERFORMS the forward pass (27 degC
    corridor trace 14/30 vs 30/30). So the oracle does NOT try to beat the
    forward pass on curve accuracy.

The oracle's real contribution here is a recall signal at the LAYER level: it
recovers a 27 degC curve from that series' (color-separable) markers and reports
that v1/v2 carry no curve layer at all, while v3 does.
"""

import os

from cv_oracle.detect.curves import trace_curve_from_markers, curve_to_rows
from cv_oracle.reconcile import missing_layers
from cv_oracle.run import detect_fused_markers, write_rows_csv
from cv_oracle.tests.conftest import repo_path


def test_oracle_flags_missing_curve_layer_in_v1_v2(el94, tmp_path):
    # Recover the 27 degC curve from its markers (curve ~= markers within tol).
    squares = detect_fused_markers(el94["image"], el94["calibration"], "27C")
    curve_pts = trace_curve_from_markers(squares)
    assert len(curve_pts) >= 10  # a usable curve over the marker span

    cv_csv = os.path.join(tmp_path, "cv_oracle.csv")
    write_rows_csv(curve_to_rows(curve_pts, "p_curve_27C"), cv_csv)

    # v1 and v2 have no curve layer -> flagged; v3 has one -> not flagged.
    assert missing_layers(cv_csv, el94["data_v1"])["curves"]["layer_missing_in_mllm"] is True
    assert missing_layers(cv_csv, el94["data_v2"])["curves"]["layer_missing_in_mllm"] is True
    assert missing_layers(cv_csv, el94["data_v3"])["curves"]["layer_missing_in_mllm"] is False


def test_v3_curve_layer_is_populated(el94):
    """Guard the premise: v3 really does carry the fit-curve layer."""
    from cv_oracle.reconcile import load_points

    assert len(load_points(el94["data_v3"], layer_filter="curves")) > 100
    assert len(load_points(el94["data_v1"], layer_filter="curves")) == 0
