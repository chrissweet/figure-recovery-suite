"""Schema-aware error-bar presence: missing_layers must catch aedes error bars
encoded as columns (y_lo/y_hi/yerr), not just synthetic ErrorBarLayer rows.

Grounded in real forward-pass outputs for el-80:
  - results (v1):    0 error-bar rows (the audit gap)
  - results-v2:      8 via a yerr column
  - results-v3:      8 via y_lo/y_hi columns
  - ground_truth:    8 via error_y_plus/minus columns
"""

import os

from cv_oracle.reconcile import errbar_count, missing_layers
from cv_oracle.run import write_rows_csv
from cv_oracle.tests.conftest import repo_path


def _el80(version):
    return repo_path(
        "extractors", "graph-data-extraction", version, "aedes-aegypti-2014", "el-80", "data.csv"
    )


def test_errbar_count_handles_both_schemas():
    # aedes column schema
    assert errbar_count(_el80("results")) == 0          # v1: no error bars
    assert errbar_count(_el80("results-v2")) == 8        # v2: yerr column
    assert errbar_count(_el80("results-v3")) == 8        # v3: y_lo/y_hi columns
    assert errbar_count(
        repo_path("corpora", "aedes-aegypti-2014", "charts", "el-80", "ground_truth.csv")
    ) == 8                                               # GT: error_y_plus/minus


def test_missing_layers_flags_aedes_errbar_absence(tmp_path):
    # Genuine oracle-style error-bar output (ErrorBarLayer rows).
    cv_csv = os.path.join(tmp_path, "cv_oracle.csv")
    write_rows_csv(
        [
            {"layer_idx": 1, "layer_type": "ErrorBarLayer", "series": "y_err_upper", "x": 24, "y": 64},
            {"layer_idx": 1, "layer_type": "ErrorBarLayer", "series": "y_err_lower", "x": 24, "y": 20},
        ],
        cv_csv,
    )

    # v1 has no error bars (column or row) -> flagged.
    assert missing_layers(cv_csv, _el80("results"))["errbars"]["layer_missing_in_mllm"] is True
    # v2/v3 carry error bars as COLUMNS -> the schema-aware check must NOT flag.
    assert missing_layers(cv_csv, _el80("results-v2"))["errbars"]["layer_missing_in_mllm"] is False
    assert missing_layers(cv_csv, _el80("results-v3"))["errbars"]["layer_missing_in_mllm"] is False


def test_errbar_count_still_counts_errorbarlayer_rows(tmp_path):
    """The synthetic ErrorBarLayer schema must still be counted."""
    p = os.path.join(tmp_path, "eb.csv")
    write_rows_csv(
        [
            {"layer_idx": 1, "layer_type": "ErrorBarLayer", "series": "y_err_upper", "x": 1, "y": 2},
            {"layer_idx": 1, "layer_type": "ErrorBarLayer", "series": "y_err_lower", "x": 1, "y": 0},
            {"layer_idx": 0, "layer_type": "Scatter Plot", "series": "A", "x": 1, "y": 1},
        ],
        p,
    )
    assert errbar_count(p) == 2
