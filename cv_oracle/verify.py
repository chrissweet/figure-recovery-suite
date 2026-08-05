"""Source-indexed recall verifier (the missing middle granularity).

Three checks exist for recall, at three granularities:

  - ``gate.audit_chart``  -- LAYER present/absent. Coarse: it PASSes el-94 even
    when 27C is 16-of-25, because the *layer* is there.
  - ``score_data.py``     -- PER-POINT vs ground truth. Needs GT (offline only).
  - **this module**       -- PER-SERIES COVERAGE, GT-free. Is a *present* series
    fully claimed, or is there series-coloured ink the forward pass never
    accounted for?

It is deliberately **source-indexed**: it enumerates ink in the *source image*
and asks "which of this has no claim near it," the negative-space question a
claim-indexed re-plot is blind to (Analysis-Replot-Loop-Efficacy-2026-06-20).
All work is in the source image's own pixel frame via OpenCV. No matplotlib, no
re-render, no axis rescaling.

Contract, and it is the whole point: this verifier **never writes a claim**. It
subtracts the claims you already made, looks at the residual, and returns a
LOCATED, TYPED discrepancy report. Acting on that report (re-parameterize the
generator and re-run it) is the caller's job -- editing output rows toward the
residual is the recorded off-course failure (Analysis-Feedback-Loop-Off-Course),
the same false-positive import as the V5 reconcile-merge. Generators write
claims; verifiers only flag and localize.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from .calibration import Calibration
from .detect.template import series_mask
from .peel import subtract_curves, subtract_points
from .prepare_canvas import prepare_canvas
from .recover import _hex_to_rgb, _is_number


def _achromatic(rgb, tol: int = 25) -> bool:
    r, g, b = rgb
    return max(abs(r - g), abs(g - b), abs(r - b)) <= tol


def classify_blob(area: int, w: int, h: int, *, min_area: int, stroke_aspect: float, stroke_extent: float) -> str:
    """Glyph (blob-like, a candidate missed marker) vs stroke (elongated, a
    curve fragment, NOT a miss) vs speck (noise below min_area).

    This is the glyph-vs-line discriminator the replot-efficacy analysis called
    for: the negative-space check alone would re-flag erased-curve fragments as
    misses; the shape gate rejects them.
    """
    if area < min_area:
        return "speck"
    aspect = max(w, h) / max(1, min(w, h))
    extent = area / max(1, w * h)
    if aspect >= stroke_aspect or extent < stroke_extent:
        return "stroke"
    return "glyph"


@dataclass
class ResidualBlob:
    x: float           # data coords (centroid), via calibration
    y: float
    col: float         # pixel centroid
    row: float
    area: int
    w: int
    h: int
    aspect: float
    extent: float
    kind: str          # glyph | stroke | speck


@dataclass
class RecallReport:
    series_id: str
    claimed_n: int
    source_glyphs_unclaimed: int          # candidate MISSES (glyph-shaped residual)
    residual_stroke_px: int               # elongated residual ink (likely curve, not a miss)
    density: dict                         # stable convergence signal for the loop
    blobs: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _density_4stat(mask: np.ndarray, stats: np.ndarray) -> dict:
    """The convergence signal that actually worked in the off-course branch:
    per-series px count, component count, area p90, area max. More stable across
    re-runs than per-pixel diff (which chases the recall noise floor)."""
    areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, stats.shape[0])] if stats.shape[0] > 1 else []
    return {
        "px": int((mask > 0).sum()),
        "cc": len(areas),
        "area_p90": int(np.percentile(areas, 90)) if areas else 0,
        "area_max": max(areas) if areas else 0,
    }


def verify_series_recall(
    canvas: np.ndarray,
    cal: Calibration,
    rgb,
    claims_px: list[tuple[float, float]],
    curves_px: list[list[tuple[float, float]]] | None = None,
    *,
    series_id: str = "?",
    achromatic: bool | None = None,
    color_tol: float = 60.0,
    erase_radius: int = 8,
    erase_curve_thickness: int = 5,
    min_area: int = 14,
    stroke_aspect: float = 3.0,
    stroke_extent: float = 0.35,
) -> RecallReport:
    """Subtract this series' claims from the canvas, mask the residual by the
    series signature, and report the shaped residual components. Pure diagnosis.
    """
    if achromatic is None:
        achromatic = _achromatic(rgb)
    residual = subtract_points(canvas, claims_px, radius=erase_radius)
    if curves_px:
        residual = subtract_curves(residual, curves_px, thickness=erase_curve_thickness)
    mask = series_mask(residual, rgb, cal.plot_frame_box, achromatic=achromatic, color_tol=color_tol)

    n, _labels, stats, centroids = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    blobs: list[ResidualBlob] = []
    stroke_px = 0
    n_glyph = 0
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        kind = classify_blob(area, w, h, min_area=min_area, stroke_aspect=stroke_aspect, stroke_extent=stroke_extent)
        if kind == "speck":
            continue
        col, row = float(centroids[i][0]), float(centroids[i][1])
        x, y = cal.pixel_to_data(col, row)
        blobs.append(ResidualBlob(
            x=round(x, 6), y=round(y, 6), col=round(col, 1), row=round(row, 1),
            area=area, w=w, h=h,
            aspect=round(max(w, h) / max(1, min(w, h)), 2),
            extent=round(area / max(1, w * h), 3), kind=kind,
        ))
        if kind == "stroke":
            stroke_px += area
        elif kind == "glyph":
            n_glyph += 1
    return RecallReport(
        series_id=series_id,
        claimed_n=len(claims_px),
        source_glyphs_unclaimed=n_glyph,
        residual_stroke_px=stroke_px,
        density=_density_4stat(mask, stats),
        blobs=blobs,
    )


def _point_pixels(rows, cal, series_id) -> list[tuple[float, float]]:
    pts = []
    for r in rows:
        if (r.get("series", "") != series_id):
            continue
        lt = (r.get("layer_type", "") or "").lower()
        if "line" in lt or "spline" in lt or "error" in lt or "errbar" in lt:
            continue
        if _is_number(r.get("x")) and _is_number(r.get("y")):
            pts.append(cal.data_to_pixel(float(r["x"]), float(r["y"])))
    return pts


def _curve_polylines(rows, cal) -> list[list[tuple[float, float]]]:
    by_series: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        lt = (r.get("layer_type", "") or "").lower()
        if ("line" in lt or "spline" in lt) and _is_number(r.get("x")) and _is_number(r.get("y")):
            by_series.setdefault(r.get("series", ""), []).append((float(r["x"]), float(r["y"])))
    out = []
    for pts in by_series.values():
        pts.sort()
        out.append([cal.data_to_pixel(x, y) for x, y in pts])
    return out


def verify_recall(
    image_path: str,
    calibration_path: str,
    metadata_path: str,
    data_csv: str,
    *,
    pad: int = 2,
    subtract_claimed_curves: bool = True,
    **params,
) -> list[RecallReport]:
    """Per-series recall report for every declared marker series in a chart.

    Reads only the image, calibration, metadata and the extractor's own
    data.csv -- all GT-free. Returns one RecallReport per marker series.
    """
    cal = Calibration.from_calibration_file(calibration_path)
    meta = json.load(open(metadata_path))
    canvas = prepare_canvas(image_path, calibration_path, pad=pad)
    rows = list(csv.DictReader(open(data_csv)))
    curves = _curve_polylines(rows, cal) if subtract_claimed_curves else None

    reports = []
    for entry in meta.get("series_legend", []):
        if not entry.get("marker_shape") or not entry.get("color"):
            continue
        sid = entry.get("series_id", "?")
        claims = _point_pixels(rows, cal, sid)
        rgb = _hex_to_rgb(entry["color"])
        reports.append(verify_series_recall(
            canvas, cal, rgb, claims, curves, series_id=sid, **params,
        ))
    return reports
