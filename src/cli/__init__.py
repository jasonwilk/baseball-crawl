"""baseball-crawl operator CLI.

Entry point: bb (registered via pyproject.toml [project.scripts]).
Fallback: python -m src.cli

Sub-command groups:
  bb creds   -- credential management (import, check)
  bb data    -- data crawl, load, sync
  bb proxy   -- proxy report, endpoints, refresh-headers, review
  bb db      -- database backup, reset
  bb status  -- system health check (top-level command)
"""

from __future__ import annotations

import logging

# Initialize logging BEFORE any script imports so this config wins (basicConfig is
# first-caller-wins; scripts call it at module level, so we must beat them).
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

import typer  # noqa: E402 -- after logging setup

from src.cli import creds, data, db, proxy, report, status  # noqa: E402

app = typer.Typer(
    name="bb",
    help="baseball-crawl operator CLI",
    add_completion=False,
    invoke_without_command=True,
    epilog="Run 'bb COMMAND --help' for more information on a command.",
)

app.add_typer(creds.app, name="creds")
app.add_typer(data.app, name="data")
app.add_typer(proxy.app, name="proxy")
app.add_typer(db.app, name="db")
app.add_typer(report.app, name="report")
app.command(name="status")(status.run)


@app.callback()
def main(ctx: typer.Context) -> None:
    """baseball-crawl operator CLI"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
