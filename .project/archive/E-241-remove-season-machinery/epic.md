# E-241: Remove the cross-season machinery residue from the core

## Status
`COMPLETED`

## Overview
Remove the cross-season / multi-season *residue* that survives in the codebase as
the always-on `season_fallback` flag and the `_PROGRAM_TYPE_SUFFIX` season-suffix
taxonomy. Collapse season derivation to a single, dumb year-only `season_id`. This
is the root fix for a directive the operator has repeated several times: the
genuine cross-season machinery was deleted with the dashboard in E-239, but its
signaling residue — the orange "season fallback" badge that fires on *every*
report — was deliberately kept by prior passes (E-235 added it, E-236 dropped it
only from the coach line, E-239 explicitly kept it as operator telemetry). This
epic removes the concept at the root, not the symptom.

## Background & Context
**The recurring complaint.** The operator saw the orange "season fallback" badge
on a dev report's `/admin/reports` row and said "we stopped with the cross season
stuff... I thought we were rid of all of that." The badge is **structurally
100%-on noise**: every scouted opponent has `program_id NULL` → no program suffix →
year-only fallback → `SeasonDerivation.fallback_used = True`. It fires on the
cleanest data and would never fire on genuinely dirty data — exactly inverted from
a useful signal.

**Why prior passes did not fix it.** Each prior pass patched a symptom rather than
removing the concept:
- E-235 introduced the `season_fallback` flag, the `report_generation_runs.season_fallback`
  column, and the coach-footer degraded-confidence line.
- E-236 (IDEA-077 Option A) dropped `season_fallback` from the *coach-visible* line
  but deliberately KEPT the column as operator telemetry.
- E-239 (D2) explicitly decided "season_fallback telemetry STAYS" while removing
  the dashboard.

The operator's current directive overrides those keep decisions: remove the
concept from the bones.

**What E-239 already removed (do not re-plan).** The genuine cross-season
machinery — season ENUMERATION (`get_available_seasons`), season SELECTION-by-year
(`_pick_season_for_year`), and cross-season CAREER profiles
(`get_player_profile`'s `batting_seasons`/`pitching_seasons` lists) — was all
dashboard-only and was deleted with the dashboard in E-239. There is no
cross-season reader left. (Source: `.project/research/E-239-season-machinery.md`,
data-engineer, 2026-06-16.) What remains is the *derivation-side* residue this
epic targets.

**Expert consultation (2026-06-20).** Completed before stories were written —
data-engineer (migration + parity fate), software-engineer (scope + goldens fate),
claude-architect (context-layer surface), baseball-coach (game-day value). See
Technical Notes for the consolidated findings.

## Goals
- Season derivation always produces a year-only `season_id` (`str(season_year)`,
  or the current year when `season_year` is absent). No program-type suffix, no
  fallback taxonomy.
- The `season_fallback` concept is removed end-to-end: the `fallback_used`
  computation, the `SeasonDerivation` dataclass, the `derive_season_id_for_team_with_fallback`
  variant, the `report_generation_runs.season_fallback` column, the generator
  write, the `/admin/reports` badge, and the docs.
- The `_PROGRAM_TYPE_SUFFIX` mapping is deleted.
- Test fixtures and context/docs no longer carry the dead compound-season-slug
  footprint.
- **Zero change to any report's stat values** (Epic-A goldens + aggregate parity
  stay green).

## Non-Goals
- **Dropping the `season_id` column.** It is the partition key (PK of
  `player_season_batting`/`player_season_pitching`, a column on `games`/`seasons`,
  an FK target) and the load-bearing within-report game filter that keeps a team's
  2025 and 2026 boxscores from blending. It stays. (per TN-1)
- **Dropping or simplifying the `programs.program_type` column.** Only the
  `_PROGRAM_TYPE_SUFFIX` *mapping* is removed. The column has a second, non-season
  consumer — `.claude/rules/pitch-rules.md` pitch-count rule selection. (per TN-6)
- **Touching the season-keyed aggregate-parity system** (`canonical_recompute`,
  `verify_aggregates`, `bb report verify-aggregates`). It is a within-season
  correctness guard, not cross-season machinery, and is slug-format-agnostic — it
  operates year-only for free once derivation emits year-only slugs. (per TN-2)
- **Migrating the ~30 inline-season test files** that use compound slugs as opaque
  partition-key literals. Cosmetic churn with no behavioral meaning. Only the two
  named shared fixtures + their tightly-coupled tests are migrated. (per TN-5)
- **Cross-team identity, multi-season rollups, longitudinal tracking** — already
  de-scoped (ROADMAP §7); nothing to do here.

## Success Criteria
- Season derivation returns a year-only `season_id` for every team; no code path
  produces a `YYYY-suffix` slug. This covers BOTH compound-slug producers: the
  loaders' `derive_season_id_for_team` AND the scouting crawler's `_derive_season_id`
  (`src/gamechanger/crawlers/scouting.py`), which the reports pipeline invokes live
  via `generator.py:1625` and which writes the slug to `seasons` + `scouting_runs`.
  Both are collapsed in E-241-06.
- `grep -rn season_fallback src/` returns no matches; the
  `report_generation_runs.season_fallback` column no longer exists after migration
  006; `/admin/reports` renders no "season fallback" badge.
- `_PROGRAM_TYPE_SUFFIX`, `SeasonDerivation`, and
  `derive_season_id_for_team_with_fallback` no longer exist in
  `src/gamechanger/loaders/__init__.py`; `derive_season_id_for_team` retains its
  `tuple[str, int | None]` signature.
- `programs.program_type` column and `.claude/rules/pitch-rules.md` are unchanged.
- The two named shared fixtures and their coupled tests carry year-only slugs; the
  dead compound-concept test class is deleted; the golden JSON
  (`tests/fixtures/golden/report_stats.json`) is byte-identical (no regen).
- The full test suite passes (`python -m pytest tests/` → 0 failed) with the
  epic's changes applied in the main checkout.
- The Epic-A golden stat tables and `bb report verify-aggregates` parity are green
  and unchanged in value.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-241-01 | Strip the season_fallback telemetry chain (generator / db / admin) | DONE | None | - |
| E-241-02 | Migration 006: drop `report_generation_runs.season_fallback` + season_id fragmentation safety | DONE | E-241-01, E-241-06 | - |
| E-241-03 | Migrate the two shared fixtures to year-only slugs; delete the dead compound-season test class | DONE | None | - |
| E-241-04 | Rewrite the season-machinery sections of `architecture-subsystems.md` | DONE | E-241-06 | - |
| E-241-05 | Update `architecture.md` + `operations.md` season_fallback documentation | DONE | E-241-01, E-241-02, E-241-06 | - |
| E-241-06 | Collapse season derivation to year-only — loaders + scouting crawler (delete the fallback variant + suffix taxonomy) | DONE | E-241-01 | - |

**Story-order note**: numbers are identifiers, not execution order — dependencies
define order. The dependency-enforced order of the code stories is
**01 (telemetry strip) → 06 (derivation collapse, both producers) → 02 (migration)**.
01 first: stripping the telemetry removes the generator's only direct call to
`derive_season_id_for_team_with_fallback`, so 06 can then delete that variant against
zero direct callers (per TN-4 sequencing). 06 before 02: the migration's preferred
no-op-default fragmentation safety is durable only once BOTH compound-slug producers
(loaders + crawler) emit year-only, and the crawler producer is fixed in 06 — so 02
is blocked by 06 as well as 01 (per TN-7). 03 (fixtures) is independent. 06 is
numbered last only because it was split out of the original combined story after the
initial draft; its dependency edges place it after 01 and before 02.

## Dispatch Team
<!-- Implementing agents. code-reviewer and product-manager are spawned as dispatch
     infrastructure (not listed here) per .claude/rules/dispatch-pattern.md. -->
- software-engineer
- data-engineer
- claude-architect
- docs-writer

## Technical Notes

### TN-1 — The load-bearing kernel that STAYS
A single `season_id` per team is the within-report game filter that keeps a team's
2025 and 2026 boxscores from blending into one report. Per the E-239 data-engineer
recon, the derivation function is *inherently single-season* — it always derives
exactly one `season_id` for one team; there is no separable "multi-season path"
inside it to strip. Therefore the `season_id` column, the `seasons` table,
`ensure_season_row`, and `canonical_recompute` all stay. The change is to the
*value* derivation produces (year-only instead of `YYYY-suffix`) and the removal of
the `fallback_used` telemetry it carried — not to the partition key itself.

### TN-2 — The aggregate-parity system is OUT OF SCOPE (data-engineer)
`canonical_recompute` / `verify_aggregates` / `bb report verify-aggregates` are a
within-season correctness guard: for each `(team_id, season_id)` scope they
recompute `boxscore_only` aggregates from per-game rows and diff against stored
`player_season_*`. They never enumerate or compare across seasons — they iterate
the distinct scopes already present in the data and check each independently. The
parity code is agnostic to the slug *format* (it reads whatever string is in the
column), so once derivation emits year-only slugs the parity system already
operates year-only with **zero code change**. Do NOT "simplify the keying" —
`season_id` is the actual PK of the aggregate tables; changing it would be a schema
change with a large blast radius and no benefit. This epic does not touch the
parity system.

### TN-3 — ZERO production report-stat change (the loud flag)
Member-team sync was removed in E-239. Every team created now is a scouted opponent
with `program_id NULL`, which already derives a year-only `season_id` (`2026`)
today. The derivation collapse therefore changes output ONLY for the now-nonexistent
member-team path (which alone could produce `2026-spring-hs`). No live path's
`season_id` value changes, so no report's stat values move. The Epic-A golden stat
tables and the aggregate-parity diff MUST stay green and unchanged in value — any
movement is a defect, not an expected consequence. The golden JSON keys on the
`season_year` integer (`generator.py:365-371`), never on the `season_id` string, so
migrating fixture slugs is invisible to rendered output (per TN-5).

### TN-4 — Derivation collapse end state + telemetry-first sequencing (software-engineer)
The SE code work is split into two stories with a real, clean dependency edge and
**no shared files**:
- **E-241-01 (telemetry strip, runs first)**: the generator switches its
  season-derivation call from `derive_season_id_for_team_with_fallback` to the
  plain `derive_season_id_for_team` wrapper and stops capturing/writing
  `season_fallback`; the read/display references (`api/db.py`, `reports.html`,
  `reports_admin.py`) are stripped. After 01, `derive_season_id_for_team_with_fallback`
  still exists but has no *direct* caller outside the `derive_season_id_for_team`
  wrapper, and derivation still emits compound slugs (harmless — no member teams
  exist). Green boundary.
- **E-241-06 (derivation collapse, blocked by 01)**: now that the generator no
  longer calls the variant directly, `derive_season_id_for_team` is rewritten to
  produce a year-only `season_id` directly, and `derive_season_id_for_team_with_fallback`,
  the `SeasonDerivation` dataclass, and `_PROGRAM_TYPE_SUFFIX` are deleted.
  Sequencing this second avoids a red boundary (deleting the variant while the
  generator still called it would break import/compile). **E-241-06 ALSO collapses
  the second compound-slug producer — the scouting crawler** (see below).

**The SECOND live compound-slug producer (E-241-06).** `src/gamechanger/crawlers/scouting.py`
has its own season machinery, independent of the loaders: `_derive_season_id`
(L604, default `season_suffix="spring-hs"`), the `ScoutingCrawler.__init__`
`season_suffix="spring-hs"` parameter (L145), and a duplicate `_ensure_season_row`
(L494). It is LIVE in the sole reports path — `generator.py:1625` constructs
`ScoutingCrawler(...)` with no `season_suffix` (→ default) and calls
`scout_team(public_id)` with no `season_id`, so the crawler derives `2026-spring-hs`
and writes it to `seasons` (L184) and `scouting_runs` (L185). Stat values are SAFE
(the loader re-derives year-only at `scouting_loader.py:108`, so this is tracking-row
provenance only — TN-3 holds), but the compound slug lands in `seasons`/`scouting_runs`
every run. E-241-06 collapses the crawler: drop the `season_suffix` parameter,
collapse `_derive_season_id` to year-only, and route the crawler's `_ensure_season_row`
to year-only. Only `generator.py:1625` and the module-level helper construct the
crawler and neither passes `season_suffix`, so dropping the parameter is safe.
**This makes the Success Criterion "no code path produces a YYYY-suffix slug" true at
closure, and makes the no-op-default migration (TN-7) durable** — without the crawler
fix, migration 006 would normalize the `seasons` rows but the next report run would
re-create `2026-spring-hs`, re-fragmenting.

Derivation end state (E-241-06): `derive_season_id_for_team(db, team_id)` keeps its
`tuple[str, int | None]` return signature (all three loader call sites unpack a
2-tuple — keeping the tuple = zero churn at the call sites; only the returned string
value changes). Its body produces a year-only `season_id` derived from the team's
`season_year` (current year when `season_year` is absent). `ensure_season_row`
already handles year-only input (`season_type='default'`); its now-dead
compound-slug split branch is removed for honesty. The implementer must run the
affected loader/report/crawler test modules and fix any assertion that expected a
loader or the crawler to emit a compound `season_id` (recon found
`tests/test_season_id_derivation.py` and `tests/test_scouting_crawler.py`
exercise the derivation contracts; the implementer is responsible for any
compound-output assertion the suite surfaces).

### TN-5 — Fixtures fate (software-engineer)
Compound slugs appear in ~33 test files, but only `tests/test_season_id_derivation.py`
exercises the derivation *contract* (it changes under TN-4 regardless). Everywhere
else the slug is an opaque partition-key literal — any consistent string works, so
migrating those ~30 inline-season files is churn and is out of scope. The two named
shared fixtures have tight, verified consumer sets:
- `tests/fixtures/seed.sql` → `test_report_golden.py` + `test_schema_queries.py`
- `tests/fixtures/parity_consistent.sql` → `test_aggregate_parity.py`

Migrate `2026-spring-hs` → `2026` and `2025-summer-legion` → `2025` (and set those
seasons' `season_type` to `default` for coherence), **keeping the two-season
structure** as the cross-scope filter guard (distinct YEARS, so no PK collision).
De-risk facts verified by recon: the golden JSON carries zero `season_id` slugs and
the report output keys on the `season_year` integer, so the golden stays
byte-identical (no regen). One consumer tests the compound-season *concept* itself
(`tests/test_schema_queries.py` class filtering `season_type = 'spring-hs'` /
`'summer-legion'` and asserting `season_id == '2026-spring-hs'`) — DELETE that test
class (or rewrite it to filter by `year`); do NOT mechanically slug-swap it, since
year-only makes both seasons `season_type='default'` and the class tests dead
behavior.

### TN-6 — `programs.program_type` column STAYS (claude-architect trap)
The change removes the `_PROGRAM_TYPE_SUFFIX` *mapping* (the season-suffix dict),
NOT the `programs.program_type` *column*. The column has a second, non-season
consumer: `.claude/rules/pitch-rules.md` selects the pitch-count rule unit
(hs/legion/usssa) from it. Dropping the column would break pitch-rule selection.
Because the column stays, `pitch-rules.md` is untouched and no coaching change is
needed.

### TN-7 — Migration 006 (data-engineer)
`report_generation_runs.season_fallback` is a plain `INTEGER NOT NULL DEFAULT 0`
(`migrations/002_report_generation_runs.sql:86`) with no index, FK, generated
column, or view reference, so its removal is a direct `ALTER TABLE ... DROP COLUMN`
on SQLite 3.35+ — not a 12-step table rebuild. The drop must land in this epic
alongside the code strip because `apply_migrations` runs at startup and the read
path would break the instant the column disappeared without the code change.
**Sequencing:** E-241-02 is blocked by BOTH E-241-01 and E-241-06.
- Blocked by **01** for the column DROP: 01 stops reading/writing `season_fallback`
  (it leaves the column physically present but unreferenced), then 02 drops it. At
  each story's staging boundary the suite is green.
- Blocked by **06** for the fragmentation-safety DURABILITY: the preferred no-op
  default is durable only once BOTH compound-slug producers emit year-only, and the
  crawler producer is collapsed in 06. If 02 landed before 06, the next report run's
  crawler would re-create `2026-spring-hs` in `seasons`/`scouting_runs`, defeating the
  no-op default's "no persisted DB can fragment" guarantee. 06 → 02 makes this a real
  dependency edge, not just prose.

**Season_id fragmentation safety (data-engineer + software-engineer converged):**
`season_id` is an FK target and join/group key, so if derivation begins emitting
`2026` while a persisted DB still holds `2026-spring-hs` rows, that team's season
fragments into two partitions and the single-season report query silently misses
half the data. By the evidence this is fixtures-only — the live dev DB is already
year-only and production is reports-first and reset-friendly. **Preferred mechanism:
the no-op default** — DROP COLUMN only, no season_id rewrite. This is correct
because (a) the live data is already year-only, and (b) E-241-06's crawler fix
(above) stops new compound slugs from being created, so the no-op default is
genuinely durable, not just momentarily clean. The worktree has no `data/` access,
so a deterministic migration that is correct regardless of DB state is the safe
default anyway.

**If — and only if — persisted compound `season_id` values are actually found**, a
normalization is needed, and a plain `UPDATE` is technically impossible:
`seasons.season_id` is a TEXT PK referenced by SEVEN child columns, NONE with
`ON UPDATE CASCADE`, and migrations run under `foreign_keys=ON`. The correct
mechanism is **insert-new-year-only-parent → repoint-all-7-children →
delete-old-compound-parent**, enumerating ALL SEVEN FK children — including
`report_generation_runs.season_id_used` (`migrations/002:83`, the easy-to-miss FK
sibling of the column 006 drops) — and collision-aware as **detect-and-fail** (NOT
`UPDATE OR REPLACE`, which would silently merge two same-year partitions). Do NOT
describe this as "FK-safe ordering" — no ordering of plain `UPDATE`s exists. Scouted
opponents are always year-only so no live collision exists, but the mechanism must
fail loudly if one is ever encountered.

`tests/test_migrations.py` is owned solely by this story (it currently asserts the
column exists/defaults to 0 — those assertions move to "column absent" under 006).
E-241-01 must NOT touch `test_migrations.py`.

### TN-8 — Context-layer surface (claude-architect)
- **`.claude/rules/architecture-subsystems.md`** (E-241-04, routes to
  claude-architect): "Season_id Derivation (Detail)" (≈L36-38) — REWRITE to
  year-only; "Canonical-Function Additive Extension Pattern" (≈L28-30) — TRIM the
  dying `derive_season_id_for_team_with_fallback`/`SeasonDerivation` worked example,
  KEEP the surviving `ensure_team_row_with_provenance`/`EnsureTeamResult` example
  (the pattern stays valuable with one live example); "Filesystem vs DB Season_id
  Decoupling" (≈L40-42) — RESOLVE: it references the suffix-taxonomy slugs and the
  `data/raw/` layout E-239 orphaned, so trim the suffix examples or retire the
  section per the implementer's read of current reality.
- **`CLAUDE.md`** "Season_id derivation" entry — VERIFY byte-untouched: it names
  only `derive_season_id_for_team()` + `ensure_season_row()` (not the `_with_fallback`
  sibling or program_type), and the tuple return shape is unchanged (TN-4), so the
  wording stands. "Canonical season-aggregate recompute" entry — NO CHANGE.
- **`.claude/rules/data-model.md`** — OUT OF SCOPE / byte-untouched (CONFIRMED, arch
  recon 2026-06-20). It references none of `season_fallback` / `SeasonDerivation` /
  `_with_fallback` / the suffix taxonomy / `derive_season_id_for_team`; its "Season
  year" footgun documents the NULL→current-year behavior that SURVIVES the collapse.
  The only two `report_generation_runs` mentions (L59-62) sit inside the
  `scheduled_report_runs` (migration 005) entry by contrast only — the
  CASCADE-vs-SET-NULL mirror — not a schema/column block, so `season_fallback` is
  not enumerated there and the migration-006 drop does not touch it. (E-238-02
  naive-grep-trap lesson — do not open it for an edit.)

### TN-9 — Documentation surface (docs-writer, doc gate)
- `docs/admin/architecture.md` — the trust-flags table row for `season_fallback`
  (≈L105) and the `program_type` value list (≈L180).
- `docs/admin/operations.md` — the `season_fallback` run-record column entry, the
  badge meaning, the troubleshooting recipe that names
  `derive_season_id_for_team_with_fallback()`, and the change-log (≈L531, L554,
  L601, L607, L830).

### TN-10 — History is NOT rewritten (PM)
`docs/ROADMAP.md` (the Option-A decision record + IDEA-077 references) and
`docs/vision-signals.md` L42 (the 2026-06-14 signal this epic answers) are left
as-is. E-241 is NOT a ROADMAP §5 slice (A-E are all COMPLETED; this is a follow-on
cleanup), so no §0 tracking-table edit. The vision signal stays for the next
"curate the vision" session.

### TN-11 — Closure obligations (agent-memory refresh; not stories)
At the closure context-layer assessment gate, two agent-memory files name the
`derive_season_id_for_team` → `_with_fallback` / `SeasonDerivation` additive-extension
example as a "durable pattern" — dead after this epic (mirrors the
`architecture-subsystems.md` trim in E-241-04): claude-architect's
`.claude/agent-memory/claude-architect/MEMORY.md` and the PM's
`.claude/agent-memory/product-manager/MEMORY.md`. Both must be refreshed at closure.
Agent-memory edits are not stories — the context-layer gate catches them. The
baseball-coach `e235`/`e236` review memory files that mention `season_fallback` are
frozen historical records — leave them untouched.

### TN-12 — Scope decision: the `season_id` override escape hatch (codex iter-2 D1)
Codex iter-2 found that `ScoutingCrawler.scout_team(public_id, season_id=None)` accepts
an explicit `season_id` override — a path that could re-introduce a compound slug and
make the "no code path produces a YYYY-suffix slug" Success Criterion an asterisked,
not absolute, claim. SE's caller-check + a whole-repo grep (2026-06-20) established the
override is **prod-dead**: the sole live `scout_team` caller (`generator.py:1626`) passes
no override; the param is forwarded only by `scout_all` (test-only) and
`scout_all_in_memory` (zero callers anywhere) — both dead opponent-discovery batch
methods orphaned by E-239, and both entangled with the override (they feed it to the
recency check before derivation). **Decision (PM, work-definition): Option 1** — drop
the `season_id` param from `scout_team` and DELETE `scout_all` + `scout_all_in_memory`
+ their tests (E-241-06). This keeps the Success Criterion honestly absolute, nets a
SMALLER code+test surface, and — because the methods are entangled with the
season-machinery escape hatch this epic removes — is the direct consequence of the
removal, not unrelated cleanup. The one acknowledged scope effect: it deletes two
provably-dead E-239-orphan methods inside E-241 (rather than deferring them to a
separate dead-code sweep). The narrower alternatives considered and rejected:
Minimal-A (keep the dead methods, restructure their recency call to not depend on the
override) invests effort to preserve zero-caller code; Option B (keep the param, narrow
the criterion to "no derivation/persisted-write path") leaves a live escape hatch and
weakens the headline guarantee the operator cares about. (Surfaced to the user in the
READY summary so the scope choice is visible.)

## Open Questions
- None blocking. The migration *mechanism* for season_id fragmentation safety
  (no-op default vs. the insert-parent/repoint-7-children/delete normalization) is
  delegated to the implementing data-engineer within the TN-7 constraints; the no-op
  default is preferred and is durable given E-241-06's crawler fix.

## History
- 2026-06-20: Created (DRAFT). Discovery completed with all four domain experts
  (data-engineer, software-engineer, claude-architect, baseball-coach); see
  Technical Notes for consolidated findings.
- 2026-06-20: Refined to READY. **Motivation** — the reports-first reframe (E-239
  removed the dashboard/cross-season machinery, but its derivation-side residue — the
  always-on `season_fallback` badge + the `_PROGRAM_TYPE_SUFFIX` taxonomy — survived).
  This epic removes the concept at the ROOT (the operator's repeated ask), not another
  leaf-patch. **Discovery** cut a planned parity story (de Q2: the season-keyed parity
  system is a within-season correctness guard, slug-format-agnostic, untouched) and
  pinned the `programs.program_type`-column-STAYS trap (TN-6: a second consumer,
  `.claude/rules/pitch-rules.md`, so only the suffix MAPPING is removed). **Restructure**
  — the SE work split 5→6 stories (telemetry-strip 01 → derivation-collapse 06) on a
  clean no-shared-files seam after review. **Key catches** — review iter-1 A1 found a
  SECOND live compound-slug producer (the scouting crawler `_derive_season_id`), folded
  into 06; Codex iter-2 D1 found the `season_id` override escape hatch, resolved via the
  Option-1 scope decision (TN-12: drop the param + delete two provably-dead E-239-orphan
  batch methods, keeping the Success Criterion honestly absolute). Zero production
  stat-value change throughout (TN-3). All review findings accepted; see the scorecard.
- 2026-06-21: COMPLETED. All 6 stories DONE. **Delivered** — season derivation now
  emits a year-only `season_id` from both producers (loaders `derive_season_id_for_team`
  + scouting crawler `_derive_season_id`); the `season_fallback` concept is removed
  end-to-end (the `fallback_used` computation, the `SeasonDerivation` dataclass, the
  `derive_season_id_for_team_with_fallback` variant, the `report_generation_runs.season_fallback`
  column via migration 006, the generator write, the `/admin/reports` badge, and the
  admin docs); `_PROGRAM_TYPE_SUFFIX` is deleted; the two named shared fixtures + their
  coupled tests carry year-only slugs and the dead compound-season test class is gone;
  the context-layer + admin docs describe year-only derivation. Zero production stat-value
  change (Epic-A goldens + aggregate parity green and unchanged; golden JSON byte-identical,
  not regenerated). `programs.program_type` column + `.claude/rules/pitch-rules.md` left
  intact (TN-6). The TN-12 Option-1 deletions landed (the `season_id` override param +
  `scout_all`/`scout_all_in_memory`); the further-orphaned freshness-gating cluster was
  deliberately DEFERRED-WHOLE to a follow-up sweep IDEA (see Ideas note below) rather than
  half-removed. **Pre-closure full suite GREEN: 3355 passed, 0 failed** (count dropped from
  prior epics' baseline ∵ dead-code + compound-fixture tests removed). **Two honest notes:**
  (a) E-241-02 made a FORCED cross-story edit to `tests/test_report_generator.py` (changed
  `run["season_fallback"] == 0` → `"season_fallback" not in run`) — a file outside 02's
  listed "Files to Modify" set, but the mechanical and unavoidable consequence of the column
  drop (`_read_run_record`'s `SELECT rgr.*` stops carrying the key, so the old assertion
  would KeyError). 02 was the only active story at the time, so there was no file contention;
  the edit was ruled acceptable (PM) as the same shape as the E-239 importer-gate pattern and
  required by the full-suite-green gate. (b) E-241-06's AC-6 "test set COMPLETE" recon claim
  was one file short: `tests/test_game_start_time.py` seeded a non-format-invariant compound
  slug (`2025-spring-hs`) that the grep-based recon missed and that grep-based per-story AC
  verification structurally cannot catch (only running the full suite surfaces a runtime
  regression in an un-enumerated file). It was caught by the Phase-4b Codex pass + the
  full-suite-green gate (exactly the designed backstop) and fixed in remediation (fixture →
  year-only `2025`). **Documentation assessment** — the doc-update trigger fired (schema +
  behavior change) but was satisfied IN-EPIC by E-241-05 (`docs/admin/architecture.md` +
  `operations.md` updated to year-only / post-006); no further docs-writer dispatch needed.
  **Context-layer assessment** — all six triggers evaluated: (1) YES, (2) YES, (3) YES,
  (4) NO, (5) YES, (6) NO. The fired triggers were codified by claude-architect at closure
  (`architecture-subsystems.md` was E-241-04; the TN-11 agent-memory refresh of the dead
  `derive_season_id_for_team_with_fallback`/`SeasonDerivation` additive-extension "durable
  pattern" reference in claude-architect's + the PM's MEMORY.md; plus the two new footguns).
  **Ideas** — a "post-E-241 dead-code + stale-example sweep" IDEA was filed at closure
  covering: the `scout_all`-orphaned freshness-gating cluster, the dead
  `format_season_display` helper, and the stale compound-slug example comments (incl. the
  DO-NOT-EDIT frozen migration 001:81). **Vision** — the 2026-06-14 signal (vision-signals.md
  L42) that this epic answers is left in place per TN-10 for the next "curate the vision"
  session.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iter-1 — CR spec audit | 3 | 3 | 0 |
| Internal iter-1 — Holistic team (de/se/arch/coach) | 4 | 4 | 0 |
| Codex spec review iter-1 | 4 | 4 | 0 |
| Codex spec review iter-2 | 3 | 3 | 0 |
| **Total** | **14** | **14** | **0** |

Scorecard notes: Internal iter-1 produced 7 consolidated findings (A1–A7) — the CR
spec-audit row counts F1/F2/F3 (= dupes of A1/A3/A5, not double-counted); the holistic
row counts the remaining A2/A4/A6/A7 (arch OBS-1 = the A7 closure obligation; arch OBS-2
and the baseball-coach holistic were clean / no-action). Codex iter-1 = C1–C4; Codex
iter-2 = D1–D3. Every finding was ACCEPTED; none dismissed.

### Dispatch & Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — 01 | 0 | 0 | 0 |
| Per-story CR — 06 | 1 | 1 | 0 |
| Per-story CR — 02 | 0 | 0 | 0 |
| Per-story CR — 03 | 0 | 0 | 0 |
| Per-story CR — 05 | 0 | 0 | 0 |
| CR integration review (Phase 4a) | 2 | 2 | 0 |
| Codex code review (Phase 4b) | 2 | 2 | 0 |
| **Total** | **5** | **5** | **0** |

Dispatch scorecard notes: Story 04 was context-layer-only (`.claude/rules/architecture-subsystems.md`)
→ code-reviewer SKIPPED, PM-alone AC verification (no CR row). Story 06's single per-story
CR finding was the SHOULD-FIX that the orphaned dead-code surface is larger than SE flagged
(the whole `scout_all` freshness-gating cluster); disposition = ACCEPTED-AS-VALID but
DEFERRED-WHOLE to the closure sweep IDEA (PM work-definition ruling — not a code change in 06;
the in-flight `_resolve_team_id` deletion was reverted so 06 landed exactly at its spec'd scope).
Story 02's cross-story `test_report_generator.py` edit was a PM AC-verify judgment (forced
mechanical consequence of the column drop), not a CR finding. Phase 4a = 2 stale compound-slug
docstring examples (scouting.py:79, generator.py:765) → year-only. Phase 4b = (1) crawler
`_ensure_season_row` season_type 'unknown'→'default' to honor the E-241 contract, (2) the
`test_game_start_time.py` compound-seed regression (the AC-6 gap). All accepted/fixed; none
dismissed.
