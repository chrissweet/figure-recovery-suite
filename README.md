# figure-recovery-suite

A benchmark and evaluation harness for recovering numeric data from figures in scientific papers — charts today, schematics and tables as the corpus grows. Each test figure ships with ground-truth coordinates, a pixel-frame calibration, and a worked example so downstream consumers can verify the math against the image. Extraction methods plug in as subdirectories and are scored against ground truth with one consistent rubric (TP/FN/FP within per-axis tolerance, plus Precision / Recall / F1 / Jaccard at the corpus level), so vision pipelines, learned models, MLLM-based methods, and human annotations can be compared apples-to-apples on the same data.

## Layout

```
figure-recovery-suite/
├── corpora/
│   └── <corpus-id>/
│       ├── README.md                       # provenance, license, version
│       └── charts/
│           └── <chart-id>/
│               ├── image.png               # the figure (input)
│               ├── ground_truth.csv        # ground-truth data points
│               ├── ground_truth_calibration.json   # ground-truth axis/frame info
│               └── metadata.json
├── extractors/
│   └── <extractor-name>/
│       └── results/
│           └── <corpus-id>/
│               ├── <chart-id>/
│               │   ├── data.csv            # this extractor's output
│               │   ├── calibration.json    # this extractor's calibration
│               │   ├── replot.png          # Phase-4 visual verification
│               │   └── ...
│               ├── set_calibration.json    # corpus-wide bundle
│               └── scoring.json            # scored against ground truth
├── scoring/
│   └── score.py                            # the scoring rubric, one script
├── docs/
│   └── *.pdf                               # per-extractor reports
├── .claude/
│   └── skills/
│       └── graph-data-extraction/          # project-local skill install
└── README.md
```

## Current contents

- **`corpora/aedes-aegypti-2014/`** — 8-chart corpus from a paper on *Aedes aegypti* parity and longevity. Ground-truth `data.csv` and `calibration.json` per chart, produced by an upstream extraction tool. See [`corpora/aedes-aegypti-2014/README.md`](corpora/aedes-aegypti-2014/README.md).
- **`extractors/graph-data-extraction/results/aedes-aegypti-2014/`** — first extractor: the `graph-data-extraction` Claude Code skill, run blind on the corpus (no use of the ground-truth files). Per-chart `data.csv` + `replot.png` + `calibration.json` (with new schema: `plot_frame_box.offset`, `pixels_per_coordinate_unit`, `data_to_pixel_formula`, `worked_example`). Set-wide bundle in `set_calibration.json`. Scoring at `scoring.json`.
- **`docs/aedes-2014_eval_r3.pdf`** — 9-page evaluation report (scoring rubric + per-chart breakdown).
- **`docs/aedes-2014_full_report.pdf`** — 11-page comprehensive report (iteration history, methodology, per-chart results, limits).
- **`.claude/skills/graph-data-extraction/`** — the skill installed project-locally so Claude Code picks it up automatically when invoked from inside this repo.

## Headline result

`graph-data-extraction` skill on `aedes-aegypti-2014` corpus:

```
Precision = 0.921
Recall    = 0.876
F1        = 0.898
```

across 251 ground-truth points and 239 predicted points. Five of eight charts perfect (F1 = 1.00); the other three hit four documented failure modes called out plainly in the skill's `METHODOLOGY.md`.

## Adding a new extractor

1. Create `extractors/<name>/results/<corpus>/<chart-id>/` for each chart with at minimum `data.csv` (one row per extracted point) and `calibration.json` (image_size + plot_frame_box + axis_calibration; the schema documented in `.claude/skills/graph-data-extraction/SKILL.md` Phase 5).
2. Run `python3 scoring/score.py <corpus> <extractor>` to produce `extractors/<name>/results/<corpus>/scoring.json`.
3. Drop a one-page report into `docs/` describing the method and headline numbers.

## Adding a new corpus

1. Create `corpora/<corpus-id>/charts/<chart-id>/` with `image.png`, `ground_truth.csv`, `ground_truth_calibration.json`, and `metadata.json`.
2. Write `corpora/<corpus-id>/README.md` documenting provenance, license, and any chart-type notes.
3. The `scoring/score.py` script accepts the corpus id and works against any corpus that follows this layout.

---

## This repository uses LLM wiki memory

figure-recovery-suite keeps a persistent, LLM-maintained knowledge base under `wiki/figure-recovery-suite.wiki/` (a separate git repo), following the [llm-wiki pattern](https://github.com/tobi/llm-wiki). It is the project's durable memory: findings, decisions, experiment results, and intermediate insights belong in the wiki and accumulate over time. Three operations, **Query** (read it), **Ingest** (write to it), and **Lint** (health-check it), are codified in `CLAUDE.md`, in `wiki/figure-recovery-suite.wiki/SCHEMA_figure-recovery-suite.md`, and in the `.claude/commands/` slash commands (`/wiki-source`, `/wiki-experiment`, `/wiki-lint`).

See also [llm-wiki.md](llm-wiki.md) in this repo for the underlying pattern.

## Quick start for collaborators

New to figure-recovery-suite? Clone the project repo, clone the wiki as a sibling sub-repo, then seed your local Claude Code memory:

```bash
git clone https://github.com/chrissweet/figure-recovery-suite.git
cd figure-recovery-suite
git clone https://github.com/chrissweet/figure-recovery-suite.wiki.git wiki/figure-recovery-suite.wiki
./wiki/agents/claude-code/setup.sh --seed-memory
```

After this, open Claude Code inside the repo. It will automatically pick up the project's slash commands (`/wiki-source` to ingest an external document, `/wiki-experiment` to file experiment results, `/wiki-lint` to health-check the wiki) along with the read/write/commit conventions in `CLAUDE.md`.

The wiki at `wiki/figure-recovery-suite.wiki/` is a separate git repo with its own history and its own remote. After any wiki edit, commit in the wiki repo (not the project repo):

```bash
git -C wiki/figure-recovery-suite.wiki add <files>
git -C wiki/figure-recovery-suite.wiki commit -m "..."
```

Push the wiki only when you intend to publish the changes:

```bash
git -C wiki/figure-recovery-suite.wiki push origin master
```

## About the template

This project was instantiated from [crcresearch/llm-wiki-memory-template](https://github.com/crcresearch/llm-wiki-memory-template). Maintainers who need to pull template updates, add a new agent overlay (Cursor, OpenCode, etc.), or understand the instantiate/update scripts should read the template repo's documentation.
