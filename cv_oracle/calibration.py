"""Section 1: deterministic pixel<->data calibration.

Loads the linear axis calibration that the forward pass already wrote
(extractors/.../<chart>/calibration.json: value = m * pixel + b) and provides
pixel<->data conversion. Adds two capabilities the existing calibration does
not encode:

  - log-axis transform (synthetic-04-log-y, owid population/co2 are log-y),
  - categorical-x snap (bar centroids drift off integer ticks: el-62/el-80
    decode {24,27,30} as {23.34,26.33,29.34}).

A 4-point affine path with a no-rotation snap (WebPlotDigitizer technique) is
provided for future rotated/skewed axes but is *not* on the critical path: all
corpus charts today are axis-aligned, so the default path is the linear m/b fit.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


@dataclass
class Axis:
    """One axis: data_value = m * pixel + b, optionally in log10 space."""

    m: float
    b: float
    log: bool = False

    def to_data(self, pixel: float) -> float:
        v = self.m * pixel + self.b
        return 10.0 ** v if self.log else v

    def to_pixel(self, value: float) -> float:
        v = math.log10(value) if self.log else value
        return (v - self.b) / self.m


class Calibration:
    """Pixel<->data mapping for an axis-aligned chart.

    Construct from a forward-pass ``calibration.json`` dict via
    :meth:`from_calibration_json`, or directly from two :class:`Axis` objects.
    """

    def __init__(self, x_axis: Axis, y_axis: Axis, plot_frame_box: dict | None = None):
        self.x = x_axis
        self.y = y_axis
        self.plot_frame_box = plot_frame_box or {}

    # ---- construction -----------------------------------------------------

    @classmethod
    def from_calibration_json(cls, cal: dict, *, log_x: bool | None = None, log_y: bool | None = None) -> "Calibration":
        """Build from the schema written by the forward pass.

        The ``formula`` convention is NOT consistent across charts:

          - most store ``value = m * pixel + b`` (m ~ data-per-pixel, small),
          - some store ``col = b + m * value`` (m ~ pixel-per-data, large),
          - log axes store ``value = 10 ** (m * pixel + b)``.

        We normalize every axis to ``value = m * pixel + b`` (in log space when
        the axis is log). Direction and log-scale are auto-detected from the
        formula string; ``log_x`` / ``log_y`` override the detection if given.
        """
        ac = cal["axis_calibration"]
        x = cls._axis_from_dict(ac["x_axis"], log_override=log_x)
        y = cls._axis_from_dict(ac["y_axis"], log_override=log_y)
        return cls(x, y, cal.get("plot_frame_box"))

    # Tokens that, as the formula's left-hand side, mean it is written
    # pixel-as-a-function-of-value (inverted) rather than value-of-pixel.
    _PIXEL_LHS = {"col", "row", "px_col", "px_row", "pixel_col", "pixel_row", "pixel", "px"}

    @classmethod
    def _axis_from_dict(cls, ax: dict, *, log_override: bool | None) -> Axis:
        m = float(ax["m"])
        b = float(ax["b"])
        formula = str(ax.get("formula", ""))
        lhs = formula.split("=", 1)[0].strip().lower() if "=" in formula else ""
        inverted = lhs in cls._PIXEL_LHS
        if log_override is None:
            log = "log10" in str(ax.get("scale", "")).lower() or "10**" in formula or "10 **" in formula
        else:
            log = log_override
        if inverted:
            # stored: pixel = m*value + b  ->  value = (pixel - b)/m = (1/m)*pixel - b/m
            m, b = 1.0 / m, -b / m
        return Axis(m=m, b=b, log=log)

    @classmethod
    def from_calibration_file(cls, path: str, *, log_x: bool | None = None, log_y: bool | None = None) -> "Calibration":
        with open(path) as fh:
            return cls.from_calibration_json(json.load(fh), log_x=log_x, log_y=log_y)

    # ---- conversion -------------------------------------------------------

    def pixel_to_data(self, col: float, row: float) -> tuple[float, float]:
        return self.x.to_data(col), self.y.to_data(row)

    def data_to_pixel(self, x: float, y: float) -> tuple[float, float]:
        return self.x.to_pixel(x), self.y.to_pixel(y)


def snap_categorical_x(x: float, ticks: list[float], max_frac: float = 0.5) -> float:
    """Snap a continuous x to the nearest categorical tick.

    Returns the nearest tick when the offset is within ``max_frac`` of the local
    tick spacing; otherwise returns ``x`` unchanged. This corrects the bar-x
    drift documented for el-62/el-80 (e.g. 23.34 -> 24) without disturbing
    genuinely off-tick values.
    """
    if not ticks:
        return x
    ticks = sorted(ticks)
    nearest = min(ticks, key=lambda t: abs(t - x))
    # local spacing = distance to the closest *other* tick (half-group width).
    others = [t for t in ticks if t != nearest]
    if not others:
        spacing = abs(nearest) or 1.0
    else:
        spacing = min(abs(t - nearest) for t in others)
    if abs(x - nearest) <= max_frac * spacing:
        return float(nearest)
    return x
