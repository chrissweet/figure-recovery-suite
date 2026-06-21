#!/usr/bin/env python3
"""One-iteration demo of the feedback-loop extractor on aedes el-100.

Pipeline:
  1. Read the existing v3 extraction output (data.csv, calibration.json,
     chart_metadata.json) as iteration 0's "extract" step. The new extractor
     is not yet built; this re-uses what v3 produced so the loop's diagnostic
     value is shown against a real, known-problem extraction.
  2. Render a fresh replot.png from data.csv + chart_metadata.json using a
     minimal templated renderer.
  3. Run Predicate A (negative-space coverage) — what did v3 MISS?
  4. Run Predicate B (glyph-vs-line discriminator) — which v3 marker claims
     are actually fragments of dashed/dotted fit lines?
  5. Write iter0_demo/ outputs: replot.png, negative_space_report.json,
     glyph_discriminator_report.json, side_by_side.png (source | replot for
     visual inspection), overlay.png (source with FN markers circled green
     and FP markers circled red).

Stops after one iteration; no convergence loop. Reports what iteration 1
of the loop WOULD do given these reports.
"""
import csv
import json
import os
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "extractors", "feedback-loop-extractor",
                                  "predicates"))
from negative_space import scan as ns_scan
from glyph_discriminator import score as gd_score


CHART = "el-100"
CORPUS = "aedes-aegypti-2014"
SRC_IMG = os.path.join(REPO, "corpora", CORPUS, "charts", CHART, "image.png")
V3_DIR  = os.path.join(REPO, "extractors", "graph-data-extraction", "results-v3",
                        CORPUS, CHART)
OUT_DIR = os.path.join(HERE)


def load_v3_rows(data_csv_path):
    rows = []
    with open(data_csv_path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"layer_idx": int(r.get("layer_idx", "0")),
                              "layer_type": r.get("layer_type", "Scatter Plot"),
                              "series": r.get("series", "default"),
                              "x": float(r["x"]), "y": float(r["y"])})
            except (KeyError, ValueError):
                continue
    return rows


def render_replot(rows, calibration, chart_metadata, out_path):
    """Templated replot. Reads axis titles + chart title from
    chart_metadata.json (NEVER hardcode). Uses the calibration's
    data_extent_box to pin matplotlib's inner axes box to the source's
    pixel geometry, so the inner plot frame matches between source and
    replot. Honest about the y-range: v3's calibration only covers
    data_range.y_max, so that's where the replot's y-axis tops out;
    any source-image ticks above that are outside v3's calibration."""
    cal = calibration
    de = cal["data_extent_box"]
    dr = cal["data_range"]
    H_px = cal["image_size"]["height"]; W_px = cal["image_size"]["width"]
    dpi = 100

    # Inner axes box as fractions of the figure, derived from
    # data_extent_box so the replot's plot frame lands at the same pixel
    # rectangle as the source's calibrated frame.
    fig = plt.figure(figsize=(W_px / dpi, H_px / dpi), dpi=dpi)
    # Matplotlib y origin = bottom; image y origin = top. Flip.
    left_frac   = de["left"]   / W_px
    right_frac  = de["right"]  / W_px
    bottom_frac = (H_px - de["bottom"]) / H_px
    top_frac    = (H_px - de["top"])    / H_px
    ax = fig.add_axes([left_frac, bottom_frac,
                        right_frac - left_frac, top_frac - bottom_frac])

    # Read titles + units from chart_metadata.json — never hardcode
    x_meta = chart_metadata.get("x_axis", {}) or {}
    y_meta = chart_metadata.get("y_axis", {}) or {}
    x_title = x_meta.get("title_verbatim") or x_meta.get("title") or ""
    y_title = y_meta.get("title_verbatim") or y_meta.get("title") or ""
    chart_title = chart_metadata.get("chart_title") or ""

    # Per-series styling
    style = {}
    for spec in chart_metadata.get("series_legend", []):
        sid = spec.get("series_id")
        style[sid] = {
            "color": spec.get("color", "#666666"),
            "marker": {"filled circle": "o", "filled square": "s",
                        "filled diamond": "D", "open circle": "o",
                        "open square": "s", "open diamond": "D"}.get(
                spec.get("marker_shape", ""), "o"),
            "line_style": {"solid": "-", "dashed": "--", "dotted": ":"}.get(
                spec.get("line_style", "solid"), "-"),
            "filled": "open" not in spec.get("marker_shape", ""),
        }

    by_sl = {}
    for r in rows:
        by_sl.setdefault((r["series"], r["layer_type"]), []).append(r)

    for (sid, layer), pts in by_sl.items():
        st = style.get(sid, {"color": "#666666", "marker": "o",
                              "line_style": "-", "filled": True})
        xs = [p["x"] for p in pts]; ys = [p["y"] for p in pts]
        if "Scatter" in layer or "Column" in layer:
            ax.scatter(xs, ys,
                        c=st["color"] if st["filled"] else "none",
                        edgecolors=st["color"],
                        marker=st["marker"], s=30, linewidth=1.2, label=sid)
        elif "Line" in layer or "Spline" in layer:
            order = np.argsort(xs)
            xs_s = [xs[i] for i in order]; ys_s = [ys[i] for i in order]
            ax.plot(xs_s, ys_s, color=st["color"], linestyle=st["line_style"],
                     linewidth=1.2, label=sid)

    # Snap the y-axis upper bound up to the next "nice" tick so absent data
    # above v3's calibrated data_range is visible as empty space rather than
    # silently chopping the chart. Source y-axes typically go to a round
    # multiple of 1/2/2.5/5 * 10^k.
    import math
    def _snap_up(v):
        if v <= 0: return v
        mag = 10 ** math.floor(math.log10(v))
        n = v / mag
        for step in (1, 2, 2.5, 5, 10):
            if n < step: return step * mag
        return 10 * mag
    y_max_display = _snap_up(dr["y_max"]) if dr["y_max"] > 0 else dr["y_max"]
    x_max_display = _snap_up(dr["x_max"]) if dr["x_max"] > 1 else dr["x_max"]
    ax.set_xlim(dr["x_min"], x_max_display)
    ax.set_ylim(dr["y_min"], y_max_display)
    if x_title: ax.set_xlabel(x_title, fontsize=10)
    if y_title: ax.set_ylabel(y_title, fontsize=10)
    if chart_title:
        # Use suptitle so it sits above the manually-positioned axes box,
        # not inside it
        fig.suptitle(chart_title, fontsize=11, y=0.97)
    ax.legend(loc="upper right", fontsize=8, frameon=True)
    ax.grid(True, alpha=0.3)

    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def render_side_by_side(src_path, replot_path, out_path, height=420):
    a = cv2.imread(src_path); b = cv2.imread(replot_path)
    if a is None or b is None:
        print(f"WARN: side-by-side failed, missing image"); return
    def scale(im, h):
        ratio = h / im.shape[0]
        return cv2.resize(im, (int(im.shape[1] * ratio), h),
                           interpolation=cv2.INTER_AREA)
    a2 = scale(a, height); b2 = scale(b, height)
    gut = np.ones((height, 20, 3), dtype=np.uint8) * 255
    comp = np.hstack([a2, gut, b2])
    cv2.imwrite(out_path, comp)


def render_overlay(src_path, ns_report, gd_report, out_path):
    """Annotate the source image:
      - FN (negative-space likely-markers): green circle
      - FP (glyph discriminator drop): red X
    """
    img = cv2.imread(src_path)
    if img is None: return
    for sid, ser in ns_report["per_series"].items():
        for u in ser["unclaimed"]:
            if u["triage"] == "likely-marker":
                cv2.circle(img, (u["col"], u["row"]), 8, (0, 220, 0), 2)
    for c in gd_report["per_claim"]:
        if c["drop"]:
            x, y = c["col"], c["row"]
            cv2.line(img, (x - 6, y - 6), (x + 6, y + 6), (0, 0, 220), 2)
            cv2.line(img, (x - 6, y + 6), (x + 6, y - 6), (0, 0, 220), 2)
    # Legend strip at top
    txt = "GREEN = unclaimed source markers (Predicate A would propose adding); RED X = claim flagged as line-fragment/swatch (Predicate B would drop)"
    cv2.rectangle(img, (0, 0), (img.shape[1], 22), (255, 255, 255), -1)
    cv2.putText(img, txt, (8, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                 (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(out_path, img)


def main():
    # 1. Load v3 outputs as iteration 0 "extract"
    cal = json.load(open(os.path.join(V3_DIR, "calibration.json")))
    md  = json.load(open(os.path.join(V3_DIR, "chart_metadata.json")))
    rows = load_v3_rows(os.path.join(V3_DIR, "data.csv"))
    print(f"Loaded {len(rows)} rows from v3 extraction.")

    # 2. Render fresh replot
    replot_path = os.path.join(OUT_DIR, "replot.png")
    render_replot(rows, cal, md, replot_path)
    print(f"  -> {replot_path}")

    # 3. Predicate A — negative-space
    ns_report = ns_scan(SRC_IMG, cal, md, rows)
    with open(os.path.join(OUT_DIR, "negative_space_report.json"), "w") as f:
        json.dump(ns_report, f, indent=2)
    s = ns_report["summary"]
    print(f"\n[Predicate A] negative-space scan:")
    print(f"  unclaimed likely-markers: {s['total_unclaimed_likely_marker']}")
    print(f"  unclaimed other:          {s['total_unclaimed_likely_other']}")
    for sid, ser in ns_report["per_series"].items():
        print(f"  {sid:>6}: claims={ser['claims']}, source_CCs={ser['source_components']}, "
               f"unclaimed={len(ser['unclaimed'])} "
               f"(likely-marker={sum(1 for u in ser['unclaimed'] if u['triage']=='likely-marker')})")

    # 4. Predicate B — glyph discriminator
    gd_report = gd_score(SRC_IMG, cal, md, rows)
    with open(os.path.join(OUT_DIR, "glyph_discriminator_report.json"), "w") as f:
        json.dump(gd_report, f, indent=2)
    s = gd_report["summary"]
    print(f"\n[Predicate B] glyph discriminator:")
    print(f"  total claims:  {s['n_claims']}")
    print(f"  claims dropped (line-fragment / legend-swatch): {s['n_dropped']}")
    print(f"  by verdict:")
    for v, n in s["by_verdict"].items():
        print(f"    {v:<20} {n}")

    # 5. Visualization
    sxs_path = os.path.join(OUT_DIR, "side_by_side.png")
    render_side_by_side(SRC_IMG, replot_path, sxs_path)
    print(f"\n  -> {sxs_path}")
    overlay_path = os.path.join(OUT_DIR, "overlay.png")
    render_overlay(SRC_IMG, ns_report, gd_report, overlay_path)
    print(f"  -> {overlay_path}")


if __name__ == "__main__":
    main()
