# Methodology: Extracting Numeric Data from Chart Images

A practical methodology for recovering numbers from a raster image of a chart when the underlying data is not available. Written from hands-on extraction of scatter plots, multi-series line plots, and histograms out of papers and screenshots. The companion `graph-data-extraction` skill packages this as runnable steps and helper scripts for Claude Code; this document is the human-readable rationale.

## The core principle

Digitization is not finished when you have a table of numbers. It is finished when you have **re-plotted those numbers and confirmed the reconstruction matches the original**. This "close the loop" test is the heart of the method.

The reason is empirical. A column of extracted values gives you no way to see that the calibration is off by a few percent, or that a legend box silently clamped a stretch of a curve, or that a dark trend line was misread as data points. Those errors are obvious the instant you overlay a re-plot on the source image, and nearly impossible to spot otherwise. Across real extractions, legend-occlusion artifacts repeatedly survived the first pass and were caught only at the re-plot. Build the loop in from the start.

## Five phases

### Phase 1 — Obtain a clean, high-resolution image

Resolution is accuracy: more pixels per data unit means smaller reading error. For figures inside PDFs, render the page at 300 DPI (`pdftoppm -png -r 300 -f PAGE -l PAGE`) rather than using a low-res embedded image. View the image yourself before writing any code, to identify the chart type, axis ranges, series and colors, and hazards (a legend over the data, dense markers, log axes, gridlines colored like a series). Crop to one panel at a time.

### Phase 2 — Calibrate pixel space to data space

This determines whether every number is right or wrong. Find the plot frame, then find the pixel positions of at least two tick labels per axis and pair them with the printed tick values. Fit `value = m·pixel + b` (or fit in log space for log axes). Two cautions that catch most mistakes:

- Do not assume the axis begins at the frame edge. Plotting libraries inset the first tick. Anchor on labeled ticks.
- Sanity-check by plugging the tick pixels back into the fit and confirming you recover the printed values. If 0.0 comes back as 0.06, the tick detection caught stray text (often a rotated axis title); narrow the detection band and refit before going on.

### Phase 3 — Extract, by chart type

- **Scatter**: color-threshold markers, take connected-component centroids, split overlapping markers by area ratio + k-means, drop off-panel detections.
- **Line/curve**: one color mask per series; per x-column take the median row of that color; resample to a regular x-grid.
- **Bar**: per bar, find the top of the colored column; handle negative bars relative to the value-0 baseline.
- **Histogram**: per x-column take the top of the colored region; report the per-bin envelope.

The failure modes that matter are not the happy-path code but the hazards: legend occlusion (a series-colored box/swatch over the data), gridline/series color collision, overlapping markers, and decorations (trend lines, error bars) matching a series color. Filter to inside the frame and to plausible value ranges; raise saturation floors to exclude pale gridlines.

### Phase 4 — Re-plot and close the loop (required)

Re-plot the extracted CSV with the same chart type, axis ranges, and series colors as the original, then compare side by side. Check that series shapes, orderings, crossings, and endpoint values match. A monotonic series that suddenly jumps or flatlines is almost always a legend-occlusion artifact from Phase 3: repair the occluded x-span by linear interpolation between the clean neighbors on each side, regenerate the CSV, and re-plot again. For scatter plots where the original printed a regression equation or R², refit the extracted points and compare; close agreement is strong evidence of fidelity, divergence signals a calibration or detection error. Iterate until the reconstruction matches.

### Phase 5 — Deliver with honest caveats

Write the corrected CSV and save the reconstruction image. State plainly that the data is pixel-estimated, not the original: give an error budget tied to the calibration (e.g. ±0.3 in x, ±0.5 in y), name any spans that are interpolations rather than direct reads, note likely undercounts in dense clusters, report the scatter refit comparison, and recommend the original source data for anything beyond drafts or rough re-analysis. If Phase 4 changed values, say the corrected file supersedes earlier intermediate ones.

## Why the loop is non-negotiable

Every other phase can be done carefully and still produce wrong numbers, because the things that go wrong (calibration offsets, occlusions, color collisions) are systematic and invisible in the output table. The re-plot converts an invisible numeric error into a visible geometric mismatch. It is cheap, it is fast, and it is the only step that actually proves the extraction worked. Treat it as the definition of "done."

## What this method covers, and what it doesn't

This skill is moderately general, not universal. Honest framing matters because over-claiming wastes the user's time when the method silently under-performs.

**The bones of the method carry across most matplotlib-style and Excel-style chart figures:**

- the five-phase workflow itself,
- tick-cluster calibration (with the y-band crop above the x-axis to stop the corner "0" label from contaminating the fit),
- legend-bounding-box exclusion *before* color masking,
- the erode-by-(line-width + 2) trick to wipe connector lines and recover discrete markers (recipe §3a),
- the aspect-ratio > 2.5 filter for dashed-line fragments,
- the close-the-loop validation step, which is the only step that converts an invisible numeric error into a visible geometric mismatch.

**Every numeric threshold is chart-specific.** HSV ranges are tuned for high-saturation matplotlib defaults plus common Office-y palettes. Pastels, transparent fills, dark themes, and custom corporate palettes need re-tuning. `thin_h`, `marker_span`, gray cutoffs, erosion kernel sizes, and mask exclusion rectangles are hand-set per figure. There is no autonomous "drop image in, get CSV out" mode and this skill does not pretend to provide one.

**The fit-curve subtraction recipe (§3b) is the most fragile addition.** It handles thin uniform-thickness curves passing through markers, where the marker height range is known. It has four failure modes documented inline:

1. *Filled markers sitting on a solid curve*: fundamentally not fixable column-wise, because inside the marker's own columns there is no "outside the marker" to use as evidence. The marker CC stays elongated and the aspect-ratio filter rejects it. Validated under-count on el-94 27°C: 14 vs 25.
2. *Dotted curves whose dots are marker-height-spaced*: the pair-preservation rule keeps them as phantom open markers. Workaround: fit a spline through surviving CC centroids and drop CCs within ε of the spline that have density < 0.3.
3. *Steep curves*: at near-vertical sections the per-column thickness exceeds `thin_h` so the curve is classified as "thick = marker" and preserved. Algorithm silently fails over that part of the chart.
4. *Crossing curves*: at a crossing, two thin runs at marker-height spacing get preserved as a phantom open marker.

**What true generality would require**, and which is out of scope for a pure-vision skill, is either a learned marker-detection model (small CNN on patches) or a workflow where the user clicks one marker in a UI and the system template-matches the rest. Until then, every extraction should be validated by the Phase-4 re-plot and the result reported with the caveats called out plainly.
