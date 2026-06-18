# Corpus: aedes-aegypti-2014

8 charts (subfigures) extracted from a single paper on *Aedes aegypti* parity and longevity under controlled temperatures: "Parity and Longevity of *Aedes aegypti* According to Temperatures in Controlled Conditions and Consequences on Dengue Transmission Risks." Each chart has ground-truth coordinates and calibration produced by an upstream extraction tool (paper-atomizer), independent of any extractor benchmarked here.

## Layout

```
aedes-aegypti-2014/
└── charts/
    ├── el-60-a/
    │   ├── image.png                          # the figure (input to extractors)
    │   ├── ground_truth.csv                   # x, y, series — paper-atomizer's reading
    │   ├── ground_truth_calibration.json      # selector_rect, axis_calibration
    │   └── metadata.json                      # chart type, axis labels, n_points, source
    ├── el-60-b/   ...
    └── el-100/    ...
```

## Charts

| id | type | series | notes |
|---|---|---|---|
| el-60-a | 3-color line plot | 24°C / 27°C / 30°C | parity rate over time |
| el-60-b | 3-point scatter | 24°C / 27°C / 30°C | max parity rate vs temperature |
| el-62 | grouped bar chart | GC1 / GC2 / GC3 | GC duration at 24 / 27 / 30°C |
| el-75 | scatter w/ x and y error bars | single series | GC duration vs temperature |
| el-80 | small grouped bar chart (stippled fill) | GC1 / GC2 / GC3 | egg counts at 24 / 27 / 30°C |
| el-88 | grayscale 3-shape scatter | 24°C / 27°C / 30°C | survival rate by age |
| el-94 | grayscale 3-shape scatter + 3 fit curves | 24°C / 27°C / 30°C | daily survival probability |
| el-100 | colored scatter + dashed/solid fit lines in same colors | 24°C / 27°C / 30°C | infective life expectancy vs parity |

Total: **251 ground-truth data points** across the 8 charts.

## Provenance

- **Source paper id (paper-atomizer):** `e9d2f862-1273-47c2-a91f-95b0c6c6f8bd`
- **Ground-truth tool:** paper-atomizer (separate project under `paper-atomizer-eval/`); ground-truth files are versioned with `calibration_version: 3` produced 2026-06-17.
- **License:** TBD — the paper itself is the underlying source; corpus files are derivative. Don't redistribute without checking the paper's license.

## Schema notes

- `ground_truth.csv` columns: `layer_idx, layer_type, series, x, y, marker_type, color, error_x_plus, error_x_minus, error_y_plus, error_y_minus`. Empty fields are common (e.g. error columns when no error bars).
- `ground_truth_calibration.json` is the paper-atomizer's own format (`selector_rect`, `axis_calibration`, `marking_method`, `points`, `version`). NOT the same schema as extractor calibrations.
- `metadata.json` lists chart type, axis labels, point count, and the source paper.

## Known quirks

- el-60-a has a misplaced 14th 27°C row appended at the end of the CSV (manual edit), out of x-order.
- el-60-b series are labeled `Series 1 / 2 / 3` rather than `24°C / 27°C / 30°C`. Map by x position.
- el-75 series is labeled `Data Points` for all three; not distinguished by temperature.
- el-62, el-80 (grouped bar charts) have x-tick centers at the *group center* rather than the bar center; tolerance should accommodate the bar-within-group visual offset.
