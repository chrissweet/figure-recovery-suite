#!/usr/bin/env python3
"""
check_artifacts.py - scan an extracted-series CSV for the signatures of
extraction artifacts (legend occlusion, gridline collision) before/after
re-plotting. This is part of the close-the-loop validation step.

Usage:
    python3 check_artifacts.py series.csv                 # checks every value column vs first (x) column
    python3 check_artifacts.py series.csv --monotonic     # also flag non-monotonic series

Reports clamped runs (constant value over several x), spikes (one point far
above both neighbours), and optionally monotonicity violations. A hit almost
always means a legend/gridline occluded that x-span; repair by interpolating
between the clean neighbours, regenerate the CSV, and re-plot.
"""
import argparse, csv, numpy as np


def flag(xs, ys, monotonic=False):
    ys = np.array(ys, float)
    issues = []
    for i in range(len(ys) - 3):
        seg = ys[i:i + 4]
        if np.all(np.isfinite(seg)) and (seg.max() - seg.min()) < 0.5:
            issues.append(f"clamped run ~{seg.mean():.2f} over x={xs[i]}..{xs[i+3]}")
            break
    for i in range(1, len(ys) - 1):
        if np.isfinite(ys[i-1:i+2]).all() and ys[i] > ys[i-1] + 5 and ys[i] > ys[i+1] + 5:
            issues.append(f"spike at x={xs[i]} (y={ys[i]:.1f} vs neighbours {ys[i-1]:.1f},{ys[i+1]:.1f})")
    if monotonic:
        d = np.diff(ys[np.isfinite(ys)])
        if (d > 2).any() and (d < -2).any():
            issues.append("non-monotonic (rises and falls > 2 units); expected monotonic")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvfile")
    ap.add_argument("--monotonic", action="store_true")
    args = ap.parse_args()

    rows = list(csv.reader(open(args.csvfile)))
    header, body = rows[0], rows[1:]
    cols = list(zip(*[[float(c) if c not in ("", None) else np.nan for c in r] for r in body]))
    xs = cols[0]

    any_issue = False
    for j in range(1, len(cols)):
        issues = flag(xs, cols[j], monotonic=args.monotonic)
        name = header[j] if j < len(header) else f"col{j}"
        if issues:
            any_issue = True
            print(f"[{name}]")
            for it in issues:
                print(f"   - {it}")
        else:
            print(f"[{name}] clean")

    if any_issue:
        print("\nLikely occlusion artifacts. Repair the flagged x-spans by linear")
        print("interpolation between clean neighbours, regenerate the CSV, then re-plot.")
    else:
        print("\nNo artifact signatures found. Still compare the re-plot to the source by eye.")


if __name__ == "__main__":
    main()
