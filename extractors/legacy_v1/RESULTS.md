# legacy_v1 — results

The `legacy_v1` code at [`code/`](code/) produced the v1 generation of extractor outputs. **Those outputs live at `../graph-data-extraction/results/`** (one chart per subdir, plus the scored summary), not under this directory, because v1 is the first generation of the same logical extractor that became v2 and v3.

## Headline on aedes-aegypti-2014 (the only corpus v1 was run on)

| layer | Precision | Recall | F1 |
|---|---|---|---|
| scatter | 0.887 | 0.840 | 0.863 |
| curves | 0.000 | 0.000 | 0.000 |
| errbars | 0.000 | 0.000 | 0.000 |
| **combined** | **0.887** | **0.466** | **0.611** |

Curves and errbars are 0.000 because legacy_v1 only emitted scatter-point data. Full per-chart breakdown + commentary at [`../graph-data-extraction/results/aedes-aegypti-2014/RESULTS.md`](../graph-data-extraction/results/aedes-aegypti-2014/RESULTS.md).

Re-score: `python3 scoring/score_data.py aedes-aegypti-2014 graph-data-extraction --results-dir results`
