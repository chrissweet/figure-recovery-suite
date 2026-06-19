# synthetic-r4-1 — synthetic-chart stress corpus

A small (10-chart, but starting with 2) synthetic corpus generated with
matplotlib. The point: each chart isolates **one methodology stress point**
of the extractor / scorer / verifier — log axes, dual axes, stacked bars,
non-default palette, etc. Because we generate the data and plot it
ourselves, **ground truth is exact**.

Per chart, the generator script writes four files under `charts/<id>/`:

  - `image.png` — the rendered chart
  - `ground_truth.csv` — the layered GT (Scatter Plot / Line Graph / Spline
    Chart / Grouped Column Chart rows) with `layer_idx, layer_type, series,
    x, y` columns
  - `ground_truth_calibration.json` — exact pixel ↔ data mapping derived
    from matplotlib's `ax.transData`. Records `scale: "linear" | "log10"`
    per axis so the recipe knows when to use the log-axis variant
  - `metadata.json` — chart type, palette, what feature the chart stresses

The generators are committed alongside the outputs so regenerating is a
matter of running `python3 generators/<id>_*.py`. Outputs are deterministic
(seeded random).

## Charts in the corpus

| # | id | feature stressed |
|---|---|---|
| 01 | linear-scatter         | baseline / harness sanity |
| 04 | log-y-line             | log axes (recipes are linear-only) |

Charts 2-3, 5-10 to come — added one at a time as the harness shape settles.

## How to regenerate

```bash
cd corpora/synthetic-r4-1
python3 generators/01_linear_scatter.py
python3 generators/04_log_y_line.py
```

Each generator overwrites the chart's directory under `charts/`.

## Why synthetic

- **Exact GT**: no annotation error.
- **One feature per chart**: when something breaks we know what.
- **Reproducible**: seeded random, generator scripts version-controlled.
- **Cheap to extend**: add a new generator, the harness picks it up.

The tradeoff vs. real-world charts is that matplotlib renders too cleanly —
real charts have aesthetic quirks (anti-aliasing variants, mixed-color
backgrounds, embedded raster artefacts) the synthetic versions skip. A
future `synthetic-r4-1-excel/` corpus could mirror this structure with
Excel-style rendering if matplotlib turns out too easy.
