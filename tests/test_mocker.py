from __future__ import annotations

from specforge.engine.mocker import MockGenerator
from specforge.models.spec import SpecFile


def test_minimal_mode_includes_only_required_fields() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "id": {"type": "integer", "required": True, "minimum": 1},
            "nickname": {"type": "string"},
            "active": {"type": "boolean", "required": True, "nullable": False},
        },
    })

    payload = MockGenerator(seed=7).generate(spec, "minimal")

    assert isinstance(payload, dict)
    assert set(payload) == {"id", "active"}
    assert "nickname" not in payload
    assert isinstance(payload["id"], int)
    assert payload["id"] >= 1
    assert isinstance(payload["active"], bool)


def test_full_mode_includes_optional_fields() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "id": {"type": "integer", "required": True, "minimum": 1},
            "nickname": {"type": "string", "minLength": 3, "nullable": False},
            "active": {"type": "boolean"},
        },
    })

    payload = MockGenerator(seed=3).generate(spec, "full")

    assert set(payload) == {"id", "nickname", "active"}
    assert isinstance(payload["nickname"], str)
    assert len(payload["nickname"]) >= 3
    assert isinstance(payload["active"], bool)
    assert isinstance(payload["id"], int)


def test_edge_mode_uses_boundary_values() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "code": {"type": "string", "required": True, "minLength": 2, "nullable": False},
            "amount": {"type": "number", "required": True, "minimum": 1.5, "nullable": False},
            "count": {"type": "integer", "required": True, "minimum": 2, "nullable": False},
            "enabled": {"type": "boolean", "required": True, "nullable": False},
            "tags": {
                "type": "array",
                "required": True,
                "nullable": False,
                "minItems": 2,
                "items": {"type": "string", "nullable": False},
            },
            "note": {"type": "string", "required": True, "nullable": True, "minLength": 5},
        },
    })

    payload = MockGenerator(seed=2).generate(spec, "edge")

    assert payload["code"] == "xx"
    assert payload["amount"] == 1.5
    assert payload["count"] == 2
    assert payload["enabled"] is False
    assert isinstance(payload["tags"], list)
    assert len(payload["tags"]) == 2
    assert payload["tags"] == ["", ""]
    assert payload["note"] is None


def test_example_mode_produces_typed_values() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "customerEmail": {"type": "string", "required": True, "format": "email", "nullable": False},
            "createdOn": {"type": "string", "required": True, "format": "date", "nullable": False},
            "requestedAt": {"type": "string", "required": True, "format": "date-time", "nullable": False},
            "price": {"type": "number", "required": True, "nullable": False},
            "quantity": {"type": "integer", "required": True, "nullable": False},
            "enabled": {"type": "boolean", "required": True, "nullable": False},
        },
    })

    payload = MockGenerator(seed=11).generate(spec, "example")

    assert "@" in payload["customerEmail"]
    assert isinstance(payload["createdOn"], str)
    assert len(payload["createdOn"]) == 10
    assert "T" in payload["requestedAt"]
    assert isinstance(payload["price"], float)
    assert isinstance(payload["quantity"], int)
    assert isinstance(payload["enabled"], bool)


def test_enum_modes_pick_expected_values() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "status": {"type": "string", "required": True, "enum": ["X", "Y", "Z"], "nullable": False},
        },
    })

    enum_values = ["X", "Y", "Z"]
    minimal_payload = MockGenerator(seed=5).generate(spec, "minimal")
    edge_payload = MockGenerator(seed=5).generate(spec, "edge")
    full_payload = MockGenerator(seed=5).generate(spec, "full")
    example_payload = MockGenerator(seed=5).generate(spec, "example")

    assert minimal_payload["status"] == enum_values[0]
    assert edge_payload["status"] == enum_values[0]
    assert full_payload["status"] in enum_values
    assert example_payload["status"] in enum_values


def test_nested_objects_are_generated() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "profile": {
                "type": "object",
                "required": True,
                "nullable": False,
                "fields": {
                    "firstName": {"type": "string", "required": True, "nullable": False, "minLength": 1},
                    "lastName": {"type": "string", "nullable": False},
                },
            },
        },
    })

    payload = MockGenerator(seed=13).generate(spec, "full")

    assert isinstance(payload["profile"], dict)
    assert set(payload["profile"]) == {"firstName", "lastName"}
    assert isinstance(payload["profile"]["firstName"], str)
    assert len(payload["profile"]["firstName"]) >= 1
    assert isinstance(payload["profile"]["lastName"], str)


def test_array_fields_are_generated() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "items": {
                "type": "array",
                "required": True,
                "nullable": False,
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "nullable": False,
                    "fields": {
                        "quantity": {"type": "integer", "required": True, "minimum": 1, "nullable": False},
                    },
                },
            },
        },
    })

    payload = MockGenerator(seed=17).generate(spec, "full")

    assert isinstance(payload["items"], list)
    assert 1 <= len(payload["items"]) <= 3
    assert all(isinstance(item, dict) for item in payload["items"])
    assert all("quantity" in item for item in payload["items"])
    assert all(isinstance(item["quantity"], int) for item in payload["items"])
    assert all(item["quantity"] >= 1 for item in payload["items"])


def test_seeded_generation_is_deterministic() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "name": {"type": "string", "required": True, "nullable": False},
            "amount": {"type": "number", "required": True, "nullable": False},
            "items": {
                "type": "array",
                "required": True,
                "nullable": False,
                "items": {"type": "integer", "nullable": False},
            },
        },
    })

    first = MockGenerator(seed=23).generate(spec, "example")
    second = MockGenerator(seed=23).generate(spec, "example")
    third = MockGenerator(seed=24).generate(spec, "example")

    assert first == second
    assert first != third


def test_pattern_field_emits_warning(caplog) -> None:
    import logging

    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "code": {"type": "string", "required": True, "nullable": False, "pattern": "^[A-Z]+$"},
        },
    })

    with caplog.at_level(logging.WARNING, logger="specforge.engine.mocker"):
        payload = MockGenerator(seed=29).generate(spec, "full")

    assert "code" in payload
    assert isinstance(payload["code"], str)
    assert any(
        "pattern constraint skipped" in record.getMessage() and "code" in record.getMessage()
        for record in caplog.records
    )


def test_nullable_edge_returns_none() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "note": {"type": "string", "required": True, "nullable": True, "minLength": 3},
            "count": {"type": "integer", "required": True, "nullable": False, "minimum": 1},
        },
    })

    payload = MockGenerator(seed=31).generate(spec, "edge")

    assert payload["note"] is None
    assert payload["count"] == 1


def test_generate_and_generate_many_return_expected_types() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "id": {"type": "integer", "required": True, "nullable": False},
        },
    })
    generator = MockGenerator(seed=37)

    single = generator.generate(spec, "minimal")
    many = generator.generate_many(spec, "minimal", 3)

    assert isinstance(single, dict)
    assert isinstance(many, list)
    assert len(many) == 3
    assert all(isinstance(item, dict) for item in many)
    assert all("id" in item for item in many)


def test_depth_guard_returns_type_correct_sentinel() -> None:
    fields = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "nestedString": {"type": "string", "required": True, "nullable": False},
            "nestedNumber": {"type": "number", "required": True, "nullable": False},
            "nestedInteger": {"type": "integer", "required": True, "nullable": False},
            "nestedBoolean": {"type": "boolean", "required": True, "nullable": False},
        },
    }).fields

    generator = MockGenerator(seed=41)

    assert generator._generate_field(fields["nestedString"], "full", "nestedString", 21) == ""
    assert generator._generate_field(fields["nestedNumber"], "full", "nestedNumber", 21) == 0.0
    assert generator._generate_field(fields["nestedInteger"], "full", "nestedInteger", 21) == 0
    assert generator._generate_field(fields["nestedBoolean"], "full", "nestedBoolean", 21) is False


def test_iter_generate_is_lazy_and_matches_generate_many() -> None:
    import types

    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "id": {"type": "integer", "required": True, "nullable": False, "minimum": 1},
        },
    })

    streamed = MockGenerator(seed=53).iter_generate(spec, "minimal", 4)
    assert isinstance(streamed, types.GeneratorType)
    streamed_list = list(streamed)

    buffered = MockGenerator(seed=53).generate_many(spec, "minimal", 4)

    assert len(streamed_list) == 4
    assert streamed_list == buffered


def test_unique_items_with_object_items_falls_back_to_list_equality() -> None:
    """Mocker generates unique array of object items — exercises unhashable fallback path."""
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "rows": {
                "type": "array",
                "required": True,
                "nullable": False,
                "uniqueItems": True,
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "nullable": False,
                    "fields": {"id": {"type": "integer", "required": True, "minimum": 1, "maximum": 1000, "nullable": False}},
                },
            },
        },
    })
    payload = MockGenerator(seed=61).generate(spec, "full")
    rows = payload["rows"]
    assert len(rows) == 3
    seen = []
    for row in rows:
        assert row not in seen
        seen.append(row)


def test_iter_generate_does_not_buffer_count() -> None:
    spec = SpecFile.model_validate({
        "type": "object",
        "fields": {
            "id": {"type": "integer", "required": True, "nullable": False},
        },
    })

    gen = MockGenerator(seed=59).iter_generate(spec, "minimal", 1_000_000)
    first = next(gen)
    assert isinstance(first, dict)
    assert "id" in first
