"""Section 3c gate: error-bar cap detection on a clean fixture.

synthetic-r4-1/06-scatter-asym-errbars has exact GT for asymmetric x and y error
bars (8 points x 4 caps = 32 ErrorBarLayer rows). The detector reads each cap off
the near-black whisker extent around the marker. Validated through the real
scorer.
"""

import importlib.util
import os

import cv2

from cv_oracle.calibration import Calibration
from cv_oracle.detect.errbars import detect_error_bars
from cv_oracle.run import detect_scatter, write_rows_csv
from cv_oracle.tests.conftest import REPO_ROOT, repo_path


def _load_scorer():
    spec = importlib.util.spec_from_file_location(
        "score_data", os.path.join(REPO_ROOT, "scoring", "score_data.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_error_bar_caps_full_recall_on_synthetic():
    chart = "06-scatter-asym-errbars"
    chart_dir = repo_path("corpora", "synthetic-r4-1", "charts", chart)
    cal_path = repo_path(
        "extractors", "graph-data-extraction", "results-v3", "synthetic-r4-1", chart, "calibration.json"
    )
    img = cv2.imread(chart_dir + "/image.png")
    cal = Calibration.from_calibration_file(cal_path)

    markers = detect_scatter(chart_dir + "/image.png", cal_path, {"Measurement": (31, 119, 180)}, color_tol=60)
    caps = detect_error_bars(img, cal, markers)

    rows = [
        {"layer_idx": 0, "layer_type": "Scatter Plot", "series": "Measurement", "x": m["x"], "y": m["y"]}
        for m in markers
    ] + caps

    out_dir = repo_path("extractors", "cv-oracle", "results-slice", "synthetic-r4-1", chart)
    os.makedirs(out_dir, exist_ok=True)
    write_rows_csv(rows, os.path.join(out_dir, "data.csv"))

    scorer = _load_scorer()
    result = scorer.score_chart("synthetic-r4-1", "cv-oracle", chart, "results-slice")
    eb = result["errbars"]["summary"]

    # All 32 GT caps recovered. (A few FP come from the legend swatch marker.)
    assert eb["tp"] == 32, f"errbar TP {eb['tp']} (expected 32)"
    assert eb["fn"] == 0, f"errbar FN {eb['fn']} (expected 0)"
