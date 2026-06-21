# Results — graph-data-extraction (v1, legacy_v1 code) on `aedes-aegypti-2014`

Produced by the `legacy_v1` extractor code at `extractors/legacy_v1/code/` (the original aedes-specific scripts). 8 real published charts from a paper on *Aedes aegypti* parity and longevity; hand-transcribed GT.

Source: `scoring_data.json` (same directory). Re-scored 2026-06-21 against the post-c8a1d86 scorer for apples-to-apples comparison with v2 and v3.

## Headline — corpus totals

| layer    | TP   | FN   | FP   | Precision | Recall | F1     | Jaccard |
|----------|------|------|------|-----------|--------|--------|---------|
| scatter  | 189 | 36 | 24 | 0.887 | 0.840 | 0.863 | 0.759 |
| curves   | 0 | 162 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| errbars  | 0 | 19 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| **combined** | **189** | **217** | **24** | **0.887** | **0.466** | **0.611** | **0.440** |

**curves and errbars are 0.000** because legacy_v1 only emitted scatter-point data; the trend lines, fit curves, and error bars that GT contains were never extracted by these scripts. The r3 PDF report (`docs/aedes-2014_eval_r3.pdf`) cited 0.898 — that number is scatter-only (the rubric at r3 didn't yet score curves/errbars). Current scorer grades all three layers, so combined F1 reflects the unsmitted-layers penalty (-0.255 vs scatter-only).

## Per-chart F1 (combined)

| chart | scatter F1 | curves F1 | errbars F1 | combined F1 | Precision | Recall |
|---|---|---|---|---|---|---|
| el-100 | 0.712 | 0.000 | 0.000 | **0.487** | 0.726 | 0.366 |
| el-60-a | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 | 0.000 |
| el-60-b | 1.000 | 0.000 | 0.000 | **0.750** | 1.000 | 0.600 |
| el-62 | 1.000 | 0.000 | 0.000 | **0.667** | 1.000 | 0.500 |
| el-75 | 1.000 | 0.000 | 0.000 | **0.545** | 1.000 | 0.375 |
| el-80 | 1.000 | 0.000 | 0.000 | **0.667** | 1.000 | 0.500 |
| el-88 | 0.961 | 0.000 | 0.000 | **0.961** | 0.948 | 0.973 |
| el-94 | 0.826 | 0.000 | 0.000 | **0.513** | 0.905 | 0.358 |

## Re-running
```bash
python3 scoring/score_data.py aedes-aegypti-2014 graph-data-extraction --results-dir results
```

## See also
- `../results-v2/` — v2 outputs (Phase-4 close-the-loop iteration; adds curves and errbars)
- `../results-v3/` — v3 outputs (current canonical; F1 = 0.864 on this corpus)
- `../../legacy_v1/code/README.md` — the scripts that produced these outputs
