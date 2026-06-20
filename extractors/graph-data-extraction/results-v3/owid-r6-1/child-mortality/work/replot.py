"""Re-plot extracted data and produce overlay vs original."""
import csv
import matplotlib.pyplot as plt
import numpy as np
import cv2

CSV = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality/data.csv"
IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/owid-r6-1/charts/child-mortality/image.png"
OUT_DIR = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v3/owid-r6-1/child-mortality"

# Read CSV
years = []
data = {}
with open(CSV) as f:
    rdr = csv.reader(f)
    header = next(rdr)
    cols = header[1:]
    for c in cols: data[c] = []
    for row in rdr:
        years.append(int(row[0]))
        for c, v in zip(cols, row[1:]):
            data[c].append(float(v) if v else np.nan)

years = np.array(years)
COLORS = {
    "Ghana":          "#916E2D",  # we'll use the BGR-derived RGB
    "India":          "#4C8C2C",
    "Brazil":         "#062941",
    "United States":  "#8A3D46",
    "United Kingdom": "#996D39",
    "France":         "#B22222",
    "Sweden":         "#4C6E9C",
}

# Use the actual sampled colors from the chart (BGR -> RGB)
RGB = {
    "Ghana":          (145/255, 62/255, 109/255),     # actually BGR was (109,62,145) => RGB (145,62,109)
    "India":          (44/255, 132/255, 101/255),     # BGR (44,132,101) => RGB (101,132,44)? wait
    "Brazil":         (91/255, 41/255, 0/255),        # BGR (0,41,91) => RGB (91,41,0)
    "United States":  (70/255, 61/255, 143/255),      # BGR(143,61,70) RGB(70,61,143)
    "United Kingdom": (57/255, 109/255, 153/255),     # BGR(153,109,57) RGB(57,109,153)
    "France":         (7/255, 53/255, 177/255),       # BGR(177,53,7) RGB(7,53,177)
    "Sweden":         (76/255, 106/255, 156/255),     # BGR(156,106,76) RGB(76,106,156)
}
# Correct: cv2 stores BGR, so BGR (B,G,R) => RGB (R,G,B):
RGB = {
    "Ghana":          (145/255, 62/255, 109/255),   # BGR (109,62,145) -> R=145,G=62,B=109 -- purple
    "India":          (44/255, 132/255, 101/255),   # BGR (101,132,44) -> R=44,G=132,B=101 -- green
    "Brazil":         (0/255,  41/255,  91/255),    # BGR (91,41,0)    -> R=0,G=41,B=91 -- navy
    "United States":  (143/255, 61/255, 70/255),    # BGR (70,61,143)  -> R=143,G=61,B=70 -- maroon
    "United Kingdom": (153/255, 109/255, 57/255),   # BGR (57,109,153) -> R=153,G=109,B=57 -- tan
    "France":         (177/255, 53/255, 7/255),     # BGR (7,53,177)   -> R=177,G=53,B=7 -- red
    "Sweden":         (76/255, 106/255, 156/255),   # BGR (156,106,76) -> R=76,G=106,B=156 -- blue
}

fig, ax = plt.subplots(figsize=(8.5, 6))
for c in cols:
    vals = np.array(data[c])
    mask = ~np.isnan(vals)
    if mask.any():
        ax.plot(years[mask], vals[mask], color=RGB[c], lw=1.0, label=c)

ax.set_xlim(1751, 2023)
ax.set_ylim(0, 50)
ax.set_xlabel("Year")
ax.set_ylabel("Child mortality (%)")
ax.set_title("Child mortality — extracted (re-plot)")
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(OUT_DIR + "/replot.png", dpi=150)
fig.savefig(OUT_DIR + "/replot.pdf")
print(f"saved replot.png and replot.pdf")

# Side-by-side comparison
import matplotlib.image as mpimg
orig = mpimg.imread(IMG)
fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 6))
ax1.imshow(orig); ax1.set_title("Original"); ax1.axis("off")
for c in cols:
    vals = np.array(data[c])
    mask = ~np.isnan(vals)
    if mask.any():
        ax2.plot(years[mask], vals[mask], color=RGB[c], lw=1.0, label=c)
ax2.set_xlim(1751, 2023); ax2.set_ylim(0, 50)
ax2.set_xlabel("Year"); ax2.set_ylabel("Child mortality (%)")
ax2.set_title("Extracted re-plot"); ax2.legend(loc="upper right", fontsize=8)
ax2.grid(True, alpha=0.3)
plt.tight_layout()
fig2.savefig(OUT_DIR + "/comparison.png", dpi=120)
print("saved comparison.png")
