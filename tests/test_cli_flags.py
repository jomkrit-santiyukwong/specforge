"""Tests for CLI-level flags: --version, --quiet, import-excel --sheet."""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from typer.testing import CliRunner

from specforge.cli import app

runner = CliRunner()

_HEADERS = (
    "field_name", "type", "required", "nullable", "description",
    "item_type", "format", "enum", "default",
    "min_length", "max_length", "pattern",
    "minimum", "maximum",
    "min_items", "max_items", "unique_items",
)


# --- --version (#17) -----------------------------------------------------

def test_version_flag_prints_version_and_exits() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "specforge" in result.output.lower()


# --- --quiet (#18) -------------------------------------------------------

def test_quiet_flag_raises_root_logger_level_to_error(tmp_path: Path) -> None:
    spec = tmp_path / f"cli-flags-spec-{uuid4().hex}.yaml"
    spec.write_text(
        "type: object\nfields:\n"
        "  code: {type: string, required: true, nullable: false}\n",
        encoding="utf-8",
    )
    runner.invoke(app, ["--quiet", "mock", "--spec", str(spec), "--mode", "minimal"])
    assert logging.getLogger().level == logging.ERROR
    # restore for other tests
    logging.getLogger().setLevel(logging.WARNING)


# --- import-excel --sheet (#19) ------------------------------------------

def _write_xlsx_two_sheets(path: Path) -> None:
    wb = openpyxl.Workbook()
    default = wb.active
    default.title = "ignored"
    default.append(list(_HEADERS))
    default.append(["a", "string", True, False, "", None, None, None, None,
                    None, None, None, None, None, None, None, None])

    wanted = wb.create_sheet("wanted")
    wanted.append(list(_HEADERS))
    wanted.append(["b", "integer", True, False, "", None, None, None, None,
                   None, None, None, 1, 100, None, None, None])
    wb.save(path)


def test_import_excel_sheet_option_picks_named_sheet(tmp_path: Path) -> None:
    src = tmp_path / f"cli-flags-two-sheets-{uuid4().hex}.xlsx"
    _write_xlsx_two_sheets(src)
    out = tmp_path / f"cli-flags-spec-{uuid4().hex}.yaml"

    result = runner.invoke(app, ["import-excel", "--input", str(src), "--sheet", "wanted", "--output", str(out)])

    assert result.exit_code == 0, result.output
    rendered = out.read_text(encoding="utf-8")
    assert "b:" in rendered
    assert "integer" in rendered
    assert "a:" not in rendered  # 'ignored' sheet's field should NOT be present


def test_import_excel_sheet_option_unknown_sheet_errors(tmp_path: Path) -> None:
    src = tmp_path / f"cli-flags-two-sheets-{uuid4().hex}.xlsx"
    _write_xlsx_two_sheets(src)

    result = runner.invoke(app, ["import-excel", "--input", str(src), "--sheet", "missing"])

    assert result.exit_code == 2
    assert "not found" in result.output.lower()
