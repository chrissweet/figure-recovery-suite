"""Command-line access to the cv_oracle tools, for the forward-pass skill.

These wrap the deterministic helpers the pitfalls field guide
(.claude/skills/graph-data-extraction/references/pitfalls-and-recipes.md) points
at, so the MLLM can reach for them by name during extraction. All inputs are
GT-free (image, calibration, chart_metadata); nothing here reads ground truth.

    python3 -m cv_oracle.cli canvas   IMAGE CALIB OUT.png [--pad N]
    python3 -m cv_oracle.cli template IMAGE CALIB '#RRGGBB' [--achromatic] [--thresh 0.55]
    python3 -m cv_oracle.cli peel     IMAGE CALIB METADATA DATA.csv
    python3 -m cv_oracle.cli snap-x   VALUE TICK1,TICK2,...
"""

from __future__ import annotations

import argparse
import csv
import sys

import cv2

from .calibration import Calibration, snap_categorical_x
from .prepare_canvas import prepare_canvas


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _is_achromatic(rgb, tol: int = 25) -> bool:
    r, g, b = rgb
    return max(abs(r - g), abs(g - b), abs(r - b)) <= tol


def _print_csv(rows, fields=("x", "y")) -> None:
    w = csv.writer(sys.stdout)
    w.writerow(fields)
    for r in rows:
        w.writerow([r[f] for f in fields])


def cmd_canvas(a) -> int:
    canvas = prepare_canvas(a.image, a.calibration, pad=a.pad)
    cv2.imwrite(a.out, canvas)
    print(f"wrote {a.out} ({canvas.shape[1]}x{canvas.shape[0]})")
    return 0


def cmd_template(a) -> int:
    from .detect.template import detect_markers_template

    rgb = _hex_to_rgb(a.color)
    achro = a.achromatic or _is_achromatic(rgb)
    cal = Calibration.from_calibration_file(a.calibration)
    canvas = prepare_canvas(a.image, a.calibration)
    pts = detect_markers_template(canvas, cal, rgb, achromatic=achro, score_thresh=a.thresh)
    _print_csv([{"x": round(x, 6), "y": round(y, 6)} for x, y in pts])
    return 0


def cmd_peel(a) -> int:
    from .peel import peel_recover_points

    misses = peel_recover_points(a.image, a.calibration, a.metadata, a.data)
    _print_csv([{"series": m.get("series", ""), "x": m["x"], "y": m["y"]} for m in misses],
               fields=("series", "x", "y"))
    return 0


def cmd_snap_x(a) -> int:
    ticks = [float(t) for t in a.ticks.split(",")]
    print(snap_categorical_x(float(a.value), ticks))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cv_oracle.cli", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("canvas", help="normalized plot canvas (white outside frame + legend)")
    c.add_argument("image"); c.add_argument("calibration"); c.add_argument("out")
    c.add_argument("--pad", type=int, default=0)
    c.set_defaults(func=cmd_canvas)

    t = sub.add_parser("template", help="seeded template-match markers of one series")
    t.add_argument("image"); t.add_argument("calibration"); t.add_argument("color")
    t.add_argument("--achromatic", action="store_true")
    t.add_argument("--thresh", type=float, default=0.55)
    t.set_defaults(func=cmd_template)

    p = sub.add_parser("peel", help="residual markers after subtracting your extraction")
    p.add_argument("image"); p.add_argument("calibration"); p.add_argument("metadata"); p.add_argument("data")
    p.set_defaults(func=cmd_peel)

    s = sub.add_parser("snap-x", help="snap a categorical bar-x to the nearest tick")
    s.add_argument("value"); s.add_argument("ticks")
    s.set_defaults(func=cmd_snap_x)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
