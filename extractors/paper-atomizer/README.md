# Extractor: paper-atomizer

[paper-atomizer](https://github.com/crcresearch/paper-atomizer)'s automatic
chart-data extraction, run through this harness. Results are the **automatic**
output of `extract_chart_data()` (a single-image Gemini call, `gemini-2.5-pro`)
— never paper-atomizer's human-curated data.

Note on the aedes corpus: its ground truth *is* paper-atomizer's own curated
output, so scoring paper-atomizer there is auto-vs-curated (a home-field
advantage), not an independent test. `owid-r6-1` (published data) and
`synthetic-r4-1` (exact generator GT) are the clean comparisons.

## Results (scored with `scoring/score_data.py`, combined F1)

| corpus | TP | FN | FP | P | R | F1 |
|---|---|---|---|---|---|---|
| synthetic-r4-1 | 222 | 310 | 26 | 0.895 | 0.417 | 0.569 |
| aedes-aegypti-2014* | 225 | 181 | 58 | 0.795 | 0.554 | 0.653 |
| owid-r6-1 | 2140 | 6004 | 0 | 1.000 | 0.263 | 0.416 |

*self-referential GT (see note above)

Per-corpus `scoring_data.json` carries the per-chart, per-layer breakdown.

## What each file is

```
results/<corpus>/<chart-id>/
    data.csv          flattened points in the harness schema
                      (layer_idx, layer_type, series, x, y, error cols, y_lo/y_hi)
    chart_data.json   raw paper-atomizer chart_data (Gemini output, unmodified)
results/<corpus>/scoring_data.json   score_data.py output
```

## Reproduce

The extraction adapter lives in the paper-atomizer repo (it imports the
pipeline), not here:

```bash
# in paper-atomizer/backend, with GOOGLE_API_KEY set:
uv run python scripts/run_harness_extraction.py --corpus <corpus-id> \
    --harness /path/to/figure-recovery-suite
# then, here:
python3 scoring/score_data.py <corpus-id> paper-atomizer --results-dir results
```

The adapter maps chart_data → the harness `data.csv` schema, auto-detecting the
corpus error-bar schema (ErrorBarLayer rows vs y_lo/y_hi columns).

## Known scoring caveats for this extractor

- **Series labels.** paper-atomizer sometimes labels a series differently than
  the GT (e.g. `"Data Points"` vs `24°C/27°C/30°C`). The per-series matcher then
  scores correct coordinates as FN. Pooling labels recovers +21 correct points
  on `owid-r6-1/life-expectancy-vs-gdp-per-capita` alone (+12.7% scatter recall)
  and +2 on aedes. A fallback to x-position mapping for arbitrary naming would
  remove this.
- **Fit curves.** paper-atomizer returns fit curves as vertices (~11 points
  spanning the x-range); scored against densely-sampled smooth-curve GT, the
  linear interpolation between vertices falls outside tolerance where the curve
  bends. A representation mismatch, not a wrong reading.
