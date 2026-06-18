#!/usr/bin/env python3
"""
extract_markers.py - detect discrete markers in a color-thresholded mask
using the erode-line-away + CC + centroid pattern.

Use this when the figure is a line plot with markers at specific x values
(e.g. integer days, sampled timepoints) and the line and markers share a
color. The naive color-mask + CC approach gives one giant component covering
line + all markers; this routine erodes the connector line away first.

Usage:
    python3 extract_markers.py IMAGE.png --color BGR_LO BGR_HI \\
        [--hsv-lo H S V] [--hsv-hi H S V] [--kernel 5] [--min-area 30] \\
        [--mask-rect TOP BOT LEFT RIGHT]... [--snap-x integer]

Examples:
    # Blue markers in HSV space:
    python3 extract_markers.py plot.png \\
        --hsv-lo 100 100 50 --hsv-hi 130 255 255 \\
        --mask-rect 30 120 565 620   # exclude legend at top right

The default kernel is 5x5 (good for line widths up to ~3 px). Use --snap-x
to round the extracted x values to integers if your data is sampled at
regular intervals.
"""
import argparse
import sys
import numpy as np
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--hsv-lo", type=int, nargs=3, required=True,
                    metavar=("H", "S", "V"))
    ap.add_argument("--hsv-hi", type=int, nargs=3, required=True,
                    metavar=("H", "S", "V"))
    ap.add_argument("--kernel", type=int, default=5,
                    help="erosion kernel size (default 5; use 2 px wider than the line)")
    ap.add_argument("--min-area", type=int, default=30,
                    help="minimum post-erosion CC area to count as a marker")
    ap.add_argument("--mask-rect", action="append", default=[], nargs=4,
                    type=int, metavar=("ROW0", "ROW1", "COL0", "COL1"),
                    help="rectangle to EXCLUDE from the mask (e.g. legend); repeatable")
    ap.add_argument("--snap-x", action="store_true",
                    help="round extracted x pixel column to nearest integer (use after applying col2x)")
    args = ap.parse_args()

    im = cv2.imread(args.image)
    if im is None:
        print(f"could not read {args.image}", file=sys.stderr)
        sys.exit(2)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(hsv, np.array(args.hsv_lo), np.array(args.hsv_hi))
    for r0, r1, c0, c1 in args.mask_rect:
        mask[r0:r1, c0:c1] = 0

    k = cv2.getStructuringElement(cv2.MORPH_RECT, (args.kernel, args.kernel))
    core = cv2.erode(mask, k)

    n, _, stats, cent = cv2.connectedComponentsWithStats(core, 8)
    pts = []
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        if a < args.min_area:
            continue
        cx, cy = cent[i]
        pts.append((cx, cy, a))
    pts.sort(key=lambda p: p[0])

    print(f"image: {args.image}")
    print(f"hsv: {args.hsv_lo} -> {args.hsv_hi}")
    print(f"mask pixels: {(mask>0).sum()}")
    print(f"after erode kernel={args.kernel}: {(core>0).sum()}")
    print(f"markers found: {len(pts)}")
    print("col,row,area")
    for cx, cy, a in pts:
        if args.snap_x:
            print(f"{round(cx)},{cy:.1f},{a}")
        else:
            print(f"{cx:.1f},{cy:.1f},{a}")


if __name__ == "__main__":
    main()
