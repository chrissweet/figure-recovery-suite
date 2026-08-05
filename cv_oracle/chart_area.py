"""Step 1: recover the chart (data) area and check it.

Split by what each method is reliable at:
  - CV detects the AXIS SPINES (long dark lines) -> gives left/bottom (and
    top/right when a full box exists) precisely and deterministically.
  - Semantics supplies the edges CV cannot key off (top/right on an L-shaped
    plot) and the legend box, and is robust to layout variety.

The CHECK is CV<->semantic AGREEMENT on the shared spine edges, not self-report:
a spine CV found and the semantic box must coincide within tolerance, or the
area is rejected for review.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Spines:
    left: int | None
    right: int | None
    top: int | None
    bottom: int | None
    strength: dict          # edge -> fraction of the span that is dark ink


def detect_spines(image_path: str, *, dark: int = 160, min_frac: float = 0.5) -> Spines:
    """Find axis spines by dark-ink projection.

    A vertical spine is a column whose dark pixels span >= ``min_frac`` of the
    plausible plot height; a horizontal spine likewise across the width. Returns
    the outermost strong lines (left/right verticals, top/bottom horizontals);
    any edge without a strong line is None (an open, spine-less side).
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    ink = gray < dark

    col_run = _max_run(ink, axis=0)          # longest vertical dark run per column
    row_run = _max_run(ink, axis=1)          # longest horizontal dark run per row
    vcols = np.where(col_run >= min_frac * H)[0]
    hrows = np.where(row_run >= min_frac * W)[0]

    def group_edge(idxs, pick):
        if len(idxs) == 0:
            return None
        # cluster adjacent indices (a spine is a few px thick), pick outermost cluster
        clusters = _cluster(idxs)
        c = clusters[0] if pick == "min" else clusters[-1]
        return int(round(np.mean(c)))

    left = group_edge(vcols, "min")
    right = group_edge(vcols, "max")
    top = group_edge(hrows, "min")
    bottom = group_edge(hrows, "max")
    if right == left:
        right = None
    if top == bottom:
        top = None
    strength = {
        "left": float(col_run[left] / H) if left is not None else 0.0,
        "right": float(col_run[right] / H) if right is not None else 0.0,
        "top": float(row_run[top] / W) if top is not None else 0.0,
        "bottom": float(row_run[bottom] / W) if bottom is not None else 0.0,
    }
    return Spines(left, right, top, bottom, strength)


def _max_run(mask: np.ndarray, axis: int) -> np.ndarray:
    """Longest consecutive-True run along ``axis`` for each line perpendicular."""
    if axis == 0:  # per column, down the rows
        m = mask
        H, W = m.shape
        best = np.zeros(W, np.int32)
        cur = np.zeros(W, np.int32)
        for r in range(H):
            cur = np.where(m[r], cur + 1, 0)
            best = np.maximum(best, cur)
        return best
    else:          # per row, across columns
        return _max_run(mask.T, axis=0)


def _cluster(idxs: np.ndarray, gap: int = 4) -> list[list[int]]:
    out, cur = [], [int(idxs[0])]
    for i in idxs[1:]:
        if i - cur[-1] <= gap:
            cur.append(int(i))
        else:
            out.append(cur); cur = [int(i)]
    out.append(cur)
    return out


def _run_extent(line: np.ndarray) -> tuple[int, int]:
    """(start, end) index of the longest True run in a 1-D boolean line."""
    best_len = best_s = 0
    s = None
    for i, v in enumerate(line):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s > best_len:
                best_len, best_s = i - s, s
            s = None
    if s is not None and len(line) - s > best_len:
        best_len, best_s = len(line) - s, s
    return best_s, best_s + best_len


def chart_area_box(image_path: str, *, dark: int = 160) -> dict:
    """Assemble the data-area rectangle from spines + their extents.

    Left/right/top/bottom come from the spine positions where a spine exists;
    the open sides of an L-shaped plot are taken from the extent of the
    perpendicular spine (top = top of the y-spine's run; right = right end of
    the x-spine's run). Returns the box plus which edges are spine-backed.
    """
    sp = detect_spines(image_path, dark=dark)
    gray = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2GRAY)
    ink = gray < dark
    box, backed = {}, {}
    box["left"] = sp.left if sp.left is not None else 0
    box["bottom"] = sp.bottom if sp.bottom is not None else gray.shape[0] - 1
    backed["left"] = sp.left is not None
    backed["bottom"] = sp.bottom is not None
    # top: top spine if present, else top of the left spine's vertical run
    if sp.top is not None:
        box["top"] = sp.top; backed["top"] = True
    elif sp.left is not None:
        box["top"] = _run_extent(ink[:, sp.left])[0]; backed["top"] = False
    else:
        box["top"] = 0; backed["top"] = False
    # right: right spine if present, else right end of the bottom spine's run
    if sp.right is not None:
        box["right"] = sp.right; backed["right"] = True
    elif sp.bottom is not None:
        box["right"] = _run_extent(ink[sp.bottom, :])[1]; backed["right"] = False
    else:
        box["right"] = gray.shape[1] - 1; backed["right"] = False
    return {"box": box, "spine_backed": backed, "strength": sp.strength}


def draw_box(image_path: str, box: dict, out_path: str, color=(0, 0, 255)) -> None:
    img = cv2.imread(image_path)
    cv2.rectangle(img, (int(box["left"]), int(box["top"])), (int(box["right"]), int(box["bottom"])), color, 2)
    cv2.imwrite(out_path, img)


def _strong_line(gray: np.ndarray, band: tuple, span: tuple, orient: str,
                 min_frac: float, thresholds) -> tuple | None:
    """Best axis-line in a search band. orient 'v' -> vertical line (scan cols in
    band, run down span rows); 'h' -> horizontal. Adaptive over dark thresholds.
    Returns (position, frac) of the strongest line clearing min_frac, else None."""
    a0, a1 = band
    s0, s1 = span
    span_len = max(1, s1 - s0)
    best = None
    for dark in thresholds:
        if orient == "v":
            sub = (gray[s0:s1, a0:a1] < dark)
            runs = _max_run(sub, 0)
        else:
            sub = (gray[a0:a1, s0:s1] < dark)
            runs = _max_run(sub, 1)
        if runs.size == 0:
            continue
        i = int(np.argmax(runs)); frac = runs[i] / span_len
        if best is None or frac > best[1]:
            best = (a0 + i, float(frac))
    if best and best[1] >= min_frac:
        return best
    return None


def snap_box(image_path: str, sem_box: list, *, window: int = 30, min_frac: float = 0.45,
             thresholds=(150, 180, 210), border: int = 8) -> dict:
    """Snap a semantic plot-box's edges to nearby axis lines for pixel precision.

    Semantics gives a robust-but-fuzzy box on ANY chart style; CV snaps each edge
    to the strongest perpendicular ink line within +/- window px, giving spine
    precision where a spine exists and leaving the semantic edge where none does
    (OWID). Lines at the image border are rejected (they are the figure frame,
    not the plot axis)."""
    gray = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    l, t, r, b = (int(round(v)) for v in sem_box)
    out = {"left": l, "top": t, "right": r, "bottom": b}
    src = {}
    # left / right: vertical lines spanning the box height
    for edge, x0 in (("left", l), ("right", r)):
        hit = _strong_line(gray, (max(0, x0 - window), min(W, x0 + window)), (t, b), "v", min_frac, thresholds)
        if hit and border < hit[0] < W - border:
            out[edge] = hit[0]; src[edge] = f"snap({hit[1]:.2f})"
        else:
            src[edge] = "semantic"
    # top / bottom: horizontal lines spanning the box width
    for edge, y0 in (("top", t), ("bottom", b)):
        hit = _strong_line(gray, (max(0, y0 - window), min(H, y0 + window)), (l, r), "h", min_frac, thresholds)
        if hit and border < hit[0] < H - border:
            out[edge] = hit[0]; src[edge] = f"snap({hit[1]:.2f})"
        else:
            src[edge] = "semantic"
    return {"box": out, "edge_source": src}


def clean_canvas(image_path: str, area_box: dict, legend_box: list | None = None, *, pad: int = 1):
    """Keep only the validated data area; white out everything else AND the
    legend. This is the corrected prepare_canvas: the legend is excluded by a
    box that was *checked*, not read from a schema that silently failed."""
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    canvas = np.full_like(img, 255)
    l = max(0, int(area_box["left"]) + pad); r = min(w, int(area_box["right"]) - pad)
    t = max(0, int(area_box["top"]) + pad); b = min(h, int(area_box["bottom"]) - pad)
    canvas[t:b, l:r] = img[t:b, l:r]
    if legend_box:
        ll, lt, lr, lb = (int(round(v)) for v in legend_box)
        canvas[max(0, lt):min(h, lb), max(0, ll):min(w, lr)] = 255
    return canvas


def check_agreement(spines: Spines, box: dict, *, tol: int = 6) -> dict:
    """CV<->semantic gate: every spine CV found strongly must match the box edge."""
    report = {}
    ok = True
    for edge in ("left", "right", "top", "bottom"):
        s = getattr(spines, edge)
        if s is None or spines.strength[edge] < 0.55:
            report[edge] = {"cv_spine": s, "box": box.get(edge), "agree": None}  # no strong spine -> semantic owns it
            continue
        agree = abs(s - box.get(edge, s)) <= tol
        report[edge] = {"cv_spine": s, "box": box.get(edge), "agree": agree}
        ok = ok and agree
    return {"pass": ok, "edges": report}
