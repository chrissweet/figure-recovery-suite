"""Section 4 gate: the gap report flags real misses and stays quiet when clean.

Two complementary checks:

1. Deterministic ablation: drop N points from a forward-pass CSV and confirm
   reconcile flags exactly those N as ``cv_found_not_in_mllm``. This proves the
   reconciliation logic independent of detector noise.

2. el-94 cross-version demonstration (reported, not a hard pixel count): the
   27 degC gray squares are undercounted 14/25 in results-v1/v2 and patched to
   25 in results-v3. Reconciling the oracle's gray-square detections against v2
   must surface a gap; against v3 the gap must be materially smaller. el-94's
   markers fuse with same-color curves, so full recall needs the curve-
   subtraction step still to come -- this test asserts the *direction*, not a
   perfect count.
"""

from cv_oracle.reconcile import load_points, reconcile
from cv_oracle.run import detect_fused_markers, detect_scatter
from cv_oracle.tests.conftest import repo_path

SERIES_COLORS = {"A": (31, 119, 180), "B": (255, 127, 14), "C": (44, 160, 44)}


def test_ablation_flags_exactly_dropped_points(tmp_path):
    chart = repo_path("corpora", "synthetic-r4-1", "charts", "01-linear-scatter")
    cal = repo_path(
        "extractors", "graph-data-extraction", "results-v3",
        "synthetic-r4-1", "01-linear-scatter", "calibration.json",
    )
    cv_rows = detect_scatter(chart + "/image.png", cal, SERIES_COLORS)

    # Forward pass that "missed" 5 points: take the oracle's own detections and
    # delete 5, so the only difference is the ablation (isolates reconcile).
    full = [{"x": r["x"], "y": r["y"], "series": r["series"]} for r in cv_rows]
    dropped = full[:5]
    mllm = full[5:]

    xs = [p["x"] for p in full]
    ys = [p["y"] for p in full]
    x_tol = 0.02 * (max(xs) - min(xs))
    y_tol = 0.02 * (max(ys) - min(ys))

    report = reconcile(full, mllm, x_tol, y_tol)
    assert report["matched"] == len(mllm)
    assert len(report["cv_found_not_in_mllm"]) == len(dropped)


def test_el94_curve_subtraction_recovers_fused_squares(el94):
    """Curve-subtraction (vertical close) recovers el-94's fused 27 degC squares.

    The squares (gray ~190) are cut by the black solid 27 degC curve; blind
    detection got 9/25. Bridging the curve cut lifts recovery to ~24/25, so the
    gap report flags the ~11 squares missing from results-v2 (which has 14) and
    stays near-silent on results-v3 (patched to 25).
    """
    cv_det = detect_fused_markers(el94["image"], el94["calibration"], "27C")
    cv_rows = [{"x": r["x"], "y": r["y"], "series": "27C"} for r in cv_det]

    # The oracle should now independently see ~25 squares, not 9.
    assert len(cv_rows) >= 22, f"fused-square recovery only found {len(cv_rows)}"

    def v27(path):
        return [r for r in load_points(path) if "27" in r["series"] and "p_" not in r["series"]]

    x_tol, y_tol = 1.0, 0.005
    gap_v2 = len(reconcile(cv_rows, v27(el94["data_v2"]), x_tol, y_tol)["cv_found_not_in_mllm"])
    gap_v3 = len(reconcile(cv_rows, v27(el94["data_v3"]), x_tol, y_tol)["cv_found_not_in_mllm"])

    # v2 has 14/25 -> oracle flags a substantial undercount (~11).
    assert gap_v2 >= 8, f"expected oracle to flag the v2 undercount (~11), got {gap_v2}"
    # v3 patched to 25 -> the gap must collapse.
    assert gap_v3 <= 2, f"v3 patched but gap still {gap_v3}"
    assert gap_v2 - gap_v3 >= 6, f"gap should shrink sharply v2->v3 ({gap_v2}->{gap_v3})"
