# Extraction recipes by chart type

Each recipe assumes you have completed calibration: a frame (`left,right,top,bot`), and `col2x`/`row2y` mapping functions. Build color masks in HSV — it separates hue from lighting far better than RGB.

## Quick chooser

| Chart looks like | Use recipe |
|---|---|
| pure scatter, one color per series | §2 Scatter |
| smooth lines/curves, no discrete markers | §3 Line / curve |
| line plot with markers AT integer x values (the line just connects them) | §3a Marker-on-line — extract the markers, then emit the line layer as the markers in x-order |
| line plot with three colored series + dashed/dotted fit lines in same colors | §3a + hazards §6.6 |
| scatter where a smooth fit curve passes through the markers in the same color | §3b Subtract the curve first, then extract |
| scatter with x or y error bars (whiskers + caps) | §2 + §2a Error bars |
| solid-color grouped bar chart | §4 Bar chart |
| grouped bar chart where one fill is dotted/stippled (CC won't see it as one blob) | §4a Bar via outline |
| three series distinguished by marker SHAPE only (no color) — filled circle, gray square, open diamond | §2b Grayscale-shape scatter |
| histogram | §5 Histogram |

## Table of contents
1. Color masks (matplotlib defaults)
2. Scatter plot
   - 2a. Error bars (x and/or y)
   - 2b. Grayscale-shape scatter (no color cue)
3. Line / curve plot
   - 3a. Marker-on-line (extract markers only)
   - 3b. Subtracting a fit curve before extracting markers
4. Bar chart
   - 4a. Bar via outline (stippled/dotted fills)
   - 4b. Error-bar caps on bar charts
5. Histogram
6. Hazards (read this — it is where extractions go wrong)

## 1. Color masks

HSV ranges covering both matplotlib defaults and **pure-primary palettes** (Excel-style charts where a colored series is drawn as straight `BGR(255, 0, 0)` etc.). The `V_max=255` ceiling is required: a tighter cap silently drops pure-primary pixels because their HSV value is exactly 255.

```python
import cv2, numpy as np
def masks(hsv):
    return {
      # V_max held at 255 so pure-primary palettes (BGR(255,0,0) → HSV(120,255,255))
      # aren't silently dropped. Matplotlib's muted defaults (e.g. C0 #1f77b4
      # has V≈180) sit well below the cap and are unaffected.
      'C0_blue'  : cv2.inRange(hsv, np.array([100, 90, 60]), np.array([125,255,255])),
      'C1_orange': cv2.inRange(hsv, np.array([  8, 90, 90]), np.array([ 22,255,255])),
      'C2_green' : cv2.inRange(hsv, np.array([ 35, 60, 60]), np.array([ 85,255,255])),
      'C3_red'   : cv2.inRange(hsv, np.array([  0,100, 80]), np.array([ 10,255,255])),  # also 170-180
    }
```
Map each mask to its series by reading the legend off the `view`ed image. Raise the saturation floor (the middle number) if pale gridlines of the same hue leak into the mask.

**Pure-primary failure mode** (added 2026-06-19 after el-60-a TDD pass): a `V_max < 255` cap (the previous default was 240 for blue, 235 for green) returns *zero* pixels for an Excel-style chart whose markers are drawn as full-intensity primaries. The mask appears to "work" — `inRange` doesn't error — but every series CC is empty, and the rest of the pipeline silently produces an empty `data.csv`. If the marker count drops to 0 unexpectedly, sample a known marker pixel (`img[row,col]`) before tuning the recipe further: if it returns `BGR(255,0,0)` or similar pure primary, raise the V ceiling.

## 2. Scatter plot

Threshold markers, find connected components, take centroids. Split merged blobs; drop off-panel noise.

```python
mask = cv2.inRange(hsv, np.array([100,80,40]), np.array([135,255,220]))   # marker color
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2,2),np.uint8))    # despeckle
n, labels, stats, cent = cv2.connectedComponentsWithStats(mask, 8)

areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1,n) if stats[i,cv2.CC_STAT_AREA] >= 15]
single = int(np.median(areas))   # area of one marker

pts = []
for i in range(1, n):
    a = stats[i, cv2.CC_STAT_AREA]
    if a < 15: continue                 # noise
    k = max(1, round(a / single))       # how many markers merged here
    if k == 1:
        pts.append(cent[i])
    else:                                # split overlapping markers
        ys, xs = np.where(labels == i)
        Z = np.float32(np.column_stack([xs, ys]))
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, _, centers = cv2.kmeans(Z, k, None, crit, 5, cv2.KMEANS_PP_CENTERS)
        pts.extend(centers)

data = []
for x, y in pts:
    bx, by = col2x(x), row2y(y)
    if left <= x <= right and top <= y <= bot:   # in-panel only; drop trend-line/legend hits
        data.append((round(bx,2), round(by,2)))
data.sort()
```
Filtering to in-panel and to plausible value ranges is essential: a dark-red regression line or a legend swatch can otherwise be misread as markers and produce impossible points (e.g. y above the axis maximum).

## 2a. Error bars (x and/or y) on scatter markers

Error bars are thin black/colored arms with a horizontal/vertical cap at each end. The vertical arm passes *through* the marker, but the marker fill hides the segment under the disk — so a naive contiguous-black walk from the marker centroid finds only the next black pixel *outside* the disk and then stops at the marker boundary.

Trick: walk outward from the centroid, but **allow a gap roughly the marker diameter** before declaring the arm ended. The gap absorbs the marker disk; once past it, you re-encounter the error-bar arm and walk all the way to the cap.

```python
def walk_with_gap(strip, c0, direction, gap_allowance):
    pos = c0; last = c0
    while True:
        found = None
        for d in range(1, gap_allowance + 1):
            p = pos + direction * d
            if p < 0 or p >= len(strip): break
            if strip[p] > 0:
                found = p; break
        if found is None: break
        pos = found; last = pos
    return last

# vertical (y) error bar: walk up and down from the marker centroid in a
# narrow column strip. Use ±3 cols, NOT ±1 — the error-bar arm is often
# offset by 1-2 px from the visual marker centroid.
cxi, cyi = int(cx), int(cy)
col_strip = black[:, max(0,cxi-3):cxi+4].max(axis=1)
gap = int(marker_diameter) + 5
y_hi_row = walk_with_gap(col_strip, cyi, -1, gap)
y_lo_row = walk_with_gap(col_strip, cyi, +1, gap)

# horizontal (x) error bar: same pattern transposed
row_strip = black[max(0,cyi-3):cyi+4, :].max(axis=0)
x_lo = walk_with_gap(row_strip, cxi, -1, gap)
x_hi = walk_with_gap(row_strip, cxi, +1, gap)
```

If two error-bar arms are close together (markers near each other), constrain the walk to stop when entering another marker's bounding box — otherwise the horizontal scan can capture a neighbor's vertical arm and report an absurdly wide x-error.

For error bars whose lower half is occluded by the bar fill in a bar chart, see §4b.

## 2b. Grayscale-shape scatter (no color cue)

Series distinguished only by marker shape. The classifier discriminates by CC area and density on the black-pixel mask. The legend usually shows three shape glyphs — *filled black disk*, *filled gray square*, *outlined diamond* — but the actual chart-area rendering of "diamond" varies by chart family.

**Pixel-probe discipline (mandatory, added 2026-06-19, generalised after el-94 TDD pass):** before tuning any threshold for a grayscale-shape chart, sample the actual pixel content at one known marker position and read off the gray values. Two charts in the same corpus may render "diamond" differently:

| chart | 30 °C marker rendering | source pixel values |
|---|---|---|
| el-88 | thin black outline around a **light-gray fill** | outline gray ≈ 25-75, interior gray ≈ 205-230 |
| el-94 | thin black outline around a **white interior** (truly "open") | outline gray ≈ 25-75, interior gray ≈ 255 |

Same legend symbol (◇), two different pixel realities. The CC-density classifier on the black mask works for either case because the outline density is similar (≈ 0.3), but threshold tuning for the *interior* (`mid = (gray >= 60) & (gray <= 210)`) succeeds on el-88 and fails on el-94. Pixel-probe first; assume nothing from the legend symbol.

```python
# Probe one marker by computing its predicted pixel from data.csv, then read.
import cv2
img = cv2.imread('image.png')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# data row: 30°C at (40, 0.15), calibration col=662 row=488
print(gray[481:495, 655:669])    # 14x14 around the marker
```

If the interior pixel is white (≥230) you have a hollow diamond; if it's light gray (~200-230) you have a filled diamond; in either case the CC-density classifier handles it but the `mid` mask thresholds need to match.

```python
# 24°C: solid black disk (gray < 50), area ~80 after no erosion
black = ((gray < 50) & (hsv[:,:,1] < 50)).astype(np.uint8)*255 * mask_area
# 27°C: solid gray square (gray 60-210)
mid = ((gray >= 60) & (gray <= 210) & (hsv[:,:,1] < 50)).astype(np.uint8)*255 * mask_area
mid[black > 0] = 0   # exclude the disks already claimed

n, labels, stats, cent = cv2.connectedComponentsWithStats(mid, 8)
sq_pts, dia_pts = [], []
for i in range(1, n):
    x,y,w,h,a = stats[i]
    if not (5 <= w <= 25 and 5 <= h <= 25): continue
    density = a / (w*h)
    if density > 0.55 and a > 30:        # solid fill -> square
        sq_pts.append(cent[i])
    elif 0.15 < density < 0.5 and 10 < a < 90:   # outline only -> open diamond
        dia_pts.append(cent[i])
```

Tunables: the density cutoff (~0.5) is the key knob. Filled markers come in at density 0.6-0.9; pure outlines (open diamond, open square) at 0.2-0.4; dashed-line fragments at <0.3 and irregular bbox. If the open-marker series gets undercounted, lower the density floor; if filled markers leak into the "open" bucket, raise it. **This recipe is fragile** — expect ~70-90 % accuracy, not the ~100 % of color-coded scatter. Note that explicitly in the caveats.

## 3. Line / curve plot

One mask per series; per x-column take the median row of that color; resample to a regular grid.

```python
def trace(mask, x0, x1, top, bot):
    pts = []
    for c in range(x0+3, x1-2):
        rr = np.where(mask[top:bot, c] > 0)[0]
        if len(rr) > 0:
            r = top + int(np.median(rr))     # median handles line thickness + small overlaps
            pts.append((col2x(c), row2y(r)))
    return pts

def resample(pts, xmax, step):
    pts = sorted(pts)
    xs = np.array([p[0] for p in pts]); ys = np.array([p[1] for p in pts])
    out = []; x = 0.0
    while x <= xmax:
        sel = ys[(xs >= x-step/2) & (xs < x+step/2)]
        if len(sel): out.append((round(x,2), round(float(np.median(sel)),1)))
        x += step
    return out
```
Where two series overlap, the median row picks one of them per column — note in the caveats that overlapping segments are approximate. The legend will contaminate columns it covers; see Hazards.

### Curve-crossing failure (added 2026-06-19 after el-94 TDD pass)

Per-column-median is greedy and **fails at curve crossings**: when two same-color curves cross at column c, the column contains two thin runs at different rows and the median collapses both into the wrong y. The matched-frame overlay test on el-94 surfaced this directly — the 30 °C dotted curve trace was *clean* from x = 3 to x = 20 and then *chaotic* from x = 23 to x = 30, where it crosses the dashed 24 °C curve.

Fix: track each curve's row trajectory across columns and prefer the per-column run whose row best matches the trajectory's local slope, falling back to the median only when there is exactly one run.

```python
def trace_with_continuity(mask, x0, x1, top, bot, seed_rows):
    """Trace N curves simultaneously using row-continuity from seed_rows.
    seed_rows: list of starting (col, row) per curve at the leftmost column."""
    curves = [[(s[0], s[1])] for s in seed_rows]
    last_row = [s[1] for s in seed_rows]
    for c in range(x0 + 3, x1 - 2):
        rr = np.where(mask[top:bot, c] > 0)[0]
        if len(rr) == 0:
            continue
        # Cluster contiguous rows into runs; one centroid per run.
        runs = []
        cur = [rr[0]]
        for r in rr[1:]:
            if r == cur[-1] + 1:
                cur.append(r)
            else:
                runs.append(top + int(np.mean(cur))); cur = [r]
        runs.append(top + int(np.mean(cur)))
        # Assign each curve to the nearest available run.
        used = [False] * len(runs)
        for i, lr in enumerate(last_row):
            best, best_i = 999, None
            for j, run_row in enumerate(runs):
                if used[j]: continue
                d = abs(run_row - lr)
                if d < best:
                    best, best_i = d, j
            if best_i is not None and best < 20:
                used[best_i] = True
                curves[i].append((col2x(c), row2y(runs[best_i])))
                last_row[i] = runs[best_i]
    return curves
```

`seed_rows` come from the legend swatches (each line style's left endpoint sits next to its label) or from manual eyeballing of the leftmost column where each curve is unambiguous. The cost is one pass with O(N_curves × N_columns) attribution. The win is correct trajectory through crossings.

Validated on el-94 (2026-06-19): the per-column-median trace had visible chaos at x = 23-30; the trajectory-tracked version follows each curve smoothly through the crossing.

## 3b. Subtracting a fit curve before extracting markers

Charts often draw a smooth fit curve (regression line, model prediction) through the data points in the same color as the markers. The curve makes marker extraction painful:

- A **solid** curve fuses each marker into a long elongated CC (so the aspect-ratio filter from §3a rejects them, and you under-count markers).
- A **dashed** curve fragments into marker-sized chunks (so the aspect-ratio filter helps a little, but is fooled by chunks that happen to be near-square).
- A **dotted** curve drops square-ish dots that pass both aspect-ratio and density tests for "open marker" — you over-count diamonds/open shapes.

The robust fix is to remove curve pixels *before* CC classification. The trick that survives all three cases is **per-column thin-run subtraction with paired-edge preservation**:

```python
def column_runs(col):
    """Return list of (start_row, end_row) for contiguous nonzero runs in one column."""
    rows = np.where(col > 0)[0]
    if len(rows) == 0: return []
    runs, s, e = [], rows[0], rows[0]
    for r in rows[1:]:
        if r == e + 1: e = r
        else: runs.append((s, e)); s, e = r, r
    runs.append((s, e))
    return runs

def subtract_curves(mask, thin_h=3, marker_span=(4, 13)):
    """
    Subtract per-column runs of height <= thin_h UNLESS they pair with
    another thin run at a distance inside marker_span (suggesting the
    top + bottom edges of an open marker).
    """
    out = mask.copy()
    H, W = mask.shape
    lo, hi = marker_span
    for c in range(W):
        runs = column_runs(mask[:, c])
        for i, (s, e) in enumerate(runs):
            if e - s + 1 > thin_h:
                continue
            paired = False
            for j, (s2, e2) in enumerate(runs):
                if i == j or e2 - s2 + 1 > thin_h:
                    continue
                gap = max(s, s2) - min(e, e2)
                if lo <= gap <= hi:
                    paired = True; break
            if not paired:
                out[s:e+1, c] = 0
    return out
```

How it works:

- A **thin curve passing through a column** appears as one ≤ 3-px-tall run with no thin neighbor → subtracted.
- A **filled marker (square, disk)** has one tall run (height > thin_h) → never matched, preserved.
- An **open marker (diamond, hollow square)** has TWO thin runs (top edge and bottom edge) 5-12 px apart → paired, preserved.

Tunables:

- `thin_h`: 2-4 px. Match the line thickness in the figure. Too high and you start subtracting marker fill rows.
- `marker_span`: typical marker height in pixels, ±2 for tolerance. For 12-px markers use `(4, 13)`; for tiny 6-px markers use `(3, 7)`.

What it doesn't fix:

- **Filled markers sitting on a solid curve**: the marker CC fuses horizontally with the curve trace inside the marker's own column range, so even after the OUTSIDE-marker columns are subtracted, the CC remains elongated. The aspect-ratio filter then still rejects it. Workaround: relax the aspect filter to `> 3.5` AND require the CC to contain a roughly-square dense kernel by eroding it and checking that the residual is square. Expect to still under-count by ~20 % when this happens.
- **Curves whose thickness matches the open-marker stroke width**: a dotted curve where each dot is 2 px tall and dots are 4 px apart visually mimics a column of paired open-marker edges. The pair preservation will keep them. Filter the resulting marker pool against a smooth spline through the surviving CC centroids and drop CCs that lie within ε of the spline AND have density < 0.3.

### Filled-square markers fused with a same-color solid curve (added 2026-06-19, validated on el-94)

The previous "what it doesn't fix" item — filled markers on a solid same-color curve — has a working fix. Audit row 7's recommendation was *almost* right; the correction:

1. Build the gray mask `(60 ≤ gray ≤ 210) ∧ (sat < 50)`, panel-restricted, legend-excluded, with disk regions of *other* series subtracted (their dilated halo too, ~7 px radius).
2. **Vertical opening with a small kernel** (`np.ones((3, 1), np.uint8)`) — *vertical*, not horizontal as the audit said. The thin (1–2 px) anti-aliased gray bands above/below the solid same-color line erode away; the square interiors (4–6 px tall) keep their center row. The audit's `1×5` horizontal opening doesn't separate the two because both line and square are wide.
3. **2×2 dilation** restores the square footprint after the opening's erosion.
4. CC analysis with relaxed thresholds: density > 0.45, area 15–250, bbox 4–24 in either dim.
5. **Restrict to the y-band the series visually occupies** (read it from the matched-frame overlay or from the GT if available) — drops detections from axis tick text and frame-corner anti-aliasing.
6. **If the series is sampled at integer x values** (common for survival-curve charts), group by integer x and keep the highest-area detection per bin — eliminates the duplicate "split CC" artefacts the opening occasionally produces.

```python
mid = ((gray >= 60) & (gray <= 210) & (sat < 50)).astype(np.uint8) * 255
mid = cv2.bitwise_and(mid, panel)
# Subtract disks of other series so they don't claim gray pixels.
mid[other_series_disk_dilated > 0] = 0
# Vertical opening to remove thin line halos; dilate to restore square footprint.
mid = cv2.morphologyEx(mid, cv2.MORPH_OPEN, np.ones((3, 1), np.uint8))
mid = cv2.dilate(mid, np.ones((2, 2), np.uint8), iterations=1)
# CC + filter + integer-x bin
```

Validated on el-94 (2026-06-19): 27 °C series went from 14 detected (Recall = 0.56, the recipe's documented failure mode #1) to **25 detected** (matches the audit's expected truth count). Matched-frame overlay confirms every source gray square from x = 14 to x = 38 is now covered. Failure mode #1 closed.

Always check the result by saving the cleaned mask (`cv2.imwrite('cleaned.png', cleaned)`) and `view`ing it before continuing — you want to see whole markers preserved and curve fragments removed.

## 3a. Marker-on-line (extract markers only)

This is the common "line chart with circles/squares/diamonds at the data points" pattern. The line and the markers share a color, so a color mask catches both as one connected component. Don't bother peak-finding the column-thickness profile — sharp transitions in the line (steep rises) create false-positive peaks that look just like markers. Use erosion instead:

```python
# Mask the series color (line + markers together)
mask = cv2.inRange(hsv, lo, hi) * mask_area  # mask_area excludes legend
# Erode with a kernel slightly larger than the line thickness (~2 px lines -> 4-5 px kernel)
k = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
core = cv2.erode(mask, k)
# Marker cores survive; the thin connector line is wiped out.
n, labels, stats, cent = cv2.connectedComponentsWithStats(core, 8)

pts = []
for i in range(1, n):
    a = stats[i, cv2.CC_STAT_AREA]
    if a < 30: continue   # too small after erosion -> probably noise
    pts.append(cent[i])
pts.sort(key=lambda p: p[0])

# If markers are at integer-day or other regular x values, snap:
snapped = [(round(col2x(cx)), round(row2y(cy), 4)) for cx, cy in pts]
```

Kernel-size rule of thumb: erode by **2 px wider than the line**. Line is 2 px → kernel 4 or 5. Line is 3 px → kernel 5 or 6. Too small and the line survives between markers (CCs merge). Too large and the markers themselves vanish (marker disk is ~12 px, kernel 8 leaves only a 4-px core). Check `(core > 0).sum()` after each tweak.

**Legend exclusion is critical here** because the legend swatch is the same color as a series and survives erosion. Always wipe out the legend's bounding box on `mask_area` *before* the color mask. Better to over-exclude than have the legend swatch contribute a phantom marker.

### Emit the line layer too, do not discard it (added 2026-06-19)

The source's drawn line is data, not decoration: the chart's reader uses the line to follow trends across days where no marker was extracted. The §3a recipe historically said "extract the markers, ignore the line" — that drops a layer the audit later flagged as missing on every line-plot chart in the corpus.

The simple, validated fix: the source's line is point-to-point straight segments through the markers in x-order. Emit a `Line Graph` layer whose vertices are exactly the extracted markers, sorted by x within each series.

```python
# After collecting the per-series snapped markers above:
import csv
with open('data.csv','w',newline='') as f:
    w = csv.writer(f)
    w.writerow(['layer_idx','layer_type','series','x','y'])
    for series, points in markers_by_series.items():
        # Layer 0: scatter markers (what the recipe already emits)
        for x, y in points:
            w.writerow([0, 'Scatter Plot', series, x, y])
        # Layer 1: line connecting them in x-order (new)
        for x, y in sorted(points):
            w.writerow([1, 'Line Graph', series, x, y])
```

The line-equals-markers-in-x-order claim is *testable* under the matched-frame TDD pass: render the line, overlay on the source, and check that the colored line coincides with the source's colored line at every segment. If the source's line bends through a point you did not extract, the marker-detection step missed a marker — fix that, then re-emit. (Validated on el-60-a 2026-06-19: 3 series, all sparse segments coincide.)

If the source clearly draws a *spline* through the markers (curved between integer x), §3a is the wrong recipe — switch to §3 line-trace.

## 4. Bar chart

For each bar, find the top of its colored column; convert to value. Identify bars by scanning for contiguous colored x-bands, or by the known category tick centers.

```python
def bar_top_value(mask, c0, c1, top, bot):
    seg = mask[top:bot, c0:c1]
    rows = np.where(seg.any(axis=1))[0]
    if len(rows) == 0: return None
    return row2y(top + rows.min())      # min row = visual top of bar
```
For negative bars (baseline not at the frame bottom), compute the baseline pixel from `row2y`-inverse of value 0 and measure bar extent relative to it. Read grouped/series bars by color mask.

## 4a. Bar via outline (stippled/dotted fills)

Some charts (especially Excel-style figures) fill bars with a hatched or stippled pattern rather than a flat color. The fill mask is full of holes, so `connectedComponentsWithStats` fragments one bar into dozens of small CCs. The bar still has a **solid dark border**, so detect that instead:

```python
# Scan downward from the top of the plot in a column band centered on the
# bar's expected x; the bar top is the first row that's mostly dark across
# the full bar width.
def find_bar_top(cx, half_width=28, dark_thr=160, min_run=40, search_start=20):
    for r in range(search_start, frame_bot):
        strip = gray[r, cx - half_width : cx + half_width + 1]
        if (strip < dark_thr).sum() >= min_run:
            return r
    return None
```

A few notes from real cases:

- The border's gray value is usually 80-160, NOT < 80. Don't use a strict "black" threshold.
- `min_run` should be ~60-70 % of the bar width — most of the strip is dark when you hit the border, but anti-aliasing chips off a few pixels.
- Predict bar x positions from the layout when CC fails: pure-color GC1 and GC3 bars are easy to find, then the stippled GC2 sits at `gc1_cx + bar_width + 1`.
- Closing the dotted mask with a 5×5 morphological close also works and lets you fall back to CC + centroid. Prefer the outline scan if closing visibly fills bars together.

## 4b. Error-bar caps on bar charts

The upper error-bar cap is above the bar's filled region (in white space), so it's findable. The lower cap is **inside the bar fill** and visually almost invisible — the bar's color covers the thin black tick. In practice:

- Detect upper caps reliably by scanning rows *above* the bar top for a horizontal black run ≥ 6 px in a narrow column band (`cx ± 12`).
- Detect lower caps unreliably or skip them. If you skip, document "lower error bound not extracted" rather than reporting `y_lo = mean` (which lies about the uncertainty).
- If the chart prints SD/CI on the bars or in a table, transcribe and pair with the extracted mean instead of reading the lower cap.

```python
def find_upper_cap(cx, bar_top, dark, half_w=12, min_run=6):
    cap_rows = []
    for r in range(20, bar_top - 1):
        strip = dark[r, cx - half_w : cx + half_w + 1]
        run = max_run = 0
        for v in strip:
            if v > 0: run += 1; max_run = max(max_run, run)
            else: run = 0
        if max_run >= min_run:
            cap_rows.append(r)
    # require cap to be > 5 rows above bar top to skip the bar-top edge itself
    cap_rows = [r for r in cap_rows if bar_top - r >= 5]
    return min(cap_rows) if cap_rows else bar_top
```

`bar_top - r >= 5` is the key filter: without it, the bar's own top border (a horizontal dark line at the bar value) gets misidentified as the upper-error cap, and you report `y_hi = mean`.

## 5. Histogram

Contiguous bars; take the top of the colored region per x-column and report the per-bin envelope.

```python
xs, hh = [], []
for c in range(left, right):
    oc = np.where(mask[top:bot, c] > 0)[0]
    if len(oc) > 2:
        xs.append(col2x(c)); hh.append(row2y(top + oc.min()))
xs, hh = np.array(xs), np.array(hh)

# envelope per integer bin
import csv
with open('hist_envelope.csv','w',newline='') as f:
    w = csv.writer(f); w.writerow(['x','normalized_count'])
    for xi in range(int(xs.min()), int(xs.max())+1):
        sel = hh[(xs >= xi-0.5) & (xs < xi+0.5)]
        if len(sel): w.writerow([xi, round(float(sel.max()),3)])
```
A single narrow tall spike (e.g. a delta at x≈0) is easy to mistake for noise — confirm it against the `view`ed image and report it explicitly rather than filtering it out.

## 6. Hazards

These are the failure modes that produce wrong numbers which *look* fine until the Phase 4 re-plot. Handle them proactively.

### Legend occlusion (the most common)
A legend box or its colored swatches sit over the data and share a series color. Two signatures:
- **Clamped run**: a span of x where the extracted value is pinned at a constant (the legend box's edge), e.g. histogram bins 93-108 all reading 0.893.
- **Spurious jump**: a curve leaps to the legend swatch's height for the few columns the swatch occupies, then drops back (e.g. an orange curve jumping to ~84 at epsilon 4-6).

Fix by linear interpolation between the clean neighbors bracketing the occluded x-span:
```python
d = dict(series)                       # {x: y}
x_lo, x_hi = 3.5, 6.0                   # last clean x before, first clean x after
y_lo, y_hi = d[x_lo], d[x_hi]
for x in [v for v in d if x_lo < v < x_hi]:
    d[x] = round(y_lo + (y_hi-y_lo)*(x-x_lo)/(x_hi-x_lo), 1)
```
Identify the occluded span from where the legend box is in the image (or detect runs of constant value / monotonicity violations automatically — see replot_and_validate.md). The same figure can have the artifact in multiple panels/series; fix each.

### Gridline / series color collision
Pale gridlines of the same hue leak into a mask and pull medians. Raise the saturation floor in `inRange`. For bars, require a minimum contiguous vertical run (`len(rr) > threshold`) so thin gridlines don't register as a bar top.

### Overlapping markers (scatter)
Handled by the area-ratio + k-means split in recipe 2. Very dense clusters may still merge a few points; report this as a known undercount rather than pretending completeness.

### Off-panel / decoration detections
Trend lines, error bars, annotations, and legend swatches can match a series color. Always filter detections to inside the frame and to plausible value ranges before converting.

### Anti-aliasing at curve edges
Thresholds that are too tight drop the faint anti-aliased pixels at a thin line's edge, biasing the median. Slightly loosen the value floor, or take the median (not the min/max) row per column.

### Dashed / dotted fit lines in the same color as the markers
A frequent magazine-figure layout: colored markers + a dashed best-fit line in the same color. Erosion-based marker detection (§3a) wipes the *connector* line cleanly, but a **dashed** line's individual segments are 5-10 px long and survive erosion as marker-sized blobs. Result: the marker count is inflated 1.5-2×.

Two mitigations (use both):

1. After CC, filter out blobs whose aspect ratio is too elongated to be a marker disk: `if max(w,h) / min(w,h) > 2.5: skip`. Dash fragments are typically 8×2 px (ratio 4); markers are roughly square (ratio < 1.5).
2. For solid fit lines (e.g. the green 27 °C line in some figures), `(w * h) > 50 * 50` AND `area / (w*h) < 0.2` catches the elongated low-density line strand specifically. Skip those CCs before centroiding.

Even with both, expect ~10-20 % over-counting in the densest regions. Report it as a known undercount-of-fidelity, not a known undercount-of-data — your markers exist, you just have phantom siblings.

### Legend text descending below the swatch
A legend swatch is small (~12 px tall), but the label *text* next to it is often 20-30 px tall and descenders ("g", "p") reach 5-8 px below the text baseline. If you exclude only the swatch rows (e.g. rows 20-120), the text descenders at rows 130-140 still contaminate your dark mask and get detected as bar caps or markers. Widen the legend exclusion by ~30 rows past the visible text, and verify by checking that no detection sits at the exclusion boundary row.

### X-axis tick label bleeding into the y-axis label band
When you crop a narrow band to the left of the y-axis for y-tick detection, the "0" character of the x-axis's "0,00" or "0.0" label at the bottom-left corner often falls *within* your y-label band. It then gets detected as a spurious y-tick and shifts the y calibration fit. Crop the y-band to rows above the x-axis (`gray[:bot-10, left-90:left-6]`) so the x-label is excluded.

### Markers stacked vertically at the same x (dense column)
Some series have many points sharing nearly the same x (e.g. a parameter-sweep with replicates). Color masking produces one tall thin CC (`w=20, h=120`) holding many merged markers. The `area / single_marker_area` ratio gives you the count, then k-means splits the pixels. The §2 scatter recipe already handles this — the gotcha is not filtering the CC out as "too elongated" or "too large" before the split:

```python
# Don't reject this CC: it's many stacked markers, not a line
if w > 100 or h > 100:
    # only reject if BOTH big AND low density (suggests fit line)
    if (stats[i, cv2.CC_STAT_AREA] / (w*h)) < 0.3:
        continue  # line, skip
    # else fall through to the k-means split path
```

### Tickle the legend before extracting
Before running any extraction, sample pixel values inside the legend's visible swatches to confirm your HSV ranges actually match the series colors. Each `cv2.inRange` should produce at least the swatch (12×12 = 144 px) plus the data. If your mask comes back near zero pixels, your HSV bounds don't match the printed swatch — fix that first, before debugging anything downstream.
