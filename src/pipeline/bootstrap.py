"""Bootstrap pipeline -- validate credentials and run the full crawl + load pipeline.

Runs four stages in order:
  1. Credential check    -- verifies .env credentials are valid (GET /me/user)
  2. Team config check   -- verifies config/teams.yaml has real team IDs
  3. Crawl               -- fetches all data from the GameChanger API
  4. Load                -- writes crawled data into the SQLite database

Exits early with a clear message if any pre-flight check fails. Crawl
failures are non-fatal -- partial crawl data is still loaded.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console

from src.gamechanger.config import load_config
from src.gamechanger.credentials import check_credentials
from src.pipeline import crawl as crawl_module
from src.pipeline import load as load_module

logger = logging.getLogger(__name__)

# Repo root: src/pipeline/bootstrap.py is 3 levels deep, so .parents[2] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "teams.yaml"

_console = Console()


def _check_team_config() -> tuple[int, str]:
    """Validate that config/teams.yaml has at least one non-placeholder team.

    Returns:
        (exit_code, message): 0 with team summary on success,
        1 with actionable message on failure.
    """
    try:
        config = load_config(_CONFIG_PATH)
    except FileNotFoundError:
        return (1, f"Team config file not found: {_CONFIG_PATH.relative_to(_PROJECT_ROOT)}")

    real_teams = [t for t in config.member_teams if not t.id.startswith("REPLACE_WITH_")]
    if not real_teams:
        return (
            1,
            "No teams configured -- edit config/teams.yaml (or use the admin UI once available)",
        )

    names = ", ".join(t.name for t in real_teams)
    return (0, f"{len(real_teams)} team(s) configured: {names}")


def run(
    check_only: bool = False,
    profile: str = "web",
    dry_run: bool = False,
) -> int:
    """Execute the bootstrap pipeline.

    Args:
        check_only: If True, run only credential and team config checks, then exit.
        profile: Header profile ("web" or "mobile") passed to the crawl stage.
        dry_run: If True, pass --dry-run through to crawl and load stages.

    Returns:
        Exit code: 0 if all stages succeeded, 1 on any failure.
    """
    summary: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Stage 1: Credential check
    # ------------------------------------------------------------------
    _console.print("Checking credentials...")
    cred_code, cred_msg = check_credentials(profile=profile)
    if cred_code == 0:
        _console.print(f"  [green]{cred_msg}[/green]")
    else:
        _console.print(f"  [red]{cred_msg}[/red]")
    summary["credentials"] = "valid" if cred_code == 0 else "expired/error"

    if cred_code != 0:
        _console.print("\n[red]Bootstrap aborted -- credentials must be valid before crawling.[/red]")
        _print_summary(summary)
        return 1

    # ------------------------------------------------------------------
    # Stage 2: Team config check
    # ------------------------------------------------------------------
    _console.print("Checking team configuration...")
    team_code, team_msg = _check_team_config()
    if team_code == 0:
        _console.print(f"  [green]{team_msg}[/green]")
    else:
        _console.print(f"  [yellow]{team_msg}[/yellow]")
    summary["teams"] = team_msg if team_code == 0 else "not configured"

    if team_code != 0:
        _console.print("\n[yellow]Bootstrap aborted -- configure teams before crawling.[/yellow]")
        _print_summary(summary)
        return 1

    if check_only:
        _console.print("\nCheck-only mode -- skipping crawl and load.")
        _print_summary(summary)
        return 0

    # ------------------------------------------------------------------
    # Stage 3: Crawl
    # ------------------------------------------------------------------
    _console.print("Crawling data...")
    crawl_code = crawl_module.run(dry_run=dry_run, profile=profile)
    if crawl_code != 0:
        _console.print(
            "  [yellow]WARNING: Crawl completed with errors. "
            "Partial data will still be loaded.[/yellow]"
        )
        summary["crawl"] = "warning (errors)"
    else:
        summary["crawl"] = "success"

    # ------------------------------------------------------------------
    # Stage 4: Load
    # ------------------------------------------------------------------
    _console.print("Loading data...")
    load_code = load_module.run(dry_run=dry_run)
    if load_code != 0:
        _console.print("  [red]ERROR: Load stage failed.[/red]")
        summary["load"] = "failed"
    else:
        summary["load"] = "success"

    _print_summary(summary)
    return 0 if (crawl_code == 0 and load_code == 0) else 1


def _print_summary(summary: dict[str, str]) -> None:
    """Print the pipeline summary using Rich Console with color coding.

    Args:
        summary: Mapping of stage name to outcome string.
    """
    _SUCCESS_OUTCOMES = {"valid", "success"}
    _FAILURE_KEYWORDS = {"failed", "expired", "error"}

    _console.print("\n[bold]--- Bootstrap summary ---[/bold]")
    for stage, outcome in summary.items():
        lower = outcome.lower()
        if outcome in _SUCCESS_OUTCOMES or "configured" in lower:
            _console.print(f"  [green]{stage}: {outcome}[/green]")
        elif any(kw in lower for kw in _FAILURE_KEYWORDS):
            _console.print(f"  [red]{stage}: {outcome}[/red]")
        else:
            _console.print(f"  [yellow]{stage}: {outcome}[/yellow]")
