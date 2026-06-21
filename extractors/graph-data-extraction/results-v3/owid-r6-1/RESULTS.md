# Results — graph-data-extraction (v3) on `owid-r6-1`

10 Our World in Data charts, GT downloaded from OWID's CSV API

Source: `scoring_data.json` (same directory). Produced by `scoring/score_data.py owid-r6-1 graph-data-extraction --results-dir results-v3` against the post-c8a1d86 scorer (percent-of-axis-range tolerance, 2 % default; relative override for log-y and extreme dynamic range; categorical-x widening for grouped/stacked bars).

## Headline — corpus totals

| layer    | TP   | FN   | FP   | Precision | Recall | F1     | Jaccard |
|----------|------|------|------|-----------|--------|--------|---------|
| scatter  | 0 | 165 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| curves   | 1923 | 6056 | 0 | 1.000 | 0.241 | 0.388 | 0.241 |
| errbars  | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| **combined** | **1923** | **6221** | **0** | **1.000** | **0.236** | **0.382** | **0.236** |

## Per-chart F1 (combined)

| chart | scatter F1 | curves F1 | errbars F1 | combined F1 | Precision | Recall |
|---|---|---|---|---|---|---|
| annual-co2-emissions-per-country | 0.000 | 0.420 | 0.000 | **0.420** | 1.000 | 0.266 |
| child-mortality | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 | 0.000 |
| co2-emissions-per-capita | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 | 0.000 |
| gdp-per-capita-worldbank | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 | 0.000 |
| global-primary-energy | 0.000 | 0.962 | 0.000 | **0.962** | 1.000 | 0.927 |
| life-expectancy | 0.000 | 0.880 | 0.000 | **0.880** | 1.000 | 0.786 |
| life-expectancy-vs-gdp-per-capita | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 | 0.000 |
| population | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 | 0.000 |
| share-electricity-low-carbon | 0.000 | 0.999 | 0.000 | **0.999** | 1.000 | 0.997 |
| share-of-individuals-using-the-internet | 0.000 | 0.909 | 0.000 | **0.909** | 1.000 | 0.833 |

## Re-running

```bash
python3 scoring/score_data.py owid-r6-1 graph-data-extraction --results-dir results-v3
```

Numbers above will reproduce as long as `extractors/graph-data-extraction/results-v3/owid-r6-1/<chart>/data.csv` is unchanged. To re-extract, point the `graph-data-extraction` skill at `corpora/owid-r6-1/charts/<chart>/image.png` per chart.
