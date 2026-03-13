"""bb creds -- credential management commands (import, check, refresh)."""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import typer
from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.gamechanger.credentials import (
    ClientKeyCheckResult,
    ProfileCheckResult,
    _ALL_PROFILES,
    _run_api_check,
    check_credentials,
    check_profile_detailed,
)
from src.gamechanger.credential_parser import (
    CurlParseError,
    atomic_merge_env_file,
    merge_env_file,
    parse_curl,
)
from src.gamechanger.exceptions import ConfigurationError, CredentialExpiredError
from src.gamechanger.key_extractor import ExtractedKey, KeyExtractionError, extract_client_key
from src.gamechanger.token_manager import AuthSigningError, TokenManager
from src.http.proxy_check import ProxyCheckOutcome

app = typer.Typer(
    help="Manage GameChanger credentials.",
    invoke_without_command=True,
    epilog="Run 'bb creds COMMAND --help' for more information on a command.",
)


@app.callback()
def _creds_group(ctx: typer.Context) -> None:
    """Manage GameChanger credentials."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

_console = Console()
_err_console = Console(stderr=True)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CURL_FILE = _PROJECT_ROOT / "secrets" / "gamechanger-curl.txt"
_ENV_FILE = _PROJECT_ROOT / ".env"

# Test endpoint displayed in the API health section (AC-6)
_ME_USER_ENDPOINT = "GET /me/user"

# Mobile credential keys written by the proxy addon during capture sessions.
_MOBILE_CRED_KEYS: tuple[str, ...] = (
    "GAMECHANGER_ACCESS_TOKEN_MOBILE",
    "GAMECHANGER_REFRESH_TOKEN_MOBILE",
    "GAMECHANGER_DEVICE_ID_MOBILE",
    "GAMECHANGER_CLIENT_ID_MOBILE",
)

# Proxy sessions directory -- scan this to detect recent iOS traffic.
_SESSIONS_DIR = _PROJECT_ROOT / "proxy" / "data" / "sessions"


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
    profile: str = typer.Option(
        "web",
        "--profile",
        metavar="PROFILE",
        help="Credential profile: web (default) or mobile.",
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
        new_credentials = parse_curl(curl_command, profile=profile)
    except CurlParseError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    merged = merge_env_file(str(_ENV_FILE), new_credentials)
    _print_import_summary(new_credentials, merged)


def _print_import_summary(new_credentials: dict[str, str], merged: dict[str, str]) -> None:
    """Print the post-import summary: key names written and token lifetime metadata."""
    _console.print(f"Credentials written to [bold]{_ENV_FILE}[/bold]:")
    for key in sorted(new_credentials.keys()):
        _console.print(f"  [green]{key}[/green]")
    _console.print(
        f"({len(new_credentials)} keys written, {len(merged)} total keys in .env)"
    )
    _print_token_info(new_credentials)


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


def _print_token_info(credentials: dict[str, str]) -> None:
    """Print token type and remaining lifetime for any tokens in *credentials*.

    Never shows credential values -- only key names and decoded timing metadata.
    """
    _token_labels = {
        "GAMECHANGER_ACCESS_TOKEN_MOBILE": "Access token (mobile)",
        "GAMECHANGER_REFRESH_TOKEN_MOBILE": "Refresh token (mobile)",
        "GAMECHANGER_REFRESH_TOKEN_WEB": "Refresh token (web)",
    }
    now = int(time.time())
    for key, label in _token_labels.items():
        token = credentials.get(key)
        if not token:
            continue
        exp = _decode_jwt_exp(token)
        if exp is None:
            continue
        remaining = exp - now
        if remaining <= 0:
            _console.print(f"  {label}: [yellow]already expired[/yellow]")
        elif remaining < 3600:
            mins = remaining // 60
            _console.print(f"  {label}: [yellow]valid for ~{mins} minute(s)[/yellow]")
        elif remaining < 86400:
            hours = remaining // 3600
            _console.print(f"  {label}: [green]valid for ~{hours} hour(s)[/green]")
        else:
            days = remaining // 86400
            _console.print(f"  {label}: [green]expires in {days} day(s)[/green]")


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
    email = env.get("GAMECHANGER_USER_EMAIL") or None
    password = env.get("GAMECHANGER_USER_PASSWORD") or None

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
            email=email,
            password=password,
        )
        access_token = tm.force_refresh(allow_login_fallback=True)
    except ConfigurationError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except CredentialExpiredError as exc:
        _err_console.print(
            f"[red]Error:[/red] {exc}\n"
            "Run `bb creds check --profile web` -- if Client Key Validation shows [XX], "
            "run `bb creds extract-key` to update it.\n"
            "If the key is valid, re-capture credentials via the proxy and run `bb creds import`."
        )
        raise typer.Exit(code=1)
    except AuthSigningError:
        _err_console.print(
            "[red]Error:[/red] Signature rejected. "
            "Run `bb creds check --profile web` to diagnose. "
            "If Client Key shows [XX], run `bb creds extract-key` to update it. "
            "If clock skew is suspected, check your system clock."
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


def _indicator(style: str) -> Text:
    """Return a status indicator Text with the given Rich style."""
    labels = {"green": "[OK]", "yellow": "[!!]", "red": "[XX]", "dim": "[--]"}
    return Text(labels[style], style=style)


def _append_row(t: Text, style: str, rest: str) -> None:
    """Append one indicator row (indicator + two spaces + text + newline)."""
    t.append_text(_indicator(style))
    t.append(f"  {rest}\n")


def _render_credentials_section(t: Text, result: ProfileCheckResult) -> None:
    """Append the Credentials section to *t*."""
    t.append("Credentials\n", style="bold")
    for key in result.presence.keys_present:
        _append_row(t, "green", key)
    for key in result.presence.keys_missing:
        _append_row(t, "red", f"{key}  (missing)")
    t.append("\n")


def _render_token_section(t: Text, result: ProfileCheckResult) -> None:
    """Append the Refresh Token section to *t*."""
    t.append("Refresh Token\n", style="bold")
    th = result.token_health
    if th is None:
        _append_row(t, "red", "Token key not present in .env")
    elif th.exp is None:
        _append_row(t, "yellow", "Token present but could not be decoded")
    else:
        exp_date = datetime.fromtimestamp(th.exp).strftime("%Y-%m-%d")
        now = int(time.time())
        is_mobile = result.profile == "mobile"
        if th.is_expired:
            days_ago = max(0, (now - th.exp) // 86400)
            _append_row(t, "yellow" if is_mobile else "red", f"Expired {days_ago} day(s) ago ({exp_date})")
        else:
            days_left = max(0, (th.exp - now) // 86400)
            suffix = " -- no auto-refresh for mobile profile" if is_mobile else ""
            _append_row(t, "yellow" if is_mobile else "green", f"Expires in {days_left} day(s) ({exp_date}){suffix}")
    t.append("\n")


def _render_client_key_section(t: Text, result: ProfileCheckResult) -> None:
    """Append the Client Key Validation section to *t*.

    Placed between Refresh Token and API Health so operators see the key
    validation result before the API health check outcome.
    """
    t.append("Client Key Validation  ", style="bold")
    t.append("(POST /auth client-auth)\n", style="dim")
    ck = result.client_key_result
    if ck is None:
        _append_row(t, "dim", "Client key validation not available")
    elif ck.status == "valid":
        _append_row(t, "green", ck.message)
    elif ck.status == "invalid":
        _append_row(t, "red", ck.message)
    elif ck.status == "clock_skew":
        _append_row(t, "yellow", ck.message)
    elif ck.status == "error":
        _append_row(t, "yellow", ck.message)
    else:
        # "skipped" and any future status
        _append_row(t, "dim", ck.message)
    t.append("\n")


def _render_api_section(t: Text, result: ProfileCheckResult) -> None:
    """Append the API Health section to *t*."""
    t.append("API Health  ", style="bold")
    t.append(f"({_ME_USER_ENDPOINT})\n", style="dim")
    ar = result.api_result
    style = "green" if ar.exit_code == 0 else ("dim" if ar.exit_code == 2 else "red")
    _append_row(t, style, ar.message)
    t.append("\n")


def _render_proxy_section(t: Text, result: ProfileCheckResult) -> None:
    """Append the Proxy (Bright Data) section to *t*."""
    t.append("Proxy (Bright Data)\n", style="bold")
    outcome = result.proxy_result.outcome
    if outcome == ProxyCheckOutcome.NOT_CONFIGURED:
        _append_row(t, "dim", "Not configured (direct connection)")
    elif outcome == ProxyCheckOutcome.PASS:
        _append_row(t, "green", "Routing correctly via Bright Data")
    elif outcome == ProxyCheckOutcome.PASS_UNVERIFIED:
        _append_row(t, "yellow", "Routing unverified (direct baseline unavailable)")
    elif outcome == ProxyCheckOutcome.FAIL:
        _append_row(t, "red", "Not routing -- proxy IP matches direct IP")
    elif outcome == ProxyCheckOutcome.ERROR:
        _append_row(t, "red", f"Proxy error: {result.proxy_result.error or 'unknown error'}")


def _render_profile_report(result: ProfileCheckResult) -> Text:
    """Build a Rich Text object for one profile's diagnostic report.

    Sections: Credentials, Refresh Token, Client Key Validation, API Health,
    Proxy (Bright Data).
    Status indicators: [OK] green, [!!] yellow, [XX] red, [--] dim.
    No credential values are included -- only key names and decoded metadata.
    """
    t = Text()
    _render_credentials_section(t, result)
    _render_token_section(t, result)
    _render_client_key_section(t, result)
    _render_api_section(t, result)
    _render_proxy_section(t, result)
    return Text(t.plain.rstrip("\n"), spans=t._spans)


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
    if profile is not None:
        result = check_profile_detailed(profile)
        _console.print(
            Panel(_render_profile_report(result), title=f"Profile: {result.profile}", expand=False)
        )
        raise typer.Exit(code=result.exit_code)

    # Multi-profile: check all profiles, exit 0 if any valid
    results = [check_profile_detailed(p) for p in _ALL_PROFILES]
    for r in results:
        _console.print(Panel(_render_profile_report(r), title=f"Profile: {r.profile}", expand=False))
    any_valid = any(r.exit_code == 0 for r in results)
    raise typer.Exit(code=0 if any_valid else 1)


# ---------------------------------------------------------------------------
# bb creds capture
# ---------------------------------------------------------------------------


def _find_most_recent_session(sessions_dir: Path) -> Path | None:
    """Return the most recent proxy session directory, or None if none exist."""
    if not sessions_dir.is_dir():
        return None
    sessions = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    return sessions[0] if sessions else None


def _has_ios_traffic(session_dir: Path) -> bool:
    """Return True if the endpoint log contains any iOS-sourced requests."""
    log_path = session_dir / "endpoint-log.jsonl"
    if not log_path.exists():
        return False
    try:
        with log_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("source") == "ios":
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return False


def _append_refresh_token_row(t: Text, refresh_token: str) -> None:
    """Append refresh token remaining lifetime row (shown when access token is expired).

    Gives the operator an honest picture: how long the refresh token is still
    valid and a clear message that recapture is needed to get a fresh access token.
    """
    if not refresh_token:
        return
    exp = _decode_jwt_exp(refresh_token)
    if exp is None:
        return
    now = int(time.time())
    remaining = exp - now
    key = "GAMECHANGER_REFRESH_TOKEN_MOBILE"
    if remaining <= 0:
        _append_row(t, "yellow", f"{key}  -- expired  [recapture needed]")
    else:
        days = max(remaining // 86400, 1)
        _append_row(t, "yellow", f"{key}  -- valid for ~{days} day(s)  [recapture to get fresh access token]")


def _append_access_token_health(t: Text, access_token: str) -> None:
    """Append access token lifetime row -- always [!!] yellow for mobile (AC-8)."""
    key = "GAMECHANGER_ACCESS_TOKEN_MOBILE"
    if not access_token:
        _append_row(t, "red", f"{key}  (missing)")
        return
    exp = _decode_jwt_exp(access_token)
    now = int(time.time())
    if exp is None:
        _append_row(t, "yellow", f"{key}  -- present but could not be decoded")
        return
    remaining = exp - now
    if remaining <= 0:
        _append_row(t, "yellow", f"{key}  -- expired  [recapture needed]")
        return
    hours = remaining // 3600
    mins = (remaining % 3600) // 60
    lifetime = f"~{hours} hour(s)" if remaining >= 3600 else f"~{mins} minute(s)"
    _append_row(t, "yellow", f"{key}  -- valid for {lifetime}  [no auto-refresh]")


def _print_capture_result(creds: dict[str, str], profile: str) -> None:
    """Display capture success: credential presence, API validation, token health."""
    t = Text()
    t.append("Captured Credentials\n", style="bold")
    for key in _MOBILE_CRED_KEYS:
        if key in creds:
            _append_row(t, "green", key)
        else:
            _append_row(t, "dim", f"{key}  (not captured)")
    t.append("\n")

    t.append("API Validation  ", style="bold")
    t.append("(GET /me/user)\n", style="dim")
    api = _run_api_check(profile)
    api_style = "green" if api.exit_code == 0 else ("dim" if api.exit_code == 2 else "red")
    _append_row(t, api_style, api.message)
    t.append("\n")

    t.append("Access Token Health\n", style="bold")
    access_token = creds.get("GAMECHANGER_ACCESS_TOKEN_MOBILE", "")
    _append_access_token_health(t, access_token)
    # AC-3: when access token is expired, show refresh token remaining lifetime.
    access_exp = _decode_jwt_exp(access_token) if access_token else None
    if access_exp is not None and access_exp < int(time.time()):
        _append_refresh_token_row(t, creds.get("GAMECHANGER_REFRESH_TOKEN_MOBILE", ""))

    _console.print(
        Panel(Text(t.plain.rstrip("\n"), spans=t._spans), title="Profile: mobile", expand=False)
    )
    _console.print(
        "Next: run [bold]bb creds check --profile mobile[/bold] for a full diagnostic."
    )


def _print_setup_guide() -> None:
    """Print the inline numbered setup guide when no proxy sessions exist."""
    _console.print(
        "[dim][--][/dim]  No proxy sessions found.\n"
        "\n"
        "  To capture mobile credentials:\n"
        "  1. Start mitmproxy (run on Mac host -- not from devcontainer):\n"
        "         cd proxy && ./start.sh\n"
        "  2. Configure your iPhone proxy settings to point to this machine.\n"
        "  3. Force-quit the GameChanger app, then reopen it\n"
        "         (the app sends POST /auth on cold start, not resume).\n"
        "  4. Stop the proxy:  cd proxy && ./stop.sh\n"
        "  5. Re-run: bb creds capture --profile mobile\n"
        "\n"
        "  See docs/admin/mitmproxy-guide.md for detailed setup instructions."
    )


def _print_capture_guidance(sessions_dir: Path) -> None:
    """Guide operator when no mobile credentials are present in .env."""
    _console.print("[yellow][!!][/yellow]  No mobile credentials found in .env.\n")

    session = _find_most_recent_session(sessions_dir)
    if session is None:
        _print_setup_guide()
        return

    _console.print(f"Most recent proxy session: [dim]{session.name}[/dim]")
    if _has_ios_traffic(session):
        _console.print(
            "[yellow][!!][/yellow]  iOS traffic was detected but credentials were not "
            "written to .env.\n"
            "      The app may have resumed without triggering POST /auth. Try:\n"
            "      1. Force-quit the GameChanger app on your iPhone.\n"
            "      2. Reopen it while the proxy is running.\n"
            "      3. Re-run: bb creds capture --profile mobile"
        )
    else:
        _console.print(
            "[yellow][!!][/yellow]  No iOS traffic found in the most recent proxy session.\n"
            "      Verify your iPhone is configured to use this proxy, then:\n"
            "      1. Force-quit the GameChanger app on your iPhone.\n"
            "      2. Reopen it while the proxy is running.\n"
            "      3. Re-run: bb creds capture --profile mobile"
        )


def _write_env_update(extracted: ExtractedKey) -> None:
    """Write the extracted client key to .env and print confirmation + next steps.

    Args:
        extracted: The :class:`~src.gamechanger.key_extractor.ExtractedKey` to persist.

    Raises:
        typer.Exit: With code 1 if the atomic write fails.
    """
    new_values: dict[str, str] = {
        "GAMECHANGER_CLIENT_ID_WEB": extracted.client_id,
        "GAMECHANGER_CLIENT_KEY_WEB": extracted.client_key,
    }
    try:
        atomic_merge_env_file(str(_ENV_FILE), new_values)
    except OSError as exc:
        _err_console.print(f"[red]Error:[/red] Failed to write .env: {exc}")
        raise typer.Exit(code=1)

    _console.print("")
    _console.print(
        "[green]Updated GAMECHANGER_CLIENT_KEY_WEB and GAMECHANGER_CLIENT_ID_WEB in .env[/green]"
    )
    _console.print(
        "Next: run [bold]bb creds check --profile web[/bold] to verify, "
        "then [bold]bb creds refresh --profile web[/bold] to test token refresh."
    )


@app.command(name="extract-key")
def extract_key(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write updated keys to .env (default: dry run -- print diff only).",
    ),
) -> None:
    """Fetch the current GameChanger client key from the public JS bundle.

    Compares the extracted key against .env and shows what would change.
    Pass --apply to write updated values to .env.
    """
    # Dry-run banner (AC-4a)
    if not apply:
        _console.print("[dim]Dry run -- pass --apply to write to .env[/dim]")
        _console.print("")

    _console.print("Fetching client key from GC JS bundle...")
    try:
        extracted = extract_client_key()
    except KeyExtractionError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    # Load current .env values for comparison.
    env = dotenv_values(str(_ENV_FILE))
    current_client_id = env.get("GAMECHANGER_CLIENT_ID_WEB") or ""
    current_client_key = env.get("GAMECHANGER_CLIENT_KEY_WEB") or ""

    id_changed = extracted.client_id != current_client_id
    key_changed = extracted.client_key != current_client_key

    # AC-4: show diff (never expose key values; UUID client_id is shown)
    _console.print("")
    if id_changed:
        _console.print(
            f"Client ID: {current_client_id or '(not set)'} -> {extracted.client_id}"
        )
    else:
        _console.print(f"Client ID: \\[unchanged] ({extracted.client_id})")

    if key_changed:
        _console.print("Client Key: \\[changed]")
    else:
        _console.print("Client key is current (no update needed).")

    if not key_changed and not id_changed:
        # Nothing to update -- exit cleanly.
        raise typer.Exit(code=0)

    if not apply:
        # Dry run: show what would happen but don't write.
        _console.print("")
        _console.print(
            "Run [bold]bb creds extract-key --apply[/bold] to write the updated key to .env."
        )
        raise typer.Exit(code=0)

    _write_env_update(extracted)


@app.command()
def capture(
    profile: str = typer.Option(
        "mobile",
        "--profile",
        metavar="PROFILE",
        help="Credential profile to capture: mobile (default).",
    ),
) -> None:
    """Scan .env for proxy-captured credentials and validate them."""
    if profile != "mobile":
        _err_console.print(
            "[red]Error:[/red] bb creds capture currently supports --profile mobile only.\n"
            "For web credentials, use: bb creds import"
        )
        raise typer.Exit(code=1)

    env = dotenv_values(str(_ENV_FILE))
    creds = {k: env[k] for k in _MOBILE_CRED_KEYS if env.get(k)}

    if creds:
        _print_capture_result(creds, profile)
        raise typer.Exit(code=0)

    _print_capture_guidance(_SESSIONS_DIR)
    raise typer.Exit(code=1)
