from typing import Any, Literal
from pydantic import BaseModel

Severity = Literal["error", "warning", "info"]


class Finding(BaseModel):
    path: str
    severity: Severity
    code: str
    message: str
    expected: Any = None
    actual: Any = None


class ValidationResult(BaseModel):
    passed: bool
    error_count: int
    warning_count: int
    findings: list[Finding]


class DiffFinding(BaseModel):
    path: str
    severity: Severity
    code: str
    classification: Literal["breaking", "non-breaking", "informational"]
    message: str
    expected: Any = None
    actual: Any = None
    related_path: str | None = None


class DiffResult(BaseModel):
    passed: bool
    error_count: int
    warning_count: int
    has_breaking: bool
    counts: dict[str, int]
    findings: list[DiffFinding]
