"""Mailgun email helper for the baseball-crawl application.

Exposes a generic async email sender (:func:`send_email`) plus the existing
magic-link login email (:func:`send_magic_link_email`, now a thin caller of the
generic sender) and the morning-run operator alerts (E-240-06). When Mailgun is
configured the sender POSTs via the Mailgun async API; otherwise it logs to
stdout so local development works without email infrastructure.

Operator alerts (E-240-06, Technical Notes TN-7) are operator-only -- no
coach-facing content -- and are addressed to ``ADMIN_EMAIL`` (the established
operator-identity env var). A synchronous wrapper (:func:`send_email_sync`) lets
the synchronous ``morning-run`` CLI invoke the async sender.

Configuration (environment variables):
    MAILGUN_API_KEY    -- Mailgun API key. If absent, falls back to stdout logging.
    MAILGUN_DOMAIN     -- Mailgun sending domain (e.g. mg.example.com).
    MAILGUN_FROM_EMAIL -- Sender address. Defaults to noreply@{MAILGUN_DOMAIN}.
    ADMIN_EMAIL        -- Operator recipient for all operator alerts.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_MAILGUN_API_BASE = "https://api.mailgun.net/v3"
_MAGIC_LINK_SUBJECT = "Your login link for Baseball Stats"


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send a plain-text email to ``to_email``.

    When ``MAILGUN_API_KEY`` is set, sends via the Mailgun async API using HTTP
    Basic auth. When it is not set, logs the message to stdout at INFO level so
    local development works without email infrastructure.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        True if the email was sent (or logged) successfully; False on error
        (missing ``MAILGUN_DOMAIN`` when configured, a non-success Mailgun
        response, or a request error).
    """
    mg_key = os.environ.get("MAILGUN_API_KEY", "")
    if not mg_key:
        logger.info("[DEV] Email to %s | subject: %s\n%s", to_email, subject, body)
        return True

    domain = os.environ.get("MAILGUN_DOMAIN", "")
    if not domain:
        logger.error("MAILGUN_DOMAIN is required when MAILGUN_API_KEY is set")
        return False

    from_email = os.environ.get("MAILGUN_FROM_EMAIL", f"noreply@{domain}")
    url = f"{_MAILGUN_API_BASE}/{domain}/messages"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=("api", mg_key),
                data={
                    "from": from_email,
                    "to": to_email,
                    "subject": subject,
                    "text": body,
                },
                timeout=10.0,
            )
        if response.is_success:
            logger.info("Email sent to %s (subject: %s)", to_email, subject)
            return True
        logger.error(
            "Mailgun request failed: status=%d body=%s",
            response.status_code,
            response.text[:200],
        )
        return False
    except httpx.RequestError:
        logger.exception("Mailgun request error for %s", to_email)
        return False


def send_email_sync(to_email: str, subject: str, body: str) -> bool:
    """Synchronous wrapper around :func:`send_email` for sync CLIs.

    The ``morning-run`` CLI is synchronous; this runs the async sender to
    completion via :func:`asyncio.run`. MUST NOT be called from within a running
    event loop (it would raise ``RuntimeError``) -- it is for sync entry points
    only.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        The :func:`send_email` result (True on success, False on error).
    """
    return asyncio.run(send_email(to_email, subject, body))


async def send_magic_link_email(to_email: str, magic_link_url: str) -> bool:
    """Send a magic link login email to the given address.

    Thin caller of :func:`send_email`: builds the magic-link subject/body and
    delegates. Observable behavior (Mailgun send vs. stdout fallback, and the
    True/False return semantics) is unchanged.

    Args:
        to_email: Recipient email address.
        magic_link_url: The full magic link URL to send.

    Returns:
        True if the email was sent (or logged) successfully; False on error.
    """
    body = (
        f"Click the link below to log in to Baseball Stats.\n\n"
        f"{magic_link_url}\n\n"
        f"This link expires in 15 minutes and can only be used once.\n"
        f"If you did not request this, you can safely ignore this email."
    )
    return await send_email(to_email, _MAGIC_LINK_SUBJECT, body)


# ---------------------------------------------------------------------------
# Morning-run operator alerts (E-240-06, TN-7) -- operator-only, no coach content
# ---------------------------------------------------------------------------


async def _send_operator_alert(subject: str, body: str) -> bool:
    """Send an operator alert to ``ADMIN_EMAIL``, warn-and-skip if it is unset.

    All operator alerts share this dispatch: the recipient is ``ADMIN_EMAIL``
    (no new config var; C2). When ``ADMIN_EMAIL`` is unset the helper logs a
    visible warning and SKIPS sending, returning False -- it does NOT crash the
    run (alerting is a side channel, not the work). A False return here means
    "not sent" (unset recipient OR a sender failure); the caller treats alerting
    as best-effort.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        logger.warning(
            "ADMIN_EMAIL is unset; skipping operator alert (subject: %s). "
            "Set ADMIN_EMAIL in .env to receive morning-run alerts.",
            subject,
        )
        return False
    return await send_email(admin_email, subject, body)


async def send_preflight_failure_alert(error_detail: str) -> bool:
    """Operator alert (a): the preflight credential refresh failed.

    The morning run aborts early when the preflight token check cannot recover
    (refresh + login fallback both failed). This alert tells the operator the
    run did not proceed and why.

    Args:
        error_detail: Human-readable description of the auth failure.

    Returns:
        True if the alert was sent; False if skipped (ADMIN_EMAIL unset) or the
        send failed.
    """
    subject = "[morning-run] Preflight credential check FAILED — run aborted"
    body = (
        "The morning-run preflight credential check failed; no reports were "
        "generated this run.\n\n"
        f"Detail: {error_detail}\n\n"
        "Action: refresh GameChanger credentials (e.g. `bb creds check` / "
        "`bb creds setup web`) and re-run, or wait for the next scheduled run "
        "once credentials are restored."
    )
    return await _send_operator_alert(subject, body)


async def send_unresolved_opponent_alert(
    *, root_team_id: str, opponent_name: str
) -> bool:
    """Operator alert (b): an opponent is unresolved-but-mappable.

    The body carries a TEMPLATE ``map-opponent`` command with ``root_team_id``
    pre-filled and the GC team URL an explicit placeholder the operator
    completes after looking up the team (the URL is unknown by definition for an
    unresolved opponent; TN-5/TN-7).

    Args:
        root_team_id: The opponent's GC ``root_team_id`` (the stable key the
            operator pastes into ``map-opponent``).
        opponent_name: The free-text opponent name from the schedule (context
            so the operator knows which team to look up).

    Returns:
        True if the alert was sent; False if skipped/failed.
    """
    subject = (
        f"[morning-run] Unresolved opponent: {opponent_name} — action needed"
    )
    body = (
        f"An upcoming opponent could not be auto-resolved to a GameChanger "
        f"team, so no scouting report was generated for it.\n\n"
        f"Opponent (as typed in GameChanger): {opponent_name}\n"
        f"root_team_id: {root_team_id}\n\n"
        "To resolve it, look up the team on GameChanger, copy its team URL, and "
        "run:\n\n"
        f"    bb report map-opponent {root_team_id} <PASTE-GC-TEAM-URL>\n\n"
        "If the team is genuinely not on GameChanger (no report possible), "
        "instead run:\n\n"
        f"    bb report map-opponent {root_team_id} --no-presence\n"
    )
    return await _send_operator_alert(subject, body)


async def send_end_of_run_summary(
    *, generated: int, failed: int, unresolved: int, detail: str = ""
) -> bool:
    """Operator alert (c): the always-sent end-of-run summary.

    Sent at the END of every (non-aborted) morning run regardless of outcome —
    its ABSENCE is the missed-run signal (TN-9). Carries success/fail counts; a
    per-game failure (e.g. all-boxscores-blocked) is surfaced HERE, not via a
    dedicated per-game alert (there is no fourth alert; AC-3).

    Args:
        generated: Count of reports generated this run.
        failed: Count of opponents whose generation was attempted and failed.
        unresolved: Count of unresolved-but-mappable opponents this run.
        detail: Optional extra body text (e.g. per-opponent lines).

    Returns:
        True if the summary was sent; False if skipped/failed.
    """
    subject = (
        f"[morning-run] Summary: {generated} generated, {failed} failed, "
        f"{unresolved} unresolved"
    )
    body = (
        "Morning-run complete.\n\n"
        f"Reports generated:           {generated}\n"
        f"Generation failures:         {failed}\n"
        f"Unresolved (need mapping):   {unresolved}\n"
    )
    if detail:
        body += f"\n{detail}\n"
    return await _send_operator_alert(subject, body)


# ---------------------------------------------------------------------------
# Sync entries for the operator alerts (mirror send_email_sync; E-240-06 SHOULD
# FIX). The synchronous morning-run CLI (E-240-07) calls THESE so it does not
# manage event loops at the call site. Each MUST NOT be called from within a
# running event loop (asyncio.run would raise RuntimeError) -- they are for sync
# entry points only. Same bool return semantics as the async forms (True sent /
# False skipped-or-failed). The async helpers remain available for callers that
# already have a loop.
# ---------------------------------------------------------------------------


def send_preflight_failure_alert_sync(error_detail: str) -> bool:
    """Synchronous wrapper around :func:`send_preflight_failure_alert`.

    Runs the async preflight-failure alert to completion via
    :func:`asyncio.run`. MUST NOT be called from within a running event loop.

    Args:
        error_detail: Human-readable description of the auth failure.

    Returns:
        True if the alert was sent; False if skipped (``ADMIN_EMAIL`` unset) or
        the send failed.
    """
    return asyncio.run(send_preflight_failure_alert(error_detail))


def send_unresolved_opponent_alert_sync(
    *, root_team_id: str, opponent_name: str
) -> bool:
    """Synchronous wrapper around :func:`send_unresolved_opponent_alert`.

    Runs the async unresolved-opponent alert to completion via
    :func:`asyncio.run`. MUST NOT be called from within a running event loop.

    Args:
        root_team_id: The opponent's GC ``root_team_id`` (pre-filled in the
            embedded ``map-opponent`` template command).
        opponent_name: The free-text opponent name from the schedule.

    Returns:
        True if the alert was sent; False if skipped/failed.
    """
    return asyncio.run(
        send_unresolved_opponent_alert(
            root_team_id=root_team_id, opponent_name=opponent_name
        )
    )


def send_end_of_run_summary_sync(
    *, generated: int, failed: int, unresolved: int, detail: str = ""
) -> bool:
    """Synchronous wrapper around :func:`send_end_of_run_summary`.

    Runs the async end-of-run summary to completion via :func:`asyncio.run`.
    MUST NOT be called from within a running event loop.

    Args:
        generated: Count of reports generated this run.
        failed: Count of opponents whose generation was attempted and failed.
        unresolved: Count of unresolved-but-mappable opponents this run.
        detail: Optional extra body text (e.g. per-opponent lines).

    Returns:
        True if the summary was sent; False if skipped/failed.
    """
    return asyncio.run(
        send_end_of_run_summary(
            generated=generated,
            failed=failed,
            unresolved=unresolved,
            detail=detail,
        )
    )
