# Extractor: paper-atomizer-pro-latest

Same [paper-atomizer](https://github.com/crcresearch/paper-atomizer) extraction
code as [`paper-atomizer`](../paper-atomizer/), but with the chart-extraction
model swapped from `gemini-2.5-pro` (production) to **`gemini-pro-latest`** — no
other change. Automatic `extract_chart_data()`, never curated data.

## Model comparison (combined F1, `score_data.py`)

| corpus | `paper-atomizer` (2.5-pro) | **`paper-atomizer-pro-latest`** | graph-data-extraction v3 |
|---|---|---|---|
| synthetic-r4-1 (exact GT) | 0.569 | **0.767** | 0.904 |
| aedes-2014 (self-ref GT*) | 0.653 | **0.919** | 0.864 |
| owid-r6-1 (independent GT) | 0.416 | **0.536** | 0.382 |

The newer model lifts every corpus. Gains are **recall-driven** (more points
found) with precision holding at ~1.0:

| corpus | recall 2.5-pro → pro-latest | precision |
|---|---|---|
| synthetic | 0.417 → 0.622 | 0.895 → 1.000 |
| aedes | 0.554 → 0.877 | 0.795 → 0.965 |
| owid | 0.263 → 0.366 | 1.000 → 1.000 |

On `owid-r6-1` — the only fully independent ground truth — `pro-latest` (0.536)
now clearly beats the pixel-detection method (0.382), where `2.5-pro` only tied it.

*aedes caveat: its GT is paper-atomizer's own curated output, so scoring there is
auto-vs-curated, not an independent test.

## Reproduce

```bash
# in paper-atomizer/backend, with a GOOGLE_API_KEY that can reach the model:
CHART_EXTRACTION_MODEL=gemini-pro-latest \
uv run python scripts/run_harness_extraction.py --corpus <corpus-id> \
    --name paper-atomizer-pro-latest --harness /path/to/figure-recovery-suite
# then, here:
python3 scoring/score_data.py <corpus-id> paper-atomizer-pro-latest --results-dir results
```

## Notes

- Same adapter, same schema, same scoring caveats as the `paper-atomizer`
  baseline (series-label matching, fit-curve vertices-vs-dense-GT — see that
  README and issue #1).
- Takeaway for paper-atomizer: the extraction model is a bigger lever than any
  calibration step. An oracle test (applying the best per-axis affine correction
  a calibration would make) recovers ~0 F1 on the 2.5-pro output; the model swap
  alone adds +0.12 to +0.27 F1.
