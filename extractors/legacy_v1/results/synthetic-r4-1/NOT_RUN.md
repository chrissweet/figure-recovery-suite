# legacy_v1 not run on `synthetic-r4-1`

The `legacy_v1` extractor was never run on this corpus. The code at `extractors/legacy_v1/code/extract_all.py` is **aedes-specific** — each of the 8 charts has its own hand-tuned function with chart-specific HSV ranges, erosion kernels, mask exclusions, and calibration constants inlined. Running it on synthetic-r4-1 would require porting all of those per-chart heuristics to the 10 synthetic chart types, which is essentially writing a new extractor.

For synthetic-r4-1 results, see [`extractors/graph-data-extraction/results-v3/synthetic-r4-1/RESULTS.md`](../../../graph-data-extraction/results-v3/synthetic-r4-1/RESULTS.md) (v3 extractor: combined F1 = 0.904).
