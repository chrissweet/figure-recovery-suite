#!/usr/bin/env python3
"""Axis-data verification crops for el-60-a.

Saves cropped regions of image.png so a vision read can verify:
  - tick label *values* (does the printed text at each detected tick
    position match the value calibration assumed?),
  - axis titles and units (does the source figure's axis title match the
    column-name claim in data.csv?),
  - any panel label.

Outputs to crops/:
  - x_tick_strip.png        rows just below the x-axis, full width
  - y_tick_strip.png        cols just left of the y-axis, full height
  - x_axis_title.png        band where the x-axis title sits
  - y_axis_title.png        band where the y-axis title sits (rotated)
  - panel_label.png         top-right corner
"""
import json
import os
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-60-a", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-60-a", "calibration.json")
CROPS = os.path.join(HERE, "crops")
os.makedirs(CROPS, exist_ok=True)


def main():
    with open(CAL) as f:
        cal = json.load(f)
    pf = cal["plot_frame_box"]
    left, right, top, bot = pf["left"], pf["right"], pf["top"], pf["bottom"]
    im = cv2.imread(IMG)
    H, W = im.shape[:2]

    # X tick label strip: from row bot+2 to bot+34, the full plot col span
    x_strip = im[bot + 2: bot + 34, max(0, left - 5): min(W, right + 5)]
    cv2.imwrite(os.path.join(CROPS, "x_tick_strip.png"), x_strip)

    # Y tick label strip: cols left-55..left-2, plot row span
    y_strip = im[max(0, top - 5): min(H, bot + 5), max(0, left - 55): left - 2]
    cv2.imwrite(os.path.join(CROPS, "y_tick_strip.png"), y_strip)

    # X-axis title band: below tick labels, roughly rows bot+35..bot+70
    x_title = im[bot + 35: min(H, bot + 75), max(0, left - 5): min(W, right + 5)]
    cv2.imwrite(os.path.join(CROPS, "x_axis_title.png"), x_title)

    # Y-axis title band: rotated text in cols 0..left-55, plot row span
    y_title = im[max(0, top - 5): min(H, bot + 5), 0: max(1, left - 55)]
    cv2.imwrite(os.path.join(CROPS, "y_axis_title.png"), y_title)

    # Panel label: top-right corner
    pl = im[0: min(H, top + 40), max(0, right - 60): W]
    cv2.imwrite(os.path.join(CROPS, "panel_label.png"), pl)

    # Provenance file
    out = os.path.join(HERE, "axis_data_crops.json")
    with open(out, "w") as f:
        json.dump({
            "image": "image.png",
            "image_size": {"width": W, "height": H},
            "plot_frame": {"left": left, "top": top, "right": right, "bottom": bot},
            "crops": {
                "x_tick_strip":   {"rows": [bot + 2, bot + 34],
                                    "cols": [max(0, left - 5), min(W, right + 5)]},
                "y_tick_strip":   {"rows": [max(0, top - 5), min(H, bot + 5)],
                                    "cols": [max(0, left - 55), left - 2]},
                "x_axis_title":   {"rows": [bot + 35, min(H, bot + 75)],
                                    "cols": [max(0, left - 5), min(W, right + 5)]},
                "y_axis_title":   {"rows": [max(0, top - 5), min(H, bot + 5)],
                                    "cols": [0, max(1, left - 55)]},
                "panel_label":    {"rows": [0, min(H, top + 40)],
                                    "cols": [max(0, right - 60), W]},
            },
            "claimed_data_csv_columns": ["series", "time_days",
                                          "percentage_parous_females"],
            "claimed_x_labels": [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23],
            "claimed_y_labels": [1.00, 0.80, 0.60, 0.40, 0.20, 0.00],
        }, f, indent=2)
    print(f"wrote crops/ and {out}")


if __name__ == "__main__":
    main()
