# Experiment: forward-pass-only (v4) vs + cv_oracle recovery (V5)

Run 2026-06-24, current model (opus-4-8). 26 charts (the v4/v5 set; 2 owid charts excluded for missing chart_metadata). Calibration reused from v3 (MLLM Phase-2). Scored against ground truth with scoring/score_data.py.

## Versions

- **v3** = forward pass + reconstruction + post-extract comparison (June extraction; historical best).
- **v4** = forward pass ONLY (Phases 1-3, no Phase 4). Fresh extraction, today.
- **V5** = v4 + cv_oracle recall recovery (GT-free, points-only merge). The re-plot->compare replacement.

## Results (combined, vs ground truth)

| Corpus | Ver | P | R | F1 | TP | FN | FP |
|---|---|---|---|---|---|---|---|
| aedes-aegypti-2014 | v3 | 0.933 | 0.804 | 0.864 | 418 | 102 | 30 |
|  | v4 | 0.923 | 0.800 | 0.858 | 325 | 81 | 27 |
|  | V5 | 0.662 | 0.805 | 0.727 | 327 | 79 | 167 |
| synthetic-r4-1 | v3 | 1.000 | 0.825 | 0.904 | 439 | 93 | 0 |
|  | v4 | 0.974 | 0.707 | 0.819 | 376 | 156 | 10 |
|  | V5 | 0.952 | 0.707 | 0.811 | 376 | 156 | 19 |
| owid-r6-1 | v3 | 1.000 | 0.322 | 0.487 | 1923 | 4044 | 0 |
|  | v4 | 1.000 | 0.633 | 0.775 | 3778 | 2189 | 0 |
|  | V5 | 1.000 | 0.633 | 0.775 | 3778 | 2189 | 0 |

## Findings

1. **cv_oracle recall recovery (v4->V5) does not earn its place.** aedes F1 0.858->0.727 (+2 TP for +140 FP; precision 0.92->0.66, the grayscale point detector firing on noise). synthetic 0.819->0.811 (+0 TP, +9 FP). owid unchanged. The clean v4->V5 delta is negative, vs re-plot->compare's v2->v3 = +0.016 on aedes. Both post-hoc recall steps fail to beat the forward pass; merging cv detections imports false positives where the forward pass is already decent.

2. **Forward-pass-only (today) ~= or beats the June full pipeline.** v4 matches v3 on aedes (0.858 vs 0.864) and doubles owid recall (0.633 vs 0.322). CONFOUNDED: v4=today's model, v3=June; this mixes Phase-4-removal with model-version, so read as "today's forward pass alone ~= last June's full pipeline," not "Phase 4 is worthless."

3. **cv_oracle helps only when a whole layer was dropped.** On v3-owid (forward pass emitted 0 scatter) recovery lifted recall 0.236->0.322; on v4 (points already present) it only adds FP. Motivates a confidence-gated V5 that recovers missing LAYERS, not extra points.

## Caveats

- aedes V5 FP is specifically the achromatic/grayscale point detector; a weakness of the recovery heuristic, not proof no recall step can help.
- 05-stacked-bar and 07-dual-y-axes hit calibration-schema edge cases in recover (fell back to v4=V5).

## Update: smarter gated V5 (V5g), same day

V5g recovers ONLY layer buckets the GT-free gate flags as declared-but-dropped (pixel-confirmed); layers the forward pass already populated are left untouched. recover.py write was also fixed to preserve v4 columns (it had been dropping y_lo/y_hi error-bar columns).

| Corpus | v4 F1 (FP) | V5 dumb F1 (FP) | V5g gated F1 (FP) |
|---|---|---|---|
| aedes-aegypti-2014 | 0.858 (27) | 0.749 (167) | 0.858 (27) |
| synthetic-r4-1 | 0.819 (10) | 0.811 (19) | 0.819 (10) |
| owid-r6-1 | 0.775 (0) | 0.775 (0) | 0.775 (0) |

**Smarter V5g lands exactly at v4 on every corpus** (aedes FP 167->27). Gating removes the false-positive harm but yields NO improvement: the gate-flagged "missing point layers" are typing disagreements (metadata declares markers, GT types the series as lines, the forward pass emitted lines correctly), so recovered points land in empty GT scatter layers and neither score nor (on this scorer) penalize.

**Verdict across both variants: a post-extraction recall step does not beat the forward pass on this corpus.** Dumb recovery hurts (FP); gated recovery is neutral (=v4). This is the same verdict re-plot->compare earned. The recall step is not worth shipping; the leverage is in the forward pass (and the GT-free gate as a *reporting* signal, not an auto-merge).