---
name: accept-header-strictness
description: GC 415s a WRONG vendor Accept type but serves a generic/absent one — so pinning is more brittle than not pinning; plus the 415-vs-false-403 split and our own two unpinned call sites
metadata:
  type: reference
---

# Accept-header strictness: a WRONG type 415s, a GENERIC one is served (2026-07-26)

Verified live on two **public, no-auth** endpoints. Not probed on authenticated endpoints —
do not generalize there ([[public-team-accept-header-inert]] is the companion negative obs).

| `Accept` sent | Result |
|---|---|
| correct vendor type | 200 |
| **wrong vendor resource type** | **415, no body, no fallback** |
| generic `application/json, text/plain, */*` | **200, full body** |

Confirmed on `GET /public/teams/{public_id}/games` and `GET /public/teams/{public_id}`.

**The 415 fires on a MISMATCH, not on absence.** Counterintuitive consequence: **pinning a
vendor type is strictly more brittle than sending a generic one** — a pin can go stale and
hard-fail, a generic header cannot. Pins buy server-side version determinism, so it is a real
trade, but every pin is a maintenance obligation and a *wrong* pin is worse than *no* pin.

The resource type is often **not guessable from the path**: the games endpoint wants
`public_team_schedule_event`, not the `public_game` any reader would guess. That guess is
exactly how the 415 gets encountered.

## Two Accept failures, two different status codes

| What's wrong with the Accept | Status |
|---|---|
| wrong **resource type** | **415** |
| stale **version** on the right type | **403** (the false-403 trap, `.claude/rules/auth-module.md`) |

Neither response mentions the header. A 415 looks like a removed/gated endpoint; a 403 looks
like credential expiry. On either, check the Accept against the endpoint doc BEFORE touching
credentials.

## How our client classifies a 415 (as of 2026-07-26, read-only audit)

`_send_with_retries` (`src/gamechanger/client.py`) drops 415 into the terminal
"Unexpected non-success status" branch → raises `GameChangerAPIError`, **not retried**. The
retry classification is CORRECT (415 is deterministic).

The **labelling** is not. `GameChangerAPIError` means "5xx after retries" everywhere else
(exception hierarchy in `.claude/rules/auth-module.md`; three client docstrings say so), and
every downstream caller treats it as transient:

- `morning_run.py` per-team → `result.transient += 1`, operator text says "5xx/connection"
- `morning_run.py` preflight → "transient error (rate-limit / 5xx / connection)"
- `scouting.py` → WARNING + skip the game/roster/schedule and continue

So a stale pin would present to the operator as a *transient* failure and, on the boxscore
path, as a team that silently crawls zero games. Note the asymmetry: the **403** path already
has a dedicated operator hint naming "Accept version pins"; the 415 path has none and its
wording actively misleads. Reported to team-lead 2026-07-26 as findings-only (no code change).

## Our own exposure (audit 2026-07-26)

Every vendor pin in `src/` matched its endpoint doc. Two call sites send **no** Accept override
and ride the browser-generic default — both benign given the rule above, both undeclared:

- `src/reports/generator.py::_fetch_public_team_info` — a raw `session.get` on
  `/public/teams/{public_id}` with no `accept=`. A SECOND path to an endpoint
  `src/gamechanger/team_resolver.py` pins with the vendor type.
- `POST /search` via `client.post_json`, which sets only `Content-Type`; `post-search.md`
  declares an `accept` (`search_results+json`) we never send.

Related: [[public-team-accept-header-inert]], [[client-id-rotation]].
