"""Section 3b gate: curve tracer beats the forward pass on the hardest chart.

synthetic-r4-1/04-log-y-line is the worst synthetic chart for the forward pass
(curves recall 0.225, F1 0.367 in results-v3): two color-distinct curves on a
log-y axis where a 1px row error is a large relative-y error. The deterministic
tracer, reading the source pixels, recovers strictly more curve points -- the
recall-recovery thesis of the whole package, measured on a chart where the
forward pass is weak.

Validation goes through the *real* scorer (scoring/score_data.py::score_chart),
not a reimplementation, so the relative-tolerance math (incl. the eps floor)
matches exactly.
"""

import importlib.util
import os

import cv2

from cv_oracle.calibration import Calibration
from cv_oracle.detect.curves import trace_curve, curve_to_rows
from cv_oracle.run import write_rows_csv
from cv_oracle.tests.conftest import REPO_ROOT, repo_path

CURVE_COLORS = {"Exponential": (214, 39, 40), "Power law": (148, 103, 189)}
FORWARD_PASS_CURVE_TP = 27  # results-v3 curves layer on 04-log-y-line (recall 0.225)


def _load_scorer():
    spec = importlib.util.spec_from_file_location(
        "score_data", os.path.join(REPO_ROOT, "scoring", "score_data.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_curve_tracer_beats_forward_pass_on_log_chart():
    chart = "04-log-y-line"
    chart_dir = repo_path("corpora", "synthetic-r4-1", "charts", chart)
    cal_path = repo_path(
        "extractors", "graph-data-extraction", "results-v3", "synthetic-r4-1", chart, "calibration.json"
    )
    img = cv2.imread(chart_dir + "/image.png")
    cal = Calibration.from_calibration_file(cal_path, log_y=True)

    rows = []
    for series, rgb in CURVE_COLORS.items():
        pts = trace_curve(img, cal, rgb, color_tol=50, x_step_px=4, log_y=True)
        rows += curve_to_rows(pts, series)

    # Write the oracle output where the real scorer expects an extractor to live.
    out_dir = repo_path("extractors", "cv-oracle", "results-slice", "synthetic-r4-1", chart)
    os.makedirs(out_dir, exist_ok=True)
    write_rows_csv(rows, os.path.join(out_dir, "data.csv"))

    scorer = _load_scorer()
    result = scorer.score_chart("synthetic-r4-1", "cv-oracle", chart, "results-slice")
    tp = result["curves"]["summary"]["tp"]

    assert tp >= 32, f"curve TP {tp} below floor (measured 35 at build time)"
    assert tp > FORWARD_PASS_CURVE_TP, f"oracle curve TP {tp} did not beat forward pass {FORWARD_PASS_CURVE_TP}"
