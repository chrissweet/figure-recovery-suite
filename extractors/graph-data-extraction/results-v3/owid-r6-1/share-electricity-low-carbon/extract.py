"""Extraction script for owid-r6-1 / share-electricity-low-carbon.

OWID multi-series line chart (8 country/region series) recovered pixel-by-pixel.
Calibration: linear x (year) from interior tick labels 1990..2020 (1985 and 2025
labels are inset and excluded from the fit). Linear y (percent) from gridlines
detected at percentages 0/20/40/60/80/100 (uniform 77 px / 20 pp).

Per-series HSV+RGB color masks pick out each line; for each integer year the
column window's median y becomes the value. Occluded years (US 1993-1994 and
2012-2014, China 1986) are linearly interpolated between neighbours and flagged
in interpolated_points.json.
"""
import csv
import json
import os
from collections import defaultdict

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_IMG = '/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/share-electricity-low-carbon/image.png'
OUT = HERE

# --- Calibration (from interior-year and gridline fits) ---
M_X = 0.060935756491891355  # year = M_X * col + B_X
B_X = 1981.6877205878168
M_Y = -0.26022184960660394  # pct  = M_Y * row + B_Y
B_Y = 133.09751064104213

Y_TOP, Y_BOT = 127, 511   # plot row range (100% and 0% gridlines)
X_LEFT, X_RIGHT = 50, 714

def year_to_col(yr): return (yr - B_X) / M_X
def row_to_pct(row): return M_Y * row + B_Y


def build_masks(img):
    """Per-series boolean masks restricted to the plot region."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    B, G, R = img[:, :, 0], img[:, :, 1], img[:, :, 2]

    def crop_plot(mask):
        m = mask.copy()
        m[:Y_TOP] = False
        m[Y_BOT + 1:] = False
        m[:, :X_LEFT] = False
        m[:, X_RIGHT + 1:] = False
        return m

    # Hue ranges and saturation/value gates established by sampling each
    # series at its label and along its line; see calibration.json detection_internals.
    return {
        'Sweden':         crop_plot((H >= 130) & (H <= 144) & (S >= 100) & (V >= 100) & (V <= 220)),
        'France':         crop_plot((H >= 0)   & (H <= 12)  & (S >= 150) & (V >= 80)  & (V <= 220)),
        'United Kingdom': crop_plot((H >= 170) & (H <= 179) & (S >= 100) & (V >= 80)  & (V <= 200)),
        'Germany':        crop_plot((H >= 13)  & (H <= 22)  & (S >= 100) & (V >= 80)  & (V <= 220)),
        # US: hue overlaps China; discriminator is "dark" (V <= 140) at high sat.
        'United States':  crop_plot((H >= 100) & (H <= 115) & (S >= 150) & (V >= 40)  & (V <= 140)),
        'World':          crop_plot((H >= 145) & (H <= 160) & (S >= 70)  & (V >= 130) & (V <= 220)),
        # China: hue overlaps US; discriminator is "muted+light" (V 140-200, S<=160)
        # plus B > R + 30 to reject anti-aliased magenta/red bleed.
        'China':          crop_plot((H >= 105) & (H <= 115) & (S >= 80)  & (S <= 160)
                                    & (V >= 140) & (V <= 200)
                                    & (B.astype(int) > R.astype(int) + 30)),
        'India':          crop_plot((H >= 70)  & (H <= 85)  & (S >= 100) & (V >= 80)  & (V <= 220)),
    }


def extract_per_year(masks, years, half_win=4):
    """Median-y per integer year for each series; None when window too sparse."""
    raw = {name: {} for name in masks}
    for name, mask in masks.items():
        for yr in years:
            xc = year_to_col(yr)
            x0 = max(int(round(xc - half_win)), X_LEFT)
            x1 = min(int(round(xc + half_win)) + 1, X_RIGHT + 1)
            sub = mask[:, x0:x1]
            ys, _ = np.where(sub)
            if len(ys) < 2:
                raw[name][yr] = None
            else:
                raw[name][yr] = round(row_to_pct(float(np.median(ys))), 2)
    return raw


def interpolate(raw, years):
    """Linearly interpolate missing INTERIOR years (don't extrapolate)."""
    results = {name: {} for name in raw}
    interpolated = []
    for name, vals in raw.items():
        valid = [y for y in years if vals[y] is not None]
        if not valid:
            for y in years:
                results[name][y] = None
            continue
        first_v, last_v = valid[0], valid[-1]
        for y in years:
            if vals[y] is not None:
                results[name][y] = vals[y]
            elif first_v <= y <= last_v:
                pv = max(v for v in valid if v < y)
                nv = min(v for v in valid if v > y)
                vv = vals[pv] + (vals[nv] - vals[pv]) * (y - pv) / (nv - pv)
                results[name][y] = round(vv, 2)
                interpolated.append({'series': name, 'year': y, 'value_pct': results[name][y]})
            else:
                results[name][y] = None
    return results, interpolated


def main():
    img = cv2.imread(SRC_IMG)
    masks = build_masks(img)
    years = list(range(1985, 2026))
    raw = extract_per_year(masks, years)
    results, interpolated = interpolate(raw, years)

    SERIES_ORDER = ['Sweden', 'France', 'United Kingdom', 'Germany',
                    'United States', 'World', 'China', 'India']

    # Canonical schema CSV
    with open(os.path.join(OUT, 'data.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['layer_idx', 'layer_type', 'series', 'x', 'y'])
        for name in SERIES_ORDER:
            for yr in years:
                v = results[name][yr]
                if v is not None:
                    w.writerow([0, 'Line Graph', name, yr, v])

    # Wide-format CSV (one column per series), convenient for spreadsheets
    with open(os.path.join(OUT, 'data_wide.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year'] + SERIES_ORDER)
        for yr in years:
            row = [yr] + [(results[n][yr] if results[n][yr] is not None else '') for n in SERIES_ORDER]
            w.writerow(row)

    with open(os.path.join(OUT, 'interpolated_points.json'), 'w') as f:
        json.dump(interpolated, f, indent=2)

    print(f'Wrote data.csv, data_wide.csv, interpolated_points.json')
    print(f'Total points: {sum(1 for n in SERIES_ORDER for y in years if results[n][y] is not None)}')
    print(f'Interpolated: {len(interpolated)}')


if __name__ == '__main__':
    main()
