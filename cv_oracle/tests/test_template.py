"""Template-matching marker detection.

Pins the validated strength: seeded template matching recovers color/intensity-
separable markers in one pass, including the el-94 27 degC squares that fuse with
the same-color solid curve (blob detection got 9; template gets all of them).

Honest scope: this is strong for SEPARABLE markers. It is NOT validated as a
universal extractor -- grayscale series whose markers share intensity with
dashed/dotted curves (aedes black disks) defeat it (curve dots match as markers),
which is why the corpus-wide v8 arm did not beat v4. See
EXPERIMENT-v4-v5-2026-06-24.md.
"""

import cv2

from cv_oracle.calibration import Calibration
from cv_oracle.detect.template import detect_markers_template
from cv_oracle.prepare_canvas import prepare_canvas
from cv_oracle.tests.conftest import repo_path


def _canvas_and_cal(corpus, chart):
    v4 = repo_path("extractors", "graph-data-extraction", "results-v4", corpus, chart)
    img = repo_path("corpora", corpus, "charts", chart, "image.png")
    cal = Calibration.from_calibration_file(v4 + "/calibration.json")
    canvas = prepare_canvas(img, v4 + "/calibration.json")
    return canvas, cal


def test_template_recovers_fused_el94_27c_squares():
    # GT has 25; blob got 9; template should recover essentially all.
    canvas, cal = _canvas_and_cal("aedes-aegypti-2014", "el-94")
    pts = detect_markers_template(canvas, cal, (190, 190, 190), achromatic=True, score_thresh=0.55)
    assert 22 <= len(pts) <= 32, f"expected ~25 fused squares, got {len(pts)}"


def test_template_finds_colored_scatter_series():
    # synthetic-01 series A has 15 markers (tab:blue).
    canvas, cal = _canvas_and_cal("synthetic-r4-1", "01-linear-scatter")
    pts = detect_markers_template(canvas, cal, (31, 119, 180), achromatic=False, score_thresh=0.55)
    assert 13 <= len(pts) <= 17, f"expected ~15, got {len(pts)}"
