"""Morning-run orchestration for scheduled scouting reports (E-240-07).

The cron-invoked ``bb report morning-run`` reads each LSB team's GameChanger
schedule, filters to the target LOCAL date, resolves each upcoming opponent via
the resolution ladder, and -- for auto-resolved opponents -- calls the existing,
UNTOUCHED ``generate_report(public_id)``. Every scheduled slot's outcome is
recorded to ``scheduled_report_runs`` and an end-of-run operator summary is sent.

This module is the orchestration SHELL (TN-1): it composes reused seams and
NEVER enters the generator's internals --

* E-240-01: :func:`resolve_own_team_gc_uuid`, :func:`fetch_schedule`,
  :func:`fetch_opponents`
* E-240-04: :func:`resolve_opponent` (the resolution ladder)
* E-240-03: the ``scheduled_report_runs`` + ``opponent_links`` tables
* E-240-06: the operator-alert sync wrappers
* the untouched ``generate_report(public_id)``

Execution is strictly SEQUENTIAL (TN-2): one process iterates teams and
opponents with a plain loop -- never concurrent. Per-opponent failures are
isolated (TN-9): one opponent's exception is recorded and the loop continues.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import httpx

from src.db.teams import ensure_team_row
from src.gamechanger.client import GameChangerClient
from src.gamechanger.crawlers.opponents import fetch_opponents, resolve_own_team_gc_uuid
from src.gamechanger.crawlers.schedule import ScheduledGame, fetch_schedule
from src.gamechanger.exceptions import (
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    RateLimitError,
)
from src.gamechanger.opponent_ladder import (
    METHOD_NO_PRESENCE,
    LadderResult,
    ResolutionOutcome,
    resolve_opponent,
)
from src.gamechanger.team_resolver import TeamProfile, resolve_team
from src.gamechanger.url_parser import parse_team_url
from src.reports.generator import GenerationResult, generate_report
from src.util.timezone import derive_local_date, operating_today, utcnow_iso

logger = logging.getLogger(__name__)

# A lightweight authenticated endpoint used for the preflight liveness check
# (forces the lazy token refresh). Same endpoint/pin `bb creds check` uses.
_ME_USER_ENDPOINT = "/me/user"
_ME_USER_ACCEPT = "application/vnd.gc.com.user+json; version=0.3.0"

# Type alias for the injectable report generator (tests substitute a fake).
GenerateFn = Callable[[str], GenerationResult]


class PreflightError(Exception):
    """Raised when the preflight credential liveness check cannot recover."""


@dataclass
class SlotResult:
    """One scheduled-slot outcome (one upcoming opponent on one team's schedule)."""

    own_team_id: int
    opponent_root_team_id: str
    opponent_name: str | None
    game_date: str
    resolution_outcome: str
    resolved_public_id: str | None = None
    report_slug: str | None = None
    delivery_status: str | None = None
    error_message: str | None = None
    # Display context for --dry-run / the summary (not persisted).
    resolved_team_name: str | None = None
    resolved_record: str | None = None
    # Which ladder rung produced the mapping (`progenitor` / `search` /
    # `operator` / `no_presence`). Display-only, NOT persisted here -- the
    # durable copy is opponent_links.resolution_method. Surfaced on the RESOLVED
    # line because it is what tells the operator whether a wrong mapping can be
    # corrected: `bb report map-opponent` accepts a `search` resolution and
    # refuses the rest, so without it they cannot tell before trying.
    resolution_method: str | None = None
    # In-memory control flag (NOT a column, NOT persisted): when True, run_morning
    # SKIPS the _upsert_slot write for this slot. Set ONLY on the fresh-reservation
    # skip path (E-252-07 P1#1 fix) so it does NOT clobber a concurrent run's
    # in-flight `delivery_status IS NULL` reservation with 'skipped' -- which would
    # make a THIRD overlapping run see a non-NULL row, fail the fresh-reservation
    # check, and double-generate. The ordinary _prior_success skip leaves this
    # False (its write is harmless: report_id is preserved via the carried slug).
    suppress_persist: bool = False


@dataclass
class MorningRunResult:
    """Aggregate outcome of a morning run (counts + per-slot detail)."""

    generated: int = 0
    failed: int = 0
    unresolved: int = 0
    deferred: int = 0
    no_games: int = 0
    skipped: int = 0
    teams_processed: int = 0
    # Teams skipped because an authenticated crawler call returned 403
    # (ForbiddenError) -- a per-team denial OR, when denied == teams_processed,
    # the FALSE-403 signature of a misconfigured CRAWLER version pin (the
    # crawlers use different pins than the preflight /me/user check, so a pin
    # error passes preflight but 403s every team). Surfaced in the summary so
    # this is never an invisible silent skip (TN-4 FALSE-403 concern).
    denied: int = 0
    # Teams skipped because an authenticated crawl raised a TRANSIENT error -- a
    # 5xx GameChangerAPIError (after the client's retries) or an httpx transport
    # error (connection/timeout). Isolated per-team like `denied`, distinct from
    # the slot-level `failed` (which is per-slot report generation). (E-252-02.)
    transient: int = 0
    # Teams skipped because an authenticated crawl raised RateLimitError (429).
    # RUN-LEVEL tally (a team-level 429 produces zero slots, so it is NOT a
    # CHECK-constrained scheduled_report_runs value). A 429 is more likely
    # systemic than a 403 (TN-9), so a RECURRENCE trips `rate_limit_aborted`.
    # CAVEAT: GC 429 behavior is UNOBSERVED (TN-6) -- revisit if a real 429 is
    # captured. (E-252-02.)
    rate_limited: int = 0
    # True when a 429 recurred across teams and the run stopped early (TN-9): no
    # further GC calls were made for the remaining teams. Surfaced in the summary
    # as "rate-limited -- aborted early". (E-252-02.)
    rate_limit_aborted: bool = False
    slots: list[SlotResult] = field(default_factory=list)

    @property
    def detail_lines(self) -> str:
        """Multi-line per-slot detail + the per-team skip lines for the summary.

        Appends the 403-denial line and the E-252-02 transient (5xx/connection)
        and rate-limit (429) lines so the always-sent summary email surfaces
        every per-team skip -- a team-level failure produces no slot, so without
        these lines an isolated 5xx/429/connect skip would be invisible.
        """
        lines = [self._format_slot(s) for s in self.slots]
        for extra in (self.denied_detail, self.rate_limit_detail, self.transient_detail):
            if extra:
                lines.append(extra)
        return "\n".join(lines)

    @property
    def denied_detail(self) -> str:
        """A summary line describing 403-denied teams, or '' when none.

        When EVERY processed team was denied (``denied == teams_processed`` and
        at least one team), this is the FALSE-403 / check-credentials-or-pins
        signal the operator must see -- a 0-generated/0-unresolved summary would
        otherwise look identical to "no games scheduled today".
        """
        if self.denied <= 0:
            return ""
        if self.denied == self.teams_processed:
            return (
                f"WARNING: ALL {self.denied} team(s) were denied (403) — likely a "
                "systematic auth/version-pin problem, NOT 'no games today'. "
                "Check credentials and the crawler Accept version pins."
            )
        return f"{self.denied} team(s) skipped: access denied (403)."

    @property
    def transient_detail(self) -> str:
        """A summary line describing transient-error-skipped teams, or ''.

        Mirrors :attr:`denied_detail`: a 5xx/connection error on a team's crawl
        is isolated and counted, so the summary surfaces it rather than letting
        it look like "no games today". (E-252-02 AC-1.)
        """
        if self.transient <= 0:
            return ""
        return (
            f"{self.transient} team(s) skipped: transient error "
            "(5xx/connection) — isolated, run continued."
        )

    @property
    def rate_limit_detail(self) -> str:
        """A summary line describing 429-skipped teams, or '' when none.

        Mirrors :attr:`denied_detail`. When a 429 RECURRED and the run stopped
        early (:attr:`rate_limit_aborted`), the line carries the explicit
        "rate-limited — aborted early" systemic signal (TN-9 / AC-4) so the
        operator learns the remaining teams were deliberately skipped, not that
        there were no games.
        """
        if self.rate_limited <= 0:
            return ""
        if self.rate_limit_aborted:
            return (
                f"WARNING: rate-limited — aborted early after {self.rate_limited} "
                "rate-limit hit(s) (429); the remaining teams were skipped to "
                "avoid hammering GameChanger (systemic 429, TN-9)."
            )
        return f"{self.rate_limited} team(s) skipped: rate limited (429)."

    @staticmethod
    def _format_slot(slot: SlotResult) -> str:
        base = (
            f"[{slot.game_date}] {slot.opponent_name or '(unnamed)'} "
            f"(opponent_id={slot.opponent_root_team_id}) -> "
            f"{slot.resolution_outcome}"
        )
        if slot.resolved_public_id and slot.resolved_team_name:
            base += (
                f"\n    RESOLVED: {slot.resolved_team_name} "
                f"[public_id: {slot.resolved_public_id}]"
            )
            # The method belongs on THIS surface too, not just the dry-run
            # console line: the summary email is what the operator actually
            # reads after an unattended cron run, and `via search` is the tag
            # that tells them a mapping is both the likeliest to be wrong and
            # the only one `bb report map-opponent` can correct.
            if slot.resolution_method:
                base += f" [via {slot.resolution_method}]"
            if slot.resolved_record:
                base += f" — record {slot.resolved_record}"
        if slot.delivery_status:
            base += f"  (delivery: {slot.delivery_status})"
        if slot.error_message:
            base += f"\n    ERROR: {slot.error_message}"
        return base


def _game_local_date(game: ScheduledGame) -> str | None:
    """The game's LOCAL date for the --date filter (falls back to game_date)."""
    return derive_local_date(game.start_datetime, game.timezone) or game.game_date


def preflight_credential_check(client: GameChangerClient) -> None:
    """Force a token refresh by hitting a lightweight authenticated endpoint.

    Runs ONCE at the top of the run (TN-9). On an unrecoverable auth failure
    (the client's refresh + login fallback both fail) this raises
    :class:`PreflightError` so the caller sends the preflight-failure operator
    alert and aborts early/visibly. A 403 (version-pin / legitimate denial) is
    NOT collapsed into auth-expiry (TN-4): it raises PreflightError with a
    distinct message.

    Args:
        client: The SHARED authenticated client the crawlers/ladder also use --
            so the preflight-refreshed token feeds the same session (AC-7).

    Raises:
        PreflightError: On an unrecoverable auth failure, a 403, or a transient
            (429 / 5xx / connection) failure -- all abort the run visibly with
            the operator alert, but with distinct, non-collapsed messages.
    """
    try:
        client.get(_ME_USER_ENDPOINT, accept=_ME_USER_ACCEPT)
    except ForbiddenError as exc:
        raise PreflightError(
            f"Preflight check got 403 (access denied / version-pin), not a token "
            f"expiry: {exc}"
        ) from exc
    except CredentialExpiredError as exc:
        raise PreflightError(
            f"Preflight credential check failed -- token refresh + login fallback "
            f"could not recover: {exc}"
        ) from exc
    except (RateLimitError, GameChangerAPIError, httpx.RequestError) as exc:
        # AC-6: a transient (non-auth) preflight failure surfaces as a PreflightError
        # (operator alert + abort) rather than an unhandled crash. Kept AFTER the
        # auth clauses so a 403/401 is never collapsed into "transient"; these
        # three types are disjoint from CredentialExpiredError so the order is
        # otherwise free. GC 429 behavior is UNOBSERVED (TN-6).
        raise PreflightError(
            f"Preflight check hit a transient error (rate-limit / 5xx / "
            f"connection), not an auth failure: {exc}"
        ) from exc


def _resolved_record(profile: TeamProfile) -> str | None:
    """Format a W-L record string from a TeamProfile, or None."""
    w, l = profile.record_wins, profile.record_losses
    if w is None and l is None:
        return None
    return f"{w or 0}-{l or 0}"


def map_outcome_to_vocabulary(result: LadderResult) -> str:
    """Map a ladder :class:`LadderResult` to a ``resolution_outcome`` (TN-11).

    The ladder never returns ``no_gc_presence``; an operator-declared
    ``no_presence`` link row surfaces as ``UNRESOLVED_MAPPABLE`` with
    ``method='no_presence'`` (from_cache) -- which maps to the
    ``no_gc_presence`` run outcome here. All other unresolved-mappables map to
    ``unresolved_mappable``.
    """
    if result.outcome is ResolutionOutcome.RESOLVED:
        return "auto_resolved"
    if result.outcome is ResolutionOutcome.DEFERRED_PLACEHOLDER:
        return "deferred_placeholder"
    # UNRESOLVED_MAPPABLE: distinguish operator-declared no_presence (TN-11).
    if result.method == METHOD_NO_PRESENCE:
        return "no_gc_presence"
    return "unresolved_mappable"


def _prior_success(
    conn: sqlite3.Connection,
    own_team_id: int,
    root_team_id: str,
    game_date: str,
    resolved_public_id: str | None = None,
) -> bool:
    """True when a prior SUCCESS slot exists for this (team, opponent, date).

    The idempotency skip predicate (TN-9): a row with
    ``resolution_outcome='auto_resolved'`` AND a non-NULL, non-expired
    ``report_id``. A re-run treats this as a skip (``delivery_status='skipped'``)
    rather than regenerating.

    ⚠ **And the prior report must be for the team we are resolving to NOW.**
    ``resolved_public_id`` is compared against the slot's stored value, because
    a mapping can CHANGE between runs: `bb report map-opponent` overrides a
    wrong rung-(c) `search` resolution (2026-08-05), and without this comparison
    the skip fires on the report generated from the OLD mapping -- so the
    operator corrects the mapping, re-runs as the runbook tells them to, sees
    "skipped", and the coach keeps reading the WRONG team's scouting report
    until it expires. The correction would be silently inert, which is worse
    than not offering one.

    A stored value that is NULL or differs does NOT skip -- it regenerates.
    That is the safe direction: the cost is a wasted regeneration, where the
    other direction serves a report for the wrong team.
    """
    row = conn.execute(
        "SELECT s.report_id, r.expires_at "
        "FROM scheduled_report_runs s "
        "LEFT JOIN reports r ON r.id = s.report_id "
        "WHERE s.own_team_id = ? AND s.opponent_root_team_id = ? "
        "AND s.game_date = ? AND s.resolution_outcome = 'auto_resolved' "
        "AND s.report_id IS NOT NULL "
        "AND s.resolved_public_id IS NOT NULL AND s.resolved_public_id = ?",
        (own_team_id, root_team_id, game_date, resolved_public_id),
    ).fetchone()
    if row is None:
        return False
    expires_at = row[1]
    if expires_at is None:
        return False
    # Non-expired => the prior report is still serveable; skip regeneration.
    # Lexical compare against the canonical UTC-iso helper: `expires_at` is
    # written from the same UTC_ISO_FORMAT, so string order == time order.
    return expires_at > utcnow_iso()


def _existing_report_slug(
    conn: sqlite3.Connection,
    own_team_id: int,
    root_team_id: str,
    game_date: str,
) -> str | None:
    """The ``report_slug`` already stored on this slot's audit row, or None.

    Used by the idempotency skip path (F-H2): a skip is NOT a regeneration, so
    the skip slot must carry the audit row's EXISTING report linkage forward --
    otherwise :func:`_upsert_slot` would look up ``report_id`` from a None slug
    and null out the row's ``report_id``/``report_slug``, and the NEXT run's
    :func:`_prior_success` would then see ``report_id IS NULL`` and wastefully
    regenerate.
    """
    row = conn.execute(
        "SELECT report_slug FROM scheduled_report_runs "
        "WHERE own_team_id = ? AND opponent_root_team_id = ? AND game_date = ?",
        (own_team_id, root_team_id, game_date),
    ).fetchone()
    return row[0] if row else None


# Reserve-before-generate lease (E-252-07 item 4 / AC-5). A slot is "reserved" by
# writing its ``auto_resolved`` audit row with ``delivery_status IS NULL`` BEFORE
# generation. A concurrent/overlapping run that finds a FRESH reservation (updated
# within this lease) SKIPS the slot rather than double-generating it; a STALE
# reservation (older than the lease -- a crashed run that left the row NULL) is
# treated as abandoned and regenerated, so a crash mid-generation cannot
# permanently block the slot. The window is longer than a report generation but
# short enough to self-heal well before the next daily run. The CHECK constraint
# on ``delivery_status`` has no 'reserved' value (that would need a migration), so
# ``auto_resolved`` + ``delivery_status IS NULL`` is the in-progress marker.
_RESERVATION_LEASE_SECONDS = 600


def _slot_reserved_fresh(
    conn: sqlite3.Connection,
    own_team_id: int,
    root_team_id: str,
    game_date: str,
) -> bool:
    """True when a FRESH reservation exists for this slot (E-252-07 AC-5).

    A fresh reservation is an ``auto_resolved`` audit row with
    ``delivery_status IS NULL`` whose ``updated_at`` is within
    :data:`_RESERVATION_LEASE_SECONDS` -- i.e. another run reserved this slot and
    is (very likely) still generating it. A STALE NULL row (a crashed run) is NOT
    fresh, so the caller regenerates rather than skipping forever.
    """
    row = conn.execute(
        "SELECT 1 FROM scheduled_report_runs "
        "WHERE own_team_id = ? AND opponent_root_team_id = ? AND game_date = ? "
        "AND resolution_outcome = 'auto_resolved' AND delivery_status IS NULL "
        "AND updated_at > datetime('now', ?)",
        (
            own_team_id,
            root_team_id,
            game_date,
            f"-{_RESERVATION_LEASE_SECONDS} seconds",
        ),
    ).fetchone()
    return row is not None


def _upsert_slot(conn: sqlite3.Connection, slot: SlotResult) -> None:
    """UPSERT one scheduled_report_runs row, idempotent per the slot key (TN-6).

    The UNIQUE key is ``(own_team_id, opponent_root_team_id, game_date)``. SQLite
    treats NULLs as DISTINCT in a UNIQUE index, so the caller MUST guarantee a
    non-NULL key on all three columns (the loader falls back to the opponent_id
    token for a null root_team_id) -- otherwise idempotency silently breaks.
    """
    report_id = _lookup_report_id(conn, slot.report_slug)
    conn.execute(
        "INSERT INTO scheduled_report_runs "
        "(game_date, own_team_id, opponent_root_team_id, opponent_name, "
        " resolution_outcome, resolved_public_id, report_id, report_slug, "
        " delivery_status, error_message, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(own_team_id, opponent_root_team_id, game_date) DO UPDATE SET "
        "opponent_name = excluded.opponent_name, "
        "resolution_outcome = excluded.resolution_outcome, "
        "resolved_public_id = excluded.resolved_public_id, "
        "report_id = excluded.report_id, "
        "report_slug = excluded.report_slug, "
        "delivery_status = excluded.delivery_status, "
        "error_message = excluded.error_message, "
        "updated_at = datetime('now')",
        (
            slot.game_date,
            slot.own_team_id,
            slot.opponent_root_team_id,
            slot.opponent_name,
            slot.resolution_outcome,
            slot.resolved_public_id,
            report_id,
            slot.report_slug,
            slot.delivery_status,
            slot.error_message,
        ),
    )
    conn.commit()


def _lookup_report_id(conn: sqlite3.Connection, slug: str | None) -> int | None:
    """Resolve a report slug to its reports.id (for the FK), or None."""
    if not slug:
        return None
    row = conn.execute("SELECT id FROM reports WHERE slug = ?", (slug,)).fetchone()
    return row[0] if row else None


def _process_opponent(
    *,
    conn: sqlite3.Connection,
    client: GameChangerClient,
    own_team_id: int,
    game: ScheduledGame,
    game_date: str,
    registry: list,
    dry_run: bool,
    generate_fn: GenerateFn,
) -> SlotResult:
    """Resolve one upcoming opponent and (non-dry-run) generate its report.

    The per-opponent body. Errors here are caught by the caller's try/except so
    one opponent's failure does not abort the run (TN-9).
    """
    # The slot key MUST be non-NULL on all three columns; fall back to the
    # opponent_id token when root_team_id would be null (TN-6 NULL footgun).
    root_team_id = game.opponent_id or f"unknown-{game.event_id}"

    ladder = resolve_opponent(
        conn=conn,
        client=client,
        our_team_id=own_team_id,
        opponent_id=root_team_id,
        opponent_name=game.opponent_name,
        registry=registry,
    )
    outcome = map_outcome_to_vocabulary(ladder)

    slot = SlotResult(
        own_team_id=own_team_id,
        opponent_root_team_id=root_team_id,
        opponent_name=game.opponent_name,
        game_date=game_date,
        resolution_outcome=outcome,
        resolved_public_id=ladder.public_id,
        resolution_method=ladder.method,
    )

    # For a resolved opponent, fetch the display name + record (the dry-run
    # eyeball line; TN-5). Same resolve_team helper as own-team resolution (C3).
    if ladder.public_id:
        try:
            profile = resolve_team(ladder.public_id)
            slot.resolved_team_name = profile.name
            slot.resolved_record = _resolved_record(profile)
        except Exception:  # noqa: BLE001 -- display enrichment is best-effort
            logger.warning(
                "Could not fetch display profile for public_id=%s", ladder.public_id,
                exc_info=True,
            )

    # Non-auto-resolved outcomes attempt no generation; delivery_status stays
    # NULL and resolution_outcome carries the reason (TN-11).
    if outcome != "auto_resolved" or dry_run or ladder.public_id is None:
        return slot

    # Idempotency: a prior non-expired SUCCESS is a skip, not a regenerate (TN-9).
    if _prior_success(
        conn, own_team_id, root_team_id, game_date, ladder.public_id
    ):
        slot.delivery_status = "skipped"
        # Carry the prior report linkage onto the skip slot (F-H2). A skip is NOT
        # a regeneration; leaving report_slug None here would make _upsert_slot
        # overwrite the audit row's report_id/report_slug with NULL, and the NEXT
        # run's _prior_success would then see report_id IS NULL and wastefully
        # regenerate. Preserving the existing slug keeps the linkage intact.
        slot.report_slug = _existing_report_slug(
            conn, own_team_id, root_team_id, game_date
        )
        return slot

    # Reserve-before-generate (E-252-07 item 4 / AC-5). We reach here only for an
    # auto_resolved, non-dry-run slot with NO prior non-expired success (the
    # _prior_success skip above already returned). Two guards:
    #   1. If a CONCURRENT run holds a FRESH reservation for this slot, SKIP rather
    #      than double-generate (the other run is generating it).
    #   2. Otherwise write OUR reservation -- an auto_resolved, delivery_status=NULL
    #      audit row -- BEFORE calling generate_fn, so an overlap/SIGKILL leaves a
    #      durable marker (idempotency is recorded before generation, not only
    #      after). Carry any existing report linkage so the reservation does not
    #      null it (reconciles with E-252-01's F-H2 carry: report_id/report_slug
    #      are preserved). The caller's post-return _upsert_slot overwrites this
    #      reservation with the final generated/failed/no_games state.
    carried_slug = _existing_report_slug(conn, own_team_id, root_team_id, game_date)
    if _slot_reserved_fresh(conn, own_team_id, root_team_id, game_date):
        slot.delivery_status = "skipped"
        slot.report_slug = carried_slug
        # P1#1 fix: do NOT persist this skip -- the audit row IS the concurrent
        # run's fresh `delivery_status IS NULL` reservation, and UPSERTing 'skipped'
        # over it would defeat the fresh-reservation check for a THIRD overlapping
        # run (which would then double-generate). Leave the NULL reservation intact
        # so run C also sees it fresh and skips; still tally it as skipped in-memory.
        slot.suppress_persist = True
        return slot
    slot.report_slug = carried_slug
    _upsert_slot(conn, slot)  # reservation write (delivery_status still None)

    # Generate via the untouched generate_report() (TN-1). A generation failure
    # here -- whether generate_fn returns a failed GenerationResult OR raises --
    # is a failure of an ALREADY-RESOLVED opponent: the slot stays
    # resolution_outcome='auto_resolved' with delivery_status='failed' (TN-11),
    # NOT unresolved_mappable. Misclassifying it would tell the operator to
    # `map-opponent` a team that is already resolved (the wrong action).
    try:
        gen: GenerationResult = generate_fn(ladder.public_id)
    except Exception as exc:  # noqa: BLE001 -- a resolved opponent whose gen blew up
        logger.exception(
            "generate_report raised for resolved opponent public_id=%s",
            ladder.public_id,
        )
        slot.delivery_status = "failed"
        slot.error_message = str(exc)
        return slot

    slot.report_slug = gen.slug
    if gen.outcome == "ready":
        slot.delivery_status = "generated"
    elif gen.outcome == "no_games":
        slot.delivery_status = "no_games"
    else:  # "failed"
        slot.delivery_status = "failed"
        slot.error_message = gen.error_message
    return slot


def run_morning(
    team_urls: list[str],
    *,
    conn: sqlite3.Connection,
    client: GameChangerClient,
    target_date: date | None = None,
    dry_run: bool = False,
    generate_fn: GenerateFn = generate_report,
) -> MorningRunResult:
    """Run the morning scheduled-report orchestration for the given teams.

    SEQUENTIAL (TN-2): one process, a plain loop over teams and opponents, never
    concurrent. Per-opponent failures are isolated (TN-9).

    Args:
        team_urls: GameChanger team URLs / public_id slugs (the crontab config).
        conn: Open SQLite connection (run records + opponent_links).
        client: The SHARED preflight-refreshed authenticated client.
        target_date: The LOCAL date to filter games to (default: today).
        dry_run: When True, generate NO reports -- only resolve + record-less
            preview.
        generate_fn: Injectable report generator (defaults to the real
            ``generate_report``); tests substitute a fake.

    Returns:
        A :class:`MorningRunResult` with counts + per-slot detail.
    """
    if target_date is None:
        # Default "today" is the venue OPERATING-tz date, NOT the container's UTC
        # date (E-252-05): the prod container clock is UTC, so an evening run
        # (past ~19:00 venue time) would otherwise default to tomorrow's games.
        # An explicit --date still overrides (target_date is not None then).
        target_date = operating_today()
    target_iso = target_date.isoformat()

    result = MorningRunResult()

    for url in team_urls:
        result.teams_processed += 1
        try:
            parsed = parse_team_url(url)
        except ValueError:
            logger.warning("Skipping unparseable team URL %r", url)
            continue
        public_id = parsed.value

        # CredentialExpiredError (a true token death mid-run) is run-fatal and
        # must surface -- it affects EVERY team, so we do NOT swallow it; it
        # propagates to the CLI. A ForbiddenError (legitimate per-team denial)
        # is its subclass, so we catch that FIRST and isolate it to this team
        # (AC-12: a real auth failure is distinguished from a legitimate denial,
        # never collapsed into a single "auth expired" meaning).
        try:
            gc_uuid = resolve_own_team_gc_uuid(client, public_id)
            if not gc_uuid:
                logger.warning(
                    "Could not resolve gc_uuid for team %s; skipping its schedule",
                    public_id,
                )
                continue

            # Own-team row (FK target for scheduled_report_runs.own_team_id).
            own_team_id = ensure_team_row(
                conn, public_id=public_id, gc_uuid=gc_uuid, source="morning_run"
            )
            # E-252-07 items 1 & 2 (TN-5): COMMIT the own-team row IMMEDIATELY --
            # BEFORE the network fetch below. ensure_team_row opens an implicit
            # write transaction that does NOT commit; leaving it open across
            # fetch_schedule/fetch_opponents (network I/O) would hold the single WAL
            # write lock for the entire multi-team crawl, so E-252-06's busy_timeout
            # could not save a competing writer (06 + 07 are two halves of ONE
            # contention fix). Committing here also makes the own-team row durable
            # for a NO-GAMES team -- whose zero slots would otherwise never commit,
            # so the default-isolation conn.close() would ROLL the INSERT back and
            # re-INSERT it every morning. This relocates E-252-02's post-crawl commit
            # to before the fetch (its correct home) -- there is no second commit.
            conn.commit()

            schedule = fetch_schedule(client, gc_uuid)
            registry = fetch_opponents(client, gc_uuid)
        except ForbiddenError:
            # Per-team denial (e.g. a team the operator does not follow): skip
            # this team, keep processing the rest. Distinct from a 401. Counted
            # so the end-of-run summary surfaces it -- otherwise an all-teams
            # FALSE-403 (a misconfigured crawler pin) would be an invisible
            # silent skip indistinguishable from "no games today" (TN-4).
            # MUST be caught BEFORE any bare CredentialExpiredError: ForbiddenError
            # is a SUBCLASS of it, and catch order is load-bearing (a 403 must not
            # collapse into "token died"). RateLimitError/GameChangerAPIError below
            # are disjoint standalone types, so they never shadow a 401.
            conn.rollback()  # TN-10: clear any partial DML before the next team.
            result.denied += 1
            logger.warning(
                "Access denied (403) for team %s; skipping it and continuing",
                public_id,
                exc_info=True,
            )
            continue
        except RateLimitError:
            # Team-level 429 (schedule/roster fetch). A 429 is more likely
            # SYSTEMIC than a 403 (TN-9), so we isolate + count this team, and if
            # a 429 RECURS across teams we STOP the run early rather than hammer
            # GameChanger. CAVEAT: GC 429 behavior is UNOBSERVED (TN-6) -- this
            # escalation is designed against the unknown; revisit if a real 429 is
            # captured. (Per-game boxscore 429s isolate at the crawler in E-252-04
            # and never reach this seam; only team-level 429s do, by design.)
            conn.rollback()  # TN-10: clear any partial DML before continuing.
            result.rate_limited += 1
            logger.warning(
                "Rate limit (429) hit for team %s; isolating it. NOTE: GC 429 "
                "behavior is UNOBSERVED (TN-6).",
                public_id,
                exc_info=True,
            )
            if result.rate_limited >= 2:
                # Recurring 429 => systemic. Abort the run: make no further GC
                # calls for the remaining teams (TN-9). The always-sent summary
                # still fires and reports "rate-limited -- aborted early".
                result.rate_limit_aborted = True
                logger.error(
                    "Recurring rate limits (429) across teams -- aborting early; "
                    "%d team(s) left unprocessed.",
                    len(team_urls) - result.teams_processed,
                )
                break
            continue
        except (GameChangerAPIError, httpx.RequestError):
            # Transient failure: a 5xx GameChangerAPIError (after the client's
            # retries) or an httpx transport error (connection refused, DNS,
            # timeout -- httpx.RequestError is the base of those). Isolate this
            # team and continue so teams 2..N still process and the always-sent
            # summary still fires (AC-1). Distinct from the slot-level `failed`.
            conn.rollback()  # TN-10: clear any partial DML before the next team.
            result.transient += 1
            logger.warning(
                "Transient error (5xx/connection) for team %s; isolating it and "
                "continuing to the remaining teams.",
                public_id,
                exc_info=True,
            )
            continue
        # NB: a bare CredentialExpiredError (HTTP 401, true token death) is NOT
        # caught here -- it affects EVERY team, so it propagates to the CLI and is
        # run-fatal (AC-2). ForbiddenError (403) was already isolated above.

        # (E-252-07: the own-team row was already committed right after
        # ensure_team_row, before the network fetch -- so it is durable here for the
        # per-game rollback and for a no-games team, with no write lock held across
        # the crawl. No commit is needed at this point anymore.)

        for game in schedule:
            local_date = _game_local_date(game)
            if local_date != target_iso:
                continue

            try:
                slot = _process_opponent(
                    conn=conn,
                    client=client,
                    own_team_id=own_team_id,
                    game=game,
                    game_date=local_date,
                    registry=registry,
                    dry_run=dry_run,
                    generate_fn=generate_fn,
                )
            except Exception as exc:  # noqa: BLE001 -- per-game isolation (TN-9)
                # Reaching here means the RESOLUTION phase itself raised (the
                # ladder, or the display-profile fetch) -- a post-resolution
                # generation failure is already caught inside _process_opponent
                # and classified auto_resolved/failed. This slot has NO public_id,
                # so it is recorded as a failure WITH an error_message; the
                # error_message is the discriminator that suppresses the
                # unresolved-mappable operator prompt/alert + the `unresolved`
                # tally (a crash is NOT a mappable opponent -- the operator must
                # not be told to `map-opponent` it). The CHECK set has no "error"
                # bucket; unresolved_mappable is the least-bad valid value and is
                # rendered inert for the operator by the error_message gate.
                #
                # TN-10 (E-252-07 AC-4, DEFENSE-IN-DEPTH): roll back before building
                # and _upsert_slot-ing the failure slot. There is NO uncommitted DML
                # to leak TODAY -- the only shared-conn writer reachable here,
                # opponent_ladder.resolve_opponent, SELF-COMMITS its opponent_links
                # writes (opponent_ladder.py:179/205), and the display-profile fetch
                # is caught internally / generate_fn runs on its own connection. This
                # rollback guards against a FUTURE ladder change that introduces
                # write->network->commit ordering on the shared connection; keep it
                # (do NOT remove as dead code).
                conn.rollback()
                logger.exception(
                    "Opponent RESOLUTION failed for team=%s opponent_id=%s",
                    public_id, game.opponent_id,
                )
                slot = SlotResult(
                    own_team_id=own_team_id,
                    opponent_root_team_id=game.opponent_id or f"unknown-{game.event_id}",
                    opponent_name=game.opponent_name,
                    game_date=local_date,
                    resolution_outcome="unresolved_mappable",
                    delivery_status="failed",
                    error_message=str(exc),
                )

            if not dry_run and not slot.suppress_persist:
                # E-252-07 item 3 + TN-10: isolate the per-slot audit write so ONE
                # slot's DB error (a lock / IntegrityError) logs and the run
                # continues -- it no longer aborts the remaining slots/teams. The
                # except rolls back FIRST (TN-10) so a partially-executed audit write
                # is not carried into a later commit. The in-memory tally still runs
                # below so the summary reflects the slot even if its row didn't land.
                # `suppress_persist` (P1#1) skips this write for the fresh-reservation
                # skip so a concurrent run's NULL reservation is left untouched.
                try:
                    _upsert_slot(conn, slot)
                except sqlite3.Error:
                    conn.rollback()
                    logger.exception(
                        "Failed to record audit row for team=%s opponent=%s date=%s; "
                        "continuing with the remaining slots",
                        own_team_id, slot.opponent_root_team_id, local_date,
                    )
            result.slots.append(slot)
            _tally(result, slot)

    return result


def _tally(result: MorningRunResult, slot: SlotResult) -> None:
    """Update the aggregate counters from one slot's outcome."""
    if slot.delivery_status == "generated":
        result.generated += 1
    elif slot.delivery_status == "failed":
        result.failed += 1
    elif slot.delivery_status == "no_games":
        result.no_games += 1
    elif slot.delivery_status == "skipped":
        result.skipped += 1

    # A GENUINE unresolved-mappable opponent (no error) counts as unresolved and
    # is surfaced to the operator. A resolution-CRASH slot carries the same
    # outcome value but an error_message + delivery_status='failed' -- it is a
    # failure, NOT a mappable opponent, so it is excluded here (and from the
    # operator prompt/alert) by the error_message gate.
    if slot.resolution_outcome == "unresolved_mappable" and slot.error_message is None:
        result.unresolved += 1
    elif slot.resolution_outcome == "deferred_placeholder":
        result.deferred += 1
