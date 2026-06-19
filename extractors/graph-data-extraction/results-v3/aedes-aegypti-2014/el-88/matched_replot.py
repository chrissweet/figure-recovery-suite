#!/usr/bin/env python3
"""Matched-frame replot for el-88 step 1 (markers only).

el-88 is a grayscale-shape scatter (filled black disk = 24°C, filled gray
square = 27°C, open black diamond = 30°C) — no color cue, no connecting
lines. The matched-frame composite is the same shape as el-60-a but the
diagnostic markers need to be visually distinct from black/gray/open so the
source markers show through underneath.

Diagnostic style:
  24°C   cyan hollow ring + cyan crosshair
  27°C   magenta hollow square + magenta crosshair
  30°C   yellow hollow diamond + yellow crosshair
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
                    "aedes-aegypti-2014", "el-88", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-88", "data.csv")


def main():
    with open(CAL) as f:
        cal = json.load(f)
    W = cal["image_size"]["width"]
    H = cal["image_size"]["height"]
    de = cal["data_extent_box"]
    dr = cal["data_range"]

    rows = []
    with open(DATA) as f:
        for r in csv.DictReader(f):
            rows.append((r["series"], float(r["age_days"]),
                         float(r["survival_proportion"])))

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    left_f   = de["left"] / W
    right_f  = de["right"] / W
    width_f  = right_f - left_f
    top_f    = (H - de["top"]) / H
    bottom_f = (H - de["bottom"]) / H
    height_f = top_f - bottom_f
    ax = fig.add_axes([left_f, bottom_f, width_f, height_f])
    ax.set_xlim(dr["x_min"], dr["x_max"])
    ax.set_ylim(dr["y_min"], dr["y_max"])

    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.patch.set_alpha(0)
    fig.patch.set_alpha(0)

    style = {
        "24C": dict(marker="o", facecolors="none", edgecolors="#00e5ff",
                    linewidths=1.2, s=120),
        "27C": dict(marker="s", facecolors="none", edgecolors="#ff00ff",
                    linewidths=1.2, s=140),
        "30C": dict(marker="D", facecolors="none", edgecolors="#ffeb3b",
                    linewidths=1.2, s=140),
    }
    for series in ("24C", "27C", "30C"):
        pts = sorted([(r[1], r[2]) for r in rows if r[0] == series])
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.scatter(xs, ys, **style[series], zorder=3)
        ax.scatter(xs, ys, marker="+", c=style[series]["edgecolors"],
                   s=24, linewidths=0.7, zorder=4)

    out = os.path.join(HERE, "replot.png")
    fig.savefig(out, dpi=100, transparent=True)
    print(f"wrote {out}  ({W} x {H} px, axes at ({de['left']},{de['top']})"
          f"-({de['right']},{de['bottom']}))")

    import cv2
    import numpy as np
    src_path = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                            "charts", "el-88", "image.png")
    src = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    rep = cv2.imread(out, cv2.IMREAD_UNCHANGED)
    if rep.shape[1] != src.shape[1] or rep.shape[0] != src.shape[0]:
        rep = cv2.resize(rep, (src.shape[1], src.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    if rep.shape[2] == 4:
        alpha = rep[:, :, 3:4].astype(float) / 255.0
        bgr   = rep[:, :, :3].astype(float)
        bgs   = src.astype(float)
        comp  = (alpha * bgr + (1 - alpha) * bgs).astype(np.uint8)
    else:
        comp = src.copy()
        comp[(rep < 250).any(axis=2)] = rep[(rep < 250).any(axis=2)]
    overlay_path = os.path.join(HERE, "overlay.png")
    cv2.imwrite(overlay_path, comp)
    print(f"wrote {overlay_path}")
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print(f"data.csv counts: {counts}  total: {sum(counts.values())}")


if __name__ == "__main__":
    main()
