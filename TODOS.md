# Open refinement work

Last updated: 2026-06-18. Source: [Phase-4 Audit 2026-06-18](https://github.com/chrissweet/figure-recovery-suite/wiki/Phase-4-Audit-2026-06-18). Raw JSON: `docs/audits/phase4-audit-2026-06-18.json`.

The Phase-4 audit found that, on the `aedes-aegypti-2014` corpus, the extraction `run3_meta.json` files self-report defects ("trend line NOT extracted", "Lower error caps NOT extracted", "blue markers on the dashed line classify as dash fragments") and ship anyway. The [Methodology](https://github.com/chrissweet/figure-recovery-suite/wiki/Methodology-Five-Phase-Workflow) is iterative on paper but is currently being run as one-shot in practice.

## Success criteria

Goal: get every chart to **✓ (matches well)**. Current state (baseline from the 2026-06-18 audit):

| chart   | current | top issue blocking ✓                                              |
|---------|---------|-------------------------------------------------------------------|
| el-60-a | ✓       | tight legend exclusion + ~0.4 day x-axis drift on right half      |
| el-60-b | ✗       | trend line missing from replot (self-reported)                    |
| el-62   | ✓       | lower error caps collapsed onto bar top (asymmetric → upward only)|
| el-75   | ✗       | red trend line missing from replot                                |
| el-80   | ✗       | error bars entirely missing, bar x on continuous pixels           |
| el-88   | ✓       | one missed 30°C tail diamond at y≈0; ~1.5 % y-offset on 24°C      |
| el-94   | ✗       | three fit curves missing; 27°C squares severely under-counted     |
| el-100  | ✗       | three IF curves missing; phantom green at (0.645, 0.25); 24°C low |

Target: **8 ✓ rows.** Stretch goal: shrink the "top issue" annotations on the three already-✓ rows.

After fixes, re-run the audit (same workflow as 2026-06-18 — read each `replot.png` and the corresponding `image.png`, judge `matches_original_well: true/false`, list mismatches). Write the new JSON to `docs/audits/phase4-audit-<YYYY-MM-DD>.json` and append a before/after column to this table.

Also re-run `python3 scoring/score.py aedes-aegypti-2014 graph-data-extraction` to confirm CSV-level scores didn't regress: current baseline is **Precision 0.921, Recall 0.876, F1 0.898, Jaccard 0.815**. If F1 drops below ~0.88, the data CSV regressed and the visual fix isn't worth keeping.

## Action items

### High-leverage (do first)

- [ ] **Phase-4 gating assertion** — refuse to mark a chart done while `run_meta.json` contains `"NOT extracted"`, `"known_undercount"`, or `declared_layer_count != rendered_series_count`. Implement as `scoring/phase4_check.py`. Closes 5 of 8 charts immediately by forcing them back through Phase 3.
- [ ] **Trend/fit-line extraction pass** — after marker HSV subtraction, run a thin-line detector (skeleton + RANSAC) on residual stroke pixels and emit Line Graph rows; replot driver renders any `layer_idx >= 1` row as a line. Closes el-60-b, el-75, el-94, el-100 (four charts in one fix).
- [ ] **Sync `run_meta.json` counts with the final post-Phase-3 CSV** so audit logs can't drift apart from shipped data. Caught el-100: meta says `24°C=12` but CSV has 17.

### Per-chart fixes

- [ ] **el-60-a** — widen `legend_exclusion` to rows 25-135 / cols 555-660. Refit x-axis on two well-separated tick centers (e.g. x=3 and x=21) to remove the ~0.4-day drift on the right half.
- [ ] **el-60-b** — extract the black trend line (two endpoints) and write it as a Line Graph layer in `data.csv`. Suppress auto-generated legend when source has no legend region. Use sub-pixel intensity-weighted centroids (current 27°C at 26.98 should round to 27.0).
- [ ] **el-62** — snap bar x-centroids to categorical 24/27/30 ticks when offset is < half group width. Mirror lower error caps (`y_lo = mean - (y_hi - mean)`) with a `mirrored_lower_cap` provenance flag. Drive legend text from `ground_truth.csv` series column ("Mean duration of GC1") instead of bare "GC1". Loosen `cap_min_run` from 3 to 2 for short caps like GC3 at 27°C.
- [ ] **el-75** — extract the red trend line as a Line Graph layer. Add a sanity check that compares declared layer count vs replotted series count.
- [ ] **el-80** — add a vertical-whisker-cap detector (short horizontal dark runs above/below bar tops with a connecting stem) and emit `yerr` in `data.csv`. Snap bar x to categorical ticks. Rasterize stippled GC2 fill correctly in the replot. Use long-form series names in the legend.
- [ ] **el-88** — drop the y=0 clipping step in the replot routine so anchor points like the 30°C tail diamond at (~40, 0) render. Refit y calibration to remove the ~1.5 % offset on 24°C disks.
- [ ] **el-94** — extract the three fit curves (dashed/solid/dotted gray). Loosen blue erode kernel from 4 to 2-3 and raise `aspect_ratio_max` so dots on the dashed line don't classify as dash fragments. Resolve overlap-zone series cross-attribution at x≈33-38.
- [ ] **el-100** — extract the three IF curves (blue dashed / green solid / red dotted). Drop stray-point at (0.6452, 0.248) — phantom green from misclassified tick or legend pixel. Widen axis exclusion masks and use Unicode degree sign in legend labels.

### Methodology-level

- [ ] **Phase 4 should not terminate while metadata acknowledges a gap.** Today, `"NOT extracted"` strings in `run_meta.json` are a *report*; they should be a *block*. Wire that into `scoring/phase4_check.py` and run it as the last step of every extractor's pipeline.
- [ ] **Replot driver should consume `ground_truth.csv` schema verbatim** (long series names, Unicode degree signs) instead of abbreviating in code, so future corpora pick up the right legends automatically.

### Reference

- Full wiki page: [Phase-4 Audit 2026-06-18](wiki/figure-recovery-suite.wiki/Phase-4-Audit-2026-06-18.md)
- Raw audit JSON: `docs/audits/phase4-audit-2026-06-18.json`
- Original methodology: [Methodology Five-Phase Workflow](wiki/figure-recovery-suite.wiki/Methodology-Five-Phase-Workflow.md)
- Extractor: [Extractor graph-data-extraction](wiki/figure-recovery-suite.wiki/Extractor-graph-data-extraction.md)
