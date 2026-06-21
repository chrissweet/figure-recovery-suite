#!/usr/bin/env python3
"""
crop_plot_frames.py — for each chart, crop image.png to plot_frame_box and
data_extent_box from its calibration.json, and produce an overlay showing
both boxes on the source image.

Outputs (per chart, in extractor results dir):
  plot_frame_crop.png       — cropped to plot_frame_box (visible plot region)
  plot_frame_overlay.png    — full image with green plot_frame_box rect
                              and red data_extent_box rect
  coordinate_box_crop.png   — cropped to data_extent_box (tick-range box)
  coordinate_box_overlay.png — same as plot_frame_overlay (kept for parity)
"""
import cv2
import json
import os

BASE = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite"
CORPUS = f"{BASE}/corpora/aedes-aegypti-2014/charts"
RESULTS = f"{BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014"

CHART_IDS = ["el-60-a", "el-60-b", "el-62", "el-75", "el-80",
             "el-88", "el-94", "el-100"]


def crop_and_overlay(cid):
    img_path = f"{CORPUS}/{cid}/image.png"
    cal_path = f"{RESULTS}/{cid}/calibration.json"
    if not (os.path.exists(img_path) and os.path.exists(cal_path)):
        print(f"skip {cid}: missing files"); return
    img = cv2.imread(img_path)
    cal = json.load(open(cal_path))
    pf = cal["plot_frame_box"]
    L, T, R, B = pf["left"], pf["top"], pf["right"], pf["bottom"]
    cv2.imwrite(f"{RESULTS}/{cid}/plot_frame_crop.png", img[T:B + 1, L:R + 1])

    # Overlay both boxes (green = plot_frame, red = data_extent if present)
    overlay = img.copy()
    cv2.rectangle(overlay, (L, T), (R, B), (0, 255, 0), 2)
    if "data_extent_box" in cal:
        d = cal["data_extent_box"]
        cv2.rectangle(overlay, (d["left"], d["top"]),
                      (d["right"], d["bottom"]), (0, 0, 255), 2)
        cv2.imwrite(f"{RESULTS}/{cid}/coordinate_box_crop.png",
                    img[d["top"]:d["bottom"] + 1, d["left"]:d["right"] + 1])
    cv2.imwrite(f"{RESULTS}/{cid}/plot_frame_overlay.png", overlay)
    cv2.imwrite(f"{RESULTS}/{cid}/coordinate_box_overlay.png", overlay)
    print(f"{cid}: cropped {R - L + 1}x{B - T + 1} at ({L},{T})")


def main():
    for cid in CHART_IDS:
        crop_and_overlay(cid)


if __name__ == "__main__":
    main()
