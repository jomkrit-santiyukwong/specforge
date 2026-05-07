from __future__ import annotations

import shutil
from pathlib import Path

import pytest

_TEST_ARTIFACTS = (
    "spec.yaml",
    "payload.json",
    "report.json",
    "old.yaml",
    "new.yaml",
    "minimal.yaml",
    "count.yaml",
    "malformed.yaml",
    "missing.yaml",
    "seed.yaml",
    "full-vs-minimal.yaml",
    "array-no-items.yaml",
    "no_such_dir",
)

_TEST_GLOB_PATTERNS = (
    "csv-importer-*.csv",
    "import-csv-cli-*.csv",
    "import-csv-cli-*.yaml",
    "excel-importer-*.xlsx",
    "import-excel-cli-*.xlsx",
    "import-excel-cli-*.yaml",
)


@pytest.fixture(autouse=True, scope="session")
def _cleanup_session() -> None:
    root = Path.cwd()
    _cleanup(root)
    yield
    _cleanup(root)


@pytest.fixture
def tmp_path() -> Path:
    root = Path.cwd()
    _cleanup(root)
    yield root
    _cleanup(root)


def _cleanup(root: Path) -> None:
    for name in _TEST_ARTIFACTS:
        path = root / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            try:
                path.unlink()
            except OSError:
                pass
    for pattern in _TEST_GLOB_PATTERNS:
        for path in root.glob(pattern):
            try:
                path.unlink()
            except OSError:
                pass
