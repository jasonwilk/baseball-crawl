"""bb proxy -- proxy analysis and diagnostics commands.

Covers two distinct proxy systems:

- **mitmproxy** (traffic capture): ``report``, ``endpoints``, ``refresh-headers``,
  and ``review`` commands analyse captured sessions from the Mac-host mitmproxy
  process.  These commands read files from ``proxy/data/`` and run shell scripts;
  they cannot be run from inside the devcontainer.

- **Bright Data** (IP anonymization): ``check`` verifies that outgoing API
  requests are routing through the configured Bright Data residential proxy.
  Reads ``PROXY_ENABLED``, ``PROXY_URL_WEB``, and ``PROXY_URL_MOBILE`` from
  ``.env`` and does not require GameChanger credentials.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Optional

import typer

from src.http.proxy_check import (
    ProxyCheckOutcome,
    check_proxy_routing,
    get_direct_ip,
)

app = typer.Typer(
    help="Proxy analysis commands.",
    invoke_without_command=True,
    epilog="Run 'bb proxy COMMAND --help' for more information on a command.",
)


@app.callback()
def _proxy_group(ctx: typer.Context) -> None:
    """Proxy analysis commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_refresh_headers_module():
    """Load scripts/proxy-refresh-headers.py via importlib (hyphenated filename)."""
    script_path = _PROJECT_ROOT / "scripts" / "proxy-refresh-headers.py"
    spec = importlib.util.spec_from_file_location("proxy_refresh_headers", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@app.command()
def report(
    session: Optional[str] = typer.Option(None, "--session", help="Session ID to report on."),
    all_sessions: bool = typer.Option(False, "--all", help="Report on the most recent closed session."),
) -> None:
    """Show header parity report from proxy captures."""
    cmd = ["scripts/proxy-report.sh"]
    if session:
        cmd.extend(["--session", session])
    if all_sessions:
        cmd.append("--all")
    result = subprocess.run(cmd, cwd=_PROJECT_ROOT, check=False)
    raise SystemExit(result.returncode)


@app.command()
def endpoints(
    session: Optional[str] = typer.Option(None, "--session", help="Session ID to inspect."),
    all_sessions: bool = typer.Option(False, "--all", help="Aggregate across all sessions."),
    unreviewed: bool = typer.Option(False, "--unreviewed", help="Aggregate across unreviewed sessions only."),
) -> None:
    """Show deduplicated endpoint summary from proxy captures."""
    cmd = ["scripts/proxy-endpoints.sh"]
    if session:
        cmd.extend(["--session", session])
    if all_sessions:
        cmd.append("--all")
    if unreviewed:
        cmd.append("--unreviewed")
    result = subprocess.run(cmd, cwd=_PROJECT_ROOT, check=False)
    raise SystemExit(result.returncode)


@app.command(name="refresh-headers")
def refresh_headers(
    apply: bool = typer.Option(False, "--apply", help="Write changes to src/http/headers.py (default: dry-run)."),
) -> None:
    """Refresh src/http/headers.py from the latest mitmproxy capture (dry-run by default)."""
    module = _load_refresh_headers_module()
    exit_code = module.run(apply=apply)
    raise SystemExit(exit_code)


@app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def review(ctx: typer.Context) -> None:
    """Manage proxy session review status (list, mark).

    Forwards all arguments to scripts/proxy-review.sh.
    Examples: bb proxy review list, bb proxy review mark <session-id>, bb proxy review mark --all
    """
    cmd = ["scripts/proxy-review.sh", *ctx.args]
    result = subprocess.run(cmd, cwd=_PROJECT_ROOT, check=False)
    raise SystemExit(result.returncode)


_PROFILES = ["web", "mobile"]

_OUTCOME_LABELS = {
    ProxyCheckOutcome.PASS: "PASS",
    ProxyCheckOutcome.FAIL: "FAIL",
    ProxyCheckOutcome.ERROR: "ERROR",
    ProxyCheckOutcome.PASS_UNVERIFIED: "PASS-UNVERIFIED",
    ProxyCheckOutcome.NOT_CONFIGURED: "NOT CONFIGURED",
}


@app.command()
def check() -> None:
    """Verify Bright Data proxy routing for each configured profile.

    Makes one direct request (no proxy) plus one request per profile that has a
    configured proxy URL, hits an IP-echo service, and compares the returned IP
    addresses.  PASS means the proxy is routing correctly (proxy IP differs from
    direct IP).

    Always exits with code 0 -- this is a diagnostic tool, not a gate.
    Proxy URLs are never displayed (they contain credentials).
    """
    typer.echo("Checking Bright Data proxy routing...")
    typer.echo("")

    typer.echo("  Fetching direct IP (no proxy)... ", nl=False)
    direct_ip = get_direct_ip()
    if direct_ip:
        typer.echo(f"{direct_ip}")
    else:
        typer.echo("FAILED (network error -- proxy results will not be compared)")
    typer.echo("")

    for profile in _PROFILES:
        result = check_proxy_routing(profile, direct_ip)
        label = _OUTCOME_LABELS.get(result.outcome, result.outcome.value)

        if result.outcome == ProxyCheckOutcome.NOT_CONFIGURED:
            typer.echo(f"  [{profile}] {label} -- proxy not enabled or URL not set")

        elif result.outcome == ProxyCheckOutcome.ERROR:
            typer.echo(f"  [{profile}] {label} -- {result.error}")

        elif result.outcome == ProxyCheckOutcome.PASS:
            typer.echo(
                f"  [{profile}] {label} -- proxy IP {result.proxy_ip} "
                f"differs from direct IP {result.direct_ip}"
            )

        elif result.outcome == ProxyCheckOutcome.FAIL:
            typer.echo(
                f"  [{profile}] {label} -- proxy IP {result.proxy_ip} "
                f"matches direct IP {result.direct_ip} (not routing through proxy)"
            )

        elif result.outcome == ProxyCheckOutcome.PASS_UNVERIFIED:
            typer.echo(
                f"  [{profile}] {label} -- proxy returned IP {result.proxy_ip} "
                "(direct baseline unavailable, cannot compare)"
            )

    typer.echo("")
    typer.echo("Done.")
