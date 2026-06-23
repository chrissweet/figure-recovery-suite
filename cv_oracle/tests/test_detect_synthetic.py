"""Section 3a gate: blob recall on a clean color-separable synthetic chart.

synthetic-r4-1/01-linear-scatter has exact matplotlib ground truth and three
default-colored series, so "correct" is unambiguous. This validates the
detector pipeline (color separation -> blobs -> data coords) end to end.
"""

import csv

from cv_oracle.run import detect_scatter
from cv_oracle.tests.conftest import repo_path

SERIES_COLORS = {  # matplotlib tab:blue / tab:orange / tab:green
    "A": (31, 119, 180),
    "B": (255, 127, 14),
    "C": (44, 160, 44),
}


def _recall(det, gt, x_tol, y_tol):
    used = [False] * len(det)
    tp = 0
    for gx, gy in gt:
        best, best_d = -1, float("inf")
        for i, (dx, dy) in enumerate(det):
            if used[i]:
                continue
            d = max(abs(dx - gx) / x_tol, abs(dy - gy) / y_tol)
            if d < best_d:
                best_d, best = d, i
        if best >= 0 and best_d <= 1.0:
            used[best] = True
            tp += 1
    return tp


def test_blob_recall_on_synthetic_scatter():
    chart = repo_path("corpora", "synthetic-r4-1", "charts", "01-linear-scatter")
    cal = repo_path(
        "extractors", "graph-data-extraction", "results-v3",
        "synthetic-r4-1", "01-linear-scatter", "calibration.json",
    )
    rows = detect_scatter(chart + "/image.png", cal, SERIES_COLORS)
    det = [(r["x"], r["y"]) for r in rows]

    gt = [(float(r["x"]), float(r["y"])) for r in csv.DictReader(open(chart + "/ground_truth.csv"))]
    xs = [p[0] for p in gt]
    ys = [p[1] for p in gt]
    x_tol = 0.02 * (max(xs) - min(xs))
    y_tol = 0.02 * (max(ys) - min(ys))

    tp = _recall(det, gt, x_tol, y_tol)
    recall = tp / len(gt)
    # Measured 36/37 = 0.973 at build time; gate a little below to stay stable.
    assert recall >= 0.90, f"recall {recall:.3f} ({tp}/{len(gt)})"
