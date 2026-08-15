"""Game loader for the baseball-crawl ingestion pipeline.

Upserts game records and per-player batting/pitching lines into the SQLite
database from an already-fetched, in-memory boxscore payload.  The caller
supplies the parsed boxscore dict and a matching :class:`GameSummaryEntry`
(``event_id``, ``home_away``, scores, start_time); ``games.game_id`` uses the
``event_id``.

Key data decisions
------------------
- **ID mapping**: DB primary key is the ``event_id`` carried on the summary.
- **Boxscore keys are classified by IDENTITY, not shape**: a key is a
  ``public_id`` slug or a UUID, and the form does NOT mark which side it is --
  both keys are slugs on ~10% of payloads (14 of 140, measured 2026-08-03).
  What DECIDES the form is NOT established: "the team has a public GC presence"
  and "the opponent was linked via team lookup" were both refuted 2026-08-03.
  Match keys against our own ``public_id`` / ``gc_uuid``; the other key is the
  opponent.  The older "own = slug, opponent = UUID" shape rule silently
  discarded the opponent's whole envelope whenever the opponent's key was also
  a slug.  A UUID-form OPPONENT key is a per-account local ``root_team_id``,
  NOT a canonical ``gc_uuid`` -- never store it as one.
  See :meth:`GameLoader._detect_team_keys`.
- **IP to ip_outs**: boxscore stores IP as float decimal innings (e.g. 3.333...
  = 3⅓ innings = 10 outs).  The schema stores ``ip_outs`` (integer outs).
  Convert: ``ip_outs = round(float(IP) * 3)``.
- **Sparse extras**: the ``extra[]`` array in each group contains only non-zero
  player values.  Missing values default to 0.
- **Stub players**: unknown player_ids get a stub row (first_name='Unknown',
  last_name='Unknown') before the stat insert (FK-safe).

Usage::

    import sqlite3
    from src.db.paths import resolve_db_path
    from src.gamechanger.loaders.game_loader import GameLoader

    conn = sqlite3.connect(str(resolve_db_path()))
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = GameLoader(conn, owned_team_ref=team_ref)
    result = loader.load_payload(boxscore_dict, summary)
    print(result)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import NamedTuple

from src.db.game_merge import GameMergeError, merge_duplicate_game
from src.db.players import ensure_player_row
from src.db.reconcile_at_load import (
    PlayerLineBlock,
    retire_absent_player_lines,
    snapshot_prior_line_player_ids,
)
from src.db.teams import ensure_team_row_with_provenance
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team
from src.gamechanger.types import TeamRef
from src.gamechanger.url_parser import is_gc_uuid
from src.util.timezone import (
    derive_local_date,
    get_operating_timezone,
    resolve_timezone,
)

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

# In-band sentinel for "this game's venue-local calendar date is not
# determinable". ``games.game_date`` is ``TEXT NOT NULL`` and
# ``_derive_game_date`` is annotated ``-> str``, so there is no out-of-band way
# to say "unknown" at this seam.
#
# ⚠️ IT IS A DEDUP KEY, and that is the cost of using it. ``_find_duplicate_game``
# gates candidates on ``game_date = ?``, so every sentinel-dated game sharing a
# team pair is a dedup candidate for every other one. That is bounded (measured
# 2026-07-27: zero stored rows carry it, and zero of 1064 reachable schedule
# events lack a ``start_ts``) but it is real, and it lands hardest on
# repeat-opponent and doubleheader cases. Widening what routes here is a
# decision, not a detail.
_UNKNOWN_GAME_DATE = "1900-01-01"

# E-278-02, widened 2026-08-15. Two listings whose start instants fall within
# this window are ONE real game that GameChanger listed twice, never two games.
#
# ⚠️ THE BOUND IS FITTED, NOT PHYSICAL -- and the previous comment here claimed
# the opposite, so read this before restoring anything from it.
#
# ⚠️ TWO POPULATIONS USE THIS ONE CONSTANT AND THEIR MARGINS DIFFER. Say which
# one you mean; conflating them reads as a safety argument that was never made.
#   * SAME-PAIR (two rows naming the same unordered team pair): twins at or
#     below 600s, doubleheader floor 5400s, so the interval (600s, 5400s) is
#     entirely EMPTY, nothing physical selects a point inside it, and 1800s
#     carries a 3x margin on BOTH sides.
#   * DIVERGENCE (shared team on the same side, two different opponent rows):
#     see the WHY-1800 block below. Its largest admitted twin sits EXACTLY ON
#     the bound -- margin ZERO above. The 3x figures do NOT transfer.
# A fitted bound inherits exactly the risk the old comment named: the observed
# floor can shift.
#
# ⚠️ THE MINIMUM-GAME-DURATION ARGUMENT IS A CEILING, NOT A FLOOR GUARANTEE, and
# it must not be written back in as one. The argument -- "two genuine games
# sharing a team cannot both START within 30 minutes, because the first must
# finish first" -- has a surviving counterexample: this rule keys on
# ``start_time``, which is a RECORDED value, not an observed one (see
# ``_parse_instant``). A scorekeeper entering both halves of a doubleheader at
# nominal times, a suspended game resumed and re-stamped, or a forfeit all
# produce two genuine games whose RECORDED starts sit inside any window. The
# corpus proves the rest of that shape is real: it already holds a genuine
# doubleheader with an IDENTICAL per-team scoreline, and that pair WOULD be
# collapsed if its recorded gap were small. So the duration argument bounds real
# PLAY while the rule reads recorded TIMESTAMPS.
#
# WHY 1800 AND NOT 3600 -- the load-bearing justification is the corpus, and it
# is entirely repo-checkable. Measured 2026-08-15 against 2,303 stored games,
# in the DIVERGENCE population: the score-agreeing shared-team deltas are
# 0, 1800, 3600, 9000, 62400s. 1800s is the LARGEST bound admitting every delta
# that population classifies as a twin -- the 0s cluster, plus the 1800s pair
# rated a PROBABLE twin on 9-of-13 batting stat-tuple overlap -- while excluding
# the UNKNOWN 3600s pair (8-of-13 overlap, the same band, which is why it is
# unadjudicated rather than ruled out) and both known non-twins. Excluding 3600s
# is the fail-closed choice, not a confident one.
# ⚠️ The admitted twin at 1800s sits ON the bound: margin ZERO above it, 2x below
# to the excluded 3600s pair. Do not quote the same-pair 3x margins here.
#
# EXPOSURE, stated rather than argued away: this widens an EXISTING exposure by
# a factor, it does not create a new class. The byte-equality tiebreaker BELOW
# this rule collapses same-instant pairs with NO score check at all, so this
# rule is still narrower than behaviour the repo already ships -- it requires
# pairwise score agreement, same-side orientation and a bounded delta. The
# mitigation is implemented, not merely noted: every collapse logs a WARNING
# naming both start instants and the delta, so a wrong merge is auditable after
# the fact rather than silent.
#
# ⚠️ SCOPE: this is a NARROWING condition, never a trigger, and inverting that
# would be unsafe. Score agreement triggers; this only bounds it.
_SAME_LISTING_MAX_DELTA_SECONDS = 1800.0

# The opponent-divergence branch's OWN bound, deliberately NOT the same-pair
# window above. It requires IDENTICAL recorded start instants.
#
# ⚠️ THE 1800s WARRANT DOES NOT REACH THIS BRANCH, which is why the constants are
# separate (operator ruling, 2026-08-15, on a code-review finding). The
# mixed-identity trigger does not discriminate the way it reads: measured over
# EVERY mixed pair the corpus contains at ANY delta, the identity-bearing side is
# the LOADING TEAM ITSELF in 28 of 28 (26 at 0s, 1 at 1,800s, 1 at 3,600s) -- and
# the loading team carries a public_id by CONSTRUCTION, not because it is a
# distinct real opponent. ⚠️ The denominator is stated PER-DELTA deliberately: an
# "in-window" count moves when the window does, and this window narrowed to 0s
# after that measurement was first written down. So the trigger
# degenerates to "the other row's differing team is a bare stub", which is true
# of any team a boxscore named but nobody ever scouted -- including a genuinely
# DIFFERENT real team. Two real games then look identical to one double-listed
# game: tournament pool play against two opponents, or a program's varsity and
# JV both facing one opponent on one date. Neither has a corpus instance, and
# neither is excluded by anything in the gate.
#
# What survives that objection is the delta-0 case, and only it: the repo
# ALREADY collapses identical-instant pairs via the byte-equality tiebreaker
# below, with no score check at all, so requiring identical instants PLUS score
# agreement PLUS same-side orientation PLUS mixed identity is strictly narrower
# than shipped behaviour. At minutes apart there is no such precedent.
# 26 of the 27 twins the OLD 1,800s window would have admitted sit at exactly
# 0s, so narrowing to 0s costs exactly ONE pair -- the 1,800s probable twin, now
# an accepted residual beside the 3,600s unadjudicated one. (Naming the old
# window explicitly: "in-window" is ambiguous now that the window moved.)
#
# ⚠️ THIS IS EXPOSURE-MINIMIZATION, NOT EXPOSURE-ELIMINATION, and nobody may
# later read delta-0 as "safe". TWO REAL GAMES CAN SHARE A RECORDED START
# INSTANT. This module already proves it one paragraph up, against its own
# earlier claim: `start_time` is a RECORDED value, not an observed one, so a
# scorekeeper entering both halves of a doubleheader at nominal times, a
# resumed suspended game, or a forfeit all produce two genuine games at one
# stamp. Delta-0 shrinks the window the hazard needs; it does not close it.
#
# The asymmetry is what decides the direction, and it is not close: a WRONG
# MERGE hard-deletes a real game FOREVER, while a MISSED duplicate sits
# visibly in a report until someone widens the rule again. Fail CLOSED --
# when in doubt, refuse to collapse.
#
# Compared on PARSED instants, not bytes: "…21:00:00Z" and "…21:00:00.000Z" are
# the same instant, and `_listing_delta_seconds` fails CLOSED on either side
# being absent or unparseable.
_DIVERGENCE_MAX_DELTA_SECONDS = 0.0

# Which row wins an opponent-divergence collapse. PROMOTE = the canonical names
# the bare-name stub, so the incoming row survives and absorbs it (a DELETE).
# PRESERVE = the canonical already names the identity-bearing team, so the
# redirect must keep the canonical orientation rather than overwrite it.
_DIVERGENCE_PROMOTE = "promote"
_DIVERGENCE_PRESERVE = "preserve"


def _parse_instant(value: str | None) -> datetime | None:
    """Parse a GameChanger wire timestamp to an AWARE datetime, or ``None``.

    Deliberately local and deliberately narrow. It answers "how far apart are
    these two instants", which is a different question from
    ``derive_local_date``'s "what calendar date is this in that zone" -- and it
    could not reuse that seam even if it wanted to: that seam returns a
    ``"YYYY-MM-DD"`` STRING, and a sub-second delta is not computable from a
    calendar date. A delta is also zone-independent, since both operands are
    absolute instants, so that seam's E-278-04 contract of REFUSING on an
    unresolvable zone would be inherited for nothing -- silently disabling dedup
    for exactly the rows whose zone GameChanger spelled unusually.

    **The one thing it DOES inherit from that seam is naive-datetime
    normalization, and omitting it was a real defect.** A bare date
    (``"2026-07-25"``) or a naive datetime PARSES cleanly, so it is neither
    absent nor unparseable and no ``except ValueError`` can catch it -- and
    subtracting a naive datetime from an aware one raises ``TypeError``. That
    exception had no handler between here and ``ScoutingLoader``'s per-game
    loop, which has no ``try``/``except`` around ``load_payload``; since
    ``load_payload`` commits per game, it would have left earlier games
    committed and ABANDONED every remaining game in that team's scout.
    Unobserved on the wire today (GC renders ``...Z``) -- but this epic exists
    because an unobserved shape in a GameChanger field is not a proven-impossible
    one, and the cost here is an aborted crawl rather than a wrong answer.

    Returns:
        A timezone-AWARE ``datetime`` (naive input is read as UTC, mirroring
        ``derive_local_date``), or ``None`` when *value* is absent or will not
        parse. The return is aware unconditionally, so arithmetic on two of
        these cannot raise.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_same_listing_delta(start_a: str | None, start_b: str | None) -> bool:
    """True when two start instants are within :data:`_SAME_LISTING_MAX_DELTA_SECONDS`.

    Fails CLOSED: an absent or unparseable instant on either side returns False,
    leaving the caller on its pre-existing tiebreaker. Refusing to narrow costs
    a duplicate row that a later pass can still collapse; narrowing on a value we
    could not read would merge two games irreversibly.

    Byte-equal instants are inside the window, so this does not COMPETE with the
    exact-match tiebreaker below. ⚠️ It does NOT supersede it, and the difference
    matters because the wrong reading points at deleting the tiebreaker as
    redundant -- which would change behavior. The tiebreaker collapses byte-equal
    instants UNCONDITIONALLY, with no score check; the rule above gates on score
    agreement. So a byte-equal pair whose scores DISAGREE is collapsed only by
    the tiebreaker, and it still has to run.
    """
    delta = _listing_delta_seconds(start_a, start_b)
    return delta is not None and delta <= _SAME_LISTING_MAX_DELTA_SECONDS


def _listing_delta_seconds(start_a: str | None, start_b: str | None) -> float | None:
    """Absolute seconds between two start instants, or ``None`` if unreadable.

    Split out of :func:`_is_same_listing_delta` so a collapse can LOG the delta
    it acted on. The mitigation for a fitted bound is auditability: a WARNING
    naming both instants and their gap makes a wrong merge reviewable after the
    fact, and a boolean cannot carry that.
    """
    a = _parse_instant(start_a)
    b = _parse_instant(start_b)
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds())


class _DivergenceCandidate(NamedTuple):
    """One stored row that satisfies the whole opponent-divergence gate."""

    existing_id: str
    incoming_differing: int
    existing_differing: int
    existing_start: str | None
    delta_seconds: float
    incoming_bearing: bool


def _differing_team_ids(
    incoming_home: int,
    incoming_away: int,
    other_home: int,
    other_away: int,
) -> tuple[int, int] | None:
    """Name the two teams that DIFFER when both rows share exactly one side.

    Returns ``(incoming_differing, other_differing)`` when the two team pairs
    share one team on the SAME side, else ``None`` -- which covers both the
    exact same-pair match and the orientation-swapped match, neither of which
    is an opponent-divergence shape.

    Single-sourced deliberately. This comparison is the DETECTOR's candidate
    test and the ROUTER's classification at the redirect site, and the two
    outcomes are opposite and destructive: a detector that admits a shape the
    router maps to ``None`` files the game under the stub-headed row (the very
    outcome the promotion exists to prevent), while a router that promotes a
    pair the ordinary team-pair pass matched would hard-delete a ``games`` row.
    Two hand-written copies of a four-line comparison must not guard that.
    """
    if other_home == incoming_home and other_away == incoming_away:
        return None                       # exact team-pair match
    if other_home == incoming_home:
        return incoming_away, other_away
    if other_away == incoming_away:
        return incoming_home, other_home
    return None                           # orientation-swapped team-pair match


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


def _derive_game_date(summary: GameSummaryEntry) -> str:
    """Derive a game's venue-LOCAL calendar date from its summary.

    The SINGLE derivation shared by ``_load_boxscore_data`` (the dedup decision)
    and ``ScoutingLoader``'s schedule-count precompute (E-261-03a). Both MUST key
    on the identical date string or the schedule-count lookup would silently
    key-miss and disable the tolerant same-game signal (TN-4 finding E(b)).

    Four cases, in the order they are decided (E-278-04):

    1. **Full-day event** (``is_full_day``): ``start_time`` is a DATE MARKER, not
       a moment, so its date slice is taken RAW with no conversion. GameChanger
       encodes "a date but no start time" as an all-day calendar event -- midnight
       UTC, a 24-hour end, and a null timezone -- and localizing that marker
       shifts it BACK a day in every western-hemisphere zone (``2026-05-31`` ->
       ``2026-05-30``). This branch keys on ``is_full_day`` and nothing else: a
       null timezone correlates with it perfectly in the measured corpus but is a
       PROXY, and "starts at midnight UTC" is a far worse one (a 7pm US Central
       start IS midnight UTC -- measured, it over-selects by 25x).
    2. **Absent instant**: the ``_UNKNOWN_GAME_DATE`` sentinel.
    3. **Present but UNRESOLVABLE timezone**: the sentinel again, and this is the
       fail-closed direction (see below).
    4. **Otherwise**: the game's own timezone when present, else the operating-tz
       seam (bridged to its IANA name via ``.key`` -- ``derive_local_date`` takes
       a NAME, never a ``ZoneInfo``), falling back to the raw UTC date slice only
       when the instant itself is unparseable.

    **Why case 3 checks the zone here rather than leaning on the seam's return.**
    Making ``derive_local_date`` return ``None`` is a NO-OP at this site, and the
    two paths are identical BY CONSTRUCTION rather than by coincidence: when the
    zone lookup fails the datetime keeps the tzinfo it was PARSED with, and
    ``.date()`` on an aware datetime yields its own written wall-clock date --
    exactly what ``[:10]`` slices off the front of the string. So the old
    fail-open output and this function's unparseable-instant fallback are the
    same bytes, and routing an unresolvable zone into that fallback would leave
    every mis-dated row mis-dated. Resolving the zone FIRST is what separates the
    two, and it is why the branches above are ordered rather than collapsed.

    **The unresolvable case does not substitute a zone**, the operating zone
    included: that would satisfy "the date is not the UTC slice" while silently
    presenting an unverified guess as venue-local. A payload that supplied a zone
    we cannot resolve gets no date, not a different zone's date. Note the
    contrast with case 4's ABSENT timezone, which is a genuinely different
    situation -- no signal was given, so the documented operating-tz default
    applies.

    **The degradation is observable without reading logs**, and the honest way to
    say so is to separate two questions that a single query cannot answer at
    once. WHICH ROWS ARE UNDATED is exactly answerable. WHY each one is undated
    is not answerable from stored fields at all.

    **1. Every undated row, no false negatives**::

        SELECT game_id, start_time, timezone FROM games
         WHERE game_date = '1900-01-01'

    This is complete by construction: ``_UNKNOWN_GAME_DATE`` is the only value
    ANY of the three refusing branches returns -- a full-day event with no date
    marker, an absent instant, and an unresolvable zone -- and nothing else in
    the codebase writes that literal into ``game_date``. Every row whose
    venue-local date could not be determined is here, whatever refused it. **For AC-4b's purpose -- an
    operator noticing degradation without reading logs -- this is the signal**,
    and the ``timezone`` column on each row names the zone to investigate.

    **2. The subset a backfill can repair**::

         ... AND start_time IS NOT NULL

    Exactly right for THIS question, and for a reason outside this module:
    ``backfill_game_dates`` refuses every NULL-``start_time`` row before it
    examines anything else (its tier-3 guard), so a sentinel row without an
    instant is unreachable by repair no matter which zone the runtime later
    learns -- it needs a re-crawl. A sentinel row WITH an instant is genuinely
    re-derivable: once its zone resolves it takes tier 1, and the differ-only
    UPDATE guard replaces the sentinel.

    **3. Case 2 versus case 3 -- NOT determinable from the stored row.** Do not
    add a predicate that claims to split them; neither stored field does, and
    each fails in the opposite direction. Both escape routes are executed
    counterexamples, not analysis, and both are pinned by tests:

    - ``start_time IS NOT NULL`` **misses** a case-3 row.
      ``_build_games_index_from_data`` fills ``date_source_instant`` from
      ``start_ts or end_ts`` but sources ``start_time`` from ``start_ts``
      ALONE, so an ``end_ts``-only event has a truthy instant and a NULL
      ``start_time``; with an unresolvable zone it is case 3 and this predicate
      drops it.
    - ``timezone IS NOT NULL`` (even with a resolvability test) **admits** a
      case-2 row, because ``timezone`` is populated independently of
      ``start_ts`` -- an absent-instant payload can still carry a zone, and an
      unresolvable one passes the test.

    A third shape defeats any naive reading of either: ``ON CONFLICT`` sets
    ``game_date = excluded.game_date`` UNCONDITIONALLY while ``start_time`` is
    ``COALESCE(excluded.start_time, games.start_time)``, so a game loaded once
    WITH an instant and re-loaded WITHOUT one ends as a case-2 sentinel over a
    retained non-NULL ``start_time``.

    All of these live in the corpus region the story's Notes flag as
    real-but-unexercised (0 of 1064 events lack a ``start_ts``) -- and
    "unexercised" is not "dead". If the cause ever needs to be machine-readable,
    it has to be RECORDED at load, not inferred from the row afterwards.
    """
    if summary.is_full_day:
        # A date marker -- slice it, never localize it. Read it from
        # ``start_time`` (the raw ``start_ts``) and from NOWHERE else.
        #
        # ⚠️ THIS IS THE ONE PATH THAT DOES NOT USE ``date_source_instant``,
        # despite that being exactly what the field is named for -- so the
        # exception is called out rather than left to look like an oversight.
        # The reason is its FALLBACK, not its primary value: upstream fills it
        # from ``end_ts`` when ``start_ts`` is absent, and on a full-day event
        # ``end_ts`` is exactly 24 hours later, so its slice is TOMORROW. A
        # full-day event with no ``start_ts`` therefore has no marker we can
        # read, and gets the sentinel rather than a date that is off by one.
        # (Unexercised: zero of 1064 reachable events lack a ``start_ts``. Zero
        # observed is not unreachable, which is why it is handled rather than
        # assumed away.)
        return summary.start_time[:10] if summary.start_time else _UNKNOWN_GAME_DATE

    if not summary.date_source_instant:
        return _UNKNOWN_GAME_DATE

    if summary.timezone:
        if resolve_timezone(summary.timezone) is None:
            logger.warning(
                "Unresolvable timezone %r on game %s; storing the %r sentinel "
                "rather than a UTC-sliced date that would be wrong by a day. "
                "The row keeps this timezone; start_time=%r (re-derivable by "
                "backfill only if that is not None).",
                summary.timezone, summary.event_id, _UNKNOWN_GAME_DATE,
                summary.start_time,
            )
            return _UNKNOWN_GAME_DATE
        tz_name = summary.timezone
    else:
        tz_name = get_operating_timezone().key

    return (
        derive_local_date(summary.date_source_instant, tz_name)
        or summary.date_source_instant[:10]
    )


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
        date_source_instant: The instant ``_derive_game_date`` derives the
            game's calendar date from -- ISO 8601, always a string (possibly
            empty). ⚠️ **Despite the resemblance, this is NOT the same value as
            ``start_time``, and the difference is the fallback.** On the public
            scouting path ``_build_games_index_from_data`` fills BOTH from
            ``start_ts``, but this field falls back to ``end_ts`` and then to
            ``""`` while ``start_time`` takes ``start_ts`` ALONE and is ``None``
            without it. So an ``end_ts``-only event gives a truthy value here
            and ``None`` there. **Renamed in E-278-05.** Its former name
            was borrowed from the authenticated game-summaries endpoint's own
            field of that name (see
            ``docs/api/endpoints/get-teams-team_id-game-summaries.md``, where
            the GameChanger field still legitimately carries it -- THAT one is
            not renamed and must not be); our file-reading loader entry points
            for that endpoint died in E-256, so no live path has supplied a
            book-touch instant since. **That stale name cost real diagnostic
            time**: an investigation of a wrong ``game_date`` followed
            ``start_time``, which is not what the date derives from, and had to
            establish by execution that the fallback it suspected never fired
            (epic TN-1; IDEA-218 records the refuted hypothesis).
        start_time: ISO 8601 datetime string from schedule/public endpoint, or
            ``None``. The raw ``start_ts`` with NO fallback -- see
            ``date_source_instant`` above for why the two differ.
        timezone: IANA timezone identifier (e.g., ``America/Chicago``), or None.
        is_full_day: ``True`` when the source event is an all-day calendar entry
            (the scorekeeper recorded a date but no start time). Carried from the
            public games payload's ``is_full_day`` key because it changes how
            ``start_time`` MUST be read: on a full-day event that timestamp is a
            DATE MARKER at midnight UTC, not a real start instant, so converting
            it to a local date shifts it back a day. Defaults to ``False`` --
            a timed event, the overwhelmingly common case.
    """

    event_id: str
    game_stream_id: str
    home_away: str | None
    owning_team_score: int | None
    opponent_team_score: int | None
    opponent_id: str
    date_source_instant: str
    start_time: str | None = None
    timezone: str | None = None
    is_full_day: bool = False


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
        schedule_counts: Optional ``{(game_date, opponent_name): count}`` map of
            how many games the OWN crawl schedule has on each local date against
            each opponent (E-261-03a / TN-4). Precomputed upstream by
            ``ScoutingLoader`` because ``load_payload`` sees ONE summary at a time
            and cannot count the schedule itself. Enables the tolerant
            schedule-count same-game signal in ``_find_duplicate_game``; ``None``
            (the default) leaves that signal OFF -- direct callers get the
            legacy exact-match-only dedup behavior.
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        owned_team_ref: TeamRef,
        created_team_ids: set[int] | None = None,
        schedule_counts: dict[tuple[str, str], int] | None = None,
    ) -> None:
        self._db = db
        self._team_ref = owned_team_ref
        self._created_team_ids = created_team_ids
        self._schedule_counts = schedule_counts
        self._season_id, self._season_year = derive_season_id_for_team(
            db, owned_team_ref.id
        )
        # {stale_event_id: surviving_game_id} accumulated as a side-effect of
        # every dedup collapse (E-244; widened 2026-08-15). A key is any event
        # id that no longer resolves to a ``games`` row -- from a REDIRECT (the
        # incoming source id, nothing deleted) or from an identity-bearing
        # PROMOTION (the canonical row's id, that row having been merged away
        # and DELETED). GameLoader is constructed fresh per report run, so this
        # map is naturally scoped to one run (no reset). Exposed to the report
        # generator via LoadResult.redirect_map so the plays/spray stages file
        # rows under the surviving id.
        self.redirect_map: dict[str, str] = {}
        # Source event ids whose payload PARSED far enough to reach the
        # dedup/redirect + upsert stage this run. Distinct from "the fetch
        # succeeded": a boxscore can 200 with an unexpected shape, take an early
        # return in ``_load_boxscore_data``, and never record its redirect entry.
        # The game-grain reconcile's ``boxscores_complete`` must be computed from
        # THIS set -- keying it on the fetched set instead lets an unparseable
        # payload silently withdraw a canonical row's vouching while the health
        # guard still reads "complete", and the canonical game is then hard-
        # deleted (Fable review, E-267 closure).
        self.processed_event_ids: set[str] = set()
        # Teams whose ``team_rosters`` rows THIS run created or touched, recorded
        # as a side effect of ``_upsert_roster_jersey``. Same per-run
        # side-effect-set pattern as the two above, and naturally scoped for the
        # same reason: GameLoader is constructed fresh per report run.
        #
        # It exists because ``_load_team_stats`` runs for BOTH sides of every
        # boxscore, so this loader writes roster rows for the scouted team's
        # OPPONENTS as well -- while the dedup sweep in ScoutingLoader was scoped
        # to the scouted team alone, leaving every opponent's split identities
        # unmerged. League play is cyclic, so no generation order converges.
        # ScoutingLoader reads this to dedup every team it actually wrote.
        self.rostered_team_ids: set[int] = set()

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

        # A multi-envelope payload carries BOTH sides. If EITHER side could not
        # be named, the only way to proceed is to attribute envelopes by key
        # shape and insertion order -- which loads one team's stats under the
        # other's id. That misattribution is strictly worse than absence (it is
        # the ordering hole this ladder exists to close), so refuse the payload
        # and count the error rather than load a guess.
        #
        # The guard is deliberately SYMMETRIC. An unnamed OWN key is the more
        # damaging direction, not the lesser one: it files our own envelope
        # under the opponent's team id, so our report shows the other side's
        # numbers. Counting the error also keeps a discarded envelope
        # distinguishable from an opponent who never used GC scorekeeping,
        # which is the modal and entirely legitimate case.
        if len(raw) >= 2 and (own_key is None or opp_key is None):
            logger.error(
                "Boxscore for game %s carries %d team envelopes but the %s key "
                "could not be identified; refusing to attribute stats by key "
                "shape alone. (all_keys=%s)",
                summary.event_id, len(raw),
                "own-team" if own_key is None else "opponent",
                list(raw.keys()),
            )
            return LoadResult(errors=1)

        # Past both parse guards: this payload will reach the dedup/redirect and
        # upsert stage, so whatever vouching it owes (its own id, or a redirect
        # entry onto a canonical row) is about to be recorded. Keyed on the
        # SOURCE id, before the redirect rewrites ``summary.event_id`` below.
        self.processed_event_ids.add(summary.event_id)

        own_data = raw.get(own_key) if own_key else None
        opp_data = raw.get(opp_key) if opp_key else None

        # Resolve INTEGER PKs for home/away team rows.  The opponent ALWAYS
        # resolves to a DISTINCT team id -- by boxscore key/UUID, by name when
        # the opponent stat block is absent, or an "Unknown Opponent" sentinel
        # stub when truly unresolvable -- so a self-game (home == away) is never
        # produced (E-245-04 / TN-6).  ``opp_data`` is None whenever ``opp_key``
        # is None, and past the guard above that means a SINGLE-envelope
        # payload -- where it is truthful: the opponent was never scored on
        # GameChanger, so there are no per-player rows to load.  A multi-
        # envelope payload whose opponent key could not be named never reaches
        # here; it was refused above rather than loaded with its opponent
        # envelope silently dropped.
        own_team_id, opp_team_id = self._resolve_team_ids(
            summary, opp_key, opponent_name=opponent_name,
        )

        # Resolve home/away for games table.
        home_team_id, away_team_id, home_score, away_score = self._resolve_home_away(
            summary, own_team_id, opp_team_id
        )

        # Game date: the venue-LOCAL calendar date of the game's START
        # instant -- NOT of a "scoring instant", which is what this
        # comment said until E-278-05 and what the field's former name
        # implied. No live path carries a book-touch timestamp; see
        # ``GameSummaryEntry.date_source_instant`` for where the value
        # really comes from.
        # (CE-3 / E-253-04). Deriving it from the raw UTC prefix files an
        # evening game under the next UTC day, skewing rest math, the 7-day
        # window, and cross-perspective dedup at UTC midnight. Factored into the
        # shared ``_derive_game_date`` seam so ScoutingLoader's schedule-count
        # precompute keys on the IDENTICAL date (E-261-03a / TN-4 finding E(b)).
        game_date = _derive_game_date(summary)

        # Tolerant same-game signal context (E-261-03a / TN-4): how many games the
        # OWN crawl schedule has on this date against this opponent. Naturally
        # keyed by (date, opponent-NAME) upstream; resolved HERE where the name is
        # in hand, then passed to _find_duplicate_game as a plain count. Fail-safe:
        # a None opponent_name or a key-miss leaves the count None, which DECLINES
        # the tolerant signal (exact-match dedup only) rather than merging on
        # missing context (AC-6 / finding E(a)+(c)).
        incoming_schedule_count: int | None = None
        if self._schedule_counts is not None and opponent_name is not None:
            incoming_schedule_count = self._schedule_counts.get(
                (game_date, opponent_name)
            )

        # Pre-load dedup check: if a game already exists for this date and
        # team pair (in either home/away order), reuse the existing game_id
        # so all stat upserts merge into the canonical row.
        #
        # An UNKNOWN date is NOT a dedup key (E-278-04). ``_find_duplicate_game``
        # gates candidates on ``game_date = ?``, so without this guard every
        # sentinel-dated game sharing a team pair becomes a dedup candidate for
        # every other one -- and "neither game's date could be determined" is no
        # evidence whatsoever that they are the same game. Declining is the safe
        # direction, because the two failure modes are not symmetric: a missed
        # merge leaves an extra row that a later pass can still collapse, while a
        # wrong merge destroys one game's stats irreversibly. Reached by both
        # sentinel producers -- the absent instant (pre-existing) and the
        # unresolvable timezone (new here), which this guard stops from
        # colliding with each other as well as within themselves.
        canonical_id = None
        if game_date != _UNKNOWN_GAME_DATE:
            canonical_id = self._find_duplicate_game(
                summary.event_id, game_date,
                home_team_id, away_team_id, home_score, away_score,
                summary.start_time,
                incoming_schedule_count=incoming_schedule_count,
            )
        preserve_scores = False
        if canonical_id is not None:
            # Capture the ORIGINAL source event id BEFORE replace() rewrites
            # summary.event_id to the canonical value (E-261-03b AC-4 / finding
            # CR LOW-5). Both the redirect_map key and the twin-existence check
            # below MUST use this captured id, not the post-replace canonical.
            source_event_id = summary.event_id

            # Identity-bearing promotion (2026-08-15). On an opponent-divergence
            # collapse the surviving row must name the opponent carrying a
            # ``public_id``/``gc_uuid``, never a bare-name stub -- otherwise which
            # identity survives is decided by LOAD ORDER, which the regenerate
            # does not control. When the canonical is the stub-headed row we
            # therefore do NOT redirect into it; the incoming row is written
            # under its own event id and the stub-headed row is merged into it.
            #
            # ⚠️ THIS IS THE CHUNK'S DESTRUCTIVE SEAM: that merge re-points five
            # child tables and HARD-DELETES a ``games`` row.
            divergence = (
                self._classify_divergence_collapse(
                    canonical_id, home_team_id, away_team_id
                )
                if source_event_id != canonical_id
                else None
            )
            if divergence == _DIVERGENCE_PROMOTE:
                return self._promote_over_stub_headed_row(
                    summary, canonical_id, game_date,
                    home_team_id, away_team_id, home_score, away_score,
                    own_data, own_team_id, opp_data, opp_team_id,
                )

            # Score ownership (E-261-03a / TN-1): a CROSS-perspective redirect must
            # NOT overwrite the canonical row's first-loaded scores -- once the
            # tolerant signal makes redirects fire on DISAGREEING scores,
            # last-writer-wins would flap the canonical scores on every report
            # regeneration. Cross-perspective == the incoming perspective is not
            # yet among the canonical row's recorded perspectives. A SAME-
            # perspective reload keeps preserve_scores False so a legitimate
            # scorekeeper correction on re-scout still updates.
            #
            # The FIRST disjunct is the divergence rule: when the canonical
            # already names the identity-bearing opponent, this redirect must
            # not rewrite its orientation tuple -- the SAME-perspective case
            # would otherwise leave this False and bury that identity under the
            # incoming stub. Scores are not at stake either way; the divergence
            # gate already forced them to agree. It short-circuits, so the
            # perspective read below does not run on that path.
            preserve_scores = (
                divergence == _DIVERGENCE_PRESERVE
                or not self._game_perspective_recorded(
                    canonical_id, self._team_ref.id
                )
            )
            logger.info(
                "Dedup: redirecting game %s → %s (same date %s, same teams)",
                source_event_id, canonical_id, game_date,
            )
            # Record the redirect keyed by the SOURCE event id, so the generator's
            # plays/spray stages file rows under the canonical id (E-244 TN-2).
            self.redirect_map[source_event_id] = canonical_id
            summary = replace(summary, event_id=canonical_id)

            # In-pipeline twin merge (E-261-03b, completes Defect A). If a games
            # row ALREADY exists under the ORIGINAL source event id -- a
            # historical un-merged twin an earlier dedup miss left behind -- merge
            # it into the canonical row BEFORE the upsert so the pair collapses to
            # one row (self-healing on regeneration). The common fresh-redirect
            # case (source event never persisted) skips this: no source row, no
            # merge, unchanged behavior.
            if source_event_id != canonical_id and self._game_row_exists(
                source_event_id
            ):
                merged = self._merge_twin_or_rollback(source_event_id, canonical_id)
                if merged is not None:
                    # A sqlite3.Error during the merge already rolled back and
                    # returned errors=1 -- do not proceed with the upsert.
                    return merged

        return self._upsert_game_and_stats(
            summary, game_date,
            home_team_id, away_team_id, home_score, away_score,
            own_data, own_team_id, opp_data, opp_team_id,
            preserve_scores=preserve_scores,
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
        2. By NAME (``opponent_name``) when the boxscore carries no opponent
           stat block -- that opponent never used GC scorekeeping, so there are
           simply no per-player stat rows to load (truthful, not fabricated).
           A multi-envelope payload whose opponent key was PRESENT but could
           not be classified does NOT reach here: ``_load_boxscore_data``
           refuses it as an error, so a discarded envelope is never mistaken
           for an opponent who was never scored.
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
        preserve_scores: bool = False,
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
            preserve_scores: When True (a CROSS-perspective redirect), the game
                upsert keeps the canonical row's existing orientation tuple
                (home/away team-ids AND scores together) instead of overwriting
                them (E-268-01 / TN-1, extending E-261-03a
                first-loaded-perspective-wins).

        Returns:
            ``LoadResult`` for this game.
        """
        # PLAYER-LINE CAPTURE ANCHOR (E-276-01). The health gate's protected
        # population must be read BEFORE any of this run's writes to this game's
        # player-line delete scope -- reading it at retire time returns
        # ``old | fresh``, so every row we just wrote lands on both sides of the
        # floor ratio and relaxes it by half a row. At a full id churn the gate
        # then reads a comfortable 9-of-18 -- 9 stale lines plus the 9 just
        # written, clearing the floor at exact equality -- and hard-deletes all
        # nine live lines.
        #
        # This is the earliest correct point and it CANNOT be hoisted out of the
        # per-game loop: the set keys on the CANONICAL game id, and that id does
        # not exist until ``_load_boxscore_data`` has resolved the duplicate,
        # recorded the redirect and rebound ``summary.event_id`` -- which it has
        # done by the time this method is entered. A whole-run pre-capture would
        # have to guess ids that do not yet exist.
        #
        # Fails CLOSED: without the snapshot the gate has no evidence, and an
        # empty one would fail OPEN via the vacuous-permit rule, so a read error
        # aborts this game's load rather than proceeding without it.
        perspective_team_id = self._team_ref.id
        try:
            prior_snapshots = snapshot_prior_line_player_ids(
                self._db,
                game_id=summary.event_id,
                perspective_team_id=perspective_team_id,
                team_ids=(own_team_id, opp_team_id),
            )
        except sqlite3.Error as exc:
            logger.error(
                "Failed to capture the pre-upsert player-line snapshot for game "
                "%s (perspective %s): %s; skipping this game rather than "
                "reconciling it against no evidence.",
                summary.event_id, perspective_team_id, exc,
            )
            return LoadResult(errors=1)

        try:
            self._upsert_game(
                summary.event_id, game_date,
                home_team_id, away_team_id, home_score, away_score,
                summary.game_stream_id,
                start_time=summary.start_time,
                timezone=summary.timezone,
                preserve_scores=preserve_scores,
            )
        except (sqlite3.Error, ValueError) as exc:
            # ValueError = the _upsert_game home != away invariant guard
            # (E-245-04 / TN-6) refusing to write a self-game.
            logger.error("Failed to upsert game %s: %s", summary.event_id, exc)
            return LoadResult(errors=1)

        # Record which perspective loaded this game.
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

        # Player-line reconcile (E-267-03): retire stat rows for players the
        # fresh boxscore no longer lists. Runs HERE -- inside the per-game load,
        # on RAW payload ids -- which is what puts it before ScoutingLoader's
        # dedup_team_players sweep (TN-10 risk 2). That ordering is structural,
        # not incidental: dedup MERGES player_ids, so a reconcile running after
        # it would diff canonical prior ids against raw payload ids, mark the
        # freshly-merged canonical "absent", and delete a live line.
        result.errors += self._retire_absent_player_lines(
            summary.event_id, perspective_team_id,
            own_data, own_team_id, opp_data, opp_team_id,
            prior_snapshots=prior_snapshots,
        )

        result.loaded += 1  # count the game itself
        return result

    # ------------------------------------------------------------------
    # Player-line reconcile (E-267-03)
    # ------------------------------------------------------------------

    @staticmethod
    def _payload_block(
        team_data: dict | None, team_id: int
    ) -> PlayerLineBlock | None:
        """Build the reconcile's view of ONE team block, or None if absent.

        Per-block, deliberately: ``_load_team_stats`` writes own AND opponent
        rows under the SAME ``perspective_team_id``, distinguished only by
        ``team_id``. Unioning the two blocks behind a single "populated" flag
        would let a half-populated payload (own with stats, opponent with
        ``stats: []``) authorize retiring the empty side's live rows -- see the
        worked example in :func:`retire_absent_player_lines`.

        ``populated`` is True only when a lineup/pitching group in THIS block
        carried at least one per-player stat row -- the TN-11 "POPULATED 200"
        test. The MODAL scored-but-empty block has both categories present with
        ``stats: []``, yielding False and therefore retiring nothing.
        """
        if not team_data:
            return None
        batting: set[str] = set()
        pitching: set[str] = set()
        populated = False
        for group in team_data.get("groups") or []:
            category = group.get("category")
            if category == "lineup":
                target = batting
            elif category == "pitching":
                target = pitching
            else:
                continue
            rows = group.get("stats") or []
            if rows:
                populated = True
            for stat_row in rows:
                player_id = stat_row.get("player_id")
                if player_id:
                    target.add(player_id)
        return PlayerLineBlock(
            team_id=team_id,
            batting_player_ids=frozenset(batting),
            pitching_player_ids=frozenset(pitching),
            populated=populated,
        )

    def _retire_absent_player_lines(
        self,
        game_id: str,
        perspective_team_id: int,
        own_data: dict | None,
        own_team_id: int,
        opp_data: dict | None,
        opp_team_id: int,
        *,
        prior_snapshots: dict[tuple[str, int], frozenset[str]],
    ) -> int:
        """Retire stale per-player stat rows for this game + perspective.

        ``prior_snapshots`` is the pre-upsert protected population captured at
        the anchor in :meth:`_upsert_game_and_stats` (E-276-01). It is required
        and keyword-only: the parameter's whole value is its TIMING, and a
        positional slot on a six-argument call is where a wrong value gets
        passed silently.

        Returns the ``LoadResult.errors`` increment (1 if the reconcile itself
        failed, else 0). A reconcile failure must not abort the game's load --
        the stat rows are already written and correct; only the cleanup pass
        failed -- so ANY exception is counted and logged rather than raised
        (matching the breadth of E-267-02's reconcile hook: a ``TypeError`` in
        id collection would otherwise propagate and discard the good load, the
        opposite of this method's whole intent).

        No rollback here, deliberately -- and the asymmetry with E-267-02's
        game-grain hook is intentional, not an omission. There, a partial retire
        left ORPHANED CHILD ROWS behind a surviving ``games`` row (an
        inconsistent shape), so the partial work had to be undone. Here every
        DELETE is an independent leaf row: a mid-loop failure leaves some stale
        lines retired and some not, which is simply less-complete cleanup of the
        same kind, and the next re-scout retries the remainder. Rolling back
        would additionally discard the freshly-loaded stat rows sharing this
        uncommitted transaction -- strictly worse than a partial cleanup.
        """
        blocks = [
            block
            for block in (
                self._payload_block(own_data, own_team_id),
                self._payload_block(opp_data, opp_team_id),
            )
            if block is not None
        ]
        try:
            retired = retire_absent_player_lines(
                self._db,
                game_id=game_id,
                perspective_team_id=perspective_team_id,
                blocks=blocks,
                prior_snapshots=prior_snapshots,
            )
            if retired.retired or retired.refusals or retired.uncovered_team_ids:
                logger.info(
                    "Player-line reconcile for game %s (perspective %s): "
                    "retired=%d across %d block-table(s), refused=%d, "
                    "uncovered team(s)=%s",
                    game_id, perspective_team_id,
                    retired.total_retired, len(retired.retired),
                    len(retired.refusals),
                    retired.uncovered_team_ids or "none",
                )
        except Exception:  # noqa: BLE001 -- cleanup must never lose a good load
            logger.error(
                "Player-line reconcile failed for game %s (perspective %s); "
                "the loaded stats are unaffected.",
                game_id, perspective_team_id, exc_info=True,
            )
            return 1
        return 0

    def _detect_team_keys(self, raw: dict) -> tuple[str | None, str | None]:
        """Identify the own-team key and opponent key in a boxscore response.

        Classification is IDENTITY-based, not shape-based.  A key is a
        ``public_id`` slug or a UUID, and the form does NOT mark which side it
        is -- both keys are slugs on ~10% of payloads (14 of 140, measured
        2026-08-03), and what DECIDES the form is not established.  The older
        "our team is the slug, the opponent is the UUID" inference therefore
        produced ``opp_key = None`` whenever the opponent's key was also a
        slug, silently discarding that team's entire batting and pitching
        envelope.

        Ladder, in order:

        1. A key equal to our ``public_id`` (case-sensitive, as GC emits it) is
           the own key.
        2. Otherwise a key equal to our ``gc_uuid`` (case-insensitive) is the
           own key.
        3. Once one key is identified, any OTHER key is the opponent, whatever
           its shape -- so a 2-key payload never yields ``opp_key = None``.
        4. Only when neither identifier resolves does shape inference run, and
           it logs a WARNING when it fires.

        Identity also makes JSON insertion order irrelevant.  The former
        ``slug_keys[0]`` pick selected by serialization order, so an all-slug
        payload serialized opponent-first would have loaded the opponent's
        stats as ours -- misattribution, strictly worse than absence.

        Args:
            raw: Top-level boxscore dict (keys are team identifiers).

        Returns:
            Tuple of ``(own_key, opp_key)``.  Either may be ``None`` if not found.
        """
        keys = list(raw.keys())
        own_key: str | None = None

        # Rung 1: exact public_id match.
        own_public_id = self._team_ref.public_id
        if own_public_id:
            own_key = next((k for k in keys if k == own_public_id), None)

        # Rung 2: gc_uuid match, compared CASE-FOLDED.  Every gc_uuid observed
        # to date is lower-case, so the fold is defensive rather than known to
        # be required -- it is kept because a stored/emitted casing difference
        # would otherwise drop to rung 4 and SWAP own for opponent silently.
        # Do not "simplify" it to rung 1's exact compare; a test pins the fold.
        if own_key is None:
            owned_gc_uuid = self._team_ref.gc_uuid
            if owned_gc_uuid:
                folded = owned_gc_uuid.lower()
                own_key = next((k for k in keys if k.lower() == folded), None)

        # Rung 3: the opponent is whatever else is in the payload.  The endpoint
        # contract is exactly 2 keys; on a hypothetical 3+-key payload this takes
        # the first other key and the rest are dropped, which the guard in
        # _load_boxscore_data cannot catch (both keys come back non-None).
        opp_key: str | None = None
        if own_key is not None:
            opp_key = next((k for k in keys if k != own_key), None)
        elif keys:
            # Rung 4: neither identifier resolved -- fall back to shape, which
            # is a guess and is logged as one.  ``is_gc_uuid`` decides own-vs-
            # opponent HERE and nowhere else, so its anchoring and IGNORECASE
            # are load-bearing on this path only.  An EMPTY payload is not a
            # fallback -- there is nothing to infer from, and the caller logs
            # its own error -- so it skips the warning rather than raising a
            # second alarm for one benign well-formed-but-empty 200.
            uuid_keys = [k for k in keys if is_gc_uuid(k)]
            slug_keys = [k for k in keys if not is_gc_uuid(k)]
            own_key = slug_keys[0] if slug_keys else None
            opp_key = uuid_keys[0] if uuid_keys else None
            logger.warning(
                "Boxscore key detection fell back to SHAPE inference: neither "
                "public_id=%s nor gc_uuid=%s matched any envelope key. "
                "own_key=%s opp_key=%s (all_keys=%s)",
                own_public_id, self._team_ref.gc_uuid, own_key, opp_key, keys,
            )

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
        incoming_schedule_count: int | None = None,
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
            incoming_schedule_count: How many games the OWN crawl schedule has on
                this date against this opponent (E-261-03a / TN-4). ``None`` (the
                default -- direct callers, or an unresolved opponent) leaves the
                tolerant schedule-count signal OFF, preserving the legacy
                exact-match-only dedup. ``1`` with exactly one candidate row fires
                the tolerant same-game guard (below); ``>= 2`` is a doubleheader
                in the own schedule and NEVER collapses via the guard.

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

        # NOTE: an EMPTY ``rows`` deliberately falls through rather than
        # returning early. The tolerant guard below cannot fire on an empty set
        # and the candidate loop cannot execute, so control reaches the single
        # divergence call at the end of this method -- one call site, not two.
        # Uniform tolerant same-game guard (E-261-03a / TN-4, findings B + E).
        # PRIMARY schedule-count signal, applied PERSPECTIVE-AGNOSTICALLY across
        # the whole candidate set (NOT only the cross-perspective sub-branch
        # below). When the OWN crawl schedule shows exactly ONE game vs this pair
        # on this date AND the DB holds exactly ONE candidate row, they are the
        # same real game regardless of a score / start_time disagreement or which
        # perspective loaded the candidate -- a real doubleheader would appear
        # TWICE in the own schedule (incoming_schedule_count >= 2) and is never
        # collapsed here. This is the ONLY standalone merge trigger; it DEFAULTS
        # OFF when no count context is supplied (``incoming_schedule_count`` is
        # None), preserving exact-match-only dedup for direct callers (SE-5b: the
        # line-598 test supplies no count, so an 11-1 vs 10-1 pair still does not
        # dedup). Placing it BEFORE the per-candidate loop also closes finding B:
        # after a twin merge the canonical row carries the own perspective, so the
        # next regeneration re-loads via the SAME-perspective branch -- which has
        # the exact-score blindness -- and would re-insert a duplicate every run
        # without this perspective-agnostic guard.
        if incoming_schedule_count == 1 and len(rows) == 1:
            existing_id = rows[0][0]
            existing_home_score = rows[0][3]
            existing_away_score = rows[0][4]
            if (home_score, away_score) != (existing_home_score, existing_away_score):
                logger.warning(
                    "Tolerant same-game dedup (E-261-03a): redirecting %s → %s on "
                    "%s. Scores DISAGREE across perspectives (incoming %s-%s vs "
                    "canonical %s-%s); own schedule-count=1 and a single candidate "
                    "confirm the same real game. Canonical scores are kept "
                    "(first-loaded perspective wins).",
                    game_id, existing_id, game_date,
                    home_score, away_score,
                    existing_home_score, existing_away_score,
                )
            return existing_id

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

            # E-278-02, widened 2026-08-15: GameChanger double-lists ONE real
            # game inside a single team's own schedule under two distinct event
            # ids. The observed gaps are 0.96s, 300s and 600s -- the rule was
            # calibrated on the sub-second pair and MISSED the minutes-apart
            # ones, which is why the window is now
            # ``_SAME_LISTING_MAX_DELTA_SECONDS`` = 1800s and NOT sub-second.
            # Both listings share a perspective, so the byte-equality
            # tiebreaker below finds their start_times unequal and files them as
            # a doubleheader -- inserting a second row and double-counting the
            # game in season aggregates.
            #
            # SCORE AGREEMENT IS THE TRIGGER; the delta bound only NARROWS
            # it. Never invert that. A delta-triggered rule would be unsafe
            # corpus-wide (three other near-zero pairs exist), and a
            # score-only rule is unsafe on its own because two genuine
            # doubleheader games can share a scoreline.
            #
            # Scores are compared PAIRWISE, never by total: 11-1 and 10-2 both
            # total 12 and are plainly different games. This is the same trap
            # the cross-perspective branch above calls out, and the score-total
            # fallback further down still carries it for the no-start_time case.
            #
            # ⚠️ What this rule must NOT consult, each ruled out on evidence:
            #   * `plays` counts (AC-8) -- both rows have ZERO at first load, so
            #     `0 == 0` reads as agreement for EVERY pair, leaving scores
            #     alone to decide. That is the destructive direction. On
            #     re-scout it is 0-vs-58 and never agrees, so the duplicate
            #     would persist forever instead. Both directions fail.
            #   * `end_ts` -- MEASURED non-discriminator: the real pair's end
            #     instants are TWO HOURS apart (a 1-hour event vs a 3-hour
            #     one), so any equality rule on it misses the very duplicate
            #     this exists to catch. It is not exposed here in any case.
            #   * `home_away` -- necessarily equal for two listings sharing a
            #     perspective, so it cannot separate duplicate from doubleheader.
            #   * player line-set equality -- the two real rows carry 18 vs 10
            #     batting and 4 vs 1 pitching rows despite identical scores, so
            #     an equality test would not fire on them.
            #
            # AC-9 VERDICT (E-278-02): no corroborator is available at this
            # decision point -- all four candidates above are rejected on the
            # measurements cited, not on taste -- so score agreement narrowed by
            # the delta bound, scoped to this branch, is judged SUFFICIENT.
            # ⚠️ That verdict was reached when the bound was 1.0s. The bound is
            # now 1800s, which WIDENS the residual below by the same factor;
            # read the constant's comment for the fitted-bound warrant rather
            # than inferring safety from this paragraph.
            #
            # RESIDUAL RISK, recorded because a verdict without one is not a
            # verdict: a genuine doubleheader whose two games carry identical
            # per-team scores AND recorded starts within the bound would be
            # wrongly collapsed. The physical-impossibility defence this
            # paragraph used to lean on is RETIRED (see
            # _SAME_LISTING_MAX_DELTA_SECONDS): `start_time` is a RECORDED
            # value, not an observed one, so a scorekeeper entering both games
            # at nominal times is the way it happens, and the corpus already
            # holds a genuine doubleheader with an IDENTICAL scoreline. That
            # case already collapses today via the byte-equality tiebreaker
            # below, which applies no score check at all -- so this rule adds a
            # score gate the tiebreaker lacks, while widening the window from 0s
            # to 1800s. It is NOT uniformly narrower than the path it sits
            # above; it is narrower on scores and wider on time.
            have_both_score_pairs = (
                home_score is not None
                and away_score is not None
                and existing_home_score is not None
                and existing_away_score is not None
            )
            if (
                have_both_score_pairs
                and (home_score, away_score)
                == (existing_home_score, existing_away_score)
                and _is_same_listing_delta(start_time, existing_start_time)
            ):
                # Logged UNCONDITIONALLY, including the byte-equal case. The
                # bound is fitted (see _SAME_LISTING_MAX_DELTA_SECONDS), so
                # every collapse this rule performs must be auditable after the
                # fact; a collapse that logs nothing is exactly the one nobody
                # can review.
                logger.warning(
                    "Same-perspective double-listing: game %s → %s on %s. "
                    "GameChanger listed one real game twice under distinct "
                    "event ids (start times %s vs %s, delta %ss, bound %.1fs); "
                    "per-team scores agree (%s-%s). Collapsing to one row.",
                    game_id, existing_id, game_date,
                    start_time, existing_start_time,
                    _listing_delta_seconds(start_time, existing_start_time),
                    _SAME_LISTING_MAX_DELTA_SECONDS,
                    home_score, away_score,
                )
                return existing_id

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

        # The team-pair pass produced no usable candidate -- it either found
        # none at all, or found some and ruled every one of them out.
        # The divergence pass asks a DIFFERENT question -- is one of these two
        # opponent team ROWS a stand-in for the other's real team? -- so it
        # still runs. It is a separate query for exactly the reason the
        # tolerant guard above is untouched: that guard's meaning depends on
        # ``len(rows)`` counting TEAM-PAIR candidates, and widening the first
        # query would silently change it.
        return self._find_divergence_duplicate_game(
            game_id, game_date,
            home_team_id, away_team_id, home_score, away_score, start_time,
        )

    # ------------------------------------------------------------------
    # Opponent-identity divergence pass (2026-08-15)
    # ------------------------------------------------------------------

    def _team_name(self, team_id: int) -> str | None:
        """The ``teams.name`` for this id, or ``None`` if the row is gone."""
        row = self._db.execute(
            "SELECT name FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        return row[0] if row else None

    def _team_is_identity_bearing(self, team_id: int) -> bool:
        """True when this ``teams`` row carries a GameChanger identity.

        Identity means a non-NULL ``gc_uuid`` OR ``public_id``. A bare-name stub
        carries neither: ``_ensure_team_row`` always passes ``gc_uuid=None``, so
        a team row this loader CREATES is never identity-bearing. An
        identity-bearing opponent row exists only because some other path -- a
        scout of that team in its own right -- created it.
        """
        return (
            self._db.execute(
                "SELECT 1 FROM teams WHERE id = ? "
                "AND (gc_uuid IS NOT NULL OR public_id IS NOT NULL)",
                (team_id,),
            ).fetchone()
            is not None
        )

    def _find_divergence_duplicate_game(
        self,
        game_id: str,
        game_date: str,
        home_team_id: int,
        away_team_id: int,
        home_score: int | None,
        away_score: int | None,
        start_time: str | None,
    ) -> str | None:
        """Second dedup pass: one real game filed under two OPPONENT team rows.

        GameChanger's second double-listing shape is not a repeated event id --
        it is one real game whose two rows name two DIFFERENT ``teams`` rows for
        one real opponent (typically the opponent's own identity-bearing row on
        one side, and a bare-name stub a boxscore created on the other). The
        natural key ``{home, away}`` structurally cannot match those, which is
        why the team-pair pass above must run first and come back empty-handed.

        ⚠️ THE SHARED TEAM IS STRUCTURAL, NOT "THE PERSPECTIVE TEAM". It is
        whichever team both rows carry on the SAME side; the DIFFERING team may
        be this load's opponent OR its own team, depending on which perspective
        is being loaded. Keying on the perspective team instead would fire in
        only one of the two load orders -- measured 2026-08-15, in all 26
        in-window corpus pairs the shared team is a perspective of exactly one
        row, uniformly the stub-headed one -- and the regenerate does not
        control load order, so the collapse must be order-independent.

        Gate, ALL required (each narrowing, none of them a trigger on its own):

        * pairwise score agreement, the TRIGGER (never by total: 11-1 and 10-2
          both total 12 and are plainly different games);
        * IDENTICAL recorded start instants -- :data:`_DIVERGENCE_MAX_DELTA_SECONDS`,
          NOT the same-pair window, and read that constant's comment before
          widening it. Fails CLOSED on an absent or unparseable instant, and it
          does NOT make the branch safe: two real games can share a recorded
          stamp. It minimizes the exposure, it does not remove it;
        * MIXED opponent identity -- exactly ONE of the two differing teams
          carries a GC identity. Both identity-bearing REFUSES and both stubs
          REFUSES.

        The mixed-identity condition is a TRIGGER, not a survivor tie-break.
        Measured over all 31 score-agreeing shared-team pairs (2026-08-15): both
        known NON-twins are the ONLY both-identity-bearing pairs, and every
        in-window twin is mixed. Refusing on both-identity costs 0 in-window
        pairs; refusing on both-stub costs exactly 1, and that loss is taken.
        ⚠️ ITS MECHANISM ARGUMENT IS WEAKER THAN IT READS, and the correction
        matters more than the original claim. The argument was: a stub stands in
        for a real opponent, so two rows BOTH carrying a GC identity are more
        likely two genuinely different opponents. But measured 2026-08-15 over
        EVERY mixed pair the corpus holds at ANY delta, the identity-bearing side
        is the LOADING TEAM ITSELF in 28 of 28 (26 at 0s, 1 at 1,800s, 1 at
        3,600s) -- and a loading team carries a public_id by
        CONSTRUCTION, not because it is a distinct real opponent. So on this
        population the test degenerates to "the other row's differing team is a
        bare stub", which is true of any team a boxscore named but nobody
        scouted. Honest bound: n=2 on the both-identity side, and the mechanism
        does not do the work it appears to. It is a fail-closed narrowing that
        removes an unevidenced destructive branch, NOT a validated
        discriminator -- never re-read it as "both-identity proves a
        doubleheader", and never treat it as the thing keeping two real games
        apart. That job belongs to the identical-instant requirement above, and
        even that only minimizes the exposure.

        AMBIGUITY REFUSES. If two or more rows satisfy the whole gate, none is
        chosen -- an arbitrary pick can hard-delete the wrong game on the
        promotion path. Costs zero collapses on the measured corpus (max
        candidate count 1), so it is a free fail-closed guard.

        Orientation-flipped pairs are deliberately NOT candidates: this branch
        has the weakest identity anchor, and on a flipped pair a raw
        home-to-home score comparison pits the shared team's score against its
        opponent's, so a "match" there can be an artifact.

        Returns:
            The existing ``game_id`` to collapse onto, or ``None``.
        """
        # Score agreement is the TRIGGER, so a missing score on either side is
        # not a near-miss -- there is nothing to trigger on. Refuse before
        # querying rather than falling through to a delta-only rule.
        if home_score is None or away_score is None:
            return None

        rows = self._db.execute(
            """
            SELECT game_id, home_team_id, away_team_id, start_time
            FROM games
            WHERE game_date = ?
              AND status = 'completed'
              AND game_id != ?
              AND home_score = ?
              AND away_score = ?
              AND (
                -- Shared team on the SAME side. ⚠️ This is guard ONE of TWO:
                -- ``_differing_team_ids`` independently rejects an
                -- orientation-swapped pair, so neither is dead code and
                -- removing either alone leaves the property standing (proven by
                -- mutation -- only removing BOTH lets a flipped pair collapse).
                -- Deliberate defence in depth on a branch that can delete a row.
                (home_team_id = ? AND away_team_id != ?)
                OR (away_team_id = ? AND home_team_id != ?)
              )
            ORDER BY start_time ASC NULLS LAST
            """,
            (game_date, game_id, home_score, away_score,
             home_team_id, away_team_id,
             away_team_id, home_team_id),
        ).fetchall()

        # Collect ALL qualifying candidates before choosing, rather than
        # returning the first. See the ambiguity refusal below -- picking the
        # first would be an ARBITRARY choice on a path that can delete a row.
        qualifying: list[_DivergenceCandidate] = []
        for existing_id, existing_home, existing_away, existing_start in rows:
            # Which team is shared, and therefore which pair DIFFERS. The SQL
            # already guarantees exactly one side matches; routing through the
            # shared helper keeps the detector and the router from drifting.
            differing = _differing_team_ids(
                home_team_id, away_team_id, existing_home, existing_away,
            )
            if differing is None:
                continue
            incoming_differing, existing_differing = differing

            # NOT ``_is_same_listing_delta`` -- this branch carries its own,
            # much tighter bound (see _DIVERGENCE_MAX_DELTA_SECONDS). Fails
            # CLOSED: an absent or unparseable instant on either side yields
            # None and refuses.
            delta = _listing_delta_seconds(start_time, existing_start)
            if delta is None or delta > _DIVERGENCE_MAX_DELTA_SECONDS:
                continue

            # ⚠️ THE SENTINEL IS NOT A STUB FOR ONE REAL OPPONENT -- it is the
            # SHARED catch-all every unresolvable opponent name-dedups onto
            # (``_resolve_team_ids``), and it can never be identity-bearing
            # because ``_ensure_team_row`` passes ``gc_uuid=None``. So it reads
            # as "the stub" against ANY known opponent, which would let a game
            # against a genuinely different unresolvable opponent collapse into
            # -- and on the promote branch DELETE -- a game against a known one.
            # Refusing costs ZERO on the live corpus (measured 2026-08-15: zero
            # teams carry the sentinel name at all), so it is free.
            if _UNKNOWN_OPPONENT_NAME in (
                self._team_name(incoming_differing),
                self._team_name(existing_differing),
            ):
                logger.info(
                    "Opponent-divergence candidate %s / %s on %s REFUSED: one "
                    "side is the shared %r sentinel, which stands in for every "
                    "unresolvable opponent and cannot evidence one real team.",
                    game_id, existing_id, game_date, _UNKNOWN_OPPONENT_NAME,
                )
                continue

            incoming_bearing = self._team_is_identity_bearing(incoming_differing)
            existing_bearing = self._team_is_identity_bearing(existing_differing)
            if incoming_bearing == existing_bearing:
                logger.info(
                    "Opponent-divergence candidate %s / %s on %s REFUSED: teams "
                    "%d and %d are %s, and this branch requires exactly one "
                    "identity-bearing side.",
                    game_id, existing_id, game_date,
                    incoming_differing, existing_differing,
                    "both identity-bearing" if incoming_bearing else "both stubs",
                )
                continue

            qualifying.append(_DivergenceCandidate(
                existing_id, incoming_differing, existing_differing,
                existing_start, delta, incoming_bearing,
            ))

        if not qualifying:
            return None

        # ⚠️ AMBIGUITY REFUSAL. Two or more rows satisfying the whole gate is not
        # a licence to pick one -- the choice would be arbitrary, and on the
        # promotion path the loser's ``games`` row is HARD-DELETED, so an
        # arbitrary choice can delete the wrong game. Nothing in the gate
        # distinguishes "one real game listed three times" from "several real
        # games that happen to share a shared team, a scoreline and a recorded
        # instant", and this branch's whole posture is to refuse what it cannot
        # tell apart. Measured 2026-08-15 over the live corpus: of the games
        # with any qualifying candidate, the MAXIMUM candidate count is 1, so
        # this refusal costs ZERO real collapses today -- it is a fail-closed
        # guard against a shape the corpus does not yet contain, adopted
        # precisely because it is free.
        if len(qualifying) > 1:
            logger.warning(
                "Opponent-divergence AMBIGUOUS for game %s on %s: %d candidates "
                "(%s) all satisfy the gate. Refusing to choose -- an arbitrary "
                "pick can delete the wrong games row. Leaving all rows.",
                game_id, game_date, len(qualifying),
                ", ".join(c.existing_id for c in qualifying),
            )
            return None

        candidate = qualifying[0]
        logger.warning(
            "Opponent-identity divergence: game %s → %s on %s. One real "
            "game filed under two opponent team rows (%d vs %d, identity "
            "on the %s side); start times %s vs %s, delta %ss, bound "
            "%.1fs; per-team scores agree (%s-%s). Collapsing to one row.",
            game_id, candidate.existing_id, game_date,
            candidate.incoming_differing, candidate.existing_differing,
            "incoming" if candidate.incoming_bearing else "canonical",
            start_time, candidate.existing_start,
            candidate.delta_seconds,
            # This branch's OWN bound, not the same-pair window. The warning is
            # this destructive path's audit trail, so naming the wrong constant
            # would misstate WHY a row was collapsed or deleted.
            _DIVERGENCE_MAX_DELTA_SECONDS,
            home_score, away_score,
        )
        return candidate.existing_id

    def _classify_divergence_collapse(
        self, canonical_id: str, home_team_id: int, away_team_id: int,
    ) -> str | None:
        """Classify a collapse as a divergence one, and say which row wins.

        Returns ``_DIVERGENCE_PROMOTE`` when the canonical row names the
        bare-name STUB (so the incoming row must survive and absorb it),
        ``_DIVERGENCE_PRESERVE`` when the canonical already names the
        identity-bearing team (a plain redirect that must NOT overwrite the
        canonical orientation), or ``None`` when this is an ordinary team-pair
        collapse.

        Derived from the canonical ROW rather than threaded out of
        ``_find_duplicate_game``, which keeps this order-independent and leaves
        that function's signature (and its many direct-calling tests) alone. The
        derivation is exact: the team-pair pass can only return a row whose
        ``{home, away}`` equals the incoming pair in one order or the other, so
        a canonical that shares exactly ONE side is necessarily a divergence
        match.

        Work item 2's mixed-identity TRIGGER means only one shape ever reaches
        here: exactly one side identity-bearing. Both-identity and both-stub
        never collapse, so they never reach the redirect at all.

        ⚠️ THE ``PRESERVE`` HALF IS NOT COSMETIC. Without it a SAME-perspective
        divergence redirect leaves ``preserve_scores`` False, and the upsert
        then overwrites the canonical row's orientation tuple with the incoming
        one -- burying the identity-bearing opponent under the stub and making
        the surviving identity depend on load order, which is exactly what the
        promotion exists to prevent. Caught by
        ``test_divergence_same_side_score_agreeing_collapses``.
        """
        row = self._db.execute(
            "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
            (canonical_id,),
        ).fetchone()
        if row is None:
            return None
        canonical_home, canonical_away = row

        differing = _differing_team_ids(
            home_team_id, away_team_id, canonical_home, canonical_away,
        )
        if differing is None:
            return None                       # an ordinary team-pair collapse
        _incoming_differing, canonical_differing = differing

        if self._team_is_identity_bearing(canonical_differing):
            return _DIVERGENCE_PRESERVE
        return _DIVERGENCE_PROMOTE

    def _promote_over_stub_headed_row(
        self,
        summary: GameSummaryEntry,
        canonical_id: str,
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
        """Load under the INCOMING event id, then merge the stub-headed row in.

        ⚠️ ORDERING IS THE SHARPEST HAZARD IN THIS CHUNK, and it is what makes
        the fail-closed fallback real rather than vacuous.
        ``merge_duplicate_game`` refuses only when the two rows' perspective
        sets INTERSECT; an EMPTY set on either side yields no intersection and
        the merge PROCEEDS. ``_upsert_game_and_stats`` is what records this
        row's ``game_perspectives`` entry, so running the merge before it
        returns would leave the new row's set empty, let a SAME-perspective pair
        through unrefused, and destroy a real game. The merge therefore runs
        AFTER the upsert, and a test pins it (the corpus contains such a pair,
        so the shape is real rather than hypothetical).

        ``preserve_scores`` is False, reasoned rather than inherited. E-268
        protects the canonical row's orientation tuple on a CROSS-perspective
        REDIRECT, so the first-loaded perspective's scores do not flap. This is
        not a redirect: it writes THIS perspective's own row under its OWN event
        id, which is the same situation as an ordinary same-perspective reload,
        where a genuine scorekeeper correction must still land. The gate has
        already forced the two rows' scores to agree, so there is no
        cross-perspective disagreement to protect -- and the orientation this
        step exists to change is precisely the one it must be free to write.

        On a merge REFUSAL both rows are left standing and no remap is
        recorded: a refusal costs a duplicate row, a wrong merge destroys a
        game.
        """
        source_event_id = summary.event_id
        logger.warning(
            "Identity-bearing promotion: loading game %s under its OWN event id "
            "and merging stub-headed row %s into it (date %s). The canonical "
            "row names a bare-name opponent stub; the surviving row must carry "
            "the opponent's GameChanger identity.",
            source_event_id, canonical_id, game_date,
        )

        result = self._upsert_game_and_stats(
            summary, game_date,
            home_team_id, away_team_id, home_score, away_score,
            own_data, own_team_id, opp_data, opp_team_id,
            preserve_scores=False,
        )
        if result.errors:
            # The incoming row did not land cleanly; do not delete anything on
            # the strength of a half-written survivor.
            return result

        # ⚠️ ASSERT THE GUARD'S PREMISE POSITIVELY -- ``result.errors`` CANNOT
        # carry it. ``_upsert_game_and_stats`` catches ``sqlite3.Error`` on the
        # ``game_perspectives`` INSERT, logs it, and builds its ``LoadResult``
        # AFTERWARDS, so a failed perspective write leaves ``errors == 0``. The
        # ordering above would then be satisfied while the thing it exists to
        # guarantee -- a NON-EMPTY perspective set on the incoming row -- was
        # never true, and ``merge_duplicate_game`` would find no intersection
        # and delete the canonical row unrefused. "Ran without errors" is not
        # the same fact as "the row is there", so ask for the row.
        if not self._game_perspective_recorded(source_event_id, self._team_ref.id):
            logger.error(
                "Refusing the identity-bearing promotion of %s over %s: this "
                "load's game_perspectives row is absent, so the merge's "
                "disjointness refusal would be VACUOUS. Leaving both rows.",
                source_event_id, canonical_id,
            )
            return result

        merged = self._merge_twin_or_rollback(canonical_id, source_event_id)
        if merged is not None:
            # sqlite3.Error mid-merge: already rolled back and counted.
            return merged

        # ``_merge_twin_or_rollback`` returns None for a clean merge, a
        # structural REFUSAL, and a vanished source alike, so the row itself is
        # the arbiter of whether anything was deleted.
        if not self._game_row_exists(canonical_id):
            self._record_deleted_row_redirect(canonical_id, source_event_id)
        return result

    def _record_deleted_row_redirect(
        self, deleted_game_id: str, surviving_game_id: str,
    ) -> None:
        """Point every redirect at the survivor after a row is deleted.

        The generator's plays and spray stages remap every SOURCE event id
        through ``redirect_map`` before filing, so an id resolving to a deleted
        ``games`` row silently strands those stages -- a skip, not an error.
        Two entries need attention and both cost one line:

        * the deleted row's OWN id, added unconditionally. At spec time the
          deleted row usually belongs to a different perspective's earlier run,
          so its id is normally absent from this run's crawl set and the entry
          is harmless insurance -- but "usually" is not a guarantee worth
          relying on at a seam whose failure mode is a silent skip.
        * any entry already POINTING AT the deleted row, which must follow it.
          Those are invisible from the deleted id alone.
        """
        for source, destination in list(self.redirect_map.items()):
            if destination == deleted_game_id:
                self.redirect_map[source] = surviving_game_id
        previous = self.redirect_map.get(deleted_game_id)
        if previous is not None and previous != surviving_game_id:
            logger.warning(
                "Redirect for deleted game %s moves from %s to %s.",
                deleted_game_id, previous, surviving_game_id,
            )
        self.redirect_map[deleted_game_id] = surviving_game_id

    # ------------------------------------------------------------------
    # Twin merge (E-261-03b)
    # ------------------------------------------------------------------

    def _game_perspective_recorded(
        self, game_id: str, perspective_team_id: int,
    ) -> bool:
        """True when this game/perspective pair is actually recorded.

        Exists so the promotion can PROVE its non-empty perspective set rather
        than infer it from an error count that structurally cannot report the
        failure (see ``_promote_over_stub_headed_row``).
        """
        return (
            self._db.execute(
                "SELECT 1 FROM game_perspectives "
                "WHERE game_id = ? AND perspective_team_id = ?",
                (game_id, perspective_team_id),
            ).fetchone()
            is not None
        )

    def _game_row_exists(self, game_id: str) -> bool:
        """Return True if a ``games`` row already exists under ``game_id``."""
        return (
            self._db.execute(
                "SELECT 1 FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
            is not None
        )

    def _merge_twin_or_rollback(
        self, source_game_id: str, canonical_game_id: str,
    ) -> LoadResult | None:
        """Merge a persisted source-event twin into the canonical row (Defect A).

        Called at the redirect site only when a ``games`` row already exists
        under the ORIGINAL source event id -- an un-merged twin left by an earlier
        dedup miss. Delegates the child re-point + delete-last to the shared
        ``merge_duplicate_game`` primitive (E-261-02).

        Returns:
            ``None`` when the caller should PROCEED to the upsert -- the merge
            succeeded, the helper structurally REFUSED a non-disjoint pair
            (E-261-02 AC-2: leave both rows, still load under the canonical id),
            OR the source twin VANISHED concurrently (Codex P2 benign race: the
            twin is already gone, i.e. the healed end-state).
            ``LoadResult(errors=1)`` when the merge raised ``sqlite3.Error`` (a
            mid-merge DML failure) or an UNEXPECTED ``GameMergeError`` with the
            source row still present: the shared connection is rolled back FIRST
            (AC-3) so the partial merge cannot bleed into the next game's commit,
            and the caller must return that result without upserting.
        """
        try:
            result = merge_duplicate_game(
                self._db, source_game_id, canonical_game_id
            )
        except sqlite3.Error as exc:
            # Shared-connection partial-commit footgun (AC-3): a mid-merge failure
            # may leave writes pending on the shared connection; roll them back so
            # ``load_payload``'s per-game commit does not silently persist a
            # half-merge.
            logger.error(
                "Twin merge %s → %s raised %s; rolling back and failing this game.",
                source_game_id, canonical_game_id, exc,
            )
            self._db.rollback()
            return LoadResult(errors=1)
        except GameMergeError as exc:
            # Read-then-write TOCTOU (Codex P2): the SQLite file is shared by
            # multiple writers (admin UI, report CLI, morning-run cron -- CLAUDE.md
            # "Canonical SQLite connection factory"), so another writer can delete
            # the source twin BETWEEN our ``_game_row_exists`` check and this
            # merge. ``merge_duplicate_game`` then raises "source not found". That
            # is a BENIGN race -- the twin is already gone (the healed end-state) --
            # NOT a programming bug, so it must not abort the whole load.
            # ``GameMergeError`` is raised only from the helper's PRE-write
            # validation, so no partial merge state exists.
            if not self._game_row_exists(source_game_id):
                # Source vanished concurrently: benign no-op. Do NOT roll back --
                # there is no partial merge state, and this load's own pending
                # team rows are still needed for the upsert below. Proceed under
                # the canonical id (the twin is already collapsed).
                logger.warning(
                    "Twin merge %s → %s: source row vanished before merge "
                    "(concurrent writer); benign no-op, loading under canonical "
                    "(%s).",
                    source_game_id, canonical_game_id, exc,
                )
                return None
            # Source still present -> NOT the vanished-source race (e.g. the
            # canonical row was concurrently deleted, or an unexpected argument).
            # Do not silently swallow a potential real bug: roll back and fail
            # THIS game (errors=1) rather than letting it abort the whole load.
            logger.error(
                "Twin merge %s → %s raised GameMergeError with source still "
                "present: %s; rolling back and failing this game.",
                source_game_id, canonical_game_id, exc,
            )
            self._db.rollback()
            return LoadResult(errors=1)
        if result.refused:
            # Non-disjoint perspectives -- refuse rather than guess (E-261-02
            # AC-2). Leave both rows intact; the game still loads under the
            # canonical id (the operator repair pass E-261-04 handles these).
            logger.warning(
                "Twin merge %s → %s REFUSED (shared perspective(s) %s); leaving "
                "both rows, loading under the canonical id.",
                source_game_id, canonical_game_id, result.shared_perspectives,
            )
        else:
            logger.info(
                "Twin merge %s → %s complete (re-pointed %s).",
                source_game_id, canonical_game_id,
                result.table_counts or "no child rows",
            )
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
        preserve_scores: bool = False,
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
            game_stream_id: Stream ID (boxscore file key); in the scouting/public
                path this equals the row's own ``event_id`` (self-keyed). Written
                verbatim on first insert; on an ``ON CONFLICT(game_id)`` update the
                canonical row's existing value is KEPT (E-261-01 keep-existing).
            start_time: ISO 8601 datetime string from schedule/public endpoint.
            timezone: IANA timezone identifier (e.g., ``America/Chicago``).
            preserve_scores: When True (a CROSS-perspective redirect), the
                ``ON CONFLICT`` update keeps the canonical row's existing
                orientation tuple -- ``home_team_id``, ``away_team_id``,
                ``home_score``, and ``away_score`` all keep-existing together
                (first-loaded perspective wins; fills only a NULL gap) instead
                of overwriting them -- so the tolerant same-game signal firing
                on a FLIPPED orientation / DISAGREEING scores does not flap the
                canonical row on every regeneration, and the frozen scores are
                never re-attributed to a swapped team-id (E-268-01 / TN-1,
                extending E-261-03a). False (a first insert or a SAME-
                perspective reload) writes the incoming values, preserving the
                scorekeeper-correction path. Scoped to the redirect site ONLY --
                do NOT confuse with a blanket COALESCE, which TN-1 forbids.

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
        # Orientation-tuple ownership (E-268-01 / TN-1, extending E-261-03a):
        # the four fields {home_team_id, away_team_id, home_score, away_score}
        # form ONE atomic orientation tuple and must move together. On a
        # CROSS-perspective redirect (preserve_scores=True) keep the canonical
        # row's existing values (COALESCE existing-first, filling only a NULL
        # gap) so disagreeing perspectives do not flap the canonical value AND
        # the frozen scores are never re-attributed to a flipped team-id; a
        # first insert or a SAME-perspective reload (preserve_scores=False)
        # writes the incoming values, preserving the scorekeeper-correction
        # path. Bound as a 0/1 flag so the SQL stays static -- the ON CONFLICT
        # clause is not evaluated on a plain insert, so ``games.*`` in the CASE
        # is safe. Gating the team-ids alongside the scores (rather than the
        # prior unconditional excluded.* overwrite) closes CC-2: the torn write
        # that swapped home/away team-ids while freezing the scores, silently
        # re-crediting runs to the wrong team on both perspectives' reports.
        preserve_flag = 1 if preserve_scores else 0
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
                home_team_id   = CASE WHEN ? THEN COALESCE(games.home_team_id, excluded.home_team_id)
                                      ELSE excluded.home_team_id END,
                away_team_id   = CASE WHEN ? THEN COALESCE(games.away_team_id, excluded.away_team_id)
                                      ELSE excluded.away_team_id END,
                home_score     = CASE WHEN ? THEN COALESCE(games.home_score, excluded.home_score)
                                      ELSE excluded.home_score END,
                away_score     = CASE WHEN ? THEN COALESCE(games.away_score, excluded.away_score)
                                      ELSE excluded.away_score END,
                status         = excluded.status,
                -- Keep-existing (E-261-01): preserve the canonical row's own
                -- game_stream_id on a cross-perspective redirect. In the
                -- scouting/public path game_stream_id is self-keyed to each
                -- row's own event_id (see scouting_loader._build_games_index),
                -- so it is non-null AND perspective-specific -- clobbering it
                -- with the incoming perspective's id poisons the canonical row
                -- and, when an un-merged twin still owns that value, trips
                -- migration 010's partial UNIQUE index. EXISTING is the FIRST
                -- COALESCE argument (NOT the prefer-new order used by the
                -- adjacent start_time/timezone lines below). First-insert is
                -- unaffected: existing is NULL, so the incoming value is written.
                game_stream_id = COALESCE(games.game_stream_id, excluded.game_stream_id),
                start_time     = COALESCE(excluded.start_time, games.start_time),
                timezone       = COALESCE(excluded.timezone, games.timezone)
            """,
            # Four preserve_flag binds -- one per CASE in ON CONFLICT, in SQL
            # order: home_team_id, away_team_id, home_score, away_score.
            (game_id, self._season_id, game_date, home_team_id, away_team_id,
             home_score, away_score, game_stream_id, start_time, timezone,
             preserve_flag, preserve_flag, preserve_flag, preserve_flag),
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
        # Record the team BEFORE the write, and unconditionally: both INSERT
        # branches live in this method, which makes it the single choke point for
        # boxscore-sourced roster rows on BOTH sides of the game. Recording after
        # the branch, or in only one of them, would silently under-report the set
        # ScoutingLoader's dedup loop iterates. A membership record for a row that
        # already existed is harmless -- dedup on an already-converged team is a
        # no-op -- so there is no reason to condition this on the row being new.
        self.rostered_team_ids.add(team_id)

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
