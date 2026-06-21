# graph-data-extraction (v3) — the canonical extractor

This directory is the **canonical source** for the `graph-data-extraction` Claude Code skill. It is reachable from two paths:

- `.claude/skills/graph-data-extraction/` — where Claude Code looks for the skill at session start. **This is the authoritative location.** Edits go here.
- `extractors/graph-data-extraction/code/` — a symlink to this directory, added to fit the project's `extractors/<name>/code/` convention so the working extractor sits next to its results (`extractors/graph-data-extraction/results/`, `results-v2/`, `results-v3/`).

Both paths show the same files. Editing through either updates the same content; there is no copy and no drift.

## Layout

```
graph-data-extraction/
  SKILL.md                  Workflow document. Read at session start by a Claude Code subagent.
                            Five-phase methodology (image -> calibrate -> extract -> replot -> deliver).
                            Phase 5 "data.csv schema conventions" (added 2026-06-19 after synthetic-r4-1
                            r5 run) is mandatory reading before emitting any data.csv.
  METHODOLOGY.md            High-level narrative of the five-phase workflow.
  references/
    calibration.md          §2 frame and tick detection, linear and log axis fitting, sanity checks.
    extraction_recipes.md   Per-chart-type recipes: §3 line trace (with `trace_with_continuity` for
                            crossings, added 2026-06-19), §3a marker-on-line, §3b fit-curve
                            subtraction, §3b filled-square-fused-with-curve (added 2026-06-19,
                            audit-row-7 closure), §4 bar charts (grouped + stacked conventions),
                            §4a stippled-fill bars, §4b error caps, §5 histograms, §6 hazards.
  scripts/
    write_calibration.py    Emits calibration.json (schema v1.0). Log10 axis support added 2026-06-19.
    calibrate.py            Interactive CLI for frame and tick detection.
    extract_markers.py      HSV CC marker extraction + per-marker classification.
    trace_curves.py         `trace_per_column_median` and `trace_with_continuity` (unique-pair +
                            clean-slope window + per-curve seed-col guard for crossings).
    subtract_curves.py      Per-column thin-run subtraction with paired-edge preservation, for
                            §3b fit-curve removal before marker extraction.
    check_artifacts.py      Post-extraction data-shape sanity (clamped runs, spikes).
```

## Performance baseline

F1 = 0.90 on the [Corpus aedes-aegypti-2014](../../../wiki/figure-recovery-suite.wiki/Corpus-aedes-aegypti-2014.md) initial 8-chart corpus; full per-chart numbers in the [r4 evaluation report](../../../docs/aedes-2014_eval_r4.pdf) and across all three corpora in the [r5 report](../../../docs/eval_r5.pdf). This is the **baseline the project tries to improve against** ([Analysis-Feedback-Loop-Off-Course-2026-06-21](../../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md)).

## Upstream

This skill is mirrored from [`chrissweet/AI_skills/skills/graph-data-extraction/`](https://github.com/chrissweet/AI_skills/tree/main/skills/graph-data-extraction). To pull upstream updates:

```bash
cp -R ~/Documents/projects/CRS_research/AI_skills/skills/graph-data-extraction/* \
      .claude/skills/graph-data-extraction/
```

## How extraction runs (a subagent does this, not a one-shot script)

A Claude Code subagent reads SKILL.md, picks the right recipe section per chart, invokes the helper scripts above, and emits the per-chart `calibration.json`, `chart_metadata.json`, `data.csv`, `replot.png` to `extractors/graph-data-extraction/results-v3/<corpus>/<chart>/`. Scoring against ground truth happens out-of-band via `scoring/score_data.py` at the repo root.

## See also

- `extractors/graph-data-extraction/results/`, `results-v2/`, `results-v3/` — three generations of extraction outputs on the aedes corpus, plus results-v3 covers synthetic-r4-1 and owid-r6-1
- `extractors/legacy_v1/code/` — the original aedes-specific extraction scripts that produced `results/`; preserved for reproducibility
- `extractors/feedback-loop-extractor/code/` (on the `feedback-loop-extractor` branch) — experimental branch that explored a re-render + diff + density feedback loop on top of this extractor. Went off-course; see the wiki analysis page
- `.claude/skills/graph-data-extraction/SKILL.md` — start here when invoking the skill
