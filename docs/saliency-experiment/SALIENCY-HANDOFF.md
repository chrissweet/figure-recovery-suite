# Handoff: AI Saliency investigation (figure-recovery-suite)

Purpose: let another person or agent pick up the "AI saliency" work — understand
what was done, what holds, where every artifact lives, and what to do next.
Project: `figure-recovery-suite` (~/Documents/projects/CRS_research/figure-recovery-suite).

## TL;DR

An agent's **transcript is a saliency map over the task**: mining where the model
concentrated effort (zoom crops, retries, self-corrections) yields a GT-free map of
**difficulty**. Established on chart-extraction transcripts and demonstrated on a
natural photo. Core results:

- **Attention is a region-level, not point-level, error signal** — attention→miss
  AUC ≈ 0.54 (near chance). It localizes the hard *region*, but cannot pick which
  individual point fails. No per-point uncertainty/compute allocation.
- **Region-targeted recompute fixes perception difficulty** — recomputing el-94's
  high-attention fusion band at 6× recovered **8/8** misses (recall 0.893 → 1.000,
  0 hallucinations), GT-free action.
- **Difficulty is 3-class and self-labeling in the transcript** — Perception
  ("PITFALL/iteration" → fixable), Structural ("unrecoverable/hidden" → not fixable),
  Semantic ("convention/interpolated" → a choice).
- **Validated**: same recompute recovers **100%** of perception misses (el-94) vs
  **~37%** of structural misses (life-exp). Structural difficulty = "the miss that
  survives recompute."

Honest scope: **behavioral** saliency (where the model chose to look), not
gradient/encoder-internal. Mostly single-chart, single-pass, small n. A research
program, not a finished result.

## What was done (logical order)

1. **Attention maps from zoom crops.** Free-rein extraction agents save magnified
   crops at the regions they inspect. Multi-scale template matching relocates each
   crop onto the chart → numbered box map (calibrate/survey/zoom) + attention
   heatmap. On el-94 the heat concentrates on the day ~28–40 marker/curve fusion band
   → visual proof "zoom is surgical local-ambiguity resolution."
2. **Natural-image demo ("find the turkeys").** Behavioral saliency from search
   crops on a photo; the **A − D** diff (attention minus detection) cancels the
   targets and leaves the *process*: attention spent on decoys (a log, a moss patch —
   ~92% of the residual mass) and cold, never-attended regions.
3. **Attention → error.** Point-level AUC of attention predicting misses: el-94 0.53,
   life-exp 0.57, pooled 0.54. Region-level yes, point-level no.
4. **Region-targeted recompute.** el-94 fusion band at 6× → 8/8 misses recovered,
   0.893 → 1.000. The misses were a *resolution artifact* (fused markers separate at
   higher res), and the attention map only had to say *where* to spend the pass.
5. **Difficulty taxonomy + validation.** Mined the transcripts for difficulty markers,
   categorized (Perception/Structural/Semantic). Validated recoverability: perception
   100% vs structural ~37% recompute recovery (floor = genuine occlusion, "no pixels
   to recover").

## Where everything lives

### Wiki (durable knowledge) — category "Saliency & Difficulty"
`wiki/figure-recovery-suite.wiki/` (separate git repo, pushed):
- `Concept-Transcript-Saliency.md` — **the hub**: the big idea, generalization to
  code/reading, the dev loop as effort-saliency iteration, research direction, threats.
- `Analysis-Attention-Map-Visualization-2026-08-12.md` — the vision method (crops → heatmap).
- `Analysis-Attention-Predicts-Error-2026-08-13.md` — AUC + recompute + validation.
- `Analysis-Difficulty-Taxonomy-From-Transcripts-2026-08-13.md` — the 3-class taxonomy.
- Embedded figures in `assets/attention-map-2026-08-12/` and `assets/saliency-2026-08-13/`.

### docs (working artifacts) — `docs/saliency-experiment/`
- `FINDINGS.md` — the AUC + recompute results with methods.
- `difficulty-taxonomy.md` — the full taxonomy table + effort ranking.
- `trajectory.md` — the turkey experiment transcript.
- Figures: `saliency_heatmap.png`, `attention_boxes.png`, `attention_minus_detection.png`
  (A−D diff), `diff_overlay.png`, `attention_error_ROC.png`, `el94_attention_vs_miss.png`,
  `el94_fusion_zoom.png`, `el94_recompute_overlay.png`, `lifeexp_occlusion.png`, `crops/`.

### Code / reproducibility
- **Saved & reusable**: `wiki/.../assets/attention-map-2026-08-12/attention_map.py`
  (locate crops → box map + heatmap; CLI: `image work_dir out_dir tag`).
- **Recompute detectors** (subagent-written): `OUT/saliency/detect_scripts/detect.py`
  (el-94 fusion markers), `detect_bubbles.py` (life-exp per-hue splitting).
- **Not yet saved as standalone scripts** (run inline; logic documented in FINDINGS.md):
  the AUC computation, the A−D diff builder, the attention→miss point sampling, the
  occlusion count. Re-deriving them from FINDINGS.md is straightforward; packaging
  them into `scoring/`-style scripts is a good first cleanup task.
- Source transcripts mined: the 5 subagent JSONL files under the session's
  `subagents/` dir, and the free-rein `trajectory.md` files in `OUT/freerein/*/`.

## Honest caveats (carry these forward)

- **Behavioral, not internal.** No encoder gradients; this is where the model *chose*
  to look, weighted by confidence. Frame as black-box/task-relevant, not as true saliency.
- **AUC ~0.54** means the point-level signal is weak; only region-level uses are supported.
- **Dense-bubble matching is unreliable** (life-exp recompute total even dropped
  132→124 while recovering 20 misses) — treat life-exp's 37% as approximate; the
  robust result is the 100% vs ~37% *contrast*.
- **Effort magnitude = transcript bytes** is a coarse proxy (conflates struggle with
  verbosity / tool output).
- **GT crept into scoring, not action.** The recompute *action* is GT-free; proving it
  worked used GT. A GT-free success metric (consensus tightening) is an open item.

## Next steps (from the wiki's open follow-ups)

1. **GT-free validation loop**: replace "recovered vs GT" with consensus tightening
   across N independent passes — removes GT entirely.
2. **Corpus-wide replication**: AUC + recompute are n=2 charts; run across the corpus.
3. **Toward a paper** (see `Concept-Transcript-Saliency` → research direction):
   align AI effort-saliency with **human** effort (free proxies: git churn /
   review-comment density for code; existing reading eye-tracking corpora for text),
   plus a causal occlusion test (perturb the salient region → answer changes).
4. **Finer effort signal**: revisit/backtrack counts instead of crop coverage, to test
   whether point-level AUC rises above 0.54.
5. **Cleanup**: package the inline analysis scripts into `scoring/` for reproducibility.

## Related deliverable (separate)

`docs/llm-wiki-deck-handoff/` holds the talk figures (per-type panels, the el-94
3-panel composite) and its own `VISION-HANDOFF.md`. That is the *presentation* handoff;
this file is the *investigation* handoff.
