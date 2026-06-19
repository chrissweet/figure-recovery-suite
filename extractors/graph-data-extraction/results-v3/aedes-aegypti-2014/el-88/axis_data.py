#!/usr/bin/env python3
"""el-88 axis-data verification crops (TDD step 5).

Same pattern as el-60-a's axis_data.py: crop the tick-label strips,
axis-title bands, panel label, and (here) the legend region. Vision-read
each crop to verify (a) tick label values match calibration's assumptions
and (b) axis titles + series legend match the data.csv column names + series
identities. Output to crops/.
"""
import json
import os
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-88", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-88", "calibration.json")
CROPS = os.path.join(HERE, "crops")
os.makedirs(CROPS, exist_ok=True)


def main():
    with open(CAL) as f:
        cal = json.load(f)
    pf = cal["plot_frame_box"]
    legend = cal["detection_internals"]["legend_exclusion_used_for_frame"]
    left, right, top, bot = pf["left"], pf["right"], pf["top"], pf["bottom"]
    im = cv2.imread(IMG)
    H, W = im.shape[:2]

    # X tick label strip
    cv2.imwrite(os.path.join(CROPS, "x_tick_strip.png"),
                 im[bot + 2: bot + 34, max(0, left - 5): min(W, right + 5)])
    # Y tick label strip
    cv2.imwrite(os.path.join(CROPS, "y_tick_strip.png"),
                 im[max(0, top - 5): min(H, bot + 5), max(0, left - 55): left - 2])
    # X-axis title band
    cv2.imwrite(os.path.join(CROPS, "x_axis_title.png"),
                 im[bot + 35: min(H, bot + 75), max(0, left - 5): min(W, right + 5)])
    # Y-axis title band (rotated text in the left margin) — for el-88 there is
    # no rotated y-title; capture the strip anyway so its absence is recorded.
    cv2.imwrite(os.path.join(CROPS, "y_axis_title.png"),
                 im[max(0, top - 5): min(H, bot + 5), 0: max(1, left - 55)])
    # Legend region (per calibration: rows 280-400, cols 870-980)
    cv2.imwrite(os.path.join(CROPS, "legend.png"),
                 im[max(0, legend[0] - 5): min(H, legend[1] + 5),
                    max(0, legend[2] - 5): min(W, legend[3] + 5)])

    out = os.path.join(HERE, "axis_data_crops.json")
    with open(out, "w") as f:
        json.dump({
            "image": "image.png",
            "image_size": {"width": W, "height": H},
            "plot_frame": {"left": left, "top": top, "right": right, "bottom": bot},
            "legend_exclusion": legend,
            "claimed_data_csv_columns": ["series", "age_days", "survival_proportion"],
            "claimed_x_labels": [0, 10, 20, 30, 40, 50],
            "claimed_y_labels": [1.00, 0.80, 0.60, 0.40, 0.20, 0.00],
            "claimed_series_legend": [
                {"series_id": "24C", "marker_shape": "disk"},
                {"series_id": "27C", "marker_shape": "square"},
                {"series_id": "30C", "marker_shape": "diamond"},
            ],
        }, f, indent=2)
    print(f"wrote crops/ and {out}")


if __name__ == "__main__":
    main()
