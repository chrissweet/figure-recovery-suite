#!/usr/bin/env python3
"""el-94 axis-data verification crops (TDD step 5)."""
import json
import os
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
IMG  = os.path.join(REPO, "corpora", "aedes-aegypti-2014",
                    "charts", "el-94", "image.png")
CAL  = os.path.join(REPO, "extractors", "graph-data-extraction", "results",
                    "aedes-aegypti-2014", "el-94", "calibration.json")
CROPS = os.path.join(HERE, "crops")
os.makedirs(CROPS, exist_ok=True)


def main():
    with open(CAL) as f: cal = json.load(f)
    pf = cal["plot_frame_box"]
    legend = cal["detection_internals"]["legend_exclusion_used_for_frame"]
    left, right, top, bot = pf["left"], pf["right"], pf["top"], pf["bottom"]
    im = cv2.imread(IMG); H, W = im.shape[:2]
    cv2.imwrite(os.path.join(CROPS, "x_tick_strip.png"),
                 im[bot + 2: bot + 34, max(0, left - 5): min(W, right + 5)])
    cv2.imwrite(os.path.join(CROPS, "y_tick_strip.png"),
                 im[max(0, top - 5): min(H, bot + 5), max(0, left - 55): left - 2])
    cv2.imwrite(os.path.join(CROPS, "x_axis_title.png"),
                 im[bot + 35: min(H, bot + 75), max(0, left - 5): min(W, right + 5)])
    cv2.imwrite(os.path.join(CROPS, "y_axis_title.png"),
                 im[0: max(1, top + 50), 0: min(W, left + 250)])
    cv2.imwrite(os.path.join(CROPS, "legend.png"),
                 im[max(0, legend[0] - 5): min(H, legend[1] + 5),
                    max(0, legend[2] - 5): min(W, legend[3] + 5)])
    print(f"wrote crops/  (image {W} x {H}, plot frame ({left},{top})-({right},{bot}))")


if __name__ == "__main__":
    main()
