#!/usr/bin/env python3
"""el-94 audit-row-7 fix: recover 27°C gray squares fused with solid fit curve.

Approach: the gray mask (60-210) connects each square (~8×8 gray blob)
with the anti-aliased gray bands above/below the solid 27°C fit curve.
Vertical opening with a 5×1 kernel removes the thin (1-2 px) anti-aliased
bands but preserves the square interiors (≥5 px tall). After opening, the
fused CC splits back into one CC per square.

Steps:
  1. Build gray mask (60-210, sat<50), panel-restricted, legend-excluded,
     disk-suppressed (subtract dilated 24°C black-disk mask).
  2. Vertical opening (5×1) to remove thin line halos.
  3. CC analysis: square candidates with area 30-200 and density > 0.55.
  4. Dilate retained square CCs 2×2 to restore footprint.
  5. Emit (col, row) centroids in data coords.

Also: filter out detections that overlap the existing 24°C disk positions
(already accounted for) or the 30°C diamond positions (separate handling).
"""
import csv
import json
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-94", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "calibration.json")
DATA = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "data.csv")


def main():
    with open(CAL) as f:
        cal = json.load(f)
    mx = cal["axis_calibration"]["x_axis"]["m"]
    bx = cal["axis_calibration"]["x_axis"]["b"]
    my = cal["axis_calibration"]["y_axis"]["m"]
    by = cal["axis_calibration"]["y_axis"]["b"]
    pf = cal["plot_frame_box"]
    legend = cal["detection_internals"]["legend_exclusion_used_for_frame"]

    im = cv2.imread(IMG)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    H, W = gray.shape
    sat = hsv[:, :, 1]

    # Panel mask
    panel = np.zeros_like(gray, dtype=np.uint8)
    panel[pf["top"] + 2: pf["bottom"] - 2, pf["left"] + 2: pf["right"] - 2] = 255
    if legend:
        panel[max(0, legend[0] - 10): min(H, legend[1] + 10),
              max(0, legend[2] - 10): min(W, legend[3] + 10)] = 0

    # 1. Gray mask (square interiors + line halos)
    mid = ((gray >= 60) & (gray <= 210) & (sat < 50)).astype(np.uint8) * 255
    mid = cv2.bitwise_and(mid, panel)

    # Subtract dilated 24°C disk region so disks don't claim gray pixels.
    black = ((gray < 50) & (sat < 50)).astype(np.uint8) * 255
    black = cv2.bitwise_and(black, panel)
    # Disks: small dense black CCs.
    n_b, _, st_b, ct_b = cv2.connectedComponentsWithStats(black, 8)
    disk_mask = np.zeros_like(black)
    for i in range(1, n_b):
        a = st_b[i, cv2.CC_STAT_AREA]
        w_, h_ = st_b[i, cv2.CC_STAT_WIDTH], st_b[i, cv2.CC_STAT_HEIGHT]
        if 5 <= w_ <= 18 and 5 <= h_ <= 18 and a >= 25:
            density = a / (w_ * h_)
            if density >= 0.6:
                cv2.circle(disk_mask, (int(ct_b[i][0]), int(ct_b[i][1])),
                           7, 255, -1)
    mid[disk_mask > 0] = 0

    cv2.imwrite(os.path.join(HERE, "27c_mid_before_open.png"), mid)
    before_px = int((mid > 0).sum())

    # 2. Vertical opening (3×1) to remove thin (1-2 px) line halos.
    #    The square interior is 4-6 px tall so the 3×1 erode preserves
    #    its center row; dilate restores width.
    open_kernel = np.ones((3, 1), np.uint8)
    mid_opened = cv2.morphologyEx(mid, cv2.MORPH_OPEN, open_kernel)
    # 3. Then dilate 2×2 to restore square footprint (per audit row 7 alt).
    dilate_kernel = np.ones((2, 2), np.uint8)
    mid_recovered = cv2.dilate(mid_opened, dilate_kernel, iterations=1)
    cv2.imwrite(os.path.join(HERE, "27c_mid_after_open.png"), mid_opened)
    cv2.imwrite(os.path.join(HERE, "27c_mid_after_dilate.png"), mid_recovered)
    after_px = int((mid_recovered > 0).sum())
    print(f"gray mask px: before opening {before_px}, after open+dilate "
          f"{after_px} "
          f"(removed {before_px - after_px}, "
          f"{100*(before_px-after_px)/max(before_px,1):.1f}%)")

    # 4. CC analysis on the recovered mask.
    n, _, stats, cent = cv2.connectedComponentsWithStats(mid_recovered, 8)
    de = cal["data_extent_box"]
    de_left, de_right = de["left"], de["right"]
    de_top, de_bottom = de["top"], de["bottom"]
    # The 27°C series sits in a narrow y band at y ≈ 0.965-0.978; restrict
    # detections to that band to drop axis-text and frame-corner noise.
    band_y_top = (0.978 - by) / my   # higher y → lower row
    band_y_bot = (0.965 - by) / my
    band_row_lo = min(band_y_top, band_y_bot)
    band_row_hi = max(band_y_top, band_y_bot)
    squares = []
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (4 <= w_ <= 24 and 4 <= h_ <= 24): continue
        cx_, cy_ = float(cent[i][0]), float(cent[i][1])
        if not (de_left <= cx_ <= de_right): continue
        if not (band_row_lo <= cy_ <= band_row_hi): continue
        density = a / (w_ * h_)
        if density > 0.45 and 15 <= a <= 250:
            squares.append((cx_, cy_, a, density))

    # Group detections by integer-day x. The 27°C series is sampled at
    # integer days; keep the highest-area square per (int day) bin, with
    # a y closest to the median of all detections in that bin.
    by_day = {}
    for cx_, cy_, a, d in squares:
        x_data = mx * cx_ + bx
        day = int(round(x_data))
        by_day.setdefault(day, []).append((cx_, cy_, a, d))
    kept = []
    for day, recs in sorted(by_day.items()):
        # Use the highest-area detection as the representative
        recs.sort(key=lambda r: -r[2])
        kept.append(recs[0])

    print(f"detected 27°C squares: {len(kept)} "
          f"(from {sum(len(v) for v in by_day.values())} raw, "
          f"grouped into {len(by_day)} integer-day bins)")
    # Convert to data coords and sort by x
    rows = []
    for cx_, cy_, a, d in sorted(kept):
        x = mx * cx_ + bx; y = my * cy_ + by
        rows.append((round(x, 2), round(y, 4), int(a), round(d, 2)))
    for r in rows:
        print(f"  x={r[0]:>6.2f} y={r[1]:>6.4f}  area={r[2]:>3d}  density={r[3]}")

    out = os.path.join(HERE, "27c_recovered.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "x", "y", "area", "density"])
        for r in rows:
            w.writerow(["27C", r[0], r[1], r[2], r[3]])
    print(f"\nwrote {out}")

    # Compare against existing data.csv 27°C rows
    existing = []
    with open(DATA) as f:
        for r in csv.DictReader(f):
            if r["series"] == "27C":
                existing.append((float(r["age_days"]),
                                  float(r["daily_survival_p"])))
    print(f"\nexisting data.csv 27C rows: {len(existing)}")
    print(f"newly detected:               {len(rows)}")
    # Find newly recovered ones (not within ±1 day, ±0.005 y of existing)
    new_recovered = []
    for x, y, *_ in rows:
        if not any(abs(x - ex) < 1 and abs(y - ey) < 0.005
                    for ex, ey in existing):
            new_recovered.append((x, y))
    print(f"newly recovered (not in existing): {len(new_recovered)}")
    for x, y in new_recovered:
        print(f"  ({x}, {y})")


if __name__ == "__main__":
    main()
