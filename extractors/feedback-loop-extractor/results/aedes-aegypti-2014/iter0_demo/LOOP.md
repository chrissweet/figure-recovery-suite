# LOOP.md — what the iteration loop would do given these results

This is the diagnostic from **one** iteration on `aedes-aegypti-2014/el-100`. The loop has run once: iteration-0 extract (from v3) → replot → compare. It has NOT yet looped back. This document describes what iterations 1, 2, ... would do given the reports just written.

## Reports from iteration 0

- `replot.png` — fresh templated reconstruction of the v3 `data.csv`
- `side_by_side.png` — source image (left) | replot (right) at same scale, for visual inspection
- `overlay.png` — source image annotated with **green circles** at Predicate-A unclaimed-likely-marker positions and **red X** at Predicate-B dropped claims
- `negative_space_report.json` — Predicate A output (what was missed)
- `glyph_discriminator_report.json` — Predicate B output (what was wrongly claimed)

## Headline numbers

| Predicate | Output | What it means |
|---|---|---|
| A (negative-space) | 47 likely-marker candidates flagged | Pixels in the source matching a series' color, NOT covered by any current marker claim, with marker-like shape (area / aspect). Candidates to propose as new claims in iteration 1 |
| B (glyph discriminator) | 13 of 57 claims dropped as line-fragment | Marker claims whose local neighbourhood is dominated by a horizontal or vertical same-color stroke (i.e. a fragment of the IF_24C dashed line or the IF_30C dotted line, mis-classified as a marker by v3) |

## What iteration 1 would do

1. **Drop the 13 claims Predicate B flagged.** These are removed from `claims.csv` and added to a per-chart "blacklist" so the extractor does not re-propose the same pixel position in subsequent iterations.

2. **Propose new claims from Predicate A's likely-marker candidates.** Each candidate is added to `claims.csv` with its (col, row) position converted to data-space (x, y) via the calibration. The series is inherited from the color mask the candidate was found in.

3. **Re-render the replot** with the updated claim set.

4. **Re-run both predicates.** Compute the per-iteration delta:
   - `claims_added` (new from Predicate A)
   - `claims_dropped` (newly flagged by Predicate B; could include a Predicate-A proposal that the discriminator now rejects, which is healthy)
   - mean per-series **color-mask IoU** improvement between iteration 0 replot and iteration 1 replot, against the source

5. **Convergence test (the AND-condition)**:
   - delta_claims == 0 AND mean per-series IoU improvement < 0.005 → converged, exit
   - else → loop back to step 1 with the new claim set
   - hard cap at MAX_LOOPS = 5

## Honest assessment of the two predicates on this iteration

### Predicate A (negative-space) — works on markers, broken on line series

For the scatter series (24C / 27C / 30C), the per-series breakdown shows:

| series | claims | source_components | unclaimed |
|---|---|---|---|
| 24C | 18 | 48 | 30 (9 likely-marker) |
| 27C | 19 | 0 | 0 |
| 30C | 20 | 95 | 0 |

24C has 9 unclaimed likely-markers — these are real candidates the loop would propose. **But** 27C reports 0 source_components, which is wrong: there are obviously many green markers in the source. The color mask for 27C (#00FF00 pure green ± 25 BGR) is missing the actual rendered shade. This is the **per-chart color tolerance** risk named in the plan — needs auto-tune from observed legend-swatch pixel variance before this predicate is trusted.

For the LINE series (IF_24C / IF_27C / IF_30C), the predicate is flagging unclaimed pixels along the entire line trace as "missing markers" because the line series have zero marker claims (correctly — they're lines, not scatter). **The predicate needs a per-layer-type branch**: for line layers, "claimed" means "within stroke-width of a line_sample row," not "within marker_radius of a centroid." This is a real bug in the current implementation; the green circles along the curves in `overlay.png` are false positives.

### Predicate B (glyph discriminator) — works where color matching works

| series | line-fragment drops | marker kept | uncertain |
|---|---|---|---|
| 24C | 3 | 14 | 1 |
| 27C | 0 | 0 | 19 |
| 30C | 10 | 10 | 0 |

24C and 30C drops are real: the dropped claims have `v_frac` ~ 0.4-0.5 (the same-color mask extends along the column past the crop), which is exactly the signature of the IF_24C dashed line and the IF_30C dotted line. **13 of v3's known 18 FP markers caught** — and the discriminator did this with zero hand-tuning.

27C is all "uncertain" because the color mask isn't finding the actual green pixels (same tolerance issue as Predicate A). When the mask returns no blob in the crop, the predicate can only return "uncertain." Once the color tolerance is right, 27C will partition into marker vs line-fragment cleanly.

## What's missing from the loop today

The demo's iteration 0 is real (extract + replot + compare ran end-to-end) but the LOOP itself is not yet implemented. To turn this into a converging loop, the open work is:

1. **Predicate A line-series branch** — claimed mask for Line Graph rows should cover stroke-width × column extent, not marker disks
2. **Per-chart color tolerance auto-tune** — fit tolerance to the variance of the legend swatch's actual rendered pixels
3. **Loop driver** — the `loop/driver.py` from the plan (Phase 3b) that runs steps 1-5 above with the convergence test
4. **Templated replot polish** — axis labels and ranges from `chart_metadata.json`, not hardcoded

The two predicates as standalone diagnostics are useful TODAY (Predicate B on this chart would drop ~13/18 of the known FPs with no further work). The loop becomes useful when steps 1 + 3 land.

## Verdict on this demo

The two predicates **find what the existing v3 verifier cannot find** (FPs from line fragments; FNs from missed markers) and they do so without GT, on the actual problematic chart. That validates the design direction: the loop is worth building. It also exposes two specific blockers (color tolerance auto-tune, line-series claim model) that are now concrete first-task targets for Phase 1.
