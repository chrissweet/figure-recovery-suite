#!/usr/bin/env python3
"""Extract bar tops for synthetic-r4-1/02-simple-bar.

Phase 3 (§4 bar chart recipe): per bar, locate the topmost dark outline row
inside the bar's interior column band. Convert (col, row) to (pos, value)
using the calibration in calibration.json.
"""
import csv
import cv2
import numpy as np

IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/synthetic-r4-1/charts/02-simple-bar/image.png"
OUT_CSV = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/synthetic-r4-1/02-simple-bar/data.csv"

# Calibration (consistent with calibration.json)
M_X, B_X = 0.00997002, -1.21632351
M_Y, B_Y = -0.070678, 27.660482

# Bar geometry detected in Phase 2: x-tick label centers
BAR_CENTERS_PX = [121.5, 222.5, 323.5, 422.5, 523.0, 623.5]
CATEGORIES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]

# Frame
TOP_FRAME = 37
BOT_FRAME = 392
# Legend exclusion (top-right inside plot)
LEG_R0, LEG_R1, LEG_C0, LEG_C1 = 40, 70, 540, 690


def extract():
    img = cv2.imread(IMG)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Dark outline mask (bar borders). Exclude top/bottom frame and legend.
    dark = (gray < 80).astype(np.uint8)
    dark[TOP_FRAME - 1:TOP_FRAME + 2, :] = 0
    dark[BOT_FRAME - 1:BOT_FRAME + 2, :] = 0
    dark[LEG_R0:LEG_R1, LEG_C0:LEG_C1] = 0

    rows_out = []
    for name, xc in zip(CATEGORIES, BAR_CENTERS_PX):
        col_lo, col_hi = int(xc) - 25, int(xc) + 25
        band = dark[:, col_lo:col_hi + 1]
        # First row from the top where the bar's horizontal outline shows up
        # across most of the interior width.
        rsum = band.sum(axis=1)
        ys = np.where(rsum > 30)[0]
        ys = ys[(ys > TOP_FRAME + 1) & (ys < BOT_FRAME - 1)]
        if len(ys) == 0:
            continue
        outline_top = int(ys[0])
        # Calibrated values
        x_val = M_X * xc + B_X
        y_val = M_Y * outline_top + B_Y
        # Snap categorical x to integer position
        x_pos = int(round(x_val))
        rows_out.append((0, "Grouped Column Chart", "Throughput", x_pos, round(y_val, 3)))
        print(f"{name}: col={xc} row={outline_top} -> x={x_pos}, y={y_val:.3f}")

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for row in rows_out:
            w.writerow(row)
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    extract()
