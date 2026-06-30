# E-247: Twin-Method & Duplicated-Block Extractions

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Collapse the copy-pasted "twin-method" and duplicated-block patterns that the project has already solved elsewhere — near-identical loader in-memory/disk paths, the reconciliation detection block reproduced for dry-run and execute, the live public_id→gc_uuid search seam re-implemented in multiple modules, credential/auth core duplications, and parallel SQL/stat/date blocks in the reports layer. Several of these copies have already silently drifted; this epic consolidates each to a single source so a future change cannot diverge between copies. Every change is behavior-preserving (byte-identical output) except one explicitly-flagged operator-awareness item (`APP_URL` default).

## Background & Context
A whole-project code-quality sweep over all of `src/` surfaced 13 maintainability themes. This epic takes the medium-risk middle tier: structural extractions where the duplication spans live code paths, so consolidation requires byte-identical-output verification and (for the credential and auth seams) security-sensitive care. The dominant pattern is "twin-method / copy-pasted block" where the correct fix already exists elsewhere in the codebase (e.g. `plays_loader._load_game`, the canonical helpers) and a few modules are holdouts — and several copies have already silently drifted: the spray disk variants log differently, the reconciliation dry-run and execute paths can diverge, and `get_login` re-implements the authenticated-user lookup.

The full triage report is the evidence base; each story preserves the report's `file:line` locations and drift notes. This epic overlaps E-246 on one file (`src/gamechanger/crawlers/opponents.py` — see Technical Notes "Cross-epic overlap") and is sequenced after E-246 as the second wave.

**Expert consultation.** **api-scout** (gc-uuid-bridge owner) was consulted for the GC search-seam work (E-247-03) given the zero-stats-regression bar (gc_uuid resolution selects which team's data is fetched); its binding constraints are recorded verbatim in E-247-03's "Expert Consultation" section and reflected in that story's ACs (regex anchoring + `game_loader` key-classification preservation, quirk handling stays in `search.py`, opponent UUID-validation and dirty-name short-circuit preserved). For the other stories — E-247-01 loaders, E-247-02 reconciliation, E-247-04 credential core, E-247-05 plays-scope SQL, E-247-06 stat-math, E-247-07 APP_URL/auth middleware — **no api-scout/baseball-coach consultation required: pure internal refactor with no GameChanger API call, response-shape, or stat-derivation change** (api-scout confirmed the stat-math twins are pure refactors of existing derivations, so the baseball-coach no-consult rationale is honest too). **data-engineer** is on the Dispatch Team for the loader/SQL stories (E-247-01, E-247-05). **claude-architect** performs a review-time security pass on E-247-04 and E-247-07 (see Open Questions).

This epic implements no `docs/ROADMAP.md` §5 slice — internal maintainability work, so the Roadmap reference convention does not apply.

## Goals
- Collapse the loader in-memory/disk twin methods to a thin JSON-read+validate wrapper delegating to a shared payload core, fixing the already-drifted spray copies.
- Extract the reconciliation per-game detection block so dry-run and execute paths share one detection function and cannot diverge.
- Extract one `resolve_gc_uuid_by_public_id` helper (the paginate-+-filter-by-public_id loop, next to `search_teams_by_name`) and a single `is_gc_uuid(s)` regex helper in `url_parser.py`, replacing the re-implemented copies (H3 consolidation half) — quirk handling stays in `search.py`.
- Consolidate the GC credential/auth core duplications (env-merge, profile-check, JWT decode, proxy-config), which are the most dangerous to let drift because they touch credential-bearing/never-log paths.
- Consolidate the reports generator's parallel plays-scope SQL, the empty-result literal, and the timestamp helper.
- Consolidate the reports renderer/prediction duplicated stat math and date formatting.
- Consolidate the API middleware/auth-route duplications (missing-table 503 handler, authenticated-user lookup, `APP_URL` helper with a single default).

## Non-Goals
- Dead-code deletions and low-risk consolidations (H3-delete, M2, M1, H1, M7, L1) — E-246.
- The GC API client error-ladder refactor (H5) — E-248, isolated for its high blast radius and test prerequisite.
- Any change to stat definitions, report content, query results, or auth behavior beyond byte-identical refactors and the one flagged `APP_URL` default change.
- Performance/efficiency tuning — the sweep found nothing actionable on hot paths (all N=1/offline); the M5 two-scan efficiency note is low value and only to be addressed as a side effect of the SQL consolidation, never as its own goal.

## Success Criteria
- **Stats integrity (HARD GATE — outranks everything else in this epic):** no story regresses stats collection or accuracy. Each stat-bearing story (E-247-01 loaders, E-247-02 reconciliation, E-247-05 plays-scope SQL, E-247-06 stat math) proves equivalence via a golden-fixture/characterization test under `pytest` (the implementer's in-dispatch gate); any theme that cannot be made provably stat-equivalent is cut or deferred, not shipped. AND `bb report verify-aggregates` MUST be run clean by the operator in the devcontainer **before the closure commit** — a non-clean result **blocks closure**. See Technical Notes "Stats Integrity — HARD GATE" and "Closure Gate (blocking)."
- Each duplicated block named in the stories is expressed exactly once and the former copies delegate to it.
- Reports, reconciliation output, and resolved gc_uuids are byte-identical/equivalent before and after (verified by existing tests or before/after comparison).
- Auth/session behavior is unchanged except the flagged `APP_URL`-default fix; the missing-table 503 and authenticated-user paths behave identically.
- Credential/auth-core consolidations never alter credential-bearing values or logging behavior.
- `python -m pytest tests/` reports 0 failed in the main checkout after all stories land.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-247-01 | Collapse loader in-memory vs disk twin methods | TODO | None | - |
| E-247-02 | Extract reconciliation per-game detection block | TODO | None | - |
| E-247-03 | Extract public_id→gc_uuid search seam + is_gc_uuid helper | TODO | None | - |
| E-247-04 | Consolidate GC credential/auth core duplications | TODO | None | - |
| E-247-05 | Consolidate reports generator plays-scope SQL + literals | TODO | E-247-03 | - |
| E-247-06 | Consolidate reports renderer/prediction stat math & dates | TODO | None | - |
| E-247-07 | Consolidate API middleware/auth-route duplication + APP_URL | TODO | E-247-05 | - |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### Stats Integrity — HARD GATE (non-negotiable, outranks the cleanup)
No change in this epic may regress stats collection or accuracy. This constraint outranks the cleanup itself: if a theme cannot be made provably stat-equivalent, it is **cut or deferred — never shipped on faith.** It binds to the project north-star ("always get closer to byte-identical play ingestion" — a cleanup must never move a stat away from the boxscore) and is enforced at three levels:
1. **Per-story proof (in-worktree):** every stat-bearing story proves output equivalence with a golden-fixture or characterization test that runs under `pytest` — not visual inspection, not "looks/algebraically equivalent" asserted by reading. The test pins the pre-change output and passes against the post-change code.
2. **Full-suite-green closure gate:** `python -m pytest tests/` reports 0 failed in the main checkout at closure.
3. **Blocking pre-closure parity gate (operator):** before the closure commit, the operator runs `bb report verify-aggregates` in the devcontainer; it MUST return clean (no per-cell mismatches). A non-clean result **blocks closure** — the closure commit MUST NOT proceed until parity is clean. The `bb` CLI and `data/` are unavailable in epic worktrees, so this is an operator/closure-sequence gate, not an in-dispatch implementer AC. See "Closure Gate (blocking)" below.

### Closure Gate (blocking)
This epic's closure commit MUST NOT proceed until BOTH hold: (a) the full pytest suite is green in the main checkout (standing gate), and (b) the operator has run `bb report verify-aggregates` in the devcontainer and it returned clean. (b) is the user's explicit, non-negotiable parity gate — a non-clean `verify-aggregates` blocks closure regardless of green tests. Because this epic consolidates stat denominators and loader/recon paths, parity is the cross-check that the in-dispatch golden-fixture proofs did not miss a live-data regression. The operator runs (b) against the merged main checkout (where `data/` and the `bb` CLI exist) before the atomic closure commit; record the clean result in the epic History at closure.

**Stat surface per story:**
- **Stat-bearing (concentrate verification here):**
  - E-247-01 (H2 loaders) — populate the per-game/per-player stat tables; loaded data must be proven equivalent for both in-memory and disk paths.
  - E-247-02 (H4 reconciliation) — corrects pitcher attribution; a detection regression silently corrupts stats. Detection output must be byte-identical in BOTH dry-run and execute paths.
  - E-247-05 (M5 plays-scope SQL) — touches stat denominators (charted-PA, perspective scoping, season scope); consolidated queries must be proven byte-identical to the originals.
  - E-247-06 (M6 stat math) — total-bases and K/9; the "algebraically-equal" TB formulas must be **proven equal across all inputs/call sites, not assumed.**
- **Stat-adjacent (confirm unchanged):** E-247-03 (H3-consolidate) — gc_uuid resolution selects WHICH team's data is fetched; a wrong resolution corrupts collection. Resolved gc_uuids must be proven identical (AC-4 of that story).
- **Pure-mechanical / non-stat gate (fast-track for stats; own gate applies):** E-247-04 (M4 credential core — security/never-log gate instead), E-247-07 (M3 auth middleware + APP_URL — auth-behavior/operator-awareness gate instead). Neither touches stat values; triage may fast-track them on stats grounds while still honoring their security gates.

### Evidence base and clean re-read
The triage report is the source of every `file:line` location and drift note. Re-confirm each location via a fresh grep before acting — line numbers may have shifted.

### Byte-identical-output constraint
Every extraction in this epic must be behavior-preserving. For each consolidation, the implementing agent must verify output is byte-identical (or provably equivalent): reports via existing report/render tests or before/after comparison; reconciliation via the existing recon tests (the report notes recon output is test-covered); resolved gc_uuids via the existing resolution tests. The one sanctioned behavior change is the `APP_URL` default in E-247-07 (see below).

### Security-sensitive seams
E-247-04 (credential/auth core) and E-247-07 (API middleware/auth) touch credential-bearing and authentication paths. Behavior must stay identical; credential values must never be logged or altered; the authenticated-user lookup and admin/session semantics must be preserved exactly. Per the user's decision (see Open Questions), **claude-architect performs a review-time security pass** on E-247-07 (M3 auth/middleware) and E-247-04 (M4 credential core) — reviewing the implementer's diff for security regressions. These remain `src/` implementation stories routed to software-engineer (not context-layer files); the CA pass is an advisory security review at review time, not a routing change or a refinement blocker.

### Reuse the established pattern
Where the project already solved a duplication (e.g. `plays_loader._load_game` / `GameLoader._load_boxscore_data` for the loader twin methods, `search_teams_by_name` for team search), the consolidation should follow that established shape rather than invent a new one. The sweep's suggested helper names are illustrative; the implementing agent owns the final shape.

### Story sequencing (shared-file dependencies)
- `src/reports/generator.py` is touched by E-247-03 (gc_uuid seam + `:1614` is_uuid consumer), E-247-05 (plays-scope SQL), AND E-247-07 (third APP_URL site at `:226`, added per Codex spec review). The dependency chain E-247-03 → E-247-05 → E-247-07 serializes all three, so the shared-file contention is resolved by ordering.
- `src/api/routes/reports_admin.py` is touched by E-247-03 (`:694` is_uuid consumer — defensive, expected unchanged), E-247-05 (`_utcnow_iso` at `:542`), and E-247-07 (`:543` APP_URL + 503 handler). Same E-247-03 → E-247-05 → E-247-07 chain serializes it.
- E-247-05 (M5) is blocked by E-247-03 (H3-consolidate) — shared `src/reports/generator.py`.
- E-247-07 (M3) is blocked by E-247-05 (M5) — shared `src/api/routes/reports_admin.py` AND `src/reports/generator.py`.
- E-247-03 additionally touches `src/gamechanger/url_parser.py`, `opponents.py`, `loaders/game_loader.py`, `search.py` — none shared with another E-247 story (opponents.py is shared with E-246-02 cross-epic; E-246 dispatches first — see "Cross-epic overlap").
- E-247-01, -02, -04, -06 are file-disjoint from the rest and from each other.

This epic overlaps E-246 on exactly one file: `src/gamechanger/crawlers/opponents.py` (E-246-02 removes dead `import json`/`data_root` plumbing and corrects a stale docstring; E-247-03 consolidates `resolve_own_team_gc_uuid` in the same file — different regions). Because epics dispatch serially and one closes/merges before the next begins, this is handled by rebasing: if both epics are authorized, **dispatch E-246 before E-247** so the dead-code cleanup lands first and E-247-03 rebases onto it. No other files are shared between the two epics. E-248 shares no files with either.

## Open Questions
All pre-dispatch sign-offs are resolved (user decisions, 2026-06-29). None remain open.
- **[RESOLVED] APP_URL default (E-247-07) — `localhost:8001`.** The user chose `localhost:8001` as the single unified default, matching the documented local-dev stack URL in CLAUDE.md (`docker compose up` → http://localhost:8001). Production sets `APP_URL` explicitly, so only dev report-links are affected when the env var is unset. This is now a decided value baked into E-247-07, not an open input.
- **[RESOLVED] claude-architect — REVIEW-TIME security advisory.** The user directed that claude-architect give a review-time security pass on the security-sensitive seams: E-247-07 (M3 auth/middleware) and E-247-04 (M4 credential core). This is an advisory review-time consultation, not a refinement blocker and not a routing change — both stories still route to software-engineer; CA reviews their diffs for security.
- **[RESOLVED] Parity gate — BLOCKING PRE-CLOSURE.** The user chose to make `bb report verify-aggregates` a blocking pre-closure operator gate (see Technical Notes "Closure Gate (blocking)").

## History
- 2026-06-29: Created (READY). Scoped from the whole-project code-quality sweep as the medium-risk extraction wave; H3-delete/M2/M1/H1/M7/L1 → E-246, H5 → E-248.
- 2026-06-29: User sign-offs resolved — APP_URL default = `localhost:8001`; parity gate set to blocking pre-closure; claude-architect assigned a review-time security pass on E-247-04 and E-247-07. Updated ahead of Codex spec review.
