"""bb proxy -- mitmproxy session commands (report, endpoints, refresh-headers, review)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Proxy analysis commands.")

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
