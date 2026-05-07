import json

from typer.testing import CliRunner

from specforge.cli import app

runner = CliRunner()


def _write(path, content):
    path.write_text(content, encoding="utf-8")


def test_diff_identical_specs_reports_no_changes(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    content = "type: object\nfields:\n  name:\n    type: string\n    required: true\n"
    _write(old, content)
    _write(new, content)

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new)])

    assert result.exit_code == 0
    assert "No changes detected" in result.output


def test_diff_breaking_change_fails_with_flag(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    _write(old, "type: object\nfields:\n  name:\n    type: string\n    required: true\n")
    _write(new, "type: object\nfields: {}\n")

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new), "--fail-on-breaking"])

    assert result.exit_code == 1


def test_diff_breaking_change_passes_without_flag(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    _write(old, "type: object\nfields:\n  name:\n    type: string\n    required: true\n")
    _write(new, "type: object\nfields: {}\n")

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new)])

    assert result.exit_code == 0


def test_diff_json_format_outputs_valid_json(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    content = "type: object\nfields:\n  name:\n    type: string\n    required: true\n"
    _write(old, content)
    _write(new, content)

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new), "--format", "json"])

    parsed = json.loads(result.output)
    assert result.exit_code == 0
    assert "findings" in parsed


def test_diff_markdown_format_outputs_report(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    content = "type: object\nfields:\n  name:\n    type: string\n    required: true\n"
    _write(old, content)
    _write(new, content)

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new), "--format", "markdown"])

    assert result.exit_code == 0
    assert "# Spec Diff Report" in result.output
    assert "## Summary" in result.output
    assert "| Breaking |" in result.output


def test_diff_rejects_missing_old_file(tmp_path):
    old = tmp_path / "missing.yaml"
    new = tmp_path / "new.yaml"
    _write(new, "type: object\nfields: {}\n")

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new)])

    assert result.exit_code == 2


def test_diff_rejects_missing_new_file(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "missing.yaml"
    _write(old, "type: object\nfields: {}\n")

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new)])

    assert result.exit_code == 2


def test_diff_rejects_invalid_format(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    content = "type: object\nfields:\n  name:\n    type: string\n    required: true\n"
    _write(old, content)
    _write(new, content)

    result = runner.invoke(app, ["diff", "--old", str(old), "--new", str(new), "--format", "garbage"])

    assert result.exit_code == 2


def test_diff_requires_old_flag(tmp_path):
    new = tmp_path / "new.yaml"
    new.write_text("type: object\nfields: {}\n", encoding="utf-8")
    result = runner.invoke(app, ["diff", "--new", str(new)])
    assert result.exit_code == 2


def test_diff_requires_new_flag(tmp_path):
    old = tmp_path / "old.yaml"
    old.write_text("type: object\nfields: {}\n", encoding="utf-8")
    result = runner.invoke(app, ["diff", "--old", str(old)])
    assert result.exit_code == 2
