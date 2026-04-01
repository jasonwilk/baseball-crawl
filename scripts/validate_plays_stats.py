#!/usr/bin/env python3
"""Validate derived FPS and QAB counts from the plays pipeline against GC season-stats.

Compares plays-derived FPS (per pitcher) and QAB (per batter) aggregates
against the ``player_season_pitching.fps`` and ``player_season_batting.qab``
columns populated by the season-stats API.  Produces a markdown validation
report with per-player comparisons, overall match rates, coverage stats,
and diagnostic detail for discrepancies exceeding 5% tolerance.

This is an operator tool -- run it post-dispatch when ``data/app.db`` has
both plays data and season stats loaded.

Usage::

    python scripts/validate_plays_stats.py [--db-path PATH] [--output PATH]

Options:
    --db-path PATH   Override DATABASE_PATH env var (default: ``data/app.db``).
    --output PATH    Override output location (default: ``.project/research/E-195-validation-results.md``).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# Add project root to sys.path so ``src`` is importable when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

# Default tolerance percentage.
TOLERANCE_PCT = 5.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PlayerComparison:
    """Comparison result for a single player's derived vs GC stat."""

    player_id: str
    season_id: str
    player_name: str
    team_name: str
    derived_value: int
    gc_value: int
    abs_diff: int
    pct_diff: float
    exceeds_tolerance: bool


@dataclass
class GameDiagnostic:
    """Diagnostic detail for a game contributing to a discrepancy."""

    game_id: str
    game_date: str
    play_count: int
    flag_count: int


@dataclass
class SamplePlay:
    """A sample play from a discrepancy investigation."""

    game_id: str
    play_order: int
    inning: int
    half: str
    outcome: str
    pitch_count: int
    flag_value: int


@dataclass
class ValidationReport:
    """Full validation report contents."""

    fps_comparisons: list[PlayerComparison]
    qab_comparisons: list[PlayerComparison]
    fps_match_rate: float
    qab_match_rate: float
    total_completed_games: int
    games_with_plays: int
    games_without_plays: list[tuple[str, str, str, str]]  # game_id, date, home, away
    fps_diagnostics: dict[str, list[GameDiagnostic]]  # player_id -> games
    qab_diagnostics: dict[str, list[GameDiagnostic]]  # player_id -> games
    fps_sample_plays: dict[str, list[SamplePlay]]  # player_id -> plays
    qab_sample_plays: dict[str, list[SamplePlay]]  # player_id -> plays


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------


def compute_derived_fps(
    db: sqlite3.Connection,
) -> dict[tuple[str, str], int]:
    """Aggregate derived FPS count per pitcher per season from the plays table.

    Uses the FPS% query pattern from TN-9: counts ``is_first_pitch_strike``
    where outcome is not in ('Hit By Pitch', 'Intentional Walk').

    Returns:
        Dict mapping (pitcher_player_id, season_id) to their derived FPS count.
    """
    rows = db.execute(
        """
        SELECT pitcher_id, season_id, SUM(is_first_pitch_strike)
        FROM plays
        WHERE pitcher_id IS NOT NULL
          AND outcome NOT IN ('Hit By Pitch', 'Intentional Walk')
        GROUP BY pitcher_id, season_id
        """
    ).fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


def compute_derived_qab(
    db: sqlite3.Connection,
) -> dict[tuple[str, str], int]:
    """Aggregate derived QAB count per batter per season from the plays table.

    Returns:
        Dict mapping (batter_player_id, season_id) to their derived QAB count.
    """
    rows = db.execute(
        """
        SELECT batter_id, season_id, SUM(is_qab)
        FROM plays
        GROUP BY batter_id, season_id
        """
    ).fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


def get_gc_fps(db: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Retrieve GC season-stats FPS values per pitcher per season.

    Returns:
        Dict mapping (player_id, season_id) to their GC FPS count.
    """
    rows = db.execute(
        """
        SELECT player_id, season_id, fps
        FROM player_season_pitching
        WHERE fps IS NOT NULL
        """
    ).fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


def get_gc_qab(db: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Retrieve GC season-stats QAB values per batter per season.

    Returns:
        Dict mapping (player_id, season_id) to their GC QAB count.
    """
    rows = db.execute(
        """
        SELECT player_id, season_id, qab
        FROM player_season_batting
        WHERE qab IS NOT NULL
        """
    ).fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


def get_player_name(db: sqlite3.Connection, player_id: str) -> str:
    """Look up a player's display name."""
    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    if row is None:
        return "Unknown"
    return f"{row[0]} {row[1]}"


def get_player_team_name(
    db: sqlite3.Connection, player_id: str, stat_table: str,
) -> str:
    """Look up the team name for a player from their season stat table."""
    valid_tables = {"player_season_pitching", "player_season_batting"}
    if stat_table not in valid_tables:
        return "Unknown"
    row = db.execute(
        f"SELECT t.name FROM {stat_table} s "  # noqa: S608 -- table name validated above
        "JOIN teams t ON s.team_id = t.id "
        "WHERE s.player_id = ? LIMIT 1",
        (player_id,),
    ).fetchone()
    return row[0] if row else "Unknown"


def compare_stats(
    db: sqlite3.Connection,
    derived: dict[tuple[str, str], int],
    gc_values: dict[tuple[str, str], int],
    stat_table: str,
    tolerance_pct: float = TOLERANCE_PCT,
) -> list[PlayerComparison]:
    """Compare derived stat counts against GC season-stats values.

    Only compares (player, season) pairs present in both sources.

    Args:
        db: Database connection for name lookups.
        derived: Dict of (player_id, season_id) -> derived count.
        gc_values: Dict of (player_id, season_id) -> GC count.
        stat_table: The season stat table name for team lookups.
        tolerance_pct: Percentage threshold for flagging discrepancies.

    Returns:
        List of PlayerComparison results, sorted by player name.
    """
    common_keys = set(derived.keys()) & set(gc_values.keys())
    comparisons: list[PlayerComparison] = []

    for key in common_keys:
        pid, season_id = key
        d_val = derived[key]
        gc_val = gc_values[key]
        abs_diff = abs(d_val - gc_val)

        # Percentage difference relative to GC value.
        if gc_val > 0:
            pct_diff = (abs_diff / gc_val) * 100.0
        elif d_val > 0:
            pct_diff = 100.0  # GC says 0, we derived non-zero.
        else:
            pct_diff = 0.0  # Both zero.

        exceeds = pct_diff > tolerance_pct

        comparisons.append(PlayerComparison(
            player_id=pid,
            season_id=season_id,
            player_name=get_player_name(db, pid),
            team_name=get_player_team_name(db, pid, stat_table),
            derived_value=d_val,
            gc_value=gc_val,
            abs_diff=abs_diff,
            pct_diff=pct_diff,
            exceeds_tolerance=exceeds,
        ))

    comparisons.sort(key=lambda c: c.player_name)
    return comparisons


def compute_match_rate(comparisons: list[PlayerComparison]) -> float:
    """Compute the percentage of players within tolerance.

    Returns:
        Match rate as a percentage (0-100). Returns 100.0 if no comparisons.
    """
    if not comparisons:
        return 100.0
    within = sum(1 for c in comparisons if not c.exceeds_tolerance)
    return (within / len(comparisons)) * 100.0


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------


def compute_coverage(
    db: sqlite3.Connection,
) -> tuple[int, int, list[tuple[str, str, str, str]]]:
    """Compute plays data coverage for completed games.

    Returns:
        Tuple of (total_completed_games, games_with_plays, games_without_plays).
        ``games_without_plays`` is a list of (game_id, date, home_name, away_name).
    """
    # Completed games involving at least one member team.
    # The plays pipeline only crawls own-team games, so tracked-vs-tracked
    # games should not count as "missing plays".
    completed_rows = db.execute(
        """
        SELECT g.game_id, g.game_date,
               COALESCE(ht.name, 'Unknown') AS home_name,
               COALESCE(at.name, 'Unknown') AS away_name
        FROM games g
        LEFT JOIN teams ht ON g.home_team_id = ht.id
        LEFT JOIN teams at ON g.away_team_id = at.id
        WHERE (g.status = 'completed' OR g.home_score IS NOT NULL)
          AND (ht.membership_type = 'member' OR at.membership_type = 'member')
        """
    ).fetchall()

    total = len(completed_rows)

    # Games with at least one play.
    games_with_plays_set = set()
    rows = db.execute("SELECT DISTINCT game_id FROM plays").fetchall()
    for row in rows:
        games_with_plays_set.add(row[0])

    games_with = 0
    games_without: list[tuple[str, str, str, str]] = []
    for game_id, game_date, home_name, away_name in completed_rows:
        if game_id in games_with_plays_set:
            games_with += 1
        else:
            games_without.append((game_id, game_date, home_name, away_name))

    return total, games_with, games_without


# ---------------------------------------------------------------------------
# Diagnostics for discrepancies
# ---------------------------------------------------------------------------


def get_fps_game_diagnostics(
    db: sqlite3.Connection, pitcher_id: str,
) -> list[GameDiagnostic]:
    """Get per-game FPS breakdown for a pitcher exceeding tolerance.

    Returns:
        List of GameDiagnostic with play counts and FPS flag counts per game.
    """
    rows = db.execute(
        """
        SELECT p.game_id,
               COALESCE(g.game_date, 'unknown'),
               COUNT(*) AS play_count,
               SUM(p.is_first_pitch_strike) AS fps_count
        FROM plays p
        LEFT JOIN games g ON p.game_id = g.game_id
        WHERE p.pitcher_id = ?
          AND p.outcome NOT IN ('Hit By Pitch', 'Intentional Walk')
        GROUP BY p.game_id
        ORDER BY g.game_date
        """,
        (pitcher_id,),
    ).fetchall()

    return [
        GameDiagnostic(
            game_id=row[0],
            game_date=row[1],
            play_count=row[2],
            flag_count=row[3],
        )
        for row in rows
    ]


def get_qab_game_diagnostics(
    db: sqlite3.Connection, batter_id: str,
) -> list[GameDiagnostic]:
    """Get per-game QAB breakdown for a batter exceeding tolerance.

    Returns:
        List of GameDiagnostic with play counts and QAB flag counts per game.
    """
    rows = db.execute(
        """
        SELECT p.game_id,
               COALESCE(g.game_date, 'unknown'),
               COUNT(*) AS play_count,
               SUM(p.is_qab) AS qab_count
        FROM plays p
        LEFT JOIN games g ON p.game_id = g.game_id
        WHERE p.batter_id = ?
        GROUP BY p.game_id
        ORDER BY g.game_date
        """,
        (batter_id,),
    ).fetchall()

    return [
        GameDiagnostic(
            game_id=row[0],
            game_date=row[1],
            play_count=row[2],
            flag_count=row[3],
        )
        for row in rows
    ]


def get_fps_sample_plays(
    db: sqlite3.Connection, pitcher_id: str, limit: int = 5,
) -> list[SamplePlay]:
    """Get sample plays for a pitcher to assist debugging FPS discrepancies.

    Returns plays where the FPS flag is set, for inspection.
    """
    rows = db.execute(
        """
        SELECT game_id, play_order, inning, half, outcome, pitch_count,
               is_first_pitch_strike
        FROM plays
        WHERE pitcher_id = ?
          AND outcome NOT IN ('Hit By Pitch', 'Intentional Walk')
        ORDER BY game_id, play_order
        LIMIT ?
        """,
        (pitcher_id, limit),
    ).fetchall()

    return [
        SamplePlay(
            game_id=row[0],
            play_order=row[1],
            inning=row[2],
            half=row[3],
            outcome=row[4],
            pitch_count=row[5],
            flag_value=row[6],
        )
        for row in rows
    ]


def get_qab_sample_plays(
    db: sqlite3.Connection, batter_id: str, limit: int = 5,
) -> list[SamplePlay]:
    """Get sample plays for a batter to assist debugging QAB discrepancies.

    Returns plays where the QAB flag is set, for inspection.
    """
    rows = db.execute(
        """
        SELECT game_id, play_order, inning, half, outcome, pitch_count, is_qab
        FROM plays
        WHERE batter_id = ?
        ORDER BY game_id, play_order
        LIMIT ?
        """,
        (batter_id, limit),
    ).fetchall()

    return [
        SamplePlay(
            game_id=row[0],
            play_order=row[1],
            inning=row[2],
            half=row[3],
            outcome=row[4],
            pitch_count=row[5],
            flag_value=row[6],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def build_report(db: sqlite3.Connection) -> ValidationReport:
    """Build the full validation report from database contents.

    Aggregates derived stats, compares against GC values, computes coverage,
    and collects diagnostics for outliers.
    """
    derived_fps = compute_derived_fps(db)
    derived_qab = compute_derived_qab(db)
    gc_fps = get_gc_fps(db)
    gc_qab = get_gc_qab(db)

    fps_comparisons = compare_stats(
        db, derived_fps, gc_fps, "player_season_pitching",
    )
    qab_comparisons = compare_stats(
        db, derived_qab, gc_qab, "player_season_batting",
    )

    fps_match_rate = compute_match_rate(fps_comparisons)
    qab_match_rate = compute_match_rate(qab_comparisons)

    total_completed, games_with, games_without = compute_coverage(db)

    # Diagnostics for players exceeding tolerance.
    fps_diagnostics: dict[str, list[GameDiagnostic]] = {}
    fps_sample_plays: dict[str, list[SamplePlay]] = {}
    for comp in fps_comparisons:
        if comp.exceeds_tolerance:
            fps_diagnostics[comp.player_id] = get_fps_game_diagnostics(
                db, comp.player_id,
            )
            fps_sample_plays[comp.player_id] = get_fps_sample_plays(
                db, comp.player_id,
            )

    qab_diagnostics: dict[str, list[GameDiagnostic]] = {}
    qab_sample_plays: dict[str, list[SamplePlay]] = {}
    for comp in qab_comparisons:
        if comp.exceeds_tolerance:
            qab_diagnostics[comp.player_id] = get_qab_game_diagnostics(
                db, comp.player_id,
            )
            qab_sample_plays[comp.player_id] = get_qab_sample_plays(
                db, comp.player_id,
            )

    return ValidationReport(
        fps_comparisons=fps_comparisons,
        qab_comparisons=qab_comparisons,
        fps_match_rate=fps_match_rate,
        qab_match_rate=qab_match_rate,
        total_completed_games=total_completed,
        games_with_plays=games_with,
        games_without_plays=games_without,
        fps_diagnostics=fps_diagnostics,
        qab_diagnostics=qab_diagnostics,
        fps_sample_plays=fps_sample_plays,
        qab_sample_plays=qab_sample_plays,
    )


def format_report(report: ValidationReport) -> str:
    """Render the validation report as markdown.

    Returns:
        Markdown string ready to write to a file.
    """
    lines: list[str] = []
    lines.append("# E-195 Plays Pipeline Validation Results")
    lines.append("")
    lines.append("Automated comparison of plays-derived FPS and QAB counts")
    lines.append("against GC season-stats API values.")
    lines.append("")

    # ---- Coverage ----
    lines.append("## Plays Data Coverage")
    lines.append("")
    total = report.total_completed_games
    with_plays = report.games_with_plays
    pct = (with_plays / total * 100.0) if total > 0 else 0.0
    lines.append(f"- **Completed games**: {total}")
    lines.append(f"- **Games with plays data**: {with_plays} ({pct:.1f}%)")
    lines.append(
        f"- **Games without plays data**: {total - with_plays}",
    )
    lines.append("")

    if report.games_without_plays:
        lines.append("### Games Missing Plays Data")
        lines.append("")
        lines.append("| Game ID | Date | Home | Away |")
        lines.append("|---------|------|------|------|")
        for game_id, date, home, away in report.games_without_plays:
            lines.append(f"| `{game_id}` | {date} | {home} | {away} |")
        lines.append("")

    # ---- FPS Comparison ----
    lines.append("## FPS (First Pitch Strike) Comparison")
    lines.append("")
    lines.append(f"**Overall match rate**: {report.fps_match_rate:.1f}%")
    lines.append(
        f"({sum(1 for c in report.fps_comparisons if not c.exceeds_tolerance)}"
        f" of {len(report.fps_comparisons)} pitchers within {TOLERANCE_PCT}% tolerance)"
    )
    lines.append("")

    if report.fps_comparisons:
        lines.append("| Player | Team | Derived | GC | Diff | % Diff | Status |")
        lines.append("|--------|------|---------|----|------|--------|--------|")
        for comp in report.fps_comparisons:
            status = "MISMATCH" if comp.exceeds_tolerance else "OK"
            lines.append(
                f"| {comp.player_name} | {comp.team_name} "
                f"| {comp.derived_value} | {comp.gc_value} "
                f"| {comp.abs_diff} | {comp.pct_diff:.1f}% | {status} |"
            )
        lines.append("")
    else:
        lines.append("*No pitchers found with data in both plays and season-stats.*")
        lines.append("")

    # FPS diagnostics
    fps_outliers = [c for c in report.fps_comparisons if c.exceeds_tolerance]
    if fps_outliers:
        lines.append("### FPS Discrepancy Diagnostics")
        lines.append("")
        for comp in fps_outliers:
            lines.append(f"#### {comp.player_name} ({comp.team_name})")
            lines.append(
                f"Derived={comp.derived_value}, GC={comp.gc_value}, "
                f"Diff={comp.abs_diff} ({comp.pct_diff:.1f}%)"
            )
            lines.append("")

            diags = report.fps_diagnostics.get(comp.player_id, [])
            if diags:
                lines.append("**Per-game breakdown:**")
                lines.append("")
                lines.append("| Game | Date | PAs | FPS Count |")
                lines.append("|------|------|-----|-----------|")
                for d in diags:
                    lines.append(
                        f"| `{d.game_id}` | {d.game_date} "
                        f"| {d.play_count} | {d.flag_count} |"
                    )
                lines.append("")

            samples = report.fps_sample_plays.get(comp.player_id, [])
            if samples:
                lines.append("**Sample plays:**")
                lines.append("")
                lines.append(
                    "| Game | Order | Inn | Half | Outcome | Pitches | FPS |"
                )
                lines.append(
                    "|------|-------|-----|------|---------|---------|-----|"
                )
                for s in samples:
                    lines.append(
                        f"| `{s.game_id}` | {s.play_order} | {s.inning} "
                        f"| {s.half} | {s.outcome} | {s.pitch_count} "
                        f"| {s.flag_value} |"
                    )
                lines.append("")

    # ---- QAB Comparison ----
    lines.append("## QAB (Quality At-Bat) Comparison")
    lines.append("")
    lines.append(f"**Overall match rate**: {report.qab_match_rate:.1f}%")
    lines.append(
        f"({sum(1 for c in report.qab_comparisons if not c.exceeds_tolerance)}"
        f" of {len(report.qab_comparisons)} batters within {TOLERANCE_PCT}% tolerance)"
    )
    lines.append("")

    if report.qab_comparisons:
        lines.append("| Player | Team | Derived | GC | Diff | % Diff | Status |")
        lines.append("|--------|------|---------|----|------|--------|--------|")
        for comp in report.qab_comparisons:
            status = "MISMATCH" if comp.exceeds_tolerance else "OK"
            lines.append(
                f"| {comp.player_name} | {comp.team_name} "
                f"| {comp.derived_value} | {comp.gc_value} "
                f"| {comp.abs_diff} | {comp.pct_diff:.1f}% | {status} |"
            )
        lines.append("")
    else:
        lines.append("*No batters found with data in both plays and season-stats.*")
        lines.append("")

    # QAB diagnostics
    qab_outliers = [c for c in report.qab_comparisons if c.exceeds_tolerance]
    if qab_outliers:
        lines.append("### QAB Discrepancy Diagnostics")
        lines.append("")
        for comp in qab_outliers:
            lines.append(f"#### {comp.player_name} ({comp.team_name})")
            lines.append(
                f"Derived={comp.derived_value}, GC={comp.gc_value}, "
                f"Diff={comp.abs_diff} ({comp.pct_diff:.1f}%)"
            )
            lines.append("")

            diags = report.qab_diagnostics.get(comp.player_id, [])
            if diags:
                lines.append("**Per-game breakdown:**")
                lines.append("")
                lines.append("| Game | Date | PAs | QAB Count |")
                lines.append("|------|------|-----|-----------|")
                for d in diags:
                    lines.append(
                        f"| `{d.game_id}` | {d.game_date} "
                        f"| {d.play_count} | {d.flag_count} |"
                    )
                lines.append("")

            samples = report.qab_sample_plays.get(comp.player_id, [])
            if samples:
                lines.append("**Sample plays:**")
                lines.append("")
                lines.append(
                    "| Game | Order | Inn | Half | Outcome | Pitches | QAB |"
                )
                lines.append(
                    "|------|-------|-----|------|---------|---------|-----|"
                )
                for s in samples:
                    lines.append(
                        f"| `{s.game_id}` | {s.play_order} | {s.inning} "
                        f"| {s.half} | {s.outcome} | {s.pitch_count} "
                        f"| {s.flag_value} |"
                    )
                lines.append("")

    # ---- Summary ----
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- FPS match rate: **{report.fps_match_rate:.1f}%**")
    lines.append(f"- QAB match rate: **{report.qab_match_rate:.1f}%**")
    lines.append(
        f"- Plays coverage: **{report.games_with_plays}/{report.total_completed_games}** "
        f"completed games"
    )
    fps_outlier_count = len(fps_outliers) if fps_outliers else 0
    qab_outlier_count = len(qab_outliers) if qab_outliers else 0
    lines.append(f"- FPS outliers (>{TOLERANCE_PCT}%): **{fps_outlier_count}**")
    lines.append(f"- QAB outliers (>{TOLERANCE_PCT}%): **{qab_outlier_count}**")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the validation and write the report.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Validate plays-derived FPS/QAB against GC season-stats.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/app.db"),
        help="Path to the SQLite database (default: data/app.db).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".project/research/E-195-validation-results.md"),
        help="Output path for the validation report.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    db_path: Path = args.db_path
    if not db_path.exists():
        logger.error("Database not found at %s", db_path)
        return 1

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
    except sqlite3.Error as exc:
        logger.error("Failed to connect to database: %s", exc)
        return 1

    try:
        report = build_report(conn)
        markdown = format_report(report)
    except sqlite3.Error as exc:
        logger.error("Database query error: %s", exc)
        return 1
    finally:
        conn.close()

    # Write the report.
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Validation report written to {output_path}")
    print(f"FPS match rate: {report.fps_match_rate:.1f}%")
    print(f"QAB match rate: {report.qab_match_rate:.1f}%")
    print(
        f"Plays coverage: {report.games_with_plays}/{report.total_completed_games} "
        f"completed games"
    )

    outlier_count = sum(
        1 for c in report.fps_comparisons + report.qab_comparisons
        if c.exceeds_tolerance
    )
    if outlier_count > 0:
        print(f"\nWARNING: {outlier_count} player(s) exceed {TOLERANCE_PCT}% tolerance.")
        print("See diagnostics in the report for details.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
