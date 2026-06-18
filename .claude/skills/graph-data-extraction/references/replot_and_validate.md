# Re-plot and validate: closing the loop

This is the verification phase and it is mandatory. The re-plot is a test, not decoration. Calibration mistakes and occlusion artifacts are invisible in a CSV column but obvious the moment you overlay a reconstruction on the source. In practice, multiple legend-occlusion artifacts have survived a first extraction pass and were caught only here.

## Table of contents
1. The loop
2. Matplotlib default colors (match the original)
3. Re-plot templates
4. Artifact-detection heuristics
5. The scatter refit check
6. When the loop passes

## 1. The loop

```
extract (Phase 3)  ->  re-plot  ->  view re-plot AND source  ->  compare
        ^                                                          |
        |________________  artifact found? fix, regenerate CSV ____|
```
Repeat until the reconstruction matches the original in shape, ordering, crossings, and endpoint values. Only then deliver.

## 2. Matplotlib default colors

Match the source so the comparison is apples-to-apples. The default cycle:
```
C0 #1f77b4 blue   C1 #ff7f0e orange  C2 #2ca02c green  C3 #d62728 red
C4 #9467bd purple C5 #8c564b brown   C6 #e377c2 pink   C7 #7f7f7f gray
```
Use the same axis ranges (`set_xlim`/`set_ylim`) and the same chart type as the original.

## 3. Re-plot templates

### Line / curve (single or multi-panel)
```python
import csv, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
def readcsv(fn):
    rows = list(csv.reader(open(fn)))
    return list(zip(*[[float(c) if c!='' else None for c in r] for r in rows[1:]]))

c = readcsv('curves.csv')   # cols: x, s1, s2, s3
fig, ax = plt.subplots(figsize=(8,4.5))
ax.plot(c[0], c[1], color='#1f77b4', lw=2, label='Series1')
ax.plot(c[0], c[2], color='#ff7f0e', lw=2, label='Series2')
ax.plot(c[0], c[3], color='#2ca02c', lw=2, label='Series3')
ax.set_xlim(0, XMAX); ax.set_ylim(0, YMAX); ax.legend()
ax.set_xlabel('...'); ax.set_ylabel('...')
fig.savefig('recon.png', dpi=150, bbox_inches='tight')
fig.savefig('recon.pdf', bbox_inches='tight')   # vector, if user wants it
```

### Scatter (overlay the original fit if there was one)
```python
import numpy as np
d = [(float(a),float(b)) for a,b in list(csv.reader(open('points.csv')))[1:]]
x = np.array([p[0] for p in d]); y = np.array([p[1] for p in d])
fig, ax = plt.subplots(figsize=(8,5))
ax.scatter(x, y, s=20, color='#1f77b4')
# if original had a quadratic/linear fit, draw it from the printed equation:
xs = np.linspace(x.min(), x.max(), 200)
ax.plot(xs, A0 + A1*xs + A2*xs**2, color='#8b0000')
ax.set_xlabel('...'); ax.set_ylabel('...')
fig.savefig('recon.png', dpi=150, bbox_inches='tight')
```

### Histogram / bar
```python
xs = [...]; ys = [...]
fig, ax = plt.subplots(figsize=(8,4.2))
ax.fill_between(xs, ys, step='mid', alpha=0.8, color='#ff7f0e', label='...')  # histogram envelope
# ax.bar(centers, heights, width=w, color='#1f77b4')                          # bars
ax.set_xlim(...); ax.set_ylim(...); ax.legend()
fig.savefig('recon.png', dpi=150, bbox_inches='tight')
```

After saving, `view('recon.png')` and `view` the source crop. Look at them back to back.

## 4. Artifact-detection heuristics

Beyond eyeballing, flag these automatically before/after re-plotting:

```python
import numpy as np
def flag_artifacts(xs, ys, expect_monotonic=False):
    ys = np.array(ys, float); issues = []
    # clamped run: many consecutive identical values
    for i in range(len(ys)-3):
        if len(set(np.round(ys[i:i+4],2))) == 1:
            issues.append(('clamped_run', xs[i], xs[i+3])); break
    # spike against neighbours (legend swatch)
    for i in range(1, len(ys)-1):
        if ys[i] > ys[i-1]+5 and ys[i] > ys[i+1]+5:
            issues.append(('spike', xs[i]))
    # monotonicity violation for series that should only decrease/increase
    if expect_monotonic:
        d = np.diff(ys)
        if (d > 2).any() and (d < -2).any():
            issues.append(('non_monotonic',))
    return issues
```
A clamped run or a spike almost always means legend occlusion → repair with the interpolation in extraction_recipes.md, regenerate the CSV, re-plot.

## 5. The scatter refit check

When the original printed a regression equation and/or R², this is the strongest single fidelity test you have. Refit the *extracted* points and compare.

```python
import numpy as np
c = np.polyfit(x, y, 2)                 # match the original's model order
yp = np.polyval(c, x)
r2 = 1 - np.sum((y-yp)**2)/np.sum((y-y.mean())**2)
print(f"refit: {c[2]:.2f} + {c[1]:.3f}x + {c[0]:.5f}x^2,  R^2={r2*100:.1f}%")
# compare against the printed equation and R^2
```
Coefficients and R² landing close to the printed values is strong evidence the calibration and detection are sound. A large gap means go back and find the error (usually calibration, or contamination from a non-marker color).

## 6. When the loop passes

The reconstruction matches the original in:
- shape of every series,
- ordering / which series is on top, and where they cross,
- values at the axis endpoints,
- (scatter) refit coefficients and R² close to printed.

Then write the corrected CSV(s) to `/mnt/user-data/outputs/`, save the reconstruction PNG (and PDF if useful), `present_files`, and deliver with the explicit caveats from SKILL.md (per-point error budget, which spans are interpolated, likely undercounts, refit comparison, and "prefer the original source data for anything beyond drafts"). If Phase 4 changed any values, say that the corrected CSV supersedes any earlier intermediate CSV you may have shown.
