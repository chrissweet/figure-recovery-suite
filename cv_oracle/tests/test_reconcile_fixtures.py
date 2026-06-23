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

import csv

import cv2

from cv_oracle.calibration import Calibration
from cv_oracle.detect import blobs as B
from cv_oracle.reconcile import load_points, reconcile
from cv_oracle.run import detect_scatter
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


def _gray_square_detections(image, cal):
    """el-94 27 degC gray squares (~RGB 190), tight band + solidity via aspect."""
    mask = B.achromatic_band_mask(image, lo=175, hi=205, achroma_tol=12)
    mask = B.crop_mask_to_box(mask, cal.plot_frame_box)
    blobs = B.detect_blobs(mask, min_diameter=5, max_diameter=18, max_aspect=1.6)
    return [cal.pixel_to_data(b.col, b.row) for b in blobs]


def test_el94_gap_direction_across_versions(el94):
    img = cv2.imread(el94["image"])
    cal = Calibration.from_calibration_file(el94["calibration"])
    det = _gray_square_detections(img, cal)
    cv_rows = [{"x": x, "y": y, "series": "27C"} for x, y in det]

    # 27 degC scatter only, from each forward-pass version.
    def v27(path):
        return [r for r in load_points(path) if "27" in r["series"] and "p_" not in r["series"]]

    mllm_v2 = v27(el94["data_v2"])
    mllm_v3 = v27(el94["data_v3"])

    # el-94 x-range ~0..50, narrow y; use the scorer-style absolute tolerances.
    x_tol, y_tol = 1.0, 0.005
    gap_v2 = len(reconcile(cv_rows, mllm_v2, x_tol, y_tol)["cv_found_not_in_mllm"])
    gap_v3 = len(reconcile(cv_rows, mllm_v3, x_tol, y_tol)["cv_found_not_in_mllm"])

    # v2 (14 of 25) must show a real gap; v3 (25 of 25) must show a smaller one.
    assert gap_v2 >= 1, f"expected oracle to flag v2 undercount, got {gap_v2}"
    assert gap_v3 < gap_v2, f"v3 patched but gap {gap_v3} not < v2 gap {gap_v2}"
