from pathlib import Path
from typing import Optional

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
    spec: Path = typer.Option(..., "--spec", help="Spec file (YAML)", exists=True, dir_okay=False),
    mode: str = typer.Option("minimal", "--mode", help="minimal | full | edge | example"),
) -> None:
    """Generate mock payloads from a spec. (coming in Phase 2)"""
    typer.echo("mock: coming in Phase 2")
    raise typer.Exit(code=0)


@app.command()
def diff(
    old: Path = typer.Option(..., "--old", help="Old spec file (YAML)", exists=True, dir_okay=False),
    new: Path = typer.Option(..., "--new", help="New spec file (YAML)", exists=True, dir_okay=False),
) -> None:
    """Compare two spec versions and explain changes. (coming in Phase 3)"""
    typer.echo("diff: coming in Phase 3")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
