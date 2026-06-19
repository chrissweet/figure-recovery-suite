#!/usr/bin/env python3
"""Build calibration.json for synthetic-r4-1/02-simple-bar."""
import sys
sys.path.insert(0, "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/.claude/skills/graph-data-extraction/scripts")
from write_calibration import write_calibration

IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/synthetic-r4-1/charts/02-simple-bar/image.png"
OUT = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/synthetic-r4-1/02-simple-bar/calibration.json"

# X axis: categorical positions 0..5 fit linearly against detected bar-label
# centers at cols [121.5, 222.5, 323.5, 422.5, 523.0, 623.5].
# Best-fit linear: pos = 0.00997002 * col + -1.21632351
# Inverse:        col = (pos - b) / m = (pos + 1.21632351) / 0.00997002
m_x, b_x = 0.00997002, -1.21632351

# Y axis: ticks at 0, 5, 10, 15, 20, 25 with row centers
#   391.5, 320.5, 249.5, 179.5, 108.5, 37.5
# Best-fit: value = -0.070678 * row + 27.660482
m_y, b_y = -0.070678, 27.660482

write_calibration(
    image_path=IMG,
    out_path=OUT,
    x_axis=(m_x, b_x),
    y_axis=(m_y, b_y),
    x_data_range=(0, 5),     # 6 categorical positions: Alpha..Foxtrot
    y_data_range=(0, 25),
    x_unit_label="pixels per category index",
    y_unit_label="pixels per req/s",
    worked_example={
        "scenario": "Top of the Delta bar (highest in the chart).",
        "x": 3, "y": 22.5,
        "verification": "Delta's bar top edge sits near col 423, row 73; this (col, row) should land at the top-center of the Delta bar in image.png.",
    },
    legend_exclusion=(40, 70, 540, 690),  # row0, row1, col0, col1
)
print(f"Wrote {OUT}")
