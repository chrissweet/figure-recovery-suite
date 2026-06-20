# Population, 10,000 BCE to 2023 — extraction

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
