"""Security and DoS-defense tests covering recent hardening fixes."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from specforge.cli import app
from specforge.parsers import json_parser, yaml_parser
from specforge.parsers.json_parser import PayloadTooLargeError, load_payload
from specforge.parsers.yaml_parser import SpecFileTooLargeError, load_spec

runner = CliRunner()


# --- YAML safe-mode (#13) ------------------------------------------------

def test_yaml_load_rejects_python_object_tag(tmp_path: Path) -> None:
    """Safe-mode loader must reject !!python tags that could execute code on load."""
    spec = tmp_path / f"security-evil-{uuid4().hex}.yaml"
    spec.write_text(
        "type: object\n"
        "fields:\n"
        "  pwned: !!python/object/apply:os.system [\"echo hacked\"]\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception) as exc:
        load_spec(spec)
    assert "python" in str(exc.value).lower() or "constructor" in str(exc.value).lower() \
        or "tag" in str(exc.value).lower()


# --- File size limits (#12) ----------------------------------------------

def test_load_spec_rejects_oversized_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(yaml_parser, "_MAX_SPEC_BYTES", 100)
    spec = tmp_path / f"security-spec-{uuid4().hex}.yaml"
    spec.write_text("type: object\nfields:\n" + ("  f: {type: string}\n" * 50), encoding="utf-8")
    with pytest.raises(SpecFileTooLargeError):
        load_spec(spec)


def test_load_payload_rejects_oversized_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(json_parser, "_MAX_PAYLOAD_BYTES", 50)
    payload = tmp_path / f"security-payload-{uuid4().hex}.json"
    payload.write_text('{"a":"' + "x" * 200 + '"}', encoding="utf-8")
    with pytest.raises(PayloadTooLargeError):
        load_payload(payload)


def test_validate_cli_reports_size_error_gracefully(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(yaml_parser, "_MAX_SPEC_BYTES", 50)
    spec = tmp_path / f"security-spec-{uuid4().hex}.yaml"
    spec.write_text("type: object\nfields:\n" + ("  f: {type: string}\n" * 50), encoding="utf-8")
    payload = tmp_path / f"security-payload-{uuid4().hex}.json"
    payload.write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["validate", "--spec", str(spec), "--input", str(payload)])
    assert result.exit_code == 2
    assert "maximum allowed" in result.output or "bytes" in result.output


# --- CSV/Excel row limits (#12, #19) -------------------------------------

def test_csv_importer_rejects_oversized_file(tmp_path: Path, monkeypatch) -> None:
    from specforge.adapters import csv_schema

    monkeypatch.setattr(csv_schema, "_MAX_CSV_BYTES", 100)
    csv = tmp_path / f"security-csv-{uuid4().hex}.csv"
    csv.write_text(
        "field_name,type,required,nullable,description,item_type,format,enum,default,"
        "min_length,max_length,pattern,minimum,maximum,min_items,max_items,unique_items\n"
        + ("a,string,,,,,,,,,,,,,,,\n" * 30),
        encoding="utf-8",
    )
    with pytest.raises(csv_schema.CSVImportError, match="maximum"):
        from specforge.adapters import import_csv
        import_csv(csv)
