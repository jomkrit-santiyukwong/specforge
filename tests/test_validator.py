import pytest
from specforge.engine import validator as validator_mod
from specforge.engine.validator import validate
from specforge.models.spec import FieldSpec, SpecFile


def make_spec(**fields) -> SpecFile:
    return SpecFile(fields=fields)


# --- required / missing ---

def test_required_field_missing():
    spec = make_spec(name=FieldSpec(type="string", required=True))
    result = validate(spec, {})
    assert not result.passed
    assert any(f.code == "REQUIRED_MISSING" for f in result.findings)


def test_optional_field_missing_is_ok():
    spec = make_spec(name=FieldSpec(type="string", required=False))
    result = validate(spec, {})
    assert result.passed


# --- type checks ---

def test_type_mismatch():
    spec = make_spec(age=FieldSpec(type="integer", required=True))
    result = validate(spec, {"age": "not-a-number"})
    assert any(f.code == "TYPE_MISMATCH" for f in result.findings)


def test_boolean_not_confused_with_integer():
    spec = make_spec(count=FieldSpec(type="integer", required=True))
    result = validate(spec, {"count": True})
    assert any(f.code == "TYPE_MISMATCH" for f in result.findings)


# --- null ---

def test_null_allowed_by_default():
    spec = make_spec(name=FieldSpec(type="string", required=True, nullable=True))
    result = validate(spec, {"name": None})
    assert result.passed


def test_null_rejected_when_not_nullable():
    spec = make_spec(name=FieldSpec(type="string", required=True, nullable=False))
    result = validate(spec, {"name": None})
    assert any(f.code == "NULL_NOT_ALLOWED" for f in result.findings)


# --- enum ---

def test_enum_valid():
    spec = make_spec(status=FieldSpec(type="string", required=True, enum=["ACTIVE", "CLOSED"]))
    result = validate(spec, {"status": "ACTIVE"})
    assert result.passed


def test_enum_invalid():
    spec = make_spec(status=FieldSpec(type="string", required=True, enum=["ACTIVE", "CLOSED"]))
    result = validate(spec, {"status": "UNKNOWN"})
    assert any(f.code == "ENUM_MISMATCH" for f in result.findings)


# --- string constraints ---

def test_min_length():
    spec = make_spec(code=FieldSpec(type="string", required=True, minLength=3))
    result = validate(spec, {"code": "ab"})
    assert any(f.code == "STRING_TOO_SHORT" for f in result.findings)


def test_max_length():
    spec = make_spec(code=FieldSpec(type="string", required=True, maxLength=5))
    result = validate(spec, {"code": "toolong"})
    assert any(f.code == "STRING_TOO_LONG" for f in result.findings)


def test_pattern_match():
    spec = make_spec(ref=FieldSpec(type="string", required=True, pattern=r"^TX-\d+$"))
    result = validate(spec, {"ref": "TX-12345"})
    assert result.passed


def test_pattern_mismatch():
    spec = make_spec(ref=FieldSpec(type="string", required=True, pattern=r"^TX-\d+$"))
    result = validate(spec, {"ref": "BAD-VALUE"})
    assert any(f.code == "PATTERN_MISMATCH" for f in result.findings)


@pytest.mark.parametrize("fmt,value", [
    ("email", "user@example.com"),
    ("date", "2024-01-15"),
    ("date-time", "2024-01-15T10:30:00"),
])
def test_format_valid_passes(fmt, value):
    spec = make_spec(f=FieldSpec(type="string", required=True, format=fmt))
    assert validate(spec, {"f": value}).passed


@pytest.mark.parametrize("fmt,value", [
    ("email", "not-an-email"),
    ("date", "15/01/2024"),
    ("date-time", "not-a-datetime"),
])
def test_format_invalid_emits_mismatch(fmt, value):
    spec = make_spec(f=FieldSpec(type="string", required=True, format=fmt))
    result = validate(spec, {"f": value})
    assert any(f.code == "FORMAT_MISMATCH" for f in result.findings)


# --- numeric ---

def test_minimum():
    spec = make_spec(amount=FieldSpec(type="number", required=True, minimum=0.01))
    result = validate(spec, {"amount": 0})
    assert any(f.code == "VALUE_TOO_SMALL" for f in result.findings)


def test_maximum():
    spec = make_spec(score=FieldSpec(type="integer", required=True, maximum=100))
    result = validate(spec, {"score": 101})
    assert any(f.code == "VALUE_TOO_LARGE" for f in result.findings)


# --- array ---

def test_array_min_items():
    spec = make_spec(tags=FieldSpec(type="array", required=True, minItems=1))
    result = validate(spec, {"tags": []})
    assert any(f.code == "ARRAY_TOO_SHORT" for f in result.findings)


def test_array_max_items():
    spec = make_spec(tags=FieldSpec(type="array", required=True, maxItems=2))
    result = validate(spec, {"tags": ["a", "b", "c"]})
    assert any(f.code == "ARRAY_TOO_LONG" for f in result.findings)


def test_array_unique_items():
    spec = make_spec(ids=FieldSpec(type="array", required=True, uniqueItems=True))
    result = validate(spec, {"ids": [1, 2, 1]})
    assert any(f.code == "DUPLICATE_ITEMS" for f in result.findings)


def test_array_items_type_check():
    spec = make_spec(
        ids=FieldSpec(type="array", required=True, items=FieldSpec(type="integer"))
    )
    result = validate(spec, {"ids": [1, "two", 3]})
    assert any(f.code == "TYPE_MISMATCH" and "[1]" in f.path for f in result.findings)


# --- unexpected fields ---

def test_unexpected_field_is_warning():
    spec = make_spec(name=FieldSpec(type="string"))
    result = validate(spec, {"name": "ok", "extra": "surprise"})
    assert result.passed
    assert any(f.code == "UNEXPECTED_FIELD" and f.severity == "warning" for f in result.findings)


# --- nested object ---

def test_nested_object():
    inner = FieldSpec(type="object", fields={"city": FieldSpec(type="string", required=True)})
    spec = make_spec(address=inner)
    result = validate(spec, {"address": {"city": "Bangkok"}})
    assert result.passed


def test_nested_object_missing_required():
    inner = FieldSpec(type="object", fields={"city": FieldSpec(type="string", required=True)})
    spec = make_spec(address=inner)
    result = validate(spec, {"address": {}})
    assert any(f.code == "REQUIRED_MISSING" and "city" in f.path for f in result.findings)


# --- ReDoS / pattern safety ---

def test_invalid_regex_pattern_rejected_at_spec_load():
    # Invalid patterns are now rejected when the spec model is built,
    # rather than warned about during payload validation.
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError, match="not a valid regex"):
        FieldSpec(type="string", required=True, pattern=r"[invalid")


def test_pattern_too_long_is_warning():
    from specforge.engine.validator import _MAX_PATTERN_LEN
    long_pattern = "a" * (_MAX_PATTERN_LEN + 1)
    spec = make_spec(ref=FieldSpec(type="string", required=True, pattern=long_pattern))
    result = validate(spec, {"ref": "a"})
    assert any(f.code == "INVALID_PATTERN" and f.severity == "warning" for f in result.findings)


def test_pattern_timeout_is_warning(monkeypatch):
    # Force the regex engine to raise TimeoutError so the warning path is exercised.
    # The `regex` library has built-in protection against most catastrophic patterns,
    # so we simulate timeout directly to test the handler.
    from specforge.engine import validator as validator_mod

    def fake_safe_match(pattern: str, value: str) -> bool | None:
        return None  # signals timeout

    monkeypatch.setattr(validator_mod, "_safe_match", fake_safe_match)

    spec = make_spec(ref=FieldSpec(type="string", required=True, pattern=r"^(a+)+$"))
    result = validate(spec, {"ref": "anything"})
    assert any(f.code == "PATTERN_TIMEOUT" and f.severity == "warning" for f in result.findings)


# --- NaN / Infinity ---

def test_nan_rejected_as_number():
    import math
    spec = make_spec(score=FieldSpec(type="number", required=True))
    result = validate(spec, {"score": float("nan")})
    assert any(f.code == "NON_FINITE_NUMBER" for f in result.findings)


def test_infinity_rejected_as_number():
    spec = make_spec(score=FieldSpec(type="number", required=True))
    result = validate(spec, {"score": float("inf")})
    assert any(f.code == "NON_FINITE_NUMBER" for f in result.findings)


# --- date-time format ---

# --- spec model validation ---

def test_object_field_without_fields_raises():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="must define 'fields'"):
        FieldSpec(type="object")


def test_object_field_with_empty_fields_is_valid():
    spec = FieldSpec(type="object", fields={})
    assert spec.fields == {}


def test_spec_file_type_must_be_object():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        from specforge.models.spec import SpecFile
        SpecFile(type="array", fields={})  # type: ignore


# --- constraint domain validation ---

def test_negative_min_length_rejected():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        FieldSpec(type="string", minLength=-1)


def test_inverted_length_bounds_rejected():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="minLength"):
        FieldSpec(type="string", minLength=10, maxLength=5)


def test_inverted_numeric_bounds_rejected():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="minimum"):
        FieldSpec(type="number", minimum=100.0, maximum=1.0)


def test_inverted_array_bounds_rejected():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="minItems"):
        FieldSpec(type="array", items=FieldSpec(type="string"), minItems=5, maxItems=2)


def test_nan_minimum_rejected():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="finite"):
        FieldSpec(type="number", minimum=float("nan"))


def test_inf_maximum_rejected():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="finite"):
        FieldSpec(type="number", maximum=float("inf"))


# --- JSON parser boundary ---

def test_load_payload_rejects_list_root(tmp_path):
    import json
    from specforge.parsers.json_parser import PayloadError, load_payload
    p = tmp_path / "payload.json"
    p.write_text(json.dumps([1, 2, 3]))
    import pytest
    with pytest.raises(PayloadError):
        load_payload(p)


def test_load_payload_rejects_string_root(tmp_path):
    import json
    from specforge.parsers.json_parser import PayloadError, load_payload
    p = tmp_path / "payload.json"
    p.write_text(json.dumps("just a string"))
    import pytest
    with pytest.raises(PayloadError):
        load_payload(p)


# --- PATTERN_SKIPPED ---

def test_pattern_skipped_for_long_input():
    from specforge.engine.validator import _MAX_MATCH_INPUT_LEN
    spec = make_spec(ref=FieldSpec(type="string", required=True, pattern=r"^a+$"))
    value = "a" * (_MAX_MATCH_INPUT_LEN + 1)
    result = validate(spec, {"ref": value})
    assert any(f.code == "PATTERN_SKIPPED" and f.severity == "warning" for f in result.findings)


# --- NaN in JSON report ---

def test_nan_in_report_produces_valid_json(tmp_path):
    import json
    from specforge.models.result import Finding, ValidationResult
    from specforge.reporters.json_reporter import write
    result = ValidationResult(
        passed=False,
        error_count=1,
        warning_count=0,
        findings=[Finding(path="$.score", severity="error", code="NON_FINITE_NUMBER",
                          message="NaN not allowed", actual=float("nan"))],
    )
    out = tmp_path / "report.json"
    write(result, out)
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["findings"][0]["actual"] == "NaN"


# --- depth guard ---

def test_deep_payload_emits_depth_exceeded_not_recursion_error(monkeypatch):
    monkeypatch.setattr(validator_mod, "_MAX_DEPTH", 5)

    def build_spec(d):
        if d == 0:
            return {"type": "string", "nullable": False}
        return {
            "type": "object",
            "required": True,
            "nullable": False,
            "fields": {"inner": build_spec(d - 1)},
        }

    spec = SpecFile.model_validate({"type": "object", "fields": {"root": build_spec(20)}})

    payload = "leaf"
    for _ in range(20):
        payload = {"inner": payload}
    payload = {"root": payload}

    result = validate(spec, payload)
    assert not result.passed
    assert any(f.code == "DEPTH_EXCEEDED" for f in result.findings)


def test_unique_items_detects_duplicate_dicts_unhashable() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "rows": {
                "type": "array",
                "required": True,
                "nullable": False,
                "uniqueItems": True,
                "items": {
                    "type": "object",
                    "nullable": False,
                    "fields": {"k": {"type": "integer", "required": True, "nullable": False}},
                },
            },
        },
    })
    payload = {"rows": [{"k": 1}, {"k": 2}, {"k": 1}]}
    result = validate(spec, payload)
    dup_findings = [f for f in result.findings if f.code == "DUPLICATE_ITEMS"]
    assert len(dup_findings) == 1
    assert dup_findings[0].path == "$.rows[2]"


def test_unique_items_caps_duplicate_findings_at_ten() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "tags": {
                "type": "array",
                "required": True,
                "nullable": False,
                "uniqueItems": True,
                "items": {"type": "integer", "nullable": False},
            },
        },
    })
    payload = {"tags": [1] * 25}
    result = validate(spec, payload)
    dup_findings = [f for f in result.findings if f.code == "DUPLICATE_ITEMS"]
    assert len(dup_findings) == 10  # capped


def test_unique_items_mixed_hashable_then_unhashable_falls_back() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "mixed": {
                "type": "array",
                "required": True,
                "nullable": False,
                "uniqueItems": True,
                "items": {"type": "object", "nullable": False, "fields": {"k": {"type": "integer", "nullable": False}}},
            },
        },
    })
    # First item triggers TypeError on hashable path; fallback to list-equality
    payload = {"mixed": [{"k": 1}, {"k": 2}, {"k": 1}]}
    result = validate(spec, payload)
    dup_findings = [f for f in result.findings if f.code == "DUPLICATE_ITEMS"]
    assert len(dup_findings) == 1
