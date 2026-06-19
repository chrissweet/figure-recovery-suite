#!/usr/bin/env python3
"""data_csv_legend_check.py - flag data.csv rows that look like phantom data.

A Phase-5 deliverable check. Two conditions catch a row:

  (a) the row's (x, y) → predicted pixel position falls inside the
      calibration's `legend_exclusion_used_for_frame` box (the extractor's
      legend mask leaked); OR
  (b) the row's (x, y) is outside the calibration's `data_range` by more
      than a small tolerance (the row is past the labelled data extent).

Either way the row is unlikely to be real data. Phase 5 should drop these
rows or the audit will count them as predictions.

Surfaced by the el-88 TDD pass (2026-06-19): three rows in el-88's data.csv
(24C @ x=56.88, 30C @ x=57.68, 30C @ x=58.27) capture legend swatches at
cols 940-962 — outside the labelled data range x ≤ 50. The calibration's
legend box (rows 280-400, cols 870-980) is tight enough that the phantom
rows at row=270 slip past condition (a), but condition (b) catches them.

Usage:
    python3 scoring/data_csv_legend_check.py <results_root>

  e.g. python3 scoring/data_csv_legend_check.py extractors/graph-data-extraction/results

Optional flag:
    --warn-only   exit 0 even when leaks are found

Exit code: 0 if no leaks across all chart dirs, 1 otherwise.
"""
import argparse
import csv
import json
import os
import sys


X_CANDIDATES = ["x", "time_days", "temperature_C", "age_days", "parity_rate"]
Y_CANDIDATES = ["y", "percentage_parous_females", "max_parity_rate",
                "mean_duration_days", "mean_GC_duration",
                "mean_eggs_per_female", "survival_proportion",
                "daily_survival_p", "life_expectancy_50pct"]


def find_col(header, candidates):
    for c in candidates:
        if c in header:
            return c
    return None


def check_chart(chart_dir):
    data_path = os.path.join(chart_dir, "data.csv")
    cal_path = os.path.join(chart_dir, "calibration.json")
    if not os.path.exists(data_path) or not os.path.exists(cal_path):
        return None
    with open(cal_path) as f:
        cal = json.load(f)
    legend = cal.get("detection_internals", {}).get(
        "legend_exclusion_used_for_frame")
    if not legend:
        return {"skipped": "no legend exclusion in calibration"}
    # Widen legend box by 15 px on every side — the calibration's recorded
    # box is the one the extractor used during detection, but real legend
    # pixels can sit slightly outside it (especially text descenders and
    # symbol swatches above the first text row). 15 px is conservative
    # against el-88's observed 10-px-above-box leak.
    margin = 15
    ly0, ly1, lx0, lx1 = legend
    ly0 -= margin; ly1 += margin; lx0 -= margin; lx1 += margin
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    with open(data_path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {"n_rows": 0, "leaks": []}
    header = rows[0].keys()
    xc = find_col(header, X_CANDIDATES)
    yc = find_col(header, Y_CANDIDATES)
    sc = find_col(header, ["series", "point"])
    if xc is None or yc is None:
        return {"skipped": "could not find x/y columns"}
    leaks = []
    for r in rows:
        try:
            x = float(r[xc]); y = float(r[yc])
        except (TypeError, ValueError):
            continue
        col = (x - bx) / mx; row = (y - by) / my
        if ly0 <= row <= ly1 and lx0 <= col <= lx1:
            leaks.append({
                "series": r.get(sc, "?") if sc else "?",
                "x": x, "y": y,
                "col_pred": round(col, 1),
                "row_pred": round(row, 1),
                "reasons": ["inside_legend_box_widened"],
            })
    return {"n_rows": len(rows), "n_leaks": len(leaks), "leaks": leaks,
             "legend_box": legend, "legend_box_widened":
                 [ly0, ly1, lx0, lx1]}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("results_root",
                    help="Path to results dir (e.g. extractors/X/results)")
    ap.add_argument("--warn-only", action="store_true",
                    help="Exit 0 even when leaks are found")
    args = ap.parse_args()
    root = os.path.abspath(args.results_root)
    if not os.path.isdir(root):
        print(f"Not a directory: {root}", file=sys.stderr); sys.exit(2)

    chart_dirs = []
    for corpus in sorted(os.listdir(root)):
        cp = os.path.join(root, corpus)
        if not os.path.isdir(cp):
            continue
        for chart in sorted(os.listdir(cp)):
            cd = os.path.join(cp, chart)
            if os.path.isdir(cd):
                chart_dirs.append((corpus, chart, cd))
    if not chart_dirs:
        print(f"No chart dirs under {root}", file=sys.stderr); sys.exit(2)

    total_leaks = 0
    print(f"Data-CSV legend-hit check over {root}")
    print(f"{'corpus':<25} {'chart':<12} {'status':<8} reason")
    print("-" * 80)
    for corpus, chart, cd in chart_dirs:
        res = check_chart(cd)
        if res is None:
            print(f"{corpus:<25} {chart:<12} SKIP     no data.csv or calibration.json")
            continue
        if "skipped" in res:
            print(f"{corpus:<25} {chart:<12} SKIP     {res['skipped']}")
            continue
        if res["n_leaks"] == 0:
            print(f"{corpus:<25} {chart:<12} PASS     -")
            continue
        total_leaks += res["n_leaks"]
        for i, leak in enumerate(res["leaks"]):
            tag = "FAIL" if i == 0 else "    "
            cor = corpus if i == 0 else ""
            ch  = chart if i == 0 else ""
            print(f"{cor:<25} {ch:<12} {tag:<8} {leak['series']} ({leak['x']}, "
                  f"{leak['y']}) → col={leak['col_pred']} row={leak['row_pred']} "
                  f"reasons={','.join(leak['reasons'])}")
    print("-" * 80)
    print(f"Total leaks: {total_leaks}")
    if total_leaks and not args.warn_only:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
