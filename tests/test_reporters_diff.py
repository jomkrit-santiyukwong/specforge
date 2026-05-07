import json

from specforge.models.result import DiffFinding, DiffResult
from specforge.reporters.console import print_diff_result
from specforge.reporters.json_reporter import diff_result_to_json
from specforge.reporters.markdown_reporter import diff_result_to_markdown


def _make_diff_result() -> DiffResult:
    findings = [
        DiffFinding(
            path="user.name",
            severity="error",
            code="TYPE_CHANGED",
            classification="breaking",
            message="Field type changed",
            expected="string",
            actual="integer",
        ),
        DiffFinding(
            path="user.nickname",
            severity="warning",
            code="FIELD_ADDED",
            classification="non-breaking",
            message="Field added",
        ),
        DiffFinding(
            path="user.bio",
            severity="info",
            code="DESCRIPTION_CHANGED",
            classification="informational",
            message="Field description changed",
        ),
        DiffFinding(
            path="username",
            severity="warning",
            code="POSSIBLE_RENAME",
            classification="breaking",
            message="Possible rename (heuristic — verify manually)",
            related_path="user_name",
        ),
    ]

    return DiffResult(
        passed=False,
        error_count=0,
        warning_count=0,
        has_breaking=True,
        counts={"breaking": 2, "non-breaking": 1, "informational": 1},
        findings=findings,
    )


def test_console_diff_smoke_breaking_section_present(capsys):
    print_diff_result(_make_diff_result())
    captured = capsys.readouterr()
    assert "Breaking Changes" in captured.out
    assert "✗" in captured.out
    assert "~" in captured.out
    assert "·" in captured.out
    assert "(was: user_name)" in captured.out
    breaking_idx = captured.out.index("Breaking Changes")
    non_breaking_idx = captured.out.index("Non-Breaking Changes")
    assert breaking_idx < non_breaking_idx


def test_json_diff_output_is_valid_and_contains_findings():
    parsed = json.loads(diff_result_to_json(_make_diff_result()))
    assert "findings" in parsed
    assert "has_breaking" in parsed
    assert isinstance(parsed["has_breaking"], bool)
    assert "counts" in parsed
    assert set(parsed["counts"]) == {"breaking", "non-breaking", "informational"}
    assert all("classification" in finding for finding in parsed["findings"])
    assert all("related_path" in finding for finding in parsed["findings"])


def test_markdown_diff_output_contains_title_and_breaking_section():
    output = diff_result_to_markdown(_make_diff_result())
    assert "# Spec Diff Report" in output
    assert "## Summary" in output
    assert "| Breaking |" in output
    assert "| 1 |" in output
    assert "## Breaking Changes" in output


def test_markdown_diff_output_contains_rename_and_nested_type_change_paths():
    result = DiffResult(
        passed=False,
        error_count=0,
        warning_count=0,
        has_breaking=True,
        counts={"breaking": 1, "non-breaking": 0, "informational": 0},
        findings=[
            DiffFinding(
                path="user.legacyName",
                severity="error",
                code="POSSIBLE_RENAME",
                classification="breaking",
                message="Possible rename (heuristic — verify manually)",
                related_path="user_name",
            ),
            DiffFinding(
                path="user.profile.name",
                severity="error",
                code="TYPE_CHANGED",
                classification="breaking",
                message="Field type changed",
                expected="string",
                actual="integer",
            ),
        ],
    )

    output = diff_result_to_markdown(result)

    assert "## Summary" in output
    assert "| Breaking |" in output
    assert "user.legacyName" in output
    assert "user.profile.name" in output
    assert "(was: `user_name`)" in output


def test_markdown_diff_no_change_still_has_summary_table():
    result = DiffResult(
        passed=True,
        error_count=0,
        warning_count=0,
        has_breaking=False,
        counts={"breaking": 0, "non-breaking": 0, "informational": 0},
        findings=[],
    )

    output = diff_result_to_markdown(result)

    assert "## Summary" in output
    assert "| Breaking | 0 |" in output
    assert "No changes detected." in output
    assert "## Breaking Changes" not in output
