#!/usr/bin/env python3
"""phase4_check.py - Phase-4 gating assertion.

Walks an extractor's results directory and refuses to mark a chart done
while its run_meta.json self-reports a gap. A "gap" is any of:

  1. "NOT extracted" (or "not extracted") appearing in any string field
     of the metadata (typical in `method` and `note`).
  2. A top-level field named `known_undercount`.
  3. A `declared_series_count` that disagrees with `rendered_series_count`
     (when both are present).

The intent: an extractor pipeline must call this script at the end of every
run. A non-zero exit means at least one chart should be re-looped through
Phase 3 to repair the gap, not shipped.

Usage:
    python3 scoring/phase4_check.py <results_root>
    python3 scoring/phase4_check.py extractors/graph-data-extraction/results-v2

Optional flags:
    --strict       any failure → exit 1 (default)
    --warn-only    print failures but exit 0
    --meta-name N  filename to look for (default: run_meta.json,
                   falls back to run3_meta.json for compatibility)

Output: one line per chart with PASS / FAIL / MISSING, then a summary.
"""
import argparse
import json
import os
import sys

NOT_EXTRACTED_TOKENS = ("not extracted",)


def _walk_strings(obj):
    """Yield every string value in a nested dict/list structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def check_meta(meta):
    """Return list of failure reasons (empty list = pass)."""
    reasons = []
    for s in _walk_strings(meta):
        sl = s.lower()
        for tok in NOT_EXTRACTED_TOKENS:
            if tok in sl:
                reasons.append(f"'{tok}' string in metadata: {s!r}")
                break
    if "known_undercount" in meta:
        reasons.append(f"known_undercount: {meta['known_undercount']!r}")
    d = meta.get("declared_series_count")
    r = meta.get("rendered_series_count")
    if d is not None and r is not None and d != r:
        reasons.append(f"declared_series_count={d} != rendered_series_count={r}")
    return reasons


def find_meta(chart_dir, meta_name):
    candidates = [meta_name, "run_meta.json", "run3_meta.json"]
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        p = os.path.join(chart_dir, c)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("results_root",
                    help="Path to results dir (e.g. extractors/X/results-v2)")
    ap.add_argument("--meta-name", default="run_meta.json",
                    help="Preferred metadata filename (default: run_meta.json)")
    ap.add_argument("--warn-only", action="store_true",
                    help="Print failures but exit 0")
    args = ap.parse_args()

    root = os.path.abspath(args.results_root)
    if not os.path.isdir(root):
        print(f"Not a directory: {root}", file=sys.stderr)
        sys.exit(2)

    chart_dirs = []
    for corpus in sorted(os.listdir(root)):
        cpath = os.path.join(root, corpus)
        if not os.path.isdir(cpath):
            continue
        for chart in sorted(os.listdir(cpath)):
            chpath = os.path.join(cpath, chart)
            if os.path.isdir(chpath):
                chart_dirs.append((corpus, chart, chpath))

    if not chart_dirs:
        print(f"No chart directories under {root}", file=sys.stderr)
        sys.exit(2)

    n_pass = n_fail = n_missing = 0
    print(f"Phase-4 gate over {root}")
    print(f"{'corpus':<25} {'chart':<12} {'status':<8} reason")
    print("-" * 80)
    for corpus, chart, chpath in chart_dirs:
        meta_path = find_meta(chpath, args.meta_name)
        if not meta_path:
            print(f"{corpus:<25} {chart:<12} MISSING  no metadata file found")
            n_missing += 1
            continue
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except json.JSONDecodeError as e:
            print(f"{corpus:<25} {chart:<12} FAIL     unparseable meta: {e}")
            n_fail += 1
            continue
        reasons = check_meta(meta)
        if not reasons:
            print(f"{corpus:<25} {chart:<12} PASS     -")
            n_pass += 1
        else:
            for i, r in enumerate(reasons):
                tag = "FAIL" if i == 0 else "    "
                col = chart if i == 0 else ""
                cor = corpus if i == 0 else ""
                print(f"{cor:<25} {col:<12} {tag:<8} {r}")
            n_fail += 1

    print("-" * 80)
    total = n_pass + n_fail + n_missing
    print(f"PASS {n_pass}/{total}   FAIL {n_fail}/{total}   MISSING {n_missing}/{total}")
    if n_fail or n_missing:
        if args.warn_only:
            print("(warn-only: returning 0 anyway)")
            sys.exit(0)
        sys.exit(1)


if __name__ == "__main__":
    main()
