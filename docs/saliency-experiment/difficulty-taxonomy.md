# Difficulty taxonomy from transcript mining (2026-08-13)

Applying the "difficulty" lens to the free-rein extraction transcripts: mine where
the agents concentrated effort (iterations, self-corrections, abandonment) and
categorize. Source transcripts: the 4 free-rein subagents (el-94, life-exp,
annual-co2, grouped-bar) + the el-94 fusion-band recompute. Evidence is the agents'
own trajectory annotations, corroborated by raw-transcript effort magnitude.

## The distinguishing effort-signature

The transcript's own language separates three difficulty classes:

- **Perception difficulty** → "PITFALL / BUG / iteration / self-correction" → effort
  spent *and it converged*. **Fixable.**
- **Structural difficulty** → "unrecoverable / omitted / hidden / below threshold /
  NOT fabricated" → effort spent, *abandoned honestly*. **Not fixable with effort.**
- **Semantic difficulty** → "convention / interpolated / series identity" → a
  *decision*, not a struggle.

## Taxonomy (grounded in the transcripts)

| super-class | category | example (chart) | transcript evidence | effort-fixable? |
|---|---|---|---|---|
| Perception | Contaminant rejection | grouped-bar, el-94 | "PITFALL: legend swatches merged with Q1 bar -> bogus val 105"; "1 legend dot" | yes (re-mask) |
| Perception | Threshold-vs-fill | grouped-bar | "green fill 82.7 < dark<90 -> green caps vanished" | yes (re-threshold) |
| Perception | Colored-label confusion | life-exp | "labels are colored text matching continent color; cannot separate by color" -> erosion | yes (morphology) |
| Perception | Color separation | annual-co2 | "China's antialiased edge == UK steel-blue; pure nearest-colour cannot separate" -> 5 tracer iterations | yes, but costly |
| Perception | Overlap/fusion (resolution-limited) | el-94, life-exp | "circles touch dashed curve & merge"; "squares hardest centroid, sit ON solid curve" | yes (recompute: 8/8 at 6x) |
| Structural | Occlusion | el-94, life-exp | "day30 hidden behind a circle, omitted"; "dots fully OCCLUDED beneath big bubbles... structurally unrecoverable" | no (info absent) |
| Structural | Sub-threshold / faint | annual-co2, life-exp | "China pre-1940 <0.1B below saturation threshold, could not be separated" | no |
| Structural | Resolution floor | annual-co2 | "sub-year impossible, 2.3 px/year" | no |
| Semantic | Calibration edge-case | annual-co2 | "outer labels shifted inward to avoid clipping - self-correction, excluded from fit" | yes (one-time gotcha) |
| Semantic | Convention ambiguity | grouped-bar, life-exp | categorical x-offset; "only 25 countries labeled -> series='Country'" | choice |
| Semantic | Gap-filling decision | el-94 | "4 gap days PCHIP-interpolated"; "curve mid-gap MODEL-interpolated, not measured" | choice |

## Effort ranking (raw-transcript magnitude, bytes as work proxy)

el-94 **4.4 MB** > life-exp 3.0 MB > annual-co2 0.8 MB > grouped-bar 0.4 MB; the
el-94 fusion-band **recompute alone was 10.7 MB** — the single hardest sub-task in
the project. Effort concentrates on **overlap/fusion** (el-94) and **color
separation** (annual-co2's 5 iterations), i.e. the perception class.

## The meta-finding

**The transcript separates difficulty that effort can fix from difficulty that
effort cannot — GT-free, before any scoring.** Perception difficulties burn
iterations and *converge*; structural difficulties burn iterations and *terminate
in "unrecoverable."* The deployable consequence: route recompute/compute to the
"PITFALL/iteration" (perception) regions, not the "unrecoverable" (structural)
ones. This also predicts *when* attention-directed recompute works — it recovered
8/8 of el-94's resolution-limited fusion misses (perception), and it would not
recover life-exp's occluded-under-bubble misses (structural), which are lexically
distinguishable in the trace.

## Open validation

Test whether these transcript-derived categories predict measured per-region
outcome: perception regions should be recoverable (recompute lowers error),
structural regions should stay missed regardless of effort. That closes the loop
from difficulty-language to measured recoverability.

## Provenance & caveats

- Behavioral / self-reported difficulty (the agents' own trajectory annotations),
  corroborated by raw-transcript byte magnitude. Not model-internal.
- n = 4 charts + 1 recompute; single free-rein pass each.
- Effort-magnitude by transcript bytes is a coarse proxy (includes tool output,
  code, and — for the recompute — heavy template-matching logs).

## See also
- `FINDINGS.md` — attention->error AUC (~0.54, region-level not point-level) + the
  el-94 recompute (0.893 -> 1.000)
- `trajectory.md` — the turkey AI-saliency experiment (same method, natural image)
