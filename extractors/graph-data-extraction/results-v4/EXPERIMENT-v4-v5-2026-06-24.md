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
## Appendix: the v4 forward-pass agent (prompt anatomy)

v4 was produced by a workflow fanning out one general-purpose agent per chart.
Each agent received the prompt below; its structured return fed the scorer. The
prompt deliberately freezes everything upstream of Phase 3 (calibration, series
identity) and forbids everything downstream (Phase 4, ground truth), so the only
variable the agent controls is the Phase-3 extraction.

Orchestration:

    MANIFEST (26 charts)
         |
    Workflow -- 1 agent per chart (concurrency-capped) --> ... per chart ...
         |
         v
    general-purpose agent (prompt below)
      inputs: image + REUSED calibration + REUSED chart_metadata
      output: results-v4/<corpus>/<chart>/data.csv
         |  returns {chart, rows_written, layers, issues}
         v
    scoring/score_data.py  (vs ground truth -- only here, never in the agent)

Prompt anatomy (5 blocks + structured return):

  1. TASK FRAME
     "Run the FORWARD PASS ONLY (Phases 1-3, NO Phase 4) on ONE chart -> data.csv"
     -> scope: single chart, single pass

  2. INPUTS (4 paths)
     - Image (look at it):                corpora/.../image.png
     - REUSE calibration, don't re-derive: <v4_dir>/calibration.json
         (axis m/b + plot_frame_box; "read the formula field" - log/inverted exist)
     - Series + colors/types:             <v4_dir>/chart_metadata.json
         (series_legend: color + marker_shape | line_style)
     - WRITE OUTPUT TO:                    <v4_dir>/data.csv

  3. HARD RULES  (the experimental controls)
     (1) DO NOT read any ground_truth file    -> keeps it GT-free
     (2) DO NOT re-plot / compare / iterate    -> removes Phase 4
         (single pass; "partial/imperfect is expected and fine")
     (3) Reuse the calibration mapping; don't refit axes -> isolates Phase 4

  4. METHODOLOGY (how)
     - Skill pointer: SKILL.md, METHODOLOGY.md,
         scripts/{extract_markers, trace_curves, subtract_curves}.py
     - Per-series method:
         scatter markers -> connected-component centroids
         lines           -> per-column color trace
         bars            -> column tops (one value/bar)
         error bars      -> whisker cap endpoints
     - Restrict detection to plot_frame_box
     - Match layer_type to what you SEE (marker_shape->Scatter; line->Line)
     - Convert all detections to DATA coords via the calibration

  5. OUTPUT CONTRACT
     columns: layer_idx, layer_type, series, x, y   (+ y_lo,y_hi for errors)
     layer_type in {Scatter Plot, Bar Chart, Line Graph, Spline Chart, ErrorBarLayer}
     one row per data point, in data coordinates

  STRUCTURED RETURN (schema-enforced):
     { chart, rows_written:int, layers:str, issues:str }
     "your final message is data, not prose - keep it short"

Element -> variable it controls:

  HARD RULE (1) no GT      -> validity: extraction cannot peek at the answer
  HARD RULE (2) no Phase4  -> the independent variable being tested
  HARD RULE (3) reuse cal  -> holds calibration constant (Phase 2 shared)
  INPUT chart_metadata     -> holds series-ID constant (Phase 1 shared)
  METHODOLOGY block        -> keeps it the MLLM forward pass, not cv_oracle
  OUTPUT CONTRACT          -> every chart scorable with zero glue code

Workflow script of record:
  .claude/projects/.../workflows/scripts/v4-forward-pass-wf_02270dda-63d.js

## v6: calibrate-first canvas + peel-loop recovery

v6 = v4 extraction (reused) + deterministic PEEL recovery. prepare_canvas whitens everything outside the plot frame + the legend box (kills the legend/axis false-positive classes deterministically). peel.py erases v4 markers from the canvas and detects what remains -- residual ink = misses. GT-free. The subtractive form of close-the-loop (no matplotlib render).

| Corpus | v4 P/R/F1 (FP) | v6 P/R/F1 (FP) |
|---|---|---|
| aedes-aegypti-2014 | 0.923/0.800/0.858 (27) | 0.859/0.837/0.848 (56) |
| synthetic-r4-1 | 0.974/0.707/0.819 (10) | 0.919/0.707/0.799 (33) |
| owid-r6-1 | 1.000/0.633/0.775 (0) | 1.000/0.633/0.775 (0) |

**Peel is the first recall step to recover real points.** On aedes it lifts recall 0.800->0.837 (+15 true positives -- the el-94 fused 27C squares the gate could not see, since the points *layer* is present but *undercounted*). The completeness property holds: synthetic-01 (v4 already complete) yields ZERO residual, and the legend false-positives V5 imported are gone (whited by prepare_canvas).

**But residual-detector false positives still outweigh the gain on net F1**: aedes 0.858->0.848, synthetic 0.819->0.799 (synthetic misses are in CURVES, which peel-points cannot help, so its residual detections there are pure noise). owid unchanged (recovered points are scatter where GT types the series as lines).

**Verdict:** the subtract-and-recheck CONCEPT works -- it is the only mechanism that moved real recall, and it validates "zero residual = complete recall" without a matplotlib render. The remaining bottleneck is the residual detector's precision (grayscale noise, open-marker rings), not the peel idea. Next lever: a more precise residual detector (shape/solidity gating) and curve-peel for the synthetic curve misses, which could flip net F1 positive.