"""Peel-and-recheck recovery + canvas normalization.

Validates the core property the subtractive close-the-loop promises:
"zero residual = complete recall" -- when the forward pass got everything,
peeling leaves nothing to add. Uses v4 outputs as the forward pass.
"""

import numpy as np

from cv_oracle.peel import peel_recover_points
from cv_oracle.prepare_canvas import prepare_canvas
from cv_oracle.tests.conftest import repo_path

V4 = ("extractors", "graph-data-extraction", "results-v4")


def _paths(corpus, chart):
    v4 = repo_path(*V4, corpus, chart)
    return {
        "image": repo_path("corpora", corpus, "charts", chart, "image.png"),
        "cal": v4 + "/calibration.json",
        "meta": v4 + "/chart_metadata.json",
        "data": v4 + "/data.csv",
    }


def test_prepare_canvas_whites_outside_frame():
    import json

    p = _paths("synthetic-r4-1", "01-linear-scatter")
    canvas = prepare_canvas(p["image"], p["cal"])
    fb = json.load(open(p["cal"]))["plot_frame_box"]
    # a pixel well outside the frame (top-left corner) must be white
    assert (canvas[2, 2] == 255).all()
    # the frame interior must retain some non-white (data) pixels
    t, b, l, r = fb["top"], fb["bottom"], fb["left"], fb["right"]
    interior = canvas[t:b, l:r]
    assert (interior < 250).any()


def test_zero_residual_when_extraction_complete():
    # synthetic-01: v4 recovered all 37 scatter points, so peeling finds nothing.
    p = _paths("synthetic-r4-1", "01-linear-scatter")
    misses = peel_recover_points(p["image"], p["cal"], p["meta"], p["data"])
    assert len(misses) == 0


def test_peel_finds_misses_where_forward_pass_dropped_markers():
    # life-expectancy: forward pass emitted lines; the markers are residual.
    p = _paths("owid-r6-1", "life-expectancy")
    misses = peel_recover_points(p["image"], p["cal"], p["meta"], p["data"])
    assert len(misses) > 0
    # recovered rows are in the GT schema (data coords)
    assert all("x" in m and "y" in m and m["layer_type"] == "Scatter Plot" for m in misses)
