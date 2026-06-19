#!/usr/bin/env python3
"""Matched-frame replot for el-60-a (TDD step 1: markers only).

Renders the extracted markers from results/aedes-aegypti-2014/el-60-a/data.csv
into a matplotlib figure whose pixel dimensions and plot-area offset are
identical to the source image, so direct overlay on image.png exposes any
position discrepancy.

Frame parameters come from results/.../el-60-a/calibration.json:
  image_size      : 870 x 563 px
  data_extent_box : left=126, top=77, right=783, bottom=433
                    (the pixel rectangle covering data range x∈[1,23], y∈[0,1])

The matplotlib axes are positioned at the same pixel rectangle inside an
870 x 563 figure so a data point at (x, y) renders at the same pixel as
calibration.json says it should.
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
                    "aedes-aegypti-2014", "el-60-a", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-60-a", "data.csv")


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
            rows.append((r["series"], float(r["time_days"]),
                         float(r["percentage_parous_females"])))

    # Figure at source pixel dimensions
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    # Axes position in figure-fraction coords; matches data_extent_box exactly.
    # matplotlib y-fraction is from the bottom, image rows from the top.
    left_f   = de["left"] / W
    right_f  = de["right"] / W
    width_f  = right_f - left_f
    top_f    = (H - de["top"]) / H
    bottom_f = (H - de["bottom"]) / H
    height_f = top_f - bottom_f
    ax = fig.add_axes([left_f, bottom_f, width_f, height_f])
    ax.set_xlim(dr["x_min"], dr["x_max"])
    ax.set_ylim(dr["y_min"], dr["y_max"])

    # No ticks, labels, or chrome — the source image already has those.
    # This first pass renders markers only so we can verify position coincidence.
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.patch.set_alpha(0)        # transparent axes background
    fig.patch.set_alpha(0)       # transparent figure background

    # Step-2 addition: tick grid. Vertical lines at every integer x in the
    # data range, horizontal lines at the printed y ticks. If calibration is
    # right, these land on the source's tick label centers; if drifted, they
    # sit off to one side.
    x_ticks = list(range(int(dr["x_min"]), int(dr["x_max"]) + 1))
    y_ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    for x in x_ticks:
        # Odd ticks (the labeled ones) brighter; even ticks (unlabeled) faint
        c = "#00bcd4" if x % 2 == 1 else "#80deea"
        a = 0.85 if x % 2 == 1 else 0.45
        ax.axvline(x, color=c, linewidth=0.6, alpha=a, zorder=2)
    for y in y_ticks:
        ax.axhline(y, color="#7c4dff", linewidth=0.6, alpha=0.75, zorder=2)

    # Diagnostic style: hollow rings + crosshair at each extracted point so
    # source markers show through. If alignment is good, the source marker
    # sits centered inside my ring; if off, the ring is offset from the dot.
    style = {
        "24C": dict(marker="o", facecolors="none", edgecolors="#00e5ff",
                    linewidths=1.4, s=180),
        "27C": dict(marker="s", facecolors="none", edgecolors="#ff00ff",
                    linewidths=1.4, s=200),
        "30C": dict(marker="D", facecolors="none", edgecolors="#ffeb3b",
                    linewidths=1.4, s=200),
    }
    for series in ("24C", "27C", "30C"):
        pts = sorted([(r[1], r[2]) for r in rows if r[0] == series])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # Connecting line: matches the source's drawn line if recipe §3a's
        # "line is just point-to-point connector" assumption holds.
        ax.plot(xs, ys, color=style[series]["edgecolors"],
                linewidth=1.2, alpha=0.85, zorder=2)
        ax.scatter(xs, ys, **style[series], zorder=3)
        ax.scatter(xs, ys, marker="+", c=style[series]["edgecolors"],
                   s=40, linewidths=0.9, zorder=4)

    out = os.path.join(HERE, "replot.png")
    fig.savefig(out, dpi=100, transparent=True)
    print(f"wrote {out}  ({W} x {H} px, axes at ({de['left']},{de['top']})"
          f"-({de['right']},{de['bottom']}))")

    # Composite the transparent replot on top of a copy of image.png.
    # Anywhere the replot has a marker, it paints over the source; everywhere
    # else the source shows through. Coincidence is then directly visible: an
    # extracted marker that lands on a source marker overlays cleanly; one
    # that drifts shows as a colored dot offset from the source marker.
    import cv2
    import numpy as np
    src_path = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                            "charts", "el-60-a", "image.png")
    src = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    rep = cv2.imread(out, cv2.IMREAD_UNCHANGED)
    # Make sure rep matches src width (matplotlib sometimes saves W-1).
    if rep.shape[1] != src.shape[1] or rep.shape[0] != src.shape[0]:
        rep = cv2.resize(rep, (src.shape[1], src.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    # rep is BGRA (transparent). Alpha-blend onto src (BGR).
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


if __name__ == "__main__":
    main()
