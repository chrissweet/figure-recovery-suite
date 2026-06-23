"""Shared fixtures: repo paths and the el-94 thin-slice fixture."""

import os

import pytest

# cv_oracle/tests/conftest.py -> repo root is two levels up.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def repo_path(*parts: str) -> str:
    return os.path.join(REPO_ROOT, *parts)


@pytest.fixture
def repo_root() -> str:
    return REPO_ROOT


@pytest.fixture
def el94():
    """Paths for the el-94 thin-slice fixture (aedes-aegypti-2014)."""
    corpus = repo_path("corpora", "aedes-aegypti-2014", "charts", "el-94")
    ext = repo_path("extractors", "graph-data-extraction")
    return {
        "image": os.path.join(corpus, "image.png"),
        "ground_truth": os.path.join(corpus, "ground_truth.csv"),
        "calibration": os.path.join(ext, "results-v3", "aedes-aegypti-2014", "el-94", "calibration.json"),
        "data_v1": os.path.join(ext, "results", "aedes-aegypti-2014", "el-94", "data.csv"),
        "data_v2": os.path.join(ext, "results-v2", "aedes-aegypti-2014", "el-94", "data.csv"),
        "data_v3": os.path.join(ext, "results-v3", "aedes-aegypti-2014", "el-94", "data.csv"),
    }
