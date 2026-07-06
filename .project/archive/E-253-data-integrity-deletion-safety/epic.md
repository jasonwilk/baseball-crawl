# E-253: Data-Integrity & Deletion Safety

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- READY set 2026-07-06 after expert consultation (SE/DE/coach), internal review iter-1, and Codex spec-review iter-1 all incorporated. Awaiting separate user dispatch authorization. -->

> **Dispatch note**: E-253-04 (and transitively E-253-11) is `blockedBy` E-252 — it reuses the E-252-05 operating-timezone seam. E-252 (CE-2) is sequenced before E-253; dispatch E-252 first, or flag that E-253-04/11 need the seam if E-253 is dispatched earlier.

## Overview
Close the data-destroyer and data-integrity defects that sit on routine operations. The headline is F-H1: deleting one report permanently destroys the play-by-play rows another live report depends on when the two teams shared a game, and whole-game plays idempotency makes the hole permanent. Alongside it, this epic fixes a cluster of ingestion, migration-safety, dedup, and reconciliation correctness gaps. This is the epic that DISCHARGES the shared-game deletion guard the E-250-02 TN-5 amendment declared REQUIRED-but-deferred, and lifts the live operator "no report deletions" hold.

## Background & Context
This epic refines the CE-3 capture stub from the 2026-07-03 platform audit (`PLATFORM-AUDIT.md`, repo root, uncommitted). The audit found that the product's report-generation happy path has no confirmed high-severity defect, but the serious problems cluster in the paths no failure has yet exercised — deletion/cleanup, ingestion edge cases, migration safety. E-253 absorbs **1 HIGH (F-H1) + 6 medium + 7 low** findings plus one Watch-List item.

Expert consultation completed during planning (relayed via the main session — peer DM silent-drop is the known dispatch-pattern issue):
- **software-engineer** — F-H1 destruction-path analysis + fix framing; confirmed the reconcile and ingestion findings are well-scoped and will be built scoreboard-compatible.
- **data-engineer** — schema/migration design read on the three DE findings, with the migration-numbering correction (spray = 009, game-dedup = 010) and the game-dedup doubleheader hazard.
- **baseball-coach** — Tier-2 suppressed-starter narrative honesty (advisory).

The three expert design reads are captured in Technical Notes (TN-1 through TN-7) as the authoritative source; story ACs reference them rather than restating.

## Goals
- Deleting a report never destroys per-game or plays data that a still-live report depends on; the operator "no report deletions" hold is lifted.
- Defensive spray rows are persisted and counted honestly (the ~16% defensive-coverage claim becomes true at the DB layer).
- A mid-file migration failure leaves the database in a clean, re-runnable state — never a permanent duplicate-column crash-loop.
- Stored `game_date` reflects the venue-local calendar date, not the UTC date.
- A GameChanger field rename that zeroes a stat surfaces as a load ERROR instead of passing silently — designed to survive into the future E-245 reconciliation scoreboard.
- The suppressed "Most Likely Arms" state shows honest absence, never a hallucinated LLM narrative.
- Dedup detection, reconcile atomicity, and score coercion no longer silently corrupt or lose data.

## Non-Goals
- **Building the E-245 plays-to-boxscore reconciliation scoreboard.** "Align, don't build" (user decision). The stat-key drift canary and the reconcile-atomicity / perspective-partition fixes MUST be designed scoreboard-compatible (TN-7), but the scoreboard itself remains a separate future epic.
- **Morning-run reliability cluster** → CE-2 (E-252). Only the `game_date` timezone derivation + backfill is here; morning-run's target-date timezone is CE-2. Both reuse the SAME operating-timezone `ZoneInfo` convention that CE-2 introduces (TN-5).
- **The query-time-aggregate cutover** (upheld REVISIT) → CE-6 (E-256).
- **Cross-season / multi-season player identity** — permanent Non-Goal (E-250). The dedup boxscore_only-scope guard (E-253-08) is a latent-defect fix, not a re-introduction of multi-season support.

## Success Criteria
- All 11 stories DONE with passing ACs; full suite green at closure.
- F-H1: an automated test proves that deleting report X preserves the shared-game plays/stat rows under a still-live report Y's perspective, AND that the teams-row deletion does not IntegrityError when a live-report game still references the team.
- Spray defensive rows persist and are counted (verified by report regeneration, not a backfill).
- Migration atomicity proven by a failing-input test (mid-file failure ⇒ zero statements applied, no `_migrations` row).
- Every other finding has at least one failing-then-passing test.
- Operator follow-ups (game_date backfill run, GS mixed-`appearance_order` live-DB check) recorded for post-dispatch execution.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-253-01 | F-H1: shared-game deletion guard (discharges E-250-02 TN-5) | DONE | None | software-engineer |
| E-253-02 | Spray `chart_type` UNIQUE migration (009) + loader accounting | DONE | E-253-03 | data-engineer |
| E-253-03 | Migration-runner atomicity + docstring correction | DONE | None | data-engineer |
| E-253-04 | `game_date` operating-timezone derivation (+ helper relocation) | DONE | E-252 (E-252-05 seam) | software-engineer |
| E-253-05 | Cross-perspective game-dedup partial UNIQUE backstop (010) | DONE | E-253-02, E-253-03 | data-engineer |
| E-253-06 | Ingestion integrity guards: stat-key drift canary + 0-0 coercion | DONE | E-253-04 | software-engineer |
| E-253-07 | Tier-2 suppress gate: skip enrichment + template honesty | DONE | E-253-01 | software-engineer |
| E-253-08 | Player-dedup detection & recompute-scope hardening | DONE | None | software-engineer |
| E-253-09 | Reconcile atomicity + perspective partition | DONE | None | software-engineer |
| E-253-10 | GS mixed-`appearance_order` semantics: pin + operator check | DONE | None | software-engineer |
| E-253-11 | `game_date` backfill subcommand (3-tier re-derivation) | DONE | E-253-04 | software-engineer |

## Dispatch Team
- software-engineer
- data-engineer
- baseball-coach (advisory only — Tier-2 diff review on E-253-07; not assigned a story)

## Technical Notes

### TN-1: F-H1 destruction path and fix framing (software-engineer design read)
The destroyer is the UNBOUNDED anchor pass in `_delete_team_anchor_and_orphan_data` (`src/reports/generator.py`, ~line 2506): `DELETE FROM plays WHERE batting_team_id = X` and `... team_id = X`, run across ALL games and perspectives. When teams X and Y played each other and Y has a live report, Y's pitcher FPS%/P-BF are computed from the plays rows where X was batting (`batting_team_id = X`) under Y's perspective (`perspective_team_id = Y`). The anchor pass wipes those rows; whole-game plays idempotency then sees Y's surviving (Y-batting) rows and never re-fetches → permanent silent hole in Y's report.

The unbounded anchor pass is INTENTIONAL FK-safety: `team_id` / `batting_team_id` FKs have no `ON DELETE` clause, so `DELETE FROM teams` IntegrityErrors unless all anchor rows are gone first. Therefore the fix cannot simply perspective-scope the anchor DELETEs — it must ALSO make the teams-row deletion conditional. The code already has a "retain the teams row when a game FK still references it" survivor pattern in `cascade_delete_team` / `cleanup_orphan_teams`; the fix extends it: when X shares a game with another team that holds a live `reports` row, delete X's own-perspective data but RETAIN X's shared-game anchor rows AND the teams row. The guard MUST live in / extend the canonical deletion helpers (`cascade_delete_team` / `cleanup_orphan_teams` per CLAUDE.md), never a new parallel delete path.

### TN-2: Tier-2 suppressed-starter honesty (baseball-coach advisory)
`_run_tier2_enrichment()` (`src/reports/generator.py:2214`) fires whenever `pitching_history_rows` is non-empty and does NOT check `starter_prediction.confidence`; `enrich_prediction()` (`src/reports/llm_analysis.py:205`) has no confidence gate either — so a `suppress` prediction (reason `insufficient_data` OR `unsupported_level`) still calls the LLM. In the template, the suppress branch (`scouting_report.html:533-536`) and ranked-candidate branch (`:537-578`) are mutually exclusive under one `{% elif %}`, but the Tier-2 narrative block (`:606-615`) sits AFTER the `{% endif %}` at `:578` — outside the branch. So a coach sees the honest "Not enough games yet" line immediately followed by an AI paragraph that structurally should not exist.

Coach verdict (option b): on `suppress` (either reason) → skip the LLM call entirely (no cost spent), render only the existing softened suppress copy, NO narrative and NO named pitcher. Non-suppress path unchanged. Rationale: `insufficient_data` suppress is the MOST COMMON early-season state (25-35 game seasons) — exactly when the coach leans hardest on the report — and an LLM narrative from a thin sample under "not enough games yet" launders a low-confidence guess into confident prose. This aligns with `.claude/rules/display-philosophy.md` ("Discounted is not unavailable"; suppress is honest absence). The gate must be applied at BOTH the enrichment call site AND the template block — either alone is incomplete. Template path: `src/api/templates/reports/scouting_report.html`.

### TN-3: Spray `chart_type` UNIQUE (data-engineer design read)
`spray_charts` carries a table-level `UNIQUE(event_gc_id, perspective_team_id)` at `migrations/001_initial_schema.sql:417`, omitting `chart_type`. Offense and defense for one event share `event_gc_id` + `perspective_team_id`, so the second (defensive) `INSERT OR IGNORE` is silently ignored — 100% of defensive rows are dropped and miscounted as idempotent skips. Fix has two parts:
- **Migration 009**: widen to `UNIQUE(event_gc_id, perspective_team_id, chart_type)`. SQLite cannot ALTER a table-level UNIQUE in place — this requires a full **table rebuild** (create new table with the wider UNIQUE, `INSERT INTO ... SELECT`, drop old, rename), preserving the existing indexes and FKs. A bare `CREATE UNIQUE INDEX` does NOT help — the narrow table constraint still fires first.
- **Loader accounting** (`src/gamechanger/loaders/scouting_spray_loader.py`): stop counting a real UNIQUE collision as an idempotent skip.
- **No backfill possible or needed**: the dropped defensive rows were never inserted, and spray loads in-memory during report generation. Defensive coverage self-heals on the next report generation once the UNIQUE widens. The AC verifies by REGENERATING a report for a game with known defensive spray data, not by a backfill pass.
- **Context-layer follow-up (closure)**: the `~16%` defensive-coverage claim in `.claude/rules/data-model.md` is false at the DB layer today; correcting it is a context-layer edit owned by claude-architect and is handled at epic closure (context-layer assessment), not within the DE story.

### TN-4: Migration-runner atomicity (data-engineer design read)
`migrations/apply_migrations.py:114-141` has a `try/except`+`rollback`, but uses `conn.executescript()`, which COMMITs any pending transaction on entry and runs bare DDL in autocommit mode. A mid-file failure (a failing 2nd `ALTER` in a multi-ALTER migration — 003/007/009 have that shape) leaves earlier statements committed and the rollback has nothing to undo → permanent duplicate-column crash-loop. Two footguns the fix must respect: `PRAGMA foreign_keys` is a no-op inside a transaction (must be set BEFORE `BEGIN`), and `executescript()` cannot nest inside a manually-opened `BEGIN`. Recommended shape: build ONE script string — `PRAGMA foreign_keys=ON;\nBEGIN;\n{migration_body}\nINSERT INTO _migrations(filename) VALUES('{escaped_name}');\nCOMMIT;` — and `executescript` the whole thing, so the file body AND the `_migrations` INSERT commit atomically or roll back together. Escape the filename defensively. Correct the false "Executes the file's SQL in a transaction" docstring at `:118`. This story lands BEFORE the two new migrations (009/010) so they run under the fixed runner — hence E-253-02 and E-253-05 depend on it.

### TN-5: `game_date` operating-timezone derivation + backfill (software-engineer SE-Q2 resolution)
Three UTC-date derivations are systemic (audit finding 4): stored `game_date`, the report reference date, and morning-run's target date. E-253 owns ONLY the stored `game_date` site (`game_loader.py:594`, derived from `last_scoring_update[:10]`). Two existing pieces are reused — E-253 must NOT introduce a second timezone convention:
- **The operating-timezone seam from E-252-05 (TN-4)**: CE-2 (E-252, sequenced BEFORE E-253, position 4 vs 5) INTRODUCES it — one reusable helper + one env read (IANA tz, `America/Chicago` default), deliberately left "importable by CE-3." E-253 REUSES it as the FALLBACK tz. Reference it abstractly (path not yet pinned by the E-252 implementer). E-253-04 is `blockedBy` E-252.
- **The existing `derive_local_date(start_datetime, tz_name)` helper** (currently `src/reports/morning_run.py:150`) for the instant→local-date conversion, using the game's own `timezone` when present. `game_loader` (under `src/gamechanger/loaders/`) importing from `src/reports/` is a **layering inversion** — E-253-04 relocates `derive_local_date` to a neutral shared module both import. This relocation is an architecture change → flag for the closure context-layer assessment.

**Interface-shape bridge (ZoneInfo → tz-name).** E-252-05's seam RETURNS a configured `ZoneInfo` OBJECT (per E-252-05 AC-2), but `derive_local_date(start_datetime, tz_name)` takes an IANA tz-NAME STRING and internally does `ZoneInfo(tz_name)`. Passing the seam's `ZoneInfo` object directly would double-wrap (`ZoneInfo(ZoneInfo(...))`) and break. E-253 MUST bridge object→name by reading the seam `ZoneInfo`'s `.key` attribute to obtain the IANA name before calling `derive_local_date` — it does NOT pass the `ZoneInfo` object into `derive_local_date`. This binds both the fallback path in E-253-04 (derivation) and the tier-2 path in E-253-11 (backfill). (E-252's implementer is separately advised that E-253 needs the resolved tz-name; if E-252-05 later chooses to also expose the name string, E-253's `.key` bridge still works unchanged.)

**Backfill (E-253-11), 3-tier — CONDITIONAL, not flag-only.** `games` stores `game_date` (mis-derived), `start_time TEXT` (ISO-8601 UTC, migration 014), `timezone TEXT` (IANA, migration 014). For scouting-loaded games `start_time` == the derivation instant (`scouting_loader.py:400-410`), so it is the recoverable absolute instant:
1. `start_time` present + `timezone` present → clean re-derivation via `derive_local_date(start_time, timezone)` (the majority — public feed + schedule loader supply both).
2. `start_time` present, `timezone` NULL → re-derive using the E-252-05 operating-tz default as fallback.
3. `start_time` NULL → no recoverable instant (legacy pre-mig-014 / game-summaries-only loads); leave `game_date` untouched, count + report the skip, do not fabricate.
Re-derive where `start_time IS NOT NULL`, UPDATE only rows where the re-derived date differs (idempotent, re-runnable — mirrors `bb data backfill-appearance-order`). The backfill MUST NOT re-run dedup — it only corrects stored dates; a corrected date that shifts 7-day-window membership is the intended correction, not a regression.

### TN-6: Game-dedup backstop hazard (data-engineer design read)
Cross-perspective game dedup is SELECT-then-INSERT via `_find_duplicate_game` (`game_loader.py:1100`) on a natural key (`game_date` + unordered `{home_team_id, away_team_id}`); there is no DB-level backstop for the cross-process race window. HAZARD: a naive `UNIQUE(game_date, team_lo, team_hi)` would REJECT the legitimate SECOND game of a doubleheader (per the Game-ordering convention in `.claude/rules/data-model.md`). The stable `game_stream_id` is NOT always present for tracked/public opponent games, and `event_id` is perspective-specific. Therefore the backstop MUST be a **partial UNIQUE INDEX gated on `game_stream_id IS NOT NULL`** (migration 010) — it backstops only games carrying the stable id and leaves doubleheaders / tracked-opponent games to the existing SELECT-then-INSERT path. Do NOT ship a bare unordered-pair UNIQUE. The AC must assert doubleheaders are not rejected.

**Cross-story non-conflict note (SE)**: E-253-04 (corrects `game_date`), E-253-06 (0-0 coercion), and E-253-05 all touch the game-dedup natural key (`game_date` + unordered team pair), but they do NOT conflict specifically because 05's backstop is gated on `game_stream_id IS NOT NULL` — the gating is load-bearing for this non-conflict, so E-253-05 MUST keep it. A bare unordered-pair UNIQUE would collide with 04's date corrections and 06's score handling.

### TN-7: Scoreboard compatibility (align, don't build)
Two SE-owned findings must be designed to survive into the future E-245 scoreboard without building it:
- Stat-key drift canary (`game_loader.py:932`): ERROR + `LoadResult.errors` when a core key is absent from ALL rows of a non-empty group (group-grain, NOT per-row) — the right grain to become a hard-fail signal in the scoreboard.
- `get_summary_from_db` perspective partition (`engine.py:1161`): add `perspective_team_id` to the dedup partition key — a correctness fix matching the perspective-provenance invariant; the scoreboard's player-level grain depends on it.

## Open Questions
- **RESOLVED (2026-07-05, SE Q2 relay)**: The E-252-05 operating-timezone seam is reused (not re-defined); `game_date` derivation also reuses the existing `derive_local_date` helper (relocated to a neutral module in E-253-04 to fix a layering inversion); the per-row UTC instant survives as `games.start_time` for the common case, so the backfill is a real 3-tier re-derivation (E-253-11), not flag-only. Folded into TN-5 + E-253-04 + E-253-11. No open questions remain blocking READY.
- **Context-layer closure items (not stories — CA-owned at closure)**: (1) `.claude/rules/data-model.md` "~16% defensive coverage" claim correction (TN-3); (2) `derive_local_date` relocation → possible CLAUDE.md canonical-helper note (TN-5); (3) new `bb data` game_date-backfill subcommand → CLAUDE.md Commands + `/workflow-help` (E-253-11).

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-3).
- 2026-07-05: Refined toward READY — expert consultation (SE/DE/coach) completed and captured in TN-1..TN-7; decomposed into 10 stories (SE=7, DE=3, coach-advisory on E-253-07).
- 2026-07-05: SE Q2 (game_date tz) resolved — split the original E-253-04 into E-253-04 (derivation + `derive_local_date` relocation, `blockedBy` E-252-05) and E-253-11 (3-tier backfill subcommand). Now **11 stories** (SE=8, DE=3). All ACs concrete; no open questions blocking READY.
- 2026-07-06: Internal review iter-1 triaged (CR spec audit + SE/DE/coach holistic). ACCEPTED: S1 (ZoneInfo→tz-name interface bridge → TN-5 + E-253-04 AC-3 + E-253-11 AC-1; E-252 implementer flagged separately), O1 (E-253-11 transitive E-252 blocker note), DE row-preservation (E-253-02 AC-6), SE 3 heads-ups (E-253-09/06 Technical Approach + TN-6 cross-story gating note). DISMISSED: O2 split (E-253-08 intentionally bundled — single-file pass; noted), O3 (migration 014/015 citations follow the archived-migration convention — no defect).
- 2026-07-06: Codex spec-review iter-1 triaged (2 findings, both ACCEPTED). P1 (E-253-10 sizing): moved the operator-doc/live-DB-follow-up items out of story ACs into Handoff Context + epic Success Criteria; E-253-10 is now a clean SE slice (AC-1 pin test + AC-2 stop-and-flag guard). P2 (E-253-06 canary contract): SE pinned the concrete contract (verified against 46 real boxscores) — batting core set `AB,R,H,RBI,BB,SO`, pitching `H,R,ER,BB,SO`+`IP`, sourced from `_BATTING_MAIN`/`_PITCHING_MAIN`; extras excluded; batting+pitching groups only (fielding/catcher out of scope). Written into E-253-06 AC-1/AC-2 + Technical Approach.
- 2026-07-06: **Status → READY** (user-approved; single Codex pass, no iter-2). 11 stories, all ACs testable, no open questions/placeholders. Awaiting separate user dispatch authorization.
- 2026-07-06: **Dispatched + all 11 stories DONE** (serial, per-story CR + PM AC verification in the epic worktree). Shipped: **E-253-01** F-H1 shared-game deletion guard (perspective-scoped anchor pass + teams-row survivor — discharges the E-250-02 TN-5 deferred guard, lifts the operator no-deletions hold); **E-253-03** migration-runner atomicity (single `executescript` `PRAGMA;BEGIN;{body};INSERT _migrations;COMMIT`, rollback-on-failure) + docstring fix; **E-253-02** spray `chart_type` UNIQUE **migration 009** (canonical table rebuild, row-preserving) + loader collision accounting; **E-253-04** `game_date` operating-tz derivation + `derive_local_date` relocation to `src/util/timezone.py` (fixes the game_loader→reports layering inversion); **E-253-05** cross-perspective game-dedup partial-UNIQUE backstop **migration 010** (gated `game_stream_id IS NOT NULL`, doubleheader-safe); **E-253-06** ingestion integrity guards (group-grain stat-key drift canary sourced from `_BATTING_MAIN`/`_PITCHING_MAIN`+IP; 0-0 score coercion → `_opt_int` NULL-preserving); **E-253-07** Tier-2 suppress gate (call-site skip + defensive tripwire + template guard, both suppress reasons); **E-253-08** player-dedup hardening (Unicode `_fold_name` shared into detection + `_terminal_names`, LIKE-metachar escape, boxscore_only recompute-scope guard); **E-253-09** reconcile `--execute` single per-game commit atomicity + `get_summary_from_db` perspective-aware partition; **E-253-10** GS mixed-`appearance_order` characterization pin (test-only; AC-2 STOP not triggered — PM affirmed the conservative-undercount semantics as acceptable-as-documented); **E-253-11** `bb data backfill-game-dates` 3-tier re-derivation subcommand (idempotent, dry-run default). Migrations shipped: **009 + 010** (next available = **011**).
- 2026-07-06: **Phase 4a integration review** (code-reviewer, whole-epic diff) — 0 findings.
- 2026-07-06: **Phase 4b Codex code review** (headless, exit 0) — 2 VALID Priority-1 findings, both on the scouting/public loader path (`scouting_loader.py`) that E-253-04/06 fixed only on the authenticated `game_loader.py` path: (1) regression from E-253-04 — the fabricated `1900-01-01T00:00:00Z` sentinel was localized to `game_date` 1899-12-31; (2) E-253-06 AC-3 gap — `int(score or 0)` coerced missing public scores to 0-0. **Both accepted, 0 dismissed.** SE Round-1 remediation (in `scouting_loader.py` + 3 teeth-bearing tests in `test_scouting_loader.py`): absent-instant → empty `last_scoring_update` preserves the `1900-01-01` sentinel; scores route through the SHARED `_opt_int` imported from `game_loader` (missing→NULL, genuine 0→0). PM-confirmed both fixes address the findings and mirror `_parse_summary_record` (Phase 4b protocol — no CR re-review). Cross-path completeness gap closed.
- 2026-07-06: **Documentation assessment** (`.claude/rules/documentation.md`) — trigger 1 (new feature ships) + trigger 5 (epic changes how the operator interacts) FIRE: the new `bb data backfill-game-dates` CLI subcommand needs an operator-runbook section. **Affected file: `docs/admin/operations.md`** (the operator runbook that already documents every other `bb data` maintenance command — `backfill-appearance-order`, `reload-annotated-pitches`, `fix-self-games`, `dedup-players`, `reconcile`). docs-writer dispatched to add a parallel `### Backfilling Game Dates (bb data backfill-game-dates)` section (3-tier re-derivation, dry-run default + `--execute`/`--db`, idempotent/re-runnable, corrects the historical UTC mis-derivation; note the post-E-253-04 one-time operator correction and the live-DB run follow-up). No coaching-doc (`docs/coaching/`) or API-doc (`docs/api/`) impact (internal data-integrity + operator-maintenance scope).
- 2026-07-06: **Context-layer assessment** (`.claude/rules/context-layer-assessment.md`, six triggers, per-trigger verdicts):
  1. New convention/pattern/constraint — **YES**: the operating-tz `ZoneInfo → .key` IANA-name bridge (never pass the object to `derive_local_date`); the migration-runner single-`executescript` atomic-body contract binding all future migrations; the partial-UNIQUE-gated-on-stable-id dedup backstop pattern; the cross-loader-path completeness discipline (a fix on the authenticated path must be mirrored on the public path).
  2. Architectural decision with ongoing implications — **YES**: `derive_local_date` relocated to `src/util/timezone.py` as the neutral shared seam both loaders + morning_run import → candidate CLAUDE.md canonical-helper note (fixes the loaders→reports layering inversion).
  3. Footgun/failure mode/boundary discovered — **YES**: authenticated-vs-public loader cross-path completeness boundary (the Phase 4b findings); reaffirmed shared-connection partial-commit footgun (reconcile), ZoneInfo double-wrap hazard, and table-rebuild silent-drop footgun (spray 009).
  4. Change to agent behavior/routing/coordination — **NO**: E-253 did not modify dispatch, routing, agent definitions, communication, or the closure sequence.
  5. Domain knowledge for future agent decisions — **YES**: the `.claude/rules/data-model.md` "~16% defensive coverage" claim is now false at the DB layer (defensive spray rows persist post-009) and must be corrected; the GS mixed-`appearance_order` conservative-undercount semantics and the canary core-key contract are data-model knowledge worth carrying forward.
  6. New CLI command/workflow/operational procedure — **YES**: new `bb data backfill-game-dates` subcommand → CLAUDE.md Commands section + `bb data` help + `/workflow-help` cheat sheet.
  **Verdict: 5 of 6 fire → claude-architect dispatched** to codify (headline items: data-model.md ~16% correction, `derive_local_date` canonical-helper note, `bb data backfill-game-dates` in CLAUDE.md Commands + `/workflow-help`). Epic MUST NOT archive until CA codification + the docs-writer update land.
- 2026-07-06: **Operator follow-ups owed** (need live-DB access, unavailable in the worktree — record in completion summary): (a) **E-253-05** — if the live DB already holds two rows sharing one non-null `game_stream_id`, migration 010's `CREATE UNIQUE INDEX` fails-and-rolls-back cleanly on apply, surfacing a real duplicate for cleanup; (b) **E-253-10** — check the live DB for legacy NULL `appearance_order` rows and, if found, run `bb data backfill-appearance-order` → `canonical_recompute` → `bb report verify-aggregates` (the Watch-List "check once during CE-3" discharge); (c) **E-253-11** — run `bb data backfill-game-dates --execute` on the live DB to correct historical UTC-mis-derived `game_date` values.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iter-1 — CR spec audit | 4 (1 SHOULD-FIX S1 + 3 minor O1/O2/O3) | 2 (S1, O1) | 2 (O2 split, O3 no-defect) |
| Internal iter-1 — Holistic team (SE/DE/coach) | 4 (DE row-preservation + 3 SE heads-ups) | 4 (1 new AC + 3 as implementer guidance, not new ACs) | 0 |
| Codex iter-1 (spec review) | 2 (P1 sizing, P2 canary contract) | 2 | 0 |
| **Spec-review subtotal** | **10** | **8** | **2** |
| Dispatch — per-story CR (11 stories) | 1 (E-253-04 SHOULD-FIX docstring, round 2) | 1 (fixed) | 0 |
| Phase 4a — CR integration review | 0 | 0 | 0 |
| Phase 4b — Codex code review | 2 (F1 sentinel-localization regression; F2 public-path 0-0 coercion gap) | 2 (both remediated, Round 1) | 0 |
| **Dispatch subtotal** | **3** | **3** | **0** |
| **Grand total** | **13** | **11** | **2** |

Notes: the 3 SE holistic heads-ups were accepted as implementer guidance folded into Technical Approach / TNs (E-253-09 rollback footgun, TN-6 cross-story gating, E-253-06 canary-key source), not as new ACs. coach's holistic pass raised no findings (E-253-07 faithful). The two dismissals: O2 (E-253-08 split — kept as one cohesive single-file dedup pass, split point noted) and O3 (migration 014/015 citations follow the archived-migration convention — no defect).
