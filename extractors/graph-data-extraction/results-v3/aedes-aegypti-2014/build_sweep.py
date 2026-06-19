#!/usr/bin/env python3
"""Build v3 layered data.csv + calibration.json copy + chart_metadata.json
for the remaining five charts in aedes-aegypti-2014.

Combines:
  - results/<chart>/data.csv      → Scatter Plot or Grouped Column Chart layer
  - results-v2/<chart>/trend_line.csv → Line Graph layer
  - results-v2/<chart>/fit_curves.csv or if_curves.csv → Spline Chart layer
  - results-v2/<chart>/data.csv (with mirrored caps for el-62, yerr for el-80)
  - results/<chart>/calibration.json → copied for the gate
"""
import csv
import json
import os
import shutil

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
RES_OLD = os.path.join(REPO, "extractors", "graph-data-extraction",
                       "results", "aedes-aegypti-2014")
RES_V2  = os.path.join(REPO, "extractors", "graph-data-extraction",
                       "results-v2", "aedes-aegypti-2014")
RES_V3  = os.path.join(REPO, "extractors", "graph-data-extraction",
                       "results-v3", "aedes-aegypti-2014")


def copy_calibration(chart):
    src = os.path.join(RES_OLD, chart, "calibration.json")
    dst = os.path.join(RES_V3, chart, "calibration.json")
    shutil.copy(src, dst)


def build_el_60_b():
    """3-point scatter + black trend line."""
    chart = "el-60-b"
    os.makedirs(os.path.join(RES_V3, chart), exist_ok=True)
    copy_calibration(chart)
    # Scatter from v2 (snapped to integer x)
    rows = []
    with open(os.path.join(RES_V2, chart, "data.csv")) as f:
        for r in csv.DictReader(f):
            rows.append([0, "Scatter Plot", r["series"],
                          float(r["x"]), float(r["y"])])
    # Trend line endpoints from v2 trend_line.csv (two rows)
    with open(os.path.join(RES_V2, chart, "trend_line.csv")) as f:
        for r in csv.DictReader(f):
            rows.append([1, "Line Graph", "Trend Line",
                          float(r["x"]), float(r["y"])])
    with open(os.path.join(RES_V3, chart, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for row in rows:
            w.writerow(row)
    return rows


def build_el_62():
    """Grouped bar chart with mirrored error caps."""
    chart = "el-62"
    os.makedirs(os.path.join(RES_V3, chart), exist_ok=True)
    copy_calibration(chart)
    rows = []
    with open(os.path.join(RES_V2, chart, "data.csv")) as f:
        for r in csv.DictReader(f):
            rows.append([0, "Grouped Column Chart", r["series"],
                          float(r["x"]), float(r["y"]),
                          float(r["y_lo"]), float(r["y_hi"])])
    with open(os.path.join(RES_V3, chart, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y",
                     "y_lo", "y_hi"])
        for row in rows:
            w.writerow(row)
    return rows


def build_el_75():
    """3 scatter points with x/y error bars + red trend line."""
    chart = "el-75"
    os.makedirs(os.path.join(RES_V3, chart), exist_ok=True)
    copy_calibration(chart)
    rows = []
    with open(os.path.join(RES_V2, chart, "data.csv")) as f:
        for r in csv.DictReader(f):
            y = float(r["y"])
            rows.append([0, "Scatter Plot", "datapoints",
                          float(r["x"]), y,
                          y - float(r["y_err_lo"]), y + float(r["y_err_hi"])])
    with open(os.path.join(RES_V2, chart, "trend_line.csv")) as f:
        for r in csv.DictReader(f):
            rows.append([1, "Line Graph", "Trend Line",
                          float(r["x"]), float(r["y"]), "", ""])
    with open(os.path.join(RES_V3, chart, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y",
                     "y_lo", "y_hi"])
        for row in rows:
            w.writerow(row)
    return rows


def build_el_80():
    """Grouped bar chart with extracted yerr (symmetric)."""
    chart = "el-80"
    os.makedirs(os.path.join(RES_V3, chart), exist_ok=True)
    copy_calibration(chart)
    rows = []
    with open(os.path.join(RES_V2, chart, "data.csv")) as f:
        for r in csv.DictReader(f):
            y = float(r["y"]); e = float(r["yerr"])
            rows.append([0, "Grouped Column Chart", r["series"],
                          float(r["x"]), y, y - e, y + e])
    with open(os.path.join(RES_V3, chart, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y",
                     "y_lo", "y_hi"])
        for row in rows:
            w.writerow(row)
    return rows


def build_el_100():
    """3-color scatter + 3 IF curves (Spline Chart layer)."""
    chart = "el-100"
    os.makedirs(os.path.join(RES_V3, chart), exist_ok=True)
    copy_calibration(chart)
    rows = []
    with open(os.path.join(RES_V2, chart, "data.csv")) as f:
        for r in csv.DictReader(f):
            rows.append([0, "Scatter Plot", r["series"],
                          float(r["x"]), float(r["y"])])
    with open(os.path.join(RES_V2, chart, "if_curves.csv")) as f:
        for r in csv.DictReader(f):
            rows.append([1, "Spline Chart", r["series"],
                          float(r["x"]), float(r["y"])])
    with open(os.path.join(RES_V3, chart, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for row in rows:
            w.writerow(row)
    return rows


def main():
    for fn, label in [(build_el_60_b, "el-60-b"),
                       (build_el_62,   "el-62"),
                       (build_el_75,   "el-75"),
                       (build_el_80,   "el-80"),
                       (build_el_100,  "el-100")]:
        rows = fn()
        # Count rows per layer
        by_layer = {}
        for r in rows:
            k = (r[0], r[1], r[2])
            by_layer[k] = by_layer.get(k, 0) + 1
        print(f"{label}:")
        for k, v in sorted(by_layer.items()):
            print(f"  layer {k[0]} {k[1]:<20} {k[2]:<25} {v}")


if __name__ == "__main__":
    main()
