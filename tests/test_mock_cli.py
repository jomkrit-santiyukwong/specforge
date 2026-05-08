from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specforge.cli import app

runner = CliRunner()


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _spec_content() -> str:
    return """type: object
fields:
  id:
    type: integer
    required: true
    minimum: 1
    nullable: false
  status:
    type: string
    required: true
    enum: [PENDING, ACTIVE]
    nullable: false
  nickname:
    type: string
    minLength: 3
    nullable: false
"""


def _case_path(tmp_path: Path, name: str) -> Path:
    return tmp_path / f"{name}.yaml"


@pytest.fixture
def spec_file() -> Path:
    return Path("examples/specs/example.yaml")


def test_mock_cli_minimal_outputs_json_object(tmp_path: Path) -> None:
    spec = _case_path(tmp_path, "minimal")
    _write(spec, _spec_content())

    result = runner.invoke(app, ["mock", "--spec", str(spec), "--mode", "minimal"])

    parsed = json.loads(result.output)
    assert result.exit_code == 0
    assert isinstance(parsed, dict)
    assert set(parsed) == {"id", "status"}
    assert parsed["status"] == "PENDING"
    assert isinstance(parsed["id"], int)


def test_mock_cli_count_outputs_json_array(tmp_path: Path) -> None:
    spec = _case_path(tmp_path, "count")
    _write(spec, _spec_content())

    result = runner.invoke(app, ["mock", "--spec", str(spec), "--count", "3", "--seed", "7"])

    parsed = json.loads(result.output)
    assert result.exit_code == 0
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    assert all(isinstance(item, dict) for item in parsed)
    assert all(set(item) == {"id", "status"} for item in parsed)
    assert all(item["status"] == "PENDING" for item in parsed)


def test_mock_cli_rejects_malformed_spec(tmp_path: Path) -> None:
    spec = _case_path(tmp_path, "malformed")
    _write(spec, "type: object\nfields: [\nbad yaml")

    result = runner.invoke(app, ["mock", "--spec", str(spec)])

    assert result.exit_code == 2
    assert "Could not parse spec file" in result.output


def test_mock_cli_rejects_nonexistent_spec(tmp_path: Path) -> None:
    spec = tmp_path / "missing.yaml"

    result = runner.invoke(app, ["mock", "--spec", str(spec)])

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_mock_cli_seed_is_deterministic(tmp_path: Path) -> None:
    spec = _case_path(tmp_path, "seed")
    _write(spec, _spec_content())

    first = runner.invoke(app, ["mock", "--spec", str(spec), "--mode", "example", "--seed", "19"])
    second = runner.invoke(app, ["mock", "--spec", str(spec), "--mode", "example", "--seed", "19"])
    third = runner.invoke(app, ["mock", "--spec", str(spec), "--mode", "example", "--seed", "20"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert third.exit_code == 0
    assert json.loads(first.output) == json.loads(second.output)
    assert json.loads(first.output) != json.loads(third.output)


def test_mock_cli_full_includes_more_fields_than_minimal(tmp_path: Path) -> None:
    spec = _case_path(tmp_path, "full-vs-minimal")
    _write(spec, _spec_content())

    minimal = runner.invoke(app, ["mock", "--spec", str(spec), "--mode", "minimal", "--seed", "5"])
    full = runner.invoke(app, ["mock", "--spec", str(spec), "--mode", "full", "--seed", "5"])

    minimal_payload = json.loads(minimal.output)
    full_payload = json.loads(full.output)
    assert minimal.exit_code == 0
    assert full.exit_code == 0
    assert len(full_payload) > len(minimal_payload)
    assert "nickname" not in minimal_payload
    assert "nickname" in full_payload
    assert full_payload["status"] in {"PENDING", "ACTIVE"}


def test_mock_cli_rejects_invalid_mode(tmp_path: Path, spec_file: Path) -> None:
    result = runner.invoke(app, ["mock", "--spec", str(spec_file), "--mode", "garbage"])

    assert result.exit_code == 2
    assert "invalid" in result.output.lower()


def test_mock_cli_rejects_count_above_max(tmp_path: Path, spec_file: Path) -> None:
    result = runner.invoke(app, ["mock", "--spec", str(spec_file), "--count", "10001"])

    assert result.exit_code == 2
    assert "invalid value" in result.output.lower() or "out of range" in result.output.lower()


def test_mock_cli_array_min_items_without_items_warns_not_crashes(tmp_path: Path, caplog) -> None:
    import logging

    spec = _case_path(tmp_path, "array-no-items")
    _write(
        spec,
        """type: object
fields:
  items:
    type: array
    required: true
    minItems: 2
""",
    )

    with caplog.at_level(logging.WARNING, logger="specforge.engine.mocker"):
        result = runner.invoke(app, ["mock", "--spec", str(spec)])

    assert result.exit_code == 0
    assert any(
        "no items spec" in record.getMessage()
        for record in caplog.records
    )


def test_mock_cli_count_shapes_are_explicit(tmp_path: Path, spec_file: Path) -> None:
    single_result = runner.invoke(app, ["mock", "--spec", str(spec_file), "--count", "1", "--seed", "7"])
    many_result = runner.invoke(app, ["mock", "--spec", str(spec_file), "--count", "2", "--seed", "7"])

    single_payload = json.loads(single_result.output)
    many_payload = json.loads(many_result.output)

    assert single_result.exit_code == 0
    assert many_result.exit_code == 0
    assert isinstance(single_payload, dict)
    assert isinstance(many_payload, list)
