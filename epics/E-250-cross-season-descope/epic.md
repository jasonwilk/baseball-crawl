# E-250: Root-Level Cross-Season / Multi-Season De-Scope

## Status
`READY`

## Overview
Rip the remaining cross-season / multi-season MACHINERY out of the project at the root, rather than leaf-patching another symptom. The reports-first reframe (2026-06-12) and E-239 already de-scoped multi-season rollups, cross-team identity, and longitudinal tracking, but cross-season *logic* still runs through the core: the CLI's unscoped dedup corner, a write-orphaned identity column and table, a write-only `season_type` footgun, compound-slug fixtures, and stale multi-season prose across the context layer and docs. This epic removes that scaffolding while KEEPING `season_id` as the single-season partition key.

## Background & Context
The user has asked repeatedly (their words: "I feel like I've asked five times") to remove cross-season machinery from "the bones of the project." Every prior pass patched a symptom (E-236 dropped `season_fallback` from the coach-facing trust term but left the flag + derivation running; E-241 collapsed the suffix taxonomy and dropped the `season_fallback` column but left other seams) instead of removing the cross-season *concept* from the core. This epic is the deliberate root de-scope.

The scope was fully audited before planning (two independent passes plus a Fable evaluation) and the user made the load-bearing decisions. This epic does NOT re-discover WHAT to remove; it structures the vetted inventory into well-formed stories.

**Key user decision**: KEEP `season_id` as the single-season partition key/FK/UNIQUE-member. Remove only cross-season *logic* — do NOT collapse `season_id`.

**Why the machinery is vestigial**: every report is a single-season snapshot. As of 2026-06-20 the live DB holds exactly ONE season (`2026`) across `player_season_batting`/`player_season_pitching` — there is no cross-season data and, by design, never will be. Explicit permanent non-goals (CLAUDE.md, `docs/ROADMAP.md`): cross-team player identity, multi-season rollups, longitudinal tracking.

**Consultations & review (this planning session)** — the stories lean on live expert input, recorded here per the consultation-documentation requirement (Codex #6):
- **data-engineer**: confirmed `season_type` fixtures must be REMOVED not defaulted; confirmed direct `ALTER TABLE ... DROP COLUMN` is feasible on the runtime (SQLite 3.45.1, no table-rebuild) with no index/view/FK dependency on either dropped column; empirically traced the `ensure_season_row` fail-loud test fallout (`test_loaders/test_game_loader.py`) and the `team_opponents` table-drop test surface. Feeds E-250-02 AC-2/AC-5/AC-6/AC-9 + TN-2/TN-6.
- **software-engineer**: confirmed the E-250-01 auto-derive shape (not a multi-season loop) and that the `team_opponents` guard removal is behavior-preserving; enumerated the 14 unscoped `plan_player_dedup`/`find_duplicate_players` call sites. Feeds E-250-01 AC-10/AC-11 + TN-5.
- **claude-architect**: produced the context-layer inventory (8 prose removals) and resolved the VISION-scope + DE-Core-Entities boundary flags. Feeds E-250-04 + IDEA-092.
- **api-scout**: produced the athlete-profile stale-line list and the cross-TEAM-in-current-season KEEP boundary. Feeds E-250-06.
- **Codex** spec review (Phase 4): 8 P2 findings, all triaged/incorporated (this round).

## Goals
- Close the CLI's unscoped cross-season-execute corner in `bb data dedup-players` by making `season_id` a required (auto-derived) scope, so a cross-season merge is unreachable by construction.
- Drop three pieces of dead cross-season/identity schema (`players.gc_athlete_profile_id`, the whole `team_opponents` table, `seasons.season_type`) and remove every code reference to them.
- Normalize compound-slug and `season_type` test fixtures/docstrings so no code path or test seeds a cross-season shape.
- Excise stale multi-season/longitudinal/cross-season-identity prose from the context layer (CLAUDE.md, rules, agent definitions) and docs (`docs/admin/`, `docs/ROADMAP.md`, `docs/api/`).
- Abandon the still-READY identity-probe epic E-104 (the cross-team-identity direction is permanently de-scoped).

## Non-Goals
- **Collapsing or removing `season_id`.** It stays as the single-season partition key/FK/UNIQUE-member. This epic removes cross-season *logic*, not the partition column.
- Touching the load-bearing single-season kernel: `derive_season_id_for_team` / `_derive_season_id` (year-only), `teams.season_year`, `canonical_recompute` / `aggregate_parity` per-scope, the single-season isolation/exclusion regression tests (which keep a second-season seed to prove exclusion), or the `season_fallback`-absent regression guards.
- Removing the `programs` org-hierarchy machinery, the `detect_league_level` unused params, the `_derive_season_id` `min(years)` rule, or reworking season-agnostic overlap-confidence — captured as ideas (see Open Questions / idea captures), out of scope here.
- Any live-DB data migration of persisted `season_id` values (none are compound in live data; migration 008 deliberately performs no `season_id` rewrite, following the 006 precedent).

## Success Criteria
- `bb data dedup-players` auto-derives `season_id` on a single-season DB with zero UX change, errors (non-zero exit) on a multi-season DB without `--season-id`, and `season_id=None` is unreachable in `plan_player_dedup` / `find_duplicate_players`.
- Migration 008 drops `players.gc_athlete_profile_id`, `team_opponents`, and `seasons.season_type`; a fresh DB (001→008) and the migrated DB converge; no `src/` code references any of the three.
- `is_team_eligible_for_cleanup` no longer references `team_opponents`, and tests prove cleanup eligibility is unchanged for every team (the removed guards were no-ops on the empty table).
- No `src/` code path or test fixture seeds a compound `season_id` slug or a `season_type` value; the full suite passes.
- No context-layer file or doc frames the project as supporting multi-season rollups, longitudinal tracking, or cross-team athlete identity as a live capability; no reference to the non-existent `PlayerTeamSeason` table remains.
- E-104 is archived as `ABANDONED`.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-250-01 | Player-dedup cross-season-execute corner closure | TODO | None | - |
| E-250-02 | Migration 008: drop identity/opponent/season_type schema + reference code + season_type fixtures | TODO | E-250-01 | - |
| E-250-03 | Fixture compound-slug (Class-1) normalization + plays_parser docstring | TODO | E-250-02 | - |
| E-250-04 | Context-layer prose de-scope | TODO | E-250-01, E-250-02, E-250-07 | - |
| E-250-05 | Documentation corrections (architecture + roadmap + operations) | TODO | E-250-02, E-250-07 | - |
| E-250-06 | API-doc athlete-profile framing softening | TODO | None | - |
| E-250-07 | Archive E-104 as ABANDONED | TODO | None | - |

## Dispatch Team
- software-engineer
- data-engineer
- claude-architect
- docs-writer
- api-scout

<!-- product-manager is spawned as dispatch infrastructure (status owner + AC verifier),
     not listed here. E-250-07 (archive E-104) is a PM-owned housekeeping story handled
     by that infrastructure PM. -->


## Technical Notes

### TN-1: Keep `season_id`; remove cross-season logic
The single decision that governs every story: `season_id` is a KEEP. It remains the single-season partition key. What gets removed is the *logic that only makes sense across seasons* — the unscoped dedup corner, the identity column/table, the `season_type` discriminator, compound-slug producers/fixtures, and multi-season prose. When in doubt whether something is kernel or scaffolding, apply the memory in `.claude/agent-memory/product-manager/` (project: remove-cross-season-from-core) and the KEEP/Non-Goals lists above.

### TN-2: Migration 008 shape (layered ALTER DROP COLUMN + DROP TABLE)
- **Number**: 008 — verified by globbing `migrations/*.sql` (highest present is `007_play_events_pitch_columns.sql`). Ignore any stale "009/012/015" numbers in prose.
- **Pattern**: follow `006_drop_season_fallback.sql`. Leave `001_initial_schema.sql`'s `CREATE TABLE` DDL unchanged; 008 performs the DROPs. A fresh DB runs 001→008 and converges with a migrated DB.
- **Mechanism (with version caveat)**: direct `ALTER TABLE ... DROP COLUMN` applies only on SQLite **3.35+** and only for plain columns with no index/FK/generated-column/view dependency — NOT a 12-step table rebuild. `players.gc_athlete_profile_id` and `seasons.season_type` are plain columns; the implementer must VERIFY (grep across `migrations/` for index/view/FK references) before relying on direct DROP, exactly as 006 documented that verification. 006 recorded the target runtime as 3.45.1 (past 3.35), so direct DROP is the expected path. **DE caveat**: if the runtime SQLite could be <3.35, the migration must instead use the 12-step table-rebuild (create new table without the column → copy → drop old → rename) for the two column drops. Spec the migration to confirm the runtime version and choose accordingly; do not assume 3.35+ without confirming.
- **SE+DE pairing**: this story spans a migration (DE-led) AND lockstep Python edits in `src/reports/generator.py` (:2560-2564 DELETE, Guard 2 :2721-2728, Guard 4 :2738-2754, docstring :2699-2705) plus the `team_opponents` DROP-vs-code atomicity. The generator.py eligibility-guard tracing (TN-5) needs SE-level rigor with tests. Assigned data-engineer-led, but the main session may pair SE; the code-reviewer + the eligibility tests are the correctness gate.
- **`team_opponents`**: `DROP TABLE team_opponents;` (drop the whole table).
- **No `season_id` rewrite**: 008 performs no `season_id` normalization, following 006's documented reasoning (live data is already year-only; both compound-slug producers were collapsed in E-241). This is the correct, DB-state-independent default for a worktree with no `data/` access.
- **Idempotency**: the migration runner applies each file once (tracked in `_migrations`); a bare DROP is sufficient (SQLite has no `DROP COLUMN/TABLE IF EXISTS` for this shape).

### TN-3: `season_type` fixture removal is ATOMIC with the column drop — all in E-250-02
The brief's original phrasing ("normalize season_type refs to 'default'") predates the DROP decision. `seasons.season_type` is `NOT NULL` with no usable default, so an INSERT that omits it FAILS while the column still exists — and every INSERT that supplies it FAILS the instant the column is dropped. There is no ordering in which a separate later story can safely remove the fixture references: the removal MUST land in the SAME story and SAME commit as the column drop. Therefore **E-250-02 owns ALL `season_type`-INSERT removal** — the code sites (`crawlers/scouting.py:364`, `loaders/__init__.py:82`) AND every fixture: ~29 test files plus the two SQL fixtures (`seed.sql`, `parity_consistent.sql`). This is what makes E-250-02's full-suite green-gate achievable (CR F1: deferring the fixtures to E-250-03 would leave the suite objectively RED at E-250-02 "done"). E-250-03 owns ONLY the Class-1 compound-slug `season_id` normalization (~5 files) + the `plays_parser` docstring — independent of the `season_type` drop. Because E-250-02 edits `test_player_dedup.py`/`test_cli_data.py` (which E-250-01 also edits), E-250-02 is blocked by E-250-01 (CR F4).

### TN-4: `ensure_season_row` cleanup lives in E-250-02 (not split)
`ensure_season_row` (`src/gamechanger/loaders/__init__.py:71-87`) contains BOTH the dead compound parse (`season_id.split("-", 1)[0]`, :77) AND the `season_type` INSERT (:82). The brief split these across two stories, but they are the same function and would collide. Both changes land in E-250-02: remove the `season_type` INSERT column, and remove the defensive `.split()`/`.isdigit()` parse so `ensure_season_row` requires a pure-year `season_id` — any non-numeric OR compound value raises via `int()` (precise behavior in E-250-02 AC-6: today `"2026-spring-hs"`→`2026` and `"old-season"`→`year=0`; after, both raise). E-250-03 does NOT touch `ensure_season_row`.

### TN-5: `team_opponents` eligibility guards are no-ops on an empty table
`is_team_eligible_for_cleanup` uses `team_opponents` in Guard 2 (`src/reports/generator.py:2721-2728` — no rows reference this team → not blocked) and Guard 4 (`:2738-2754` — no shared game with a tracked team → not blocked). `team_opponents` has been write-orphaned since E-239 (empty in live data). On an empty/dropped table, both guards are no-ops: Guard 2 finds no rows and does not block; Guard 4's `EXISTS` over an empty table is false and does not block. Removing them is therefore behavior-preserving. **SE-confirmed**: after removal, the two surviving guards — Guard 1 (`is_active = 0`) and the no-other-report guard (currently Guard 3, renumbered to Guard 2 after the removal per E-250-02 AC-7 and reflected in the prose per E-250-04 AC-7) — ARE the correct reports-first eligibility semantics; this is not just a no-op removal, it leaves the semantically right guard set. The `reports_admin.py:604` caller is unaffected. E-250-02 must PROVE this with tests: cleanup eligibility must be unchanged for teams that would previously have hit the `is_active` and no-other-report guards, and the removal must not make any currently-ineligible team eligible. **SE precision on the invariant**: "no ineligible team becomes eligible" holds specifically because the table is EMPTY in live data. The ONLY class of team that WOULD flip eligible is one tracked via a seeded `team_opponents` row — but that is exactly the dead mechanism being removed, and it does not exist in live data. So the test `tests/test_admin_reports.py:462-510` (`test_ac2_preserved_when_tracked_via_team_opponents`), which SEEDS a `team_opponents` row and asserts preservation via guard 2, must be DELETED (it asserts the removed behavior and cannot even INSERT into the dropped table) — NOT "made to pass", which would accidentally reintroduce the removed guard. This is the data-protection gate on the guard removal — the implementer must trace it, not assume it. The stale tests that seed/assert `team_opponents` (`test_admin_reports.py`, `test_schema.py`, `test_migrations.py`, `test_e100_schema.py`'s `TestTeamOpponents` class) MUST be fixed in the same story or the table drop breaks them.

**F-H1 amendment (2026-07-04, platform audit):** The original TN-5 above blessed the surviving two-guard set (`is_active` + no-other-report) as "the correct reports-first eligibility semantics." That blessing is RETRACTED as a completeness claim. Audit finding **F-H1** (HIGH, `src/reports/generator.py`) shows the surviving guards do NOT make report deletion safe: when team X and team Y played each other and you delete X's report, the deletion cascade destroys the shared game's plays rows that Y's live report depends on (FPS%/P-BF), and whole-game plays idempotency makes the hole permanent (the plays never re-fetch, so Y's report goes silently wrong or blank forever). Removing the `team_opponents` guards here does NOT create or worsen F-H1 — those guards were empty-table no-ops and never protected shared-game plays (they only ever checked tracked-opponent rows) — but E-250-02 MUST NOT ratify the reduced guard set as complete deletion safety. **Requirement**: correct deletion safety requires a shared-game / live-reports eligibility guard (or scoping the anchor-pass DELETEs to exclude perspectives that have a live report). That guard is REQUIRED but its implementation is owned by the data-integrity epic **CE-3** (F-H1), NOT E-250-02. E-250-02's obligation is narrowed accordingly: perform the guard removal as a behavior-preserving de-scope of the dead `team_opponents` mechanism, and in AC-7 describe the surviving guards as "the correct guards for the removed `team_opponents` mechanism" — NOT as complete deletion-safety semantics, which remain open under F-H1/CE-3.

### TN-6: Fixture literal classification — THREE classes
E-250-03 must classify each literal into one of THREE classes before changing it, per the Filesystem-vs-DB-Season_id-Decoupling rule in `.claude/rules/architecture-subsystems.md` (per DE prep):
- **Class 1 — DB `season_id` literals** (compound slugs used as the DB partition key/FK): normalize to year-only.
- **Class 2 — Opaque isolation tokens** (arbitrary partition markers like `'s1'`, `'old-season'` used only to prove scoping/exclusion, not real slugs): LEAVE unchanged — they are deliberate test scaffolding, not cross-season logic. **DE caveat (safety condition)**: an opaque token is safe to leave alone ONLY if it is seeded via a DIRECT `INSERT INTO seasons` (never int-parsed). A token that flows through `ensure_season_row` is NOT safe after E-250-02's fail-loud change (`int("old-season")` raises) — it must be numericized or re-seeded via direct INSERT. The known instance (`ensure_season_row(db, "old-season"/"new-season")` in `tests/test_loaders/test_game_loader.py`) is fixed inside E-250-02, not left for E-250-03.
- **Class 3 — FILESYSTEM slug literals** (opaque disk paths, e.g. `data/raw/2025-spring-hs/...`, the `src/gamechanger/loaders/plays_loader.py:32` disk-slug contract): LEAVE unchanged — NOT cross-season logic; handle per the decoupling rule. (CR F2: the `plays_loader.py:32` docstring is Class-3 KEEP — it must NOT be "corrected"; only the `src/gamechanger/parsers/plays_parser.py:22` docstring, a Class-1 `season_id` literal, is fixed.)
- **Across all classes: KEEP two DISTINCT YEARS (2025 AND 2026)** in the single-season isolation/exclusion fixtures — they prove single-season exclusion. Drop only the SUFFIX on Class 1 literals, never the second year.
- The green-full-suite gate (TN-8) — not a grep count — is the proof the classification was correct.

### TN-7: Context-layer edits are claude-architect's to design
Per the domain-expert-designs convention, E-250-04 (context-layer prose) routes to claude-architect, which owns the exact edits within CLAUDE.md, `.claude/rules/**`, and `.claude/agents/**`. The story frames grep-verifiable outcomes (what must no longer appear) and names the files; CA determines the precise wording. The line numbers cited in the story are from the vetting pass and may have drifted — CA locates the current occurrences.

### TN-8: Full-suite gate is mandatory on BOTH fixture-touching stories
Both E-250-02 (drops `season_type` + removes its ~29+2 fixtures) and E-250-03 (Class-1 compound-slug normalization) carry a MANDATORY full-suite gate (E-241-06 lesson): a seeded compound `season_id` feeding a year-only-deriving loader — or a lingering `season_type` INSERT after the column drop — fails as a SILENT `FOREIGN KEY constraint failed` / constraint error that grep reconnaissance cannot catch. `python -m pytest tests/` must be green before each of these stories is DONE. E-250-02's green-gate is what proves its own `season_type` fixture removal is complete (CR F1); E-250-03's proves the compound-slug classification was correct. This is in addition to the epic-closure full-suite-green gate.

### TN-9: Fold the scouting crawler's private `_ensure_season_row` into the canonical seam (audit §2 MEDIUM, added 2026-07-04)
`ScoutingCrawler._ensure_season_row` (`src/gamechanger/crawlers/scouting.py`, ~:351-369) keeps its OWN `INSERT INTO seasons(...season_type...) ... ON CONFLICT(season_id) DO NOTHING` instead of delegating to the canonical `ensure_season_row` (`src/gamechanger/loaders/__init__.py`). Because the live report path runs this writer BEFORE the canonical helper and both use first-writer-wins `DO NOTHING`, whichever runs first wins — the exact drift shape behind E-241's bug — and `.claude/rules/architecture-subsystems.md` falsely claims consolidation ("replacing all private `_ensure_season_row()` methods") is already complete. E-250-02 ALREADY edits both season-row INSERT sites for the `season_type` removal (AC-4), so folding the delegation in here is the cheapest place (per the audit's own routing: "cheapest folded into E-250-02, which already edits both INSERT sites"). Outcome (E-250-02 AC-11): the scouting crawler no longer contains a private season-row INSERT; its season-row creation delegates to the canonical `ensure_season_row` seam, which subsumes the scouting.py portion of AC-4 (the delegation removes the whole private INSERT, including its `season_type` column and multi-writer docstring) and inherits the AC-6 fail-loud behavior (a non-numeric/compound `season_id` now RAISES rather than silently deriving year 0). The implementer chooses delete-the-method-and-call-canonical vs. thin-delegating-wrapper. This makes the arch-subsystems.md consolidation claim finally TRUE — that prose correction is E-250-04's (context-layer) to make, per the Handoff.

## Open Questions
- None blocking. The scope is vetted; per-story verification requirements (guard blast-radius tracing in E-250-02, fixture classification in E-250-03) are baked into ACs rather than resolved at planning time.

## Idea Captures (OUT OF SCOPE)
- **IDEA-091** (FILED): `programs` org-hierarchy machinery never read + `detect_league_level` unused `program_type`/`classification` params; AND the `_derive_season_id` `min(years)` rule (no driving problem on single-season data).
- **IDEA-092** (FILED): `.claude/agents/data-engineer.md` Core Entities table broadly stale vs live schema (beyond the cross-season/`PlayerTeamSeason` cells E-250-04 removes) — surfaced by CA's context-layer inventory (Flag B); blocked-by E-250-04 so it starts from the trimmed table.
- Season-agnostic overlap-confidence — already addressed inside the epic as the `seen_collapse_keys` comment tweak in E-250-01 (no idea needed).

## History
- 2026-07-03: Created (DRAFT). Scope pre-vetted by two audit passes + a Fable evaluation; structured into 7 stories by PM.
- 2026-07-03: Set to READY. Cleared all review gates — iteration-1 holistic review (DE/SE/CA/api-scout), CR spec audit (F1-F4 + minors), and Codex Phase-4 spec review (8/8 P2 findings incorporated + 3/3 domain-expert concurrences: CA #1/#7, api-scout #2, DE #4/#5). No open findings at any severity; quality checklist passes; consistency sweeps clean. Dispatch NOT yet authorized — READY gate only.
- 2026-07-04: Two surgical amendments from the 2026-07-03 platform audit (`PLATFORM-AUDIT.md`), applied while still READY (dispatch remains unauthorized). (a) **F-H1 (HIGH)**: TN-5 retracts its blessing of the surviving two-guard set as complete deletion-safety semantics and records that a shared-game / live-reports eligibility guard is REQUIRED — with that guard's implementation owned by CE-3, not E-250-02; E-250-02 AC-7 wording softened to "the correct guards for the removed `team_opponents` mechanism" (removal here does not create/worsen F-H1: the removed guards were empty-table no-ops). User accepted the interim risk (2026-07-04) with an operator hold — no report deletions until CE-3/E-253 lands the guard; the guard implementation stays in E-253, NOT added to E-250-02. (b) **Scouting `_ensure_season_row` fold (audit §2 MEDIUM)**: added TN-9 + E-250-02 AC-11 folding the scouting crawler's private season-row INSERT (`scouting.py:~351`) into the canonical `ensure_season_row` seam, since E-250-02 already edits both INSERT sites; this subsumes the scouting.py portion of AC-4 and makes the arch-subsystems.md "consolidation complete" claim true (that prose fix is E-250-04's). Story count unchanged (7); Success Criteria unchanged. No re-review requested — amendments are additive constraints, not scope expansions.
