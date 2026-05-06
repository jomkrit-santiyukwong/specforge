import json
import pytest
from typer.testing import CliRunner
from specforge.cli import app

runner = CliRunner()


def _write(path, content):
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def valid_spec(tmp_path):
    p = tmp_path / "spec.yaml"
    _write(p, "type: object\nfields:\n  name:\n    type: string\n    required: true\n")
    return p


@pytest.fixture
def valid_payload(tmp_path):
    p = tmp_path / "payload.json"
    _write(p, json.dumps({"name": "Alice"}))
    return p


def test_validate_passes_with_valid_input(valid_spec, valid_payload):
    result = runner.invoke(app, ["validate", "--spec", str(valid_spec), "--input", str(valid_payload)])
    assert result.exit_code == 0


def test_validate_fails_with_invalid_payload(valid_spec, tmp_path):
    payload = tmp_path / "payload.json"
    _write(payload, json.dumps({}))
    result = runner.invoke(app, ["validate", "--spec", str(valid_spec), "--input", str(payload)])
    assert result.exit_code == 1


def test_validate_rejects_non_object_payload(valid_spec, tmp_path):
    payload = tmp_path / "payload.json"
    _write(payload, json.dumps([1, 2, 3]))
    result = runner.invoke(app, ["validate", "--spec", str(valid_spec), "--input", str(payload)])
    assert result.exit_code == 2
    assert "Payload root must be a JSON object" in result.output


def test_validate_rejects_malformed_json(valid_spec, tmp_path):
    payload = tmp_path / "payload.json"
    _write(payload, "{ not valid json }")
    result = runner.invoke(app, ["validate", "--spec", str(valid_spec), "--input", str(payload)])
    assert result.exit_code == 2
    assert "Could not parse payload file" in result.output


def test_validate_rejects_malformed_yaml(tmp_path, valid_payload):
    spec = tmp_path / "spec.yaml"
    _write(spec, "type: object\nfields: [\nbad yaml")
    result = runner.invoke(app, ["validate", "--spec", str(spec), "--input", str(valid_payload)])
    assert result.exit_code == 2
    assert "Could not parse spec file" in result.output


def test_validate_rejects_invalid_spec_structure(tmp_path, valid_payload):
    spec = tmp_path / "spec.yaml"
    _write(spec, "type: object\nfields:\n  x:\n    type: object\n")  # object without fields
    result = runner.invoke(app, ["validate", "--spec", str(spec), "--input", str(valid_payload)])
    assert result.exit_code == 2
    assert "Invalid spec structure" in result.output


def test_validate_writes_json_report(valid_spec, valid_payload, tmp_path):
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["validate", "--spec", str(valid_spec), "--input", str(valid_payload),
                                  "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["passed"] is True


def test_validate_output_to_nonexistent_dir(valid_spec, valid_payload, tmp_path):
    out = tmp_path / "no_such_dir" / "report.json"
    result = runner.invoke(app, ["validate", "--spec", str(valid_spec), "--input", str(valid_payload),
                                  "--output", str(out)])
    assert result.exit_code == 2
    assert "Could not write report" in result.output
