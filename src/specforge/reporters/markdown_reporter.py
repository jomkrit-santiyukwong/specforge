from specforge.models.result import DiffResult


def _md_escape(value: str) -> str:
    """Escape backtick characters so they cannot break markdown code spans."""
    return str(value).replace("`", "\\`")


def diff_result_to_markdown(result: DiffResult) -> str:
    groups = [
        ("breaking", "Breaking Changes"),
        ("non-breaking", "Non-Breaking Changes"),
        ("informational", "Informational Changes"),
    ]

    lines = [
        "# Spec Diff Report",
        "",
        "## Summary",
        "| Classification | Count |",
        "|---|---|",
        f"| Breaking | {result.counts.get('breaking', 0)} |",
        f"| Non-breaking | {result.counts.get('non-breaking', 0)} |",
        f"| Informational | {result.counts.get('informational', 0)} |",
        "",
    ]

    if not result.findings:
        lines.append("No changes detected.")
        return "\n".join(lines).rstrip() + "\n"

    for classification, title in groups:
        findings = [
            finding
            for finding in result.findings
            if getattr(finding, "classification", None) == classification
        ]
        if not findings:
            continue

        lines.append(f"## {title}")
        lines.append("")
        for finding in findings:
            line = f"- `{_md_escape(finding.path)}`: {finding.message}"
            if finding.related_path is not None:
                line += f" (was: `{_md_escape(finding.related_path)}`)"
            details: list[str] = []
            if finding.expected is not None:
                details.append(f"old: `{_md_escape(str(finding.expected))}`")
            if finding.actual is not None:
                details.append(f"new: `{_md_escape(str(finding.actual))}`")
            if details:
                line = f"{line} ({', '.join(details)})"
            lines.append(line)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
