#!/usr/bin/env python3
"""Feedback-loop extractor — iteration driver.

Iterates the extract -> re-project -> compare cycle on a single chart.
At each step:
  1. Render the current claim set to a pixel-level data layer (no matplotlib)
  2. Measure per-series IoU between source and replot data layer
  3. Run Predicate A (negative-space): unclaimed source components
  4. Run Predicate B (glyph discriminator): claims to drop
  5. Update claim set: add high-confidence A proposals, drop B-flagged claims,
     and blacklist dropped claims' pixel positions
  6. Test convergence; loop or terminate

Iteration 0's claim set comes from a bootstrap (the v3 extractor's data.csv).
This isolates the research question (is the LOOP useful as verification?)
from the bootstrap extraction quality.

GT is never consulted. All signals come from the source image and the
extracted artifacts.
"""
import csv
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "predicates"))
sys.path.insert(0, os.path.join(HERE, "..", "render"))
sys.path.insert(0, os.path.join(HERE, "..", "compare"))

from pixel_replot import render
from per_series_iou import compute as compute_iou
from negative_space import scan as ns_scan
from glyph_discriminator import score as gd_score
from color_tolerance import autotune as autotune_tolerances


MAX_ITERATIONS = 4
IOU_FLOOR = 0.85   # mean per-series IoU floor for "converged"


def load_rows(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"layer_idx": int(r.get("layer_idx", "0") or 0),
                              "layer_type": r.get("layer_type", "Scatter Plot"),
                              "series": r.get("series", "default"),
                              "x": float(r["x"]), "y": float(r["y"])})
            except (KeyError, ValueError):
                continue
    return rows


def write_rows(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in rows:
            w.writerow([r["layer_idx"], r["layer_type"], r["series"],
                          r["x"], r["y"]])


def pixel_to_data(col, row, calibration):
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    x_scale = x_ax.get("scale", "linear")
    y_scale = y_ax.get("scale", "linear")
    if x_scale == "log10":
        x = float(10 ** (mx * col + bx))
    else:
        x = float(mx * col + bx)
    if y_scale == "log10":
        y = float(10 ** (my * row + by))
    else:
        y = float(my * row + by)
    return x, y


def propose_from_negative_space(ns_report, calibration, chart_metadata):
    """Each likely-marker unclaimed component becomes a candidate Scatter Plot
    claim. Series inherited from the color-mask that found it."""
    out = []
    for sid, ser in ns_report["per_series"].items():
        # Decide the layer type to PROPOSE: if the chart_metadata's series
        # legend marks this series as having a line_style, default to Line
        # Graph; else Scatter Plot.
        layer = "Scatter Plot"
        for spec in chart_metadata.get("series_legend", []):
            if spec.get("series_id") == sid:
                if spec.get("line_style") and not spec.get("marker_shape"):
                    layer = "Line Graph"
                break
        for u in ser["unclaimed"]:
            if u["triage"] != "likely-marker":
                continue
            x, y = pixel_to_data(u["col"], u["row"], calibration)
            out.append({"layer_idx": 0, "layer_type": layer,
                          "series": sid, "x": x, "y": y,
                          "_proposed_iter": True})
    return out


def claim_key(r, calibration):
    """Stable key for a claim: (series, layer_type, pixel_col, pixel_row).
    Used for the dropped-claim blacklist so re-proposals at the same pixel
    don't re-enter on the next iteration."""
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    if x_ax.get("scale", "linear") == "log10":
        col = int((np.log10(r["x"]) - bx) / mx) if r["x"] > 0 else -1
    else:
        col = int((r["x"] - bx) / mx)
    if y_ax.get("scale", "linear") == "log10":
        row = int((np.log10(r["y"]) - by) / my) if r["y"] > 0 else -1
    else:
        row = int((r["y"] - by) / my)
    return (r["series"], r["layer_type"], col, row)


def run(source_image_path, bootstrap_dir, out_dir):
    """Run the loop on one chart.

    Args:
      source_image_path: path to image.png
      bootstrap_dir:    directory containing the iteration-0 calibration.json,
                         chart_metadata.json, and data.csv (typically the v3
                         extractor's output for this chart)
      out_dir:          where to write iteration artifacts and convergence
                         history.
    """
    os.makedirs(out_dir, exist_ok=True)
    iters_dir = os.path.join(out_dir, "iterations"); os.makedirs(iters_dir,
                                                                    exist_ok=True)

    calibration   = json.load(open(os.path.join(bootstrap_dir, "calibration.json")))
    chart_metadata = json.load(open(os.path.join(bootstrap_dir, "chart_metadata.json")))
    rows = load_rows(os.path.join(bootstrap_dir, "data.csv"))

    src_img = cv2.imread(source_image_path)
    H, W = src_img.shape[:2]
    image_size = {"width": W, "height": H}

    # Auto-tune per-series color tolerance from the legend swatch
    tol_per_series = autotune_tolerances(src_img, chart_metadata, calibration)
    print(f"Color tolerance auto-tune:")
    for sid, info in tol_per_series.items():
        nominal = info.get("target_bgr")
        nom_str = f"BGR={tuple(int(v) for v in nominal)}" if nominal is not None else "?"
        tol_str = f"tol={info['tolerance']:.1f}"
        print(f"  {sid}: {nom_str}  {tol_str}  source={info.get('source','default')}")

    history = []
    blacklist = set()

    for it in range(MAX_ITERATIONS):
        it_dir = os.path.join(iters_dir, f"{it}")
        os.makedirs(it_dir, exist_ok=True)

        # Save current claim set
        data_csv_path = os.path.join(it_dir, "data.csv")
        write_rows(data_csv_path, rows)

        # Render data layer
        canvas = render(image_size, calibration, chart_metadata, rows)
        replot_path = os.path.join(it_dir, "replot_data_layer.png")
        cv2.imwrite(replot_path, canvas)

        # Predicate A — negative-space; use auto-tuned tolerance
        # (negative_space.scan accepts a scalar `color_tolerance` only; for
        # this demo use the median of per-series tolerances. Per-series
        # tolerance threading is a Phase-2 cleanup.)
        median_tol = float(np.median([info["tolerance"]
                                        for info in tol_per_series.values()])) \
                       if tol_per_series else 25.0
        ns_report = ns_scan(source_image_path, calibration, chart_metadata,
                              rows, color_tolerance=median_tol)
        with open(os.path.join(it_dir, "negative_space_report.json"), "w") as f:
            json.dump(ns_report, f, indent=2)

        # Predicate B — glyph discriminator; same tolerance
        gd_report = gd_score(source_image_path, calibration, chart_metadata,
                              rows, color_tolerance=median_tol)
        with open(os.path.join(it_dir, "glyph_discriminator_report.json"), "w") as f:
            json.dump(gd_report, f, indent=2)

        # Per-series IoU between source and replot data layer
        iou_report = compute_iou(source_image_path, replot_path,
                                   calibration, chart_metadata,
                                   color_tolerance=median_tol)
        with open(os.path.join(it_dir, "per_series_iou.json"), "w") as f:
            json.dump(iou_report, f, indent=2)

        # Bookkeeping for convergence test
        proposals = propose_from_negative_space(ns_report, calibration,
                                                  chart_metadata)
        proposals = [p for p in proposals
                       if claim_key(p, calibration) not in blacklist]
        drops = [c for c in gd_report["per_claim"] if c["drop"]]
        delta_claims = len(proposals) - len(drops)

        snap = {
            "iter": it, "n_claims": len(rows),
            "mean_iou": iou_report["mean_iou"],
            "weighted_iou": iou_report["weighted_iou"],
            "per_series_iou": {sid: ser["iou"]
                                for sid, ser in iou_report["per_series"].items()},
            "unclaimed_likely_marker_total":
                ns_report["summary"]["total_unclaimed_likely_marker"],
            "drops_this_iter": len(drops),
            "proposals_this_iter": len(proposals),
            "delta_claims": delta_claims,
        }
        history.append(snap)

        print(f"\n[iter {it}] claims={len(rows)} | mean_iou={iou_report['mean_iou']:.3f} | "
               f"proposals(+)={len(proposals)} | drops(-)={len(drops)} | "
               f"delta={delta_claims}")
        for sid, iou in snap["per_series_iou"].items():
            print(f"    {sid:>8}: IoU={iou:.3f}")

        # Convergence test: IoU above floor AND nothing to add/drop
        converged_iou  = iou_report["mean_iou"] >= IOU_FLOOR
        converged_dlt  = (len(proposals) == 0) and (len(drops) == 0)
        if converged_iou and converged_dlt:
            snap["convergence_reason"] = "iou_and_delta_converged"
            print(f"  -> converged (iou >= {IOU_FLOOR} and delta == 0)")
            break

        if it == MAX_ITERATIONS - 1:
            snap["convergence_reason"] = "max_iter_hit"
            print(f"  -> max_iter hit; stopping without convergence")
            break

        # Apply updates for the next iteration:
        #   - blacklist dropped claims' pixel keys
        #   - filter rows to remove dropped claims
        #   - add proposals
        for d in drops:
            blacklist.add((d["series"], "Scatter Plot",
                              int(d["col"]), int(d["row"])))
        drop_keys = {(d["series"], "Scatter Plot", int(d["col"]), int(d["row"]))
                       for d in drops}
        rows = [r for r in rows
                  if (r["series"], r["layer_type"],
                      *_xy_to_pixel(r, calibration)) not in drop_keys]
        for p in proposals:
            # Strip the internal flag before writing as a row
            rows.append({k: v for k, v in p.items() if not k.startswith("_")})

    # Final outputs
    with open(os.path.join(out_dir, "convergence_history.json"), "w") as f:
        json.dump(history, f, indent=2)

    # Side-by-side composite of source vs final data layer
    final_replot = cv2.imread(os.path.join(iters_dir,
                                              f"{history[-1]['iter']}",
                                              "replot_data_layer.png"))
    composite = _side_by_side(src_img, final_replot)
    cv2.imwrite(os.path.join(out_dir, "side_by_side.png"), composite)

    # Final canonical deliverables for compatibility with the scorer
    final_iter_dir = os.path.join(iters_dir, f"{history[-1]['iter']}")
    import shutil
    shutil.copy(os.path.join(final_iter_dir, "data.csv"),
                  os.path.join(out_dir, "data.csv"))
    shutil.copy(os.path.join(bootstrap_dir, "calibration.json"),
                  os.path.join(out_dir, "calibration.json"))
    shutil.copy(os.path.join(bootstrap_dir, "chart_metadata.json"),
                  os.path.join(out_dir, "chart_metadata.json"))
    shutil.copy(os.path.join(final_iter_dir, "replot_data_layer.png"),
                  os.path.join(out_dir, "replot.png"))

    print(f"\nDONE. Outputs in {out_dir}")
    return history


def _xy_to_pixel(r, calibration):
    x_ax = calibration["axis_calibration"].get("x_axis", {})
    y_ax = (calibration["axis_calibration"].get("y_axis")
            or calibration["axis_calibration"].get("y_axis_left"))
    mx, bx = x_ax["m"], x_ax["b"]
    my, by = y_ax["m"], y_ax["b"]
    if x_ax.get("scale", "linear") == "log10":
        col = int((np.log10(r["x"]) - bx) / mx) if r["x"] > 0 else -1
    else:
        col = int((r["x"] - bx) / mx)
    if y_ax.get("scale", "linear") == "log10":
        row = int((np.log10(r["y"]) - by) / my) if r["y"] > 0 else -1
    else:
        row = int((r["y"] - by) / my)
    return col, row


def _side_by_side(a, b, h=420):
    def scale(im, ht):
        ratio = ht / im.shape[0]
        return cv2.resize(im, (int(im.shape[1] * ratio), ht),
                           interpolation=cv2.INTER_AREA)
    a2 = scale(a, h); b2 = scale(b, h)
    gut = np.ones((h, 20, 3), dtype=np.uint8) * 255
    return np.hstack([a2, gut, b2])


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: driver.py <source_image> <bootstrap_dir> <out_dir>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], sys.argv[3])
