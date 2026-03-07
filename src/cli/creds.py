"""bb creds -- credential management commands (refresh, check)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.gamechanger.credentials import check_credentials
from src.gamechanger.credential_parser import CurlParseError, merge_env_file, parse_curl

app = typer.Typer(help="Manage GameChanger credentials.")

_console = Console()
_err_console = Console(stderr=True)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CURL_FILE = _PROJECT_ROOT / "secrets" / "gamechanger-curl.txt"
_ENV_FILE = _PROJECT_ROOT / ".env"


@app.command()
def refresh(
    curl: Optional[str] = typer.Option(
        None,
        "--curl",
        metavar="CURL_COMMAND",
        help="Inline curl command string.",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        metavar="PATH",
        help=(
            "Path to a file containing the curl command. "
            f"Defaults to {_DEFAULT_CURL_FILE} when neither --curl nor --file is given."
        ),
    ),
) -> None:
    """Extract credentials from a curl command and write them to .env."""
    if curl is not None and file is not None:
        _err_console.print("[red]Error:[/red] --curl and --file are mutually exclusive.")
        raise typer.Exit(code=1)

    # Determine the curl command string.
    if curl is not None:
        curl_command = curl
    else:
        source_path = file if file is not None else _DEFAULT_CURL_FILE
        if not source_path.exists():
            _err_console.print(
                f"[red]Error:[/red] curl command file not found: {source_path}\n"
                "Provide a curl command with --curl or --file, or save one to "
                f"{_DEFAULT_CURL_FILE}."
            )
            raise typer.Exit(code=1)
        curl_command = source_path.read_text(encoding="utf-8")

    try:
        new_credentials = parse_curl(curl_command)
    except CurlParseError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    merged = merge_env_file(str(_ENV_FILE), new_credentials)

    _console.print(f"Credentials written to [bold]{_ENV_FILE}[/bold]:")
    for key in sorted(new_credentials.keys()):
        _console.print(f"  [green]{key}[/green]")
    _console.print(
        f"({len(new_credentials)} keys written, {len(merged)} total keys in .env)"
    )


@app.command()
def check(
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        metavar="PROFILE",
        help="Credential profile to check: web or mobile. Checks all profiles if omitted.",
    ),
) -> None:
    """Validate GameChanger credentials stored in .env."""
    exit_code, message = check_credentials(profile=profile)

    if exit_code == 0:
        _console.print(f"[green]{message}[/green]")
    elif exit_code == 2:
        _console.print(f"[yellow]{message}[/yellow]")
    else:
        _console.print(f"[red]{message}[/red]")

    raise typer.Exit(code=exit_code)
