# Results — feedback-loop-extractor (experimental, single-chart)

This extractor is the **experimental branch** documented in [Analysis-Feedback-Loop-Off-Course-2026-06-21](../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md). There is **no corpus-wide evaluation** because the loop was only ever run on a single chart (aedes-aegypti-2014 / el-100) as a diagnostic. The six update heuristics + the loop driver each produced an iter-1 `data.csv` on that chart. Each one is scored below against el-100 GT, vs the v3 baseline (which is iter 0 — what the loop bootstrapped from).

Scoring: `scoring/score_data.py` against the post-c8a1d86 percent-of-axis-range scorer, on `aedes-aegypti-2014/el-100` only.

## Per-iteration F1 on aedes el-100

| iteration | scatter F1 | curves F1 | errbars F1 | Precision | Recall | combined F1 | delta vs baseline |
|---|---|---|---|---|---|---|---|
| **v3 baseline (iter 0)** | 0.618 | 0.957 | 0.000 | 0.772 | 0.772 | **0.772** | (baseline) |
| diff_update | 0.438 | 0.957 | 0.000 | 0.938 | 0.594 | 0.727 | -0.045 |
| absdiff_update | 0.545 | 0.957 | 0.000 | 0.789 | 0.703 | 0.744 | -0.029 |
| subregion_update | 0.069 | 0.957 | 0.000 | 0.939 | 0.455 | 0.613 | -0.159 |
| local_crop_update | 0.428 | 0.957 | 0.000 | 0.520 | 0.772 | 0.622 | -0.151 |
| **count_balance** | 0.455 | 0.957 | 0.000 | 0.810 | 0.634 | **0.711** | -0.061 |
| loop driver iter 1 (3 of 4) | 0.404 | 0.921 | 0.000 | 0.627 | 0.634 | 0.630 | -0.142 |

## Honest summary

- **No iteration improved F1 over the v3 baseline.** Best delta is 0.000 (no change); most are negative.
- The most productive update (count_balance) reduced per-color over-ink by 70 % on el-100 but did not improve F1 against GT because dropped marker positions then count as FN.
- The root cause is documented in the wiki analysis: the loop manipulated v3's output rows directly instead of feeding signals into v3's parameters and re-running v3. Editing rows can only ever shuffle the points; it can't re-detect what v3 missed.
- See `code/README.md` for what's worth keeping (pixel_replot, count_balance signal, color_tolerance HSV fallback, local-crop pattern) vs what's worth discarding (the row-manipulation heuristics themselves).

## Re-scoring

Each iteration's `data.csv` is at the path listed in the table. To re-score any of them against el-100 GT, stage it as `extractors/<name>/<results-dir>/aedes-aegypti-2014/el-100/data.csv` (with v3's `calibration.json` + `chart_metadata.json` alongside) and run `python3 scoring/score_data.py aedes-aegypti-2014 <name> --results-dir <results-dir>`.
