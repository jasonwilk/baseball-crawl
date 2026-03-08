"""bb creds -- credential management commands (import, check, refresh)."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Optional

import httpx
import typer
from dotenv import dotenv_values
from rich.console import Console

from src.gamechanger.credentials import check_credentials
from src.gamechanger.credential_parser import CurlParseError, merge_env_file, parse_curl
from src.gamechanger.exceptions import ConfigurationError, CredentialExpiredError
from src.gamechanger.token_manager import AuthSigningError, TokenManager

app = typer.Typer(help="Manage GameChanger credentials.")

_console = Console()
_err_console = Console(stderr=True)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CURL_FILE = _PROJECT_ROOT / "secrets" / "gamechanger-curl.txt"
_ENV_FILE = _PROJECT_ROOT / ".env"


@app.command(name="import")
def import_creds(
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


def _decode_jwt_exp(token: str) -> int | None:
    """Extract the ``exp`` claim from a JWT payload without verification.

    Returns the exp integer, or None if the token cannot be decoded.
    """
    try:
        payload_segment = token.split(".")[1]
        # Add padding to make length a multiple of 4.
        padding = 4 - len(payload_segment) % 4
        payload_segment += "=" * (padding % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
        return int(payload["exp"])
    except Exception:  # noqa: BLE001
        return None


@app.command()
def refresh(
    profile: Optional[str] = typer.Option(
        "web",
        "--profile",
        metavar="PROFILE",
        help="Credential profile to refresh: web (default). Mobile not yet supported.",
    ),
) -> None:
    """Perform a programmatic token refresh via POST /auth and update .env."""
    if profile == "mobile":
        _err_console.print(
            "[red]Error:[/red] Mobile programmatic token refresh is not yet available.\n"
            "The iOS client key has not been extracted. "
            "Capture a fresh access token manually and set "
            "GAMECHANGER_ACCESS_TOKEN_MOBILE in .env."
        )
        raise typer.Exit(code=1)

    env = dotenv_values(str(_ENV_FILE))
    suffix = f"_{profile.upper()}"
    client_id = env.get(f"GAMECHANGER_CLIENT_ID{suffix}") or None
    client_key = env.get(f"GAMECHANGER_CLIENT_KEY{suffix}") or None
    refresh_token = env.get(f"GAMECHANGER_REFRESH_TOKEN{suffix}") or None
    device_id = env.get(f"GAMECHANGER_DEVICE_ID{suffix}") or None
    base_url = env.get("GAMECHANGER_BASE_URL") or None

    missing = []
    if not client_id:
        missing.append(f"GAMECHANGER_CLIENT_ID{suffix}")
    if not client_key:
        missing.append(f"GAMECHANGER_CLIENT_KEY{suffix}")
    if not refresh_token:
        missing.append(f"GAMECHANGER_REFRESH_TOKEN{suffix}")
    if not device_id:
        missing.append(f"GAMECHANGER_DEVICE_ID{suffix}")
    if not base_url:
        missing.append("GAMECHANGER_BASE_URL")

    if missing:
        _err_console.print(
            "[red]Error:[/red] Missing required credentials in .env:\n"
            + "\n".join(f"  {k}" for k in missing)
        )
        raise typer.Exit(code=1)

    try:
        tm = TokenManager(
            profile=profile,
            client_id=client_id,
            client_key=client_key,
            refresh_token=refresh_token,
            device_id=device_id,  # type: ignore[arg-type]
            base_url=base_url,  # type: ignore[arg-type]
            env_path=_ENV_FILE,
        )
        access_token = tm.force_refresh()
    except ConfigurationError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except CredentialExpiredError as exc:
        _err_console.print(
            f"[red]Error:[/red] {exc}\n"
            "Re-capture credentials via the proxy and run: bb creds import"
        )
        raise typer.Exit(code=1)
    except AuthSigningError:
        _err_console.print(
            "[red]Error:[/red] Signature rejected by server (possible clock skew).\n"
            "Check your system clock and try again."
        )
        raise typer.Exit(code=1)
    except Exception as exc:  # noqa: BLE001
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    exp = _decode_jwt_exp(access_token)
    if exp is not None:
        remaining = exp - int(time.time())
        _console.print(
            f"[green]Access token refreshed for {profile} profile, "
            f"expires in {remaining}s[/green]"
        )
    else:
        _console.print(f"[green]Access token refreshed for {profile} profile.[/green]")
    _console.print("TokenManager wrote rotated refresh token to .env (check logs if write-back failed).")


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
