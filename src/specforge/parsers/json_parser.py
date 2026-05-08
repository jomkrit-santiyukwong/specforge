import json
from pathlib import Path

_MAX_PAYLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class PayloadError(ValueError):
    pass


class PayloadTooLargeError(OSError):
    pass


def load_payload(path: Path) -> dict:
    size = path.stat().st_size
    if size > _MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(
            f"Payload file is {size} bytes; maximum allowed is {_MAX_PAYLOAD_BYTES} bytes"
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise PayloadError(
            f"Payload root must be a JSON object (got {type(data).__name__})"
        )
    return data
