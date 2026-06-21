# Results — cross-extractor cross-corpus summary

One row per (corpus, extractor) scored against GT via `scoring/score_data.py` (post-c8a1d86 percent-of-axis-range scorer).

Per-corpus detail (including per-chart F1 distribution and which extractors fully ran the corpus vs partial) is at `corpora/<corpus>/RESULTS.md`.

| corpus | extractor | charts run | corpus P | corpus R | corpus F1 | pc F1 mean |
|---|---|---|---|---|---|---|
| aedes-aegypti-2014 | legacy_v1 | 8/8 | 0.887 | 0.466 | **0.611** | 0.574 |
| aedes-aegypti-2014 | graph-data-extraction v3 | 8/8 | 0.933 | 0.804 | **0.864** | 0.892 |
| aedes-aegypti-2014 | feedback-loop-extractor | 1/8 (partial) | 0.810 | 0.634 | **0.711** | 0.711 |
| synthetic-r4-1 | graph-data-extraction v3 | 10/10 | 1.000 | 0.825 | **0.904** | 0.937 |
| owid-r6-1 | graph-data-extraction v3 | 10/10 | 1.000 | 0.236 | **0.382** | 0.417 |

## Average across extractors that fully ran each corpus

| corpus | n full extractors | mean cP | mean cR | mean cF1 |
|---|---|---|---|---|
| aedes-aegypti-2014 | 2 | 0.910 | 0.635 | **0.737** |
| synthetic-r4-1 | 1 | 1.000 | 0.825 | **0.904** |
| owid-r6-1 | 1 | 1.000 | 0.236 | **0.382** |

## Reading notes

- **corpus-aggregate P / R / F1** weights each chart by its GT-point count (a chart with 100 GT points counts 10× a chart with 10).
- **per-chart F1 mean** weights every chart equally regardless of GT size; useful when a few large charts shouldn't dominate.
- **'partial' coverage** means the extractor was only run on a subset of the corpus's charts. The F1 reported is over the subset, not the full corpus.

## Re-generate
```bash
for corpus in aedes-aegypti-2014 synthetic-r4-1 owid-r6-1; do
    python3 scoring/score_data.py $corpus graph-data-extraction --results-dir results-v3
done
python3 scoring/score_data.py aedes-aegypti-2014 graph-data-extraction --results-dir results  # v1
```
