# legacy_v1 — the original extractor code (provenance archive)

This directory captures the **actual code that produced** the initial extraction results at `extractors/graph-data-extraction/results/aedes-aegypti-2014/` (passes 1 through 3, June 2026). The work happened in an interactive Claude Code session with a lot of inline `python3 <<'EOF' ... EOF` heredocs that ran once and were never saved. These files are the post-hoc reconstruction of those heredocs as standalone scripts.

> **Legacy.** Not the canonical extractor going forward. The current canonical implementation is the Claude Code skill at `.claude/skills/graph-data-extraction/` (project-local), with the upstream source at [`chrissweet/AI_skills/skills/graph-data-extraction/`](https://github.com/chrissweet/AI_skills/tree/main/skills/graph-data-extraction). Active research uses the skill plus `scoring/score.py` at the repo root. The skill's helper scripts are general-purpose; the scripts here are aedes-corpus-specific.

## Why preserve this

Reproducibility. Five things came out of these scripts that the rest of the project depends on:

1. `extractors/graph-data-extraction/results/aedes-aegypti-2014/<chart>/data.csv` — the original 8-chart extraction (TP=220 / FN=31 / FP=19, F1=0.898 in `docs/aedes-2014_eval_r3.pdf`).
2. `extractors/graph-data-extraction/results/aedes-aegypti-2014/<chart>/calibration.json` — schema v1.0 calibration with `plot_frame_box.offset`, `pixels_per_coordinate_unit`, `data_to_pixel_formula`, `worked_example`.
3. `extractors/graph-data-extraction/results/aedes-aegypti-2014/set_calibration.json` — set-wide aggregate.
4. `extractors/graph-data-extraction/results/aedes-aegypti-2014/<chart>/replot.png` — Phase-4 reconstructions used by the audit workflow.
5. `extractors/graph-data-extraction/results/aedes-aegypti-2014/<chart>/plot_frame_crop.png` + overlays — visual verification of the calibration.

Without these scripts saved somewhere, re-running the same experiment would require reading the conversation log and re-typing the heredocs. With them saved here, `python3 extract_all.py && python3 compute_calibration.py && python3 build_set_calibration.py && python3 crop_plot_frames.py && python3 score_vs_groundtruth.py` reproduces the v1 results from `corpora/aedes-aegypti-2014/` alone.

## Files

| script | what it does | inputs | outputs |
|---|---|---|---|
| `extract_all.py` | runs all 8 chart-specific extractors end-to-end (the original `run_all.py` from the session). Each chart has its own function with hand-tuned HSV ranges, erosion kernels, mask exclusions, and calibration formulas. The chart-type recipes (§3a marker-on-line, §2b grayscale-shape, §3b fit-curve subtraction, §4a bar-via-outline, §4b error caps) are all here, inlined per chart. | `corpora/aedes-aegypti-2014/charts/<id>/image.png` | `extractors/.../<id>/data.csv`, `replot.png`, `run3_meta.json` |
| `compute_calibration.py` | per-chart `calibration.json` (schema v1.0). Detects plot frame from y-axis line (longest dark vertical), x-axis line (longest dark horizontal), top/right from non-white bbox inside the L-quadrant with legend rect excluded. Includes a worked example per chart. | per-chart image + the hand-coded calibration constants near the top of the file | `extractors/.../<id>/calibration.json` |
| `build_set_calibration.py` | aggregates the 8 per-chart `calibration.json` files into a single `set_calibration.json` with `summary_table` + `charts` dict keyed by id. Adds chart titles from `metadata.json`. | per-chart `calibration.json` | `extractors/.../set_calibration.json` |
| `crop_plot_frames.py` | for each chart, crops `image.png` to `plot_frame_box` (and `data_extent_box` if present) and emits an overlay showing both boxes drawn on the source. Used to visually verify the calibration. | per-chart `image.png` + `calibration.json` | `plot_frame_crop.png`, `plot_frame_overlay.png`, `coordinate_box_crop.png`, `coordinate_box_overlay.png` |
| `score_vs_groundtruth.py` | greedy nearest-neighbor matching of extracted points vs ground truth with per-axis tolerances; per-series TP/FN/FP, corpus P/R/F1/Jaccard, matched-pair distance distribution. Handles series-label special cases (el-60-b Series 1/2/3, el-75 pooled, el-94/el-100 fit-curve exclusions). | per-chart `data.csv` + `ground_truth.csv` | `extractors/.../scoring_legacy_v1.json` |
| `audit_replot_workflow.js` | the JS Workflow script that fanned out 8 per-chart audit agents (one per chart). Each agent read `image.png` + `replot.png` + the CSVs and produced a structured judgment of whether the replot visually matches the source, what mismatches exist, and what refinements would close them. Output bundled and saved as `docs/audits/phase4-audit-2026-06-18.json`. | per-chart `image.png` + `replot.png` + `data.csv` + `ground_truth.csv` | `docs/audits/phase4-audit-2026-06-18.json` (the audit findings driving `TODOS.md`) |

## How to re-run

From the repo root:

```bash
cd /Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite
pip install opencv-python-headless numpy matplotlib scikit-learn

python3 extractors/legacy_v1/code/extract_all.py
python3 extractors/legacy_v1/code/compute_calibration.py
python3 extractors/legacy_v1/code/build_set_calibration.py
python3 extractors/legacy_v1/code/crop_plot_frames.py
python3 extractors/legacy_v1/code/score_vs_groundtruth.py
```

Each script's `BASE` constant points at the absolute repo path; edit if you move the repo. Output paths are wired to write into `extractors/graph-data-extraction/results/aedes-aegypti-2014/` so re-running overwrites that directory in place. To compare against the audit baseline, copy `extractors/graph-data-extraction/results/aedes-aegypti-2014/` aside first.

The audit workflow (`audit_replot_workflow.js`) is not directly executable — it's the Workflow tool script that Claude Code ran. It's preserved here for documentation only; re-running it requires invoking the Workflow tool through Claude Code (the script will load from `scriptPath`).

## What's NOT in legacy_v1

- The Claude Code skill itself (`.claude/skills/graph-data-extraction/`) — that's the canonical, project-independent version of the same recipes, with general-purpose helper scripts (`calibrate.py`, `extract_markers.py`, `subtract_curves.py`, `write_calibration.py`, `check_artifacts.py`) and detailed methodology docs (`METHODOLOGY.md`, `references/*.md`). Treat the skill as the playbook; `extract_all.py` here is a transcript of one game.
- The canonical scorer at `scoring/score.py` — it generalizes `score_vs_groundtruth.py` to any (corpus, extractor) pair, accepts a `--tolerances` file, and writes to `extractors/<name>/results/<corpus>/scoring.json`. The legacy copy is hard-coded to aedes and writes a `_legacy_v1.json` suffix so it can't collide with the canonical scorer's output.
- The Phase-4 gating script (`scoring/phase4_check.py`) and the v2 follow-up extractor outputs (`extractors/graph-data-extraction/results-v2/...`) — those came after legacy v1.

## Provenance

- Original session: Claude Code, June 17-18 2026, in `paper-atomizer-eval/chart-extraction/charts/` (cwd at the time).
- Snapshot directory: `paper-atomizer-eval/chart-extraction/charts/` still exists as the pre-move baseline.
- Audit that judged this code's outputs: [Phase-4-Audit-2026-06-18](../../../wiki/figure-recovery-suite.wiki/Phase-4-Audit-2026-06-18.md). 3 of 8 charts read as visually faithful; 5 of 8 had severity-high mismatches (the basis for `TODOS.md`).
- Iteration history (pass 1 → v1→v2 → pass 2 → v2→v3 → pass 3) documented in `docs/aedes-2014_full_report.pdf`.
