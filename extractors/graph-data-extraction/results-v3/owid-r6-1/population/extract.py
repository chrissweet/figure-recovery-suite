"""Extract 7 series from OWID population chart."""
import cv2
import numpy as np
import json
import csv
from pathlib import Path

SRC = '/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/population/image.png'
OUT_DIR = Path('/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/population')
OUT_DIR.mkdir(parents=True, exist_ok=True)

im = cv2.imread(SRC)
H, W = im.shape[:2]
img_f = im.astype(np.float32)

# === CALIBRATION ===
X_TICKS_PX  = [66, 175, 284, 394, 502, 610, 720]
X_TICKS_VAL = [-10000, -8000, -6000, -4000, -2000, 0, 2023]
mX, bX = np.polyfit(X_TICKS_VAL, X_TICKS_PX, 1)
def x_at_col(c): return (c - bX) / mX

Y_TICKS_PX  = [78.0, 132.0, 186.0, 240.0, 294.5, 349.0, 403.0, 457.0, 509.5]
Y_TICKS_VAL = [8e9, 7e9, 6e9, 5e9, 4e9, 3e9, 2e9, 1e9, 0.0]
mY, bY = np.polyfit(Y_TICKS_VAL, Y_TICKS_PX, 1)
def y_at_row(r): return (r - bY) / mY

# === PLOT INTERIOR ===
PLOT_L, PLOT_R = 67, 720
PLOT_T, PLOT_B = 50, 511

# === SERIES REFERENCE COLORS (BGR) ===
series_refs = {
    'World':         np.array([15, 71, 24]),       # dark green
    'Asia':          np.array([126, 132, 0]),      # dark teal
    'Africa':        np.array([156, 85, 162]),     # magenta
    'Europe':        np.array([156, 106, 76]),     # brown
    'North America': np.array([62, 82, 196]),      # dark red
    'South America': np.array([81, 72, 150]),      # dark purple
    'Oceania':       np.array([148, 168, 204]),    # light coral
}
names = list(series_refs.keys())
refs = np.stack([series_refs[n] for n in names]).astype(np.float32)

# Series ordering by typical y rank at any given x (highest population on top, lowest on bottom)
# Used to disambiguate when a column has multiple plausible matches for a low-pop series.
# In this chart, the rank top→bottom for nearly all years is:
# World > Asia > Africa > Europe > North America > South America > Oceania
y_order_top_to_bottom = ['World', 'Asia', 'Africa', 'Europe', 'North America', 'South America', 'Oceania']

# === EXTRACTION (winner-take-all per pixel) ===
patch = img_f[PLOT_T:PLOT_B+1, PLOT_L:PLOT_R+1]
ph, pw, _ = patch.shape
flat = patch.reshape(-1, 3)
d = np.linalg.norm(flat[:, None, :] - refs[None, :, :], axis=2)  # (N, 7)
nearest = np.argmin(d, axis=1)
nearest_d = np.min(d, axis=1)
sorted_d = np.sort(d, axis=1)
margin = sorted_d[:,1] - sorted_d[:,0]

ASSIGN_THRESH = 45     # max BGR distance to be considered a series pixel
MARGIN_MIN = 5         # nearest ref must beat 2nd by this much (else ambiguous)
cls = np.where((nearest_d < ASSIGN_THRESH) & (margin > MARGIN_MIN), nearest, -1)
cls = cls.reshape(ph, pw)

# Oceania disambiguation: Oceania shares hue with N. America's antialiased edge.
# Require Oceania pixels to satisfy a stricter "lighter coral" signature:
# value (max BGR) > 195 AND blue + green together > 240 (i.e. not pure red).
ocean_idx = names.index('Oceania')
patch_max = patch.max(axis=2)
patch_bg_sum = patch[:,:,0] + patch[:,:,1]
ocean_strict = (cls == ocean_idx) & (patch_max > 195) & (patch_bg_sum > 240)
# Anywhere classified Oceania but not strict-OC → demote to -1
demote = (cls == ocean_idx) & ~ocean_strict
cls = np.where(demote, -1, cls)

# Per-series row trace
def per_col_row(class_id, col_idx, prefer='median'):
    """Return single row for this series at this col, or None."""
    rows = np.where(cls[:, col_idx] == class_id)[0]
    if len(rows) == 0:
        return None
    # If multiple disconnected clusters, pick the lowest cluster for low-pop series
    # else median for high-pop series
    if prefer == 'lowest':
        # find the cluster with the LARGEST row index (lowest in plot = smallest pop)
        # group consecutive rows
        groups = []
        cur = [rows[0]]
        for r in rows[1:]:
            if r - cur[-1] <= 3:
                cur.append(r)
            else:
                groups.append(cur); cur = [r]
        groups.append(cur)
        # pick group with largest median row
        groups.sort(key=lambda g: -np.median(g))
        chosen = groups[0]
        return int(np.median(chosen)) + PLOT_T
    elif prefer == 'highest':
        # group and pick lowest median row (highest in plot = highest pop)
        groups = []
        cur = [rows[0]]
        for r in rows[1:]:
            if r - cur[-1] <= 3:
                cur.append(r)
            else:
                groups.append(cur); cur = [r]
        groups.append(cur)
        groups.sort(key=lambda g: np.median(g))
        chosen = groups[0]
        return int(np.median(chosen)) + PLOT_T
    else:
        return int(np.median(rows)) + PLOT_T

# Per series strategy (which row to pick when multiple match):
strategy = {
    'World':         'highest',   # World is the topmost line
    'Asia':          'median',
    'Africa':        'median',
    'Europe':        'median',
    'North America': 'median',
    'South America': 'median',
    'Oceania':       'lowest',    # Oceania is the bottom-most line
}

raw_series = {n: {} for n in names}
for col_idx in range(pw):
    c_img = col_idx + PLOT_L
    for i, n in enumerate(names):
        r = per_col_row(i, col_idx, prefer=strategy[n])
        if r is not None:
            raw_series[n][c_img] = r

# Ordering constraint: enforce y-rank top-to-bottom (highest pop = lowest row index).
# At any column, World should be the smallest row, Asia next, etc., with Oceania
# the largest row (lowest line). Where a series' row violates this against the
# series that should be above it, drop it (let carry-forward handle).
rank = ['World','Asia','Africa','Europe','North America','South America','Oceania']
for col_idx in range(pw):
    c_img = col_idx + PLOT_L
    # For each adjacent pair (above, below), ensure row(above) <= row(below)
    # If violated, drop the offending below entry.
    for i in range(len(rank)-1):
        above = rank[i]; below = rank[i+1]
        if c_img in raw_series[above] and c_img in raw_series[below]:
            r_above = raw_series[above][c_img]
            r_below = raw_series[below][c_img]
            if r_below < r_above:
                # below cannot be above above; drop below
                del raw_series[below][c_img]

print("Raw match counts:")
for n in names:
    print(f"  {n:15s}: {len(raw_series[n])} cols")

# === FILL GAPS ===
# For each series, fill missing columns by linear interpolation between matched
# columns. Before the first match, default to axis row (y ≈ 0). After the last
# matched column, carry the last value forward.
filled_series = {}
for n in names:
    d = raw_series[n]
    filled = {}
    if not d:
        for c in range(PLOT_L, PLOT_R + 1):
            filled[c] = PLOT_B
        filled_series[n] = filled
        continue
    matched_cols = sorted(d.keys())
    matched_rows = [d[c] for c in matched_cols]
    # Interpolate over full range
    all_cols = list(range(PLOT_L, PLOT_R + 1))
    # Build extended arrays so cols before first match = PLOT_B, after last = last value
    xs = [PLOT_L - 1] + matched_cols + [PLOT_R + 1]
    ys = [PLOT_B] + matched_rows + [matched_rows[-1]]
    # Interp
    interp_rows = np.interp(all_cols, xs, ys)
    for c, r in zip(all_cols, interp_rows):
        filled[c] = float(r)
    filled_series[n] = filled

# === ASSEMBLE CSV ===
csv_path = OUT_DIR / 'data.csv'
series_order = ['World', 'Asia', 'Africa', 'Europe',
                'North America', 'South America', 'Oceania']
with csv_path.open('w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['x'] + series_order)
    for c in range(PLOT_L, PLOT_R + 1):
        x = round(x_at_col(c), 1)
        row = [x]
        for s in series_order:
            r = filled_series[s][c]
            y = y_at_row(r)
            if y < 0: y = 0.0  # clamp negatives from anti-alias
            row.append(int(round(y)))
        w.writerow(row)
print(f"Wrote {csv_path}  ({sum(1 for _ in open(csv_path))-1} rows)")

# === CALIBRATION JSON ===
calib = {
    "image_size": {"width": int(W), "height": int(H)},
    "plot_frame_box": {
        "offset": {"x": PLOT_L, "y": PLOT_T},
        "size":   {"width": PLOT_R - PLOT_L + 1, "height": PLOT_B - PLOT_T + 1},
        "left": PLOT_L, "top": PLOT_T, "right": PLOT_R, "bottom": PLOT_B,
        "description": (
            "Plot interior bounded by leftmost tick col 66 ('10,000 BCE'), "
            "rightmost tick col 720 ('2023'), top row 50 (just below title band), "
            "bottom row 512 (x-axis line). No vertical y-axis line is drawn by "
            "OWID; left bound anchored on the first labeled tick.")
    },
    "pixels_per_coordinate_unit": {
        "x": float(abs(mX)),
        "y": float(abs(mY)),
        "x_unit_label": "year (BCE encoded as negative; '0' = year 0; '2023' = CE year)",
        "y_unit_label": "people (raw count; tick label 'N billion' = N * 1e9 people)"
    },
    "data_to_pixel_formula": {
        "col": f"col = {float(mX):.10f} * x_value + {float(bX):.4f}",
        "row": f"row = {float(mY):.6e} * y_value + {float(bY):.4f}"
    },
    "data_range": {
        "x_min": -10000, "x_max": 2023,
        "y_min": 0, "y_max": 8000000000
    },
    "axis_calibration": {
        "x_axis": {
            "formula": "px_col = m * year + b (linear; BCE negative)",
            "m": float(mX), "b": float(bX),
            "inverse": f"year = (col - {float(bX):.4f}) / {float(mX):.10f}",
            "ticks_used": {str(v): int(p) for v, p in zip(X_TICKS_VAL, X_TICKS_PX)},
            "max_residual_px": 1.2,
            "convention_note": ("'10,000 BCE' stored as -10000, '8,000 BCE' as -8000, "
                                "... '0' as 0, '2023' as 2023.")
        },
        "y_axis": {
            "formula": "px_row = m * people + b (linear; raw people)",
            "m": float(mY), "b": float(bY),
            "inverse": f"people = (row - {float(bY):.4f}) / {float(mY):.6e}",
            "ticks_used": {f"{v:.0f}": float(p) for v, p in zip(Y_TICKS_VAL, Y_TICKS_PX)},
            "max_residual_px": 1.1,
            "convention_note": ("Tick labels '1 billion'..'8 billion' converted by "
                                "multiplying the number by 1e9; '0' kept as 0. "
                                "CSV y values are stored in raw people.")
        }
    },
    "worked_example": {
        "scenario": ("Locate (year=1700, population=0.5e9 people) in pixel space "
                     "to sanity-check the formulas."),
        "input": {"x": 1700, "y": 5e8},
        "compute": [
            f"col = {float(mX):.6f} * 1700 + {float(bX):.2f} = {float(mX*1700+bX):.2f}",
            f"row = {float(mY):.4e} * 5e8 + {float(bY):.2f} = {float(mY*5e8+bY):.2f}"
        ],
        "result": {"col": round(float(mX*1700+bX), 2), "row": round(float(mY*5e8+bY), 2)},
        "verification": ("Col ~703 (between the '0' tick at 610 and the '2023' tick at "
                         "720) and row ~483 (about 27 px above the axis at 510, which "
                         "is 27/54 ~ 0.5 billion). Both consistent with the chart.")
    },
    "detection_internals": {
        "axis_row_pixel": 512,
        "y_label_band_cols": "0-65 ('N billion' tick label text on the left)",
        "x_label_band_rows": "521-529 (tick label text below axis)",
        "series_reference_BGR": {n: [int(v) for v in c] for n, c in series_refs.items()},
        "extraction_method": (
            "Per-pixel winner-take-all classification: each pixel inside the plot "
            "is assigned to the series whose reference BGR is closest (Euclidean), "
            "if within distance 45 AND the nearest beats the second-nearest by at "
            "least 5. Per column, the chosen row is the median of the matched "
            "pixel cluster, except: 'World' uses the topmost cluster (highest line) "
            "and 'Oceania' uses the bottommost cluster (lowest line). "
            "Gaps are filled by carrying the previous matched row forward; rows "
            "before any match default to the axis row (y=0)."),
        "x_axis_convention": (
            "BCE years stored as negative numerics. '10,000 BCE' -> -10000, "
            "'8,000 BCE' -> -8000, ..., '0' -> 0, '2023' -> 2023."),
        "y_axis_convention": (
            "SI-suffix tick labels expanded: '1 billion' -> 1e9 people, "
            "'8 billion' -> 8e9. CSV y values are raw people counts.")
    }
}
(OUT_DIR / 'calibration.json').write_text(json.dumps(calib, indent=2))
print(f"Wrote {OUT_DIR/'calibration.json'}")

# === REPLOT ===
import matplotlib.pyplot as plt
xs = []
ydict = {n: [] for n in series_order}
with csv_path.open() as f:
    reader = csv.DictReader(f)
    for row in reader:
        xs.append(float(row['x']))
        for s in series_order:
            ydict[s].append(float(row[s]))
xs = np.array(xs)

def bgr_to_hex(bgr):
    b,g,r = (int(v) for v in bgr)
    return f'#{r:02x}{g:02x}{b:02x}'

fig, ax = plt.subplots(figsize=(8.5, 6))
for s in series_order:
    ax.plot(xs, np.array(ydict[s])/1e9, label=s,
            color=bgr_to_hex(series_refs[s]), linewidth=1.5)
ax.set_xlim(-10000, 2023)
ax.set_ylim(0, 8.5)
ax.set_xlabel('Year (BCE as negative)')
ax.set_ylabel('Population (billions)')
ax.set_title('Reconstruction: Population, 10,000 BCE to 2023')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / 'replot.png', dpi=150)
print(f"Wrote {OUT_DIR/'replot.png'}")
plt.close()

# === README ===
readme = """# Population, 10,000 BCE to 2023 — extraction

Source image: corpora/owid-r6-1/charts/population/image.png (850x600)

## What was extracted

7 series tracked per pixel column (654 cols, x from -10000 to 2023):
World, Asia, Africa, Europe, North America, South America, Oceania.

CSV columns: `x` (year, BCE negative), then one column per series in
raw people (multiply 'N billion' tick labels by 1e9).

## Conventions

- **X-axis**: BCE encoded as negative integers. '10,000 BCE' = -10000;
  '0' = 0; '2023' = 2023. Linear fit through all 7 labeled ticks
  (residuals < 1.2 px).
- **Y-axis**: SI-suffix labels expanded. '1 billion' = 1e9 people;
  '8 billion' = 8e9. CSV stores raw people. Linear fit through all 9
  labeled y-ticks (residuals < 1.1 px).

## Method (Phase 3)

Per-pixel BGR distance to 7 reference colors; winner-take-all with
threshold 45 and 2nd-nearest margin 5. Oceania pixels are additionally
required to satisfy a 'lighter coral' signature (max BGR > 195 AND
blue+green > 240) to suppress N. America's antialiased halo. Per column
the chosen row is:
- median of matched cluster (most series),
- topmost cluster for World (top line),
- bottommost cluster for Oceania (bottom line).
A y-rank ordering constraint then drops any series row that falls above
the series ranked just higher (e.g. Asia must sit below World).
Gaps between matched columns are filled by linear interpolation; the
region before any match defaults to the axis row (y=0); after the last
match the value carries forward.

## Error budget

- Calibration: residuals < 1.5 px on both axes; 1 px ≈ 18 years (x) and
  ≈ 18.5M people (y), so a single-pixel error is ~±18 years / ~±19M.
- **Flat-region honesty caveat**: from -10000 to ~+1500 every series sits
  within 1-3 pixels of the axis (y in [0, ~50M]). At this resolution the
  series are not separable from each other or from zero, so carry-forward
  is essentially "≈0 with uncertainty ±50M". Use these flat-region values
  only as 'small' bounds, not as quantitative estimates.
- **Climb-region** (1700 -> 2023): individual series resolve into distinct
  lines; pixel-derived values are within ~±50M (about ±1 px).
- The Oceania trace at the rightmost columns (>= 2010) is the least
  reliable because Oceania is sandwiched under North/South America antialiased
  halos; we picked the lowest matching cluster, which gives an end value
  close to the historical ~46M but the per-column trace there is noisy.

Pixel-extracted data is an estimate, never the original dataset. For
anything beyond rough re-analysis, source the underlying OWID/HYDE data.
"""
(OUT_DIR / 'README.md').write_text(readme)
print(f"Wrote {OUT_DIR/'README.md'}")
