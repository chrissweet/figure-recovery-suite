# Results — graph-data-extraction (v3) on `synthetic-r4-1`

10 matplotlib-generated charts, exact GT via ax.transData.transform()

Source: `scoring_data.json` (same directory). Produced by `scoring/score_data.py synthetic-r4-1 graph-data-extraction --results-dir results-v3` against the post-c8a1d86 scorer (percent-of-axis-range tolerance, 2 % default; relative override for log-y and extreme dynamic range; categorical-x widening for grouped/stacked bars).

## Headline — corpus totals

| layer    | TP   | FN   | FP   | Precision | Recall | F1     | Jaccard |
|----------|------|------|------|-----------|--------|--------|---------|
| scatter  | 108 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| curves   | 269 | 93 | 0 | 1.000 | 0.743 | 0.853 | 0.743 |
| errbars  | 62 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **combined** | **439** | **93** | **0** | **1.000** | **0.825** | **0.904** | **0.825** |

## Per-chart F1 (combined)

| chart | scatter F1 | curves F1 | errbars F1 | combined F1 | Precision | Recall |
|---|---|---|---|---|---|---|
| 01-linear-scatter | 1.000 | 0.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| 02-simple-bar | 1.000 | 0.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| 03-grouped-bar-errbars | 1.000 | 0.000 | 1.000 | **1.000** | 1.000 | 1.000 |
| 04-log-y-line | 0.000 | 0.367 | 0.000 | **0.367** | 1.000 | 0.225 |
| 05-stacked-bar | 1.000 | 0.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| 06-scatter-asym-errbars | 1.000 | 0.000 | 1.000 | **1.000** | 1.000 | 1.000 |
| 07-dual-y-axes | 0.000 | 1.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| 08-percent-scinot-ticks | 0.000 | 1.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| 09-open-markers-with-fit | 1.000 | 1.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| 10-crossing-curves | 0.000 | 1.000 | 0.000 | **1.000** | 1.000 | 1.000 |

## Re-running

```bash
python3 scoring/score_data.py synthetic-r4-1 graph-data-extraction --results-dir results-v3
```

Numbers above will reproduce as long as `extractors/graph-data-extraction/results-v3/synthetic-r4-1/<chart>/data.csv` is unchanged. To re-extract, point the `graph-data-extraction` skill at `corpora/synthetic-r4-1/charts/<chart>/image.png` per chart.
