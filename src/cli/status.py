"""bb status -- system health dashboard (top-level command, not a sub-app)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from src.gamechanger.credentials import check_single_profile

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _PROJECT_ROOT / "data"
_DB_PATH = _DATA_ROOT / "app.db"
_RAW_DATA_ROOT = _DATA_ROOT / "raw"
_PROXY_SESSIONS_DIR = _PROJECT_ROOT / "proxy" / "data" / "sessions"

_PROFILES: tuple[str, ...] = ("web", "mobile")


def _human_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable string (KB / MB / GB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes:.1f} TB"


def _get_credential_status() -> dict[str, tuple[int, str]]:
    """Return per-profile credential check results.

    Returns:
        Mapping of profile name to (exit_code, message) pairs.
        Exit codes: 0=valid, 1=expired/error, 2=missing.
    """
    results: dict[str, tuple[int, str]] = {}
    for profile in _PROFILES:
        results[profile] = check_single_profile(profile)
    return results


def _get_last_crawl() -> tuple[str | None, int]:
    """Find the most recent manifest.json and return (crawled_at, total_files).

    Returns:
        (crawled_at_str, total_files) where crawled_at_str is None if no manifest exists.
    """
    manifests = list(_RAW_DATA_ROOT.glob("*/manifest.json"))
    if not manifests:
        return (None, 0)

    best_ts: str | None = None
    best_files = 0
    for manifest_path in manifests:
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            ts = data.get("crawled_at", "")
            crawlers = data.get("crawlers", {})
            total = sum(
                c.get("files_written", 0) for c in crawlers.values()
            )
            if best_ts is None or ts > best_ts:
                best_ts = ts
                best_files = total
        except (OSError, json.JSONDecodeError):
            continue

    return (best_ts, best_files)


def _format_crawled_at(raw_ts: str) -> str:
    """Convert ISO8601 UTC timestamp from manifest to a display string.

    Converts ``"2026-03-05T14:30:00Z"`` -> ``"2026-03-05 14:30:00"``.
    """
    return raw_ts.replace("T", " ").rstrip("Z")


def _get_db_info() -> tuple[bool, str]:
    """Return (exists, display_string) for data/app.db."""
    if not _DB_PATH.exists():
        return (False, "")
    size = _DB_PATH.stat().st_size
    return (True, f"{_DB_PATH.relative_to(_PROJECT_ROOT)} ({_human_size(size)})")


def _get_proxy_sessions() -> dict | None:
    """Scan proxy/data/sessions/ and return summary info, or None if unavailable.

    Returns a dict with keys:
        total: int
        unreviewed: int
        latest_id: str | None
        latest_ts: str | None  (started_at from most recent session)
    or None if the sessions directory does not exist or has no sessions.
    """
    if not _PROXY_SESSIONS_DIR.exists():
        return None

    session_dirs = sorted(
        [d for d in _PROXY_SESSIONS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    if not session_dirs:
        return None

    total = 0
    unreviewed = 0
    latest_id: str | None = None
    latest_ts: str | None = None

    for session_dir in session_dirs:
        session_file = session_dir / "session.json"
        if not session_file.exists():
            continue
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        total += 1
        if not data.get("reviewed", True):
            unreviewed += 1

        # Track the latest session (last in sorted order = most recent by name)
        latest_id = data.get("session_id", session_dir.name)
        latest_ts = data.get("started_at")

    if total == 0:
        return None

    return {
        "total": total,
        "unreviewed": unreviewed,
        "latest_id": latest_id,
        "latest_ts": latest_ts,
    }


def run() -> None:
    """Print a system health summary (credentials, database, crawl, proxy session)."""
    console = Console()

    # Determine if we're in a terminal for color support (rich auto-detects this,
    # but we explicitly create Console() without force_terminal so it respects piped output).
    label_width = 26  # for aligned output

    # --- Credentials ---
    cred_results = _get_credential_status()
    creds_failed = False
    for profile, (code, msg) in cred_results.items():
        label = f"Credentials ({profile}):"
        if code == 0:
            # msg is like "valid -- logged in as Jason Smith"
            display = msg.replace("valid -- logged in as ", "valid (logged in as ") + ")"
            console.print(f"  {label:<{label_width}} [green]{display}[/green]")
        elif code == 2:
            console.print(
                f"  {label:<{label_width}} [red]missing -> run: bb creds refresh[/red]"
            )
            creds_failed = True
        else:
            console.print(
                f"  {label:<{label_width}} [red]expired -> run: bb creds refresh[/red]"
            )
            creds_failed = True

    # --- Last crawl ---
    crawled_at, total_files = _get_last_crawl()
    label = "Last crawl:"
    if crawled_at is None:
        console.print(f"  {label:<{label_width}} [yellow]never[/yellow]")
    else:
        display_ts = _format_crawled_at(crawled_at)
        console.print(f"  {label:<{label_width}} {display_ts} ({total_files} files)")

    # --- Database ---
    db_exists, db_display = _get_db_info()
    label = "Database:"
    if db_exists:
        console.print(f"  {label:<{label_width}} {db_display}")
    else:
        console.print(
            f"  {label:<{label_width}} [yellow]not found -> run: bb data sync[/yellow]"
        )

    # --- Proxy sessions ---
    sessions = _get_proxy_sessions()
    label = "Proxy sessions:"
    if sessions is None:
        console.print(f"  {label:<{label_width}} [yellow]none[/yellow]")
    else:
        total = sessions["total"]
        unreviewed = sessions["unreviewed"]
        latest_id = sessions["latest_id"] or ""
        latest_ts = sessions.get("latest_ts") or ""
        summary = f"{total} total"
        if unreviewed:
            summary += f", {unreviewed} unreviewed"
        if latest_id:
            ts_display = ""
            if latest_ts:
                ts_display = _format_crawled_at(latest_ts) + ", "
            summary += f" (latest: {ts_display}{latest_id})"
        console.print(f"  {label:<{label_width}} {summary}")

    # Exit code: 1 if any credential is expired or missing; 0 otherwise.
    if creds_failed:
        raise typer.Exit(code=1)
