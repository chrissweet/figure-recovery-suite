# feedback-loop-extractor — results

Layout follows the project convention: `results/<corpus>/` per corpus.

| corpus | run? | combined Precision | Recall | F1 | details |
|---|---|---|---|---|---|
| aedes-aegypti-2014 | **partial** (1 chart, el-100) | **0.810** | **0.634** | **0.711** | [`results/aedes-aegypti-2014/RESULTS.md`](results/aedes-aegypti-2014/RESULTS.md) |
| synthetic-r4-1 | no | – | – | – | [`results/synthetic-r4-1/NOT_RUN.md`](results/synthetic-r4-1/NOT_RUN.md) |
| owid-r6-1 | no | – | – | – | [`results/owid-r6-1/NOT_RUN.md`](results/owid-r6-1/NOT_RUN.md) |

This extractor is the **experimental branch** documented in [Analysis-Feedback-Loop-Off-Course-2026-06-21](../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md). The aedes "partial" row reflects a single-chart diagnostic on `el-100`; the remaining 7 aedes charts plus synthetic-r4-1 and owid-r6-1 were never run.

## Single-chart headline (el-100, the only chart attempted)

| iteration | combined F1 | Δ vs v3 baseline |
|---|---|---|
| **v3 baseline (iter 0)** | **0.772** | (bar to beat) |
| absdiff_update | 0.744 | −0.028 |
| diff_update | 0.727 | −0.045 |
| **count_balance** (canonical `el-100/data.csv`) | **0.711** | **−0.061** |
| loop driver iter 3 (of 4) | 0.630 | −0.142 |
| local_crop_update | 0.622 | −0.150 |
| subregion_update | 0.613 | −0.159 |

**No iteration improved on the v3 baseline.** The wiki analysis explains the architectural reason: the loop edited v3's output rows directly instead of feeding signals into v3's parameters and re-running v3. Editing rows can shuffle points but cannot re-detect what v3 missed.

Per-chart detail, all iteration variants, and the diagnostic artifact directory layout are in `results/aedes-aegypti-2014/RESULTS.md`.

## Code

`code/` holds the loop driver, the two predicates, the pixel-precise renderer, the per-color count-balance update, and the five other update-heuristic attempts. See `code/README.md` for what's worth keeping vs what's worth discarding.
