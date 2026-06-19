#!/usr/bin/env python3
"""Build side-by-side (original | reconstruction) composites for the r4 report.

For each chart, picks the best available reconstruction:
  - results-v3/.../overlay_v3.png (el-94 only — post audit-row-7 fix)
  - results-v3/.../overlay.png (the matched-frame overlay)
  - else results-v2/.../replot.png (matplotlib replot when no v3 overlay)

Saves to docs/figs/<chart>_compare.png at uniform height so the report
layout is consistent.
"""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
FIGS = os.path.join(HERE, "figs")
os.makedirs(FIGS, exist_ok=True)

CHARTS = ["el-60-a", "el-60-b", "el-62", "el-75", "el-80",
           "el-88", "el-94", "el-100"]

def find_recon(chart):
    """Pick the best-available reconstruction for this chart."""
    v3 = os.path.join(REPO, "extractors", "graph-data-extraction",
                       "results-v3", "aedes-aegypti-2014", chart)
    v2 = os.path.join(REPO, "extractors", "graph-data-extraction",
                       "results-v2", "aedes-aegypti-2014", chart)
    # Prefer the post-fix overlay for el-94
    for cand in ("overlay_v3.png", "overlay.png"):
        p = os.path.join(v3, cand)
        if os.path.exists(p):
            return p
    # Fall back to v2 matplotlib replot
    p = os.path.join(v2, "replot.png")
    if os.path.exists(p):
        return p
    return None


def make_compare(chart, target_height=420):
    src = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                       "charts", chart, "image.png")
    rec = find_recon(chart)
    if not os.path.exists(src) or rec is None:
        print(f"  SKIP {chart}: missing {src} or recon")
        return None
    a = cv2.imread(src)
    b = cv2.imread(rec)
    if a is None or b is None:
        print(f"  SKIP {chart}: failed to read images")
        return None
    # Scale both to target_height
    def scale(im, h):
        ratio = h / im.shape[0]
        return cv2.resize(im, (int(im.shape[1] * ratio), h),
                           interpolation=cv2.INTER_AREA)
    a2 = scale(a, target_height); b2 = scale(b, target_height)
    # Pad the shorter image's width with white if they differ a lot, then concat
    # horizontally with a small white gutter.
    gutter = 20
    gut = np.ones((target_height, gutter, 3), dtype=np.uint8) * 255
    composite = np.hstack([a2, gut, b2])
    out = os.path.join(FIGS, f"{chart}_compare.png")
    cv2.imwrite(out, composite)
    print(f"  wrote {out}  ({composite.shape[1]} x {composite.shape[0]} px) "
          f"<- {os.path.basename(rec)}")
    return out


def main():
    for chart in CHARTS:
        make_compare(chart)


if __name__ == "__main__":
    main()
