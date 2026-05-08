import math
import re
from datetime import date, datetime
from typing import Any

import regex as _regex

from specforge.models.result import Finding, ValidationResult
from specforge.models.spec import FieldSpec, SpecFile

_MAX_PATTERN_LEN = 500
_MAX_MATCH_INPUT_LEN = 10_000
_PATTERN_TIMEOUT_SECONDS = 1.0
_MAX_DEPTH = 64

PatternError = _regex.error


def _safe_match(pattern: str, value: str) -> bool | None:
    """Match `value` against `pattern` using the `regex` library's native timeout.

    Returns True/False on success, None on timeout. Raises `PatternError` for
    invalid patterns (caller turns this into an INVALID_PATTERN finding).
    """
    compiled = _regex.compile(pattern)
    try:
        return bool(compiled.search(value, timeout=_PATTERN_TIMEOUT_SECONDS))
    except TimeoutError:
        return None


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MISSING = object()


def validate(spec: SpecFile, payload: dict) -> ValidationResult:
    findings: list[Finding] = []
    _validate_object(spec.fields, payload, "$", findings, depth=0)
    error_count = sum(1 for f in findings if f.severity == "error")
    warning_count = sum(1 for f in findings if f.severity == "warning")
    return ValidationResult(
        passed=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        findings=findings,
    )


def _validate_object(
    fields: dict[str, FieldSpec], payload: dict, path: str, findings: list[Finding], depth: int
) -> None:
    if depth > _MAX_DEPTH:
        findings.append(Finding(
            path=path,
            severity="error",
            code="DEPTH_EXCEEDED",
            message=f"Payload exceeds maximum nesting depth of {_MAX_DEPTH}",
        ))
        return

    for key in payload:
        if key not in fields:
            findings.append(Finding(
                path=f"{path}.{key}",
                severity="warning",
                code="UNEXPECTED_FIELD",
                message=f"Field '{key}' is not defined in spec",
            ))

    for name, spec in fields.items():
        field_path = f"{path}.{name}"
        value = payload.get(name, _MISSING)

        if value is _MISSING:
            if spec.required:
                findings.append(Finding(
                    path=field_path,
                    severity="error",
                    code="REQUIRED_MISSING",
                    message=f"Required field '{name}' is missing",
                ))
            continue

        _validate_field(spec, value, field_path, findings, depth)


def _validate_field(spec: FieldSpec, value: Any, path: str, findings: list[Finding], depth: int) -> None:
    if value is None:
        if not spec.nullable:
            findings.append(Finding(
                path=path,
                severity="error",
                code="NULL_NOT_ALLOWED",
                message="Field does not allow null",
                actual=None,
            ))
        return

    if not _type_matches(spec.type, value):
        findings.append(Finding(
            path=path,
            severity="error",
            code="TYPE_MISMATCH",
            message=f"Expected type '{spec.type}' but got '{_type_name(value)}'",
            expected=spec.type,
            actual=_type_name(value),
        ))
        return

    if spec.enum is not None and value not in spec.enum:
        findings.append(Finding(
            path=path,
            severity="error",
            code="ENUM_MISMATCH",
            message=f"Value '{value}' is not one of the allowed values",
            expected=spec.enum,
            actual=value,
        ))

    if spec.type == "string":
        _check_string(spec, value, path, findings)
    elif spec.type in ("integer", "number"):
        _check_numeric(spec, value, path, findings)
    elif spec.type == "array":
        _check_array(spec, value, path, findings, depth)
    elif spec.type == "object" and spec.fields:
        _validate_object(spec.fields, value, path, findings, depth + 1)


def _check_string(spec: FieldSpec, value: str, path: str, findings: list[Finding]) -> None:
    if spec.minLength is not None and len(value) < spec.minLength:
        findings.append(Finding(
            path=path,
            severity="error",
            code="STRING_TOO_SHORT",
            message=f"Length {len(value)} is below minimum {spec.minLength}",
            expected=f">={spec.minLength}",
            actual=len(value),
        ))

    if spec.maxLength is not None and len(value) > spec.maxLength:
        findings.append(Finding(
            path=path,
            severity="error",
            code="STRING_TOO_LONG",
            message=f"Length {len(value)} exceeds maximum {spec.maxLength}",
            expected=f"<={spec.maxLength}",
            actual=len(value),
        ))

    if spec.pattern is not None:
        if len(spec.pattern) > _MAX_PATTERN_LEN:
            findings.append(Finding(
                path=path,
                severity="warning",
                code="INVALID_PATTERN",
                message=f"Spec pattern exceeds maximum length of {_MAX_PATTERN_LEN} characters",
            ))
        elif len(value) > _MAX_MATCH_INPUT_LEN:
            findings.append(Finding(
                path=path,
                severity="warning",
                code="PATTERN_SKIPPED",
                message=f"Pattern match skipped: input too long ({len(value)} chars, max {_MAX_MATCH_INPUT_LEN})",
            ))
        else:
            try:
                matched = _safe_match(spec.pattern, value)
                if matched is None:
                    findings.append(Finding(
                        path=path,
                        severity="warning",
                        code="PATTERN_TIMEOUT",
                        message="Pattern match timed out (possible ReDoS pattern in spec)",
                        expected=spec.pattern,
                    ))
                elif not matched:
                    findings.append(Finding(
                        path=path,
                        severity="error",
                        code="PATTERN_MISMATCH",
                        message=f"Value does not match pattern '{spec.pattern}'",
                        expected=spec.pattern,
                        actual=value,
                    ))
            except PatternError as e:
                findings.append(Finding(
                    path=path,
                    severity="warning",
                    code="INVALID_PATTERN",
                    message=f"Spec pattern is invalid regex: {e}",
                ))

    if spec.format == "email":
        if not _EMAIL_RE.match(value):
            findings.append(Finding(
                path=path,
                severity="error",
                code="FORMAT_MISMATCH",
                message="Value is not a valid email address",
                expected="email",
                actual=value,
            ))
    elif spec.format == "date":
        if not _DATE_RE.match(value):
            findings.append(Finding(
                path=path,
                severity="error",
                code="FORMAT_MISMATCH",
                message="Value is not a valid date (expected YYYY-MM-DD)",
                expected="date",
                actual=value,
            ))
        else:
            try:
                date.fromisoformat(value)
            except ValueError:
                findings.append(Finding(
                    path=path,
                    severity="error",
                    code="FORMAT_MISMATCH",
                    message="Value is not a valid date (expected YYYY-MM-DD)",
                    expected="date",
                    actual=value,
                ))
    elif spec.format == "date-time":
        try:
            datetime.fromisoformat(value)
        except ValueError:
            findings.append(Finding(
                path=path,
                severity="error",
                code="FORMAT_MISMATCH",
                message="Value is not a valid date-time (expected ISO 8601)",
                expected="date-time",
                actual=value,
            ))


def _check_numeric(spec: FieldSpec, value: Any, path: str, findings: list[Finding]) -> None:
    if not math.isfinite(value):
        findings.append(Finding(
            path=path,
            severity="error",
            code="NON_FINITE_NUMBER",
            message=f"Value '{value}' is not a finite number (NaN and Infinity are not allowed)",
            actual=value,
        ))
        return

    if spec.minimum is not None and value < spec.minimum:
        findings.append(Finding(
            path=path,
            severity="error",
            code="VALUE_TOO_SMALL",
            message=f"Value {value} is below minimum {spec.minimum}",
            expected=f">={spec.minimum}",
            actual=value,
        ))

    if spec.maximum is not None and value > spec.maximum:
        findings.append(Finding(
            path=path,
            severity="error",
            code="VALUE_TOO_LARGE",
            message=f"Value {value} exceeds maximum {spec.maximum}",
            expected=f"<={spec.maximum}",
            actual=value,
        ))


def _check_array(spec: FieldSpec, value: list, path: str, findings: list[Finding], depth: int) -> None:
    if spec.minItems is not None and len(value) < spec.minItems:
        findings.append(Finding(
            path=path,
            severity="error",
            code="ARRAY_TOO_SHORT",
            message=f"Array has {len(value)} item(s), minimum is {spec.minItems}",
            expected=f">={spec.minItems}",
            actual=len(value),
        ))

    if spec.maxItems is not None and len(value) > spec.maxItems:
        findings.append(Finding(
            path=path,
            severity="error",
            code="ARRAY_TOO_LONG",
            message=f"Array has {len(value)} item(s), maximum is {spec.maxItems}",
            expected=f"<={spec.maxItems}",
            actual=len(value),
        ))

    if spec.uniqueItems:
        seen_hashable: set[Any] = set()
        seen_unhashable: list[Any] = []
        unhashable_mode = False
        duplicates_reported = 0
        max_duplicates = 10
        for index, item in enumerate(value):
            is_duplicate = False
            if unhashable_mode:
                is_duplicate = any(item == existing for existing in seen_unhashable)
                if not is_duplicate:
                    seen_unhashable.append(item)
            else:
                try:
                    if item in seen_hashable:
                        is_duplicate = True
                    else:
                        seen_hashable.add(item)
                except TypeError:
                    unhashable_mode = True
                    seen_unhashable = list(seen_hashable)
                    seen_hashable = set()
                    is_duplicate = any(item == existing for existing in seen_unhashable)
                    if not is_duplicate:
                        seen_unhashable.append(item)
            if is_duplicate:
                if duplicates_reported < max_duplicates:
                    findings.append(Finding(
                        path=f"{path}[{index}]",
                        severity="error",
                        code="DUPLICATE_ITEMS",
                        message="Array contains duplicate items",
                        actual=item,
                    ))
                duplicates_reported += 1

    if spec.items is not None:
        for i, item in enumerate(value):
            _validate_field(spec.items, item, f"{path}[{i}]", findings, depth + 1)


def _type_matches(expected: str, value: Any) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    type_map = {"string": str, "boolean": bool, "object": dict, "array": list, "null": type(None)}
    return isinstance(value, type_map.get(expected, object))


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__
