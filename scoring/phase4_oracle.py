#!/usr/bin/env python3
"""phase4_oracle.py - ground-truth-free recall gate over a results root.

Companion to phase4_check.py. Where phase4_check.py reads the extractor's
self-reported metadata strings ("NOT extracted", known_undercount), this gate
independently checks that every layer the forward pass DECLARED in its
chart_metadata.json legend is actually present in its data.csv. A chart fails
when it declares a layer it did not emit (the el-94 / el-100 fit-curve gap).

No ground truth is read, so this runs on a fine-tuning corpus that has none.

Usage:
    python3 scoring/phase4_oracle.py <results_root> [--json OUT] [--warn-only]

Example:
    python3 scoring/phase4_oracle.py extractors/graph-data-extraction/results-v3
"""
import argparse
import json
import os
import sys

# Make the repo root importable so `cv_oracle` resolves when run as a script.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from cv_oracle.gate import audit_results_root  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_root", help="e.g. extractors/graph-data-extraction/results-v3")
    ap.add_argument("--json", help="write the full audit report to this path")
    ap.add_argument("--warn-only", action="store_true", help="report failures but exit 0")
    args = ap.parse_args()

    report = audit_results_root(args.results_root)
    t = report["totals"]

    for corpus, charts in report["corpora"].items():
        print(f"=== {corpus} ===")
        for chart, res in charts.items():
            line = f"  {chart:42s} {res['status']:13s}"
            if res["status"] == "FAIL":
                line += f" missing={res['missing_layers']} (declared={res['expected']})"
            elif res["status"] == "AMBIGUOUS":
                line += f" missing={res['missing_layers']} but {res['untyped_rows']} untyped rows present"
            elif res["status"] == "NOT_ASSESSED":
                line += f" ({res.get('reason', '')})"
            print(line)

    print(
        f"\n{t['charts']} charts: {t['pass']} pass, {t['fail']} FAIL, "
        f"{t['ambiguous']} ambiguous, {t['not_assessed']} not-assessed, "
        f"{t['missing_data']} missing-data"
    )

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"wrote {args.json}")

    if t["fail"] and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
