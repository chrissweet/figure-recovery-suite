# Pitfalls and recipes (field guide for the forward pass)

This is the map of where chart extraction goes wrong, learned the hard way from a
Phase-4 audit and a run of deterministic-CV experiments (v4-v8, 2026-06). Each
deterministic method that was tried hit the *same* traps; the lesson is that the
MLLM forward pass should be **told the traps and handed the tools**, then use its
semantic judgment to route around them. The CV tools live in `cv_oracle/` and are
callable from the command line via `python3 -m cv_oracle.cli` (see "Tools" below).

Read this before extracting. For each pitfall: how to recognize it, what to do,
and which tool helps.

---

## Calibration

**P1. Anchor on ticks, not the frame edge.** Matplotlib insets the first tick, so
the axis does NOT start at the plot-frame edge. If you fit `value = m*pixel + b`
assuming `x_min` sits at the left frame line, every number is biased.
- *Recipe:* run `python3 .claude/skills/graph-data-extraction/scripts/calibrate.py IMAGE`
  to get frame + tick pixel centers; read the printed tick VALUES yourself; fit on
  the tick centers. Verify by round-tripping a tick: if `0` comes back as `0.06`,
  the tick detector caught stray axis-title text -- narrow the band and refit.
- *Evidence:* el-60 calibration drift; the worked-example round-trip catches it.

**P2. Formula conventions are inconsistent.** Some charts store `value = m*pixel + b`
(m small), some `col = b + m*value` (m large, inverted), log axes store
`value = 10**(m*pixel+b)`. `cv_oracle.calibration.Calibration` auto-detects from
the `formula` string -- write the formula string, not just m/b.

---

## Markers / scatter

**P3. Markers fuse with a same-color curve -> undercount.** When a marker series
sits on a fit/trend curve of the *same* color, the curve cuts each marker and
connected-components fragments it. el-94 27 degC squares: GT 25, blob detection got
**9**, the generic MLLM pass got **15**.
- *Recipe (best):* **template-match the glyph** -- seed a binary template from one
  clean marker and slide it; partial overlap where the curve cuts still peaks.
  `cv_oracle.cli template` recovered **25/25** on el-94 27 degC.
- *Recipe (alt):* bridge the cut with a vertical morphological close
  (`detect/blobs.bridge_curve_cut`) before blob detection.

**P4. Dotted/dashed curve-dots look like markers -> false positives.** The single
biggest failure mode for every CV detector. A dotted curve is a row of marker-
sized dots at the *same intensity* as a black marker series, so no local detector
(blob, template, intensity-quantization) can separate them -- it's a SHAPE/context
problem, not a brightness one. Template matching exploded to **172+ FP** on aedes
this way.
- *Recipe:* **identify the dotted/dashed curve FIRST** (this is the MLLM's job --
  "these aligned dots lie on a smooth path, so they're a curve, not data"), trace
  it as a curve, then **exclude its pixels before marker detection**. Solid/dashed
  curves can also be removed by eroding by (line-width + 2) -- but dotted dots
  survive erosion, so they need the semantic call.

**P5. Same color, different shape -> series get swapped.** el-88 renders 27 degC
(square) and 30 degC (diamond) in the same gray. Color/blob detection conflates
them.
- *Recipe:* separate by SHAPE with a per-series template (`cv_oracle.cli template`
  one series at a time), not by color.

**P6. Legend swatches get extracted as data points.** A legend marker is a real
glyph of the series color; detection picks it up (synthetic-01: +3 phantom points).
- *Recipe:* mask the plot to data-only first with `cv_oracle.cli canvas` -- it
  whites out everything outside the frame AND the legend box (legend bbox comes
  from the calibration's `detection_internals`). Extract from the canvas.

**P7. Markers on the axis line get clipped.** A point at y=0 sits on the x-axis
spine; a tight frame crop erases it (el-88 30 degC tail diamond at y~=0).
- *Recipe:* use `cv_oracle.cli canvas --pad 0` (don't shrink the frame inward) and
  treat axis-adjacent points specially, or read them off the original image.

**P8. Open markers (rings/hollow diamonds).** Erasing/filling the center leaves a
ring that re-detects as a phantom. Template matching handles the hole shape; blob
detection does not.

---

## Curves / lines

**P9. Log-y: tolerance is RELATIVE; trace in pixel space.** On a log axis a 1px row
error is a large relative-y error. Fit/trace in pixel space and let the calibration
do the `10**(...)` conversion at the end (`Calibration(..., log_y=True)`); don't
fit in data space.

**P10. Curve recovery must EXTEND, never interleave.** If you re-trace a curve and
merge the points into an existing series, the scorer's per-series interpolation is
corrupted and TRUE POSITIVES are destroyed (aedes curve recall 0.741 -> 0.364 when
done naively). Only add curve points OUTSIDE the existing curve's x-coverage
(truncated tails). Curve FP is 0 in the scorer, so extending coverage is free, but
interleaving is not.

**P11. In-range curve misses need density/accuracy, not extension.** owid's curve FN
(92% of its misses) is *inside* the covered x-range -- the trace is just sparse or
slightly off. Extension can't reach it; denser per-column tracing can, but carefully
(see P10).

---

## Bars / error bars

**P12. Categorical bar-x drifts off the ticks.** A continuous x-calibration maps bar
centers to 23.34/26.33/29.34 instead of {24,27,30} (el-62, el-80).
- *Recipe:* `cv_oracle.cli snap-x` snaps to the nearest categorical tick when within
  half a group width. The scorer uses an absolute x-tolerance (1.5) for these.

**P13. Lower error cap occluded by bar fill.** The lower whisker disappears into a
dark/stippled bar (el-62, el-80).
- *Recipe:* mirror the visible upper cap: `y_lo = mean - (y_hi - mean)`, and flag
  it `mirrored_lower_cap` in provenance.

---

## Output schema (cheap mistakes that zero a chart)

**P14. `layer_type` must be EXACT strings.** The scorer routes by substring and is
case-sensitive: `"Line Graph"` -> curves, but `"line"` -> points. v7 wrote `"line"`
and a whole chart scored **0.00**. Use exactly: `Scatter Plot`, `Bar Chart`,
`Line Graph`, `Spline Chart`, `ErrorBarLayer`.

**P15. Match the layer to what you SEE.** A series the metadata calls a "marker"
may be rendered as a line (owid). Emit the layer type you observe, not the one the
legend implies.

---

## The completeness self-check (peel)

After extracting, don't guess whether you got everything -- **subtract what you
found and look at what's left**. `cv_oracle.cli peel` erases your extracted markers
from the canvas and reports residual ink (GT-free). This is the subtractive
close-the-loop (no matplotlib render needed):

    source - extraction ~= empty   <=>   no misses

Crucially, treat the residual as a **reasoning surface, not an auto-merge**. When
peel reports residual at x~=33-38, *you* decide: "is that a missed marker, or the
dotted curve I already traced (P4)?" Auto-merging the residual imports false
positives (V5/V6 did this and lost precision); reasoning about it does not. The
property to aim for: when the residual is empty, extraction is complete.

---

## Tools (callable)

All read GT-free inputs (image, calibration, chart_metadata) -- never ground truth.

    python3 -m cv_oracle.cli canvas   IMAGE CALIB OUT.png [--pad N]
        normalized plot canvas: white outside frame + legend.  (P6, P7)
    python3 -m cv_oracle.cli template IMAGE CALIB '#RRGGBB' [--achromatic] [--thresh 0.55]
        seeded template-match markers of one series -> CSV (x,y).  (P3, P5, P8)
    python3 -m cv_oracle.cli peel     IMAGE CALIB METADATA DATA.csv
        residual markers after subtracting your extraction -> CSV.  (self-check)
    python3 -m cv_oracle.cli snap-x   VALUE TICK1,TICK2,...
        snap a categorical bar-x to the nearest tick.  (P12)

Use them as helpers inside the five-phase workflow; the MLLM decides which to reach
for based on the pitfalls above.
