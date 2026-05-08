from pathlib import Path
import json
from typing import Optional

import click
import typer
from pydantic import ValidationError

app = typer.Typer(name="specforge", help="Validate, mock, and diff API specs", add_completion=False)


def _abort(msg: str) -> None:
    typer.echo(f"Error: {msg}", err=True)
    raise typer.Exit(code=2)


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import PackageNotFoundError, version

        try:
            ver = version("specforge")
        except PackageNotFoundError:
            ver = "unknown"
        typer.echo(f"specforge {ver}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress warning logs (errors still shown)",
    ),
) -> None:
    import logging

    level = logging.ERROR if quiet else logging.WARNING
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)


@app.command()
def validate(
    spec: Path = typer.Option(..., "--spec", help="Spec file (YAML)", exists=True, dir_okay=False, readable=True),
    input: Path = typer.Option(..., "--input", help="Payload file (JSON)", exists=True, dir_okay=False, readable=True),
    output: Optional[Path] = typer.Option(None, "--output", help="Write JSON report to file"),
) -> None:
    """Validate a JSON payload against a spec."""
    import json

    from ruamel.yaml import YAMLError

    from specforge.engine.validator import validate as run_validate
    from specforge.parsers.json_parser import PayloadError, load_payload
    from specforge.parsers.yaml_parser import load_spec
    from specforge.reporters import console as console_reporter
    from specforge.reporters import json_reporter

    try:
        spec_model = load_spec(spec)
    except YAMLError as e:
        _abort(f"Could not parse spec file: {e}")
    except ValidationError as e:
        _abort(f"Invalid spec structure:\n{e}")
    except OSError as e:
        _abort(f"Could not read spec file: {e}")

    try:
        payload = load_payload(input)
    except json.JSONDecodeError as e:
        _abort(f"Could not parse payload file: {e}")
    except PayloadError as e:
        _abort(str(e))
    except OSError as e:
        _abort(f"Could not read payload file: {e}")

    result = run_validate(spec_model, payload)
    console_reporter.report(result, str(spec), str(input))

    if output:
        try:
            json_reporter.write(result, output)
            typer.echo(f"Report written to {output}")
        except OSError as e:
            _abort(f"Could not write report: {e}")
        except (TypeError, ValueError) as e:
            _abort(f"Could not serialize report: {e}")

    if not result.passed:
        raise typer.Exit(code=1)


@app.command()
def mock(
    spec: Path = typer.Option(..., "--spec", help="Spec file (YAML)", dir_okay=False, readable=True),
    mode: str = typer.Option(
        "minimal",
        "--mode",
        click_type=click.Choice(["minimal", "full", "edge", "example"], case_sensitive=False),
    ),
    count: int = typer.Option(1, "--count", min=1, max=10_000, help="Number of mock payloads to generate (max 10,000)"),
    seed: int | None = typer.Option(None, "--seed", help="Seed for deterministic generation"),
) -> None:
    """Generate mock payloads from a spec."""
    from ruamel.yaml import YAMLError

    from specforge.engine.mocker import MockGenerator
    from specforge.parsers.yaml_parser import load_spec

    if not spec.exists():
        _abort(f"Spec file does not exist: {spec}")

    try:
        spec_model = load_spec(spec)
    except YAMLError as e:
        _abort(f"Could not parse spec file: {e}")
    except ValidationError as e:
        _abort(f"Invalid spec structure:\n{e}")
    except OSError as e:
        _abort(f"Could not read spec file: {e}")

    mode = mode.lower()
    generator = MockGenerator(seed=seed)
    try:
        if count == 1:
            typer.echo(json.dumps(generator.generate(spec_model, mode), indent=2))
        else:
            typer.echo("[")
            for i, obj in enumerate(generator.iter_generate(spec_model, mode, count)):
                rendered = json.dumps(obj, indent=2)
                indented = "\n".join("  " + line for line in rendered.splitlines())
                suffix = "," if i < count - 1 else ""
                typer.echo(indented + suffix)
            typer.echo("]")
    except (TypeError, ValueError) as e:
        _abort(f"Could not serialize mock output: {e}")


@app.command()
def diff(
    old: Path = typer.Option(..., "--old", help="Old spec file"),
    new: Path = typer.Option(..., "--new", help="New spec file"),
    format: str = typer.Option("console", "--format", help="Output format: console, json, markdown"),
    fail_on_breaking: bool = typer.Option(False, "--fail-on-breaking", help="Exit 1 if breaking changes detected"),
) -> None:
    """Compare two spec versions and explain changes."""
    from ruamel.yaml import YAMLError

    from specforge.engine.differ import diff_specs
    from specforge.parsers.yaml_parser import load_spec
    from specforge.reporters.console import print_diff_result
    from specforge.reporters.json_reporter import diff_result_to_json
    from specforge.reporters.markdown_reporter import diff_result_to_markdown

    if not old.exists():
        _abort(f"Old spec file does not exist: {old}")
    if not new.exists():
        _abort(f"New spec file does not exist: {new}")

    try:
        old_spec = load_spec(old)
    except YAMLError as e:
        _abort(f"Could not parse spec file: {e}")
    except ValidationError as e:
        _abort(f"Invalid spec structure:\n{e}")
    except OSError as e:
        _abort(f"Could not read spec file: {e}")

    try:
        new_spec = load_spec(new)
    except YAMLError as e:
        _abort(f"Could not parse spec file: {e}")
    except ValidationError as e:
        _abort(f"Invalid spec structure:\n{e}")
    except OSError as e:
        _abort(f"Could not read spec file: {e}")

    result = diff_specs(old_spec, new_spec)
    format = format.lower()

    if format == "console":
        print_diff_result(result)
    elif format == "json":
        print(diff_result_to_json(result))
    elif format == "markdown":
        print(diff_result_to_markdown(result))
    else:
        _abort(f"Invalid format: {format}")

    if fail_on_breaking and result.has_breaking:
        raise typer.Exit(code=1)


@app.command("import-csv")
def import_csv_command(
    input: Path = typer.Option(..., "--input", help="CSV schema file", exists=True, dir_okay=False, readable=True),
    output: Optional[Path] = typer.Option(None, "--output", help="Write YAML spec to file"),
) -> None:
    """Import a CSV schema and convert it into a SpecForge YAML spec."""
    from specforge.adapters import CSVImportError, import_csv
    from specforge.parsers.yaml_parser import dump_spec, write_spec

    try:
        spec_model = import_csv(input)
    except CSVImportError as e:
        _abort(str(e))
    except OSError as e:
        _abort(f"Could not read CSV file: {e}")

    try:
        rendered = dump_spec(spec_model)
        if output:
            write_spec(spec_model, output)
            typer.echo(f"Spec written to {output}")
        else:
            typer.echo(rendered, nl=False)
    except OSError as e:
        _abort(f"Could not write spec file: {e}")


@app.command("import-excel")
def import_excel_command(
    input: Path = typer.Option(..., "--input", help="Excel schema file (.xlsx)", exists=True, dir_okay=False, readable=True),
    output: Optional[Path] = typer.Option(None, "--output", help="Write YAML spec to file"),
    sheet: Optional[str] = typer.Option(None, "--sheet", help="Sheet name (default: active sheet)"),
) -> None:
    """Import an Excel schema and convert it into a SpecForge YAML spec."""
    from specforge.adapters.csv_schema import CSVImportError
    from specforge.adapters.excel_importer import import_excel
    from specforge.parsers.yaml_parser import dump_spec, write_spec

    try:
        spec_model = import_excel(input, sheet=sheet)
    except CSVImportError as e:
        _abort(str(e))
    except OSError as e:
        _abort(f"Could not read Excel file: {e}")

    try:
        rendered = dump_spec(spec_model)
        if output:
            write_spec(spec_model, output)
            typer.echo(f"Spec written to {output}")
        else:
            typer.echo(rendered, nl=False)
    except OSError as e:
        _abort(f"Could not write spec file: {e}")


if __name__ == "__main__":
    app()
