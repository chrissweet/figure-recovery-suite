"""cv_oracle: a deterministic computer-vision recall/calibration oracle.

This package reads the *original* chart image (never a reconstruction) and
detects candidate points/curves/error-bars with no knowledge of what the
forward-pass extractor produced. Its job is to surface what the forward pass
*missed* (recall), the half that three regimes of reconstruct-and-compare
never delivered.

Design contract (see /Users/.../plans + CLAUDE.md):
  - import-only: this package never imports the forward-pass extractor, and the
    extractor never imports this package. It can score any extractor.
  - emits the standard ground-truth CSV schema
    (layer_idx, layer_type, series, x, y [, y_lo, y_hi, cap]) in data
    coordinates, so scoring/score_data.py scores it with zero new scorer code.
  - reconciliation produces a *gap report*; it never rewrites a forward-pass
    data.csv.
"""

from .calibration import Calibration

__all__ = ["Calibration"]
