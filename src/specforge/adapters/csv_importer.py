from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from specforge.adapters.csv_mapper import build_spec_tree
from specforge.adapters.csv_schema import CSVImportError, load_csv_rows
from specforge.models.spec import SpecFile


def import_csv(path: Path) -> SpecFile:
    try:
        rows = load_csv_rows(path)
        spec_data = build_spec_tree(rows)
        return SpecFile.model_validate(spec_data)
    except ValidationError as exc:
        raise CSVImportError(f"Generated spec is invalid:\n{exc}") from exc
