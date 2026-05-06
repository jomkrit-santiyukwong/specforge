import json
from pathlib import Path


class PayloadError(ValueError):
    pass


def load_payload(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise PayloadError(
            f"Payload root must be a JSON object (got {type(data).__name__})"
        )
    return data
