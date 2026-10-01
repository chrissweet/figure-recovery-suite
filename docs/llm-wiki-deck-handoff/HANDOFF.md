# Slide handoff: Claude Code extracts data from a chart

For the **llm-wiki deck**. One worked example (Aedes survival combo chart, `el-94`)
carries the whole story. All numbers below are real script outputs, tagged with
their corpus. Source wiki pages are listed at the end.

## The one-line

Given only a chart image, Claude Code writes its own OpenCV pipeline to digitize
it: it locates the plot frame, reads the axis ticks to calibrate, detects every
point and line, **zooms in on the ambiguous spots**, and then re-draws its
extracted data back onto the source image to pixel-check the result — scoring
**F1 = 0.93** on this chart (the hardest in the corpus) and **~0.94 mean across a
28-chart corpus**.

## The slide image

`slide_el94_pipeline.png` — a 3-panel composite (the three panels are also
provided as separate files if you want to place them individually):

| panel | file | what it shows |
|---|---|---|
| 1. Generated OpenCV targets | `el-94_boxes.png` | the regions the model's own code worked on, colored by phase |
| 2. Attention heatmap | `el-94_heatmap.png` | where it zoomed — concentrated, not uniform |
| 3. Pixel-check vs input | `overlay_final.png` | extracted data redrawn on the source to verify |

## What each panel means (speaker notes)

**Panel 1 — the generated code's target regions.** No recipe is given; the model
decides the approach and writes the OpenCV code. Every run follows the same
implicit skeleton, and the boxes show its three phases:
- **blue = calibrate / structure** — tight crops on the y-axis ticks, both x-axis
  ends, and the legend box. This is "find the frame, read the numbers off the
  axes" so pixels can be converted to data coordinates.
- **green = bulk survey** — wide crops sweeping the marker field and the curves.
  This is the main "detect the points and lines" pass.
- **red = ambiguity zoom** — small crops where the signal is locally confusing
  (markers touching, curves fusing).

**Panel 2 — the attention heatmap.** Accumulating those zoom regions shows *where
the model actually looked*. The hot band sits over days ~28-40, exactly where the
three marker series and three fitted curves merge into a grayscale tangle. The
takeaway line for the slide: **the model spends its effort like a human analyst —
surgically, on the hard local spots, not evenly across the chart.**

**Panel 3 — the pixel-check comparison.** This is the verification step: the model
re-plots its extracted markers and curve samples on top of the original image.
Colored dots landing on the drawn glyphs = the extraction matches the picture.
This is how the method catches its own errors before reporting, and it is what
makes the digitization trustworthy rather than eyeballed.

## Suggested slide copy

> **Claude Code digitizes a chart by writing its own vision pipeline**
> - Reads the axes to calibrate pixels → data (no human setup)
> - Detects every point and line, then **zooms in on the ambiguous regions**
> - **Pixel-checks** by redrawing its data on the source image
> - F1 0.93 on the hardest chart; ~0.94 mean over a 28-chart corpus

## Numbers you can quote (all real outputs, corpus-tagged)

- el-94 (aedes-aegypti-2014): **position F1 0.93** (recall 0.88, precision 0.99).
- This run: the model wrote ~25 code executions and saved 21 zoom crops; the
  attention map relocated **17 regions** onto the chart.
- Corpus-wide (28 charts, per-type metric): free-rein mean **0.940**, beating a
  hand-written recipe's 0.891.

## Honest caveats (so nothing on the slide overclaims)

- The **heatmap is reconstructed post-hoc** from the crops the model saved to
  disk, so it is a lower bound on where it looked and has no time-ordering. Fine
  as an illustration; do not present it as a live eye-tracker.
- Scores use a **per-type prototype scorer**, not a hardened benchmark.
- el-94 is a strong worked example; a couple of other chart types (dense multi-
  series lines) still expose a measurement-layer gap, documented in the wiki.

## Source wiki pages

- `Experiment-Free-Rein-Transcript-Review-2026-08-06` — the 6-step pipeline, the
  contaminant handling, and the F1 numbers
- `Analysis-Attention-Map-Visualization-2026-08-12` — the heatmap / box-map method
  and the "attention concentrates on the fusion zone" finding
- `Analysis-Graph-Type-Characterization-2026-08-05` — "zoom is surgical local-
  ambiguity resolution"
- `Experiment-Free-Rein-vs-Structured-2026-08-05` — the 0.940 corpus mean
- `Scoring-Rubric` — how the pixel-check maps to TP/FN/FP and F1
