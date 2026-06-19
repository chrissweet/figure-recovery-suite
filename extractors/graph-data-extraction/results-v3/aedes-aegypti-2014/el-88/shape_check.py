#!/usr/bin/env python3
"""el-88 shape-classification check (TDD step 4).

el-88 has no connecting lines (pure scatter), so the step-4 verification is
not "line-overlay" but "does each extracted marker actually have the claimed
shape at its predicted pixel position?" We look in a small window around
each predicted (col, row) and classify the glyph independently:

  disk     = dense black blob (gray<50 fills most of the window's center)
  square   = dense gray blob (60-210 fills most of the window's center)
  diamond  = sparse black outline (gray<50 along a thin border, white interior)

Series claims: 24C=disk, 27C=square, 30C=diamond. Mismatch surfaces
classifier errors that the original extractor may have made.
"""
import csv
import json
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-88", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-88", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-88", "data.csv")

EXPECTED_SHAPE = {"24C": "disk", "27C": "square", "30C": "diamond"}


def classify_glyph(gray, hsv, col, row):
    """Classify glyph by inner-window content + outer-corner check.

    Discovery from el-88 (2026-06-19): the "open diamond" 30°C markers in
    this chart are actually filled with light gray (gray ≈ 200-230). The
    §2b recipe says "open black diamond" — that's wrong about el-88. So
    "open vs filled" can't be the distinguisher.

    Instead, distinguish square from diamond by what fills the OUTER
    CORNERS of a 13x13 window:
      - Square: corners gray (the square fills the bounding-box corners)
      - Diamond: corners white (the diamond's vertices don't reach corners)
      - Disk: corners white (the disk is smaller than the window)

    Inner-center content separates disk from the other two:
      - Disk: center dark
      - Diamond/Square: center gray
    """
    h, w = gray.shape
    # Inner 7x7
    ic0 = max(0, int(col) - 3); ic1 = min(w, int(col) + 4)
    ir0 = max(0, int(row) - 3); ir1 = min(h, int(row) + 4)
    inner = gray[ir0:ir1, ic0:ic1]
    inner_sat = hsv[ir0:ir1, ic0:ic1, 1]
    inner_dark = ((inner < 50) & (inner_sat < 50))
    inner_gray = ((inner >= 60) & (inner <= 230) & (inner_sat < 50))
    n_inner_dark = int(inner_dark.sum())
    n_inner_gray = int(inner_gray.sum())

    # Outer corners — sample the 4 corners of a 13x13 window.
    half = 6
    oc0 = max(0, int(col) - half); oc1 = min(w, int(col) + half + 1)
    or0 = max(0, int(row) - half); or1 = min(h, int(row) + half + 1)
    outer = gray[or0:or1, oc0:oc1]
    outer_sat = hsv[or0:or1, oc0:oc1, 1]
    # 4 corner 3x3 patches
    corners = [
        (outer[:3, :3],            outer_sat[:3, :3]),
        (outer[:3, -3:],           outer_sat[:3, -3:]),
        (outer[-3:, :3],           outer_sat[-3:, :3]),
        (outer[-3:, -3:],          outer_sat[-3:, -3:]),
    ]
    corner_gray = 0; corner_white = 0
    for c, cs in corners:
        gray_pix = ((c >= 60) & (c <= 230) & (cs < 50)).sum()
        white_pix = (c >= 230).sum()
        if gray_pix >= 6: corner_gray += 1
        elif white_pix >= 6: corner_white += 1
    info = {"n_inner_dark": n_inner_dark, "n_inner_gray": n_inner_gray,
             "corner_gray": corner_gray, "corner_white": corner_white}

    # Disk: dark dominates the centre
    if n_inner_dark >= 18 and n_inner_gray < 12:
        return ("disk", info)
    # Square: gray centre + gray corners (fills the whole bbox)
    if n_inner_gray >= 18 and n_inner_dark < 12 and corner_gray >= 3:
        return ("square", info)
    # Diamond: gray centre + white corners (corners are background)
    if n_inner_gray >= 14 and n_inner_dark < 12 and corner_white >= 3:
        return ("diamond", info)
    return ("unclear", info)


def main():
    with open(CAL) as f:
        cal = json.load(f)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]

    im = cv2.imread(IMG)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)

    per_series = {}
    misclass = []
    with open(DATA) as f:
        for r in csv.DictReader(f):
            series = r["series"]
            x = float(r["age_days"]); y = float(r["survival_proportion"])
            col = (x - bx) / mx; row = (y - by) / my
            shape, info = classify_glyph(gray, hsv, col, row)
            expected = EXPECTED_SHAPE[series]
            ok = (shape == expected)
            rec = {"x": x, "y": y, "expected": expected,
                    "classified_as": shape, "ok": ok, "info": info}
            per_series.setdefault(series, []).append(rec)
            if not ok:
                misclass.append((series, x, y, expected, shape, info))

    print(f"{'series':<6} {'expect':>8} {'n':>4} {'correct':>9} "
          f"{'mismatched':>12} {'unclear':>9}")
    for series in ("24C", "27C", "30C"):
        recs = per_series.get(series, [])
        ok = sum(1 for r in recs if r["ok"])
        misc = sum(1 for r in recs
                    if not r["ok"] and r["classified_as"] != "unclear")
        unc = sum(1 for r in recs if r["classified_as"] == "unclear")
        print(f"{series:<6} {EXPECTED_SHAPE[series]:>8} {len(recs):>4d} "
              f"{ok:>9d} {misc:>12d} {unc:>9d}")

    if misclass:
        print()
        print("Mismatched rows:")
        for series, x, y, expected, got, info in misclass:
            print(f"  {series} ({x}, {y}): expected {expected}, "
                  f"got {got}  ({info})")
    else:
        print("\n  (no mismatches)")

    out = os.path.join(HERE, "shape_check.json")
    with open(out, "w") as f:
        json.dump(per_series, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
