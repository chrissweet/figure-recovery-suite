# Attention → error: does agentic attention predict / fix misses?

Two measurements on the chart corpus (real script outputs).

## 1. Attention does NOT predict WHICH point fails (point-level)

For every ground-truth point: sample the attention density there, label it recovered/missed,
compute AUC of attention → P(miss).

| chart | GT pts | misses | AUC |
|---|---|---|---|
| el-94 (aedes) | 75 | 8 | 0.534 |
| life-exp (owid) | 165 | 54 | 0.567 |
| **pooled** | 240 | 62 | **0.541** |

AUC ≈ 0.54 is barely above chance. Misses are *regionally* concentrated in high-attention
zones, but those zones are dominated by correctly-recovered points, so attention cannot
discriminate the individual failures. **Consequence: per-point uncertainty or per-point
compute allocation is NOT justified by this signal.** The signal is region-level, not point-level.
(Caveat: attention here is reconstructed from broad zoom crops; a finer effort signal —
revisit counts, zoom depth — might discriminate better.)

## 2. Region-targeted recompute DOES fix misses (region-level)

el-94's 8 misses all sit in one fused band (day 30–40, top-right). Recomputing ONLY that
region at 6× resolution with a dedicated shape-based detector:

- **recovered 8 / 8 of the original misses**
- **precision 100%** (32/32 new markers match a real GT point; 0 hallucinations)
- **recall 0.893 → 1.000**, no human in the loop

The misses were a *resolution artifact*: at native scale three marker types fuse; at 6× they
separate. The attention map told us WHERE to spend the expensive high-res pass (~5% of the image).

## Reconciliation & scope

- Attention is a **region-level difficulty localizer**, not a point-level error predictor.
  The deployable use is **adaptive test-time compute at region granularity**: recompute the
  hot region at higher resolution/effort. Demonstrated: +0.107 recall on el-94, automatically.
- **Mechanism matters.** Recompute helps for *resolution-limited* misses (fused markers separate
  at higher res). It will NOT help *occlusion-limited* misses (e.g. a dot fully hidden under a
  big bubble in the dense-bubble chart) — a different failure mode that more resolution can't fix.
- **n = 1 chart** for the recompute; AUC is 2 charts. Needs corpus-wide replication before it is
  a paper claim.

## Artifacts
- `attention_error_ROC.png` — the ROC curves
- `el94_fusion_zoom.png` — the 6× crop of the hot region
- `el94_recompute_overlay.png` — the recompute's detected markers
- `el94_attention_vs_miss.png` — misses (red) sitting in the hottest attention zone
