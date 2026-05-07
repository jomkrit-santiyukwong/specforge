from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from typer.testing import CliRunner

from specforge.cli import app
from specforge.parsers.yaml_parser import load_spec

runner = CliRunner()

HEADERS = (
    "field_name", "type", "required", "nullable", "description",
    "item_type", "format", "enum", "default",
    "min_length", "max_length", "pattern",
    "minimum", "maximum",
    "min_items", "max_items", "unique_items",
)


def _write_xlsx(name: str, rows: list[dict]) -> Path:
    path = Path(f"import-excel-cli-{uuid4().hex}-{name}.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(HEADERS))
    for row in rows:
        ws.append([row.get(h, None) for h in HEADERS])
    wb.save(path)
    return path


def _case_path(name: str, suffix: str) -> Path:
    return Path(f"import-excel-cli-{uuid4().hex}-{name}{suffix}")


def test_import_excel_writes_yaml_and_loads_with_existing_parser() -> None:
    input_file = Path("examples/specs/import_excel_sample.xlsx")
    output_file = _case_path("spec", ".yaml")

    result = runner.invoke(app, ["import-excel", "--input", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()
    assert load_spec(output_file).type == "object"


def test_import_excel_golden_path_matches_expected_yaml() -> None:
    input_file = Path("examples/specs/import_excel_sample.xlsx")
    output_file = _case_path("golden", ".yaml")
    expected = Path("examples/specs/import_excel_sample.expected.yaml").read_text(encoding="utf-8")

    result = runner.invoke(app, ["import-excel", "--input", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 0
    assert output_file.read_text(encoding="utf-8") == expected


def test_import_excel_missing_input_file_exits_2() -> None:
    missing = _case_path("missing", ".xlsx")

    result = runner.invoke(app, ["import-excel", "--input", str(missing)])

    assert result.exit_code == 2


def test_import_excel_malformed_headers_exit_2() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["field_name", "required"])
    ws.append(["name", "true"])
    input_file = _case_path("bad-headers", ".xlsx")
    wb.save(input_file)

    result = runner.invoke(app, ["import-excel", "--input", str(input_file)])

    assert result.exit_code == 2
    assert "Missing required CSV header" in result.output


def test_import_excel_path_conflict_exits_2() -> None:
    input_file = _write_xlsx("path-conflict", [
        {"field_name": "address.street", "type": "string", "required": "true", "nullable": "false"},
        {"field_name": "address", "type": "string", "required": "true", "nullable": "false"},
    ])

    result = runner.invoke(app, ["import-excel", "--input", str(input_file)])

    assert result.exit_code == 2
    assert "already used as a parent object" in result.output


def test_import_excel_nonexistent_output_dir_exits_2() -> None:
    input_file = Path("examples/specs/import_excel_sample.xlsx")
    output_file = Path(f"import-excel-cli-{uuid4().hex}-missing") / "spec.yaml"

    result = runner.invoke(app, ["import-excel", "--input", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 2
    assert "Could not write spec file" in result.output


def test_import_excel_without_output_prints_yaml_to_stdout() -> None:
    input_file = Path("examples/specs/import_excel_sample.xlsx")
    expected = Path("examples/specs/import_excel_sample.expected.yaml").read_text(encoding="utf-8")

    result = runner.invoke(app, ["import-excel", "--input", str(input_file)])

    assert result.exit_code == 0
    assert result.output == expected
