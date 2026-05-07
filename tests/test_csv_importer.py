from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from specforge.adapters import CSVImportError, import_csv
from specforge.models.spec import SpecFile

HEADERS = (
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


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8", newline="")
    return path


def _csv(*rows: str) -> str:
    return "\n".join((",".join(HEADERS), *rows, ""))


def _row(**values: str) -> str:
    return ",".join(values.get(header, "") for header in HEADERS)


def _case_path(name: str) -> Path:
    return Path(f"csv-importer-{uuid4().hex}-{name}.csv")


def test_minimal_csv_maps_to_specfile() -> None:
    path = _write_csv(_case_path("minimal"), _csv(_row(field_name="name", type="string", required="true", nullable="false")))
    spec = import_csv(path)

    assert isinstance(spec, SpecFile)
    assert spec.fields["name"].type == "string"
    assert spec.fields["name"].required is True
    assert spec.fields["name"].nullable is False


def test_missing_required_header_fails() -> None:
    path = _write_csv(_case_path("missing-header"), "field_name,required\nname,true\n")

    with pytest.raises(CSVImportError, match="Missing required CSV header"):
        import_csv(path)


def test_unknown_extra_column_fails() -> None:
    path = _write_csv(_case_path("extra-header"), "field_name,type,wat\nname,string,x\n")

    with pytest.raises(CSVImportError, match="Unknown CSV header"):
        import_csv(path)


def test_empty_csv_fails() -> None:
    path = _write_csv(_case_path("empty"), "")

    with pytest.raises(CSVImportError, match="CSV file is empty"):
        import_csv(path)


def test_header_only_csv_fails() -> None:
    path = _write_csv(_case_path("header-only"), _csv())

    with pytest.raises(CSVImportError, match="at least one non-blank data row"):
        import_csv(path)


def test_blank_rows_are_ignored() -> None:
    path = _write_csv(_case_path("blank-rows"), _csv("", "," * (len(HEADERS) - 1), _row(field_name="name", type="string")))
    spec = import_csv(path)

    assert set(spec.fields) == {"name"}


def test_boolean_columns_accept_mixed_case_and_invalid_boolean_fails() -> None:
    valid = _write_csv(
        _case_path("bools"),
        _csv(_row(field_name="name", type="string", required="TrUe", nullable="FalSe")),
    )
    spec = import_csv(valid)
    assert spec.fields["name"].required is True
    assert spec.fields["name"].nullable is False

    invalid = _write_csv(
        _case_path("invalid-bool"),
        _csv(_row(field_name="name", type="string", required="yes", nullable="false")),
    )
    with pytest.raises(CSVImportError, match="required must be true or false"):
        import_csv(invalid)


def test_invalid_type_fails() -> None:
    path = _write_csv(_case_path("invalid-type"), _csv(_row(field_name="name", type="uuid")))

    with pytest.raises(CSVImportError, match="invalid type"):
        import_csv(path)


def test_enum_pipe_split_and_empty_optional_cells_omitted() -> None:
    path = _write_csv(
        _case_path("enum"),
        _csv(_row(field_name="status", type="string", required="true", nullable="false", enum="A|B|C")),
    )
    spec = import_csv(path)

    field = spec.fields["status"]
    assert field.enum == ["A", "B", "C"]
    assert field.description is None
    assert field.default is None


def test_numeric_constraints_coerce_and_invalid_numeric_fails() -> None:
    valid = _write_csv(
        _case_path("numbers"),
        _csv(_row(field_name="amount", type="number", minimum="-1.5", maximum="3.25")),
    )
    spec = import_csv(valid)

    field = spec.fields["amount"]
    assert field.minimum == -1.5
    assert field.maximum == 3.25

    invalid = _write_csv(
        _case_path("invalid-number"),
        _csv(_row(field_name="amount", type="number", minimum="abc")),
    )
    with pytest.raises(CSVImportError, match="minimum must be a number"):
        import_csv(invalid)


def test_implicit_parent_object_is_created() -> None:
    path = _write_csv(
        _case_path("implicit-parent"),
        _csv(_row(field_name="address.street", type="string", required="true", nullable="false")),
    )
    spec = import_csv(path)

    address = spec.fields["address"]
    assert address.type == "object"
    assert address.required is False
    assert address.nullable is True
    assert address.fields["street"].type == "string"


def test_explicit_parent_object_merges_and_type_conflict_fails() -> None:
    valid = _write_csv(
        _case_path("merge-parent"),
        _csv(
            _row(field_name="address.street", type="string", required="true", nullable="false"),
            _row(field_name="address", type="object", required="true", nullable="false", description="Mailing address"),
        ),
    )
    spec = import_csv(valid)

    address = spec.fields["address"]
    assert address.required is True
    assert address.nullable is False
    assert address.description == "Mailing address"
    assert "street" in address.fields

    invalid = _write_csv(
        _case_path("merge-conflict"),
        _csv(
            _row(field_name="address.street", type="string", required="true", nullable="false"),
            _row(field_name="address", type="string", required="true", nullable="false"),
        ),
    )
    with pytest.raises(CSVImportError, match="already used as a parent object"):
        import_csv(invalid)


def test_duplicate_path_fails() -> None:
    row = _row(field_name="name", type="string")
    path = _write_csv(_case_path("duplicate"), _csv(row, row))

    with pytest.raises(CSVImportError, match="duplicate path 'name'"):
        import_csv(path)


@pytest.mark.parametrize("field_path", ["name..value", ".name", "name."])
def test_invalid_paths_fail(field_path: str) -> None:
    path = _write_csv(_case_path("invalid-path"), _csv(_row(field_name=field_path, type="string")))

    with pytest.raises(CSVImportError, match="invalid field_name path"):
        import_csv(path)


def test_scalar_array_maps_items_type() -> None:
    path = _write_csv(_case_path("scalar-array"), _csv(_row(field_name="tags", type="array", item_type="string")))
    spec = import_csv(path)

    tags = spec.fields["tags"]
    assert tags.type == "array"
    assert tags.items is not None
    assert tags.items.type == "string"


def test_object_array_and_item_child_rows_map_to_object_items() -> None:
    path = _write_csv(
        _case_path("object-array"),
        _csv(
            _row(field_name="items", type="array", required="true", nullable="false", item_type="object"),
            _row(field_name="items.item.code", type="string", required="true", nullable="false"),
            _row(field_name="items.item.qty", type="integer"),
        ),
    )
    spec = import_csv(path)

    items = spec.fields["items"]
    assert items.items is not None
    assert items.items.type == "object"
    assert set(items.items.fields) == {"code", "qty"}


def test_child_row_under_array_missing_item_segment_fails() -> None:
    path = _write_csv(
        _case_path("array-child-missing-item"),
        _csv(
            _row(field_name="items", type="array", required="true", nullable="false", item_type="object"),
            _row(field_name="items.code", type="string"),
        ),
    )

    with pytest.raises(CSVImportError, match="must use '.item.'"):
        import_csv(path)


def test_array_row_missing_item_type_fails() -> None:
    path = _write_csv(_case_path("array-missing-item-type"), _csv(_row(field_name="items", type="array")))

    with pytest.raises(CSVImportError, match="item_type is required when type is array"):
        import_csv(path)


def test_non_array_row_with_item_type_fails() -> None:
    path = _write_csv(
        _case_path("non-array-item-type"),
        _csv(_row(field_name="name", type="string", item_type="string")),
    )

    with pytest.raises(CSVImportError, match="item_type may only be set when type is array"):
        import_csv(path)


def test_nested_array_item_path_is_rejected() -> None:
    path = _write_csv(
        _case_path("nested-item"),
        _csv(
            _row(field_name="groups", type="array", required="true", nullable="false", item_type="object"),
            _row(field_name="groups.item.item.code", type="string"),
        ),
    )

    with pytest.raises(CSVImportError, match="nested array item traversal is not supported"):
        import_csv(path)


def test_generated_structure_validates_against_specfile_model() -> None:
    path = _write_csv(
        _case_path("valid-structure"),
        _csv(
            _row(field_name="id", type="integer", required="true", nullable="false"),
            _row(field_name="address.street", type="string", required="true", nullable="false"),
            _row(field_name="tags", type="array", item_type="string", min_items="1", max_items="5", unique_items="true"),
        ),
    )
    spec = import_csv(path)

    assert isinstance(spec, SpecFile)
