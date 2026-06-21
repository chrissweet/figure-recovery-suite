# Research notes — feedback-loop extractor on aedes el-100

**Goal of this run:** produce a defensible answer to "is per-series IoU a usable convergence signal without GT?" on one chart, before extending to more.

**Chart:** `aedes-aegypti-2014/el-100` — 3 colored scatter series (24C blue circles, 27C green squares, 30C red diamonds) + 3 fit lines in the SAME 3 colors (IF_24C dashed blue, IF_27C solid green, IF_30C dotted red). This chart was deliberately chosen because it's the v3 corpus chart with the worst known marker errors (18 FP markers from line fragments).

**Bootstrap:** v3 extractor's `data.csv` for el-100 (251 rows: ~57 markers across 3 scatter series + ~194 line samples across 3 line series).

**Stopping condition:** mean per-series IoU ≥ 0.85 AND no new proposals AND no drops. `MAX_ITERATIONS = 4`.

## What happened

| iter | claims | mean_iou | 24C IoU | 27C IoU | 30C IoU | proposals | drops |
|------|--------|----------|---------|---------|---------|-----------|-------|
| 0    | 251    | 0.221    | 0.255   | 0.000   | 0.409   | 52        | 14    |
| 1    | 289    | 0.143    | 0.200   | 0.000   | 0.230   | 31        | 2     |
| 2    | 318    | 0.153    | 0.205   | 0.000   | 0.255   | 21        | 4     |
| 3    | 335    | 0.139    | 0.175   | 0.000   | 0.241   | 14        | 0     |

**Loop diverged.** Mean IoU started at 0.22 and got *worse* across iterations, ending at 0.14. The Predicate-A proposals were actively hurting accuracy, not fixing gaps. Convergence floor (0.85) was never approached.

## Side-by-side

`side_by_side.png` shows the final iteration's data layer vs source. Visible failure modes:

- **Long zig-zag of blue circles along the IF_24C dashed line.** Predicate A flagged every blue line-fragment as a "missing 24C marker" because 24C and IF_24C share the color `#0000FF`. The loop dutifully added them as 24C markers. The replot now has a snake of extra blue dots where the dashed line should be.
- **Same pattern for red along IF_30C.** Extra red diamonds along the dotted red fit line.
- **Green completely absent from the replot.** The 27C green series is invisible because the source's actual rendered green doesn't match `#00FF00` even within the ±80 wide-search tolerance auto-tune uses to find the legend swatch. The loop ran the entire time with `27C: IoU = 0.000`.

## Research questions, answered with evidence

### Q1 — Is per-series IoU a usable convergence signal without GT?

**On el-100, no.** It diverged. Two compounding reasons made it useless as a convergence signal on this chart:

- **The signal mis-attributed claims to the wrong series** (the shared-color problem; see Q4)
- **One series got IoU = 0 throughout** because the legend-swatch auto-tune couldn't find the green swatch, leaving the 27C / IF_27C IoU pinned at 0 (which dragged the mean down and gave the loop no actionable signal for green)

**This is not "the methodology doesn't work."** It's "on a chart where per-series color masks decompose ambiguously AND where one series' actual rendered color is far from its nominal hex, the IoU signal is the wrong primitive to drive iteration." A different chart (one with unique colors per series, all close to legend nominal) might work.

### Q2 — What's the practical IoU floor?

**Couldn't measure on el-100.** The loop never approached the IOU_FLOOR = 0.85. Even iteration 0's bootstrap (which is v3's known-good-ish extraction) was at mean IoU = 0.22. That's a stronger signal than I expected before the run: even a reasonable extraction lands at 0.22 IoU on a chart where colors are shared and rendered green ≠ nominal green. The 0.85 floor was wishful; calibration of this number requires a chart where ALL the necessary preconditions for per-series IoU are met.

### Q3 — Where does the loop converge falsely?

**Did not converge at all.** No false convergence to study. The HONEST behavior — diverging, not silently converging on a wrong answer — is mildly reassuring: the loop is detecting that something is wrong, even if it can't fix it. The `convergence_history.json` records `convergence_reason: "max_iter_hit"` cleanly.

### Q4 — Are there charts where per-series color masks fundamentally don't work?

**Yes, this chart. Confirmed empirically.** 24C and IF_24C both hex `#0000FF`. The per-series color mask is the same boolean array for both. The loop can't tell which blue pixel belongs to a marker vs to the fit-line. Predicate A's proposals are uniformly mis-attributed.

**The "fallback signal" question is the open follow-up.** Possible directions, none implemented:

- **Shape gate at proposal time** — before adding an Unclaimed-Component as a 24C marker, check that its aspect ratio + density match a circle (not a line fragment). This is essentially folding Predicate B into Predicate A's proposal step.
- **Topology gate** — markers are isolated blobs; line fragments are connected along the line's trajectory. Could classify by connectivity to a previously-traced line.
- **Tie-break by layer presence** — if a series already has a Line Graph row at the candidate's column, attribute candidate to the line; only attribute to the marker series if no line claim is nearby.
- **Use marker shape** — for 24C, shape is `filled circle`; for IF_24C, no shape (it's a line). The renderer already uses this. The negative-space predicate could too: when proposing a new claim, require its local shape to match the series' declared marker shape.

The last is probably the most direct and the right next step.

### Q5 — Does pixel-precise rendering close the diagnostic gap vs matplotlib?

**Partial yes, with a different gap surfaced.** The pixel renderer eliminated the autolayout / chrome-positioning class of bugs entirely (no axis label disputes, no plot frame mismatch, no font issues). What we got instead was a clean signal about the per-series color decomposition problem — which is more useful because it's pointing at a real methodological issue with the loop's primary signal, not at a render artifact. So the pixel renderer is doing its job: it's letting the comparison signal reflect *extraction* problems, not render problems.

## Practical honest assessment

The loop, as currently implemented, **is not yet a useful convergence test** on el-100. The reasons are specific:

1. **Predicate A's proposal step is too crude** — it proposes any unclaimed same-color component as a marker for that color's first series. Needs shape gate AND/OR layer-aware tie-breaking before it can be trusted.
2. **Color-tolerance auto-tune fails on el-100's green** — even ±80 wide-search doesn't find the swatch. Needs HSV-based legend swatch detection rather than BGR-distance from nominal.
3. **The IoU signal is meaningful only when per-series colors are distinguishable** — el-100 is the wrong chart to expect convergence on without first fixing (1).

The architecture itself (extract → pixel-replot → compare → iterate, no GT) is sound. The pixel renderer is a clear win over the matplotlib approach (made all chrome arguments moot). But for this loop to actually IMPROVE extractions, the proposal mechanism needs to be smarter than "any unclaimed same-color blob = a marker."

## Recommended next investigation (not run)

Pick a chart from `synthetic-r4-1` where every series has a unique color AND the rendered colors match their nominal hex tightly (matplotlib defaults). Candidates: `01-linear-scatter` (3 default-palette colors), `06-scatter-asym-errbars` (1 series, no ambiguity), `09-open-markers-with-fit` (open markers, possibly easier shape gate). Run the same loop. Compare convergence behavior.

If the loop converges on synthetic-r4-1 charts with unique colors, that's evidence the methodology works WHEN per-series color masks are clean. The next research question is then: how do we handle real-world charts where they aren't?

## Files in this directory

- `iterations/<n>/data.csv` — claim set at iteration n
- `iterations/<n>/replot_data_layer.png` — pixel-replot of iteration n's data
- `iterations/<n>/per_series_iou.json` — per-series IoU at iteration n
- `iterations/<n>/negative_space_report.json` — Predicate A output
- `iterations/<n>/glyph_discriminator_report.json` — Predicate B output
- `convergence_history.json` — per-iteration summary
- `side_by_side.png` — source vs final replot
- `data.csv` / `calibration.json` / `chart_metadata.json` / `replot.png` — canonical deliverables (copy of final iteration)
- this file

## STOP

Stopping after this run per plan; user inspection requested before extending.
