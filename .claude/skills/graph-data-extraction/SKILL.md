---
name: graph-data-extraction
description: Extract numeric data from chart and plot images (scatter plots, line/curve plots, bar charts, histograms) when the underlying data is not provided, and recover values at the pixel level when a chart has no data labels. Use this whenever a user uploads or points to a figure (PNG/JPEG/PDF page) and asks to "extract the data", "get the points", "digitize this plot", "read the values off this graph", "turn this chart into a CSV/table", or reconstruct/re-plot a figure. Also use when a paper figure has unlabeled curves whose numbers the user wants recovered. Pixel-level tracing is the core capability here, so reach for this skill even when the request sounds simple ("can you get the points?") because reliable digitization needs calibration and a verification loop, not eyeballing.
---

# Graph Data Extraction (chart digitization)

Recover numeric data from a raster image of a chart when you don't have the source numbers. The output is a CSV (or table) of calibrated data points, plus, when useful, a reconstructed re-plot used as a self-check.

The single most important idea in this skill: **digitization is not done until you have re-plotted the extracted data and compared it against the original.** Calibration errors and occlusion artifacts (legends, gridlines, overlapping markers) are nearly invisible in a column of numbers but jump out instantly when you overlay the re-plot on the source. Treat the re-plot as a mandatory test that closes the loop, not as an optional nicety. In practice this step is where most real bugs are caught.

## When to use vs. when not to

Use this skill when the data behind a figure is unavailable and must be read from pixels. Do NOT use it when:
- The numbers are already printed on the chart or in an adjacent table (just transcribe them).
- The user supplied the underlying data/CSV (plot from that instead).
- The "chart" is actually a diagram, schematic, or flowchart with no quantitative axes (describe it instead).

If a figure has *some* labeled values (e.g. bar-top labels) and *some* unlabeled series, transcribe the labeled parts and pixel-extract only the unlabeled series.

## Environment setup

Extraction is done with Python + OpenCV + NumPy; re-plotting with Matplotlib. Network is often disabled, so check what's already installed before assuming a `pip install` works:

```bash
python3 -c "import cv2, numpy, matplotlib; print('ok')" 2>&1 | tail -1
which pdftoppm pdfimages   # poppler tools, for getting figures out of PDFs
```

If a package is missing and the network is up, `pip install opencv-python-headless numpy matplotlib --break-system-packages -q`. If the network is down, work with whatever is present (`pdftoppm`/`pdfimages` from poppler are usually available and cover the PDF case).

## The workflow

The process is always the same five phases regardless of chart type. Phases 1-2 are setup, 3 is the type-specific extraction, 4-5 are the verification loop.

### Phase 1 — Get a clean, high-resolution image of the plot

- If the figure is inside a PDF, render the page at 300 DPI rather than using the embedded thumbnail: `pdftoppm -png -r 300 -f <page> -l <page> input.pdf out`. Higher DPI means more pixels per data unit, which directly reduces reading error.
- `view` the image yourself first. Confirm it actually contains a chart with quantitative axes, identify the chart type, the axis ranges, the series and their colors, and note hazards: a legend box sitting over the data, dense/overlapping markers, log axes, gridlines that share a color with a series.
- Crop to the single plot panel you're extracting (multi-panel figures: do one panel at a time). Save the crop; you'll reference its pixel coordinates throughout.

### Phase 2 — Calibrate pixel space to data space

This is the step that determines whether every number you produce is right or wrong, so do it carefully.

1. Locate the plot frame (the axis box). Find it as long dark rows/columns, or fall back to viewing a crop and reading edges. Record left/right/top/bottom pixel coordinates.
2. Find the **tick-label pixel positions** for at least two ticks per axis (more is better — it lets you fit a line and detect nonlinearity). Detect the dark text clusters in the margin band just outside each axis and group them into label centers.
3. Build the mapping. For a linear axis, fit `value = m * pixel + b` through the tick (pixel, value) pairs. **Do not assume the axis starts at the frame edge** — matplotlib commonly insets the first tick. Always anchor on labeled ticks, not on the box corners.
4. Sanity-check the fit: plug the known tick pixels back in and confirm you recover the printed tick values to within a fraction of a unit. If `0.0` comes back as `0.06`, your fit is contaminated (often by axis-title text caught in the label band) — narrow the detection band and refit.
5. Watch for **log axes** (tick labels like 1, 10, 100 unevenly spaced): map in log space, i.e. fit `log10(value) = m*pixel + b`.

See `references/calibration.md` for robust tick-detection code and the log-axis variant.

### Phase 3 — Extract the data (by chart type)

Pick the matching recipe in `references/extraction_recipes.md` (which now starts with a "Quick chooser" table). The covered types:

- **Scatter plot** → color-threshold, find CCs, take centroids. Split merged blobs (overlapping points) by area-ratio + k-means.
- **Scatter with error bars** → §2a walk-with-gap routine bridges the marker-fill that interrupts the error-bar arm.
- **Grayscale-shape scatter** → §2b classifies series by area density (filled disk / solid square / open diamond) when there's no color cue. Less reliable; expect 70-90 %.
- **Line / curve plot** → one color mask per series; per x-column take the median row.
- **Line plot with markers AT integer x values** → §3a. Erode the connector line away (kernel 2 px wider than line thickness), then CC + centroid. The naive "color mask + CC" approach gives one giant blob for line + all markers; erosion separates them cleanly.
- **Scatter where a smooth fit curve passes through the markers in the same color** → §3b. Subtract the curve via per-column thin-run subtraction with paired-edge preservation (thin runs are line; paired thin runs at marker-height spacing are an open marker's top/bottom edges). Run BEFORE CC classification.
- **Bar chart** → §4 per bar, find the top of the colored fill. For **stippled or dotted fills** that fragment under CC, §4a scans for the bar's dark *outline* row instead. §4b covers upper error-bar caps (lower caps are typically occluded by the bar fill).
- **Histogram** → take the top of the colored region per x-column; report the per-bin envelope.

Common extraction hazards and how to handle them are in `references/extraction_recipes.md` under "Hazards". The big ones:

- **Legend occlusion**: a legend swatch sits over the data. Wipe out the legend bounding box on the color mask *before* CC, and widen the exclusion by ~30 rows past the visible text (descenders bleed in).
- **Dashed/dotted fit lines sharing a series color**: the dash segments survive erosion as marker-sized blobs and inflate the count. Filter by aspect ratio (`max(w,h)/min(w,h) > 2.5` → not a marker).
- **Gridline/series color collision**: raise the saturation floor in the color mask.
- **Overlapping markers**: the area-ratio + k-means split.
- **X-axis "0" label bleeding into y-tick band**: cap the y-band crop at `bot-10`.

### Phase 4 — Re-plot and close the loop (REQUIRED)

Re-plot the extracted CSV with Matplotlib, matching the original's chart type, axis ranges, and series colors. Then compare the reconstruction against the source image, ideally `view` them one after the other. You are looking for:

- Curve shapes and orderings that match (which series is on top, where they cross).
- Start/end values at the axis limits matching the original.
- Monotonic series that should be smooth but show sudden jumps or flat clamped runs → almost always an occlusion artifact from Phase 3 that slipped through. Go back, repair it (interpolate the occluded span), regenerate the CSV, and re-plot again.
- Scatter fits: if the original printed a regression equation or R², refit the extracted points and compare coefficients and R². Close agreement is strong evidence the extraction is faithful; large divergence means a calibration or detection error.

This loop is iterative. Repeat Phase 3 fix → Phase 4 re-plot until the reconstruction matches. In real use, multiple legend-occlusion artifacts have survived the first extraction pass and were only caught here, so do not skip it even when the numbers "look fine."

`references/replot_and_validate.md` has the re-plot templates and the scatter refit check.

### Phase 5 — Deliver

- Write the data to CSV in `/mnt/user-data/outputs/` (one column per axis/series; for resampled curves, a shared x column plus one column per series). If you discovered and repaired occlusions in Phase 4, make sure the delivered CSV reflects the corrected values, and say so — earlier intermediate CSVs are superseded.
- **Write a `calibration.json` next to the CSV** capturing the plot geometry: image size, the rectangle enclosing the axes and plot (pixel bounding box), the data tick range and its corresponding pixel box, and the linear axis calibration. Downstream consumers often need the plot region in pixel coords to re-render or to align with other extractions. Use `scripts/write_calibration.py` (programmatic API or CLI) to produce this consistently — don't roll your own format.
- Save the reconstruction as PNG (and PDF if the user might want vector) so the user can see the loop was closed.
- Present files with `present_files`.

The `calibration.json` schema:

```json
{
  "image_size": {"width": W, "height": H},
  "plot_frame_box": {
    "offset": {"x": ..., "y": ...},     // top-left of plot in image coords
    "size":   {"width": ..., "height": ...},
    "left": ..., "top": ..., "right": ..., "bottom": ...,
    "description": "..."
  },
  "pixels_per_coordinate_unit": {
    "x": ...,                            // |1 / m_x|, px per x-unit
    "y": ...,                            // |1 / m_y|, px per y-unit
    "x_unit_label": "...", "y_unit_label": "..."
  },
  "data_to_pixel_formula": {
    "col": "col = (x_value - b_x) / m_x",
    "row": "row = (y_value - b_y) / m_y"
  },
  "data_range": {"x_min": ..., "x_max": ..., "y_min": ..., "y_max": ...},
  "axis_calibration": {
    "x_axis": {"formula": "...", "m": ..., "b": ..., "inverse": "..."},
    "y_axis": {...}
  },
  "worked_example": {                    // sanity-check the formula visually
    "scenario": "...",
    "input": {"x": ..., "y": ...},
    "compute": ["col = ...", "row = ..."],
    "result": {"col": ..., "row": ...},
    "verification": "..."
  },
  "detection_internals": { ... }         // axis-line detections + the rule used
}
```

A colleague needs three things to find any point in pixel coords: the plot frame's `offset`, the `pixels_per_coordinate_unit` ratio, and the data range — all top-level fields. The full formula is also written out in `data_to_pixel_formula` so the conversion is two arithmetic lines, no calibration math required. The `worked_example` confirms the formula on one known point.

For a corpus of charts, bundle the per-chart `calibration.json` files into one set-wide `set_calibration.json` with a `summary_table` (for quick scanning) and a `charts` dict keyed by chart-id. An example is at `docs/example_set_calibration.json`.

## Always state the caveats

Pixel-extracted data is an estimate, never the original dataset. Every delivery must say so plainly. Be specific about the error budget and the known gaps rather than giving a blanket disclaimer:

- Give an approximate per-point error tied to the calibration (e.g. "roughly ±0.3 in x and ±0.5 in y" based on pixels-per-unit and marker size).
- Name any spans that are interpolations rather than direct reads (occluded regions).
- Note points likely lost to overlap in dense clusters.
- For scatter, report the refit-vs-printed comparison as the fidelity evidence.
- Recommend the original source data over the extraction for anything beyond slides/drafts/rough re-analysis.

## Reference files

- `references/calibration.md` — frame and tick detection, linear and log axis fitting, calibration sanity checks.
- `references/extraction_recipes.md` — quick chooser, per-chart-type extraction code (scatter + error bars, grayscale-shape scatter, line/curve, marker-on-line, bar incl. stippled-fill variant + bar error-bar caps, histogram), and the Hazards section.
- `references/replot_and_validate.md` — Matplotlib re-plot templates per chart type, matplotlib default color cycle, the scatter refit check, and the artifact-detection heuristics for the loop.
- `scripts/calibrate.py` — detect plot frame and tick-label pixel centers from the command line.
- `scripts/extract_markers.py` — erode-line-away + CC + centroid marker detection from the command line.
- `scripts/subtract_curves.py` — per-column thin-run subtraction with paired-edge preservation (§3b).
- `scripts/write_calibration.py` — emit `calibration.json` capturing the plot frame box, data extent box, and axis calibration. Use this in Phase 5 alongside `data.csv`.
- `scripts/check_artifacts.py` — scan an extracted CSV for clamped runs, spikes, and monotonicity violations.
