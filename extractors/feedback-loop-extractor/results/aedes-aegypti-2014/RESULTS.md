# Results — feedback-loop-extractor on `aedes-aegypti-2014`

**Partial corpus run only.** The loop driver was exercised on a single chart (`el-100`) as a diagnostic across six update heuristics + one full loop-driver run. The remaining 7 charts in aedes-aegypti-2014 were never extracted by this branch.

## Canonical el-100 output

`el-100/data.csv` carries the **count_balance iter-1 output** (the most-developed heuristic). Scored against el-100 GT via the post-c8a1d86 scorer:

| layer    | TP | FN | FP | Precision | Recall | F1     |
|----------|----|----|----|-----------|--------|--------|
| scatter  | 20 | 33 | 15 | 0.571 | 0.377 | 0.455 |
| curves   | 44 | 4  | 0  | 1.000 | 0.917 | 0.957 |
| errbars  | 0  | 0  | 0  | – | – | – |
| **combined** | **64** | **37** | **15** | **0.810** | **0.634** | **0.711** |

**vs v3 baseline on the same chart: F1 = 0.772 → 0.711, a loss of 0.061.** The "best" iteration is worse than doing nothing (i.e., shipping v3's output unchanged).

## All iteration variants compared

Re-scoring each heuristic's `iter1_data.csv` (the inputs are in `single_pass/el-100_*/`) against the same GT:

| iteration | scatter F1 | curves F1 | combined F1 | Precision | Recall | Δ vs v3 baseline |
|---|---|---|---|---|---|---|
| **v3 baseline (iter 0)** | 0.618 | 0.957 | **0.772** | 0.772 | 0.772 | (baseline) |
| absdiff_update | 0.545 | 0.957 | 0.744 | 0.789 | 0.703 | −0.028 |
| diff_update | 0.438 | 0.957 | 0.727 | 0.938 | 0.594 | −0.045 |
| count_balance | 0.455 | 0.957 | **0.711** | 0.810 | 0.634 | **−0.061** |
| loop driver iter 3 (of 4) | 0.404 | 0.921 | 0.630 | 0.627 | 0.634 | −0.142 |
| local_crop_update | 0.428 | 0.957 | 0.622 | 0.520 | 0.772 | −0.150 |
| subregion_update | 0.069 | 0.957 | 0.613 | 0.939 | 0.455 | −0.159 |

**Every iteration is worse than the v3 baseline.** count_balance was the most productive on the per-color count metric (70 % per-color over-ink reduction) but that translated to a 0.061 F1 loss against GT because dropped markers are then counted as missing data.

## Diagnostic artifacts

Each subdirectory under this corpus folder is a per-experiment record:

- `iter0_demo/` — early visual demo (binary-mask diff, before the iteration arc began)
- `research_demo/el-100/` — full loop-driver run, 4 iterations under `iterations/0..3/` with per-iter `data.csv`, `replot_data_layer.png`, three reports
- `single_pass/el-100_*/` — one subdir per update heuristic, each with `iter0_replot.png`, `iter1_replot.png`, `iter1_data.csv`, `summary.json`, and a `before_after_absdiff.png`
- `single_pass/el-100/` — the bootstrap state (v3 output rendered through `code/render/pixel_replot.py` with the absdiff diagnostic)

## Why no other charts

The wiki analysis [Analysis-Feedback-Loop-Off-Course-2026-06-21](../../../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md) explains. Short version: the loop operated on v3's output rows instead of v3's parameters, which can only shuffle existing claims and cannot re-detect what v3 missed. Running it on the other 7 aedes charts would reproduce the same architectural failure mode without addressing the root cause.

## Re-running

```bash
python3 scoring/score_data.py aedes-aegypti-2014 feedback-loop-extractor --results-dir results
```

Will produce / refresh `scoring_data.json` next to this file. To re-score a specific iteration variant, swap its `iter1_data.csv` in for `el-100/data.csv` first.
