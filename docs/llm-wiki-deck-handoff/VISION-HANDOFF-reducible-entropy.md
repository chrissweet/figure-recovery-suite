# Handoff → vision agent: build ONE slide

## Slide title (important — use this)

**"Beyond analytics: behavioural saliency and epistemic / aleatoric entropy?"**

(Raw phrasing from the author: *"Beyond analytics/behavioural saliency and
epistemic/aleatoric entropy?"* — the "?" is intended; if you prefer, an alternate
split is *"Beyond analytics & behavioural saliency: reducible vs irreducible
entropy?"*. Confirm with the author before finalizing.)

## The one message of the slide

A model's transcript is a **behavioural saliency** map, and the method built on it
does not look for a *target* — it looks for **reducible entropy** (uncertainty it
can resolve by spending effort). Because the objective is entropy reduction, not
target matching, the loop is **GT-free by construction**. It acts on **epistemic**
(reducible) uncertainty and correctly stalls on **aleatoric** (irreducible).

## Hero graphic (include this)

`docs/llm-wiki-deck-handoff/el94_entropy_loop_3panel.png` (absolute:
`/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/docs/llm-wiki-deck-handoff/el94_entropy_loop_3panel.png`)

Three panels, left→right: **1 Locate the high-entropy region** (attention/ambiguity
heatmap from the transcript; 8 misses in the hot band) → **2 Zoom 6× + re-extract**
(the fused markers separate; 32 detected) → **3 Result** (all 8 recovered, 0
hallucinations). Caption the arc: **89% → 100%, +8 points.**

## The core table (put on the slide)

| entropy | = uncertainty type | example | zoom + re-extract |
|---|---|---|---|
| **reducible** | epistemic | el-94 fused grayscale markers | **resolves → 8/8 recovered** |
| **irreducible** | aleatoric | dots fully under an opaque bubble | **can't → ~37% floor** |

The method acts on the top row and correctly stops on the bottom row — that
contrast (100% vs ~37% recovery) is the evidence it distinguishes the two.

## Discussion (speaker notes / bullets)

- **Two kinds of "where to look."** Classic analytics / gradient saliency finds
  *where the signal or target is* — it needs to know what to look for. **Behavioural
  saliency** reads the model's own effort trace from the transcript: *where it was
  uncertain and worked hardest.* Different question, no target required.
- **The objective is reducing reducible entropy, not matching an answer.** So GT
  never enters the decision of where to act — the loop is GT-free by construction.
  (We *score* the result against ground truth to report 89%→100%; that is ordinary
  validation, not supervision — every unsupervised method is checked against labels.)
- **Epistemic vs aleatoric is the payoff distinction.** Zoom + re-extract resolves
  *epistemic* uncertainty (fused markers separate at higher resolution) but not
  *aleatoric* (an occluded dot has no pixels to recover). The method spends effort on
  the former and stalls on the latter — automatically.
- **Reducibility is confirmed GT-free, by attempting it.** The entropy map alone
  doesn't know in advance which is which; the loop *tries*, then checks the result
  without ground truth — a pixel-check (do the new markers land on real ink?) or
  cross-pass consensus tells you whether entropy actually dropped.
- **The full GT-free loop:** flag high entropy (transcript) → attempt reduction
  (zoom + re-extract) → confirm reduction GT-free (pixel-check / consensus) → keep if
  reduced, stop if not.

## Suggested layout

- Title bar: the title above.
- Left ~60%: the 3-panel hero graphic with the "89% → 100%, +8" caption.
- Right ~40%: the reducible/irreducible table on top, the 5 discussion bullets below
  (trim to 3 if space is tight: two-kinds-of-where-to-look; objective-is-entropy-
  reduction-so-GT-free; epistemic-resolves / aleatoric-stalls).

## Honest guardrails (do not overclaim on the slide)

- Say **behavioural** saliency (where the model chose to look / spent effort), NOT
  gradient/encoder-internal saliency.
- The 100% endpoint is a from-scratch recompute (all 8 within tolerance, 0
  hallucinations); the author recalled "99%" — use **100%** unless they specify a
  different denominator.
- Evidence is n = 2 charts (el-94 epistemic, life-exp aleatoric); frame as a
  demonstration, not a benchmarked law.

## Deeper context (for Q&A, optional)

Wiki category "Saliency & Difficulty": `Concept-Transcript-Saliency` (the thesis),
`Analysis-Attention-Predicts-Error-2026-08-13` (AUC + recompute + validation),
`Analysis-Difficulty-Taxonomy-From-Transcripts-2026-08-13` (perception/structural =
reducible/irreducible). Full method + artifacts:
`docs/saliency-experiment/SALIENCY-HANDOFF.md`.
