from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from typer.testing import CliRunner

from specforge.cli import app
from specforge.parsers.yaml_parser import load_spec

runner = CliRunner()
HEADERS = (
    "field_name",
    "type",
    "required",
    "nullable",
    "description",
    "item_type",
    "format",
    "enum",
    "default",
    "min_length",
    "max_length",
    "pattern",
    "minimum",
    "maximum",
    "min_items",
    "max_items",
    "unique_items",
)


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8", newline="")
    return path


def _csv(*rows: str) -> str:
    return "\n".join((",".join(HEADERS), *rows, ""))


def _row(**values: str) -> str:
    return ",".join(values.get(header, "") for header in HEADERS)


def _case_path(name: str, suffix: str) -> Path:
    return Path(f"import-csv-cli-{uuid4().hex}-{name}{suffix}")


def test_import_csv_writes_yaml_file_and_loads_with_existing_parser() -> None:
    input_file = Path("examples/specs/import_csv_sample.csv")
    output_file = _case_path("spec", ".yaml")

    result = runner.invoke(app, ["import-csv", "--input", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()
    assert load_spec(output_file).type == "object"


def test_import_csv_golden_path_matches_expected_yaml_shape() -> None:
    input_file = Path("examples/specs/import_csv_sample.csv")
    output_file = _case_path("golden", ".yaml")
    expected = Path("examples/specs/import_csv_sample.expected.yaml").read_text(encoding="utf-8")

    result = runner.invoke(app, ["import-csv", "--input", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 0
    assert output_file.read_text(encoding="utf-8") == expected


def test_import_csv_missing_input_file_exits_2() -> None:
    missing = _case_path("missing", ".csv")

    result = runner.invoke(app, ["import-csv", "--input", str(missing)])

    assert result.exit_code == 2


def test_import_csv_malformed_headers_exit_2() -> None:
    input_file = _write_csv(_case_path("bad-headers", ".csv"), "field_name,required\nname,true\n")

    result = runner.invoke(app, ["import-csv", "--input", str(input_file)])

    assert result.exit_code == 2
    assert "Missing required CSV header" in result.output


def test_import_csv_path_conflict_exit_2() -> None:
    input_file = _write_csv(
        _case_path("path-conflict", ".csv"),
        _csv(
            _row(field_name="address.street", type="string", required="true", nullable="false"),
            _row(field_name="address", type="string", required="true", nullable="false"),
        ),
    )

    result = runner.invoke(app, ["import-csv", "--input", str(input_file)])

    assert result.exit_code == 2
    assert "already used as a parent object" in result.output


def test_import_csv_nonexistent_output_dir_exit_2() -> None:
    input_file = Path("examples/specs/import_csv_sample.csv")
    output_file = Path(f"import-csv-cli-{uuid4().hex}-missing") / "spec.yaml"

    result = runner.invoke(app, ["import-csv", "--input", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 2
    assert "Could not write spec file" in result.output


def test_import_csv_without_output_prints_yaml_to_stdout() -> None:
    input_file = Path("examples/specs/import_csv_sample.csv")
    expected = Path("examples/specs/import_csv_sample.expected.yaml").read_text(encoding="utf-8")

    result = runner.invoke(app, ["import-csv", "--input", str(input_file)])

    assert result.exit_code == 0
    assert result.output == expected
