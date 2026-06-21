# feedback-loop-extractor not run on `synthetic-r4-1`

The `feedback-loop-extractor` experimental branch was only ever run on a single chart (`aedes-aegypti-2014/el-100`) as a diagnostic. The loop driver diverged on that chart (mean per-series IoU went 0.22 → 0.14 over 4 iterations) and none of the six update heuristics improved F1 over the v3 baseline.

The wiki analysis [Analysis-Feedback-Loop-Off-Course-2026-06-21](../../../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md) names why: the loop manipulated v3's output rows directly instead of feeding signals back into v3's parameters. Running it on synthetic-r4-1 would reproduce the same wrong-layer failure mode on 10 more charts without addressing the architectural issue.

For synthetic-r4-1 results, see [`extractors/graph-data-extraction/results-v3/synthetic-r4-1/RESULTS.md`](../../../graph-data-extraction/results-v3/synthetic-r4-1/RESULTS.md) (v3 baseline: combined F1 = 0.904).
