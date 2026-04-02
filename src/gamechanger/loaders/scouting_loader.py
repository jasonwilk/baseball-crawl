"""Scouting loader for the baseball-crawl ingestion pipeline.

Reads raw scouting files written by ``ScoutingCrawler`` and loads them into
the SQLite database.  Delegates per-game boxscore loading to the existing
``GameLoader.load_file()`` (which handles all boxscore parsing, player stubs,
game records, and batting/pitching stat upserts).

Additional responsibilities beyond ``GameLoader``:
- Roster loading into ``players`` and ``team_rosters``.
- ``scouting_runs`` metadata tracking (status transitions, timestamps).
- Season aggregate computation: sums per-game stats from
  ``player_game_batting`` and ``player_game_pitching``, then upserts into
  ``player_season_batting`` and ``player_season_pitching``.
- UUID opportunism: ensures a ``teams`` row exists for any UUID discovered
  as a boxscore key.

Expected raw file layout (written by ``ScoutingCrawler``)::

    data/raw/{season_id}/scouting/{public_id}/games.json
    data/raw/{season_id}/scouting/{public_id}/roster.json
    data/raw/{season_id}/scouting/{public_id}/boxscores/{game_stream_id}.json

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = ScoutingLoader(conn)
    result = loader.load_team(
        Path("data/raw/2025-spring-hs/scouting/8O8bTolVfb9A"),
        team_id=42,
        season_id="2025-spring-hs",
    )
    print(result)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from src.db.teams import ensure_team_row
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team, ensure_season_row
from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry
from src.gamechanger.types import TeamRef

logger = logging.getLogger(__name__)

# UUID pattern: 8-4-4-4-12 hex digits with dashes.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# run_type used by the scouting crawler for scouting_runs.
_RUN_TYPE = "full"


class ScoutingLoader:
    """Loads raw scouting files into the SQLite database.

    Delegates boxscore loading to ``GameLoader.load_file()`` and adds
    roster loading, season aggregate computation, and scouting_runs tracking.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_team(
        self,
        scouting_dir: Path,
        team_id: int,
        season_id: str,
    ) -> LoadResult:
        """Load all scouting data for one opponent from a raw directory.

        Reads ``games.json``, ``roster.json``, and all ``boxscores/*.json``
        files.  Delegates boxscore loading to ``GameLoader.load_file()`` and
        computes season aggregates from the loaded per-game rows.

        Args:
            scouting_dir: Path to ``data/raw/{season_id}/scouting/{public_id}/``.
            team_id: The opponent's INTEGER PK in the ``teams`` table.
            season_id: Season slug used for **file path construction only**
                (locating the scouting directory on disk).  The DB season_id
                for loaded data is derived from team metadata via
                ``derive_season_id_for_team()``.

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
        # Derive the canonical DB season_id from team metadata (not the crawl path).
        db_season_id, db_season_year = derive_season_id_for_team(self._db, team_id)
        ensure_season_row(self._db, db_season_id)

        total = self._load_roster_section(scouting_dir, team_id, db_season_id)

        boxscores_dir = scouting_dir / "boxscores"
        if not boxscores_dir.is_dir():
            logger.info("No boxscores directory at %s; nothing to load.", boxscores_dir)
            return total

        # Build TeamRef for GameLoader by looking up gc_uuid and public_id.
        team_ref = self._build_team_ref(team_id)
        game_loader = GameLoader(db=self._db, owned_team_ref=team_ref)
        games_path = scouting_dir / "games.json"
        games_index = self._build_games_index(games_path)
        opponent_name_index = self._build_opponent_name_index(games_path)
        bs_result = self._load_boxscores(
            game_loader, games_index, boxscores_dir,
            season_year=db_season_year,
            opponent_name_index=opponent_name_index,
            own_gc_uuid=team_ref.gc_uuid,
        )
        total.loaded += bs_result.loaded
        total.skipped += bs_result.skipped
        total.errors += bs_result.errors

        self._compute_season_aggregates(team_id, db_season_id)
        self._db.commit()
        logger.info(
            "Scouting load complete for team_id=%d season=%s: loaded=%d skipped=%d errors=%d",
            team_id, db_season_id, total.loaded, total.skipped, total.errors,
        )
        return total

    def _build_team_ref(self, team_id: int) -> TeamRef:
        """Build a ``TeamRef`` by looking up the teams row for ``team_id``.

        Args:
            team_id: INTEGER PK in the ``teams`` table.

        Returns:
            ``TeamRef`` populated with gc_uuid and public_id from the DB row.
        """
        row = self._db.execute(
            "SELECT gc_uuid, public_id FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if row:
            return TeamRef(id=team_id, gc_uuid=row[0], public_id=row[1])
        logger.warning("No teams row found for team_id=%d; TeamRef will have null identifiers.", team_id)
        return TeamRef(id=team_id)

    def _load_roster_section(
        self, scouting_dir: Path, team_id: int, season_id: str
    ) -> LoadResult:
        """Load the roster.json file if present; return a LoadResult.

        Args:
            scouting_dir: Base scouting directory.
            team_id: INTEGER PK of the opponent team.
            season_id: Season slug.

        Returns:
            ``LoadResult`` from roster loading, or an empty result if the file
            is absent.
        """
        roster_path = scouting_dir / "roster.json"
        if roster_path.exists():
            return self._load_roster(roster_path, team_id, season_id)
        logger.warning("roster.json not found at %s; skipping.", roster_path)
        return LoadResult()

    def _load_boxscores(
        self,
        game_loader: GameLoader,
        games_index: dict,
        boxscores_dir: Path,
        season_year: int | None = None,
        opponent_name_index: dict[str, str] | None = None,
        own_gc_uuid: str | None = None,
    ) -> LoadResult:
        """Load all boxscore files in ``boxscores_dir`` via ``game_loader``.

        Args:
            game_loader: Configured ``GameLoader`` for the scouted team.
            games_index: Mapping of ``game_stream_id`` → ``GameSummaryEntry``.
            boxscores_dir: Directory containing ``{game_stream_id}.json`` files.
            season_year: Calendar year from team metadata, passed to
                ``ensure_team_row()`` for UUID opportunism.
            opponent_name_index: Optional mapping of ``game_stream_id`` →
                opponent team name.  When provided, real names are used for
                opponent team rows instead of UUID placeholders.
            own_gc_uuid: The scouted team's own GameChanger UUID, used by the
                safety-net to avoid labeling the own-team UUID as the opponent.

        Returns:
            Aggregated ``LoadResult`` across all boxscore files.
        """
        name_index = opponent_name_index or {}
        total = LoadResult()
        for bs_path in sorted(boxscores_dir.glob("*.json")):
            game_stream_id = bs_path.stem
            summary = games_index.get(game_stream_id)
            if summary is None:
                logger.warning(
                    "No games.json entry for game_stream_id=%s; skipping %s",
                    game_stream_id, bs_path,
                )
                total.skipped += 1
                continue
            opponent_name = name_index.get(game_stream_id)
            result = game_loader.load_file(bs_path, summary, opponent_name=opponent_name)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors
            self._record_uuid_from_boxscore(
                bs_path, season_year=season_year,
                opponent_name=opponent_name, own_gc_uuid=own_gc_uuid,
            )
        return total

    # ------------------------------------------------------------------
    # Games index builder
    # ------------------------------------------------------------------

    def _build_opponent_name_index(self, games_path: Path) -> dict[str, str]:
        """Build a ``game_stream_id → opponent_team.name`` mapping from games.json.

        Used to supply real opponent team names to ``GameLoader`` so team rows
        are created with human-readable names instead of UUID placeholders.

        Args:
            games_path: Path to ``games.json`` (public games response).

        Returns:
            Dict mapping ``game_stream_id`` (= the ``id`` field in games.json)
            to the opponent team display name.  Returns empty dict on error.
        """
        if not games_path.exists():
            return {}
        try:
            with games_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s for opponent name index: %s", games_path, exc)
            return {}
        if not isinstance(raw, list):
            return {}

        index: dict[str, str] = {}
        for game in raw:
            game_id = game.get("id")
            opponent_team = game.get("opponent_team") or {}
            name = opponent_team.get("name")
            if game_id and name:
                index[str(game_id)] = name
        return index

    def _build_games_index(self, games_path: Path) -> dict[str, GameSummaryEntry]:
        """Build a ``game_stream_id -> GameSummaryEntry`` mapping from games.json."""
        if not games_path.exists():
            logger.warning("games.json not found at %s; no game index built.", games_path)
            return {}
        try:
            with games_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", games_path, exc)
            return {}
        if not isinstance(raw, list):
            logger.error("Expected JSON array in %s, got %s", games_path, type(raw).__name__)
            return {}

        index: dict[str, GameSummaryEntry] = {}
        for game in raw:
            if game.get("game_status") != "completed":
                continue
            game_id = game.get("id")
            if not game_id:
                continue
            score = game.get("score") or {}
            start_ts = game.get("start_ts") or game.get("end_ts") or "1900-01-01T00:00:00Z"
            entry = GameSummaryEntry(
                event_id=str(game_id),
                game_stream_id=str(game_id),
                home_away=game.get("home_away"),
                owning_team_score=int(score.get("team") or 0),
                opponent_team_score=int(score.get("opponent_team") or 0),
                opponent_id="",
                last_scoring_update=str(start_ts),
            )
            index[entry.game_stream_id] = entry

        logger.info("Built games index: %d entries from %s", len(index), games_path)
        return index

    # ------------------------------------------------------------------
    # Roster loading
    # ------------------------------------------------------------------

    def _load_roster(
        self, roster_path: Path, team_id: int, season_id: str
    ) -> LoadResult:
        """Load players from a roster.json file into players and team_rosters."""
        try:
            with roster_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", roster_path, exc)
            return LoadResult(errors=1)
        if not isinstance(raw, list):
            logger.error("Expected JSON array in %s, got %s", roster_path, type(raw).__name__)
            return LoadResult(errors=1)

        result = LoadResult()
        for player in raw:
            player_id = player.get("id")
            if not player_id:
                logger.warning("Roster entry missing 'id'; skipping. entry=%r", player)
                result.skipped += 1
                continue
            ok = self._upsert_roster_player(
                player_id=player_id,
                first_name=str(player.get("first_name") or ""),
                last_name=str(player.get("last_name") or ""),
                team_id=team_id,
                season_id=season_id,
                jersey_number=player.get("number") or None,
            )
            if ok:
                result.loaded += 1
            else:
                result.errors += 1

        self._db.commit()
        logger.info("Roster loaded for team_id=%d: %d players, %d errors.", team_id, result.loaded, result.errors)
        return result

    def _upsert_roster_player(
        self,
        player_id: str,
        first_name: str,
        last_name: str,
        team_id: int,
        season_id: str,
        jersey_number: str | None,
    ) -> bool:
        """Upsert one player into players and team_rosters; return True on success."""
        try:
            self._db.execute(
                """
                INSERT INTO players (player_id, first_name, last_name)
                VALUES (?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    last_name  = excluded.last_name
                """,
                (player_id, first_name, last_name),
            )
            self._db.execute(
                """
                INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id, player_id, season_id) DO UPDATE SET
                    jersey_number = excluded.jersey_number
                """,
                (team_id, player_id, season_id, jersey_number),
            )
            return True
        except sqlite3.Error as exc:
            logger.error("DB error loading roster player %s for team %d: %s", player_id, team_id, exc)
            return False

    # ------------------------------------------------------------------
    # Season aggregate computation
    # ------------------------------------------------------------------

    def _compute_season_aggregates(self, team_id: int, season_id: str) -> None:
        """Compute and upsert season aggregate stats from per-game rows.

        Delegates to batting and pitching sub-methods.  Rate stats (AVG, OBP,
        ERA, WHIP) are NOT stored -- they are computed at display time.

        Args:
            team_id: INTEGER PK of the scouted team.
            season_id: Season slug.
        """
        n_batting = self._compute_batting_aggregates(team_id, season_id)
        n_pitching = self._compute_pitching_aggregates(team_id, season_id)
        logger.info(
            "Season aggregates computed: %d batting, %d pitching rows for team=%d season=%s.",
            n_batting, n_pitching, team_id, season_id,
        )

    def _compute_batting_aggregates(self, team_id: int, season_id: str) -> int:
        """Sum game batting rows into player_season_batting; return player count."""
        rows = self._db.execute(
            """
            SELECT
                pgb.player_id,
                COUNT(*)         AS games_tracked,
                SUM(pgb.ab)      AS ab,
                SUM(pgb.h)       AS h,
                SUM(pgb.doubles) AS doubles,
                SUM(pgb.triples) AS triples,
                SUM(pgb.hr)      AS hr,
                SUM(pgb.rbi)     AS rbi,
                SUM(pgb.r)       AS r,
                SUM(pgb.bb)      AS bb,
                SUM(pgb.so)      AS so,
                SUM(pgb.sb)      AS sb,
                SUM(pgb.tb)      AS tb,
                SUM(pgb.hbp)     AS hbp,
                SUM(pgb.shf)     AS shf,
                SUM(pgb.cs)      AS cs
            FROM player_game_batting pgb
            JOIN games g ON pgb.game_id = g.game_id
            WHERE pgb.team_id = ? AND g.season_id = ?
            GROUP BY pgb.player_id
            """,
            (team_id, season_id),
        ).fetchall()
        for (player_id, games_tracked,
             ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
             tb, hbp, shf, cs) in rows:
            self._db.execute(
                """
                INSERT INTO player_season_batting
                    (player_id, team_id, season_id,
                     gp, games_tracked, ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
                     tb, hbp, shf, cs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                    gp            = excluded.gp,
                    games_tracked = excluded.games_tracked,
                    ab            = excluded.ab,
                    h             = excluded.h,
                    doubles       = excluded.doubles,
                    triples       = excluded.triples,
                    hr            = excluded.hr,
                    rbi           = excluded.rbi,
                    r             = excluded.r,
                    bb            = excluded.bb,
                    so            = excluded.so,
                    sb            = excluded.sb,
                    tb            = excluded.tb,
                    hbp           = excluded.hbp,
                    shf           = excluded.shf,
                    cs            = excluded.cs
                """,
                (player_id, team_id, season_id, games_tracked, games_tracked,
                 ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
                 tb, hbp, shf, cs),
            )
        return len(rows)

    def _compute_pitching_aggregates(self, team_id: int, season_id: str) -> int:
        """Sum game pitching rows into player_season_pitching; return player count.

        Note: ``hr`` is excluded -- ``player_game_pitching`` does not store HR
        allowed (not present in the boxscore pitching extras per the schema).
        """
        rows = self._db.execute(
            """
            SELECT
                pgp.player_id,
                COUNT(*)              AS games_tracked,
                SUM(pgp.ip_outs)      AS ip_outs,
                SUM(pgp.h)            AS h,
                SUM(pgp.r)            AS r,
                SUM(pgp.er)           AS er,
                SUM(pgp.bb)           AS bb,
                SUM(pgp.so)           AS so,
                SUM(pgp.wp)           AS wp,
                SUM(pgp.hbp)          AS hbp,
                SUM(pgp.pitches)      AS pitches,
                SUM(pgp.total_strikes) AS total_strikes,
                SUM(pgp.bf)           AS bf
            FROM player_game_pitching pgp
            JOIN games g ON pgp.game_id = g.game_id
            WHERE pgp.team_id = ? AND g.season_id = ?
            GROUP BY pgp.player_id
            """,
            (team_id, season_id),
        ).fetchall()
        for (player_id, games_tracked,
             ip_outs, h, r, er, bb, so,
             wp, hbp, pitches, total_strikes, bf) in rows:
            self._db.execute(
                """
                INSERT INTO player_season_pitching
                    (player_id, team_id, season_id,
                     gp_pitcher, games_tracked, ip_outs, h, r, er, bb, so,
                     wp, hbp, pitches, total_strikes, bf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                    gp_pitcher    = excluded.gp_pitcher,
                    games_tracked = excluded.games_tracked,
                    ip_outs       = excluded.ip_outs,
                    h             = excluded.h,
                    r             = excluded.r,
                    er            = excluded.er,
                    bb            = excluded.bb,
                    so            = excluded.so,
                    wp            = excluded.wp,
                    hbp           = excluded.hbp,
                    pitches       = excluded.pitches,
                    total_strikes = excluded.total_strikes,
                    bf            = excluded.bf
                """,
                (player_id, team_id, season_id, games_tracked, games_tracked,
                 ip_outs, h, r, er, bb, so,
                 wp, hbp, pitches, total_strikes, bf),
            )
        return len(rows)

    # ------------------------------------------------------------------
    # UUID opportunism
    # ------------------------------------------------------------------

    def _record_uuid_from_boxscore(
        self, bs_path: Path, *, season_year: int | None = None,
        opponent_name: str | None = None, own_gc_uuid: str | None = None,
    ) -> None:
        """Ensure a ``teams`` stub row exists for any UUID key found in a boxscore.

        The GameLoader already creates stubs during load_file(), so this is a
        safety net for UUID keys not covered by normal team detection.

        When ``opponent_name`` is provided, the row is created with the real name
        instead of the UUID placeholder.  Existing rows with ``name == gc_uuid``
        (UUID-stubs) are updated to the real name.

        The ``own_gc_uuid`` parameter prevents mislabeling the scouted team's own
        UUID as the opponent.  When a boxscore has two UUID keys and we cannot
        identify which is the own team (``own_gc_uuid`` is ``None``), neither UUID
        gets ``opponent_name`` — both fall back to UUID-as-name to avoid false labels.

        Args:
            bs_path: Path to a boxscore JSON file.
            opponent_name: Human-readable opponent team name.
            own_gc_uuid: The scouted team's own GC UUID.  When provided, the
                matching key is not labeled as the opponent.
        """
        try:
            with bs_path.open(encoding="utf-8") as fh:
                boxscore = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Could not read boxscore for UUID opportunism: %s", exc)
            return

        if not isinstance(boxscore, dict):
            return

        uuid_keys = [k for k in boxscore if _UUID_RE.match(k)]
        multi_uuid = len(uuid_keys) >= 2

        for key in uuid_keys:
            is_own_team = bool(own_gc_uuid and key.lower() == own_gc_uuid.lower())
            ambiguous = own_gc_uuid is None and multi_uuid
            name = key if (is_own_team or ambiguous) else (opponent_name or key)

            ensure_team_row(
                self._db,
                gc_uuid=key,
                name=name,
                season_year=season_year,
                source="scouting_loader",
            )
            logger.debug("UUID opportunism (loader): ensured stub row for gc_uuid=%s", key)

    # ------------------------------------------------------------------
    # FK prerequisite helpers
    # ------------------------------------------------------------------

