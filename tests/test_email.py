# synthetic-test-data
"""Tests for src.api.email (E-240-06).

Covers the generic async sender (configured-Mailgun + stdout-fallback paths),
the preserved magic-link behavior, the three operator-alert helpers, the
ADMIN_EMAIL-unset warn-and-skip path, the sync wrapper, and the sender-failure
error path. No real HTTP -- Mailgun is mocked via respx; per .claude/rules/testing.md.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from src.api.email import (
    send_email,
    send_email_sync,
    send_end_of_run_summary,
    send_end_of_run_summary_sync,
    send_magic_link_email,
    send_preflight_failure_alert,
    send_preflight_failure_alert_sync,
    send_unresolved_opponent_alert,
    send_unresolved_opponent_alert_sync,
    validate_alerting_config,
)

_MAILGUN_URL = "https://api.mailgun.net/v3/mg.example.com/messages"

_MAILGUN_ENV = {
    "MAILGUN_API_KEY": "key-fake",
    "MAILGUN_DOMAIN": "mg.example.com",
    "MAILGUN_FROM_EMAIL": "noreply@mg.example.com",
}


# ---------------------------------------------------------------------------
# AC-1: generic sender -- Mailgun-configured path
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_send_email_posts_to_mailgun_when_configured() -> None:
    route = respx.post(_MAILGUN_URL).mock(return_value=httpx.Response(200))

    with patch.dict("os.environ", _MAILGUN_ENV, clear=False):
        ok = await send_email("op@example.com", "Subj", "Body text")

    assert ok is True
    assert route.called
    request = route.calls.last.request
    # Form-encoded body carries the subject/body/recipient.
    sent = request.content.decode()
    assert "to=op%40example.com" in sent
    assert "subject=Subj" in sent


@respx.mock
@pytest.mark.asyncio
async def test_send_email_returns_false_on_mailgun_error_status() -> None:
    respx.post(_MAILGUN_URL).mock(return_value=httpx.Response(500, text="boom"))

    with patch.dict("os.environ", _MAILGUN_ENV, clear=False):
        ok = await send_email("op@example.com", "Subj", "Body")

    assert ok is False


@respx.mock
@pytest.mark.asyncio
async def test_send_email_returns_false_on_request_error() -> None:
    respx.post(_MAILGUN_URL).mock(side_effect=httpx.ConnectError("no route"))

    with patch.dict("os.environ", _MAILGUN_ENV, clear=False):
        ok = await send_email("op@example.com", "Subj", "Body")

    assert ok is False


@pytest.mark.asyncio
async def test_send_email_missing_domain_when_key_set_returns_false() -> None:
    with patch.dict(
        "os.environ", {"MAILGUN_API_KEY": "key-fake", "MAILGUN_DOMAIN": ""}, clear=False
    ):
        ok = await send_email("op@example.com", "Subj", "Body")

    assert ok is False


# ---------------------------------------------------------------------------
# AC-1: generic sender -- stdout fallback (no MAILGUN_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_stdout_fallback_when_no_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # APP_ENV pinned to development so the tri-state's dev branch is deterministic
    # (E-252-03 -- no key + non-production => stdout + True).
    with patch.dict("os.environ", {"MAILGUN_API_KEY": "", "APP_ENV": "development"}, clear=False):
        with caplog.at_level("INFO"):
            ok = await send_email("op@example.com", "Hello", "Body here")

    assert ok is True
    assert "[DEV]" in caplog.text
    assert "op@example.com" in caplog.text
    assert "Body here" in caplog.text


@pytest.mark.asyncio
async def test_send_email_no_key_in_production_returns_false(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-4: production + unconfigured Mailgun must NOT report a stdout-logged
    message as sent -- the tri-state returns False (a misconfiguration), so the
    missed-run summary never gets a false 'sent'.
    """
    with patch.dict("os.environ", {"MAILGUN_API_KEY": "", "APP_ENV": "production"}, clear=False):
        with caplog.at_level("ERROR"):
            ok = await send_email("op@example.com", "Hello", "Body here")

    assert ok is False
    assert "MAILGUN_API_KEY" in caplog.text


@pytest.mark.asyncio
async def test_send_email_no_key_in_development_returns_true() -> None:
    """AC-5: local dev preserved -- no key + development => treated as sent (True)."""
    with patch.dict("os.environ", {"MAILGUN_API_KEY": "", "APP_ENV": "development"}, clear=False):
        ok = await send_email("op@example.com", "Hello", "Body here")
    assert ok is True


@pytest.mark.asyncio
async def test_send_email_no_key_unset_app_env_returns_true() -> None:
    """AC-5: APP_ENV unset defaults to development => stdout fallback treated as sent."""
    env = {k: v for k, v in os.environ.items() if k != "APP_ENV"}
    env["MAILGUN_API_KEY"] = ""
    with patch.dict("os.environ", env, clear=True):
        ok = await send_email("op@example.com", "Hello", "Body here")
    assert ok is True


# ---------------------------------------------------------------------------
# E-252-03: validate_alerting_config() -- the non-dry-run alerting preflight
# ---------------------------------------------------------------------------


def test_validate_alerting_config_admin_unset_returns_error() -> None:
    """AC-2: no ADMIN_EMAIL => no operator recipient => misconfigured (error string)."""
    with patch.dict("os.environ", {"ADMIN_EMAIL": ""}, clear=False):
        err = validate_alerting_config()
    assert err is not None
    assert "ADMIN_EMAIL" in err


def test_validate_alerting_config_prod_without_mailgun_returns_error() -> None:
    """AC-2/AC-4: production + no Mailgun => misconfigured (stdout is not delivery)."""
    with patch.dict(
        "os.environ",
        {"ADMIN_EMAIL": "op@lsb.test", "APP_ENV": "production", "MAILGUN_API_KEY": ""},
        clear=False,
    ):
        err = validate_alerting_config()
    assert err is not None
    assert "MAILGUN_API_KEY" in err


def test_validate_alerting_config_dev_with_admin_is_ok() -> None:
    """AC-5: development + ADMIN_EMAIL set + no Mailgun => deliverable (None)."""
    with patch.dict(
        "os.environ",
        {"ADMIN_EMAIL": "op@lsb.test", "APP_ENV": "development", "MAILGUN_API_KEY": ""},
        clear=False,
    ):
        assert validate_alerting_config() is None


def test_validate_alerting_config_prod_with_mailgun_is_ok() -> None:
    """Production WITH BOTH MAILGUN_API_KEY and MAILGUN_DOMAIN + ADMIN_EMAIL =>
    deliverable (None). (P1#2: the domain is required, so it must be set here.)"""
    with patch.dict(
        "os.environ",
        {
            "ADMIN_EMAIL": "op@lsb.test",
            "APP_ENV": "production",
            "MAILGUN_API_KEY": "key-fake",
            "MAILGUN_DOMAIN": "mg.example.com",
        },
        clear=False,
    ):
        assert validate_alerting_config() is None


def test_validate_alerting_config_prod_without_domain_returns_error() -> None:
    """P1#2: production + MAILGUN_API_KEY set but MAILGUN_DOMAIN UNSET => misconfigured.
    send_email hard-fails without the domain (returns False), so the summary would
    silently never send -- the preflight must catch it, not green-light the run."""
    with patch.dict(
        "os.environ",
        {
            "ADMIN_EMAIL": "op@lsb.test",
            "APP_ENV": "production",
            "MAILGUN_API_KEY": "key-fake",
            "MAILGUN_DOMAIN": "",  # explicitly unset (overrides any ambient value)
        },
        clear=False,
    ):
        err = validate_alerting_config()
    assert err is not None
    assert "MAILGUN_DOMAIN" in err


# ---------------------------------------------------------------------------
# AC-2: magic-link behavior preserved (thin caller of send_email)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_magic_link_delegates_to_send_email() -> None:
    with patch(
        "src.api.email.send_email", new_callable=AsyncMock, return_value=True
    ) as mock_send:
        ok = await send_magic_link_email("user@example.com", "https://x/abc")

    assert ok is True
    mock_send.assert_awaited_once()
    args = mock_send.await_args.args
    assert args[0] == "user@example.com"
    assert args[1] == "Your login link for Baseball Stats"
    assert "https://x/abc" in args[2]
    assert "expires in 15 minutes" in args[2]


@pytest.mark.asyncio
async def test_send_magic_link_stdout_fallback_returns_true(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Preserved behavior: no key -> stdout log, returns True, link in output.

    APP_ENV pinned to development so the tri-state's dev branch is deterministic.
    """
    with patch.dict(
        "os.environ", {"MAILGUN_API_KEY": "", "APP_ENV": "development"}, clear=False
    ):
        with caplog.at_level("INFO"):
            ok = await send_magic_link_email("user@example.com", "https://x/magic")

    assert ok is True
    assert "https://x/magic" in caplog.text


@respx.mock
@pytest.mark.asyncio
async def test_send_magic_link_returns_false_on_failure() -> None:
    respx.post(_MAILGUN_URL).mock(return_value=httpx.Response(401))

    with patch.dict("os.environ", _MAILGUN_ENV, clear=False):
        ok = await send_magic_link_email("user@example.com", "https://x/magic")

    assert ok is False


# ---------------------------------------------------------------------------
# AC-3 / AC-4: the three operator alerts -> ADMIN_EMAIL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preflight_failure_alert_addresses_admin_with_detail() -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            ok = await send_preflight_failure_alert("refresh + login both failed")

    assert ok is True
    to, subject, body = mock_send.await_args.args
    assert to == "admin@lsb.test"
    assert "Preflight" in subject
    assert "refresh + login both failed" in body


@pytest.mark.asyncio
async def test_unresolved_opponent_alert_embeds_template_command() -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            ok = await send_unresolved_opponent_alert(
                root_team_id="root-xyz-9", opponent_name="Bellevue West"
            )

    assert ok is True
    to, subject, body = mock_send.await_args.args
    assert to == "admin@lsb.test"
    assert "Bellevue West" in subject
    # AC-3(b): the template command has root_team_id pre-filled and a URL placeholder.
    assert "bb report map-opponent root-xyz-9 <PASTE-GC-TEAM-URL>" in body
    # The --no-presence alternative is also offered.
    assert "bb report map-opponent root-xyz-9 --no-presence" in body
    assert "Bellevue West" in body


@pytest.mark.asyncio
async def test_end_of_run_summary_carries_counts() -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            ok = await send_end_of_run_summary(
                generated=4, failed=1, unresolved=2, detail="extra line"
            )

    assert ok is True
    to, subject, body = mock_send.await_args.args
    assert to == "admin@lsb.test"
    assert "4 generated" in subject
    assert "1 failed" in subject
    assert "2 unresolved" in subject
    assert "extra line" in body


# ---------------------------------------------------------------------------
# AC-4: ADMIN_EMAIL unset -> warn and skip, no crash, returns False
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "coro_factory",
    [
        lambda: send_preflight_failure_alert("x"),
        lambda: send_unresolved_opponent_alert(root_team_id="r", opponent_name="n"),
        lambda: send_end_of_run_summary(generated=0, failed=0, unresolved=0),
    ],
)
@pytest.mark.asyncio
async def test_operator_alert_admin_email_unset_warns_and_skips(
    coro_factory, caplog: pytest.LogCaptureFixture
) -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": ""}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            with caplog.at_level("WARNING"):
                ok = await coro_factory()

    # Skipped (not sent), returned False, no crash, warning logged.
    assert ok is False
    mock_send.assert_not_awaited()
    assert "ADMIN_EMAIL is unset" in caplog.text


@pytest.mark.asyncio
async def test_operator_alert_send_failure_surfaced_as_false() -> None:
    """Error path: when the underlying send fails, the alert returns False."""
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=False
        ):
            ok = await send_preflight_failure_alert("auth dead")

    assert ok is False


# ---------------------------------------------------------------------------
# AC-5: sync wrapper
# ---------------------------------------------------------------------------


def test_send_email_sync_runs_async_sender() -> None:
    with patch(
        "src.api.email.send_email", new_callable=AsyncMock, return_value=True
    ) as mock_send:
        ok = send_email_sync("op@example.com", "Subj", "Body")

    assert ok is True
    mock_send.assert_awaited_once_with("op@example.com", "Subj", "Body")


def test_send_email_sync_returns_false_on_failure() -> None:
    with patch(
        "src.api.email.send_email", new_callable=AsyncMock, return_value=False
    ):
        ok = send_email_sync("op@example.com", "Subj", "Body")

    assert ok is False


# ---------------------------------------------------------------------------
# SHOULD FIX (E-240-06): sync entries for the three operator alerts
# ---------------------------------------------------------------------------


def test_preflight_failure_alert_sync_sends_when_admin_set() -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            ok = send_preflight_failure_alert_sync("auth dead")

    assert ok is True
    to, _subject, body = mock_send.await_args.args
    assert to == "admin@lsb.test"
    assert "auth dead" in body


def test_unresolved_opponent_alert_sync_sends_with_template() -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            ok = send_unresolved_opponent_alert_sync(
                root_team_id="root-99", opponent_name="Millard South"
            )

    assert ok is True
    to, _subject, body = mock_send.await_args.args
    assert to == "admin@lsb.test"
    assert "bb report map-opponent root-99 <PASTE-GC-TEAM-URL>" in body


def test_end_of_run_summary_sync_sends_with_counts() -> None:
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            ok = send_end_of_run_summary_sync(generated=3, failed=0, unresolved=1)

    assert ok is True
    to, subject, _body = mock_send.await_args.args
    assert to == "admin@lsb.test"
    assert "3 generated" in subject


@pytest.mark.parametrize(
    "call",
    [
        lambda: send_preflight_failure_alert_sync("x"),
        lambda: send_unresolved_opponent_alert_sync(
            root_team_id="r", opponent_name="n"
        ),
        lambda: send_end_of_run_summary_sync(generated=0, failed=0, unresolved=0),
    ],
)
def test_alert_sync_admin_email_unset_skips_returns_false(
    call, caplog: pytest.LogCaptureFixture
) -> None:
    """The ADMIN_EMAIL-unset skip path is reachable through the sync wrapper."""
    with patch.dict("os.environ", {"ADMIN_EMAIL": ""}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            with caplog.at_level("WARNING"):
                ok = call()

    assert ok is False
    mock_send.assert_not_awaited()
    assert "ADMIN_EMAIL is unset" in caplog.text


def test_alert_sync_send_failure_surfaced_as_false() -> None:
    """Error path through the sync wrapper: a sender failure returns False."""
    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@lsb.test"}, clear=False):
        with patch(
            "src.api.email.send_email", new_callable=AsyncMock, return_value=False
        ):
            ok = send_preflight_failure_alert_sync("auth dead")

    assert ok is False
