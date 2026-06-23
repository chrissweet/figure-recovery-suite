"""Section 4: reconcile CV detections against a forward-pass data.csv.

This is the point of the whole package. It diffs two CSVs *in data coordinates*
and emits a gap report:

  - ``cv_found_not_in_mllm``: detections the oracle saw on the source image that
    the forward pass does not have -> the recall signal the replot verifier
    could never produce (it iterated over claimed positions, not source ones).
  - ``mllm_found_not_in_cv``: forward-pass rows with no CV support -> FP suspects.

Per design principle 4, this NEVER edits the forward-pass CSV; it only reports.
Glyph-vs-line discrimination happens upstream at detection time (blob aspect /
solidity filters), so by the time rows reach here they are already typed.
"""

from __future__ import annotations

import csv
import json

# Column resolution mirrors scoring/score_data.py so we read either schema.
X_CANDIDATES = ["x", "time_days", "temperature_C", "age_days", "parity_rate"]
Y_CANDIDATES = [
    "y", "percentage_parous_females", "max_parity_rate", "mean_duration_days",
    "mean_GC_duration", "mean_eggs_per_female", "survival_proportion",
    "daily_survival_p", "life_expectancy_50pct",
]
S_CANDIDATES = ["series", "point"]

# Error bars travel under two schemas: ErrorBarLayer rows (synthetic), or error
# columns on a data/bar row (aedes). These are the column names that signal the
# latter (scorer's ERR_* candidates plus the GT-side error_y_plus/minus).
ERR_COL_CANDIDATES = [
    "y_lo", "y_low", "yerr_lo", "y_err_lo",
    "y_hi", "y_high", "yerr_hi", "y_err_hi",
    "yerr", "y_err", "error_y_plus", "error_y_minus",
]


def _pick(header: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in header:
            return c
    return None


def load_points(csv_path: str, *, layer_filter: str | None = "points") -> list[dict]:
    """Load (x, y, series) rows from a CSV, resolving column names.

    ``layer_filter`` selects a layer bucket the way the scorer routes layers
    ('points' = scatter/bar, 'curves', 'errbars'); None keeps all rows.
    """
    with open(csv_path) as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        xc = _pick(header, X_CANDIDATES)
        yc = _pick(header, Y_CANDIDATES)
        sc = _pick(header, S_CANDIDATES)
        rows = []
        for r in reader:
            if layer_filter is not None and not _in_bucket(r.get("layer_type", ""), layer_filter):
                continue
            try:
                x = float(r[xc])
                y = float(r[yc])
            except (TypeError, ValueError, KeyError):
                continue
            rows.append({"x": x, "y": y, "series": (r.get(sc) if sc else "") or ""})
    return rows


def _in_bucket(layer_type: str, bucket: str) -> bool:
    lt = (layer_type or "").lower()
    if "line" in lt or "spline" in lt:
        actual = "curves"
    elif "error" in lt or "errbar" in lt:
        actual = "errbars"
    else:
        actual = "points"
    return actual == bucket


def reconcile(cv_rows: list[dict], mllm_rows: list[dict], x_tol: float, y_tol: float) -> dict:
    """Greedy nearest-neighbour match (Chebyshev, per-axis normalized).

    Returns a gap report dict.
    """
    used = [False] * len(mllm_rows)
    matched = 0
    cv_unmatched = []
    for cv in cv_rows:
        best, best_d = -1, float("inf")
        for j, ml in enumerate(mllm_rows):
            if used[j]:
                continue
            d = max(abs(cv["x"] - ml["x"]) / x_tol, abs(cv["y"] - ml["y"]) / y_tol)
            if d < best_d:
                best_d, best = d, j
        if best >= 0 and best_d <= 1.0:
            used[best] = True
            matched += 1
        else:
            cv_unmatched.append(cv)
    mllm_unmatched = [ml for j, ml in enumerate(mllm_rows) if not used[j]]
    return {
        "n_cv": len(cv_rows),
        "n_mllm": len(mllm_rows),
        "matched": matched,
        "cv_found_not_in_mllm": cv_unmatched,
        "mllm_found_not_in_cv": mllm_unmatched,
        "x_tol": x_tol,
        "y_tol": y_tol,
    }


def errbar_count(csv_path: str) -> int:
    """Number of error-bar signals in a CSV under EITHER schema.

    Counts ErrorBarLayer rows (synthetic) and rows carrying a non-empty error
    column such as y_lo/y_hi/yerr (aedes). Without this dual handling, an aedes
    forward pass that drops its error bars looks identical to one that keeps
    them, because both route to the points bucket under layer_type.
    """
    with open(csv_path) as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        err_cols = [c for c in ERR_COL_CANDIDATES if c in header]
        n = 0
        for r in reader:
            lt = (r.get("layer_type", "") or "").lower()
            if "error" in lt or "errbar" in lt:
                n += 1
            elif any((r.get(c) or "") != "" for c in err_cols):
                n += 1
    return n


def missing_layers(cv_csv: str, mllm_csv: str, buckets=("points", "curves", "errbars")) -> dict:
    """Layer-level recall signal: which layer buckets does the oracle populate
    that the forward pass leaves empty?

    This catches the el-94 / el-100 audit gap that point-level matching cannot:
    the forward pass dropped the entire fit-curve layer in v1/v2 (0 curve rows),
    so the signal is "oracle has a curves layer, forward pass has none", not a
    per-point miss. The errbars bucket is schema-aware (see :func:`errbar_count`)
    so it also catches aedes error bars encoded as columns rather than rows.
    """
    report = {}
    for bucket in buckets:
        if bucket == "errbars":
            cv_n = errbar_count(cv_csv)
            ml_n = errbar_count(mllm_csv)
        else:
            cv_n = len(load_points(cv_csv, layer_filter=bucket))
            ml_n = len(load_points(mllm_csv, layer_filter=bucket))
        report[bucket] = {
            "cv_n": cv_n,
            "mllm_n": ml_n,
            "layer_missing_in_mllm": cv_n > 0 and ml_n == 0,
        }
    return report


def reconcile_files(cv_csv: str, mllm_csv: str, x_tol: float, y_tol: float, out_json: str | None = None) -> dict:
    report = reconcile(load_points(cv_csv), load_points(mllm_csv), x_tol, y_tol)
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(report, fh, indent=2)
    return report
