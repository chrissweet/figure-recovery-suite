# feedback-loop-extractor — code

Code for the experimental `feedback-loop-extractor` (branch `feedback-loop-extractor`). This is an **experimental branch**, not the canonical extractor. See [Analysis-Feedback-Loop-Off-Course-2026-06-21](../../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md) in the wiki for the diagnosis of why the work in this branch didn't improve on v3.

> **Canonical extractor.** The working, scored extractor is `extractors/graph-data-extraction/code/` (which symlinks to `.claude/skills/graph-data-extraction/`). F1 = 0.90 on aedes-aegypti-2014. This branch's code was intended to feed a diff/density signal back into v3's parameters to improve it; instead it operated on v3's output rows directly, bypassing v3's principled detection logic and never re-scoring against v3's F1. Preserved as a diagnostic record.

## Worth keeping (future-inputs for a properly-targeted feedback loop)

- **`render/pixel_replot.py`** — cv2-only data-layer renderer. Plots markers / lines / bars at the calibration's exact pixel positions on a blank canvas at the source's exact (W, H). NO matplotlib autolayout drift. This is a clean primitive; reusable as-is.
- **`single_pass/count_balance.py`** — per-color pixel count as the convergence signal. On aedes el-100 reduced per-color over-ink by 70 % in one iteration (24C +783 → +237 px; 30C +1751 → +524 px). The 4-stat-per-color summary (px count, CC count, area p90, area max) captured every signal the per-pixel diff was trying to surface, and pointed at action directions (drop FPs, thin strokes).
- **`predicates/color_tolerance.py`** — HSV-hue fallback for cases where the chart_metadata's nominal hex doesn't match source. Recovered the el-100 27C green case where `#00FF00` returned 0 source pixels even at ±60 BGR tolerance.
- **The "local crop" pattern** in `single_pass/local_crop_update.py` — per-region image extraction for diagnosis. Each disagreement CC gets its own small image suitable for VLM adjudication of edge cases.

## Worth discarding

- **`single_pass/{diff_update, absdiff_update, subregion_update, local_crop_update}.py`** — six successive output-row-manipulation update heuristics. Each tried to improve the extraction by editing rows directly in `data.csv`. All produced net-worse per-pixel residual because they bypass v3's principled detection logic. Preserved as artifacts of the diagnostic arc; not a path forward.
- **`predicates/{negative_space, glyph_discriminator}.py`** — diagnostic predicates that operate on the extractor's *output*, not its parameters. Useful as standalone diagnostics; not useful as iteration signals in the way they were used here.
- **`loop/driver.py`** — the iteration driver that called all of the above in a loop. Diverged on el-100 (mean per-series IoU 0.22 → 0.14 over 4 iterations) for the same wrong-layer reason.

## Layout

```
code/
  predicates/
    negative_space.py      Predicate A: source colour mask minus claim-coverage mask -> CC residual
                           -> triage by area/aspect -> "unclaimed-likely-marker" candidates.
                           Standalone diagnostic; misattributes on shared-color charts (el-100 24C
                           and IF_24C both #0000FF).
    glyph_discriminator.py Predicate B: per-claim local-crop shape + neighbour-stroke check.
                           Drops false-positive markers that are actually line fragments.
                           Caught 13 of 18 known FPs on el-100.
    color_tolerance.py     HSV-hue autotune fallback for the case where chart_metadata's nominal
                           hex doesn't match the source's rendered shade.
  render/
    pixel_replot.py        cv2-only renderer. No matplotlib. Pixel-precise placement from
                           calibration. Worth keeping.
  compare/
    per_series_iou.py      Source-mask vs replot-mask IoU per series. Brittle on shared-color
                           series; superseded by per-color pixel-count balance.
  loop/
    driver.py              Iteration loop that wires render + compare + predicates. Diverged on
                           el-100; preserved as record.
  single_pass/
    diff_update.py         v1 attempt: binary presence-mask diff -> drop/add. Net residual worse.
    absdiff_update.py      v2: cv2.absdiff per CC, classify by MEAN colour. Worse still.
    subregion_update.py    v3: per-CC source-only / replot-only / mismatch sub-masks. Still worse.
    local_crop_update.py   v4: per-CC local crop, attribution by closest legend hex (no tolerance
                           gate). 49 adds happened but residual went +3423 px (drew markers where
                           source had thin line fragments).
    count_balance.py       v5: per-colour pixel-count balance. THE ONE THAT WORKED: 70% per-colour
                           over-ink reduction in one iteration. Per-pixel diff went slightly up
                           because the dropped marker positions now show as missed source data;
                           this exposed that per-pixel diff is not the right convergence signal.
  iter0_demo/
    run_demo.py            Early visual demo before the iteration arc began. Compares source vs
                           replot via the binary presence-mask diff that was later abandoned.
  README.md                This file.
```

The result directories sit at the extractor's top level next to this code/ folder:

```
extractors/feedback-loop-extractor/
  DESIGN.md                Original design doc on the branch (commit c8b11d5).
  code/                    (this directory)
  research_demo/el-100/    Iteration artifacts from running loop/driver.py on aedes el-100.
                           4 iterations under iterations/0..3/, plus convergence_history.json
                           and the side-by-side image.
  iter0_demo/              Output files from the early demo (replot.png, overlay.png,
                           side_by_side.png, the two report JSONs, LOOP.md).
  single_pass/             Per-script output directories (one el-100_* subdir per update
                           heuristic). The .py scripts themselves moved into code/single_pass/
                           when this README was added.
```

## How to read the iteration arc

If you want to walk the diagnostic path the way it actually happened, in order:

1. `iter0_demo/run_demo.py` and its outputs — early visual demo of the binary-mask compare
2. `single_pass/el-100/` and `code/single_pass/diff_update.py` — first attempt at diff-driven update
3. `single_pass/el-100_absdiff_iter1/` and `code/single_pass/absdiff_update.py` — switch to cv2.absdiff
4. `single_pass/el-100_subregion_iter1/` and `code/single_pass/subregion_update.py` — per-CC sub-region decomposition
5. `single_pass/el-100_localcrop_iter1/` and `code/single_pass/local_crop_update.py` — per-CC local crops
6. `single_pass/el-100_countbalance/` and `code/single_pass/count_balance.py` — per-colour count balance (the productive signal)
7. The wiki analysis page diagnoses why (1)–(5) failed and (6) partially worked: wrong layer of abstraction. The loop manipulated v3's output rows instead of feeding signals into v3's parameters.

## See also

- `../DESIGN.md` — the original design doc on this branch
- `../../graph-data-extraction/code/README.md` — the canonical v3 extractor's README
- `../../legacy_v1/code/README.md` — the original aedes-specific extractor scripts (the v1 baseline)
- `../../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md` — user's diagnosis of why this branch went off-course
- `../../../wiki/figure-recovery-suite.wiki/Analysis-Replot-Loop-Efficacy-2026-06-20.md` — the analysis that motivated creating this branch in the first place
