from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specforge.models.spec import FieldType

CSV_HEADERS = (
    "field_name",
    "type",
    "required",
    "nullable",
    "description",
    "item_type",
    "format",
    "enum",
    "default",
    "min_length",
    "max_length",
    "pattern",
    "minimum",
    "maximum",
    "min_items",
    "max_items",
    "unique_items",
)

REQUIRED_HEADERS = {"field_name", "type"}
VALID_TYPES: set[FieldType] = {"string", "integer", "number", "boolean", "object", "array", "null"}


class CSVImportError(ValueError):
    pass


@dataclass(slots=True)
class CSVFieldRow:
    row_number: int
    field_name: str
    type: FieldType
    required: bool = False
    nullable: bool = True
    description: str | None = None
    item_type: FieldType | None = None
    format: str | None = None
    enum: list[str] | None = None
    default: str | None = None
    minLength: int | None = None
    maxLength: int | None = None
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    minItems: int | None = None
    maxItems: int | None = None
    uniqueItems: bool = False

    def to_field_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type,
            "required": self.required,
            "nullable": self.nullable,
        }
        optional_values = {
            "description": self.description,
            "default": self.default,
            "format": self.format,
            "enum": self.enum,
            "minLength": self.minLength,
            "maxLength": self.maxLength,
            "pattern": self.pattern,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "minItems": self.minItems,
            "maxItems": self.maxItems,
        }
        for key, value in optional_values.items():
            if value is not None:
                data[key] = value
        if self.uniqueItems:
            data["uniqueItems"] = True
        return data


def load_csv_rows(path: Path) -> list[CSVFieldRow]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            _validate_headers(headers)
            rows = [_parse_row(index + 2, row) for index, row in enumerate(reader)]
    except csv.Error as exc:
        raise CSVImportError(f"Could not parse CSV file: {exc}") from exc

    parsed_rows = [row for row in rows if row is not None]
    if not parsed_rows:
        raise CSVImportError("CSV file must contain at least one non-blank data row")
    return parsed_rows


def _validate_headers(headers: list[str] | None) -> None:
    if headers is None:
        raise CSVImportError("CSV file is empty")

    normalized = [header.strip() for header in headers]
    if any(header == "" for header in normalized):
        raise CSVImportError("CSV header row contains an empty column name")

    missing = sorted(REQUIRED_HEADERS - set(normalized))
    if missing:
        raise CSVImportError(f"Missing required CSV header(s): {', '.join(missing)}")

    unknown = sorted(set(normalized) - set(CSV_HEADERS))
    if unknown:
        raise CSVImportError(f"Unknown CSV header(s): {', '.join(unknown)}")


def _parse_row(row_number: int, raw_row: dict[str, str | None]) -> CSVFieldRow | None:
    row = {key.strip(): _clean(value) for key, value in raw_row.items() if key is not None}
    if not any(value is not None for value in row.values()):
        return None

    field_name = row.get("field_name")
    if not field_name:
        raise CSVImportError(f"Row {row_number}: field_name is required")

    field_type = _parse_type(row_number, "type", row.get("type"), required=True)
    item_type = _parse_type(row_number, "item_type", row.get("item_type"), required=False)

    if field_type == "array" and item_type is None:
        raise CSVImportError(f"Row {row_number}: item_type is required when type is array")
    if field_type != "array" and item_type is not None:
        raise CSVImportError(f"Row {row_number}: item_type may only be set when type is array")

    return CSVFieldRow(
        row_number=row_number,
        field_name=field_name,
        type=field_type,
        required=_parse_bool(row_number, "required", row.get("required"), default=False),
        nullable=_parse_bool(row_number, "nullable", row.get("nullable"), default=True),
        description=row.get("description"),
        item_type=item_type,
        format=row.get("format"),
        enum=_parse_enum(row.get("enum")),
        default=row.get("default"),
        minLength=_parse_int(row_number, "min_length", row.get("min_length")),
        maxLength=_parse_int(row_number, "max_length", row.get("max_length")),
        pattern=row.get("pattern"),
        minimum=_parse_float(row_number, "minimum", row.get("minimum")),
        maximum=_parse_float(row_number, "maximum", row.get("maximum")),
        minItems=_parse_int(row_number, "min_items", row.get("min_items")),
        maxItems=_parse_int(row_number, "max_items", row.get("max_items")),
        uniqueItems=_parse_bool(row_number, "unique_items", row.get("unique_items"), default=False),
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped != "" else None


def _parse_bool(row_number: int, column: str, value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise CSVImportError(f"Row {row_number}: {column} must be true or false")


def _parse_type(row_number: int, column: str, value: str | None, *, required: bool) -> FieldType | None:
    if value is None:
        if required:
            raise CSVImportError(f"Row {row_number}: {column} is required")
        return None
    if value not in VALID_TYPES:
        raise CSVImportError(f"Row {row_number}: invalid {column} {value!r}")
    return value


def _parse_enum(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return value.split("|")


def _parse_int(row_number: int, column: str, value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CSVImportError(f"Row {row_number}: {column} must be an integer") from exc
    if parsed < 0:
        raise CSVImportError(f"Row {row_number}: {column} must be >= 0")
    return parsed


def _parse_float(row_number: int, column: str, value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise CSVImportError(f"Row {row_number}: {column} must be a number") from exc
