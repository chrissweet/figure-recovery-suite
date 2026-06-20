# Feedback-Loop Extractor — Design Document

A new extractor for the figure-recovery-suite, built from the ground up with the **extract → replot → compare → iterate** loop as a first-class architectural primitive rather than a Phase-4 postscript. Lives on branch `feedback-loop-extractor`.

## Why a new extractor

The existing `graph-data-extraction` skill (`.claude/skills/graph-data-extraction/`) treats the replot loop as Phase 4 of a sequential workflow. Phase 4's verifier (`scoring/verify_artifacts.py`) was evaluated against its stated purpose in [Analysis-Replot-Loop-Efficacy-2026-06-20](../../wiki/figure-recovery-suite.wiki/Analysis-Replot-Loop-Efficacy-2026-06-20.md):

- Across 5 charts with 72+ known marker/line-level extraction errors, the verifier marker/line predicate caught **0**.
- The 88-92 % corpus-wide PASS rate measures the precision of what was extracted, not the recall of what was missed.
- Calibration drift IS caught (structural predicates), but the failure modes that dominate F1 are invisible to the current loop.

The diagnostic surface that DID drive wins (el-94 audit row 7; el-88 phantom rows; OWID self-reported caveats) was either human eyes on the overlay or separate gates (legend-hit). The Phase-4 predicates were not the catch in any of these cases.

This extractor inverts that. The loop is not a check at the end — it is **how extraction proceeds**. Every claim the extractor makes must survive the loop before it lands in `data.csv`, and the loop is the mechanism by which the extractor discovers data it would otherwise have missed.

## Design principles

1. **The loop is the algorithm, not a check.** Extraction is iterative: propose a set of claims, render them against the source, look for delta (regions of source with no claim; claims with no source support); revise; repeat until the delta stops shrinking.

2. **No GT in the loop.** Every signal the loop uses must come from the source image. The two new predicates (below) are GT-free by design. This matches [Decision-Test-Harness-Principles-2026-06-20](../../wiki/figure-recovery-suite.wiki/Decision-Test-Harness-Principles-2026-06-20.md) Principle 3: GT must never feed back into extraction.

3. **Negative space is a first-class signal.** The current loop iterates claims; this loop iterates BOTH claims and unclaimed regions. A glyph the source has but the claim set does not is the highest-value signal in the system — it directly drives recall.

4. **Claim provenance is explicit.** Every entry in `data.csv` carries a trace of which loop iteration produced it, what predicate(s) admitted it, and what the residual delta was. Diagnostic by construction; nothing is dropped on the floor.

## The two new predicates (loop signals, not just post-hoc checks)

These are the open follow-ups named in [Analysis-Replot-Loop-Efficacy-2026-06-20](../../wiki/figure-recovery-suite.wiki/Analysis-Replot-Loop-Efficacy-2026-06-20.md). In the new extractor, they run on every iteration as part of the loop, not just at the end.

### Predicate A — Negative-space coverage check

**Goal**: find markers / line segments / bar tops in the source image that the current claim set does not cover. Closes the "missed data" gap (synthetic 04 trace endpoints, OWID life-exp-vs-gdp 44 missing markers).

**Mechanism**: for each series in `chart_metadata.json`:
1. Build a color mask over `image.png` using the legend swatch RGB ± tolerance.
2. Mask out regions that are explained by current claims (markers from `data.csv`, traced-line columns from line-graph rows, bar fills from bar-top rows).
3. Run connected-component detection on the remaining mask.
4. Each residual component is a candidate missing claim. Emit as an `unclaimed_artifact` of the appropriate type with a confidence proportional to component area / shape.

**Output**: `negative_space_report.json` — per-series list of unclaimed components with pixel positions, sizes, and a triage label (`likely-marker`, `likely-line-fragment`, `likely-noise`).

**Loop integration**: every iteration, the negative-space report's `likely-marker` entries are pushed back to the extraction proposer. If iteration N+1 doesn't reduce the count of `likely-marker` unclaimed, the loop converges.

### Predicate B — Glyph-vs-line discriminator

**Goal**: filter false-positive markers that are actually fragments of dashed/dotted lines or legend swatches. Closes the "over-counting" gap (el-100 18 FP, el-94 4 FP).

**Mechanism**: for each `marker_centroid` claim:
1. Build a small (e.g. 17×17 px) crop centered on the claimed pixel.
2. Compute connected-component shape stats on the dark/colored region within the crop: area, aspect ratio (max(w, h) / min(w, h)), fill density (area / bbox_area), neighbour-stroke check (does the same-color mask extend along the column or row beyond the crop boundary?).
3. Score "marker-ness" vs "line-fragment-ness":
   - Real marker: aspect ratio ~ 1, fill density 0.4-1.0 (filled / outlined), no neighbour stroke extending along an axis.
   - Line fragment: aspect ratio elongated along one axis, OR fill density low with the stroke extending across the crop boundary.
   - Legend swatch: small, isolated, sits inside the `legend_exclusion_used_for_frame` box.

**Output**: `glyph_discriminator.json` — per-claim score + verdict.

**Loop integration**: claims that fail the discriminator are dropped from `data.csv` before scoring. The discriminator's verdict is recorded in the claim's provenance so a human can audit.

## Loop architecture

Pseudocode for the main extraction loop:

```python
def extract(image_path, chart_metadata):
    claims = bootstrap_initial_claims(image_path, chart_metadata)
    for iteration in range(MAX_ITER):
        # Predicate A — find what we missed
        neg_space = negative_space_check(image_path, chart_metadata, claims)
        # Predicate B — filter what we got wrong
        claims = [c for c in claims if glyph_discriminator(image_path, c)]
        # Combine: propose new claims from negative-space candidates
        proposed = propose_from_negative_space(neg_space, chart_metadata)
        # Bookkeep
        delta = len(proposed) + count_dropped(claims)
        claims = claims + proposed
        if delta == 0:
            break  # converged
    return claims, diagnostic_record
```

Per-iteration artifacts saved to `iterations/<n>/`:
- `claims.csv` — the claim set at this iteration
- `negative_space_report.json` — what was missed (per-series unclaimed components)
- `glyph_discriminator.json` — what was filtered (per-claim verdict)
- `iteration_overlay.png` — visual diff: green = passed both predicates, red = dropped by discriminator, yellow = unclaimed region flagged by negative-space

The final `data.csv` + `calibration.json` + `chart_metadata.json` come from the last iteration; the iterations directory IS the diagnostic record.

## Phase plan

Phase order is bottom-up so each phase has a measurable success criterion before the next is built.

### Phase 1 — Negative-space coverage predicate as standalone

- Pure code, no skill prompts yet
- Input: existing v3 extractor output for any aedes / synthetic / owid chart, plus the source image
- Output: per-series `negative_space_report.json` listing unclaimed components
- Success criterion: when pointed at the 5 charts in the analysis (el-100, el-88, el-94, synthetic 04, owid life-exp-vs-gdp), it flags at least the known missed components (44 on life-exp-vs-gdp, 5 trace samples on synthetic 04). Validates the approach catches what the current verifier misses

### Phase 2 — Glyph-vs-line discriminator as standalone

- Pure code, no skill prompts yet
- Input: existing v3 extractor output, source image
- Output: per-claim discriminator verdict
- Success criterion: flags at least the 18 FP on el-100, 4 FP on el-94, 1 FP on el-88 (or articulates honestly why each survives the discriminator)

### Phase 3 — Loop driver

- Wires Phases 1 + 2 into the iteration loop
- Input: source image + chart metadata (axis titles, legend swatches, units) read from the source by an initial cropping pass
- Output: iterated `claims.csv`, `negative_space_report.json`, `glyph_discriminator.json`, `iteration_overlay.png` per iteration, plus final `data.csv` + `calibration.json` + `chart_metadata.json`
- Success criterion: convergence (delta = 0) within MAX_ITER on every chart in synthetic-r4-1

### Phase 4 — Test against the three corpora

- Run end-to-end on aedes / synthetic-r4-1 / owid-r6-1
- Compare combined F1 against the existing `graph-data-extraction` skill on the same scorer (post the percent-of-axis-range refactor, commit `c8a1d86`)
- Success criterion: on owid-r6-1, lift combined F1 by addressing the marker-recall and marker-precision gaps the v3 skill leaves open. Aedes and synthetic should also lift on the FP-marker charts (el-100, el-94)

### Phase 5 — Skill packaging

- Wrap the loop driver as a `.claude/skills/feedback-loop-extractor/` skill so subagents can invoke it
- Document the loop's outputs in SKILL.md alongside `data.csv` / `calibration.json` / `chart_metadata.json`
- Compatibility: the final `data.csv` schema matches SKILL.md Phase 5 conventions; the iterations directory is optional diagnostic output

## What this design explicitly does NOT change

- **The data.csv / calibration.json / chart_metadata.json schemas**: unchanged from v4 conventions. The new extractor produces the same final deliverables; the diagnostic outputs are extras.
- **The scorer**: unchanged. Same `scoring/score_data.py` (post c8a1d86 refactor) grades both extractors.
- **The corpora**: unchanged. The new extractor will be evaluated on the existing aedes / synthetic-r4-1 / owid-r6-1 corpora plus any future additions.
- **The verifier**: unchanged for the v3 extractor; the new extractor's iteration overlays are an internal artifact and don't replace `scoring/verify_artifacts.py`.

## Open design questions

These are real ambiguities to resolve before Phase 3:

1. **Color mask tolerance for negative-space** — too tight misses anti-aliased pixels at marker edges; too loose pulls in everything. The current `verify_artifacts.py` color-mask code uses ±15 BGR; that's a starting point. May need per-chart adaptation based on observed marker glyph variance.

2. **What counts as "claimed"** — a marker_centroid at (col, row) "claims" some local neighbourhood; a line_sample at (col, row) "claims" the column at row ± stroke-width. The mask-subtraction step needs a sane local-claim model so we don't double-count or miss real un-claimed regions.

3. **Convergence vs cycling** — what if iteration N adds a claim, iteration N+1's discriminator drops it, and the cycle repeats? Need a "blacklist" of dropped claims so we don't propose them again.

4. **What about line plots without distinct markers?** — negative-space against a continuous trace means measuring whether each source-mask column has at least one line_sample claim within stroke-width-rows. Slightly different mechanism than for markers; specify in Phase 1.

5. **Chart-metadata bootstrapping** — the loop needs `chart_metadata.json` to know what series exist and what their colors are. Where does this come from on iteration 0 if the extractor hasn't read the legend yet? Probably: a Phase-0 pre-pass that does legend detection + axis-title extraction (the existing v3 skill's Phase 1 mostly does this). Phase 0 is borrowed from v3; Phases 1+ are the new contribution.

## Open scope questions

1. Should the loop ALSO discover series that aren't in the bootstrap `chart_metadata.json`? E.g. a 7th line that the legend reading missed? Negative-space-by-color would naturally surface unclaimed colored regions; we could add an "unknown series" bucket. Defer to Phase 4 once basics work.

2. How does the loop handle stacked-bar / stacked-area charts where every pixel is "claimed" by SOME series? Negative-space-coverage becomes a per-series count check rather than a per-pixel coverage check. Worth a chart-type branch in Predicate A.

## References

- [Analysis-Replot-Loop-Efficacy-2026-06-20](../../wiki/figure-recovery-suite.wiki/Analysis-Replot-Loop-Efficacy-2026-06-20.md) — the gap analysis this design closes
- [Decision-Test-Harness-Principles-2026-06-20](../../wiki/figure-recovery-suite.wiki/Decision-Test-Harness-Principles-2026-06-20.md) — the rules every test of this extractor must follow
- [Decision-Pixel-Frame-Verification-2026-06-18](../../wiki/figure-recovery-suite.wiki/Decision-Pixel-Frame-Verification-2026-06-18.md) — the matched-frame methodology this extractor builds on
- [Methodology-Five-Phase-Workflow](../../wiki/figure-recovery-suite.wiki/Methodology-Five-Phase-Workflow.md) — the v3 skill's structure; the new extractor's Phase 0 is its Phase 1; Phases 1-3 here replace the v3 skill's Phase 3-4
- [Extractor-graph-data-extraction](../../wiki/figure-recovery-suite.wiki/Extractor-graph-data-extraction.md) — the existing v3 extractor this one is a successor to (NOT a replacement until measured F1 supports it)
