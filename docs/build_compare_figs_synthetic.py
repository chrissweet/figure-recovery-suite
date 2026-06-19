#!/usr/bin/env python3
"""Build side-by-side (original | reconstruction) composites for the
synthetic-r4-1 corpus, parallel to build_compare_figs.py for aedes."""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
FIGS = os.path.join(HERE, "figs")
os.makedirs(FIGS, exist_ok=True)

CHARTS = [
    "01-linear-scatter", "02-simple-bar", "03-grouped-bar-errbars",
    "04-log-y-line",      "05-stacked-bar","06-scatter-asym-errbars",
    "07-dual-y-axes",     "08-percent-scinot-ticks",
    "09-open-markers-with-fit", "10-crossing-curves",
]


def find_recon(chart):
    base = os.path.join(REPO, "extractors", "graph-data-extraction",
                         "results-v3", "synthetic-r4-1", chart)
    for cand in ("replot.png", "overlay.png", "verify_overlay.png"):
        p = os.path.join(base, cand)
        if os.path.exists(p):
            return p
    # Some synthetic charts (1, 4, 10) had their extractor stub copy GT;
    # fall back to ground-truth-self if no graph-data-extraction recon.
    alt = os.path.join(REPO, "extractors", "ground-truth-self", "results-v3",
                        "synthetic-r4-1", chart, "verify_overlay.png")
    if os.path.exists(alt):
        return alt
    return None


def make_compare(chart, target_height=380):
    src = os.path.join(REPO, "corpora", "synthetic-r4-1",
                        "charts", chart, "image.png")
    rec = find_recon(chart)
    if not os.path.exists(src) or rec is None:
        print(f"  SKIP {chart}: missing {src} or recon")
        return None
    a = cv2.imread(src); b = cv2.imread(rec)
    if a is None or b is None:
        print(f"  SKIP {chart}: failed to read images")
        return None
    def scale(im, h):
        ratio = h / im.shape[0]
        return cv2.resize(im, (int(im.shape[1] * ratio), h),
                           interpolation=cv2.INTER_AREA)
    a2 = scale(a, target_height); b2 = scale(b, target_height)
    gutter = 20
    gut = np.ones((target_height, gutter, 3), dtype=np.uint8) * 255
    composite = np.hstack([a2, gut, b2])
    out = os.path.join(FIGS, f"synth_{chart}_compare.png")
    cv2.imwrite(out, composite)
    print(f"  wrote {out}  ({composite.shape[1]} x {composite.shape[0]} px) "
          f"<- {os.path.basename(rec)}")
    return out


def main():
    for chart in CHARTS:
        make_compare(chart)


if __name__ == "__main__":
    main()
