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


def test_curve_peel_extends_only_never_interleaves():
    """The invariant that keeps curve-peel from corrupting the scorer's per-series
    interpolation: every recovered curve point must fall OUTSIDE the forward
    pass's x-coverage for that series (a truncated tail), never inside it."""
    import csv as _csv

    from cv_oracle.peel import peel_recover_curves

    p = _paths("aedes-aegypti-2014", "el-94")
    recovered = peel_recover_curves(p["image"], p["cal"], p["meta"], p["data"])
    assert recovered, "el-94 has truncated curve tails; expected some recovery"

    # forward pass x-range per curve series
    v4_xrange = {}
    for r in _csv.DictReader(open(p["data"])):
        lt = (r.get("layer_type", "") or "").lower()
        if "line" in lt or "spline" in lt:
            try:
                x = float(r["x"])
            except (TypeError, ValueError):
                continue
            lo, hi = v4_xrange.get(r["series"], (x, x))
            v4_xrange[r["series"]] = (min(lo, x), max(hi, x))

    for row in recovered:
        rng = v4_xrange.get(row["series"])
        if rng is None:
            continue  # series the forward pass lacked entirely -> whole curve OK
        lo, hi = rng
        assert row["x"] < lo or row["x"] > hi, (
            f"curve-peel interleaved at x={row['x']} inside v4 range [{lo},{hi}]"
        )
