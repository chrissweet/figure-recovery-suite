#!/usr/bin/env python3
"""el-94 step 4: fit-curve overlay.

el-94 has three fit curves (dashed 24°C, solid 27°C, dotted 30°C). The v2
TDD pass traced them into fit_curves.csv. Here we render them at matched
frame, composite on image.png, and judge per-curve coincidence with the
source's drawn curves.

This is the step-4 variant for charts with explicit fit curves (unlike
el-60-a's "connecting lines = markers in x-order" or el-88's pure scatter).
"""
import csv
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "data.csv")
CURVES = os.path.join(REPO, "extractors", "graph-data-extraction",
                      "results-v2", "aedes-aegypti-2014", "el-94",
                      "fit_curves.csv")


def main():
    with open(CAL) as f: cal = json.load(f)
    W, H = cal["image_size"]["width"], cal["image_size"]["height"]
    de = cal["data_extent_box"]; dr = cal["data_range"]

    # Markers from data.csv (background context)
    markers = []
    with open(DATA) as f:
        for r in csv.DictReader(f):
            markers.append((r["series"], float(r["age_days"]),
                              float(r["daily_survival_p"])))
    # Fit curves from v2
    curves = {"24C": [], "27C": [], "30C": []}
    with open(CURVES) as f:
        for r in csv.DictReader(f):
            sname = r["series"]  # p_curve_24C → 24C
            if "24" in sname:    curves["24C"].append((float(r["x"]), float(r["y"])))
            elif "27" in sname:  curves["27C"].append((float(r["x"]), float(r["y"])))
            elif "30" in sname:  curves["30C"].append((float(r["x"]), float(r["y"])))
    for k in curves: curves[k].sort()

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    left_f, right_f = de["left"] / W, de["right"] / W
    top_f, bottom_f = (H - de["top"]) / H, (H - de["bottom"]) / H
    ax = fig.add_axes([left_f, bottom_f, right_f - left_f, top_f - bottom_f])
    ax.set_xlim(dr["x_min"], dr["x_max"])
    ax.set_ylim(dr["y_min"], dr["y_max"])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.patch.set_alpha(0); fig.patch.set_alpha(0)

    # Diagnostic curve colors (distinct from source's all-black curves)
    curve_style = {
        "24C": dict(color="#00e5ff", linestyle="--", linewidth=1.6),
        "27C": dict(color="#ff00ff", linestyle="-",  linewidth=1.6),
        "30C": dict(color="#ffeb3b", linestyle=":",  linewidth=2.0),
    }
    # Markers behind, faint
    marker_style = {
        "24C": dict(marker="o", facecolors="none", edgecolors="#00e5ff",
                    linewidths=0.7, s=50),
        "27C": dict(marker="s", facecolors="none", edgecolors="#ff00ff",
                    linewidths=0.7, s=60),
        "30C": dict(marker="D", facecolors="none", edgecolors="#ffeb3b",
                    linewidths=0.7, s=60),
    }
    for series in ("24C", "27C", "30C"):
        pts = sorted([(r[1], r[2]) for r in markers if r[0] == series])
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.scatter(xs, ys, **marker_style[series], zorder=2, alpha=0.55)
        cv = curves[series]
        if cv:
            ax.plot([p[0] for p in cv], [p[1] for p in cv],
                    zorder=3, **curve_style[series])

    out = os.path.join(HERE, "curve_replot.png")
    fig.savefig(out, dpi=100, transparent=True)
    print(f"wrote {out}")

    import cv2
    import numpy as np
    src_path = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                            "charts", "el-94", "image.png")
    src = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    rep = cv2.imread(out, cv2.IMREAD_UNCHANGED)
    if rep.shape[1] != src.shape[1] or rep.shape[0] != src.shape[0]:
        rep = cv2.resize(rep, (src.shape[1], src.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    if rep.shape[2] == 4:
        alpha = rep[:, :, 3:4].astype(float) / 255.0
        comp = (alpha * rep[:, :, :3].astype(float) +
                (1 - alpha) * src.astype(float)).astype(np.uint8)
    else:
        comp = src.copy()
        comp[(rep < 250).any(axis=2)] = rep[(rep < 250).any(axis=2)]
    overlay_path = os.path.join(HERE, "curve_overlay.png")
    cv2.imwrite(overlay_path, comp)
    print(f"wrote {overlay_path}")
    for k, v in curves.items():
        print(f"  {k} curve: {len(v)} points")


if __name__ == "__main__":
    main()
