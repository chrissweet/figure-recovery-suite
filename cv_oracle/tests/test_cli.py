"""Smoke tests for the cv_oracle.cli tool surface the skill calls."""

import os

from cv_oracle import cli
from cv_oracle.tests.conftest import repo_path


def test_snap_x(capsys):
    assert cli.main(["snap-x", "23.34", "24,27,30"]) == 0
    assert capsys.readouterr().out.strip() == "24.0"


def test_canvas_writes_normalized_image(tmp_path):
    img = repo_path("corpora", "synthetic-r4-1", "charts", "01-linear-scatter", "image.png")
    cal = repo_path(
        "extractors", "graph-data-extraction", "results-v4", "synthetic-r4-1", "01-linear-scatter", "calibration.json"
    )
    out = os.path.join(tmp_path, "canvas.png")
    assert cli.main(["canvas", img, cal, out]) == 0
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_template_csv_output(capsys):
    img = repo_path("corpora", "synthetic-r4-1", "charts", "01-linear-scatter", "image.png")
    cal = repo_path(
        "extractors", "graph-data-extraction", "results-v4", "synthetic-r4-1", "01-linear-scatter", "calibration.json"
    )
    assert cli.main(["template", img, cal, "#1f77b4"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0] == "x,y"
    assert 13 <= len(out) - 1 <= 17  # ~15 blue markers
