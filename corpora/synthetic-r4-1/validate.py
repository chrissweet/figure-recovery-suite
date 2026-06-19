#!/usr/bin/env python3
"""Validate the synthetic-r4-1 harness by copying GT into a fake extractor
location and running the existing verifier + scorer against it.

If the harness is correct, the verifier should PASS everything (GT data
is at the right pixels by construction) and the scorer should report
F1 = 1.0. Anything else reveals a verifier bug, a scorer assumption that
doesn't survive synthetic data, or a harness bug.
"""
import csv
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CORPUS = "synthetic-r4-1"
EXTRACTOR = "ground-truth-self"


def find_charts():
    p = os.path.join(HERE, "charts")
    return sorted(d for d in os.listdir(p)
                  if os.path.isdir(os.path.join(p, d)))


def chart_metadata_from_synth_meta(meta):
    """Adapt the synthetic metadata.json to the chart_metadata.json schema
    that scoring/verify_artifacts.py reads (only `series_legend[].color` is
    consumed today, but keep the rest for honest provenance)."""
    return {
        "panel_id": meta.get("panel_id"),
        "source_citation": None,
        "x_axis": {
            "title": meta.get("x_axis_title"),
            "unit": meta.get("x_axis_unit"),
            "title_verbatim": meta.get("x_axis_title"),
            "decimal_separator": meta.get("decimal_separator", "."),
        },
        "y_axis": {
            "title": meta.get("y_axis_title"),
            "unit": meta.get("y_axis_unit"),
            "title_verbatim": meta.get("y_axis_title"),
            "decimal_separator": meta.get("decimal_separator", "."),
        },
        "series_legend": meta.get("series_legend", []),
        "chart_title": meta.get("chart_title"),
        "notes": (f"Synthetic chart (generator: "
                   f"{os.path.basename(meta.get('generator', '?'))}, "
                   f"seed: {meta.get('seed')}). "
                   f"Feature stressed: {meta.get('feature_stressed', '?')}."),
    }


def materialise_fake_extractor():
    """For each synthetic chart, build the fake-extractor result dir."""
    fake_root = os.path.join(REPO, "extractors", EXTRACTOR, "results-v3",
                              CORPUS)
    os.makedirs(fake_root, exist_ok=True)
    for chart in find_charts():
        src_chart = os.path.join(HERE, "charts", chart)
        dst_chart = os.path.join(fake_root, chart)
        os.makedirs(dst_chart, exist_ok=True)
        # data.csv  = ground_truth.csv (layered)
        shutil.copy(os.path.join(src_chart, "ground_truth.csv"),
                     os.path.join(dst_chart, "data.csv"))
        # calibration.json = ground_truth_calibration.json
        shutil.copy(os.path.join(src_chart, "ground_truth_calibration.json"),
                     os.path.join(dst_chart, "calibration.json"))
        # chart_metadata.json adapted from metadata.json
        with open(os.path.join(src_chart, "metadata.json")) as f:
            meta = json.load(f)
        with open(os.path.join(dst_chart, "chart_metadata.json"), "w") as f:
            json.dump(chart_metadata_from_synth_meta(meta), f, indent=2)
    return fake_root


def run(cmd):
    """Run a command, capture both stdout and exit code, print compactly."""
    print(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr[:400])
    return r.returncode, r.stdout


def main():
    fake_root = materialise_fake_extractor()
    print(f"fake extractor at: {fake_root}\n")

    print("=" * 70)
    print("1. verify_artifacts.py on synthetic corpus (GT-as-extractor)")
    print("=" * 70)
    # The verifier expects <results_root>/<corpus>/<chart>, so pass the
    # results-v3 parent and let it walk into synthetic-r4-1.
    rc1, _ = run(["python3", "scoring/verify_artifacts.py",
                   os.path.relpath(os.path.dirname(fake_root), REPO),
                   "--warn-only", "--no-overlay"])

    print("=" * 70)
    print("2. score_data.py on synthetic corpus (should be F1 = 1.0)")
    print("=" * 70)
    rc2, _ = run(["python3", "scoring/score_data.py", CORPUS, EXTRACTOR,
                   "--results-dir", "results-v3"])

    print("\nSummary")
    print(f"  verify_artifacts exit: {rc1}")
    print(f"  score_data exit:       {rc2}")


if __name__ == "__main__":
    main()
