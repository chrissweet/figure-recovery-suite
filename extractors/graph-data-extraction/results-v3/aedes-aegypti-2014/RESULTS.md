# Results — graph-data-extraction (v3) on `aedes-aegypti-2014`

8 real published charts from a paper on Aedes aegypti parity and longevity; hand-transcribed GT

Source: `scoring_data.json` (same directory). Produced by `scoring/score_data.py aedes-aegypti-2014 graph-data-extraction --results-dir results-v3` against the post-c8a1d86 scorer (percent-of-axis-range tolerance, 2 % default; relative override for log-y and extreme dynamic range; categorical-x widening for grouped/stacked bars).

## Headline — corpus totals

| layer    | TP   | FN   | FP   | Precision | Recall | F1     | Jaccard |
|----------|------|------|------|-----------|--------|--------|---------|
| scatter  | 197 | 28 | 30 | 0.868 | 0.876 | 0.872 | 0.772 |
| curves   | 205 | 71 | 0 | 1.000 | 0.743 | 0.852 | 0.743 |
| errbars  | 16 | 3 | 0 | 1.000 | 0.842 | 0.914 | 0.842 |
| **combined** | **418** | **102** | **30** | **0.933** | **0.804** | **0.864** | **0.760** |

## Per-chart F1 (combined)

| chart | scatter F1 | curves F1 | errbars F1 | combined F1 | Precision | Recall |
|---|---|---|---|---|---|---|
| el-100 | 0.618 | 0.957 | 0.000 | **0.772** | 0.772 | 0.772 |
| el-60-a | 0.000 | 0.762 | 0.000 | **0.762** | 1.000 | 0.615 |
| el-60-b | 1.000 | 1.000 | 0.000 | **1.000** | 1.000 | 1.000 |
| el-62 | 1.000 | 0.000 | 1.000 | **1.000** | 1.000 | 1.000 |
| el-75 | 1.000 | 1.000 | 0.000 | **0.769** | 1.000 | 0.625 |
| el-80 | 1.000 | 0.000 | 1.000 | **1.000** | 1.000 | 1.000 |
| el-88 | 0.980 | 0.000 | 0.000 | **0.980** | 0.987 | 0.973 |
| el-94 | 0.913 | 0.832 | 0.000 | **0.857** | 0.972 | 0.766 |

## Re-running

```bash
python3 scoring/score_data.py aedes-aegypti-2014 graph-data-extraction --results-dir results-v3
```

Numbers above will reproduce as long as `extractors/graph-data-extraction/results-v3/aedes-aegypti-2014/<chart>/data.csv` is unchanged. To re-extract, point the `graph-data-extraction` skill at `corpora/aedes-aegypti-2014/charts/<chart>/image.png` per chart.
