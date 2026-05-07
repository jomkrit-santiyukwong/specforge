from specforge.engine.differ import diff_specs
from specforge.models.spec import FieldSpec, SpecFile


def make_spec(**fields) -> SpecFile:
    return SpecFile(fields=fields)


def get_finding(result, code: str):
    for finding in result.findings:
        if finding.code == code:
            return finding
    raise AssertionError(f"Finding {code!r} not found")


def test_field_added_optional():
    old_spec = make_spec()
    new_spec = make_spec(name=FieldSpec(type="string", required=False))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "FIELD_ADDED")
    assert finding.path == "name"
    assert finding.classification == "non-breaking"
    assert result.counts["non-breaking"] == 1


def test_field_added_required():
    old_spec = make_spec()
    new_spec = make_spec(name=FieldSpec(type="string", required=True))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "FIELD_ADDED")
    assert finding.path == "name"
    assert finding.classification == "breaking"
    assert result.has_breaking is True


def test_field_removed():
    old_spec = make_spec(name=FieldSpec(type="string"))
    new_spec = make_spec()

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "FIELD_REMOVED")
    assert finding.path == "name"
    assert finding.classification == "breaking"


def test_type_changed():
    old_spec = make_spec(age=FieldSpec(type="integer"))
    new_spec = make_spec(age=FieldSpec(type="string"))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "TYPE_CHANGED")
    assert finding.path == "age"
    assert finding.classification == "breaking"
    assert finding.expected == "integer"
    assert finding.actual == "string"


def test_required_false_to_true():
    old_spec = make_spec(name=FieldSpec(type="string", required=False))
    new_spec = make_spec(name=FieldSpec(type="string", required=True))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "REQUIRED_ADDED")
    assert finding.path == "name"
    assert finding.classification == "breaking"


def test_required_true_to_false():
    old_spec = make_spec(name=FieldSpec(type="string", required=True))
    new_spec = make_spec(name=FieldSpec(type="string", required=False))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "REQUIRED_REMOVED")
    assert finding.path == "name"
    assert finding.classification == "non-breaking"


def test_enum_value_added():
    old_spec = make_spec(status=FieldSpec(type="string", enum=["OPEN"]))
    new_spec = make_spec(status=FieldSpec(type="string", enum=["OPEN", "CLOSED"]))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "ENUM_VALUE_ADDED")
    assert finding.path == "status"
    assert finding.classification == "non-breaking"


def test_enum_value_removed():
    old_spec = make_spec(status=FieldSpec(type="string", enum=["OPEN", "CLOSED"]))
    new_spec = make_spec(status=FieldSpec(type="string", enum=["OPEN"]))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "ENUM_VALUE_REMOVED")
    assert finding.path == "status"
    assert finding.classification == "breaking"


def test_default_changed():
    old_spec = make_spec(limit=FieldSpec(type="integer", default=10))
    new_spec = make_spec(limit=FieldSpec(type="integer", default=20))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "DEFAULT_CHANGED")
    assert finding.path == "limit"
    assert finding.classification == "non-breaking"
    assert finding.expected == 10
    assert finding.actual == 20


def test_description_changed():
    old_spec = make_spec(name=FieldSpec(type="string", description="Old"))
    new_spec = make_spec(name=FieldSpec(type="string", description="New"))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "DESCRIPTION_CHANGED")
    assert finding.path == "name"
    assert finding.classification == "informational"


def test_nested_object_recursion_uses_dot_path():
    old_spec = make_spec(
        address=FieldSpec(
            type="object",
            fields={"city": FieldSpec(type="string")},
        )
    )
    new_spec = make_spec(
        address=FieldSpec(
            type="object",
            fields={"city": FieldSpec(type="integer")},
        )
    )

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "TYPE_CHANGED")
    assert finding.path == "address.city"


def test_array_items_recursion_uses_bracket_path():
    old_spec = make_spec(
        items=FieldSpec(
            type="array",
            items=FieldSpec(type="object", fields={"id": FieldSpec(type="integer")}),
        )
    )
    new_spec = make_spec(
        items=FieldSpec(
            type="array",
            items=FieldSpec(type="object", fields={"id": FieldSpec(type="string")}),
        )
    )

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "TYPE_CHANGED")
    assert finding.path == "items[].id"


def test_rename_heuristic_hit():
    old_spec = make_spec(user_name=FieldSpec(type="string"))
    new_spec = make_spec(username=FieldSpec(type="string"))

    result = diff_specs(old_spec, new_spec)

    finding = get_finding(result, "POSSIBLE_RENAME")
    assert finding.path == "username"
    assert finding.classification == "breaking"
    assert finding.related_path == "user_name"
    assert finding.message == "Possible rename (heuristic — verify manually)"


def test_rename_heuristic_recurses_into_renamed_object():
    old_spec = make_spec(
        user_name=FieldSpec(
            type="object",
            fields={"id": FieldSpec(type="integer")},
        )
    )
    new_spec = make_spec(
        username=FieldSpec(
            type="object",
            fields={"id": FieldSpec(type="string")},
        )
    )

    result = diff_specs(old_spec, new_spec)

    rename_finding = get_finding(result, "POSSIBLE_RENAME")
    assert rename_finding.path == "username"
    assert rename_finding.related_path == "user_name"

    nested_finding = get_finding(result, "TYPE_CHANGED")
    assert nested_finding.path == "username.id"
    assert nested_finding.expected == "integer"
    assert nested_finding.actual == "string"


def test_rename_heuristic_recurses_into_renamed_array():
    old_spec = make_spec(
        tags=FieldSpec(
            type="array",
            items=FieldSpec(type="object", fields={"label": FieldSpec(type="string")}),
        )
    )
    new_spec = make_spec(
        tag_list=FieldSpec(
            type="array",
            items=FieldSpec(type="object", fields={"label": FieldSpec(type="integer")}),
        )
    )

    result = diff_specs(old_spec, new_spec)

    rename_finding = get_finding(result, "POSSIBLE_RENAME")
    assert rename_finding.path == "tag_list"
    assert rename_finding.related_path == "tags"

    nested_finding = get_finding(result, "TYPE_CHANGED")
    assert nested_finding.path == "tag_list[].label"


def test_rename_heuristic_miss():
    old_spec = make_spec(foo=FieldSpec(type="string"))
    new_spec = make_spec(bar=FieldSpec(type="string"))

    result = diff_specs(old_spec, new_spec)

    codes = [finding.code for finding in result.findings]
    assert "POSSIBLE_RENAME" not in codes
    assert "FIELD_REMOVED" in codes
    assert "FIELD_ADDED" in codes


def test_rename_heuristic_same_scope_only():
    old_spec = make_spec(
        parent_a=FieldSpec(
            type="object",
            fields={"user_name": FieldSpec(type="string")},
        ),
        parent_b=FieldSpec(
            type="object",
            fields={"something_else": FieldSpec(type="string")},
        ),
    )
    new_spec = make_spec(
        parent_a=FieldSpec(
            type="object",
            fields={"something_new": FieldSpec(type="string")},
        ),
        parent_b=FieldSpec(
            type="object",
            fields={"username": FieldSpec(type="string")},
        ),
    )

    result = diff_specs(old_spec, new_spec)

    rename_pairs = {
        (finding.related_path, finding.path)
        for finding in result.findings
        if finding.code == "POSSIBLE_RENAME"
    }
    assert ("parent_a.user_name", "parent_b.username") not in rename_pairs

    removed_paths = {
        finding.path for finding in result.findings if finding.code == "FIELD_REMOVED"
    }
    added_paths = {
        finding.path for finding in result.findings if finding.code == "FIELD_ADDED"
    }
    assert "parent_a.user_name" in removed_paths
    assert "parent_b.username" in added_paths


def test_rename_heuristic_threshold_boundary():
    from difflib import SequenceMatcher

    old_name = "alpha_id"
    new_name = "beta_code"
    ratio = SequenceMatcher(None, old_name, new_name).ratio()
    assert ratio <= 0.6

    old_spec = make_spec(parent=FieldSpec(type="object", fields={old_name: FieldSpec(type="string")}))
    new_spec = make_spec(parent=FieldSpec(type="object", fields={new_name: FieldSpec(type="string")}))

    result = diff_specs(old_spec, new_spec)

    codes = [finding.code for finding in result.findings]
    assert "POSSIBLE_RENAME" not in codes

    removed_paths = {
        finding.path for finding in result.findings if finding.code == "FIELD_REMOVED"
    }
    added_paths = {
        finding.path for finding in result.findings if finding.code == "FIELD_ADDED"
    }
    assert f"parent.{old_name}" in removed_paths
    assert f"parent.{new_name}" in added_paths


def test_rename_heuristic_emits_required_change_on_renamed_field():
    old_spec = make_spec(user_name=FieldSpec(type="string", required=False))
    new_spec = make_spec(username=FieldSpec(type="string", required=True))

    result = diff_specs(old_spec, new_spec)

    rename_finding = get_finding(result, "POSSIBLE_RENAME")
    assert rename_finding.path == "username"
    assert rename_finding.related_path == "user_name"

    required_finding = get_finding(result, "REQUIRED_ADDED")
    assert required_finding.path == "username"
    assert required_finding.classification == "breaking"


def test_rename_heuristic_emits_property_changes_on_renamed_field():
    old_spec = make_spec(
        user_name=FieldSpec(type="string", required=False, enum=["A", "B"], default="A")
    )
    new_spec = make_spec(
        username=FieldSpec(type="string", required=True, enum=["A", "B", "C"], default="B")
    )

    result = diff_specs(old_spec, new_spec)

    rename_finding = get_finding(result, "POSSIBLE_RENAME")
    assert rename_finding.path == "username"
    assert rename_finding.related_path == "user_name"

    required_finding = get_finding(result, "REQUIRED_ADDED")
    assert required_finding.path == "username"
    assert required_finding.classification == "breaking"

    enum_finding = get_finding(result, "ENUM_VALUE_ADDED")
    assert enum_finding.path == "username"
    assert enum_finding.classification == "non-breaking"

    default_finding = get_finding(result, "DEFAULT_CHANGED")
    assert default_finding.path == "username"
    assert default_finding.classification == "non-breaking"
