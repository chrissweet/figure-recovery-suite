# AI saliency experiment — "find the turkeys" (IMG_7085.png, 3024×4032)

Behavioral saliency: where the model directed visual attention while searching for
turkeys, reconstructed from the search transcript and weighted by detection
confidence. This is NOT gradient/attention-weight saliency from a vision encoder;
it is a *behavioral* proxy (which regions the model chose to zoom into, and how
strongly each held attention for the "turkey" query).

## Transcript (attention trace)

1. **Coarse scan** — viewed the full downscaled image. The scene is a vegetated
   left/upper slope beside a paved drive; the lower ~60% is empty asphalt.
   Formed candidate regions: a turkey-shaped cluster on the upper slope, a clear
   foreground bird, and two dark/ambiguous shapes worth ruling out (a diagonal
   log, a moss patch on the asphalt).

2. **Zoom — foreground** (crop 280,1140–1100,2440): definitive turkey. Pale
   bluish head/neck, dark body, legs on the log. → **T1, conf 1.00**.

3. **Zoom — upper cluster** (crop 880,540–2340,1400): resolved to **three** birds:
   a head-down forager (left), a large body rump-toward-camera (center), and a
   hunched bird with a tan wing/tail patch (upper-right).
   → **T2 0.90, T3 0.90, T4 0.72** (T4 partly occluded, lower confidence).

4. **Zoom — decoy log** (crop 60,1940–720,2600): weathered wood grain, a fallen
   log. Not a bird. → ruled out, residual salience 0.35 (drew attention, no payoff).

5. **Decoy moss** (crop 1820,3640–2400,4010): moss/debris on asphalt, dismissed
   from the coarse view. → ruled out, salience 0.15.

## Result

**4 turkeys found.** Detections (original coords, x0,y0,x1,y1, confidence):

| id | box | conf | note |
|---|---|---|---|
| T1 | 362,1205,1002,2336 | 1.00 | foreground, clearest |
| T2 | 938,953,1260,1280 | 0.90 | head-down forager |
| T3 | 1610,781,2048,1125 | 0.90 | center, rump toward camera |
| T4 | 2019,566,2340,1013 | 0.72 | upper-right, partly occluded |
| log | 60,1940,720,2600 | — | decoy, ruled out (0.35) |
| moss | 1820,3640,2400,4010 | — | decoy, ruled out (0.15) |

## Heatmap construction

Each attended region contributes a Gaussian (σ ≈ 0.32 × box size) centered on the
region, weighted by its saliency score; summed, normalized, JET-colormapped, and
overlaid with **alpha proportional to saliency** so the empty asphalt (never
attended) stays clean rather than getting a flat color wash.

## Honest caveats

- **Behavioral, not internal.** This visualizes where the model *chose to look* and
  how confident it was, not encoder gradients. A true saliency map would need
  model-internal signals we don't have here.
- **Somewhat self-fulfilling.** Heat sits where turkeys were found; the informative
  parts are the *decoys* (attention spent, ruled out) and the *cold* asphalt
  (majority of the image, never attended).
- **Coordinates are hand-refined** from the zoom crops (a few % slop on boxes).
- Same method as the chart attention maps
  (`Analysis-Attention-Map-Visualization-2026-08-12`), applied to a natural photo.

## Artifacts
- `saliency_heatmap.png` — the overlay
- `attention_boxes.png` — the 4 turkey detections + 2 ruled-out decoys
- `crops/` — the zoom crops that constitute the attention trace
