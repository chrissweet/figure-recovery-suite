# Calibration: pixel space → data space

Calibration is the foundation. If it is wrong, every extracted number is wrong by the same systematic factor, and the re-plot in Phase 4 will look plausibly shaped but sit at the wrong values. Anchor on labeled ticks, never on the frame corners.

## Table of contents
1. Render / load the image
2. Find the plot frame
3. Find tick-label pixel centers
4. Fit the axis mapping (linear)
5. Sanity-check the fit
6. Log axes
7. Multi-panel figures

## 1. Render / load

```python
import cv2, numpy as np
# From PDF (preferred for papers): pdftoppm -png -r 300 -f PAGE -l PAGE in.pdf out
im = cv2.imread('plot.png')
print(im.shape)  # (H, W, 3)
hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
```

Always `view` the image before writing extraction code. Decisions that depend on what you see: chart type, axis ranges, series colors, log vs linear, and hazards (legend over data, dense markers, gridline color).

## 2. Find the plot frame (axis box)

The frame is usually the darkest long horizontal/vertical lines. Thresholds vary; if the frame is light gray, raise the threshold.

```python
dark = gray < 80                      # try 80; raise to ~130 for light gray frames
colblack = dark.sum(axis=0)           # dark pixels per column
rowblack = dark.sum(axis=1)           # dark pixels per row
H, W = gray.shape
vcols = np.where(colblack > 0.4*H)[0] # vertical frame lines
hrows = np.where(rowblack > 0.3*W)[0] # horizontal frame lines

def group(idx, gap=10):
    g=[]; c=[idx[0]]
    for x in idx[1:]:
        if x-c[-1] <= gap: c.append(x)
        else: g.append(int(np.mean(c))); c=[x]
    g.append(int(np.mean(c))); return g

print("vertical frame x:", group(vcols))   # e.g. [left, right]  (or 4 values for 2 panels)
print("horizontal frame y:", group(hrows)) # e.g. [top, bottom]
```

If the frame doesn't show up at any threshold, crop the margin and `view` it to read edge pixels by eye. Two clean numbers per axis are enough to proceed.

## 3. Find tick-label pixel centers

Tick labels are dark text clusters in the margin just outside the frame. Detect them in a thin band and group into centers. The band must be narrow enough to exclude the rotated axis *title* (e.g. a vertical "Accuracy" label), which otherwise contaminates the centers.

X-axis labels (below the bottom frame):
```python
band = gray[bottom+6 : bottom+40, :] < 100   # band just under the axis
col = band.sum(axis=0)
xs = np.where(col > 1)[0]
xcenters = group(xs, gap=25)   # reuse group(); widen gap for multi-digit labels
print("x tick centers:", xcenters)
```

Y-axis labels (left of the left frame). **Crop the y-band to rows above the x-axis** — otherwise the "0" or "0,0" character of the x-axis "0" tick at the bottom-left often falls inside the y-band and registers as a phantom y-tick, biasing the fit:
```python
band = gray[:bot-10, left-90 : left-6] < 100   # NOTE the row cap at bot-10
row = band.sum(axis=1)
ys = np.where(row > 2)[0]
ycenters = group(ys, gap=20)
print("y tick centers:", ycenters)
```

Map each detected center to its printed tick value by reading the labels off the `view`ed image (left-to-right for x, top-to-bottom for y). Discard stray centers that are actually the axis title (often the first/last entry, far from the others).

If the count of detected centers doesn't match the count of visible labels, that's a sign of contamination — usually one of: (a) axis title text caught in the band, (b) the "0" of the x-axis bleeding in (fix above), (c) two adjacent labels merging because your `gap` is too large, or (d) a digit getting split because `gap` is too small (multi-digit labels like "100" need gap ≥ 12 to merge).

## 4. Fit the axis mapping (linear)

With >= 2 (pixel, value) pairs per axis, fit a line. Using all available ticks (not just two) averages out detection jitter and lets the sanity check catch problems.

```python
xp = np.array([265, 495, 713]);  xv = np.array([0, 100, 200])   # x ticks
yp = np.array([167, 273, 380, 487, 593, 700]); yv = np.array([100,80,60,40,20,0])

ax_x = np.polyfit(xp, xv, 1)   # [m, b] for value = m*pixel + b
ax_y = np.polyfit(yp, yv, 1)
def col2x(c): return ax_x[0]*c + ax_x[1]
def row2y(r): return ax_y[0]*r + ax_y[1]
```

Equivalent two-point form (when you only trust two ticks): `value = v0 + (pixel - p0) * (v1 - v0)/(p1 - p0)`.

## 5. Sanity-check the fit (do not skip)

Plug the tick pixels back in; you must recover the printed values closely.

```python
print("x check:", [round(col2x(p),2) for p in xp])  # expect ~[0,100,200]
print("y check:", [round(row2y(p),2) for p in yp])  # expect ~[100,80,60,40,20,0]
```

If a value is off (classic symptom: `0.0` comes back as `0.06`), the label band caught extra text (axis title) or a gridline. Narrow the band, drop the contaminated center, refit. Don't proceed on a bad fit.

## 6. Log axes

Tell-tale: tick labels 1, 10, 100, 1000 at *even* pixel spacing. Fit in log space.

```python
xp = np.array([...]); xv = np.array([1,10,100,1000])
ax_x = np.polyfit(xp, np.log10(xv), 1)
def col2x(c): return 10**(ax_x[0]*c + ax_x[1])
```

Check by confirming midpoints land where expected (e.g. the pixel halfway between the 1 and 100 ticks should map near 10).

**Record the scale in `calibration.json` (added 2026-06-19 after synthetic-r4-1 chart #4 round-trip).** The `axis_calibration.{x,y}_axis` block must carry an explicit `scale` field — `"linear"` or `"log10"` — so downstream consumers (scorer, verifier, replot driver) know which formula to use. The `write_calibration.py` script accepts `x_scale=` / `y_scale=` kwargs for exactly this purpose:

```python
from write_calibration import write_calibration
write_calibration(image_path, out_path,
                  x_axis=(mx, bx), y_axis=(my, by),
                  x_data_range=(1, 1000), y_data_range=(0, 100),
                  x_scale="log10",            # <-- new
                  y_scale="linear",
                  ...)
```

Without the `scale` field, a calibration written from a log-axis fit (`m, b` in log space) will be MISREAD by every existing consumer as linear — producing a 30-100 %-per-tick misread on every value. The synthetic-r4-1 chart #4 (validated 2026-06-19) catches this with the per-element verifier: an axis predicate that respects `scale` passes, one that doesn't fails 0/4 on line endpoints. Schema back-compat: missing `scale` defaults to `"linear"`, so the aedes-aegypti-2014 corpus (written before this field existed) continues to work.

## 7. Multi-panel figures

`group(vcols)` returning four x-values means two side-by-side panels: panel A `[x0,x1]`, panel B `[x2,x3]`. Calibrate and extract each panel independently — they often share the y-axis but have different x-ranges (e.g. an L2 panel 0-250 and an L-infinity panel 0-15). Detect each panel's own x ticks within its own column span.
