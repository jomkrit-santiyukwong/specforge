from rich.console import Console
from rich.markup import escape
from specforge.models.result import DiffResult
from specforge.models.result import ValidationResult

_console = Console()


def report(result: ValidationResult, spec_path: str, input_path: str) -> None:
    _console.print(f"\n[bold]SpecForge Validator[/bold]")
    _console.print(f"  spec:  [cyan]{escape(spec_path)}[/cyan]")
    _console.print(f"  input: [cyan]{escape(input_path)}[/cyan]")

    if not result.findings:
        _console.print("\n[bold green][OK] Validation passed[/bold green] - no issues found\n")
        return

    _console.print()
    for f in result.findings:
        icon, color = _style(f.severity)
        _console.print(f"  {icon} [{color}]{f.severity.upper()}[/{color}]  [dim]{escape(f.path)}[/dim]")
        _console.print(f"       {escape(f.message)}")
        if f.expected is not None:
            _console.print(f"       expected: [green]{escape(str(f.expected))}[/green]")
        if f.actual is not None:
            _console.print(f"       actual:   [red]{escape(str(f.actual))}[/red]")
        _console.print()

    status = "[bold green]PASSED[/bold green]" if result.passed else "[bold red]FAILED[/bold red]"
    parts = [f"  Result: {status}"]
    if result.error_count:
        parts.append(f"[red]{result.error_count} error(s)[/red]")
    if result.warning_count:
        parts.append(f"[yellow]{result.warning_count} warning(s)[/yellow]")
    _console.print("  ".join(parts) + "\n")


def _style(severity: str) -> tuple[str, str]:
    return {"error": ("[X]", "red"), "warning": ("[!]", "yellow"), "info": ("[i]", "blue")}.get(
        severity, ("[-]", "white")
    )


def print_diff_result(result: DiffResult) -> None:
    groups = [
        ("breaking", "red", "Breaking Changes", "✗"),
        ("non-breaking", "yellow", "Non-Breaking Changes", "~"),
        ("informational", "blue", "Informational Changes", "·"),
    ]

    findings_by_classification = {
        classification: [
            finding
            for finding in result.findings
            if getattr(finding, "classification", None) == classification
        ]
        for classification, _, _, _ in groups
    }

    if not any(findings_by_classification.values()):
        _console.print("[green]No changes detected.[/green]")
        return

    for classification, color, title, icon in groups:
        findings = findings_by_classification[classification]
        if not findings:
            continue

        _console.print(f"[bold {color}]{title}[/bold {color}]")
        for finding in findings:
            message = escape(finding.message)
            if finding.related_path is not None:
                message += f" (was: {escape(finding.related_path)})"
            _console.print(f"  {icon} [dim]{escape(finding.path)}[/dim] {message}")
            if finding.expected is not None:
                _console.print(f"      old: [green]{escape(str(finding.expected))}[/green]")
            if finding.actual is not None:
                _console.print(f"      new: [red]{escape(str(finding.actual))}[/red]")
        _console.print()
