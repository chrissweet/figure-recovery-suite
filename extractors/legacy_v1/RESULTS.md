# legacy_v1 — results

Layout follows the project convention: `results/<corpus>/` per corpus.

| corpus | run? | combined Precision | Recall | F1 | details |
|---|---|---|---|---|---|
| aedes-aegypti-2014 | yes | **0.887** | **0.466** | **0.611** | [`results/aedes-aegypti-2014/RESULTS.md`](results/aedes-aegypti-2014/RESULTS.md) (symlink → `../../graph-data-extraction/results/aedes-aegypti-2014/`) |
| synthetic-r4-1 | no | – | – | – | [`results/synthetic-r4-1/NOT_RUN.md`](results/synthetic-r4-1/NOT_RUN.md) — v1 code is aedes-specific |
| owid-r6-1 | no | – | – | – | [`results/owid-r6-1/NOT_RUN.md`](results/owid-r6-1/NOT_RUN.md) — same |

The aedes numbers reflect re-scoring against the current post-c8a1d86 scorer. Scatter-only F1 = 0.863 (close to the historic r3 PDF's 0.898 — current scorer is slightly stricter). Curves and errbars are 0.000 because legacy_v1 only emitted scatter-point data; the trend lines, fit curves, and error bars that GT contains were never extracted by these scripts.

## Code

`code/` holds the original aedes-specific scripts. See `code/README.md` for the per-script breakdown and why they exist (post-hoc reconstruction of in-session heredocs that produced the v1 outputs).

## Why the results live where they do

`results/aedes-aegypti-2014/` is a symlink into `../../graph-data-extraction/results/aedes-aegypti-2014/` because v1 outputs were historically placed there (v1 is the first generation of the same logical extractor that became v2 and v3, all writing under `extractors/graph-data-extraction/results*/`). The symlink makes the data discoverable from the `legacy_v1` extractor folder following the `extractors/<name>/results/<corpus>/` project convention.

## How to add a corpus

To run legacy_v1 on a new corpus, port the per-chart functions in `code/extract_all.py` to the new corpus's chart types. v1's chart-specific heuristics don't generalise.
