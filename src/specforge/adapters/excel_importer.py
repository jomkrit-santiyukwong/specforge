from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from specforge.adapters.csv_mapper import build_spec_tree
from specforge.adapters.csv_schema import (
    CSVFieldRow,
    CSVImportError,
    _parse_row,
    _validate_headers,
)
from specforge.models.spec import SpecFile

_HEADERS = (
    "field_name", "type", "required", "nullable", "description",
    "item_type", "format", "enum", "default",
    "min_length", "max_length", "pattern",
    "minimum", "maximum",
    "min_items", "max_items", "unique_items",
)


def import_excel(path: Path) -> SpecFile:
    try:
        import openpyxl
    except ImportError as exc:
        raise CSVImportError("openpyxl is required for Excel import: pip install openpyxl") from exc

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise CSVImportError(f"Could not open Excel file: {exc}") from exc

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)

    try:
        header_row = next(rows_iter)
    except StopIteration:
        wb.close()
        raise CSVImportError("Excel file is empty")

    headers = [str(h).strip() if h is not None else "" for h in header_row]
    headers = [h for h in headers if h]

    if not headers:
        wb.close()
        raise CSVImportError("Excel file is empty")

    _validate_headers(headers)

    rows: list[CSVFieldRow] = []
    for row_num, raw_row in enumerate(rows_iter, start=2):
        normalized: dict[str, str | None] = {}
        for i, header in enumerate(headers):
            cell_val = raw_row[i] if i < len(raw_row) else None
            if cell_val is None:
                normalized[header] = None
            else:
                s = str(cell_val).strip()
                normalized[header] = s if s else None

        parsed = _parse_row(row_num, normalized)
        if parsed is not None:
            rows.append(parsed)

    wb.close()

    if not rows:
        raise CSVImportError(
            "Excel file has a header but no field rows — at least one non-blank data row is required"
        )

    try:
        spec_data = build_spec_tree(rows)
        return SpecFile.model_validate(spec_data)
    except ValidationError as exc:
        raise CSVImportError(f"Generated spec is invalid:\n{exc}") from exc
