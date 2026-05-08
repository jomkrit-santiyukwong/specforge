from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from specforge.models.result import DiffFinding, DiffResult
from specforge.models.spec import FieldSpec, SpecFile


def _list_diff(old: list[Any], new: list[Any]) -> tuple[list[Any], list[Any]]:
    """Return (removed, added) using equality comparison so unhashable values work."""
    removed = [v for v in old if not any(v == n for n in new)]
    added = [v for v in new if not any(v == o for o in old)]
    return removed, added


def _enum_sort_key(value: Any) -> str:
    return repr(value)


def diff_specs(old_spec: SpecFile, new_spec: SpecFile) -> DiffResult:
    findings: list[DiffFinding] = []
    _diff_fields(old_spec.fields, new_spec.fields, path="", findings=findings)
    has_breaking = any(f.classification == "breaking" for f in findings)
    counts = {"breaking": 0, "non-breaking": 0, "informational": 0}
    for finding in findings:
        counts[finding.classification] += 1

    result = DiffResult(
        passed=not has_breaking,
        error_count=counts["breaking"],
        warning_count=counts["non-breaking"],
        has_breaking=has_breaking,
        counts=counts,
        findings=findings,
    )
    return result


def _diff_fields(
    old_fields: dict[str, FieldSpec],
    new_fields: dict[str, FieldSpec],
    path: str,
    findings: list[DiffFinding],
) -> None:
    shared_names = old_fields.keys() & new_fields.keys()
    unmatched_old = {name: old_fields[name] for name in old_fields.keys() - shared_names}
    unmatched_new = {name: new_fields[name] for name in new_fields.keys() - shared_names}

    for name in sorted(shared_names):
        old_field = old_fields[name]
        new_field = new_fields[name]
        field_path = _join_path(path, name)

        if old_field.type != new_field.type:
            findings.append(_make_finding(
                path=field_path,
                classification="breaking",
                code="TYPE_CHANGED",
                message="Field type changed",
                expected=old_field.type,
                actual=new_field.type,
            ))

        if old_field.required is False and new_field.required is True:
            findings.append(_make_finding(
                path=field_path,
                classification="breaking",
                code="REQUIRED_ADDED",
                message="Field changed from optional to required",
                expected=False,
                actual=True,
            ))
        elif old_field.required is True and new_field.required is False:
            findings.append(_make_finding(
                path=field_path,
                classification="non-breaking",
                code="REQUIRED_REMOVED",
                message="Field changed from required to optional",
                expected=True,
                actual=False,
            ))

        old_enum_list = list(old_field.enum or [])
        new_enum_list = list(new_field.enum or [])
        removed_enum, added_enum = _list_diff(old_enum_list, new_enum_list)
        if removed_enum:
            findings.append(_make_finding(
                path=field_path,
                classification="breaking",
                code="ENUM_VALUE_REMOVED",
                message="Enum values were removed",
                expected=sorted(old_enum_list, key=_enum_sort_key),
                actual=sorted(new_enum_list, key=_enum_sort_key),
            ))
        if added_enum:
            findings.append(_make_finding(
                path=field_path,
                classification="non-breaking",
                code="ENUM_VALUE_ADDED",
                message="Enum values were added",
                expected=sorted(old_enum_list, key=_enum_sort_key),
                actual=sorted(new_enum_list, key=_enum_sort_key),
            ))

        if old_field.default != new_field.default:
            findings.append(_make_finding(
                path=field_path,
                classification="non-breaking",
                code="DEFAULT_CHANGED",
                message="Default value changed",
                expected=old_field.default,
                actual=new_field.default,
            ))

        if old_field.description != new_field.description:
            findings.append(_make_finding(
                path=field_path,
                classification="informational",
                code="DESCRIPTION_CHANGED",
                message="Field description changed",
                expected=old_field.description,
                actual=new_field.description,
            ))

        if old_field.type == "object" and new_field.type == "object":
            _diff_fields(old_field.fields or {}, new_field.fields or {}, field_path, findings)
        elif old_field.type == "array" and new_field.type == "array":
            _diff_array_items(old_field.items, new_field.items, field_path, findings)

    rename_matches = _match_renames(unmatched_old, unmatched_new)
    for old_name, new_name in rename_matches:
        old_field = unmatched_old.pop(old_name)
        new_field = unmatched_new.pop(new_name)
        new_path = _join_path(path, new_name)
        findings.append(_make_finding(
            path=new_path,
            classification="breaking",
            code="POSSIBLE_RENAME",
            message="Possible rename (heuristic — verify manually)",
            related_path=_join_path(path, old_name),
            expected=old_name,
            actual=new_name,
        ))

        if old_field.required is False and new_field.required is True:
            findings.append(_make_finding(
                path=new_path,
                classification="breaking",
                code="REQUIRED_ADDED",
                message="Field changed from optional to required",
                expected=False,
                actual=True,
            ))
        elif old_field.required is True and new_field.required is False:
            findings.append(_make_finding(
                path=new_path,
                classification="non-breaking",
                code="REQUIRED_REMOVED",
                message="Field changed from required to optional",
                expected=True,
                actual=False,
            ))

        old_enum_list = list(old_field.enum or [])
        new_enum_list = list(new_field.enum or [])
        removed_enum, added_enum = _list_diff(old_enum_list, new_enum_list)
        if removed_enum:
            findings.append(_make_finding(
                path=new_path,
                classification="breaking",
                code="ENUM_VALUE_REMOVED",
                message="Enum values were removed",
                expected=sorted(old_enum_list, key=_enum_sort_key),
                actual=sorted(new_enum_list, key=_enum_sort_key),
            ))
        if added_enum:
            findings.append(_make_finding(
                path=new_path,
                classification="non-breaking",
                code="ENUM_VALUE_ADDED",
                message="Enum values were added",
                expected=sorted(old_enum_list, key=_enum_sort_key),
                actual=sorted(new_enum_list, key=_enum_sort_key),
            ))

        if old_field.default != new_field.default:
            findings.append(_make_finding(
                path=new_path,
                classification="non-breaking",
                code="DEFAULT_CHANGED",
                message="Default value changed",
                expected=old_field.default,
                actual=new_field.default,
            ))

        if old_field.description != new_field.description:
            findings.append(_make_finding(
                path=new_path,
                classification="informational",
                code="DESCRIPTION_CHANGED",
                message="Field description changed",
                expected=old_field.description,
                actual=new_field.description,
            ))
        if old_field.type == "object":
            _diff_fields(old_field.fields or {}, new_field.fields or {}, path=new_path, findings=findings)
        elif old_field.type == "array":
            _diff_array_items(old_field.items, new_field.items, new_path, findings)

    for name in sorted(unmatched_old):
        findings.append(_make_finding(
            path=_join_path(path, name),
            classification="breaking",
            code="FIELD_REMOVED",
            message="Field removed",
        ))

    for name in sorted(unmatched_new):
        new_field = unmatched_new[name]
        findings.append(_make_finding(
            path=_join_path(path, name),
            classification="breaking" if new_field.required else "non-breaking",
            code="FIELD_ADDED",
            message="Field added",
        ))


def _diff_array_items(
    old_items: FieldSpec | None,
    new_items: FieldSpec | None,
    field_path: str,
    findings: list[DiffFinding],
) -> None:
    items_path = f"{field_path}[]"
    if old_items is None and new_items is not None:
        findings.append(_make_finding(
            path=items_path,
            classification="breaking",
            code="ITEMS_SPEC_ADDED",
            message="Array items spec added (new shape constraint)",
            actual=new_items.type,
        ))
        return
    if old_items is not None and new_items is None:
        findings.append(_make_finding(
            path=items_path,
            classification="non-breaking",
            code="ITEMS_SPEC_REMOVED",
            message="Array items spec removed (constraint relaxed)",
            expected=old_items.type,
        ))
        return
    if old_items is None or new_items is None:
        return

    if old_items.type == "object" and new_items.type == "object":
        _diff_fields(old_items.fields or {}, new_items.fields or {}, items_path, findings)
    else:
        _diff_fields({"": old_items}, {"": new_items}, items_path, findings)


def _match_renames(
    old_fields: dict[str, FieldSpec],
    new_fields: dict[str, FieldSpec],
) -> list[tuple[str, str]]:
    candidates: list[tuple[float, str, str]] = []
    for old_name, old_field in old_fields.items():
        old_len = len(old_name)
        for new_name, new_field in new_fields.items():
            if old_field.type != new_field.type:
                continue
            new_len = len(new_name)
            # ratio = 2*M/(old_len+new_len), M <= min(old_len, new_len).
            # ratio > 0.6 requires max(L) < 7/3 * min(L); skip pairs that can't pass.
            if old_len > new_len * 7 // 3 or new_len > old_len * 7 // 3:
                continue
            ratio = SequenceMatcher(None, old_name, new_name).ratio()
            if ratio > 0.6:
                candidates.append((ratio, old_name, new_name))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_old: set[str] = set()
    used_new: set[str] = set()
    matches: list[tuple[str, str]] = []
    for _, old_name, new_name in candidates:
        if old_name in used_old or new_name in used_new:
            continue
        used_old.add(old_name)
        used_new.add(new_name)
        matches.append((old_name, new_name))
    return matches


def _join_path(base: str, name: str) -> str:
    if not base:
        return name
    if not name:
        return base
    return f"{base}.{name}"


def _make_finding(
    *,
    path: str,
    classification: str,
    code: str,
    message: str,
    expected: object = None,
    actual: object = None,
    related_path: str | None = None,
) -> DiffFinding:
    severity = {
        "breaking": "error",
        "non-breaking": "warning",
        "informational": "info",
    }[classification]
    finding = DiffFinding(
        path=path,
        severity=severity,
        code=code,
        classification=classification,
        message=message,
        expected=expected,
        actual=actual,
        related_path=related_path,
    )
    return finding
