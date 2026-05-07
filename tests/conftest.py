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
