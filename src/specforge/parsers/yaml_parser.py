from pathlib import Path
from ruamel.yaml import YAML
from specforge.models.spec import SpecFile

_MAX_SPEC_BYTES = 10 * 1024 * 1024  # 10 MB


class SpecFileTooLargeError(OSError):
    pass


def load_spec(path: Path) -> SpecFile:
    size = path.stat().st_size
    if size > _MAX_SPEC_BYTES:
        raise SpecFileTooLargeError(
            f"Spec file is {size} bytes; maximum allowed is {_MAX_SPEC_BYTES} bytes"
        )
    yaml = YAML(typ="safe")
    with open(path, encoding="utf-8") as f:
        data = yaml.load(f)
    return SpecFile.model_validate(data)


def dump_spec(spec: SpecFile) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False

    from io import StringIO

    buffer = StringIO()
    yaml.dump(_ordered_spec(spec.model_dump(exclude_none=True)), buffer)
    return buffer.getvalue()


def write_spec(spec: SpecFile, path: Path) -> None:
    content = dump_spec(spec)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)


def _ordered_spec(data: dict) -> dict:
    ordered: dict = {"type": data["type"]}
    ordered["fields"] = {name: _ordered_field(field) for name, field in data["fields"].items()}
    return ordered


def _ordered_field(field: dict) -> dict:
    ordered: dict = {"type": field["type"]}
    key_order = (
        "required",
        "nullable",
        "description",
        "default",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
        "enum",
        "minItems",
        "maxItems",
        "uniqueItems",
    )
    for key in key_order:
        if key in field:
            if key == "uniqueItems" and field[key] is False:
                continue
            ordered[key] = field[key]
    if "fields" in field:
        ordered["fields"] = {name: _ordered_field(child) for name, child in field["fields"].items()}
    if "items" in field:
        ordered["items"] = _ordered_field(field["items"])
    return ordered
