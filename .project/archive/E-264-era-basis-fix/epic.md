# E-264: League-Aware ERA Basis Fix

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- READY set 2026-07-15 (freshness clock starts here; re-confirm by 2026-09-13 if not yet dispatched). -->

## Overview
Our scouting reports compute ERA on a hardcoded 9-inning basis (`ER × 27 / ip_outs`) for every team, but GameChanger computes ERA on a per-team-season **game-length** basis (a configured integer, observed 6 or 7). The result is that our reported ERA overstates the number the coach sees in the GC app for the same team by ~29% — a visible, checkable contradiction of the source of truth the coach already trusts, on the single most-scanned pitching stat. This epic reads each team's actual game-length basis from GameChanger, stores it, and applies it at the two ERA computation sites so our ERA reconciles with the GC app. It also discloses the basis on the report so a coach always knows which game length produced the number.

## Background & Context
This epic was prompted by an empirical api-scout investigation against live GameChanger data (this session), which established the correct formula and its source with zero scatter:

- **GC formula:** `ERA = innings_per_game × ER / IP`, where `innings_per_game` is a **per-team-season configured integer** (observed 6 or 7). Back-solved exactly (to 4 decimals) across 7 owned teams and every pitcher.
- **It is NOT an age/league rule.** Two 12U teams differ (one 6, one 7); a 10U is set to 7. Any hardcoded age×league table would be actively wrong. The value reflects the format each team actually plays, so we must **read the per-team field**, never derive it from classification.
- **Source:** `settings.scorekeeping.bats.innings_per_game` in the authenticated `GET /teams/{gc_uuid}` (Accept: `application/vnd.gc.com.team+json; version=0.10.0`). Integer.
- **Opponent-capable (the primary report case):** the authenticated `GET /teams/{gc_uuid}` returns this field even for non-owned teams, given the `gc_uuid` — resolvable via the existing `public_id`→`gc_uuid` search bridge the report generator already uses for spray charts. The field is NOT on the public profile (`GET /public/teams/{public_id}`), so resolution must go through the authenticated endpoint. (Individual opponents may return 403 for access/privacy states; the fetch tolerates that and falls back — see TN-6 and E-264-02 AC-2.) (Contrast: the season-stats endpoint is 403 for opponents; the team-metadata endpoint is not.)
- **Fallback = 7** when the field cannot be read (missing gc_uuid, etc.) — NOT 9, NOT an age table. 7 is the modal, correct value for HS/Legion/13U+/most youth. (Reserve 9 only if an adult/senior team ever appears — out of scope here.)

Expert consultation completed during formation:
- **data-engineer** owns the storage shape (see Technical Notes TN-2/TN-3/TN-4).
- **baseball-coach** confirmed fallback 7, the ERA-only scope (see TN-9), and the display-disclosure requirement and its exact copy (see TN-7).
- **software-engineer** confirmed the computation sites and the test obligation (see TN-5/TN-8).
- **api-scout** performed the live empirical investigation (findings above) and owns the endpoint-doc correction (E-264-04).

This epic is FILE-DISJOINT from and sequenced AHEAD of E-263 (Deep Scout, READY, not dispatched). It does NOT touch E-263 or its planned `deep_scout` framework.

## Goals
- Our reported ERA reconciles with the GameChanger app for the same team, on the same game-length basis GC uses.
- The game-length basis is read from GameChanger per team-season (opponent-capable), stored, and self-heals on report regeneration.
- Every ERA on the report discloses the basis it was computed on; an assumed (fallback) basis is never presented silently.
- Existing regression guards (golden stat table, report e2e, db) are updated in lockstep so the suite stays green.

## Non-Goals
- **K/9 is NOT changed.** Our report's K/9 (`SO × 27 / outs`) is our own stat, not a GC-displayed stat, and coaches benchmark traditional 9-inning K/9 against external recruiting standards. It stays exactly as-is on its 9-inning basis. The deliberate, holistic K-rate decision (K/9 vs K/G vs K/BF vs K/BB) belongs to the upcoming pitcher-outings epic, not a piecemeal edit here (see TN-9; tracked as IDEA-141).
- **WHIP is NOT changed.** WHIP is per-inning (`(BB+H)/IP`, ×3 at the outs level) and already correct — no game-length multiplier applies.
- No new `bb data` CLI command and no backfill maintenance pass (the value self-heals through report regeneration; see TN-4). Consequently no CLAUDE.md/context-layer change.
- No age/league→innings mapping table. Read the per-team field.
- Retroactively re-deriving ERA on already-frozen reports. Reports are self-contained static HTML frozen at generation; existing frozen reports keep their old ERA until they naturally expire (14-day) and are regenerated. This is acceptable.

## Success Criteria
- For a team whose `innings_per_game` is known (e.g. 7), the report ERA equals `ER × (innings_per_game × 3) / ip_outs` and matches the GC app value.
- For a team whose basis is unreadable, ERA is computed on the fallback 7-inning basis AND the report visibly discloses the assumed basis via the header asterisk and footnote per TN-7.
- Every ERA surface on the report carries a basis label per TN-7 (known and assumed cases).
- `teams.innings_per_game` is populated (as a fetched integer) for any team a report is generated for after this epic **and whose basis GameChanger exposes**; a team whose basis is unreadable (unresolved gc_uuid, 403, or absent field) keeps NULL and renders on the assumed-basis path (per E-264-02 AC-2), as does a never-reported team.
- `python -m pytest tests/` is green with the regenerated golden and updated suites (TN-8).
- The `GET /teams/{team_id}` endpoint doc documents `settings.scorekeeping.bats.innings_per_game` as the authoritative ERA basis and corrects the K/G mislabel (E-264-04).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-264-01 | Storage foundation: migration 012 + reader JOIN + ensure_team_row plumbing | DONE | None | data-engineer |
| E-264-02 | ERA basis correction: fetch, apply at the ERA sites, regenerate guards | DONE | E-264-01 | software-engineer |
| E-264-03 | Visible ERA-basis disclosure on the report | DONE | E-264-02 | software-engineer |
| E-264-04 | Endpoint-doc: authoritative ERA basis + K/G mislabel fix | DONE | None | api-scout |

## Dispatch Team
- data-engineer
- software-engineer
- api-scout
<!-- baseball-coach is advisory (copy/scope), not an implementer. -->

## Technical Notes

### TN-1: The ERA basis — value and source
GC's ERA formula is `innings_per_game × ER / IP`. `innings_per_game` is a per-team-season integer read from `settings.scorekeeping.bats.innings_per_game` in the authenticated `GET /teams/{gc_uuid}` (Accept `application/vnd.gc.com.team+json; version=0.10.0`). It is opponent-capable given the `gc_uuid` (not on the public profile; individual opponents may 403 for access/privacy states, handled by the NULL→fallback-7 path). Fallback = 7. Our internal stat is stored as `ip_outs` (integer outs, 1 IP = 3 outs), so the equivalent computation over our storage is `ER × (innings_per_game × 3) / ip_outs`. Do NOT derive the basis from team classification/age — the value does not map to age (TN empirical finding).

### TN-2: Storage shape (data-engineer, final)
`teams` IS the team-season entity in this single-season-scoped schema (it already carries `season_year`, `classification`, `gc_uuid`; one `teams` row = one team-season = one `public_id`). The basis is a per-team-season constant, so it is a column on `teams`.

Migration `012` adds a **bare NULLABLE** column (no default):
```sql
-- Per-team-season ERA/K-per-game denominator basis (GC's regulation innings/game).
-- NULLABLE BY DESIGN: NULL = never successfully fetched -> ERA computed on the
-- assumed 7-inning fallback and the report MUST flag "(assumed)". A stored integer
-- = fetched from settings.scorekeeping.bats.innings_per_game (GET /teams/{gc_uuid}),
-- shown without the assumed flag. DO NOT add a DEFAULT or NOT NULL here: it would
-- collapse the fetched-vs-assumed distinction the display layer depends on.
ALTER TABLE teams ADD COLUMN innings_per_game INTEGER;
```
**NULL is load-bearing provenance.** `SQLite ADD COLUMN` with no default leaves every existing row NULL — correct, because we have not fetched those teams' basis yet, so they ARE assumed until regenerated. A future `DEFAULT 7` or `NOT NULL` backfill would silently erase the assumed signal and break the display disclosure — this must not happen.

### TN-3: Reader threading (query-time, E-259 posture)
Season ERA is derived at query time (E-259 retired the stored `player_season_*` tables). `get_season_pitching` (`src/api/db.py:520`) wraps the SHARED single-source projection `pitching_recompute_select()` (`src/db/season_projection.py`) as a subquery, with the `players`/`team_rosters` joins layered on the OUTSIDE. `innings_per_game` MUST be added at the **OUTER wrapper level** (alongside the existing outer joins / outer SELECT), NOT inside `pitching_recompute_select()` — that shared projection has other consumers and modifying it would break the single-source invariant. The outer level is post-aggregation (one row per player), so there is no `GROUP BY` interaction. Carry `teams.innings_per_game` RAW (possibly NULL) on every pitcher row so the basis and its provenance travel with the data to the computation sites; the implementer chooses the mechanism (an outer `LEFT JOIN teams` or a scalar subselect on the already-filtered `team_id` — mind bind-param position). Do NOT `COALESCE` in SQL — the display layer needs to see the NULL. The perspective filter is untouched (the added read keys on the already-filtered `team_id`).

### TN-4: Self-heal plumbing (mirror `season_year` exactly)
`ensure_team_row` / `ensure_team_row_with_provenance` (`src/db/teams.py`) take a new `innings_per_game: int | None` param; a new `_backfill_innings_per_game` mirrors `_backfill_season_year` — it fills an existing NULL from a non-NULL fetched value and MUST NOT clobber a stored integer with a later `None` (a failed re-fetch keeps the last known good). Every report regeneration that re-touches a team writes the fetched value. No separate `bb data` backfill command (the value is fetched as a normal part of report generation, so regeneration IS the backfill).

### TN-5: The `×27` sites — which change (scope b)
`27` = 9 innings × 3 outs appears at three sites. Under this epic's ERA-only scope, only the two ERA sites change; the K/9 sites are UNCHANGED.
- **CHANGES (ERA):**
  - `src/reports/generator.py:453` — `_compute_pitching_rates`, the display ERA string: `(er * 27) / ip_outs` → `(er * basis * 3) / ip_outs` where `basis = innings_per_game if innings_per_game is not None else 7` (the explicit `is not None` guard is load-bearing — a bare `if not None` is always True and would never fall back, crashing `None * 3` on the assumed path).
  - `src/reports/renderer.py:264` — `_era_raw` (heat-map ranking input): same substitution. This site is scale-invariant for ranking (a team-uniform basis does not change relative order), but it MUST change in lockstep to a single basis constant so no hardcoded `27` diverges.
- **UNCHANGED (K/9, per Non-Goals):** `src/reports/generator.py:454`, `src/reports/renderer.py:265`, `src/api/db.py:369` (`build_pitcher_profiles` `season_k9`). Leave these on `27`.

The `7` fallback constant lives at the compute site (TN-3 keeps SQL NULL-carrying). Because both the `× 3` and the fallback `7` now appear at both compute sites, keep them from drifting — a single shared basis definition (e.g. a small helper) is one way to prevent the two sites diverging; the mechanism is the implementer's choice.

### TN-6: Fetch ordering + write mechanism (report pipeline)
In the report generator, the initial `_ensure_team_row` (`generator.py:1553` → `ensure_team_row_with_provenance(..., season_year=self.season_year_from_api)` at ~1622) runs at Step 2, BEFORE `_resolve_gc_uuid_stage` (`generator.py:1972`) resolves `self.resolved_gc_uuid`. The `season_year`/`public_id` writes at `generator.py:1638-1655` live INSIDE that initial `_ensure_team_row` and are therefore PRE-resolution (fed by public-profile data) — do NOT model the `innings_per_game` write on them. Because `innings_per_game` requires the authenticated `GET /teams/{gc_uuid}` (not on the public profile), it is only available AFTER gc_uuid resolution. The genuine post-resolution write site is the `if self.resolved_gc_uuid:` block inside `_resolve_gc_uuid_stage` where `self.resolved_gc_uuid` is live (~`generator.py:1994-2001`). Fetch `innings_per_game` there whenever `resolved_gc_uuid` is available (regardless of which resolution branch produced it), independent of whether spray-chart loading succeeds. Write it via `ensure_team_row(innings_per_game=...)` / `_backfill_innings_per_game` (TN-4) — the membership-agnostic, NULL-safe single write path built in E-264-01 — NOT the relic tracked-only `UPDATE teams SET gc_uuid ... AND membership_type = 'tracked'` at ~1997, which would couple the new write to a self-heal gate. (Note: the `membership_type == 'member'` branch at ~1988 is DEAD in practice — E-239 removed the member-creation path and all live teams are `tracked`, so there is no live bug either way; routing through `ensure_team_row` is the clean-design choice, not a bug fix. The membership-agnostic path keeps the write correct whether `'member'` stays dead, gets swept, or is ever revived. Do not justify it on member-team behavior.)

### TN-7: Display disclosure copy (baseball-coach, verbatim)
Always show a basis indicator on ERA — BOTH the known and the assumed case — because a coach comparing ERAs across teams (or across two reports) computed on different game lengths needs the signal. Basis is a team-level constant, so label once per team's pitching table (a column header), not per row. Use these strings verbatim:

**Header-level (the report's Pitching table — a single-team table with one ERA `<th>` at `scouting_report.html:673`; this is the preferred/applicable form):**
- Known basis: `ERA (7-inn)` — substitute the actual fetched value, e.g. `ERA (6-inn)`.
- Assumed/fallback basis: `ERA (7-inn)*`
- Footnote, printed once under the table, ONLY when the assumed case applies: `* Game length not available from GameChanger for this team -- ERA assumed on a 7-inning basis.`

**Inline-per-value (for the standalone key-player card ERA at `scouting_report.html:648`, which is a single ERA outside a table):**
- Known basis: `4.50 (7-inn)` (the ERA value followed by the basis)
- Assumed/fallback basis: `4.50 (7-inn)*` — same footnote applies once on the report.

Wording is fixed: "assumed" (not "estimated"/"default"), "-inn" (not "-inning") in the compact forms, the footnote spells "inning" in full, and NO raw field name (`innings_per_game`) is user-facing — the footnote says "game length." If the actual header markup cannot fit even the compact form, SE flags baseball-coach to shrink the wording rather than dropping the label.

### TN-8: Test obligation (MUST-FIX in this epic)
Changing the ERA formula breaks the committed golden and value fixtures; updating them is part of THIS epic, not follow-up (per `.claude/rules/testing.md`, inverse-direction stale tests). Concretely:
- Regenerate the golden via the explicit `scripts/regen_report_golden.py` path (the test never self-writes it; the regenerated golden surfaces in `git diff` and is code-reviewed).
- Affected suites: `tests/test_report_golden.py`, `tests/test_report_e2e.py`, `tests/test_db.py` (plus any ERA fixture assertions elsewhere).
- The golden fixture (`tests/fixtures/seed.sql`) MUST seed BOTH provenance cases so each path is exercised: at least one team with a stored integer (including a **6** to exercise a non-7 basis in the ERA math and the `ERA (6-inn)` label) AND at least one team with NULL (assumed → fallback-7 math AND the assumed-basis disclosure — header asterisk + footnote per TN-7). A fixture that seeds only integers passes the assumed branch vacuously.

### TN-9: Scope decision (b) — ERA-only (rationale)
E-264 fixes ERA only. baseball-coach's reasoning: the must-fix argument for ERA is that GC's app displays ERA for the same pitcher, so a wrong-basis ERA is a visible contradiction of the trusted source (the North Star fidelity argument). K/9 has NO GC-displayed equivalent to contradict, so that argument does not transfer; and coaches specifically benchmark traditional 9-inning K/9 against external recruiting standards ("8+ K/9 is a dominant arm"), so silently rebasing it would mislead. The holistic K-rate stat decision is deferred to the pitcher-outings epic (IDEA-141 ensures that epic's scope picks it up so it is not dropped between epics).

## Open Questions
- None blocking. (SE should confirm during E-264-03 that the compact header form fits the existing `<th>` markup; if not, TN-7 directs SE to flag baseball-coach for shorter copy rather than dropping the label. The same copy-confirmation should also bless the key-player card composition, where the inline form sits next to the existing static label — `4.50 (7-inn) ERA · …` at `scouting_report.html:648-649` — so the doubled/adjacent "ERA" wording reads acceptably.)

## History
- 2026-07-15: Created (DRAFT). Discovery from live api-scout investigation; storage shape from data-engineer; scope + display copy from baseball-coach; computation sites + test obligation from software-engineer.
- 2026-07-15: Set **READY** after six review passes (four expert holistic reviews + code-reviewer spec audit + Codex spec review). All findings accepted and incorporated, 0 dismissed, no design defects. Freshness clock starts 2026-07-15 (re-confirm by 2026-09-13 if not yet dispatched). User authorized straight-to-READY (Codex re-run skipped). Two follow-up ideas filed during formation: IDEA-141 (pitcher-outings epic owns the K-rate basis decision) and IDEA-142 (remove dead `member` membership_type residue).

### Review Scorecard
| Review pass | Findings | Accepted | Dismissed |
|-------------|---------:|---------:|----------:|
| baseball-coach (holistic) | 1 | 1 | 0 |
| data-engineer (holistic) | 3 | 3 | 0 |
| api-scout (holistic) | 3 | 3 | 0 |
| software-engineer (holistic) | 6 | 6 | 0 |
| code-reviewer (spec audit) | 4 | 4 | 0 |
| Codex (spec review) | 4 | 4 | 0 |
| **Total** | **21** | **21** | **0** |

Notes: ~20 distinct findings — code-reviewer MUST-FIX 1 overlapped software-engineer Issue 1 (same TN-6 line-reference defect). The software-engineer count is its 2 BLOCKING issues + 4 incorporated advisory notes (a 5th note was a confirmation, not counted). A post-audit software-engineer self-correction (TN-6 rationale: the "member team" premise was false — no `member` teams exist) refined an already-fixed item and is not counted as a distinct finding. Highest-severity catches: a real crash bug (the `if not None` fallback that never falls back → `None * 3` TypeError on the assumed-basis report), two BLOCKING spec errors, a 403 crash-class, and a completeness miss (a third K/G-mislabel doc).

- 2026-07-16: **Dispatched and all four stories DONE** (serial 01 → 02 → 03 → 04; each passed code-review + PM AC verification before the staging boundary advanced). Shipped: migration `012` (bare-nullable `teams.innings_per_game`, NULL = load-bearing "assumed" provenance); `get_season_pitching` carries the raw basis at the outer wrapper level (no SQL COALESCE); `ensure_team_row` `innings_per_game` param + NULL-safe `_backfill_innings_per_game` (mirrors `season_year`); the report pipeline fetches the basis from the authenticated `GET /teams/{gc_uuid}` at the gc_uuid-resolution seam (non-fatal on 403/absence, never clobbers a stored value); both ERA sites compute `ER × (basis × 3) / ip_outs` via the new shared `era_basis_innings()` helper (`src/api/helpers.py`, explicit `is not None else 7`) — K/9 and WHIP unchanged; a verbatim TN-7 basis label on the Pitching ERA header (`ERA (N-inn)` / `ERA (N-inn)*`) + conditional one-time footnote + inline key-player-card label; golden regenerated to the basis-6 values; the two endpoint-doc K/G "per-9" mislabels + the `innings_per_game` age-speculation corrected. Full worktree suite green (3853 passed / 0 failed at the last story).

### Dispatch & Closure Review Scorecard
| Review pass | Findings | Accepted | Dismissed |
|-------------|---------:|---------:|----------:|
| Per-story CR — E-264-01 | 0 | 0 | 0 |
| Per-story CR — E-264-02 | 1 | 1 | 0 |
| Per-story CR — E-264-03 | 0 | 0 | 0 |
| Per-story CR — E-264-04 | 0 | 0 | 0 |
| Closure CR Integration Review | 0 | 0 | 0 |
| Codex (code review) | 1 | 1 | 0 |
| **Total** | **2** | **2** | **0** |

Notes: E-264-02's single per-story CR finding was a SHOULD-FIX, accepted and fixed in review round 2. Codex's one Priority-1 finding (migration 012 lacked a deploy-time-safety scope assertion) was **satisfied as a review artifact, 0 code changes**: migration 012 is the safest metadata-only shape (bare nullable `ADD COLUMN`, no DEFAULT/NOT NULL/FK/DML), already test-asserted (`notnull==0`, `dflt is None`, existing rows NULL, idempotent); CR produced the explicit migration-scope assertion (zero row writes, metadata-only) in the Step 1c Closure CR Integration Review, alongside the Step 1a invariant audit (the `ensure_team_row` additive-optional signature change per TN-4 holds repo-wide). Step 1b full-suite-green gate and Step 1d closure runtime smoke run post-merge at Step 8.

- 2026-07-16: **COMPLETED.** All four stories DONE, all reviews passed (see scorecards above), full worktree suite green. Status authored in the epic worktree at Step 8 sub-step 3 to ride the closure patch; finalized only after the post-merge full-suite-green gate (a red gate reverts the patch and this flip with it).

### Closure Assessments

**Documentation assessment** (`.claude/rules/documentation.md`): The required-correction check PASSES — the coaching stat guide's K/9 and BB/9 sections (`docs/coaching/understanding-stats.md`, "scaled to a nine-inning game") remain accurate because E-264's deliberate ERA-ONLY scope kept K/9/BB/9 on the 9-inning basis; there is no ERA-formula section to correct. One optional coach-facing enhancement was flagged: the report's Pitching ERA column now carries a visible `ERA (N-inn)` / `ERA (N-inn)*` basis label + assumed footnote, and `docs/coaching/standalone-reports.md:35` (which documents that table) does not yet describe it. Disposition: **docs-writer authored** a light-touch note on `docs/coaching/standalone-reports.md:35` — the ERA column header now names the game length it's computed on (e.g. "ERA (7-inn)"), with the assumed-basis asterisk + footnote explained — plus a staleness header; the K/9/BB/9 sections were left untouched (still correct under the ERA-only scope).

**Context-layer assessment** (`.claude/rules/context-layer-assessment.md`, eight triggers):
1. New convention/pattern/constraint — **YES.** The new `teams.innings_per_game` column carries a load-bearing NULL-as-"assumed"-provenance semantic and a "never add DEFAULT/NOT NULL" invariant that the display-disclosure contract depends on. That invariant currently lives only in the frozen migration-012 comment; it belongs in `.claude/rules/data-model.md` alongside the parallel `teams.season_year` entry (`data-model.md:18`), so a future schema-touching agent is warned before adding a NULL→7 backfill. **Fires → claude-architect authored the data-model.md entry (`data-model.md:19`), rides the closure patch.**
2. Architectural decision with ongoing implications — NO (localized data-model addition; the K-rate future interaction is captured in IDEA-141).
3. Footgun/failure mode/boundary — NO as a standalone (the `is not None` crash guard + NULL-provenance are inline-documented and were caught in spec review, not a new runtime discovery); the no-DEFAULT/NOT-NULL footgun is folded into the trigger-1 data-model.md entry.
4. Agent behavior/routing/coordination — NO.
5. Domain knowledge for future agents — NO (the per-team-not-age-derived ERA/K-G basis finding is captured in `docs/api` via E-264-04 and in the trigger-1 data-model.md entry; an optional baseball-coach memory pointer on the deliberate K/9-not-rebased decision is left to that agent, not required).
6. New CLI command/workflow/procedure — NO (Non-Goals: no new `bb` command, no backfill pass).
7. Net context-layer growth ratchet — NO concern (the epic touched zero `.claude/` files; the trigger-1 line replaces reliance on a frozen migration comment for a durable invariant — net-positive, not bloat).
8. Reusable behavioral lesson — NO (the `is not None` point is generic; no recurrence citation).

Verdict: trigger 1 fired and is **discharged**. claude-architect authored the `data-model.md` `teams.innings_per_game` entry (`data-model.md:19`, parallel to `season_year`), capturing the load-bearing-NULL provenance + the hard "never add DEFAULT/NOT NULL, never blindly backfill NULL→value" invariant + the `era_basis_innings()`/`DEFAULT_ERA_BASIS_INNINGS` pointer. CA resolved both in-domain judgment calls **NO**: `era_basis_innings()` does not warrant a CLAUDE.md canonical-seam note (narrow two-site display helper, below the ensure_team_row/get_connection bar), and no baseball-coach memory pointer is needed. Both this codification and the docs-writer update above are authored in the worktree and ride the closure patch.
