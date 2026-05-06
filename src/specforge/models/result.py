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
