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
    spec: Path = typer.Option(..., "--spec", help="Spec file (YAML)", exists=True, dir_okay=False, readable=True),
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
        payload = generator.generate(spec_model, mode) if count == 1 else generator.generate_many(spec_model, mode, count)
        typer.echo(json.dumps(payload, indent=2))
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


if __name__ == "__main__":
    app()
