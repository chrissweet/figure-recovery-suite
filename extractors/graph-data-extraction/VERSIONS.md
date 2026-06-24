# Version ledger: v1 -> v9 (recall investigation, 2026-06)

What this records: a run of experiments asking one question -- **can anything beat
the MLLM forward pass on recall, given we usually have no ground truth in the
wild?** Each version is a methodology; the answer that emerged is "not a post-hoc
recovery step, but yes if you ARM the forward pass with the traps and the tools."

All scores are **combined F1 vs ground truth** from `scoring/score_data.py`.
v3-v9 are scored over the **26-chart common set** (the charts that carry
`chart_metadata.json`); v1/v2 only ever ran on the 8 aedes charts.

## The ledger

| Ver | Definition | aedes | synthetic | owid | Verdict |
|----|------------|-------|-----------|------|---------|
| **v1** | Forward pass, **scatter only** (Jun) | 0.611 | — | — | no curves/errbars |
| **v2** | + reconstruction (replot + audit fixes) (Jun) | 0.848 | — | — | adding layers was the gain |
| **v3** | + post-extract comparison / verifier (Jun) | 0.864 | 0.904 | 0.487 | historical best; baseline |
| **v4** | **Forward pass only** (Phases 1-3, no Phase 4), fresh, reused calibration | 0.858 | 0.819 | 0.775 | ≈ v3; the clean baseline |
| **V5** | v4 + cv_oracle reconcile-merge (recall recovery) | 0.749 | 0.811 | 0.775 | HURTS (imports FP) |
| **V5g** | V5, gated to declared-but-dropped layers only | 0.858 | 0.819 | 0.775 | = v4 (neutral) |
| **v6** | v4 + calibrate-first canvas + **peel-loop** (subtractive close-the-loop) | 0.856 | 0.798 | 0.775 | first to recover REAL recall, but FP offset it |
| **v7** | **Calibrate-first** (fresh calib -> verify -> extract on canvas) | pilot | pilot | pilot | ≈ or below v4 (calib variance, edge clip) |
| **v8** | **Template-matching** markers (WPD primary tool, auto-seeded) | 0.594 | 0.816 | — | great on separable markers, fails on grayscale+dashes |
| **v9** | **Armed forward pass** (MLLM + pitfalls field guide + cv_oracle tools) | pilot | pilot | pilot | WINS on pitfall charts (el-94 0.818->0.856) |

## Per version

- **v1** (`results/`): scatter centroids only; curves and error bars score 0. Combined 0.611 because whole layers are absent.
- **v2** (`results-v2/`): added curve and error-bar extraction + a matplotlib re-plot with audit-driven manual fixes. The jump v1->v2 (0.611->0.848) is almost entirely **adding the missing layers**, not the re-plot correcting values.
- **v3** (`results-v3/`): added the per-element verifier and Phase-4 gating, run across all three corpora. Best historical methodology. (owid over all 10 charts was 0.382; 0.487 here is the 8-chart common set.)
- **v4** (`results-v4/`): the forward pass **with Phase 4 removed**, re-run on today's model, calibration + series identity reused from v3. The clean single-pass baseline. ≈ v3 on aedes, doubles owid recall (model+extraction improvement, but confounds model-version with Phase-4-removal).
- **V5 / V5g** (`results-v5/`, `results-v5g/`): cv_oracle detects markers independently and merges what the forward pass "missed". Dumb merge imports false positives (aedes precision 0.92->0.66). Gating to fully-dropped layers makes it neutral (= v4). The merge does not earn its place -- same verdict the v2->v3 re-plot loop earned (+0.016).
- **v6** (`results-v6/`): `prepare_canvas` (white out non-data) + `peel` (erase what you found, detect the residual = the subtractive close-the-loop, no matplotlib render). **First method to recover real recall** (aedes 0.800->0.852, the el-94 fused squares), but residual-detector false positives keep net F1 ≈ v4. Curve-peel must EXTEND only (interleaving corrupts the scorer's interpolation).
- **v7** (`results-v7/`, pilot): compute calibration fresh, verify it, extract on the canvas. Lands ≈ or below v4 -- fresh-calibration variance + the canvas clipping axis-adjacent points cost more than the FP removal saves. Key realization from the user: masking and calibrating are the *same detection*, so calibration is not a precious reused artifact, just a cheap deterministic scan + reading the tick numbers.
- **v8** (`results-v8/`): seeded template matching as the PRIMARY marker finder. Isolated win: el-94 27C fused squares **25/25** (blob 9, MLLM 15). But the corpus arm ties v4 on color-separable markers and fails on grayscale, because black markers and black dotted/dashed curve-dots are the same intensity -> curve-dots match as markers. Best tool for separable markers; not universal.
- **v9** (`results-v9/`, pilot): the synthesis. The forward pass armed with `references/pitfalls-and-recipes.md` and the `cv_oracle.cli` tools. On the pitfall-heavy chart it WINS: el-94 0.818->0.856 (template recovered 27C 15->25; the MLLM *reasoned* about dotted-curve dots instead of extracting them). Neutral on clean charts; slightly worse on generic line tracing (more steps = more variance). Higher cost/longer runs.

## What the whole thing concluded

1. **The forward pass is the strong part; recall is its weakness, but no post-hoc recovery step beats it when it is already decent.** Re-plot->compare (v2->v3 +0.016), reconcile-merge (V5 negative), gated merge (V5g neutral), peel-merge (v6 ≈ flat) all confirm this. They import false positives faster than they recover misses.

2. **The subtractive close-the-loop works where the additive one didn't.** Peel ("source - extraction ≈ empty") recovers real misses with no matplotlib render -- the v3 re-plot used matplotlib, whose axis re-scaling made image-vs-replot diffs meaningless. The limiter is residual-detector precision, not the idea.

3. **The persistent hard case is grayscale markers sharing intensity with dotted/dashed curves.** No deterministic method (blob, template, intensity-quantization) separates a dotted-curve dot from a marker -- it is a shape/context problem. Only the MLLM's semantic read handles it.

4. **The payoff of all the CV work was not a better extractor -- it was the field guide and tools.** Arming the MLLM (v9) with the catalogued pitfalls and a deterministic tool per trap beats the plain forward pass on the charts that matter, by playing to the MLLM's judgment instead of around it.

## What was built (cv_oracle/)

A deterministic CV toolkit, import-only, GT-free, emitting the standard CSV schema:
`calibration` (affine + log + categorical snap, convention auto-detect), `separation`
(color mask + grid removal), `detect/{blobs, curves, errbars, template}`,
`reconcile`, `gate` (GT-free corpus recall gate, pixel-confirmed -- the most useful
*reporting* artifact), `recover` (reconcile-merge), `peel` (subtractive recovery),
`prepare_canvas` (normalize), `cli` (the tool surface the skill calls). Plus the
skill field guide `references/pitfalls-and-recipes.md`. 39 tests.

## Honest caveats

- **v4-vs-v3 confounds model-version with Phase-4-removal** (v4 = today, v3 = June). A clean Phase-4 ablation needs v3-with-Phase-4 re-run on today's model.
- **Scorer quirks**: curve FP is always 0 (extra coverage unpenalized); empty GT layers neither credit nor penalize (so some "harmless" recoveries are scorer artifacts); `layer_type` routing is case-sensitive (a `"line"` vs `"Line Graph"` typo zeroed a whole chart in v7).
- **v7 / v9 are pilots** (3 charts), not full-corpus runs. Their pattern is clear but the corpus numbers are not in.

## Detail docs

- `results-v4/EXPERIMENT-v4-v5-2026-06-24.md` -- v4/V5/V5g/v6/v8 full numbers + v4 prompt anatomy.
- `wiki/.../Analysis-V4-V5-Recall-Step-2026-06-24.md` -- the analysis page.
- `.claude/skills/graph-data-extraction/references/pitfalls-and-recipes.md` -- the field guide.
