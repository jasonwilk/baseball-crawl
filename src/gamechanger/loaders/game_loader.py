"""Game loader for the baseball-crawl ingestion pipeline.

Upserts game records and per-player batting/pitching lines into the SQLite
database from an already-fetched, in-memory boxscore payload.  The caller
supplies the parsed boxscore dict and a matching :class:`GameSummaryEntry`
(``event_id``, ``home_away``, scores, start_time); ``games.game_id`` uses the
``event_id``.

Key data decisions
------------------
- **ID mapping**: DB primary key is the ``event_id`` carried on the summary.
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
    from src.gamechanger.loaders.game_loader import GameLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = GameLoader(conn, owned_team_ref=team_ref)
    result = loader.load_payload(boxscore_dict, summary)
    print(result)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, replace

from src.db.players import ensure_player_row
from src.db.teams import ensure_team_row_with_provenance
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team
from src.gamechanger.types import TeamRef
from src.gamechanger.url_parser import is_gc_uuid
from src.util.timezone import derive_local_date, get_operating_timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Batting stats mapped from boxscore to DB columns.
# Stats present in the main stats object (always):
_BATTING_MAIN: dict[str, str] = {
    "AB": "ab",
    "R": "r",
    "H": "h",
    "RBI": "rbi",
    "BB": "bb",
    "SO": "so",
}

# Extras mapped from stat_name to DB column (absent = 0):
_BATTING_EXTRAS: dict[str, str] = {
    "2B": "doubles",
    "3B": "triples",
    "HR": "hr",
    "SB": "sb",
    "TB": "tb",
    "HBP": "hbp",
    "CS": "cs",
}
# Nullable batting extras: SHF and E may be absent from some boxscore responses.
# Use dict.get() without default -- absent = NULL (not 0).
# SHF: listed in GC JS bundle but not confirmed in observed boxscore extras.
# E: placement varies (some boxscores list under FIELDING_EXTRA, not BATTING_EXTRA).
_BATTING_EXTRAS_NULLABLE: dict[str, str] = {
    "SHF": "shf",
    "E": "e",
}

# Pitching stats mapped from boxscore to DB columns.
_PITCHING_MAIN: dict[str, str] = {
    "H": "h",
    "R": "r",
    "ER": "er",
    "BB": "bb",
    "SO": "so",
}
# "IP" is converted to ip_outs (not a simple name mapping).

# Pitching extras mapped from stat_name to DB column (absent = 0):
_PITCHING_EXTRAS: dict[str, str] = {
    "WP": "wp",
    "HBP": "hbp",
    "#P": "pitches",
    "TS": "total_strikes",
    "BF": "bf",
}
# HR allowed is genuinely not in the boxscore pitching extras (confirmed by E-100).
_PITCHING_EXTRAS_SKIP_DEBUG = {"HR"}

# Stat-key drift canary core sets (E-253-06 / TN-7). Single-sourced from the
# parse dicts above so adding/removing a main key makes the canary track it
# automatically -- NEVER a fresh parallel hardcoded list. These are the keys the
# loader reads out of each row's ``stats`` dict; pitching additionally reads the
# always-present ``IP`` literal (converted to ip_outs, so not in _PITCHING_MAIN).
# Verified invariant across 46 real boxscores (941 batting, 207 pitching rows):
# every core key is present in every row. When a core key is absent from ALL
# rows of a NON-EMPTY group, that is the signature of a GameChanger field rename
# silently zeroing the stat for every player -- the canary fires (group-grain).
# Extras are DELIBERATELY excluded: they live in the sparse ``extra[]`` array,
# not the per-row ``stats`` dict, and are optionally-absent by design.
_BATTING_CANARY_KEYS: tuple[str, ...] = tuple(_BATTING_MAIN)
_PITCHING_CANARY_KEYS: tuple[str, ...] = (*_PITCHING_MAIN, "IP")

# Sentinel opponent name used when an opponent is truly unresolvable (no stat
# block, no UUID, no schedule name). Resolving to a distinct sentinel row -- not
# ``own_team_id`` -- is the home != away invariant guard (E-245-04 / TN-6).
_UNKNOWN_OPPONENT_NAME = "Unknown Opponent"


def _opt_int(value: object) -> int | None:
    """Coerce a score-like value to int, preserving MISSING as ``None``.

    A present ``0`` (a genuinely scoreless line) stays ``0``; only an absent or
    blank value becomes ``None``. This is the fix for the 0-0 coercion footgun
    (E-253-06 / audit LOW): flattening missing scores to ``0`` lets two distinct
    scoreless games on the same date/team-pair collapse under the natural-key
    dedup (both look like the same 0-0 game). ``None`` scores instead leave the
    dedup with no score signal, so distinct games stay distinct rows.
    """
    if value is None or value == "":
        return None
    return int(value)


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
        owning_team_score: Score for the team that owns the game-summaries file,
            or None when the summary omits score data (NOT coerced to 0 -- see
            :func:`_opt_int`).
        opponent_team_score: Score for the opponent team, or None when absent.
        opponent_id: UUID of the opponent team.
        last_scoring_update: ISO 8601 timestamp string.
        start_time: ISO 8601 datetime string from schedule/public endpoint, or None.
        timezone: IANA timezone identifier (e.g., ``America/Chicago``), or None.
    """

    event_id: str
    game_stream_id: str
    home_away: str | None
    owning_team_score: int | None
    opponent_team_score: int | None
    opponent_id: str
    last_scoring_update: str
    start_time: str | None = None
    timezone: str | None = None


@dataclass
class _PlayerBatting:
    """Per-player batting line ready for DB insertion."""

    player_id: str
    ab: int = 0
    r: int = 0
    h: int = 0
    doubles: int = 0
    triples: int = 0
    hr: int = 0
    rbi: int = 0
    bb: int = 0
    so: int = 0
    sb: int = 0
    tb: int = 0
    hbp: int = 0
    cs: int = 0
    shf: int | None = None
    e: int | None = None


@dataclass
class _PlayerPitching:
    """Per-player pitching line ready for DB insertion."""

    player_id: str
    ip_outs: int = 0
    h: int = 0
    r: int = 0
    er: int = 0
    bb: int = 0
    so: int = 0
    wp: int = 0
    hbp: int = 0
    pitches: int = 0
    total_strikes: int = 0
    bf: int = 0
    appearance_order: int | None = None


# ---------------------------------------------------------------------------
# GameLoader
# ---------------------------------------------------------------------------


class GameLoader:
    """Loads in-memory boxscore payloads into the SQLite database.

    Each call resolves the payload against its caller-supplied
    ``GameSummaryEntry`` and upserts the game record plus per-player batting and
    pitching lines.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
        owned_team_ref: ``TeamRef`` for the team whose API call produced the
            payload.  Used to identify which boxscore key belongs to the owned
            team vs. the opponent.  ``gc_uuid`` is used for boxscore key
            detection; ``id`` is used for FK inserts.
        created_team_ids: Optional in-memory set the loader records into when it
            INSERTs a brand-new opponent team row (E-235-04). Used by the report
            generator's per-run created-set so orphan cleanup deletes only teams
            THIS run inserted -- closing the cross-process team-deletion race
            without a global pre/post snapshot diff. ``None`` (the default)
            disables recording for all other callers.
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        owned_team_ref: TeamRef,
        created_team_ids: set[int] | None = None,
    ) -> None:
        self._db = db
        self._team_ref = owned_team_ref
        self._created_team_ids = created_team_ids
        self._season_id, self._season_year = derive_season_id_for_team(
            db, owned_team_ref.id
        )
        # {source_event_id: canonical_game_id} accumulated as a side-effect each
        # time _find_duplicate_game redirects a cross-perspective duplicate to an
        # existing canonical row (E-244). GameLoader is constructed fresh per
        # report run, so this map is naturally scoped to one run (no reset).
        # Exposed to the report generator via LoadResult.redirect_map so the
        # plays/spray stages file rows under the canonical id.
        self.redirect_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_payload(
        self,
        raw: dict,
        summary: GameSummaryEntry,
        opponent_name: str | None = None,
    ) -> LoadResult:
        """Load a single in-memory boxscore dict.

        The sole entry point: applies team-key detection, ID resolution,
        ``_find_duplicate_game`` dedup, and per-player stat upsert to an
        already-parsed boxscore dict, then commits per call (TN-10 option (b)).

        PRECONDITION: the caller MUST ensure the ``seasons`` row for
        ``self._season_id`` exists (``ensure_season_row``) before calling.  This
        method INSERTs ``games.season_id`` and ``team_rosters.season_id`` but
        does not create the parent row, so a missing season raises a FOREIGN KEY
        error that surfaces as ``LoadResult(errors=1)``.  ``ScoutingLoader``
        (the only production caller) does this in ``_load_team_core``; the
        deleted ``load_all`` used to do it inline (E-256-01).

        Args:
            raw: Parsed boxscore response dict.
            summary: Resolved game-summaries entry for this game.
            opponent_name: Human-readable opponent team name.  When provided,
                used as the ``teams.name`` value instead of the UUID placeholder.

        Returns:
            ``LoadResult`` for this single game.
        """
        result = self._load_boxscore_data(raw, summary, opponent_name=opponent_name)
        self._db.commit()
        return result

    # ------------------------------------------------------------------
    # Core loading logic
    # ------------------------------------------------------------------

    def _load_boxscore_data(
        self,
        raw: dict | list,
        summary: GameSummaryEntry,
        opponent_name: str | None = None,
    ) -> LoadResult:
        """Process a single parsed boxscore payload into games + stat rows.

        Performs the non-dict guard, team-key detection, ID resolution,
        ``_find_duplicate_game`` dedup, and per-player stat upsert.  Does NOT
        commit -- :meth:`load_payload` owns the commit boundary.

        Args:
            raw: Parsed boxscore payload (expected to be a dict).
            summary: Resolved game-summaries entry for this game.
            opponent_name: Human-readable opponent team name.
        """
        if not isinstance(raw, dict):
            logger.error(
                "Expected boxscore payload to be a JSON object, got %s",
                type(raw).__name__,
            )
            return LoadResult(errors=1)

        # Detect which key is own team and which is opponent.
        own_key, opp_key = self._detect_team_keys(raw)
        if own_key is None and opp_key is None:
            logger.error(
                "Could not identify team keys in boxscore for game %s",
                summary.event_id,
            )
            return LoadResult(errors=1)

        own_data = raw.get(own_key) if own_key else None
        opp_data = raw.get(opp_key) if opp_key else None

        # Resolve INTEGER PKs for home/away team rows.  The opponent ALWAYS
        # resolves to a DISTINCT team id -- by boxscore key/UUID, by name when
        # the opponent stat block is absent, or an "Unknown Opponent" sentinel
        # stub when truly unresolvable -- so a self-game (home == away) is never
        # produced (E-245-04 / TN-6).  ``opp_data`` is already None whenever the
        # boxscore lacks the opponent stat block (``opp_key`` is None); the
        # opponent then simply has no per-player stat rows (truthful).
        own_team_id, opp_team_id = self._resolve_team_ids(
            summary, opp_key, opponent_name=opponent_name,
        )

        # Resolve home/away for games table.
        home_team_id, away_team_id, home_score, away_score = self._resolve_home_away(
            summary, own_team_id, opp_team_id
        )

        # Game date: the venue-LOCAL calendar date of the scoring instant
        # (CE-3 / E-253-04). Deriving it from the raw UTC prefix files an
        # evening game under the next UTC day, skewing rest math, the 7-day
        # window, and cross-perspective dedup at UTC midnight. Use the game's
        # own timezone when present, else the operating-tz seam -- bridging the
        # seam's ZoneInfo to its IANA name via ``.key`` (derive_local_date takes
        # a NAME, never a ZoneInfo object). Falls back to the old UTC slice only
        # when the instant is absent/unparseable.
        if summary.last_scoring_update:
            tz_name = summary.timezone or get_operating_timezone().key
            game_date = (
                derive_local_date(summary.last_scoring_update, tz_name)
                or summary.last_scoring_update[:10]
            )
        else:
            game_date = "1900-01-01"

        # Pre-load dedup check: if a game already exists for this date and
        # team pair (in either home/away order), reuse the existing game_id
        # so all stat upserts merge into the canonical row.
        canonical_id = self._find_duplicate_game(
            summary.event_id, game_date,
            home_team_id, away_team_id, home_score, away_score,
            summary.start_time,
        )
        if canonical_id is not None:
            logger.info(
                "Dedup: redirecting game %s → %s (same date %s, same teams)",
                summary.event_id, canonical_id, game_date,
            )
            # Record the redirect BEFORE replace() rewrites summary.event_id, so
            # the source→canonical mapping is captured for the generator's
            # plays/spray stages (E-244 TN-2). Only actual redirects are recorded.
            self.redirect_map[summary.event_id] = canonical_id
            summary = replace(summary, event_id=canonical_id)

        return self._upsert_game_and_stats(
            summary, game_date,
            home_team_id, away_team_id, home_score, away_score,
            own_data, own_team_id, opp_data, opp_team_id,
        )

    def _resolve_team_ids(
        self,
        summary: GameSummaryEntry,
        opp_key: str | None,
        opponent_name: str | None = None,
    ) -> tuple[int, int]:
        """Resolve INTEGER PKs for own and opponent teams.

        The opponent ALWAYS resolves to a DISTINCT team id so a self-game
        (``home_team_id == away_team_id``) is never produced (E-245-04 / TN-6):

        1. By the boxscore stat-block key / opponent UUID when present.
        2. By NAME (``opponent_name``) when the opponent stat block is absent
           (these opponents never used GC scorekeeping, so the boxscore carries
           only the scouted team's key).  The opponent row gets no per-player
           stat rows -- truthful, not fabricated.
        3. By an "Unknown Opponent" sentinel stub when truly unresolvable (no
           key, no UUID, no name) -- NEVER ``own_team_id``.

        A final invariant guard substitutes the sentinel if name dedup happened
        to collapse the opponent onto ``own_team_id`` (e.g. an opponent name
        matching the scouted team).

        Args:
            summary: Game summary entry containing opponent_id.
            opp_key: Opponent key from the boxscore response (fallback UUID).
            opponent_name: Human-readable opponent team name to use when
                creating or updating the teams row.

        Returns:
            ``(own_team_id, opp_team_id)`` -- both are real, DISTINCT team PKs.
        """
        own_team_id: int = self._team_ref.id
        opp_identifier = summary.opponent_id or opp_key
        if opp_identifier:
            opp_team_id = self._ensure_team_row(opp_identifier, opponent_name=opponent_name)
        elif opponent_name:
            # No opponent stat block/UUID, but the schedule names the opponent:
            # create a DISTINCT opponent row by name (E-245-04 / TN-6).
            logger.info(
                "No opponent stat block for game %s; resolving opponent by name %r.",
                summary.event_id, opponent_name,
            )
            opp_team_id = self._ensure_team_row(opponent_name, opponent_name=opponent_name)
        else:
            # Truly unresolvable -- use the sentinel stub, never own_team_id.
            logger.warning(
                "Opponent unresolvable for game %s (no stat block, UUID, or name); "
                "using %r sentinel stub.",
                summary.event_id, _UNKNOWN_OPPONENT_NAME,
            )
            opp_team_id = self._ensure_team_row(
                _UNKNOWN_OPPONENT_NAME, opponent_name=_UNKNOWN_OPPONENT_NAME,
            )

        # Invariant guard (TN-6): the opponent MUST be distinct from own team.
        # If name dedup collapsed it onto own_team_id, fall back to the sentinel.
        if opp_team_id == own_team_id:
            logger.warning(
                "Opponent for game %s resolved to own team id %d; substituting "
                "%r sentinel to preserve home != away.",
                summary.event_id, own_team_id, _UNKNOWN_OPPONENT_NAME,
            )
            opp_team_id = self._ensure_team_row(
                _UNKNOWN_OPPONENT_NAME, opponent_name=_UNKNOWN_OPPONENT_NAME,
            )
            if opp_team_id == own_team_id:
                # Pathological: own team is itself named the sentinel. Use a
                # game-suffixed sentinel so the row is guaranteed distinct.
                suffixed = f"{_UNKNOWN_OPPONENT_NAME} ({summary.event_id})"
                opp_team_id = self._ensure_team_row(suffixed, opponent_name=suffixed)
        return own_team_id, opp_team_id

    def _resolve_home_away(
        self,
        summary: GameSummaryEntry,
        own_team_id: int,
        opp_team_id: int,
    ) -> tuple[int, int, int | None, int | None]:
        """Determine home/away team IDs and scores from the game summary.

        Args:
            summary: Game summary entry with home_away and score fields.
            own_team_id: INTEGER PK of the owned team.
            opp_team_id: INTEGER PK of the opponent team.

        Returns:
            ``(home_team_id, away_team_id, home_score, away_score)``.
        """
        home_away = summary.home_away
        if home_away == "home":
            return own_team_id, opp_team_id, summary.owning_team_score, summary.opponent_team_score
        if home_away == "away":
            return opp_team_id, own_team_id, summary.opponent_team_score, summary.owning_team_score
        # home_away is None -- default own team to home and log warning.
        logger.warning(
            "home_away is None for game_id=%s; defaulting own team to home.",
            summary.event_id,
        )
        return own_team_id, opp_team_id, summary.owning_team_score, summary.opponent_team_score

    def _upsert_game_and_stats(
        self,
        summary: GameSummaryEntry,
        game_date: str,
        home_team_id: int,
        away_team_id: int,
        home_score: int | None,
        away_score: int | None,
        own_data: dict | None,
        own_team_id: int,
        opp_data: dict | None,
        opp_team_id: int,
    ) -> LoadResult:
        """Upsert the game row and load per-player stats for both teams.

        Args:
            summary: Game summary entry.
            game_date: ISO date string (YYYY-MM-DD).
            home_team_id: INTEGER PK of the home team.
            away_team_id: INTEGER PK of the away team.
            home_score: Final score for the home team.
            away_score: Final score for the away team.
            own_data: Boxscore data dict for the owned team (or None).
            own_team_id: INTEGER PK of the owned team.
            opp_data: Boxscore data dict for the opponent team (or None).
            opp_team_id: INTEGER PK of the opponent team.

        Returns:
            ``LoadResult`` for this game.
        """
        try:
            self._upsert_game(
                summary.event_id, game_date,
                home_team_id, away_team_id, home_score, away_score,
                summary.game_stream_id,
                start_time=summary.start_time,
                timezone=summary.timezone,
            )
        except (sqlite3.Error, ValueError) as exc:
            # ValueError = the _upsert_game home != away invariant guard
            # (E-245-04 / TN-6) refusing to write a self-game.
            logger.error("Failed to upsert game %s: %s", summary.event_id, exc)
            return LoadResult(errors=1)

        # Record which perspective loaded this game.
        perspective_team_id = self._team_ref.id
        try:
            self._db.execute(
                """
                INSERT OR IGNORE INTO game_perspectives
                    (game_id, perspective_team_id)
                VALUES (?, ?)
                """,
                (summary.event_id, perspective_team_id),
            )
        except sqlite3.Error as exc:
            logger.error(
                "Failed to insert game_perspectives for game %s perspective %s: %s",
                summary.event_id, perspective_team_id, exc,
            )

        result = LoadResult()
        if own_data:
            r = self._load_team_stats(own_data, own_team_id, summary.event_id, perspective_team_id)
            result.loaded += r.loaded
            result.skipped += r.skipped
            result.errors += r.errors
        if opp_data:
            r = self._load_team_stats(opp_data, opp_team_id, summary.event_id, perspective_team_id)
            result.loaded += r.loaded
            result.skipped += r.skipped
            result.errors += r.errors
        result.loaded += 1  # count the game itself
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
        uuid_keys = [k for k in keys if is_gc_uuid(k)]
        slug_keys = [k for k in keys if not is_gc_uuid(k)]

        own_key: str | None = slug_keys[0] if slug_keys else None
        opp_key: str | None = uuid_keys[0] if uuid_keys else None

        # If all keys are UUIDs (opponent-vs-opponent data), pick own team by
        # matching against the owned team's gc_uuid; the other is the opponent.
        if own_key is None and len(uuid_keys) >= 2:
            owned_gc_uuid = self._team_ref.gc_uuid
            if owned_gc_uuid is None:
                logger.warning(
                    "Cannot identify own team key in UUID-only boxscore: gc_uuid is None. "
                    "own_key will be None."
                )
            else:
                for k in uuid_keys:
                    if k.lower() == owned_gc_uuid.lower():
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
        self, team_data: dict, team_id: int, game_id: str,
        perspective_team_id: int,
    ) -> LoadResult:
        """Parse and load batting + pitching lines for one team in a boxscore.

        Also extracts player names from the ``players`` array and uses them
        for player row creation/upgrade (conditional UPSERT: only overwrites
        "Unknown" stubs).  Jersey numbers are backfilled into ``team_rosters``.

        Args:
            team_data: Value under one team key in the boxscore (contains
                ``players`` and ``groups``).
            team_id: INTEGER PK from the ``teams`` table for this side of the game.
            game_id: Canonical event_id (games.game_id FK).
            perspective_team_id: INTEGER PK of the team whose API call produced
                this boxscore data.

        Returns:
            ``LoadResult`` for this team's players.
        """
        # Build player info lookup from the boxscore players array.
        player_info: dict[str, dict] = {}
        for p in team_data.get("players") or []:
            pid = p.get("id")
            if pid:
                player_info[pid] = p

        result = LoadResult()
        groups: list[dict] = team_data.get("groups") or []

        for group in groups:
            category = group.get("category")
            if category == "lineup":
                r = self._load_batting_group(group, team_id, game_id, player_info, perspective_team_id)
            elif category == "pitching":
                r = self._load_pitching_group(group, team_id, game_id, player_info, perspective_team_id)
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
        self, group: dict, team_id: int, game_id: str,
        player_info: dict[str, dict] | None,
        perspective_team_id: int,
    ) -> LoadResult:
        """Parse and upsert batting lines from a lineup group.

        Args:
            group: The ``category="lineup"`` group dict from the boxscore.
            team_id: INTEGER PK from the ``teams`` table for this batting side.
            game_id: Canonical event_id.
            player_info: Lookup from the boxscore ``players`` array
                (``{player_id: {first_name, last_name, number, ...}}``).

        Returns:
            ``LoadResult`` for this batting group.
        """
        if player_info is None:
            player_info = {}
        result = LoadResult()

        # Build extras lookup: {player_id: {stat_name: value}}
        extras = self._build_extras_index(group.get("extra") or [])

        stat_rows: list[dict] = group.get("stats") or []
        result.errors += self._canary_stat_key_drift(
            stat_rows, _BATTING_CANARY_KEYS,
            group_label="batting", team_id=team_id, game_id=game_id,
        )

        for stat_row in stat_rows:
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
            for api_key, db_col in _BATTING_EXTRAS.items():
                val = player_extras.get(api_key, 0)
                setattr(batting, db_col, int(val))
            for api_key, db_col in _BATTING_EXTRAS_NULLABLE.items():
                val = player_extras.get(api_key)
                setattr(batting, db_col, int(val) if val is not None else None)

            try:
                info = player_info.get(player_id, {})
                ensure_player_row(
                    self._db,
                    player_id,
                    info.get("first_name") or "Unknown",
                    info.get("last_name") or "Unknown",
                )
                self._upsert_roster_jersey(
                    team_id, player_id, info.get("number"),
                )
                self._upsert_batting(batting, team_id, game_id, perspective_team_id)
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
        self, group: dict, team_id: int, game_id: str,
        player_info: dict[str, dict] | None,
        perspective_team_id: int,
    ) -> LoadResult:
        """Parse and upsert pitching lines from a pitching group.

        Args:
            group: The ``category="pitching"`` group dict from the boxscore.
            team_id: INTEGER PK from the ``teams`` table for this pitching side.
            game_id: Canonical event_id.
            player_info: Lookup from the boxscore ``players`` array.

        Returns:
            ``LoadResult`` for this pitching group.
        """
        if player_info is None:
            player_info = {}
        result = LoadResult()

        extras = self._build_extras_index(group.get("extra") or [])

        stat_rows: list[dict] = group.get("stats") or []
        result.errors += self._canary_stat_key_drift(
            stat_rows, _PITCHING_CANARY_KEYS,
            group_label="pitching", team_id=team_id, game_id=game_id,
        )

        for idx, stat_row in enumerate(stat_rows, start=1):
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

            pitching = _PlayerPitching(player_id=player_id, appearance_order=idx)
            for api_key, db_col in _PITCHING_MAIN.items():
                if api_key in raw_stats:
                    setattr(pitching, db_col, int(raw_stats[api_key]))
            # IP -> ip_outs conversion (1 IP = 3 outs)
            if "IP" in raw_stats:
                pitching.ip_outs = round(float(raw_stats["IP"]) * 3)
            for api_key, db_col in _PITCHING_EXTRAS.items():
                val = player_extras.get(api_key, 0)
                setattr(pitching, db_col, int(val))
            for api_key in _PITCHING_EXTRAS_SKIP_DEBUG:
                if api_key in player_extras:
                    logger.debug(
                        "Pitching extra %r not in schema; ignoring (player=%s game=%s)",
                        api_key,
                        player_id,
                        game_id,
                    )

            try:
                info = player_info.get(player_id, {})
                ensure_player_row(
                    self._db,
                    player_id,
                    info.get("first_name") or "Unknown",
                    info.get("last_name") or "Unknown",
                )
                self._upsert_roster_jersey(
                    team_id, player_id, info.get("number"),
                )
                self._upsert_pitching(pitching, team_id, game_id, perspective_team_id)
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

    def _canary_stat_key_drift(
        self,
        stat_rows: list[dict],
        core_keys: tuple[str, ...],
        *,
        group_label: str,
        team_id: int,
        game_id: str,
    ) -> int:
        """Stat-key drift canary (E-253-06 / TN-7): return 1 on fire, else 0.

        Fires at GROUP grain (never per-row) when a core key is absent from the
        per-row ``stats`` dict of ALL rows in a NON-EMPTY group -- the signature
        of a GameChanger field rename that would silently zero the stat for
        every player on the team. A cross-perspective reconciliation cannot catch
        this because both perspectives share the same corrupted source. The returned ``1`` is
        the ``LoadResult.errors`` increment the caller adds -- a hard-fail signal
        the future E-245 reconciliation scoreboard can consume (AC-4).

        The group is still loaded (a renamed key is unreadable regardless of what
        we do here); the point is that the corruption is now LOUD (an ERROR +
        ``errors`` increment) instead of silently loading zeros. Extras are NOT
        checked: they live in the sparse ``extra[]`` array, not the per-row
        ``stats`` dict, and are optionally-absent by design (AC-2).
        """
        if not stat_rows:
            return 0
        per_row_stats = [row.get("stats") or {} for row in stat_rows]
        drifted = [k for k in core_keys if all(k not in s for s in per_row_stats)]
        if not drifted:
            return 0
        logger.error(
            "Stat-key drift canary FIRED for %s group (game %s team %s): core "
            "key(s) %s absent from the stats dict of ALL %d row(s) -- likely a "
            "GameChanger field rename silently zeroing the stat for every player.",
            group_label, game_id, team_id, sorted(drifted), len(per_row_stats),
        )
        return 1

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

    # ------------------------------------------------------------------
    # Dedup check
    # ------------------------------------------------------------------

    def _find_duplicate_game(
        self,
        game_id: str,
        game_date: str,
        home_team_id: int,
        away_team_id: int,
        home_score: int | None,
        away_score: int | None,
        start_time: str | None,
    ) -> str | None:
        """Check if a game already exists for this date and team pair.

        Searches for a completed game on the same date involving the same two
        teams (order-insensitive).  Doubleheaders are distinguished by
        ``start_time`` first, then by score totals as a fallback.

        Args:
            game_id: The incoming game's event_id.
            game_date: ISO date string (YYYY-MM-DD).
            home_team_id: INTEGER PK of the home team.
            away_team_id: INTEGER PK of the away team.
            home_score: Final home score.
            away_score: Final away score.
            start_time: ISO 8601 datetime string or None.

        Returns:
            The existing ``game_id`` to reuse, or ``None`` if no duplicate.
        """
        rows = self._db.execute(
            """
            SELECT game_id, home_team_id, away_team_id,
                   home_score, away_score, start_time
            FROM games
            WHERE game_date = ?
              AND status = 'completed'
              AND game_id != ?
              AND (
                (home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?)
              )
            ORDER BY start_time ASC NULLS LAST
            """,
            (game_date, game_id,
             home_team_id, away_team_id,
             away_team_id, home_team_id),
        ).fetchall()

        if not rows:
            return None

        incoming_perspective_team_id = self._team_ref.id
        incoming_total = (
            home_score + away_score
            if home_score is not None and away_score is not None
            else None
        )

        for row in rows:
            existing_id = row[0]
            existing_home_score = row[3]
            existing_away_score = row[4]
            existing_start_time = row[5]
            existing_total = (
                existing_home_score + existing_away_score
                if existing_home_score is not None and existing_away_score is not None
                else None
            )

            # Provenance: which perspective(s) already loaded this candidate?
            existing_perspective_ids = {
                r[0] for r in self._db.execute(
                    "SELECT perspective_team_id FROM game_perspectives WHERE game_id = ?",
                    (existing_id,),
                ).fetchall()
            }

            cross_perspective = (
                bool(existing_perspective_ids)
                and incoming_perspective_team_id not in existing_perspective_ids
            )

            if cross_perspective:
                # Cross-perspective duplicate case: a different tracked team's
                # scout already loaded this row. Scores are stable across
                # perspectives; GC reports per-perspective start_times that
                # can disagree for the same real game (observed ~30-minute
                # offsets). Per-team score match is the authoritative signal.
                # IMPORTANT: compare (home_score, away_score) pairwise, NOT
                # the sum -- a real doubleheader can produce same-total
                # different-scoreline games (e.g. 11-1 and 10-2 both total 12).
                have_both_scores = (
                    home_score is not None
                    and away_score is not None
                    and existing_home_score is not None
                    and existing_away_score is not None
                )
                if have_both_scores:
                    scores_match = (
                        home_score == existing_home_score
                        and away_score == existing_away_score
                    )
                    if scores_match:
                        if (start_time is not None
                            and existing_start_time is not None
                            and start_time != existing_start_time):
                            logger.warning(
                                "Cross-perspective dedup: game %s (perspective %d) "
                                "→ %s (perspectives %s). Start times disagree "
                                "(%s vs %s); treating as duplicate because "
                                "per-team scores match (%s-%s). GC reports "
                                "per-perspective start_times for the same real game.",
                                game_id, incoming_perspective_team_id, existing_id,
                                sorted(existing_perspective_ids),
                                start_time, existing_start_time,
                                home_score, away_score,
                            )
                        return existing_id
                    # Different per-team scores across perspectives → distinct
                    # games (real doubleheader or a data-quality disagreement
                    # worth surfacing as separate rows).
                    continue

                # Scores unavailable on one or both sides; fall back to
                # start_time match as the only available signal.
                if start_time is not None and existing_start_time is not None:
                    if start_time == existing_start_time:
                        return existing_id
                    continue

                logger.warning(
                    "Cannot distinguish cross-perspective game %s from existing "
                    "%s on %s (no scores, no start_time to compare); skipping "
                    "candidate.",
                    game_id, existing_id, game_date,
                )
                continue

            # Same-perspective or no-provenance candidate: preserve the
            # legacy tiebreaker (start_time first, score fallback). Same-
            # perspective re-loads reach this branch when the whole-game
            # idempotency check doesn't cover the path (e.g., different
            # event_ids for the same real game from the same perspective).
            if start_time is not None and existing_start_time is not None:
                if start_time != existing_start_time:
                    # Different start times → distinct games (doubleheader).
                    continue
                # Same start time → duplicate.
                return existing_id

            if incoming_total is not None and existing_total is not None:
                if incoming_total != existing_total:
                    # Different score totals → distinct games (doubleheader).
                    continue
                # Same score total → duplicate.
                return existing_id

            # Neither start_time nor score can distinguish → skip this
            # candidate and check remaining rows.
            logger.warning(
                "Cannot distinguish game %s from existing %s on %s "
                "(no start_time, no score to compare); skipping candidate.",
                game_id, existing_id, game_date,
            )
            continue

        return None

    # ------------------------------------------------------------------
    # DB write helpers
    # ------------------------------------------------------------------

    def _upsert_game(
        self,
        game_id: str,
        game_date: str,
        home_team_id: int,
        away_team_id: int,
        home_score: int | None,
        away_score: int | None,
        game_stream_id: str,
        start_time: str | None = None,
        timezone: str | None = None,
    ) -> None:
        """Upsert a game record into the ``games`` table.

        Args:
            game_id: Canonical event_id (PK).
            game_date: ISO 8601 date string.
            home_team_id: INTEGER PK of the home team.
            away_team_id: INTEGER PK of the away team.
            home_score: Final home score, or None when the summary omits it
                (stored as NULL -- never coerced to 0, per E-253-06).
            away_score: Final away score, or None when the summary omits it.
            game_stream_id: Stream ID from game-summaries (boxscore file key).
            start_time: ISO 8601 datetime string from schedule/public endpoint.
            timezone: IANA timezone identifier (e.g., ``America/Chicago``).

        Raises:
            ValueError: If ``home_team_id == away_team_id`` -- the home != away
                invariant guard (E-245-04 / TN-6).  Opponent resolution
                guarantees a distinct opponent, so this is a defensive last
                gate; the caller turns it into a ``LoadResult(errors=1)``.
        """
        if home_team_id == away_team_id:
            raise ValueError(
                f"Refusing to upsert self-game {game_id}: "
                f"home_team_id == away_team_id == {home_team_id} "
                f"(E-245-04 / TN-6 home != away invariant)."
            )
        self._db.execute(
            """
            INSERT INTO games
                (game_id, season_id, game_date, home_team_id, away_team_id,
                 home_score, away_score, status, game_stream_id,
                 start_time, timezone)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)
            ON CONFLICT(game_id) DO UPDATE SET
                season_id      = excluded.season_id,
                game_date      = excluded.game_date,
                home_team_id   = excluded.home_team_id,
                away_team_id   = excluded.away_team_id,
                home_score     = excluded.home_score,
                away_score     = excluded.away_score,
                status         = excluded.status,
                game_stream_id = excluded.game_stream_id,
                start_time     = COALESCE(excluded.start_time, games.start_time),
                timezone       = COALESCE(excluded.timezone, games.timezone)
            """,
            (game_id, self._season_id, game_date, home_team_id, away_team_id,
             home_score, away_score, game_stream_id, start_time, timezone),
        )
        logger.debug(
            # %s (not %d): home/away score may be None for a score-less summary.
            "Upserted game %s: %s vs %s (%s-%s) on %s",
            game_id,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            game_date,
        )

    def _upsert_batting(
        self, batting: _PlayerBatting, team_id: int, game_id: str,
        perspective_team_id: int,
    ) -> None:
        """Upsert a batting line into ``player_game_batting``.

        Args:
            batting: Parsed batting record.
            team_id: INTEGER PK from the ``teams`` table.
            game_id: Canonical event_id.
            perspective_team_id: INTEGER PK of the team whose API call produced
                this data.  REQUIRED -- no default per E-220 hard-error guarantee.
        """
        self._db.execute(
            """
            INSERT INTO player_game_batting
                (game_id, player_id, team_id, perspective_team_id,
                 ab, r, h, doubles, triples,
                 hr, rbi, bb, so, sb, tb, hbp, cs, shf, e)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id, player_id, perspective_team_id) DO UPDATE SET
                team_id = excluded.team_id,
                ab      = excluded.ab,
                r       = excluded.r,
                h       = excluded.h,
                doubles = excluded.doubles,
                triples = excluded.triples,
                hr      = excluded.hr,
                rbi     = excluded.rbi,
                bb      = excluded.bb,
                so      = excluded.so,
                sb      = excluded.sb,
                tb      = excluded.tb,
                hbp     = excluded.hbp,
                cs      = excluded.cs,
                shf     = excluded.shf,
                e       = excluded.e
            """,
            (
                game_id,
                batting.player_id,
                team_id,
                perspective_team_id,
                batting.ab,
                batting.r,
                batting.h,
                batting.doubles,
                batting.triples,
                batting.hr,
                batting.rbi,
                batting.bb,
                batting.so,
                batting.sb,
                batting.tb,
                batting.hbp,
                batting.cs,
                batting.shf,
                batting.e,
            ),
        )

    def _upsert_pitching(
        self, pitching: _PlayerPitching, team_id: int, game_id: str,
        perspective_team_id: int,
    ) -> None:
        """Upsert a pitching line into ``player_game_pitching``.

        Args:
            pitching: Parsed pitching record.
            team_id: INTEGER PK from the ``teams`` table.
            game_id: Canonical event_id.
            perspective_team_id: INTEGER PK of the team whose API call produced
                this data.  REQUIRED -- no default per E-220 hard-error guarantee.
        """
        self._db.execute(
            """
            INSERT INTO player_game_pitching
                (game_id, player_id, team_id, perspective_team_id,
                 ip_outs, h, r, er, bb, so,
                 wp, hbp, pitches, total_strikes, bf, appearance_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id, player_id, perspective_team_id) DO UPDATE SET
                team_id          = excluded.team_id,
                ip_outs          = excluded.ip_outs,
                h                = excluded.h,
                r                = excluded.r,
                er               = excluded.er,
                bb               = excluded.bb,
                so               = excluded.so,
                wp               = excluded.wp,
                hbp              = excluded.hbp,
                pitches          = excluded.pitches,
                total_strikes    = excluded.total_strikes,
                bf               = excluded.bf,
                appearance_order = excluded.appearance_order
            """,
            (
                game_id,
                pitching.player_id,
                team_id,
                perspective_team_id,
                pitching.ip_outs,
                pitching.h,
                pitching.r,
                pitching.er,
                pitching.bb,
                pitching.so,
                pitching.wp,
                pitching.hbp,
                pitching.pitches,
                pitching.total_strikes,
                pitching.bf,
                pitching.appearance_order,
            ),
        )

    def _upsert_roster_jersey(
        self,
        team_id: int,
        player_id: str,
        jersey_number: str | None,
    ) -> None:
        """Upsert a ``team_rosters`` row with jersey number backfill.

        Creates a new roster row if none exists, or backfills ``jersey_number``
        on an existing row only when the current value is NULL.  ``position``
        is left NULL on boxscore-sourced rows; existing values are never
        overwritten.

        Args:
            team_id: INTEGER PK from the ``teams`` table.
            player_id: GameChanger player UUID.
            jersey_number: Jersey number string from boxscore (or ``None``).
        """
        if jersey_number is None:
            # Still ensure the roster row exists (position stays NULL).
            self._db.execute(
                """
                INSERT INTO team_rosters (team_id, player_id, season_id)
                VALUES (?, ?, ?)
                ON CONFLICT(team_id, player_id, season_id) DO NOTHING
                """,
                (team_id, player_id, self._season_id),
            )
            return

        self._db.execute(
            """
            INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(team_id, player_id, season_id) DO UPDATE
            SET jersey_number = excluded.jersey_number
            WHERE team_rosters.jersey_number IS NULL
            """,
            (team_id, player_id, self._season_id, jersey_number),
        )

    def _ensure_team_row(self, identifier: str, opponent_name: str | None = None) -> int:
        """Ensure a ``teams`` row exists for an opponent and return its INTEGER PK.

        Delegates to the shared ``ensure_team_row()`` dedup cascade with
        ``gc_uuid=None`` to prevent boxscore-derived opponent-perspective
        identifiers from contaminating the ``gc_uuid`` column.

        When a ``created_team_ids`` set was supplied (E-235-04) and this call
        INSERTs a brand-new row (provenance ``inserted=True``), the new team id
        is recorded into it. MATCHED rows are never recorded -- two concurrent
        runs referencing the same pre-existing opponent must not both claim it.

        Args:
            identifier: Boxscore key or opponent_id string.  Used only as a
                name fallback when ``opponent_name`` is ``None``.
            opponent_name: Human-readable team name.  When ``None``, falls back
                to ``identifier`` as the name to preserve unique row naming.

        Returns:
            The ``teams.id`` INTEGER PK for the row.
        """
        result = ensure_team_row_with_provenance(
            self._db,
            gc_uuid=None,
            name=opponent_name or identifier,
            season_year=self._season_year,
            source="game_loader",
        )
        if result.inserted and self._created_team_ids is not None:
            self._created_team_ids.add(result.team_id)
        return result.team_id
