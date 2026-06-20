#!/usr/bin/env python3
"""Build side-by-side (original | reconstruction) composites for the
owid-r6-1 corpus, parallel to build_compare_figs.py for aedes."""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
FIGS = os.path.join(HERE, "figs")
os.makedirs(FIGS, exist_ok=True)

CHARTS = [
    "life-expectancy",
    "annual-co2-emissions-per-country",
    "global-primary-energy",
    "life-expectancy-vs-gdp-per-capita",
    "share-of-individuals-using-the-internet",
    "child-mortality",
    "population",
    "share-electricity-low-carbon",
    "co2-emissions-per-capita",
    "gdp-per-capita-worldbank",
]


def find_recon(chart):
    base = os.path.join(REPO, "extractors", "graph-data-extraction",
                         "results-v3", "owid-r6-1", chart)
    # File-naming drift: a couple of agents produced reconstruction.png
    # instead of replot.png. Report-friendly to handle both.
    for cand in ("replot.png", "reconstruction.png", "overlay.png",
                  "verify_overlay.png"):
        p = os.path.join(base, cand)
        if os.path.exists(p):
            return p
    return None


def make_compare(chart, target_height=380):
    src = os.path.join(REPO, "corpora", "owid-r6-1",
                        "charts", chart, "image.png")
    rec = find_recon(chart)
    if not os.path.exists(src) or rec is None:
        print(f"  SKIP {chart}: missing {src} or recon"); return None
    a = cv2.imread(src); b = cv2.imread(rec)
    if a is None or b is None:
        print(f"  SKIP {chart}: failed to read images"); return None
    def scale(im, h):
        ratio = h / im.shape[0]
        return cv2.resize(im, (int(im.shape[1] * ratio), h),
                           interpolation=cv2.INTER_AREA)
    a2 = scale(a, target_height); b2 = scale(b, target_height)
    gutter = 20
    gut = np.ones((target_height, gutter, 3), dtype=np.uint8) * 255
    composite = np.hstack([a2, gut, b2])
    out = os.path.join(FIGS, f"owid_{chart}_compare.png")
    cv2.imwrite(out, composite)
    print(f"  wrote {out}  ({composite.shape[1]} x {composite.shape[0]} px) "
          f"<- {os.path.basename(rec)}")
    return out


def main():
    for chart in CHARTS:
        make_compare(chart)


if __name__ == "__main__":
    main()
