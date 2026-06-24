#!/usr/bin/env python3
"""Forward-pass extraction for el-100. Phases 1-3 only. No re-plot/iterate."""
import numpy as np, cv2, csv

IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v4/aedes-aegypti-2014/el-100/image.png"
# wait: image lives in corpora
IMG = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/corpora/aedes-aegypti-2014/charts/el-100/image.png"
OUT = "/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite/extractors/graph-data-extraction/results-v4/aedes-aegypti-2014/el-100/data.csv"

# calibration
def col2x(c): return 0.001318*c - 0.073362
def row2y(r): return -0.04908*r + 27.995901

# plot frame
L, R, T, B = 56, 929, 8, 570
# legend region to exclude (cols >= 745 covers swatches + text on the right)
LEG_COL = 745

im = cv2.imread(IMG)
hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
H, W = im.shape[:2]

def frame_mask(mask):
    m = mask.copy()
    m[:T, :] = 0; m[B+1:, :] = 0
    m[:, :L] = 0; m[:, R+1:] = 0
    m[:, LEG_COL:] = 0  # kill legend on right
    return m

rows = []

# ---------- SCATTER MARKERS ----------
# Blue 24C filled circles
blue = frame_mask(cv2.inRange(hsv, np.array([100,120,40]), np.array([135,255,255])))
# Green 27C filled squares
green = frame_mask(cv2.inRange(hsv, np.array([40,120,40]), np.array([85,255,255])))
# Red 30C filled diamonds (red wraps hue)
red1 = cv2.inRange(hsv, np.array([0,120,40]), np.array([10,255,255]))
red2 = cv2.inRange(hsv, np.array([165,120,40]), np.array([180,255,255]))
red = frame_mask(red1 | red2)

def markers(mask, label, min_area, pitch):
    """k=3 erosion preserves small marker cores; vertical merged stacks (ar>2)
    are split into round(h/pitch) evenly-spaced points."""
    k = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
    core = cv2.erode(mask,k)
    n,_,stats,cent = cv2.connectedComponentsWithStats(core,8)
    pts=[]
    for i in range(1,n):
        a=stats[i,cv2.CC_STAT_AREA]
        w=stats[i,cv2.CC_STAT_WIDTH]; h=stats[i,cv2.CC_STAT_HEIGHT]
        top=stats[i,cv2.CC_STAT_TOP]; left=stats[i,cv2.CC_STAT_LEFT]
        if a<min_area: continue
        cx,cy=cent[i]
        ar = max(w,h)/max(1,min(w,h))
        if h>w and ar>2.0:
            # vertical stack of merged markers -> split by height
            cnt=max(1,round(h/pitch))
            for j in range(cnt):
                ry = top + (j+0.5)*h/cnt
                pts.append((cx,ry,a/cnt))
        elif ar>3.0:
            continue  # horizontal line fragment
        else:
            pts.append((cx,cy,a))
    pts.sort(key=lambda p:p[0])
    print(f"{label}: maskpx={(mask>0).sum()} erode={(core>0).sum()} markers={len(pts)}")
    return pts

bpts = markers(blue,  "24C-scatter", 40, 11)
gpts = markers(green, "27C-scatter", 40, 13)
rpts = markers(red,   "30C-scatter", 25, 10)

for cx,cy,a in bpts:
    rows.append((0,"Scatter Plot","24C",round(col2x(cx),4),round(row2y(cy),3)))
for cx,cy,a in gpts:
    rows.append((1,"Scatter Plot","27C",round(col2x(cx),4),round(row2y(cy),3)))
for cx,cy,a in rpts:
    rows.append((2,"Scatter Plot","30C",round(col2x(cx),4),round(row2y(cy),3)))

# ---------- FIT LINES (trace per column, median row of THIN runs) ----------
def remove_markers(mask, pts, radius):
    """Zero out detected marker blobs so only the thin fit line remains."""
    m = mask.copy()
    for cx,cy,a in pts:
        c0=int(cx-radius); c1=int(cx+radius); r0=int(cy-radius); r1=int(cy+radius)
        m[max(0,r0):r1, max(0,c0):c1] = 0
    return m

def trace(mask, label, series, lidx, ltype, step=6, maxrun=12):
    out=[]
    for c in range(L,LEG_COL,step):
        col = np.where(mask[:,c]>0)[0]
        if len(col)==0: continue
        # keep only thin runs (line thickness), reject wide blocks = leftover markers
        # group contiguous
        groups=[]; start=col[0]; prev=col[0]
        for v in col[1:]:
            if v-prev>2:
                groups.append((start,prev)); start=v
            prev=v
        groups.append((start,prev))
        thin=[(s+e)/2 for s,e in groups if (e-s)<=maxrun]
        if not thin: continue
        r=np.median(thin)
        out.append((c,r))
    print(f"{label}: {len(out)} samples")
    for c,r in out:
        rows.append((lidx,ltype,series,round(col2x(c),4),round(row2y(r),3)))
    return out

blue_line = remove_markers(blue, bpts, 12)
green_line = remove_markers(green, gpts, 14)
red_line = remove_markers(red, rpts, 12)
trace(blue_line, "IF_24C-line", "IF_24C", 3, "Line Graph", maxrun=8)
trace(green_line,"IF_27C-line", "IF_27C", 4, "Line Graph", maxrun=8)
trace(red_line,  "IF_30C-line", "IF_30C", 5, "Line Graph", maxrun=8)

with open(OUT,"w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["layer_idx","layer_type","series","x","y"])
    w.writerows(rows)
print("rows:",len(rows))
