from rich.console import Console
from rich.markup import escape
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
