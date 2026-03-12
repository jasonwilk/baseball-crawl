"""Game loader for the baseball-crawl ingestion pipeline.

Reads boxscore JSON files written by the game-stats crawler and upserts game
records and per-player batting/pitching lines into the SQLite database.

Expected file layout (written by GameStatsCrawler)::

    data/raw/{season}/teams/{team_id}/games/{game_stream_id}.json

The loader also reads game-summaries files (one per team directory) to build a
``game_stream_id -> event_id`` mapping and resolve ``home_away`` assignments::

    data/raw/{season}/teams/{team_id}/game_summaries.json

``games.game_id`` uses the ``event_id`` from game-summaries (not the
``game_stream_id``).

Key data decisions
------------------
- **ID mapping**: file name is ``game_stream_id``; DB primary key is ``event_id``.
  The game-summaries index is required to resolve this mapping.
- **Asymmetric boxscore keys**: own team key = public_id slug (alphanumeric, no
  dashes); opponent key = UUID (lowercase hex with dashes, 36 chars).
- **IP to ip_outs**: boxscore stores IP as float decimal innings (e.g. 3.333...
  = 3⅓ innings = 10 outs).  The schema stores ``ip_outs`` (integer outs).
  Convert: ``ip_outs = round(float(IP) * 3)``.
- **Sparse extras**: the ``extra[]`` array in each group contains only non-zero
  player values.  Missing values default to 0.
- **Stub players**: unknown player_ids get a stub row (first_name='Unknown',
  last_name='Unknown') before the stat insert (FK-safe).

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.game_loader import GameLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = GameLoader(conn, season_id="2025", owned_team_id="abc-team-uuid")
    result = loader.load_all(Path("data/raw/2025/teams/abc-team-uuid"))
    print(result)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from src.gamechanger.loaders import LoadResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# UUID pattern: 8-4-4-4-12 hex digits with dashes (36 chars total)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Batting stats mapped from boxscore to DB columns.
# Stats present in the main stats object (always):
_BATTING_MAIN: dict[str, str] = {
    "AB": "ab",
    "H": "h",
    "RBI": "rbi",
    "BB": "bb",
    "SO": "so",
}
# "R" is not in the schema -- log at DEBUG, do not store.
_BATTING_SKIP_DEBUG = {"R", "TB"}

# Extras mapped from stat_name to DB column:
_BATTING_EXTRAS: dict[str, str] = {
    "2B": "doubles",
    "3B": "triples",
    "HR": "hr",
    "SB": "sb",
}
# Extras not in batting schema -- log at DEBUG, do not store.
_BATTING_EXTRAS_SKIP_DEBUG = {"TB", "HBP", "CS", "E"}

# Pitching stats mapped from boxscore to DB columns.
_PITCHING_MAIN: dict[str, str] = {
    "H": "h",
    "ER": "er",
    "BB": "bb",
    "SO": "so",
}
# "IP" is converted to ip_outs (not a simple name mapping).
# "R" is not in the schema.
_PITCHING_SKIP_DEBUG = {"R"}
# Pitching extras not in schema:
_PITCHING_EXTRAS_SKIP_DEBUG = {"WP", "HBP", "#P", "TS", "BF", "HR"}


# ---------------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GameSummaryEntry:
    """Parsed entry from a game-summaries file.

    Attributes:
        event_id: Canonical game UUID (games.game_id PK).
        game_stream_id: Boxscore file key (used as filename).
        home_away: 'home', 'away', or None.
        owning_team_score: Score for the team that owns the game-summaries file.
        opponent_team_score: Score for the opponent team.
        opponent_id: UUID of the opponent team.
        last_scoring_update: ISO 8601 timestamp string.
    """

    event_id: str
    game_stream_id: str
    home_away: str | None
    owning_team_score: int
    opponent_team_score: int
    opponent_id: str
    last_scoring_update: str


@dataclass
class _PlayerBatting:
    """Per-player batting line ready for DB insertion."""

    player_id: str
    ab: int = 0
    h: int = 0
    doubles: int = 0
    triples: int = 0
    hr: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0
    sb: int = 0


@dataclass
class _PlayerPitching:
    """Per-player pitching line ready for DB insertion."""

    player_id: str
    ip_outs: int = 0
    h: int = 0
    er: int = 0
    bb: int = 0
    so: int = 0
    hr: int = 0


# ---------------------------------------------------------------------------
# GameLoader
# ---------------------------------------------------------------------------


class GameLoader:
    """Loads boxscore JSON files into the SQLite database.

    Reads all ``games/{game_stream_id}.json`` files in a team directory, maps
    them to canonical ``event_id`` values via the game-summaries index, and
    upserts game records plus per-player batting and pitching lines.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
        season_id: Season slug used as FK in all inserts (e.g. ``'2025'``).
        owned_team_id: UUID of the team that owns the data directory.  Used to
            identify which boxscore key belongs to the owned team vs. the
            opponent.
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        season_id: str,
        owned_team_id: str,
    ) -> None:
        self._db = db
        self._season_id = season_id
        self._owned_team_id = owned_team_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self, team_dir: Path) -> LoadResult:
        """Load all boxscore files in a team directory.

        Reads ``game_summaries.json`` from ``team_dir`` to build the
        ``game_stream_id -> event_id`` index, then loads each
        ``games/{game_stream_id}.json`` file found in ``team_dir``.

        Args:
            team_dir: Path to ``data/raw/{season}/teams/{team_id}/``.

        Returns:
            Aggregated ``LoadResult`` across all game files.
        """
        summaries_index = self._build_summaries_index(team_dir)
        if summaries_index is None:
            return LoadResult(errors=1)

        games_dir = team_dir / "games"
        if not games_dir.is_dir():
            logger.info("No games directory at %s; nothing to load.", games_dir)
            return LoadResult()

        self._ensure_season_row(self._season_id)

        total = LoadResult()
        for boxscore_path in sorted(games_dir.glob("*.json")):
            game_stream_id = boxscore_path.stem
            summary = summaries_index.get(game_stream_id)
            if summary is None:
                logger.warning(
                    "No game-summaries entry for game_stream_id=%s; skipping %s",
                    game_stream_id,
                    boxscore_path,
                )
                total.skipped += 1
                continue

            result = self._load_boxscore_file(boxscore_path, summary)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors

        self._db.commit()
        logger.info(
            "Game load complete for %s: loaded=%d skipped=%d errors=%d",
            team_dir,
            total.loaded,
            total.skipped,
            total.errors,
        )
        return total

    def load_file(
        self, boxscore_path: Path, summary: GameSummaryEntry
    ) -> LoadResult:
        """Load a single boxscore file.

        Public for testing.  Callers must supply a matching ``GameSummaryEntry``
        with the resolved ``event_id``, ``home_away``, and score data.

        Args:
            boxscore_path: Path to a ``{game_stream_id}.json`` boxscore file.
            summary: Resolved game-summaries entry for this game.

        Returns:
            ``LoadResult`` for this single game.
        """
        result = self._load_boxscore_file(boxscore_path, summary)
        self._db.commit()
        return result

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_summaries_index(
        self, team_dir: Path
    ) -> dict[str, GameSummaryEntry] | None:
        """Build a ``game_stream_id -> GameSummaryEntry`` mapping.

        Reads ``game_summaries.json`` from ``team_dir`` and parses each record.

        Args:
            team_dir: Path to the team data directory.

        Returns:
            Dict keyed by ``game_stream_id``, or ``None`` on read error.
        """
        summaries_path = team_dir / "game_summaries.json"
        if not summaries_path.exists():
            logger.error(
                "game_summaries.json not found at %s; cannot build ID index.",
                summaries_path,
            )
            return None

        try:
            with summaries_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse %s: %s", summaries_path, exc)
            return None

        if not isinstance(raw, list):
            logger.error(
                "Expected JSON array in %s, got %s",
                summaries_path,
                type(raw).__name__,
            )
            return None

        index: dict[str, GameSummaryEntry] = {}
        for record in raw:
            entry = self._parse_summary_record(record)
            if entry is not None:
                index[entry.game_stream_id] = entry

        logger.info(
            "Built game-summaries index: %d entries from %s",
            len(index),
            summaries_path,
        )
        return index

    def _parse_summary_record(self, record: dict) -> GameSummaryEntry | None:
        """Parse one game-summaries record into a ``GameSummaryEntry``.

        Args:
            record: Raw dict from game_summaries.json array.

        Returns:
            Parsed entry, or ``None`` if required fields are missing.
        """
        event_id = record.get("event_id")
        game_stream = record.get("game_stream") or {}
        game_stream_id = game_stream.get("id")

        if not event_id or not game_stream_id:
            logger.warning(
                "Skipping summary record missing event_id or game_stream.id: %r", record
            )
            return None

        return GameSummaryEntry(
            event_id=str(event_id),
            game_stream_id=str(game_stream_id),
            home_away=record.get("home_away"),
            owning_team_score=int(record.get("owning_team_score") or 0),
            opponent_team_score=int(record.get("opponent_team_score") or 0),
            opponent_id=str(game_stream.get("opponent_id") or ""),
            last_scoring_update=str(record.get("last_scoring_update") or ""),
        )

    # ------------------------------------------------------------------
    # Core loading logic
    # ------------------------------------------------------------------

    def _load_boxscore_file(
        self, path: Path, summary: GameSummaryEntry
    ) -> LoadResult:
        """Parse and load a single boxscore JSON file.

        Args:
            path: Path to the boxscore JSON file.
            summary: Resolved game-summaries metadata for this game.

        Returns:
            ``LoadResult`` for this file.
        """
        raw = self._read_json(path)
        if raw is None:
            return LoadResult(errors=1)

        if not isinstance(raw, dict):
            logger.error(
                "Expected JSON object in %s, got %s", path, type(raw).__name__
            )
            return LoadResult(errors=1)

        # Detect which key is own team and which is opponent.
        own_key, opp_key = self._detect_team_keys(raw)
        if own_key is None and opp_key is None:
            logger.error("Could not identify team keys in boxscore %s", path)
            return LoadResult(errors=1)

        own_data = raw.get(own_key) if own_key else None
        opp_data = raw.get(opp_key) if opp_key else None

        # Resolve home/away for games table.
        home_away = summary.home_away  # 'home', 'away', or None
        own_team_id = self._owned_team_id
        opp_team_id = summary.opponent_id or (opp_key or "unknown-opponent")

        if home_away == "home":
            home_team_id = own_team_id
            away_team_id = opp_team_id
            home_score = summary.owning_team_score
            away_score = summary.opponent_team_score
        elif home_away == "away":
            home_team_id = opp_team_id
            away_team_id = own_team_id
            home_score = summary.opponent_team_score
            away_score = summary.owning_team_score
        else:
            # home_away is None -- use own team as home by convention, log warning.
            logger.warning(
                "home_away is None for game_id=%s; defaulting own team to home.",
                summary.event_id,
            )
            home_team_id = own_team_id
            away_team_id = opp_team_id
            home_score = summary.owning_team_score
            away_score = summary.opponent_team_score

        # Game date from last_scoring_update (YYYY-MM-DD prefix).
        game_date = summary.last_scoring_update[:10] if summary.last_scoring_update else "1900-01-01"

        # Ensure FK prerequisite rows.
        self._ensure_team_row(home_team_id)
        self._ensure_team_row(away_team_id)

        # Upsert the game row.
        try:
            self._upsert_game(
                summary.event_id,
                game_date,
                home_team_id,
                away_team_id,
                home_score,
                away_score,
            )
        except sqlite3.Error as exc:
            logger.error(
                "Failed to upsert game %s: %s", summary.event_id, exc
            )
            return LoadResult(errors=1)

        result = LoadResult()

        # Load per-player stats for own team.
        if own_data:
            r = self._load_team_stats(own_data, own_team_id, summary.event_id)
            result.loaded += r.loaded
            result.skipped += r.skipped
            result.errors += r.errors

        # Load per-player stats for opponent team.
        if opp_data:
            r = self._load_team_stats(opp_data, opp_team_id, summary.event_id)
            result.loaded += r.loaded
            result.skipped += r.skipped
            result.errors += r.errors

        # Count the game itself as a loaded record.
        result.loaded += 1
        return result

    def _detect_team_keys(self, raw: dict) -> tuple[str | None, str | None]:
        """Identify the own-team key and opponent key in a boxscore response.

        Own team key = public_id slug (alphanumeric, no dashes, not 36 chars).
        Opponent key = UUID (lowercase hex with dashes, 36 chars).

        If all keys are UUIDs, fall back to matching the opponent_id.

        Args:
            raw: Top-level boxscore dict (keys are team identifiers).

        Returns:
            Tuple of ``(own_key, opp_key)``.  Either may be ``None`` if not found.
        """
        keys = list(raw.keys())
        uuid_keys = [k for k in keys if _UUID_RE.match(k)]
        slug_keys = [k for k in keys if not _UUID_RE.match(k)]

        own_key: str | None = slug_keys[0] if slug_keys else None
        opp_key: str | None = uuid_keys[0] if uuid_keys else None

        # If all keys are UUIDs (opponent-vs-opponent data), pick own team by
        # matching against self._owned_team_id; the other is the opponent.
        if own_key is None and len(uuid_keys) >= 2:
            for k in uuid_keys:
                if k.lower() == self._owned_team_id.lower():
                    own_key = k
                else:
                    opp_key = k

        logger.debug(
            "Boxscore key detection: own_key=%s opp_key=%s (all_keys=%s)",
            own_key,
            opp_key,
            keys,
        )
        return own_key, opp_key

    def _load_team_stats(
        self, team_data: dict, team_id: str, game_id: str
    ) -> LoadResult:
        """Parse and load batting + pitching lines for one team in a boxscore.

        Args:
            team_data: Value under one team key in the boxscore (contains
                ``players`` and ``groups``).
            team_id: GameChanger team UUID for this side of the game.
            game_id: Canonical event_id (games.game_id FK).

        Returns:
            ``LoadResult`` for this team's players.
        """
        result = LoadResult()
        groups: list[dict] = team_data.get("groups") or []

        for group in groups:
            category = group.get("category")
            if category == "lineup":
                r = self._load_batting_group(group, team_id, game_id)
            elif category == "pitching":
                r = self._load_pitching_group(group, team_id, game_id)
            else:
                logger.debug("Unknown boxscore category %r for team %s; ignoring.", category, team_id)
                continue
            result.loaded += r.loaded
            result.skipped += r.skipped
            result.errors += r.errors

        return result

    # ------------------------------------------------------------------
    # Batting
    # ------------------------------------------------------------------

    def _load_batting_group(
        self, group: dict, team_id: str, game_id: str
    ) -> LoadResult:
        """Parse and upsert batting lines from a lineup group.

        Args:
            group: The ``category="lineup"`` group dict from the boxscore.
            team_id: Team UUID for this batting side.
            game_id: Canonical event_id.

        Returns:
            ``LoadResult`` for this batting group.
        """
        result = LoadResult()

        # Build extras lookup: {player_id: {stat_name: value}}
        extras = self._build_extras_index(group.get("extra") or [])

        for stat_row in group.get("stats") or []:
            player_id = stat_row.get("player_id")
            if not player_id:
                logger.error(
                    "Batting row missing player_id in game %s team %s; skipping. row=%r",
                    game_id,
                    team_id,
                    stat_row,
                )
                result.skipped += 1
                continue

            raw_stats: dict = stat_row.get("stats") or {}
            player_extras = extras.get(player_id, {})

            batting = _PlayerBatting(player_id=player_id)
            for api_key, db_col in _BATTING_MAIN.items():
                if api_key in raw_stats:
                    setattr(batting, db_col, int(raw_stats[api_key]))
            for api_key in _BATTING_SKIP_DEBUG:
                if api_key in raw_stats:
                    logger.debug(
                        "Batting field %r not in schema; ignoring (player=%s game=%s)",
                        api_key,
                        player_id,
                        game_id,
                    )
            for api_key, db_col in _BATTING_EXTRAS.items():
                val = player_extras.get(api_key, 0)
                setattr(batting, db_col, int(val))
            for api_key in _BATTING_EXTRAS_SKIP_DEBUG:
                if api_key in player_extras:
                    logger.debug(
                        "Batting extra %r not in schema; ignoring (player=%s game=%s)",
                        api_key,
                        player_id,
                        game_id,
                    )

            try:
                self._ensure_stub_player(player_id)
                self._upsert_batting(batting, team_id, game_id)
                result.loaded += 1
            except sqlite3.Error as exc:
                logger.error(
                    "DB error upserting batting for player=%s game=%s: %s",
                    player_id,
                    game_id,
                    exc,
                )
                result.errors += 1

        return result

    # ------------------------------------------------------------------
    # Pitching
    # ------------------------------------------------------------------

    def _load_pitching_group(
        self, group: dict, team_id: str, game_id: str
    ) -> LoadResult:
        """Parse and upsert pitching lines from a pitching group.

        Args:
            group: The ``category="pitching"`` group dict from the boxscore.
            team_id: Team UUID for this pitching side.
            game_id: Canonical event_id.

        Returns:
            ``LoadResult`` for this pitching group.
        """
        result = LoadResult()

        extras = self._build_extras_index(group.get("extra") or [])

        for stat_row in group.get("stats") or []:
            player_id = stat_row.get("player_id")
            if not player_id:
                logger.error(
                    "Pitching row missing player_id in game %s team %s; skipping. row=%r",
                    game_id,
                    team_id,
                    stat_row,
                )
                result.skipped += 1
                continue

            raw_stats: dict = stat_row.get("stats") or {}
            player_extras = extras.get(player_id, {})

            pitching = _PlayerPitching(player_id=player_id)
            for api_key, db_col in _PITCHING_MAIN.items():
                if api_key in raw_stats:
                    setattr(pitching, db_col, int(raw_stats[api_key]))
            for api_key in _PITCHING_SKIP_DEBUG:
                if api_key in raw_stats:
                    logger.debug(
                        "Pitching field %r not in schema; ignoring (player=%s game=%s)",
                        api_key,
                        player_id,
                        game_id,
                    )
            # IP -> ip_outs conversion (1 IP = 3 outs)
            if "IP" in raw_stats:
                pitching.ip_outs = round(float(raw_stats["IP"]) * 3)
            for api_key in _PITCHING_EXTRAS_SKIP_DEBUG:
                if api_key in player_extras:
                    logger.debug(
                        "Pitching extra %r not in schema; ignoring (player=%s game=%s)",
                        api_key,
                        player_id,
                        game_id,
                    )

            try:
                self._ensure_stub_player(player_id)
                self._upsert_pitching(pitching, team_id, game_id)
                result.loaded += 1
            except sqlite3.Error as exc:
                logger.error(
                    "DB error upserting pitching for player=%s game=%s: %s",
                    player_id,
                    game_id,
                    exc,
                )
                result.errors += 1

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_extras_index(
        self, extra_list: list[dict]
    ) -> dict[str, dict[str, int]]:
        """Build a player-keyed extras lookup from the ``extra[]`` array.

        The ``extra[]`` array is sparse: only non-zero values are included.

        Args:
            extra_list: The ``extra`` array from a lineup or pitching group.

        Returns:
            Dict ``{player_id: {stat_name: value}}``.
        """
        index: dict[str, dict[str, int]] = {}
        for extra_entry in extra_list:
            stat_name = extra_entry.get("stat_name", "")
            for stat in extra_entry.get("stats") or []:
                pid = stat.get("player_id")
                value = stat.get("value", 0)
                if pid:
                    index.setdefault(pid, {})[stat_name] = int(value)
        return index

    def _read_json(self, path: Path) -> dict | list | None:
        """Read and parse a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed JSON value, or ``None`` on error.
        """
        try:
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            logger.error("File not found: %s", path)
            return None
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error in %s: %s", path, exc)
            return None

    # ------------------------------------------------------------------
    # DB write helpers
    # ------------------------------------------------------------------

    def _upsert_game(
        self,
        game_id: str,
        game_date: str,
        home_team_id: str,
        away_team_id: str,
        home_score: int,
        away_score: int,
    ) -> None:
        """Upsert a game record into the ``games`` table.

        Args:
            game_id: Canonical event_id (PK).
            game_date: ISO 8601 date string.
            home_team_id: Home team UUID.
            away_team_id: Away team UUID.
            home_score: Final home score.
            away_score: Final away score.
        """
        self._db.execute(
            """
            INSERT INTO games
                (game_id, season_id, game_date, home_team_id, away_team_id,
                 home_score, away_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
            ON CONFLICT(game_id) DO UPDATE SET
                game_date    = excluded.game_date,
                home_team_id = excluded.home_team_id,
                away_team_id = excluded.away_team_id,
                home_score   = excluded.home_score,
                away_score   = excluded.away_score,
                status       = excluded.status
            """,
            (game_id, self._season_id, game_date, home_team_id, away_team_id,
             home_score, away_score),
        )
        logger.debug(
            "Upserted game %s: %s vs %s (%d-%d) on %s",
            game_id,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            game_date,
        )

    def _upsert_batting(
        self, batting: _PlayerBatting, team_id: str, game_id: str
    ) -> None:
        """Upsert a batting line into ``player_game_batting``.

        Args:
            batting: Parsed batting record.
            team_id: Team UUID.
            game_id: Canonical event_id.
        """
        self._db.execute(
            """
            INSERT INTO player_game_batting
                (game_id, player_id, team_id, ab, h, doubles, triples,
                 hr, rbi, bb, so, sb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id, player_id) DO UPDATE SET
                team_id = excluded.team_id,
                ab      = excluded.ab,
                h       = excluded.h,
                doubles = excluded.doubles,
                triples = excluded.triples,
                hr      = excluded.hr,
                rbi     = excluded.rbi,
                bb      = excluded.bb,
                so      = excluded.so,
                sb      = excluded.sb
            """,
            (
                game_id,
                batting.player_id,
                team_id,
                batting.ab,
                batting.h,
                batting.doubles,
                batting.triples,
                batting.hr,
                batting.rbi,
                batting.bb,
                batting.so,
                batting.sb,
            ),
        )

    def _upsert_pitching(
        self, pitching: _PlayerPitching, team_id: str, game_id: str
    ) -> None:
        """Upsert a pitching line into ``player_game_pitching``.

        Args:
            pitching: Parsed pitching record.
            team_id: Team UUID.
            game_id: Canonical event_id.
        """
        self._db.execute(
            """
            INSERT INTO player_game_pitching
                (game_id, player_id, team_id, ip_outs, h, er, bb, so, hr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id, player_id) DO UPDATE SET
                team_id = excluded.team_id,
                ip_outs = excluded.ip_outs,
                h       = excluded.h,
                er      = excluded.er,
                bb      = excluded.bb,
                so      = excluded.so,
                hr      = excluded.hr
            """,
            (
                game_id,
                pitching.player_id,
                team_id,
                pitching.ip_outs,
                pitching.h,
                pitching.er,
                pitching.bb,
                pitching.so,
                pitching.hr,
            ),
        )

    def _ensure_stub_player(self, player_id: str) -> None:
        """Ensure a player row exists; insert stub if not present.

        Logs WARNING when a stub is created (FK-safe orphan handling).

        Args:
            player_id: GameChanger player UUID.
        """
        existing = self._db.execute(
            "SELECT 1 FROM players WHERE player_id = ?;", (player_id,)
        ).fetchone()
        if existing is None:
            logger.warning(
                "Unknown player_id=%s; inserting stub row (first_name='Unknown', last_name='Unknown').",
                player_id,
            )
            self._db.execute(
                """
                INSERT INTO players (player_id, first_name, last_name)
                VALUES (?, 'Unknown', 'Unknown')
                ON CONFLICT(player_id) DO NOTHING
                """,
                (player_id,),
            )

    def _ensure_team_row(self, team_id: str) -> None:
        """Ensure a ``teams`` row exists for ``team_id``.

        Args:
            team_id: GameChanger team UUID.
        """
        self._db.execute(
            """
            INSERT INTO teams (team_id, name, is_owned, is_active)
            VALUES (?, ?, 0, 0)
            ON CONFLICT(team_id) DO NOTHING
            """,
            (team_id, team_id),
        )

    def _ensure_season_row(self, season_id: str) -> None:
        """Ensure a ``seasons`` row exists for ``season_id``.

        Args:
            season_id: Season slug.
        """
        parts = season_id.split("-")
        year = 0
        for part in parts:
            if part.isdigit() and len(part) == 4:
                year = int(part)
                break

        self._db.execute(
            """
            INSERT INTO seasons (season_id, name, season_type, year)
            VALUES (?, ?, 'unknown', ?)
            ON CONFLICT(season_id) DO NOTHING
            """,
            (season_id, season_id, year),
        )
