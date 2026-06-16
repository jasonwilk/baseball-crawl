# E-238: D1 — Quarantine + Navigation Retarget + Passkey Fix

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Execute roadmap slice **D1**: quarantine the unused surfaces (dashboard, member-team sync,
opponent discovery) so no future work is routed to them, retarget all navigation off the
quarantined `/dashboard` onto the live `/admin/reports` surface, fix the passkey-challenge
store so login survives multiple workers and restarts, and add expired-report file cleanup.
This makes the reports-first reframe (the product as actually used) the navigable default
and hardens the operator's real login path — **without deleting any code or tables** (that
is D2).

## Background & Context
The product is reports-first: log in → generate a one-off scouting report for a GameChanger
`public_id` → share the link. Roughly 25-30% of the codebase serves surfaces nobody uses
(dashboard, member-sync orchestration, opponent-management admin UI). D1 is the
**quarantine-ONLY** first half of the cleanup: mark deprecated, stop maintaining, exclude
from parity rules — but defer all deletion and import-decoupling to D2. D1 also lands the two
real code changes the reframe needs (navigation retarget + passkey fix) plus expired-report
cleanup, because today's auth success paths land the operator on the quarantined dashboard
and the passkey store is single-worker-only.

Three domain experts (software-engineer, data-engineer, claude-architect) analyzed D1 during
discovery; their findings are folded into the Technical Notes and stories below. Key
corrections from discovery vs. the roadmap text: there are **five** auth.py redirect sites
(not four), the next migration is **004** (not 002 — `.claude/rules/migrations.md` is stale;
the live `migrations/` dir is authoritative), and several protected-core seams *look*
dashboard-owned by name but must NOT be quarantined (see Risks).

**No api-scout consultation needed** despite story 03 codifying a GameChanger identifier-namespace
ban: the relevant API facts (`root_team_id` ≠ `gc_uuid` namespace; the follow endpoint mutates
external GC state) are ALREADY established and verified in `CLAUDE.md` "Opponent entry duality"
and `docs/ROADMAP.md` §4. Story 03 codifies these existing verified facts into a durable ban — it
does not discover new API behavior, so the api-scout consultation trigger does not fire.

## Roadmap
Implements `docs/ROADMAP.md` §5 slice **D1** ("Quarantine + navigation retarget"). Per the
§0 Roadmap Tracking convention, the §0 table was flipped to `E-238` / `PLANNING` at this
epic's planning commit; it flips to `COMPLETED` at epic closure. Scope boundaries are
governed by §3 (Protected Core), §4 (Cruft verdicts), §6 (Safety Rules), and §7 (Non-Goals).

## Goals
- Every quarantined surface carries a durable deprecation marker (code banner + context-layer
  rule) so future work is never routed into it.
- The follow→bridge→unfollow `resolve_unlinked()` path (mutates external GameChanger state
  against the wrong namespace) is banned first and most loudly — code banner + context-layer.
- No navigation entry point lands a user on `/dashboard`; the operator's login → generate →
  share path is fully on `/admin/reports`.
- Passkey challenges live in a TTL'd SQLite table that survives multiple workers and app
  restarts, with login behavior byte-identical to today.
- Expired report HTML files are cleaned off disk (the `reports` row is kept, marked expired).

## Non-Goals
- **No deletion of any code, route, template, table, or CLI command.** All removal and
  import-decoupling is D2.
- No change to report stat values, the generation pipeline's stages, or query semantics.
- No quarantine marking of protected-core seams (see Risks — these LOOK dashboard-owned but
  serve the reports flow).
- No touching `.claude/rules/data-model.md` "Season-Aggregate Parity" or the
  `canonical_recompute` / `bb report verify-aggregates` aggregate-integrity machinery — those
  are Epic C concerns, not surface parity (naive-grep trap; see Technical Notes).
- No new background jobs, schedulers, or runtime dependencies for cleanup or challenge TTL.

## Success Criteria
- All quarantined `src/**` surfaces carry deprecation banners that say "stop maintaining, NOT
  delete" and point to the central quarantine rule (no root README exists — the top-level signal
  is the CLAUDE.md pointer per Technical Notes).
- `.claude/rules/quarantine.md` exists, is path-scoped to the quarantined surfaces, states the
  four quarantine semantics, names the `resolve_unlinked()` ban as highest priority, and
  carries the "quarantine ≠ delete (deletion + import decoupling is D2)" caveat.
- The four surface/delivery parity rule sites are amended to reflect quarantine; the
  Season-Aggregate Parity rule and aggregate-integrity references are demonstrably untouched.
- No reachable navigation path (root redirect, auth success redirects, passkey templates,
  error pages, base-template bottom nav on `/admin/reports`) sends a user to `/dashboard`.
- Passkey login and magic-link login challenges are stored/consumed via migration-004's
  `webauthn_challenges` table, replay-proof, and readable across connections (multi-worker
  proof); the full live login canary is the manual operator post-merge check.
- Expired reports have their HTML files unlinked (row kept) via a single helper, reachable
  both opportunistically at generation start and via `bb report cleanup`.
- The login → generate → share canary is verified per the "Canary verification mechanism"
  (Technical Notes) on every story touching the auth/redirect/passkey/generate path — the
  testable half (redirect targets, seeded report serving) in-worktree, the live half as a
  manual operator post-merge check; full test suite green at closure.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-238-01 | Create the central quarantine rule + context-layer pointers | DONE | None | - |
| E-238-02 | Amend surface/delivery parity rules for quarantine | DONE | E-238-01 | - |
| E-238-03 | Add the `resolve_unlinked()` context-layer ban | DONE | E-238-01 | - |
| E-238-04 | Add code deprecation banners to quarantined surfaces | DONE | E-238-01 | - |
| E-238-05 | Retarget all navigation off `/dashboard` | DONE | None | - |
| E-238-06 | Move passkey challenges to a TTL'd SQLite table | DONE | E-238-05 | - |
| E-238-07 | Expired-report file cleanup | DONE | None | - |

**Dependency notes**: 02 depends on 01 because both edit `CLAUDE.md` (01 adds the pointer line,
02 amends parity sections — serial ordering avoids a staging-boundary collision). 06 depends on
05 because both edit `src/api/routes/auth.py` (05 retargets redirects, 06 replaces the passkey
challenge store). 03 and 04 depend on 01 because they reference the quarantine rule it creates.

## Dispatch Team
- claude-architect
- software-engineer
- data-engineer

## Technical Notes

### Quarantine semantics (the four meanings)
Quarantine means a surface is: (1) **deprecated**, (2) **unmaintained** (no upkeep beyond
keeping the app booting), (3) **excluded from new-feature parity requirements**, and (4)
**closed to new feature work** (a story that would route new work here escalates to PM).
Quarantine is explicitly **NOT deletion** — deletion plus import decoupling is D2. No banner,
comment, or rule may read as a delete-license.

### Surfaces to quarantine (code-side banners, story 04)
- Dashboard: `src/api/routes/dashboard.py` + the dashboard Jinja templates.
- Member-team sync: `src/pipeline/crawl.py`, `src/pipeline/load.py`, `src/pipeline/bootstrap.py`,
  and `run_member_sync` in `src/pipeline/trigger.py`.
- Opponent discovery: `src/gamechanger/loaders/opponent_seeder.py` (loaders/, NOT crawlers/),
  `src/gamechanger/crawlers/opponent_resolver.py`, and `run_scouting_sync` (a FUNCTION-level
  banner in `src/pipeline/trigger.py`, alongside `run_member_sync` — NOT a module banner).
- The `resolve_unlinked()` follow→bridge→unfollow functions get the **highest-priority**
  in-code banner (its context-layer half is story 03).
- **No root README quarantine note**: there is no `/workspaces/baseball-crawl/README.md` at the
  repo root (the roadmap §5 D1 "README note" assumed one exists). The top-level human/agent-visible
  quarantine signal is the `CLAUDE.md` pointer to the quarantine rule (story 01 AC-5) — we do NOT
  create a project README as a side effect of a quarantine epic.
- **Protected-core scouting modules must NOT be module-bannered**: `crawlers/scouting.py`,
  `loaders/scouting_loader.py`, and the shared `GameLoader`/`PlaysLoader` serve the reports
  flow. Banner only the quarantined functions (`run_scouting_sync`), not these modules.
- **Member-ONLY loaders** (`loaders/` schedule/roster/season-stats) are NOT file-level marked
  in D1 — they share `GameLoader`/`PlaysLoader`/`ScoutingLoader` protected-core code. File-level
  inventory and markers for them are DEFERRED to D2 (documented decision per roadmap, not an
  oversight).

### Parity-rule amendment sites (story 02 — claude-architect core deliverable)
Amend these FOUR surface/delivery parity sites to reflect that both sides (or the consuming
surface) are quarantined and parity-excluded:
1. `CLAUDE.md` "Scouting pipeline parity" — both sides quarantined; annotate FROZEN/inert,
   not a forward constraint.
2. `CLAUDE.md` "Shared query functions" — dashboard quarantined; reword so NEW cross-surface
   needs target reports only, while preserving the pattern for protected-core seams still
   serving both surfaces.
3. `.claude/rules/scouting-data-flows.md` "Feature parity principle" — add a top-of-file
   QUARANTINE banner; rewrite so reports is the SOLE forward surface.
4. `.claude/rules/key-metrics.md` `get_pitching_workload()` parity requirement — soften to
   frozen; KEEP the shared function (protected core in `src/api/db.py`); note the dashboard
   CONSUMER is quarantined; drop forward parity framing.

**EXPLICIT NON-TARGETS (do NOT touch — naive grep on "parity" grabs these):**
`.claude/rules/data-model.md` "Season-Aggregate Parity" (aggregate-integrity / Epic C),
`CLAUDE.md` `canonical_recompute` bullet, and `CLAUDE.md` `bb report verify-aggregates` —
these are aggregate-integrity, not surface parity.

### Navigation retarget inventory (story 05 — SE discovery)
All retargets go to `/admin/reports`. Sites:
- **Route redirects in `src/api/routes/auth.py`** (FIVE, not four): the two GET `/login`
  already-authenticated redirects; the GET `/verify` magic-link success `/dashboard` branch
  (change only that branch — leave the `/auth/passkey/prompt` branch); the POST
  `/passkey/register` success JSON `redirect`; the POST passkey-login success JSON `redirect`.
- **Root redirect**: `src/api/main.py` `root_redirect()`.
- **Templates**: `auth/passkey_prompt.html` "Skip for now" href; `auth/passkey_register.html`
  "Cancel" href; `admin/reports.html` header's own Dashboard nav link (recommend REMOVING
  since the dashboard is quarantined — PM ruling: remove it).
- **`is_admin_page` threading**: the `list_reports` route (`src/api/routes/admin.py`) is the
  one admin route NOT passing `is_admin_page=True`, so `base.html`'s bottom fixed nav (3
  `/dashboard*` links) renders on `/admin/reports`. Fix by adding `"is_admin_page": True` to
  that route's context dict (no template edit).
- **Error pages** (`errors/404.html`, `errors/forbidden.html`, `errors/500.html` "go to
  dashboard" buttons): PM ruling — retarget for canary consistency.
- **OUT OF SCOPE (D2 churn)**: the six soon-removed admin templates' header links — do NOT
  retarget in D1. **Exception (in scope for story 05)**: the auth.py in-function redirect
  docstrings (~lines 245/251/369/604) describe the EXACT redirect behavior story 05 changes, so
  they ARE retargeted/updated in 05 (story 05 AC-7) to stay accurate. The six D2 admin-template
  header docstrings remain out of scope.

### Passkey challenge store (story 06 — DE/SE)
Replace the two module-global dicts (`_PASSKEY_LOGIN_CHALLENGES`,
`_PASSKEY_REG_CHALLENGES`) in `src/api/routes/auth.py` with migration **004**'s
`webauthn_challenges` table. Schema: `(kind TEXT CHECK(kind IN ('login','registration')),
lookup_key TEXT, challenge TEXT, expires_at TEXT NOT NULL DEFAULT (datetime('now','+5 minutes')),
created_at TEXT DEFAULT (datetime('now')), PRIMARY KEY(kind, lookup_key))` plus an index on
`expires_at`. **SQLite column defaults that call functions MUST be parenthesized** — a bare
`DEFAULT datetime(...)` is a syntax error. The migration uses `CREATE TABLE/INDEX IF NOT EXISTS`
(concatenation-safe for `conftest.load_real_schema`, which globs and concatenates all
migrations — no conftest edit needed).
Login is keyed by the challenge itself (anonymous, no session, matches today); registration is
keyed by the session-id hash with repeat-GET overwrite via `ON CONFLICT DO UPDATE`. No FK / no
`user_id`. TTL uses SQLite `datetime` text consistently (aligns with `sessions` /
`magic_link_tokens`) — never epoch floats. TTL enforcement = BOTH cleanup-on-read (DELETE the
consumed row after py_webauthn verifies — replay-proof, mirrors today's `pop`) AND
sweep-on-write (`DELETE WHERE expires_at <= datetime('now')` at each create — replaces
`_purge_expired_challenges`). No background job. Extract a `src/api/passkey_challenges.py`
helper (store/get/consume/sweep) keeping SQL out of route handlers and unit-testable.

**Login lookup-key MUST stay byte-identical**: the current derivation rebuilds the key from
`clientDataJSON.challenge` (urlsafe_b64decode with padding → standard b64encode round-trip).
That derivation is preserved exactly; a unit test asserts byte-identical output. py_webauthn
remains the crypto check — the DB only gates live-and-unconsumed.

### `bb report cleanup` / opportunistic cleanup (story 07 — SE)
Add `cleanup_expired_reports()` in `src/reports/generator.py`: SELECT expired rows
(`expires_at < now`) with `report_path NOT NULL`, unlink each file with per-file error
isolation (model the existing `_delete_report` `.is_file()`-guarded `.unlink()` and canonical
`_REPO_ROOT` resolution), then NULL `report_path` — but KEEP the `reports` row so the list
still shows "expired". Trigger it opportunistically at the start of `generate_report()` AND via
a new `bb report cleanup` CLI command (`src/cli/report.py`); both reuse the one helper.

### Canary path (Safety Rule §5)
"Login → generate → share" is the canary. Every story touching the auth/redirect/passkey/
generate path (05, 06, 07) carries an explicit canary AC. Note the auth-scope shift in Risks.

**Canary verification mechanism (the canary AC is split into a testable half + a manual half)**:
the epic worktree has no live GC credentials or pipeline, and per-story worktree pytest is barred
(code-reviewer verifies by file inspection). So each canary AC splits into:
1. **Automated (testable in-worktree)**: a route test using the existing mocked-GC/auth patterns
   (`TestClient`) asserting the redirect `Location` contains no `/dashboard`, and that a seeded
   `reports` row's share link serves via the existing serve/404 route. Report tests already mock
   GC — reuse those patterns.
2. **Manual (post-merge operator check)**: the full live login → generate → open-share-link
   end-to-end is designated an operator verification after merge, not an in-worktree AC.

### §0 Roadmap Tracking flip at closure
At epic closure the `docs/ROADMAP.md` §0 D1 row flips from `PLANNING` to `COMPLETED`. This is a
planning-artifact edit authored by PM during the closure staging so it rides the closure patch
(consistent with E-234's pattern).

## Risks
- **Auth-scope shift (biggest canary risk)**: `/dashboard` was reachable by ANY authenticated
  user; `/admin/reports` requires admin (`_require_admin`). After retarget, a logged-in
  NON-admin lands on a 403. Acceptable for the single-operator product, but the canary AC must
  verify the operator account IS admin. Redirects do not bypass auth (no redirect loop —
  confirmed in discovery).
- **Byte-identical login lookup-key**: the passkey-login lookup-key normalization
  (`clientDataJSON.challenge` round-trip) is a silent-break risk #1. A unit test must assert
  byte-identical derivation against the current code.
- **Protected-core seams that must NOT be quarantined** (they look dashboard-owned by name but
  serve the reports flow): `src/api/helpers.py` (report Jinja filters), `src/charts/spray.py`
  (both surfaces), `get_pitching_workload` / `get_pitching_history` / `build_pitcher_profiles`
  in `src/api/db.py`, and the year-only/current-season derivation in
  `derive_season_id_for_team()`. Banners and rule edits must not touch these.
- **Quarantine ≠ delete**: import coupling (`admin.py` → `trigger` → `crawl`/`load`) is real;
  deleting "unused" pipeline code now would break app startup for the reports admin surface.
  D1 only marks; no banner/rule may read as a delete-license. Deletion + decoupling is D2.
- **Naive-grep parity trap**: do NOT amend `.claude/rules/data-model.md` "Season-Aggregate
  Parity", `CLAUDE.md` `canonical_recompute`, or `bb report verify-aggregates` — they are
  aggregate-integrity (Epic C), not surface parity. Story 02's AC asserts they are untouched.
- **Multi-worker / replay correctness**: the challenge table works across workers because all
  workers share `data/app.db` (WAL on); replay protection is DELETE-on-consume (do not switch
  to a mark-used flag); `expires_at` must be SQLite datetime text everywhere (no epoch-float
  mixing). No speculative indexes.

## Open Questions
- None blocking. (PM rulings recorded inline: remove the `admin/reports.html` Dashboard nav
  link rather than retarget it; retarget the three error-page buttons for canary consistency.)

## History
- 2026-06-16: Created (DRAFT). Discovery input from SE/DE/CA folded into Technical Notes and
  stories. §0 Roadmap Tracking table flipped to E-238 / PLANNING at planning commit.
- 2026-06-16: Refined through one internal review iteration + one Codex spec-review pass; all
  findings accepted and incorporated; two formal consistency sweeps clean. Set to READY after
  user authorization.
- 2026-06-16: Dispatched and executed. All 7 stories DONE (serial: 01→02/03/04 context-layer,
  05→06 auth.py, 07 reports). Delivered D1 quarantine (central rule + context-layer pointers +
  resolve_unlinked ban + code/template deprecation banners across the dashboard, member-sync,
  and opponent-discovery surfaces), navigation retarget off the quarantined `/dashboard` onto
  `/admin/reports` (5 auth redirects + root + passkey/error templates + `is_admin_page`
  bottom-nav suppression), the passkey/magic-link challenge store moved to migration-004's TTL'd
  `webauthn_challenges` SQLite table (multi-worker + restart-safe, byte-identical login
  lookup-key, DELETE-on-consume replay protection), and expired-report HTML file cleanup
  (`cleanup_expired_reports()` opportunistic + `bb report cleanup`, row kept / path nulled).
  Phase-4b Codex returned 2 findings: F1 (P1 — passkey replay protection not atomic under
  concurrent multi-worker; the read-verify-delete TOCTOU window let two workers both consume one
  challenge) ACCEPTED as an in-scope AC-2 correctness defect and fixed within E-238-06
  (`consume_challenge` returns rowcount as the atomic replay arbiter; login verify gates on
  rowcount==1 else 401/no-session/no-sign_count-bump; 3 concurrency regression tests added). F2
  (P5 — `/admin/reports`→`/admin/users`→`/dashboard` reachable via `users.html` header link)
  DISMISSED: story 05 AC-7 + Technical Notes explicitly defer the six admin-template header links
  to D2, and the epic Success Criteria enumerates the in-scope nav surfaces (the admin subnav and
  `users.html` are not among them) — a documented scope decision, not a defect. Full suite green
  at 4725 passed / 0 failed.
- 2026-06-16: Closure assessments completed.
  - **Documentation assessment** (`.claude/rules/documentation.md`): ONE trigger fired — the new
    `bb report cleanup` CLI command was missing from `docs/admin/operations.md`'s `bb report`
    reference; docs-writer added a `cleanup` subsection (modeled on `verify-aggregates`). No
    trigger for the login-landing change (no doc claimed a post-login `/dashboard` landing; the
    surface is quarantined, not removed) or migration 004 (internal auth table, not operator-doc'd).
  - **Context-layer assessment** (`.claude/rules/context-layer-assessment.md`) — six per-trigger
    verdicts (claude-architect dispatched to codify the firing triggers; files changed: `CLAUDE.md`,
    `.claude/rules/migrations.md`, `.claude/rules/data-model.md`):
    1. New convention/pattern — **YES**: quarantine self-codified by stories 01-03; the stale
       `migrations.md` "next migration" pointer was corrected this closure.
    2. Architectural decision — **YES**: the quarantine reframe + passkey-store-to-SQLite are
       codified by the epic's own deliverables; CA grepped the context layer for stale
       `_PASSKEY`/in-memory-dict references and found zero, so no further pointer was needed.
    3. Footgun/boundary — **YES**: the multi-worker single-use-token TOCTOU replay window is
       codified as a "Single-Use Token Consume (DELETE-is-the-arbiter)" section in
       `.claude/rules/data-model.md`.
    4. Agent behavior/routing — **NO**.
    5. Domain knowledge — **NO**.
    6. New CLI command/workflow — **YES**: `bb report cleanup` added to `CLAUDE.md` Commands.
  - **Non-target verification (story 02 AC-5 / Non-Goal)**: confirmed CA's closure edit to
    `data-model.md` did NOT alter the "Season-Aggregate Parity" section — it remains pure
    aggregate-integrity content (provenance, member-load asymmetry, `cells_compared` footgun, E-237
    mixed-provenance invariant), with CA's two additions (Single-Use Token section + header example
    reword) demonstrably elsewhere in the file. PASS.
  - **Memory maintenance**: the `feedback_delivery_parity.md` auto-memory was annotated
    "SUPERSEDED IN PART (E-238/D1)" — dashboard quarantined/parity-excluded, reports is the sole
    forward delivery surface.

### Review Scorecard — Planning
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 5 | 5 | 0 |
| Internal iteration 1 — Holistic team (SE/DE/CA) | 8 | 8 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| **Total** | **18** | **18** | **0** |

### Review Scorecard — Dispatch & Post-Dev
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-238-01/02/03 | N/A | — | — |
| Per-story CR — E-238-04 | 0 | 0 | 0 |
| Per-story CR — E-238-05 | 0 | 0 | 0 |
| Per-story CR — E-238-06 | 0 | 0 | 0 |
| Per-story CR — E-238-07 | 0 | 0 | 0 |
| CR integration review (Phase 4a) | 0 | 0 | 0 |
| Codex code review (Phase 4b) | 2 | 1 | 1 |
| **Total** | **2** | **1** | **1** |

E-238-01/02/03 were context-layer-only (PM-only AC verification; per-story code review skipped
per the context-layer-only skip condition). F1 accepted+fixed; F2 dismissed (D2 scope).
- **Memory-maintenance flag (for PM/main, handled separately — not edited here)**: the
  `feedback_delivery_parity.md` auto-memory ("update BOTH delivery paths") is partially
  superseded for quarantined surfaces and should be annotated once D1 lands.
