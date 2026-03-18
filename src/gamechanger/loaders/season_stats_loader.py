"""Season stats loader for the baseball-crawl ingestion pipeline.

Reads ``stats.json`` files (written by the season-stats crawler) and upserts
per-player season batting and pitching records into the SQLite database.

Expected file path convention::

    data/raw/{season_id}/teams/{team_id}/stats.json

The ``team_id`` and ``season_id`` are inferred from the path.

Response shape (from ``GET /teams/{team_id}/season-stats``)::

    {
        "id": "<team_uuid>",
        "team_id": "<team_uuid>",
        "stats_data": {
            "players": {
                "<player_uuid>": {
                    "stats": {
                        "offense": { ... },   # batting stats; absent for pitcher-only
                        "defense": { ... },   # pitching + fielding; absent for DH-only
                        "general": { ... }    # GP, shared
                    }
                }
            },
            ...
        }
    }

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.season_stats_loader import SeasonStatsLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = SeasonStatsLoader(conn)
    result = loader.load_file(Path("data/raw/2025/teams/abc-123/stats.json"))
    print(result)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.gamechanger.loaders import LoadResult

logger = logging.getLogger(__name__)


def _ip_to_ip_outs(ip: float | int | None) -> int | None:
    """Convert API ``IP`` (decimal innings) to ``ip_outs`` (integer outs).

    The API represents innings pitched as a decimal where the fractional part
    is a true decimal fraction of an inning (e.g. 8.333... = 8⅓ innings = 25
    outs).  The schema stores ``ip_outs`` as integer total outs.

    Args:
        ip: Raw ``IP`` value from the API (float or int), or ``None``.

    Returns:
        Total outs as an integer, or ``None`` if input is ``None``.
    """
    if ip is None:
        return None
    return round(ip * 3)


class SeasonStatsLoader:
    """Loads a season stats JSON file into the SQLite database.

    Upserts player season batting stats into ``player_season_batting`` and
    pitching stats into ``player_season_pitching``.  Split columns (home/away,
    vs L/R) are always NULL because the season-stats API does not provide them.

    Before inserting stat rows, ensures FK prerequisite rows exist for
    ``teams`` and ``seasons``.  Orphaned player IDs (not in ``players`` table)
    receive a stub row (``first_name='Unknown'``, ``last_name='Unknown'``).

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def load_file(self, path: Path) -> LoadResult:
        """Load a season stats JSON file into the database.

        Infers ``team_id`` and ``season_id`` from the file path using the
        convention ``data/raw/{season_id}/teams/{team_id}/stats.json``.

        Args:
            path: Absolute or relative path to the ``stats.json`` file.

        Returns:
            A ``LoadResult`` summarising records loaded, skipped, and errors.
        """
        team_id, season_id = self._infer_ids_from_path(path)
        logger.info(
            "Loading season stats file: %s (team=%s, season=%s)", path, team_id, season_id
        )

        data = self._read_json(path)
        if data is None:
            return LoadResult(errors=1)

        players_by_uuid: dict[str, Any] = (
            data.get("stats_data", {}).get("players", {})
        )

        if not isinstance(players_by_uuid, dict):
            logger.error(
                "Expected stats_data.players to be a dict in %s, got %s",
                path,
                type(players_by_uuid).__name__,
            )
            return LoadResult(errors=1)

        # Ensure FK prerequisite rows before any stat inserts.
        team_int = self._ensure_team_row(team_id)
        self._ensure_season_row(season_id)

        result = LoadResult()
        for player_id, player_data in players_by_uuid.items():
            if not player_id:
                logger.warning("Encountered empty player_id key in %s; skipping.", path)
                result.skipped += 1
                continue
            try:
                loaded = self._load_player(player_id, player_data, team_int, season_id)
                result.loaded += loaded
                if loaded == 0:
                    result.skipped += 1
            except sqlite3.Error as exc:
                logger.error(
                    "Database error loading season stats for player %s team %s: %s",
                    player_id,
                    team_id,
                    exc,
                )
                result.errors += 1

        self._db.commit()
        logger.info(
            "Season stats load complete: loaded=%d skipped=%d errors=%d",
            result.loaded,
            result.skipped,
            result.errors,
        )
        return result

    # ------------------------------------------------------------------
    # Per-player helpers
    # ------------------------------------------------------------------

    def _load_player(
        self,
        player_id: str,
        player_data: Any,
        team_id: int,
        season_id: str,
    ) -> int:
        """Upsert batting and/or pitching season stats for a single player.

        Args:
            player_id: GameChanger player UUID.
            player_data: Dict with ``stats.offense`` and/or ``stats.defense``.
            team_id: INTEGER PK from the ``teams`` table.
            season_id: Season slug.

        Returns:
            Number of stat rows upserted (0, 1, or 2 -- one per table).
        """
        if not isinstance(player_data, dict):
            logger.warning(
                "Player data for %s is not a dict; skipping.", player_id
            )
            return 0

        stats = player_data.get("stats", {}) or {}
        offense = stats.get("offense")
        defense = stats.get("defense")

        has_offense = isinstance(offense, dict) and bool(offense)
        has_defense = isinstance(defense, dict) and bool(defense)

        if not has_offense and not has_defense:
            logger.debug(
                "No offense or defense stats for player %s; skipping.", player_id
            )
            return 0

        # AC-4: ensure player stub exists before inserting FK-referencing rows.
        self._ensure_player_row(player_id)

        rows_upserted = 0

        if has_offense:
            self._upsert_batting(player_id, team_id, season_id, offense)  # type: ignore[arg-type]
            rows_upserted += 1

        if has_defense and self._is_pitcher(defense):  # type: ignore[arg-type]
            self._upsert_pitching(player_id, team_id, season_id, defense)  # type: ignore[arg-type]
            rows_upserted += 1

        return rows_upserted

    def _is_pitcher(self, defense: dict[str, Any]) -> bool:
        """Return True if the defense stats object includes pitching data.

        Uses ``GP:P`` (games played as pitcher) as the discriminator.  If it
        is present and > 0, the player pitched.  Fielding-only players have
        ``GP:P`` absent or 0.

        Args:
            defense: Defense stats dict from the API.

        Returns:
            ``True`` if the player has pitching stats to load.
        """
        gp_p = defense.get("GP:P", 0)
        try:
            return int(gp_p) > 0
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------
    # Batting upsert
    # ------------------------------------------------------------------

    def _upsert_batting(
        self,
        player_id: str,
        team_id: int,
        season_id: str,
        offense: dict[str, Any],
    ) -> None:
        """Upsert a player_season_batting row.

        Populates all 47 batting stat columns from the season-stats API
        offense section.  Sets ``stat_completeness = 'full'`` because
        the season-stats endpoint provides authoritative aggregate data.
        All split columns are NULL -- the season-stats API does not provide
        home/away or left/right pitcher splits.

        Args:
            player_id: GameChanger player UUID.
            team_id: INTEGER PK from the ``teams`` table.
            season_id: Season slug.
            offense: Offense stats dict from the API.
        """
        self._db.execute(
            """
            INSERT INTO player_season_batting (
                player_id, team_id, season_id, stat_completeness,
                gp, pa, ab, h, singles, doubles, triples, hr, rbi, r,
                bb, so, sol, hbp, shb, shf, gidp, roe, fc, ci, pik, sb, cs,
                tb, xbh, lob, three_out_lob, ob, gshr, two_out_rbi, hrisp, abrisp,
                qab, hard, weak, lnd, flb, gb, ps, sw, sm, inp, full,
                two_strikes, two_s_plus_3, six_plus, lobb
            ) VALUES (
                ?, ?, ?, 'full',
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                stat_completeness = 'full',
                gp           = excluded.gp,
                pa           = excluded.pa,
                ab           = excluded.ab,
                h            = excluded.h,
                singles      = excluded.singles,
                doubles      = excluded.doubles,
                triples      = excluded.triples,
                hr           = excluded.hr,
                rbi          = excluded.rbi,
                r            = excluded.r,
                bb           = excluded.bb,
                so           = excluded.so,
                sol          = excluded.sol,
                hbp          = excluded.hbp,
                shb          = excluded.shb,
                shf          = excluded.shf,
                gidp         = excluded.gidp,
                roe          = excluded.roe,
                fc           = excluded.fc,
                ci           = excluded.ci,
                pik          = excluded.pik,
                sb           = excluded.sb,
                cs           = excluded.cs,
                tb           = excluded.tb,
                xbh          = excluded.xbh,
                lob          = excluded.lob,
                three_out_lob = excluded.three_out_lob,
                ob           = excluded.ob,
                gshr         = excluded.gshr,
                two_out_rbi  = excluded.two_out_rbi,
                hrisp        = excluded.hrisp,
                abrisp       = excluded.abrisp,
                qab          = excluded.qab,
                hard         = excluded.hard,
                weak         = excluded.weak,
                lnd          = excluded.lnd,
                flb          = excluded.flb,
                gb           = excluded.gb,
                ps           = excluded.ps,
                sw           = excluded.sw,
                sm           = excluded.sm,
                inp          = excluded.inp,
                full         = excluded.full,
                two_strikes  = excluded.two_strikes,
                two_s_plus_3 = excluded.two_s_plus_3,
                six_plus     = excluded.six_plus,
                lobb         = excluded.lobb
            """,
            (
                player_id,
                team_id,
                season_id,
                # Standard batting (10 existing + 22 new)
                offense.get("GP"),
                offense.get("PA"),
                offense.get("AB"),
                offense.get("H"),
                offense.get("1B"),
                offense.get("2B"),
                offense.get("3B"),
                offense.get("HR"),
                offense.get("RBI"),
                offense.get("R"),
                offense.get("BB"),
                offense.get("SO"),
                offense.get("SOL"),
                offense.get("HBP"),
                offense.get("SHB"),
                offense.get("SHF"),
                offense.get("GIDP"),
                offense.get("ROE"),
                offense.get("FC"),
                offense.get("CI"),
                offense.get("PIK"),
                offense.get("SB"),
                offense.get("CS"),
                offense.get("TB"),
                offense.get("XBH"),
                offense.get("LOB"),
                offense.get("3OUTLOB"),
                offense.get("OB"),
                offense.get("GSHR"),
                offense.get("2OUTRBI"),
                offense.get("HRISP"),
                offense.get("ABRISP"),
                # Advanced batting (15 new)
                offense.get("QAB"),
                offense.get("HARD"),
                offense.get("WEAK"),
                offense.get("LND"),
                offense.get("FLB"),
                offense.get("GB"),
                offense.get("PS"),
                offense.get("SW"),
                offense.get("SM"),
                offense.get("INP"),
                offense.get("FULL"),
                offense.get("2STRIKES"),
                offense.get("2S+3"),
                offense.get("6+"),
                offense.get("LOBB"),
            ),
        )
        logger.debug(
            "Upserted batting: player=%s team=%s season=%s",
            player_id, team_id, season_id,
        )

    # ------------------------------------------------------------------
    # Pitching upsert
    # ------------------------------------------------------------------

    def _upsert_pitching(
        self,
        player_id: str,
        team_id: int,
        season_id: str,
        defense: dict[str, Any],
    ) -> None:
        """Upsert a player_season_pitching row.

        Populates all 47 pitching stat columns from the season-stats API
        defense section.  Sets ``stat_completeness = 'full'`` because
        the season-stats endpoint provides authoritative aggregate data.
        Converts ``IP`` (float) to ``ip_outs`` (integer outs).  All split
        columns are NULL -- the season-stats API does not provide splits.

        Optimistic columns (23) use ``defense.get("KEY")`` -- if the API
        omits a field, ``None`` flows to NULL, which is correct for nullable
        columns.  The ``gp`` column (games played, all roles) will likely be
        NULL because the API places ``GP`` in the ``general`` section, not
        ``defense``.

        Note: ``TB`` in the pitching/defense context means "Total Balls"
        (not "Total Bases"), stored in schema column ``total_balls``.

        Args:
            player_id: GameChanger player UUID.
            team_id: INTEGER PK from the ``teams`` table.
            season_id: Season slug.
            defense: Defense stats dict from the API.
        """
        ip_outs = _ip_to_ip_outs(defense.get("IP"))

        self._db.execute(
            """
            INSERT INTO player_season_pitching (
                player_id, team_id, season_id, stat_completeness,
                gp_pitcher, gs, ip_outs, bf, pitches,
                h, er, bb, so, hr, bk, wp, hbp, svo, sb, cs,
                go, ao, loo, zero_bb_inn, inn_123, fps, lbfpn,
                gp, w, l, sv, bs, r, sol, lob, pik,
                total_strikes, total_balls,
                lt_3, first_2_out, lt_13,
                bbs, lobb, lobbs, sm, sw, weak, hard, lnd, fb, gb
            ) VALUES (
                ?, ?, ?, 'full',
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                stat_completeness = 'full',
                gp_pitcher   = excluded.gp_pitcher,
                gs           = excluded.gs,
                ip_outs      = excluded.ip_outs,
                bf           = excluded.bf,
                pitches      = excluded.pitches,
                h            = excluded.h,
                er           = excluded.er,
                bb           = excluded.bb,
                so           = excluded.so,
                hr           = excluded.hr,
                bk           = excluded.bk,
                wp           = excluded.wp,
                hbp          = excluded.hbp,
                svo          = excluded.svo,
                sb           = excluded.sb,
                cs           = excluded.cs,
                go           = excluded.go,
                ao           = excluded.ao,
                loo          = excluded.loo,
                zero_bb_inn  = excluded.zero_bb_inn,
                inn_123      = excluded.inn_123,
                fps          = excluded.fps,
                lbfpn        = excluded.lbfpn,
                gp           = excluded.gp,
                w            = excluded.w,
                l            = excluded.l,
                sv           = excluded.sv,
                bs           = excluded.bs,
                r            = excluded.r,
                sol          = excluded.sol,
                lob          = excluded.lob,
                pik          = excluded.pik,
                total_strikes = excluded.total_strikes,
                total_balls  = excluded.total_balls,
                lt_3         = excluded.lt_3,
                first_2_out  = excluded.first_2_out,
                lt_13        = excluded.lt_13,
                bbs          = excluded.bbs,
                lobb         = excluded.lobb,
                lobbs        = excluded.lobbs,
                sm           = excluded.sm,
                sw           = excluded.sw,
                weak         = excluded.weak,
                hard         = excluded.hard,
                lnd          = excluded.lnd,
                fb           = excluded.fb,
                gb           = excluded.gb
            """,
            (
                player_id,
                team_id,
                season_id,
                # Confirmed-in-endpoint (standard + existing)
                defense.get("GP:P"),     # gp_pitcher
                defense.get("GS"),       # gs
                ip_outs,                 # ip_outs (converted from IP float)
                defense.get("BF"),       # bf
                defense.get("#P"),       # pitches
                defense.get("H"),        # h
                defense.get("ER"),       # er
                defense.get("BB"),       # bb
                defense.get("SO"),       # so
                defense.get("HR"),       # hr
                defense.get("BK"),       # bk
                defense.get("WP"),       # wp
                defense.get("HBP"),      # hbp
                defense.get("SVO"),      # svo
                defense.get("SB"),       # sb
                defense.get("CS"),       # cs
                defense.get("GO"),       # go
                defense.get("AO"),       # ao
                defense.get("LOO"),      # loo
                defense.get("0BBINN"),   # zero_bb_inn
                defense.get("123INN"),   # inn_123
                defense.get("FPS"),      # fps
                defense.get("LBFPN"),    # lbfpn
                # Optimistic (expected in API but not yet confirmed in endpoint doc)
                defense.get("GP"),       # gp (likely None -- GP lives in general section)
                defense.get("W"),        # w
                defense.get("L"),        # l
                defense.get("SV"),       # sv
                defense.get("BS"),       # bs
                defense.get("R"),        # r
                defense.get("SOL"),      # sol
                defense.get("LOB"),      # lob
                defense.get("PIK"),      # pik
                defense.get("TS"),       # total_strikes
                defense.get("TB"),       # total_balls (TB in pitching = Total Balls, NOT Total Bases)
                defense.get("<3"),       # lt_3
                defense.get("1ST2OUT"),  # first_2_out
                defense.get("<13"),      # lt_13
                defense.get("BBS"),      # bbs
                defense.get("LOBB"),     # lobb
                defense.get("LOBBS"),    # lobbs
                defense.get("SM"),       # sm
                defense.get("SW"),       # sw
                defense.get("WEAK"),     # weak
                defense.get("HARD"),     # hard
                defense.get("LND"),      # lnd
                defense.get("FB"),       # fb
                defense.get("GB"),       # gb
            ),
        )
        logger.debug(
            "Upserted pitching: player=%s team=%s season=%s ip_outs=%s",
            player_id, team_id, season_id, ip_outs,
        )

    # ------------------------------------------------------------------
    # FK prerequisite helpers (mirrors RosterLoader pattern)
    # ------------------------------------------------------------------

    def _ensure_player_row(self, player_id: str) -> None:
        """Ensure a ``players`` row exists for ``player_id``.

        Inserts a stub row (``first_name='Unknown'``, ``last_name='Unknown'``)
        if none exists, logging a WARNING.  Does nothing if already present.

        Args:
            player_id: GameChanger player UUID.
        """
        existing = self._db.execute(
            "SELECT 1 FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()

        if existing is None:
            logger.warning(
                "Player %s not found in players table; inserting stub row.", player_id
            )
            self._db.execute(
                """
                INSERT INTO players (player_id, first_name, last_name)
                VALUES (?, 'Unknown', 'Unknown')
                ON CONFLICT(player_id) DO NOTHING
                """,
                (player_id,),
            )

    def _ensure_team_row(self, gc_uuid: str) -> int:
        """Ensure a ``teams`` row exists for ``gc_uuid`` and return its INTEGER PK.

        Inserts a stub row (membership_type='tracked') if none exists.  If the
        row already exists (IGNORE fires), falls back to SELECT.

        Args:
            gc_uuid: GameChanger team UUID.

        Returns:
            The ``teams.id`` INTEGER PK for the row.
        """
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO teams (name, membership_type, gc_uuid, is_active) "
            "VALUES (?, 'tracked', ?, 0)",
            (gc_uuid, gc_uuid),
        )
        if cursor.rowcount:
            logger.debug("Created teams row for gc_uuid=%s id=%d", gc_uuid, cursor.lastrowid)
            return cursor.lastrowid
        row = self._db.execute(
            "SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)
        ).fetchone()
        if row:
            logger.debug("Found existing teams row for gc_uuid=%s id=%d", gc_uuid, row[0])
            return row[0]
        raise RuntimeError(f"Failed to find or create teams row for gc_uuid={gc_uuid!r}")

    def _ensure_season_row(self, season_id: str) -> None:
        """Ensure a ``seasons`` row exists for ``season_id``.

        Inserts a stub row if none exists.  Does nothing if already present.

        Args:
            season_id: Season slug (e.g. ``'2025'`` or ``'2026-spring-hs'``).
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
        logger.debug("Ensured seasons row for season_id=%s", season_id)

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _infer_ids_from_path(self, path: Path) -> tuple[str, str]:
        """Extract ``team_id`` and ``season_id`` from the stats file path.

        Expects the convention ``.../{season_id}/teams/{team_id}/stats.json``.

        Args:
            path: Path to the stats JSON file.

        Returns:
            Tuple of ``(team_id, season_id)``.
        """
        parts = path.parts
        for i, part in enumerate(parts):
            if part == "teams" and i + 1 < len(parts):
                team_id = parts[i + 1]
                season_id = parts[i - 1] if i > 0 else "unknown"
                return team_id, season_id

        team_id = path.parent.name
        season_id = path.parent.parent.parent.name
        logger.warning(
            "Could not infer team_id/season_id from path %s; "
            "falling back to team_id=%s season_id=%s",
            path,
            team_id,
            season_id,
        )
        return team_id, season_id

    def _read_json(self, path: Path) -> dict | None:
        """Read and parse the JSON file at ``path``.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed dict, or ``None`` on read/parse error.
        """
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            logger.error("Stats file not found: %s", path)
            return None
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse stats JSON at %s: %s", path, exc)
            return None

        if not isinstance(data, dict):
            logger.error(
                "Expected a JSON object in %s, got %s", path, type(data).__name__
            )
            return None

        return data
