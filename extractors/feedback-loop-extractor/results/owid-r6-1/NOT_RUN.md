# feedback-loop-extractor not run on `owid-r6-1`

Same reason as `synthetic-r4-1/NOT_RUN.md`: the loop was a single-chart diagnostic on `aedes-aegypti-2014/el-100`, every iteration scored worse than the v3 baseline, and the wiki analysis documents why ([Analysis-Feedback-Loop-Off-Course-2026-06-21](../../../../wiki/figure-recovery-suite.wiki/Analysis-Feedback-Loop-Off-Course-2026-06-21.md)). Running it on owid-r6-1 would reproduce the architectural failure on 10 more charts.

For owid-r6-1 results, see [`extractors/graph-data-extraction/results-v3/owid-r6-1/RESULTS.md`](../../../graph-data-extraction/results-v3/owid-r6-1/RESULTS.md) (v3 baseline: combined F1 = 0.382).
