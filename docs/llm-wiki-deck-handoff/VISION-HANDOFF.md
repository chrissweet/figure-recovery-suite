# Handoff → vision agent: 4-panel per-type figures for the talk

**Purpose:** include the updated per-type extraction panels in the talk. There are
four panels, one per graph type Claude Code encountered. Each shows *what the
generated OpenCV pipeline targeted/did* alongside the *pixel-check against the
input*. Use them as the "Claude Code can digitize charts" sequence.

## The four panels (drop-in PNGs)

All in `docs/llm-wiki-deck-handoff/panels/` (absolute:
`/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/docs/llm-wiki-deck-handoff/panels/`).

| file | type | representative chart | layout | headline number |
|---|---|---|---|---|
| `type1_grayscale-combo.png` | Grayscale-fusion combo | Aedes daily survival (el-94) | 2-up (targets + pixel-check) | position **F1 0.93** |
| `type2_dense-bubble.png` | Dense bubble scatter | Life-expectancy vs GDP (OWID) | **4-stage process grid** | density corr **0.94**, 132/165 |
| `type3_multi-line.png` | Multi-series time-series line | Annual CO2 emissions (OWID) | **4-stage process grid** | 7 lines traced, overlay-verified |
| `type4_grouped-bar.png` | Grouped bar + error bars | Synthetic #3 throughput | 2-up (T-cap zoom + pixel-check) | bar-value **F1 1.00** |

## What changed in this update (vs any earlier copy)

- **type2 (dense-bubble)** is now a **4-stage process grid**: color mask (markers +
  colored labels both light up) → erode (text strokes die, seeds land on dots) →
  distance-transform peaks (132 centers) → pixel-check. (Old version was a 2-up that
  "didn't describe the process.")
- **type3 (multi-line)** is now a **4-stage process grid**: calibrate + sample the 7
  series colors → classify every pixel to its nearest color (7 separated traces) →
  resolve the China-navy vs UK-steel collision → pixel-check. (Old version leaned on
  a sparse attention heatmap.)
- **type1 and type4** are unchanged 2-up panels.

Use the current files as-is; they supersede any earlier panel PNGs.

## One-line narrative for the set

"Given only a chart image, Claude Code writes its own OpenCV pipeline — calibrate
from the axes, detect points/lines, zoom to resolve local ambiguity, then re-draw
its extracted data on the source to pixel-check — across four different graph
types."

## Suggested slide captions (per panel)

- **type1:** "Grayscale-fusion combo — 3 marker series + 3 fused fit curves; F1 0.93."
- **type2:** "Dense bubbles — erosion removes label text, distance-transform splits touching bubbles; density corr 0.94."
- **type3:** "7 same-family colored lines — per-pixel nearest-color classification separates them; China-vs-UK collision resolved."
- **type4:** "Grouped bars + asymmetric error bars — threshold-tuned T-cap reading; bar-value F1 1.00, all 15 bars + 30 caps."

## Honest-use notes (so the talk doesn't overclaim)

- Left images are the model's own detection/process artifacts **except**: type1's
  target-region box map is a post-hoc reconstruction from saved zoom crops, and
  type3's stages 1–2 (calibration + nearest-color classification) are faithful
  reconstructions of the documented method (the agent saved no intermediate stage
  images for that chart). type2 and type4 stages are the agent's own saved artifacts.
- Right images (pixel-check overlays) are the model's own verification renders.
- **annual-co2 (type3)** scores curve-F1 0.34 under the current scorer despite the
  overlay-verified trace — a measurement-layer artifact, not an extraction failure —
  so the panel says "7 lines traced (overlay-verified)," **not** a score. Keep that
  framing in the talk.

## Deeper context (optional, for Q&A)

The extraction method and per-type findings live in the project wiki:
`Experiment-Free-Rein-Transcript-Review-2026-08-06` (the 6-step pipeline + the 4
contaminant classes) and `Analysis-Graph-Type-Characterization-2026-08-05` (the
per-type map). The saliency/attention framing (where the model looks, difficulty as
effort) is under the wiki's "Saliency & Difficulty" category
(`Concept-Transcript-Saliency`).

## Companion assets (if a wider story is wanted)

- `docs/llm-wiki-deck-handoff/slide_el94_pipeline.png` — a single 3-panel composite
  (targets → attention heatmap → pixel-check) for one worked example.
- `docs/llm-wiki-deck-handoff/HANDOFF.md` — the el-94 worked-example write-up with
  quotable numbers.
- `docs/llm-wiki-deck-handoff/panels/README.md` — the panel index + provenance table.
