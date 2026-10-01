# Per-type extraction panels

One panel per graph type Claude Code encountered in the free-rein runs. Panels come in two layouts. The **combo** and **grouped-bar** panels are 2-up
(generated-OpenCV target/detection on the left, pixel-check against the input on
the right). The **dense-bubble** and **multi-line** panels are **4-stage process
grids**, because their value is the pipeline itself (separating overlapping
bubbles from colored labels; separating 7 same-family line colors). Representative
chart named in each title; score is the real per-type metric
(`scoring/per_type_score.py`), corpus-tagged.

| panel | type | representative chart | headline |
|---|---|---|---|
| `type1_grayscale-combo.png` | Grayscale-fusion combo | Aedes daily survival el-94 (aedes-aegypti-2014) | position F1 0.93 |
| `type2_dense-bubble.png` | Dense bubble scatter | Life expectancy vs GDP (owid-r6-1) | density corr 0.94, 132/165 markers |
| `type3_multi-line.png` | Multi-series time-series line | Annual CO2 emissions (owid-r6-1) | 7 lines traced (overlay-verified) |
| `type4_grouped-bar.png` | Grouped bar + error bars | Synthetic #3 throughput (synthetic-r4-1) | bar-value F1 1.00, 15 bars + 30 caps |

Notes for honest use on a slide:
- Provenance of the stage images:
  - **dense-bubble** stages (mask, erode, peaks, overlay) and **grouped-bar** (T-cap
    zoom, overlay) are all the model's **own saved artifacts**.
  - **el-94** target-region box map is a **post-hoc reconstruction** from the saved
    zoom crops (a lower bound on where it looked), not live eye-tracking.
  - **multi-line** stages 1–2 (calibration + nearest-color classification) are
    **faithful reconstructions of the documented method** (the agent saved no
    intermediate stage images for this chart); stages 3–4 (crowded-band zoom,
    pixel-check overlay) are the agent's own saved artifacts.
- Right images are the model's verification overlays (extracted data redrawn on
  the source), the step that makes the digitization checkable.
- annual-co2's curve F1 is 0.34 under the current scorer despite the verified
  trace; that is a measurement-layer gap (out-of-range + tight tolerance), so the
  panel reports "traced onto their lines (overlay-verified)" rather than a score.

Source wiki pages: `Analysis-Attention-Map-Visualization-2026-08-12`,
`Experiment-Free-Rein-Transcript-Review-2026-08-06`,
`Analysis-Graph-Type-Characterization-2026-08-05`.
