import json
import math
from pathlib import Path
from typing import Any
from specforge.models.result import ValidationResult


_JSON_NATIVE = (bool, int, float, str, type(None))


def _sanitize(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if not isinstance(value, _JSON_NATIVE):
        return str(value)
    return value


def write(result: ValidationResult, output_path: Path) -> None:
    payload = _sanitize(result.model_dump())
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
