#!/usr/bin/env python3
"""
subtract_curves.py - remove thin fit-curve traces from a binary mask while
preserving open-marker outlines (whose top + bottom edges look thin but pair
at a marker-height distance).

The image-input mode loads the image, builds a gray<200 mask (with the
24-disk-class subtracted), runs the subtraction, and writes the cleaned
mask. Use this to visualize whether the technique cleans your specific
chart before committing to it in extraction code.

Usage:
    python3 subtract_curves.py IMAGE.png cleaned.png \\
        [--gray-max 200] [--exclude-disk-below 50] \\
        [--thin-h 3] [--marker-span 4 13] \\
        [--mask-rect ROW0 ROW1 COL0 COL1]...

The --exclude-disk-below threshold removes very dark pixels first (gray <
threshold), which is typically the 24°C-class filled-disk series in grayscale
3-shape scatter plots. Curve subtraction is then applied to the remaining
medium-gray pixels.
"""
import argparse
import sys
import numpy as np
import cv2


def column_runs(col):
    rows = np.where(col > 0)[0]
    if len(rows) == 0:
        return []
    runs, s, e = [], rows[0], rows[0]
    for r in rows[1:]:
        if r == e + 1:
            e = r
        else:
            runs.append((s, e)); s, e = r, r
    runs.append((s, e))
    return runs


def subtract_curves(mask, thin_h=3, marker_span=(4, 13)):
    out = mask.copy()
    H, W = mask.shape
    lo, hi = marker_span
    for c in range(W):
        runs = column_runs(mask[:, c])
        for i, (s, e) in enumerate(runs):
            if e - s + 1 > thin_h:
                continue
            paired = False
            for j, (s2, e2) in enumerate(runs):
                if i == j or e2 - s2 + 1 > thin_h:
                    continue
                gap = max(s, s2) - min(e, e2)
                if lo <= gap <= hi:
                    paired = True
                    break
            if not paired:
                out[s:e + 1, c] = 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("output")
    ap.add_argument("--gray-max", type=int, default=200,
                    help="upper gray threshold for the mask (default 200)")
    ap.add_argument("--exclude-disk-below", type=int, default=50,
                    help="exclude pixels gray < this (the filled-disk class) before curve subtraction")
    ap.add_argument("--thin-h", type=int, default=3,
                    help="max run height treated as a thin curve trace (default 3)")
    ap.add_argument("--marker-span", type=int, nargs=2, default=[4, 13],
                    metavar=("LO", "HI"),
                    help="paired-thin-run gap range that preserves open markers (default 4 13)")
    ap.add_argument("--mask-rect", action="append", default=[], nargs=4, type=int,
                    metavar=("ROW0", "ROW1", "COL0", "COL1"),
                    help="rectangle to EXCLUDE from the input mask; repeatable")
    args = ap.parse_args()

    im = cv2.imread(args.image)
    if im is None:
        print(f"could not read {args.image}", file=sys.stderr)
        sys.exit(2)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    mask = ((gray < args.gray_max) & (hsv[:, :, 1] < 50)).astype(np.uint8) * 255
    if args.exclude_disk_below > 0:
        disks = ((gray < args.exclude_disk_below) & (hsv[:, :, 1] < 50))
        mask[disks] = 0
    for r0, r1, c0, c1 in args.mask_rect:
        mask[r0:r1, c0:c1] = 0

    before = int((mask > 0).sum())
    cleaned = subtract_curves(mask, thin_h=args.thin_h, marker_span=tuple(args.marker_span))
    after = int((cleaned > 0).sum())
    cv2.imwrite(args.output, cleaned)
    print(f"pixels: {before} -> {after}  (removed {before - after}, {100*(before-after)/max(before,1):.1f}%)")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
