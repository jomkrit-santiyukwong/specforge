from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from specforge.adapters.csv_schema import CSVFieldRow, CSVImportError


@dataclass(slots=True)
class _Node:
    type: str | None = None
    required: bool = False
    nullable: bool = True
    description: str | None = None
    default: str | None = None
    format: str | None = None
    enum: list[str] | None = None
    minLength: int | None = None
    maxLength: int | None = None
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    minItems: int | None = None
    maxItems: int | None = None
    uniqueItems: bool = False
    fields: dict[str, _Node] = field(default_factory=dict)
    items: _Node | None = None
    explicit: bool = False


def build_spec_tree(rows: list[CSVFieldRow]) -> dict[str, Any]:
    root_fields: dict[str, _Node] = {}
    for row in rows:
        _insert_row(root_fields, row)
    return {"type": "object", "fields": {name: _serialize_node(node) for name, node in root_fields.items()}}


def _insert_row(root_fields: dict[str, _Node], row: CSVFieldRow) -> None:
    segments = _parse_path(row.field_name, row.row_number)
    current_fields = root_fields
    current_node: _Node | None = None
    current_path: list[str] = []

    for index, segment in enumerate(segments):
        is_last = index == len(segments) - 1

        if segment == "item":
            if index > 0 and segments[index - 1] == "item":
                raise CSVImportError(f"Row {row.row_number}: nested array item traversal is not supported")
            if current_node is None or current_node.type != "array":
                raise CSVImportError(
                    f"Row {row.row_number}: path '{row.field_name}' uses reserved segment 'item' without an array parent"
                )
            if is_last:
                raise CSVImportError(f"Row {row.row_number}: path '{row.field_name}' cannot end with 'item'")
            if current_node.items is None:
                current_node.items = _Node(type="object")
            elif current_node.items.type is None:
                current_node.items.type = "object"
            elif current_node.items.type != "object":
                raise CSVImportError(
                    f"Row {row.row_number}: array item at '{'.'.join(current_path)}' is {current_node.items.type}, not object"
                )
            current_node = current_node.items
            current_fields = current_node.fields
            current_path.append(segment)
            continue

        if current_node is not None and current_node.type == "array":
            raise CSVImportError(
                f"Row {row.row_number}: child path '{row.field_name}' under array '{'.'.join(current_path)}' must use '.item.'"
            )

        node = current_fields.get(segment)
        if node is None:
            node = _Node()
            current_fields[segment] = node

        current_path.append(segment)

        if is_last:
            _apply_row(node, row)
            return

        next_segment = segments[index + 1]
        if next_segment == "item":
            if node.type is None:
                raise CSVImportError(
                    f"Row {row.row_number}: path '{row.field_name}' uses reserved segment 'item' without an array parent"
                )
            if node.type != "array":
                raise CSVImportError(
                    f"Row {row.row_number}: path '{row.field_name}' uses reserved segment 'item' without an array parent"
                )
        else:
            if node.type is None:
                node.type = "object"
            elif node.type == "array":
                raise CSVImportError(
                    f"Row {row.row_number}: child path '{row.field_name}' under array '{'.'.join(current_path)}' must use '.item.'"
                )
            elif node.type != "object":
                raise CSVImportError(
                    f"Row {row.row_number}: path conflict at '{'.'.join(current_path)}' - expected object, found {node.type}"
                )
        current_node = node
        current_fields = node.fields


def _parse_path(path: str, row_number: int) -> list[str]:
    if path.startswith(".") or path.endswith(".") or ".." in path:
        raise CSVImportError(f"Row {row_number}: invalid field_name path '{path}'")
    segments = path.split(".")
    if any(segment == "" for segment in segments):
        raise CSVImportError(f"Row {row_number}: invalid field_name path '{path}'")
    return segments


def _apply_row(node: _Node, row: CSVFieldRow) -> None:
    if node.explicit:
        raise CSVImportError(f"Row {row.row_number}: duplicate path '{row.field_name}'")

    if row.type != "object" and node.fields:
        raise CSVImportError(f"Row {row.row_number}: path conflict - '{row.field_name}' is already used as a parent object")
    if row.type != "array" and node.items is not None:
        raise CSVImportError(f"Row {row.row_number}: path conflict - '{row.field_name}' is already used as a parent array")

    _merge_field_attributes(node, row)
    node.explicit = True

    if row.type == "object":
        node.fields = node.fields or {}
    elif row.type == "array":
        assert row.item_type is not None
        _merge_array_item(node, row)


def _merge_field_attributes(node: _Node, row: CSVFieldRow) -> None:
    node.type = row.type
    node.required = row.required
    node.nullable = row.nullable
    node.description = row.description
    node.default = row.default
    node.format = row.format
    node.enum = row.enum
    node.minLength = row.minLength
    node.maxLength = row.maxLength
    node.pattern = row.pattern
    node.minimum = row.minimum
    node.maximum = row.maximum
    node.minItems = row.minItems
    node.maxItems = row.maxItems
    node.uniqueItems = row.uniqueItems


def _merge_array_item(node: _Node, row: CSVFieldRow) -> None:
    item_type = row.item_type
    assert item_type is not None

    if node.items is None:
        node.items = _Node(type=item_type)
        if item_type == "object":
            node.items.fields = {}
        return

    if node.items.type is None:
        node.items.type = item_type
    elif node.items.type != item_type:
        raise CSVImportError(
            f"Row {row.row_number}: path conflict - array '{row.field_name}' item_type is {node.items.type}, not {item_type}"
        )

    if item_type != "object" and node.items.fields:
        raise CSVImportError(f"Row {row.row_number}: path conflict - array '{row.field_name}' already has object item fields")
    if item_type == "object":
        node.items.fields = node.items.fields or {}


def _serialize_node(node: _Node) -> dict[str, Any]:
    if node.type is None:
        raise CSVImportError("Internal error: unresolved node type")

    data: dict[str, Any] = {
        "type": node.type,
        "required": node.required,
        "nullable": node.nullable,
    }

    optional_values = (
        ("description", node.description),
        ("default", node.default),
        ("format", node.format),
        ("enum", node.enum),
        ("minLength", node.minLength),
        ("maxLength", node.maxLength),
        ("pattern", node.pattern),
        ("minimum", node.minimum),
        ("maximum", node.maximum),
        ("minItems", node.minItems),
        ("maxItems", node.maxItems),
    )
    for key, value in optional_values:
        if value is not None:
            data[key] = value

    if node.uniqueItems:
        data["uniqueItems"] = True

    if node.type == "object":
        data["fields"] = {name: _serialize_node(child) for name, child in node.fields.items()}
    elif node.type == "array":
        if node.items is None:
            raise CSVImportError("Internal error: array node missing items spec")
        data["items"] = _serialize_node(node.items)

    return data
