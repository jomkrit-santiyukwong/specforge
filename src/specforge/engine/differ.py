from __future__ import annotations

from difflib import SequenceMatcher

from specforge.models.result import DiffFinding, DiffResult
from specforge.models.spec import FieldSpec, SpecFile


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

        old_enum = set(old_field.enum or [])
        new_enum = set(new_field.enum or [])
        removed_enum = sorted(old_enum - new_enum, key=repr)
        added_enum = sorted(new_enum - old_enum, key=repr)
        if removed_enum:
            findings.append(_make_finding(
                path=field_path,
                classification="breaking",
                code="ENUM_VALUE_REMOVED",
                message="Enum values were removed",
                expected=sorted(old_enum, key=repr),
                actual=sorted(new_enum, key=repr),
            ))
        if added_enum:
            findings.append(_make_finding(
                path=field_path,
                classification="non-breaking",
                code="ENUM_VALUE_ADDED",
                message="Enum values were added",
                expected=sorted(old_enum, key=repr),
                actual=sorted(new_enum, key=repr),
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
            old_items = old_field.items
            new_items = new_field.items
            if old_items is not None and new_items is not None:
                items_path = f"{field_path}[]"
                if old_items.type == "object" and new_items.type == "object":
                    _diff_fields(old_items.fields or {}, new_items.fields or {}, items_path, findings)
                else:
                    _diff_fields({"": old_items}, {"": new_items}, items_path, findings)

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
        if old_field.type != new_field.type:
            findings.append(_make_finding(
                path=new_path,
                classification="breaking",
                code="TYPE_CHANGED",
                message="Field type changed",
                expected=old_field.type,
                actual=new_field.type,
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

        old_enum = set(old_field.enum or [])
        new_enum = set(new_field.enum or [])
        removed_enum = sorted(old_enum - new_enum, key=repr)
        added_enum = sorted(new_enum - old_enum, key=repr)
        if removed_enum:
            findings.append(_make_finding(
                path=new_path,
                classification="breaking",
                code="ENUM_VALUE_REMOVED",
                message="Enum values were removed",
                expected=sorted(old_enum, key=repr),
                actual=sorted(new_enum, key=repr),
            ))
        if added_enum:
            findings.append(_make_finding(
                path=new_path,
                classification="non-breaking",
                code="ENUM_VALUE_ADDED",
                message="Enum values were added",
                expected=sorted(old_enum, key=repr),
                actual=sorted(new_enum, key=repr),
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
            old_items = old_field.items
            new_items = new_field.items
            if old_items is not None and new_items is not None:
                items_path = f"{new_path}[]"
                if old_items.type == "object" and new_items.type == "object":
                    _diff_fields(old_items.fields or {}, new_items.fields or {}, items_path, findings)
                else:
                    _diff_fields({"": old_items}, {"": new_items}, items_path, findings)

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


def _match_renames(
    old_fields: dict[str, FieldSpec],
    new_fields: dict[str, FieldSpec],
) -> list[tuple[str, str]]:
    candidates: list[tuple[float, str, str]] = []
    for old_name, old_field in old_fields.items():
        for new_name, new_field in new_fields.items():
            if old_field.type != new_field.type:
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
