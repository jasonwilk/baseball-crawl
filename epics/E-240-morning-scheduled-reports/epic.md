# E-240: Morning-of-Game Scheduled Reports

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
A cron-invoked CLI (`bb report morning-run`) reads each LSB team's GameChanger
schedule, resolves each upcoming opponent to a GameChanger `public_id`, and
generates a fresh scouting report the morning of every game — reusing the
existing, untouched `generate_report()` pipeline. This is the forward feature of
the reports-first reframe (`docs/ROADMAP.md` §5 "Epic E"): it turns the manual
"generate-and-share" workflow into a scheduled one. This epic ships **operator**
alerts and run records only; coach-facing email delivery is deferred to a
follow-up epic (captured as IDEA-080).

## Background & Context
The product, as actually used, is reports-first: generate a one-off scouting
report for a GameChanger `public_id` and share the link (`docs/ROADMAP.md` §1,
CLAUDE.md L21). Epics A–D2 (E-234 through E-239) hardened the reports flow,
added run records + trust signals + quality gates, removed the temp-file
bridges, and removed the unused dashboard / member-sync / opponent-management
surfaces. Epic E is the payoff: an unattended morning run that produces a fresh
opponent report and surfaces its outcome to the operator.

Discovery (a four-expert fan-out plus a **live schedule-access probe that
passed**, 2026-06-17) settled the design. Key findings:

- **Schedule access is GO.** `GET /teams/{gc_uuid}/schedule` (Accept
  `event:list+json; version=0.2.0`) returns **200 at fan/follower level** (the
  operator only needs to FOLLOW a team), with future-dated games carrying
  `pregame_data` including `opponent_id` + `opponent_name`. The roadmap's
  "assumed" fan-access gate is now verified.
- **Two authenticated list-crawlers must be built, and neither exists
  post-E-239.** The only surviving schedule readers are public (free-text
  opponent names only), and the opponent-discovery machinery
  (`opponent_resolver.py`, `opponent_seeder.py`, etc.) was DELETED in E-239. So
  E-240-01 builds BOTH the authenticated schedule crawler AND the authenticated
  opponents-registry crawler (`GET /teams/{gc_uuid}/opponents`, paginated).
- **Opponents resolve from the SCHEDULE + the live registry, not a cache.**
  `pregame_data` carries `opponent_id` (the `root_team_id` namespace) but NOT
  `progenitor_team_id`, and `opponent_links` has no `progenitor_team_id` column,
  so the canonical UUID / `public_id` is reached by joining `opponent_id` to the
  live authenticated opponents registry to read `progenitor_team_id`, then
  `GET /teams/{progenitor_team_id}`. `opponent_id` must NEVER be fed to
  `GET /teams/{id}` (wrong namespace).
- **Rung (a) fires for upcoming opponents (probe-verified).** The F4 registry
  probe (2026-06-17) found 6/6 upcoming opponents present in the registry (it is
  NOT historical-only — GC populates `root_team_id` at scheduling time), 3/6
  carrying `progenitor_team_id` (auto-resolvable), 3/6 manual. ~50% auto-resolve,
  consistent with the roadmap's 64% aggregate estimate.
- **The data layer needs no new opponent DDL**: the dormant `opponent_links`
  table (migrations/001) already has the `root_team_id → public_id` mapping shape
  and the resolve-once `UNIQUE(our_team_id, root_team_id)` key (a LOCAL,
  per-owning-team key — see the operator-burden note in Goals). It is revived as
  the mapping store. Scheduler runs need a NEW `scheduled_report_runs` table
  (migration 005) — the existing `report_generation_runs` is 1:1 with a PRODUCED
  report and cannot represent unresolved / no-presence / deferred slots.

The operator's locked decisions (operator session 2026-06-13, `docs/ROADMAP.md`
§5 lines 434–483) bind this epic: admin-free (no team-management / opponent
registry UI), team list inline in the crontab, opponent mapping keyed on
`root_team_id` (never the typed name), and a three-way outcome that is never a
silent skip.

## Goals
- A cron-invocable `bb report morning-run [--date YYYY-MM-DD] [--dry-run] <team-urls...>`
  command that, for each team, reads the schedule, filters to the target date
  (deriving each game's LOCAL date from its UTC `start.datetime` + timezone),
  drops canceled games, resolves each upcoming opponent, and calls the existing
  `generate_report(public_id)` — **sequentially**, never concurrently.
- Two authenticated list-crawlers (new, both in E-240-01): the own-team schedule
  crawler and the opponents-registry crawler (`GET /teams/{gc_uuid}/opponents`,
  paginated), with the probe's findings pinned as regression tests.
- A persisted opponent resolution ladder (rungs a–d) so each opponent is
  resolved once **per team-opponent pairing** and cached, with a three-way
  outcome (auto-resolved / unresolved-but-mappable / no-GC-presence) that is
  always surfaced, never silently skipped.
- A `bb report map-opponent <root_team_id> <public_id|GC team URL>` command for
  the one-time operator resolution of unresolved-but-mappable opponents.
- A `scheduled_report_runs` audit table (migration 005) recording every
  scheduled slot and its outcome, surviving report expiry/cleanup.
- Operator alerting: a preflight-failure alert, an unresolved-but-mappable alert
  carrying the ready-to-run `map-opponent` command, and an always-sent
  end-of-run summary (so the absence of a summary is the missed-run signal),
  built on a generic Mailgun sender extracted from `src/api/email.py`.

**Operator-burden expectation (set deliberately).** The operator queue is larger
than the progenitor-present auto-resolve rate alone implies, for two compounding
reasons that are CORRECT behavior, not defects: (1) **per-team-opponent-pairing
(B15)** — `opponent_links`' key is `(our_team_id, root_team_id)`, so one real
opponent faced by multiple LSB teams must be mapped once per team (mapping
Bellevue West for Varsity does not auto-resolve it for JV); (2)
**tournament-queue pressure (B16)** — tournament/bracket/event names (e.g.
"Slumpbuster", a "Challenge") that escape the placeholder pattern fall through to
the operator queue by design, because an unknown bracket opponent genuinely
cannot be scouted. The TN-10 runbook note sets this expectation for the operator.

## Non-Goals
- **Coach-facing email delivery** — deferred to a follow-up epic (IDEA-080).
  This epic forwards report links to coaches manually (the operator does it).
  No `report_subscriptions`, no coach-content email.
- **Any change to expiry/freshness semantics.** The existing 14-day report
  expiry is kept as-is; no `source` column, no expiry extension, no
  stable "latest-per-opponent" URL (operator decision #1). The 14-day window
  already outlives game morning. (The stable-URL/extended-expiry option is
  captured in IDEA-080.)
- **Any modification to `generate_report()` / the protected-core generator
  pipeline.** Morning-run only CALLS it. See Technical Notes TN-1.
- **A heartbeat / missed-run paging detector.** Deferred; the always-sent
  end-of-run summary is the minimal missed-run signal (TN-9).
- **A tournament/event name pattern arms race.** The rung-(b) placeholder
  pattern is a best-effort heuristic; event names are unbounded and are handled
  by the three-way outcome, not by chasing an exhaustive pattern set (TN-3).
- **Admin / opponent-registry / team-management UI.** Operator decision #4 —
  unresolved opponents surface only in `--dry-run` output and the run record on
  the existing `/admin/reports` page.
- **The follow→bridge→unfollow resolver path.** Explicitly banned (it mutates
  external GC follow state against the wrong namespace; `.claude/rules/gc-uuid-bridge.md`).
- **Concurrent generation** (one invocation per team). Re-opens the
  `cleanup_orphan_teams` race the Epic B lock closed (TN-2).

## Success Criteria
- `bb report morning-run --dry-run <team-urls...>` prints, per team and per
  in-scope upcoming opponent, a line carrying the opponent text, its
  `opponent_id`, the three-way outcome, and — for resolved opponents — the
  RESOLVED team name + `public_id` + W-L record for one-time operator
  eyeball verification (TN-5). No report is generated in `--dry-run`.
- A non-dry run generates a report for each auto-resolved opponent via the
  existing `generate_report()`, records one `scheduled_report_runs` row per
  scheduled slot (idempotent per `(own_team_id, opponent_root_team_id,
  game_date)`), isolates per-game failures (one opponent's failure never aborts
  the loop), and sends an end-of-run operator summary email.
- `bb report map-opponent <root_team_id> <public_id|GC team URL>` resolves the
  pending `opponent_links` mapping keyed on `root_team_id` (updating every LSB
  team's pending row for that opponent), and a subsequent `morning-run`
  auto-resolves that opponent.
- The two authenticated list-crawlers (schedule + opponents) reproduce the probe
  assertions as passing regression tests (200 fan-level access shape, future +
  same-day games returned, canceled filter, `opponent_id`/`opponent_name`
  presence; opponents-registry pagination across the page boundary).
- The full test suite is green; Epic A golden stat tables and
  `bb report verify-aggregates` parity are unchanged (proven, not assumed —
  TN-1).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-240-01 | Authenticated list-crawlers (schedule + opponents-registry) + probe-confirmation tests | TODO | None | - |
| E-240-02 | Schedule endpoint doc + opponent-resolution flow-doc refresh | TODO | None | - |
| E-240-03 | Migration 005: `scheduled_report_runs` + cascade line; revive `opponent_links` as mapping store | TODO | None | - |
| E-240-04 | Opponent resolution ladder (rungs a–d) | TODO | E-240-01, E-240-03 | - |
| E-240-05 | `bb report map-opponent` CLI command | TODO | E-240-03, E-240-04 | - |
| E-240-06 | Generic Mailgun sender extraction + operator alerts | TODO | None | - |
| E-240-07 | `bb report morning-run` orchestration | TODO | E-240-01, E-240-03, E-240-04, E-240-05, E-240-06 | - |

## Dispatch Team
- api-scout
- data-engineer
- software-engineer
- code-reviewer

## Technical Notes

### TN-1: Protected-core boundary (the load-bearing safety constraint)
Morning-run is an **orchestration shell**: it parses team URLs, resolves
opponents, and CALLS the existing `generate_report(public_id)` in
`src/reports/generator.py`. The whole crawl→load→spray→plays→reconciliation→
render pipeline is reused untouched. **No story in this epic may modify
`generate_report()` or any stage method it calls.** The single exception is
E-240-03's additive cascade line (a `DELETE FROM scheduled_report_runs …`
appended to the canonical team-deletion cascade) — additive cleanup that does
not touch stat computation. Every story that runs code carries an AC that Epic A
golden stat tables (`tests/test_report_golden.py`) and
`bb report verify-aggregates` parity remain unchanged (proven by running the
relevant guards, not assumed). This is the `docs/ROADMAP.md` §6 safety rule: by
construction, the morning-run path keeps the goldens green because it never
enters the generator's internals.

### TN-2: Sequential execution invariant (load-bearing)
The morning run is ONE process iterating teams and opponents with a plain
sequential loop. It is a THIRD SQLite writer (admin-UI + CLI + cron on one
`data/app.db`). **Never concurrent / never one invocation per team.** Concurrency
re-opens the `cleanup_orphan_teams()` race the Epic B (E-235) concurrency lock
closed, duplicates credential refreshes, and breaks rate-limit coordination.
Sequential single-process respects the Epic B concurrency lock and the
`created_team_ids` orphan-attribution mechanism. The crontab line IS the config
(operator decision #1) — variadic team URLs as args, edited once a season. This
constraint is a load-bearing CR-inspection item on E-240-07 (a negative
structural invariant, asserted by review, not by a test). Because dispatch is
serial (not parallel), the actual file-collision risk is already mitigated; each
story's Files-to-Create-or-Modify list names specific paths (incl. named test
files) for ownership PROVABILITY, not to prevent parallel collisions (C4).

### TN-3: Opponent resolution ladder (per upcoming opponent, resolve-once-per-pairing)
Per upcoming game, take `pregame_data.opponent_name` + `opponent_id`. The
`opponent_id` is the `root_team_id` namespace (verified 54/54). Resolve via this
ordered ladder, persisting the result in `opponent_links` keyed on
`(our_team_id, root_team_id)` so each opponent resolves once **per team-opponent
pairing** (the key is local to the owning team — one real opponent faced by
several LSB teams needs one mapping per team; see the Goals operator-burden note):

- **Rung (a) — registry `progenitor_team_id` reverse bridge.** Join
  `opponent_id → root_team_id` in the LIVE authenticated opponents registry
  (`GET /teams/{own_team_gc_uuid}/opponents`, built in E-240-01), read that
  record's `progenitor_team_id`. Eligibility test MUST be **key-absent**
  (`"progenitor_team_id" in record`), NOT a truthiness/null check — the key is
  omitted on manual entries. If present, `GET /teams/{progenitor_team_id}`
  returns `public_id` directly for non-managed teams at fan level (verified).
  MUST NOT use `GET /teams/{id}/public-team-profile-id` (403s for non-managed).
  If the `opponent_id` is wholly absent from the registry (a defensive
  robustness case — observed 0/6 in the F4 probe, NOT the modal path), fall
  through; do not over-invest in this branch.
- **Rung (b) — placeholder deferral.** No structural flag exists; classify by
  name pattern (`TBD|TBA|Winner|Loser|Seed|Game \d|Pool|Bracket|Tournament|
  Invitational|Classic|Showcase`; optionally `Challenge` and similar tokens as
  best-effort). A placeholder is deferred and re-polled near game time — DON'T
  persist an `opponent_links` row, DON'T ask the operator. **By design,
  tournament/event names that escape this pattern set (e.g. "Slumpbuster", "Prep
  Baseball KC Challenge") are NOT chased with an ever-growing pattern — they fall
  through to rung (c)/(d) and land in the operator queue as unresolved-but-mappable
  (the operator may later declare no-GC-presence via `map-opponent --no-presence`).
  That is HONEST behavior (an unknown bracket opponent cannot be scouted), not a
  bug.**
- **Rung (c) — `POST /search` by name.** MUST route through
  `search_teams_by_name()` (`src/gamechanger/search.py`) — never
  `client.post_json("/search", …)` directly. Name source must be a real `name`
  field (registry entry / `GET /public/teams/...`), NEVER a URL slug (slug → 0
  hits). Auto-ingest ONLY on an unambiguous single match — a wrong-team
  false-positive silently scouts the wrong opponent. A zero-hit is ambiguous
  (punctuation quirk vs. genuinely unindexed) → fall to rung (d), not a hard
  failure.
- **Rung (d) — operator queue.** Otherwise → unresolved-but-mappable: PERSIST a
  not-resolved `opponent_links` row (`our_team_id` + `root_team_id` +
  `opponent_name`; `public_id` NULL, `resolution_method` NULL) so
  `bb report map-opponent` (E-240-05) has a pending row to UPDATE; surface in
  `--dry-run` and the run record; accept a pasted `public_id` or GC team URL.
  **The auto-ladder NEVER emits `no_gc_presence`** — a zero-hit/no-match is always
  ambiguous, so an unmatched opponent stays `unresolved_mappable` indefinitely
  until the operator acts. The `no_gc_presence` (resolved-negative) state is
  OPERATOR-DECLARED ONLY, via `bb report map-opponent <root_team_id> --no-presence`
  (E-240-05) once the operator confirms the team is genuinely not on GameChanger.
  (C1 decision, Option a — coach + de unanimous.)

`opponent_links` three states (read from `public_id` + `resolution_method` ONLY):
not-resolved (`public_id NULL AND resolution_method NULL`), resolved-positive
(`public_id NOT NULL`, method in `progenitor`/`search`/`operator`),
resolved-negative/no-presence (`public_id NULL AND resolution_method='no_presence'`,
operator-declared). **A NULL `resolved_team_id` on a resolved-positive row is NOT
"not resolved"** (resolution can precede team-row creation) — the three states key
on `public_id` and `resolution_method` only, never on `resolved_team_id`.
**Terminality / resolve-once gate (C1, de-critical):** the "is this opponent
already resolved? stop re-attempting" gate MUST key on `resolution_method IS NOT
NULL` (covers BOTH resolved-positive AND operator-declared no_presence) — NOT on
`public_id IS NOT NULL`. A no_presence row has `public_id` NULL by design, so a
public_id-based gate would RE-QUEUE and RE-ATTEMPT it every morning run (the
resurrection bug). This is DISTINCT from the `scheduled_report_runs`
per-`(team,opponent,date)` regeneration skip in TN-9 (that governs report
regeneration; this governs ladder re-resolution) — keep both. Placeholders
persist NO row. Leave `is_hidden` alone.

### TN-4: 403 is overloaded — three meanings + version pins
An unattended run MUST distinguish three meanings of a 403, never auto-classify
every 403 as auth-expiry (which would mask a real auth failure as "no report
possible"): **auth-expiry** (handled by the preflight refresh and re-raised
visibly), **version-pin mismatch** (a wrong `Accept` version yields a FALSE
403), and **legitimate denial** (genuine access denied). Pin each endpoint's
`Accept` version correctly:
- schedule: `event:list+json; version=0.2.0`
- opponents registry: `opponent_team:list+json; version=0.0.0` (paginated —
  `start_at` cursor via the `x-next-page` response header; page size ~50, so a
  multi-season LSB team REQUIRES pagination — load-bearing, not optional)
- search: `post_search+json; version=0.0.0`
- rung-(a) reverse bridge `GET /teams/{progenitor_team_id}`: `team+json;
  version=0.10.0` (NOTE: this is `team+json` — DISTINCT from `/me/teams`'
  `team:list+json`; a wrong pin here yields a FALSE 403 that would wrongly mark
  an otherwise-resolvable opponent "no report possible")
- `/me/teams` (if used): `team:list+json; version=0.10.0`

CR-checklist line: every authenticated call in this epic asserts the correct
version pin and does not collapse all 403s into "auth expired".

### TN-5: Three-way outcome + wrong-mapping mitigation
Every scheduled opponent resolves to exactly one of: **auto-resolved** (rungs
a–c, or a prior operator mapping; report generated), **unresolved-but-mappable**
(on GC but not auto-matched; surfaced for one-time `map-opponent`),
**no-GC-presence** (operator-declared via `map-opponent --no-presence`; "no report
possible" — the auto-ladder never sets this, per TN-3); a placeholder is a fourth,
transient **deferred** state. Never a silent skip. The exact mapping of a ladder
return to the persisted vocabulary (`scheduled_report_runs.resolution_outcome`,
`opponent_links.resolution_method`, `delivery_status`) is in TN-11.
**Wrong-mapping mitigation (MUST):** `--dry-run` output prints, next to the
opponent text, the RESOLVED team name + `public_id` + W-L record (e.g.
`→ RESOLVED: Bellevue West HS (Bellevue, WA) [public_id: …] — record 12-8`) so the
operator eyeballs the mapping once before trusting it forever. The resolved team
name/city/state/record for this line comes from the SAME `resolve_team(public_id)`
helper (`src/gamechanger/team_resolver.py`, fields `name`/`city`/`state`/
`record_wins`/`record_losses`) used for own-team resolution (C3) — one helper, two
uses (own-team gc_uuid resolution and opponent dry-run display). `TeamProfile` has
no total-games field, so the line shows the W-L record, not a game count (D4).
For unresolved-but-mappable, emit a prominent CLI line AND an operator alert
carrying a TEMPLATE `bb report map-opponent <root_team_id> <PASTE-GC-TEAM-URL>`
command — `root_team_id` pre-filled, the URL an explicit placeholder the operator
completes after looking up the team (D1) — (TN-7). The `--date` override + a
runbook note (operator education, not code)
handle early-start tournaments (~9am); the 6am default fits weekday HS/Legion
4–7pm starts.

### TN-6: Data layer (one migration — 005)
- **`scheduled_report_runs` (NEW table, migration 005).** Columns the table MUST
  support: `id` PK; `game_date`; `own_team_id` FK `teams(id)`;
  `opponent_root_team_id TEXT` (the `root_team_id` registry namespace — NO FK, it
  is the GC namespace, NOT a `gc_uuid` column); `opponent_name`;
  `resolution_outcome` CHECK in (`auto_resolved`, `unresolved_mappable`,
  `no_gc_presence`, `deferred_placeholder`); `resolved_public_id`; `report_id`
  FK `reports(...)` **ON DELETE SET NULL** (NOT cascade — the audit log must
  outlive report cleanup/expiry); `report_slug` (frozen-string audit fallback);
  `delivery_status` (CHECK in (`generated`, `no_games`, `failed`, `skipped`);
  NULLABLE — NULL means generation was not attempted, and `resolution_outcome`
  explains why; see TN-11); `error_message`; `created_at`; `updated_at`.
  **Idempotency:** `UNIQUE INDEX (own_team_id, opponent_root_team_id, game_date)`
  with UPSERT on conflict. **NULL footgun:** SQLite treats NULLs as DISTINCT in
  UNIQUE indexes, so the loader MUST guarantee a non-NULL key on all three
  columns (fall back to the `opponent_id` token when `opponent_root_team_id`
  would be null), or idempotency silently breaks. Migration follows
  `.claude/rules/migrations.md` (idempotent `CREATE TABLE IF NOT EXISTS` /
  `CREATE INDEX IF NOT EXISTS`, parenthesized `datetime()` defaults,
  concatenation-safe for `conftest.load_real_schema`).
- **Cascade mirror invariant + audit survival.** Adding `scheduled_report_runs`
  requires the canonical team-deletion cascade in `src/reports/generator.py` (the
  `_delete_team_scoped_data` DELETE set referenced in `.claude/rules/data-model.md`
  "Cleanup-Detection Mirror Invariant") to gain a
  `DELETE FROM scheduled_report_runs WHERE own_team_id IN (...)` in the SAME
  story that adds the table. Distinctly, a `scheduled_report_runs` row MUST
  SURVIVE report deletion (`_delete_report`) with its `report_id` nulled (the
  ON DELETE SET NULL behavior) — the deliberate mirror-image of E-235's "run row
  gone after report delete"; a test asserts this so an implementer does not copy
  the CASCADE pattern and destroy the audit trail. `opponent_links` is already in
  the team-deletion cascade — reviving it needs no new cascade work.
- **`opponent_links` revival (NO new DDL).** The dormant table (migrations/001)
  is the mapping store. Writers: the auto-ladder (E-240-04) persists
  resolved-positive / not-resolved rows (it NEVER writes resolved-negative — C1);
  `map-opponent` (E-240-05) UPDATEs pending not-resolved rows to resolved-positive,
  or — with `--no-presence` — to operator-declared resolved-negative. All writers
  set `resolved_at` on a positive/negative resolution. Document the revival
  convention in a code/migration doc-comment only (the `.claude/rules/data-model.md`
  update is a closure context-layer obligation — TN-10).

### TN-7: Mailgun sender extraction + operator alerts
- **Extract a generic async sender** from `src/api/email.py` (today it hardcodes
  the magic-link subject/body in `send_magic_link_email`): a behavior-preserving
  refactor that introduces a generic `send_email(to, subject, body)`-shaped
  async function and re-expresses `send_magic_link_email` as a thin caller of it.
  Keep `send_magic_link_email`'s existing tests green (its behavior — including
  the no-`MAILGUN_API_KEY` stdout fallback — is unchanged). First new caller =
  operator alerts.
- **Exactly three operator alerts (operator-only, no coach content):** (1)
  preflight credential-refresh FAILURE — fail early and visibly; (2)
  unresolved-but-mappable — carries the ready-to-run `map-opponent` command
  (TN-5); (3) an **always-sent end-of-run summary** (success/fail counts) so the
  absence of a summary is the missed-run signal (TN-9). **There is no fourth
  per-game-failure alert** — a per-game failure (e.g. all-boxscores-blocked →
  `failed`) is surfaced via the end-of-run summary, not a dedicated helper.
  morning-run is a sync CLI; calling the async sender needs an
  `asyncio.run()`-style wrapper.
- **Recipient (C2):** all operator alerts go to `ADMIN_EMAIL` — the established
  operator-identity env var (`src/api/auth.py`, CLAUDE.md); no new config var. If
  `ADMIN_EMAIL` is unset, log a visible warning and SKIP the alert — do NOT crash
  the run (alerting is a side channel, not the work).

### TN-8: Hard gates (do not generate / no link)
- **Zero completed games** — extend the existing E-235/E-236 no-games gate to
  scheduled mode (a scheduled opponent with no completed games yields the
  explicit no-games outcome, not an empty "ready" report).
- **All-boxscores-blocked → hard `failed`** — already in E-236; confirm it gates
  scheduled delivery (surfaced via the end-of-run summary per TN-7; no shareable
  link). "We were blocked" ≠ "no data exists".
- **Placeholder opponent** (TBD/Winner/Seed…) — don't generate; defer and
  re-poll (TN-3 rung b).
These gates are enforced by `generate_report()` (already built); E-240-07's job
is to honor their outcomes in the run record and operator surfacing, not to
re-implement them.

### TN-9: Cron mechanics
No APScheduler, no long-lived process — host cron invokes the CLI (survives app
restarts, no new runtime dependency). **Preflight credential check ONCE** at the
top of the run: actively validate token liveness against a lightweight
authenticated endpoint (forcing the lazy token-manager refresh), and on an
unrecoverable auth failure (refresh + login fallback both fail) send the
preflight-failure operator alert (TN-7) and abort early/visibly. The 14-day web
refresh token has lapsed in this project's history, so this preflight is
load-bearing and its failure-path test mocks the refresh failure explicitly. The
preflight-refreshed credentials MUST feed the SAME client/session the crawlers
and the resolution ladder use. **Per-game try/except isolation:** one opponent's
failure records to the run table (`error_message`) and the loop continues; it
never aborts the run. **Idempotency per `(team, opponent, date)`:** before
generating, check `scheduled_report_runs` for the UNIQUE key; treat a prior
SUCCESS as a skip — the success predicate is a row with `resolution_outcome =
'auto_resolved'` AND a non-NULL, non-expired `report_id` (then `delivery_status
= 'skipped'` on the re-run). **Missed-run signal:** cron cannot detect a
no-show, so the minimal mechanism is the always-sent end-of-run summary (TN-7) —
absence of the summary is the signal. A heartbeat detector is heavier and is
DEFERRED (Non-Goals).

### TN-10: Roadmap tracking + closure obligations
This is a `docs/ROADMAP.md` §5 Epic E (slice E) epic — see the `## Roadmap`
section. Closure obligations (NOT stories):
- The §0 Roadmap Tracking table row for slice E flips `— / NOT STARTED` →
  `E-240 / PLANNING` at the planning commit (main session makes the doc edit)
  and → `COMPLETED` at closure.
- Documentation assessment at closure: `docs/admin/operations.md` gains a
  morning-run runbook section (cron line, `--date` override for early-start
  tournaments, `map-opponent` workflow, reading the end-of-run summary, **and the
  operator-burden expectation: tournament-heavy schedules and the
  per-team-opponent-pairing mapping key both enlarge the operator queue — by
  design**). Owner: docs-writer. The schedule endpoint doc and the
  opponent-resolution flow doc are updated by E-240-02 (api-scout owns) during
  the epic, not at closure.
- Context-layer assessment at closure: `.claude/rules/data-model.md` documents
  the `scheduled_report_runs` table, the `opponent_links` revival, and the
  idempotency NULL footgun; CLAUDE.md Commands section gains
  `bb report morning-run` and `bb report map-opponent`. Owner: claude-architect.

### TN-11: Outcome vocabulary mapping (single source for B9)
E-240-07 maps each resolution result to the persisted vocabulary using this table
(referenced by E-240-07 AC-3). The three persisted columns live in two tables:
`scheduled_report_runs.resolution_outcome` and `.delivery_status` (per slot),
and `opponent_links.resolution_method` (per mapping). Note the producer column:
the auto-ladder produces rows 1–2 and 4–5; the operator (`map-opponent`) produces
rows 3 and 6 — **the auto-ladder NEVER produces `no_gc_presence`** (C1).

| Resolution result (producer) | `resolution_outcome` (scheduled_report_runs) | `opponent_links` state (`resolution_method`) | `delivery_status` (after the slot is processed) |
|---|---|---|---|
| Ladder rung (a) progenitor chain | `auto_resolved` | resolved-positive (`progenitor`) | `generated` / `no_games` / `failed` / `skipped` |
| Ladder rung (c) search single match | `auto_resolved` | resolved-positive (`search`) | `generated` / `no_games` / `failed` / `skipped` |
| Prior operator `map-opponent` (positive) | `auto_resolved` | resolved-positive (`operator`) | `generated` / `no_games` / `failed` / `skipped` |
| Ladder rung (b) placeholder | `deferred_placeholder` | no row persisted | NULL (not attempted) |
| Ladder rung (d) unresolved-but-mappable | `unresolved_mappable` | not-resolved (`resolution_method` NULL, `public_id` NULL) | NULL (not attempted) |
| Operator `map-opponent --no-presence` | `no_gc_presence` | resolved-negative (`resolution_method='no_presence'`, `public_id` NULL) | NULL (not attempted) |

`delivery_status` is non-NULL only when generation was attempted (an
`auto_resolved` slot); `resolution_outcome` carries the reason for every
non-attempt. For a non-attempt slot, `scheduled_report_runs.resolved_public_id`
and `.report_id` are both NULL (the CHECK and FK already permit this; UPSERT
handles re-runs; no cascade interaction).

## Roadmap
Implements `docs/ROADMAP.md` §5 **Epic E — Morning-of-game scheduled reports**
(slice **E**), the forward feature of the reports-first reframe. Per the §0
Roadmap Tracking convention, the §0 table row for slice E is updated to
`E-240 / PLANNING` at the planning commit and `E-240 / COMPLETED` at closure
(main session makes the `docs/ROADMAP.md` edits — see TN-10). Design is bound by
§5 lines ~364–483 (the Epic E scope + the 2026-06-13 operator-session
decisions).

## Open Questions
- None blocking. The `opponent_id → root_team_id → progenitor_team_id` join, the
  schedule fan-access gate, and the rung-(a) fire rate on upcoming opponents
  (F4: 6/6 present, 3/6 progenitor-resolvable) are all probe-verified; the
  1-team schedule probe sample is strong enough to commit the design, and
  E-240-01's own crawler run is the second confirmation (a regression-test AC,
  not a blocking spike).

## History
- 2026-06-17: Created (DRAFT). Discovery complete (four-expert fan-out + a live
  schedule-access probe + an F4 registry probe that passed, 2026-06-17).
  Coach-facing email delivery deferred to IDEA-080.
- 2026-06-17: Phase 3 internal review (CR spec audit + 4 holistic domain
  reviews) incorporated — 16 findings (B1–B16), all accepted. Notable: the
  opponents-registry crawler folded into E-240-01 (B1); the
  `map-opponent`-updates-pending-row mechanics + new E-240-04→05 dep (B4);
  timezone-aware local-date filtering (B3); the TN-11 outcome-vocabulary mapping
  (B9); and the operator-burden framing (B15 + B16). Closure obligation: flip
  `docs/ROADMAP.md` §0 slice E row to COMPLETED (TN-10).
- 2026-06-17: Phase 4 Codex spec review incorporated — 5 findings (C1–C5), all
  accepted. C1 (RULED Option a, coach + de unanimous): `no_gc_presence` is
  OPERATOR-DECLARED only via `map-opponent --no-presence`; the auto-ladder never
  emits it; the terminality/resolve-once gate keys on `resolution_method IS NOT
  NULL` (not `public_id`) to avoid the no_presence resurrection bug. C2: operator
  alerts → `ADMIN_EMAIL` (unset → warn+skip, no crash). C3: own-team
  `public_id → gc_uuid` reuses `team_resolver.resolve_team` + `search_teams_by_name`
  in E-240-01 (no generator.py edit); same helper feeds the dry-run opponent
  display line. C4: story Files lists tightened to specific paths. C5: E-240-02
  ACs trimmed to the real doc delta.
- 2026-06-17: Phase 4 Codex spec review iteration 2 incorporated — 5 findings
  (D1–D5), all accepted (operator chose fix+READY at the iteration-2 circuit
  breaker). D1: the unresolved-mappable alert carries a TEMPLATE
  `map-opponent <root_team_id> <PASTE-GC-TEAM-URL>` (root_team_id pre-filled, URL a
  placeholder — the URL is the operator's lookup). D2: E-240-07 AC-11 reconciled
  with the warn+skip rule ("always sent when `ADMIN_EMAIL` configured"). D3:
  scrubbed `no-GC-presence` as a ladder outcome from E-240-04 Description+Handoff +
  TN-3 (it is operator-declared only). D4: the dry-run line shows the W-L record
  (`record_wins`/`record_losses`), not a game count (`TeamProfile` has no
  games field) — no `team_resolver` change. D5: E-240-07 AC-9 placeholder outcome
  → `deferred_placeholder` (matches the CHECK/TN-11 vocabulary). Tightened
  consistency sweep (underscore + hyphen/space variants) clean; two stragglers it
  surfaced (Success-Criteria "game count", TN-5 old `<url>` command) fixed.
- 2026-06-17: **Status → READY.** All review passes incorporated; consistency
  sweep clean. Review scorecard:

  | Review pass | Findings | Accepted | Dismissed |
  |---|---|---|---|
  | Internal iter-1 (CR spec audit + 4 holistic domain reviews) | 16 (B1–B16) | 16 | 0 |
  | Codex spec review iter-1 | 5 (C1–C5) | 5 | 0 |
  | Codex spec review iter-2 | 5 (D1–D5) | 5 | 0 |
  | **Total** | **26** | **26** | **0** |

  Awaiting dispatch authorization (separate from READY). Closure obligation
  (TN-10): main session flips `docs/ROADMAP.md` §0 slice E → `E-240 / PLANNING` at
  the planning commit, and → `COMPLETED` at epic closure.
