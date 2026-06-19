#!/usr/bin/env python3
"""el-94 verification overlay AFTER audit-row-7 fix.

Reads from v3 data.csv (which now contains 25 recovered 27°C squares) and
renders the matched-frame overlay. Compares against the source's 27°C
squares — every gray-square glyph in the chart-area should now have a
magenta ring overlay.
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
DATA = os.path.join(HERE, "data.csv")  # v3 layered data.csv


def main():
    with open(CAL) as f: cal = json.load(f)
    W, H = cal["image_size"]["width"], cal["image_size"]["height"]
    de = cal["data_extent_box"]; dr = cal["data_range"]

    rows = []
    with open(DATA) as f:
        for r in csv.DictReader(f):
            if r["layer_type"] != "Scatter Plot": continue
            rows.append((r["series"], float(r["x"]), float(r["y"])))

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

    style = {
        "24C": dict(marker="o", facecolors="none", edgecolors="#00e5ff",
                    linewidths=1.0, s=80),
        "27C": dict(marker="s", facecolors="none", edgecolors="#ff00ff",
                    linewidths=1.0, s=90),
        "30C": dict(marker="D", facecolors="none", edgecolors="#ffeb3b",
                    linewidths=1.0, s=90),
    }
    for series in ("24C", "27C", "30C"):
        pts = sorted([(r[1], r[2]) for r in rows if r[0] == series])
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.scatter(xs, ys, **style[series], zorder=3)

    out = os.path.join(HERE, "replot_v3.png")
    fig.savefig(out, dpi=100, transparent=True)

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
    cv2.imwrite(os.path.join(HERE, "overlay_v3.png"), comp)
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print(f"counts: {counts}  total: {sum(counts.values())}")


if __name__ == "__main__":
    main()
