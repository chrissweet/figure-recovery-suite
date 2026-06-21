#!/usr/bin/env python3
"""
build_set_calibration.py — aggregate per-chart calibration.json into one
set_calibration.json with a summary_table + a charts dict keyed by chart id.

Run after compute_calibration.py has produced per-chart calibration.json
files.
"""
import json
import os

BASE = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite"
RESULTS = f"{BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014"
CORPUS = f"{BASE}/corpora/aedes-aegypti-2014/charts"

CHART_IDS = ["el-60-a", "el-60-b", "el-62", "el-75", "el-80",
             "el-88", "el-94", "el-100"]


def chart_title(cid):
    p = f"{CORPUS}/{cid}/metadata.json"
    try:
        m = json.load(open(p))
        return m.get("short_title") or m.get("chart_title") or "Untitled"
    except Exception:
        return "Untitled"


def main():
    out = {
        "set": "aedes-aegypti-2014 (paper e9d2f862-1273-47c2-a91f-95b0c6c6f8bd)",
        "n_charts": len(CHART_IDS),
        "format_version": "1.0",
        "description": (
            "Aggregated plot-frame calibration for the 8-chart aedes corpus. "
            "Each chart entry has plot_frame_box (offset + size), per-axis "
            "pixels_per_coordinate_unit ratios, and closed-form data_to_pixel "
            "formulas. A worked example per chart sanity-checks the math "
            "visually against image.png."
        ),
        "usage": {
            "step_1": "Pick a chart by id (e.g. 'el-62'). Open charts['el-62'].",
            "step_2": "Read plot_frame_box.offset = top-left corner in image.png.",
            "step_3": "Read pixels_per_coordinate_unit.x / .y for px/data ratios.",
            "step_4": ("Use data_to_pixel_formula to convert (x_value, y_value) "
                       "→ (col, row). The worked_example shows the calc for "
                       "one known point."),
        },
        "summary_table": [],
        "charts": {},
    }
    for cid in CHART_IDS:
        p = f"{RESULTS}/{cid}/calibration.json"
        if not os.path.exists(p):
            print(f"skip {cid}: no calibration.json")
            continue
        cal = json.load(open(p))
        out["charts"][cid] = {
            "image_path_relative": f"corpora/aedes-aegypti-2014/charts/{cid}/image.png",
            "title": chart_title(cid),
            **cal,
        }
        pf = cal["plot_frame_box"]
        out["summary_table"].append({
            "chart_id": cid,
            "title": chart_title(cid),
            "image_size": f"{cal['image_size']['width']}x{cal['image_size']['height']}",
            "plot_frame_offset": [pf["offset"]["x"], pf["offset"]["y"]],
            "plot_frame_size": [pf["size"]["width"], pf["size"]["height"]],
            "pixels_per_x_unit": cal["pixels_per_coordinate_unit"]["x"],
            "pixels_per_y_unit": cal["pixels_per_coordinate_unit"]["y"],
            "x_unit_label": cal["pixels_per_coordinate_unit"]["x_unit_label"],
            "y_unit_label": cal["pixels_per_coordinate_unit"]["y_unit_label"],
            "data_range": cal["data_range"],
        })
    out_path = f"{RESULTS}/set_calibration.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {out_path}")
    for row in out["summary_table"]:
        print(f"  {row['chart_id']:8s}  offset=({row['plot_frame_offset'][0]},{row['plot_frame_offset'][1]})  "
              f"{row['plot_frame_size'][0]}x{row['plot_frame_size'][1]}  "
              f"px/x={row['pixels_per_x_unit']:.2f} px/y={row['pixels_per_y_unit']:.2f}")


if __name__ == "__main__":
    main()
