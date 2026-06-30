# E-247: Twin-Method & Duplicated-Block Extractions

## Status
`COMPLETED`
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
| E-247-01 | Collapse loader in-memory vs disk twin methods | DONE | None | - |
| E-247-02 | Extract reconciliation per-game detection block | DONE | None | - |
| E-247-03 | Extract public_id→gc_uuid search seam + is_gc_uuid helper | DONE | None | - |
| E-247-04 | Consolidate GC credential/auth core duplications | DONE | None | - |
| E-247-05 | Consolidate reports generator plays-scope SQL + literals | DONE | E-247-03 | - |
| E-247-06 | Consolidate reports renderer/prediction stat math & dates | DONE | None | - |
| E-247-07 | Consolidate API middleware/auth-route duplication + APP_URL | DONE | E-247-05 | - |

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
- **[RESOLVED — REVISED AT CLOSURE 2026-06-30] APP_URL default (E-247-07) — `baseball.localhost:8001`.** The single unified default is `http://baseball.localhost:8001`. Rationale: the dev browses the app at `baseball.localhost` (the WebAuthn/passkey origin and the Traefik dev host), so unifying the APP_URL default to `baseball.localhost:8001` keeps auth-origin coherence — magic links AND passkeys share one dev host — and keeps the `WEBAUTHN_ORIGIN must match APP_URL` invariant intact (all three = `baseball.localhost`). This SUPERSEDES the earlier 2026-06-29 decision of `localhost:8001` (whose rationale was the thin "matches the CLAUDE.md docker-compose `localhost:8001` line"); that choice was found at closure to split auth-origin coherence (magic links on `localhost`, passkeys on `baseball.localhost`) and to make `.env.example`'s documented default stale — both dissolved by reverting to `baseball.localhost:8001`. Production sets `APP_URL` explicitly, so only the dev unset-default is affected. In practice the unification now moves the generator.py + reports_admin.py report-link defaults from `localhost:8001` → `baseball.localhost:8001` (auth.py's magic-link default was already `baseball.localhost:8001` and is unchanged).
- **[RESOLVED] claude-architect — REVIEW-TIME security advisory.** The user directed that claude-architect give a review-time security pass on the security-sensitive seams: E-247-07 (M3 auth/middleware) and E-247-04 (M4 credential core). This is an advisory review-time consultation, not a refinement blocker and not a routing change — both stories still route to software-engineer; CA reviews their diffs for security.
- **[RESOLVED] Parity gate — BLOCKING PRE-CLOSURE.** The user chose to make `bb report verify-aggregates` a blocking pre-closure operator gate (see Technical Notes "Closure Gate (blocking)").

## History
- 2026-06-29: Created (READY). Scoped from the whole-project code-quality sweep as the medium-risk extraction wave; H3-delete/M2/M1/H1/M7/L1 → E-246, H5 → E-248.
- 2026-06-29: User sign-offs resolved — APP_URL default = `localhost:8001`; parity gate set to blocking pre-closure; claude-architect assigned a review-time security pass on E-247-04 and E-247-07. Updated ahead of Codex spec review.
- 2026-06-30: All 7 stories DONE. Dispatched serially in the epic worktree following the `E-247-03 → E-247-05 → E-247-07` shared-file chain (generator.py + reports_admin.py); E-247-01/-02/-04/-06 were file-disjoint. The ONE sanctioned behavior change shipped: the APP_URL dev-default was unified via the new `src/api/helpers.py::get_app_url` helper (E-247-07). Through dispatch and Phase 4 the decided value was `localhost:8001`; **this was reversed to `baseball.localhost:8001` at closure at the user's direction — see the 2026-06-30 reversal entry below for the final value and rationale.** Every other change is behavior-preserving (byte-identical), proven per stat-bearing story (E-247-01 loaders, E-247-02 reconciliation, E-247-05 plays-scope SQL, E-247-06 stat math) by a golden-fixture/characterization pytest, and per stat-adjacent story (E-247-03 resolved-gc_uuid + game_loader key-split). The two security-sensitive seams (E-247-04 credential core, E-247-07 auth/middleware) each cleared a claude-architect review-time security pass returning SECURITY-CLEAN.
- 2026-06-30: Phase 4b Codex review caught a real HARD-GATE regression that per-story review missed. Codex returned 3 findings: **F1 (VALID, P1 stat path)** — the E-247-01 loader consolidation dropped the in-memory path's empty-boxscores early-return, so `_load_team_core` ran `canonical_recompute` unconditionally and would DELETE+rewrite `boxscore_only` season aggregates on a populated-DB boxscoreless refresh (a stat regression the fresh-DB golden test could not see); **F2 (VALID, low)** — the disk path stopped emitting `LoadResult(errors=1)` on a present-but-malformed roster.json (behavior-preservation deviation under the epic mandate, not an AC); **F3 (INVALID)** — the "all three sites" APP_URL test drove only 2 sites, but the code satisfied E-247-07 AC-4 by composition (a test-name over-promise, not a code gap). F1+F2 were remediated on a reopened E-247-01: the per-path empty-boxscore-source guard was restored (in-memory skips on an empty boxscores dict; disk skips only on an absent directory — a present-but-empty dir still runs the tail, matching pre-refactor), pinned by a populated-DB characterization test with proven teeth (a stale `boxscore_only` aggregate ab=99 disagreeing with its per-game sum ab=4 must stay untouched; DE proved the unconditional tail makes it FAIL ab=99→4); and `errors=1` was restored roster-only with a missing≠malformed boundary guard. F3 was a non-reopening test-honesty correction. PM re-verified E-247-01 AC-4 PASS / HARD GATE met after remediation. Full suite: 3499 passed / 0 failed.
- 2026-06-30: **APP_URL default reversed at closure, at the user's direction.** During the PM closure documentation assessment, PM surfaced that the 2026-06-29 `localhost:8001` choice left `.env.example`'s documented APP_URL default stale AND split auth-origin coherence (magic links would resolve on `localhost` while passkeys/WebAuthn stay on `baseball.localhost`, contradicting `.env.example`'s `WEBAUTHN_ORIGIN must match APP_URL` invariant). The user reconsidered and flipped the unified default to **`http://baseball.localhost:8001`** — restoring auth-origin coherence (all three of APP_URL / WEBAUTHN_ORIGIN / WEBAUTHN_RP_ID align on `baseball.localhost`) and dissolving the documentation gate (`.env.example` already documents `baseball.localhost:8001`, so it is no longer stale; the WebAuthn-match divergence is resolved). E-247-07 was REOPENED for the code+test change (flip `get_app_url()`'s default + update the APP_URL-default test assertions); CA to re-confirm security (trivial — returns the magic-link default to its pre-epic value), PM to re-verify AC-4 against the revised decided value. Net effect of the unification now: generator.py + reports_admin.py report-link dev-defaults move `localhost:8001` → `baseball.localhost:8001`; auth.py's magic-link default was already `baseball.localhost:8001` (unchanged).
- 2026-06-30: **COMPLETED.** All 7 stories collapsed their twin-method / duplicated-block patterns to a single source each (loaders, reconciliation detection, gc_uuid search seam + is_gc_uuid, credential/auth core, plays-scope SQL + literals, renderer/prediction stat math + dates, API middleware/auth + APP_URL), every consolidation behavior-preserving except the one sanctioned change. **Net behavior:** after the closure-time APP_URL reversal to `baseball.localhost:8001`, the magic-link default returns to its pre-epic value (ZERO net magic-link change), leaving the report-link dev-default move (`localhost:8001` → `baseball.localhost:8001` at generator.py + reports_admin.py) as the SOLE sanctioned behavior change; all other output is byte-identical. The Phase 4b Codex review caught one real HARD-GATE regression (F1: E-247-01 dropped the in-memory empty-boxscores early-return → unconditional `canonical_recompute` would rewrite populated-DB aggregates), remediated on a reopened E-247-01 with a populated-DB characterization test that has proven teeth; F2 (lost roster `errors=1`) restored; F3 (test-name over-promise) corrected. **Closure gates:** documentation = No impact (after the reversal); context-layer = triggers 1+3 codified by claude-architect (CLAUDE.md canonical-seam bullets for is_gc_uuid / get_app_url / resolve_gc_uuid_by_public_id; data-model.md twin-method-collapse + populated-fixture footgun bullets).
- 2026-06-30: **Blocking parity gate: `bb report verify-aggregates` run clean by the operator in the devcontainer at closure (2026-06-30)** against the merged main checkout (no per-cell mismatches), authorizing the closure commit. Per the epic's HARD GATE this is the live-data cross-check that the in-dispatch golden-fixture proofs did not miss a stat regression (the epic consolidated stat denominators and the loader/recon paths). Authored under the skill's author-then-validate model: the single atomic closure commit is gated on (a) the full-suite-green gate in main AND (b) this clean parity run — a non-clean result aborts the commit and reverts the patch, so this line is never committed unless both gates actually pass.

### Review Scorecard
| Story / Phase | Reviewer(s) | Rounds | Outcome | Findings (accepted / dismissed) |
|---|---|---|---|---|
| E-247-01 | code-reviewer | 2 (initial + Phase 4b reopen) | APPROVED | initial: 1 SHOULD FIX accepted (no-op test renamed), 1 dismissed; Phase 4b: F1+F2 accepted & fixed |
| E-247-02 | code-reviewer | 1 | APPROVED | 0 MUST FIX; 1 SHOULD FIX dismissed (absolute-golden redundant — pre-existing recon suite pins it) |
| E-247-03 | code-reviewer (+ api-scout consult at planning) | 2 | APPROVED | round-1 test-scope MUST FIX accepted & fixed (4 omitted importers run green) |
| E-247-04 | code-reviewer + claude-architect (security) | 1 | APPROVED + SECURITY-CLEAN | 0 MUST FIX; 2 SHOULD FIX dismissed (test-enum, dict(os.environ) benign) |
| E-247-05 | code-reviewer | 1 | APPROVED | 0 MUST FIX; 1 SHOULD FIX dismissed (`_utcnow_iso` underscore cross-module import — simple-first) |
| E-247-06 | code-reviewer | 1 | APPROVED | 0 MUST FIX; 1 SHOULD FIX dismissed (full-render golden redundant); 2 PM judgment items confirmed (scope ~5→3, error-path unreachable) |
| E-247-07 | code-reviewer + claude-architect (security) | 1 (+ comment-only re-confirm) | APPROVED + SECURITY-CLEAN | 0 MUST FIX; 1 SHOULD FIX (orphan-session) → PM ruled AC-2 PASS (fail-safe drift-correction) |
| Phase 4a — CR integration review (full epic diff) | code-reviewer | 1 | CLEAN | — |
| Phase 4b — Codex review (full epic diff) | Codex (PM AC-triage + CR validity) | 1 | 3 findings → 2 accepted (F1, F2), 1 dismissed-invalid (F3, cosmetic test-honesty touch made) | F1+F2 fixed on reopened E-247-01; F3 test-name corrected |
| E-247-07 APP_URL-flip re-confirm (closure) | code-reviewer + claude-architect (security) | 1 | APPROVED + SECURITY-CLEAN | value-only flip to `baseball.localhost:8001` (user closure decision); CR: single-helper invariant holds, no stale localhost:8001 pin; CA: magic-link byte-identical to pre-epic, WebAuthn coherence restored; PM: AC-4 re-verified PASS |

(Planning-phase: Codex spec review in Phase 3 surfaced the generator.py third APP_URL site, folded into E-247-07 AC-4 before dispatch.)

### Documentation Assessment (`.claude/rules/documentation.md`)
Per-trigger: (1) new feature/endpoint — **no**. (2) architecture/deployment config change — **no**. (3) new/modified agent — **no**. (4) DB schema change — **no** (no migrations). (5) epic changes how the system works / how users interact — **no (after the 2026-06-30 APP_URL reversal)**.

**No documentation impact.** This assessment initially flagged trigger 5 because the (then-decided) `localhost:8001` APP_URL default left `.env.example` stale and created a `WEBAUTHN_ORIGIN must match APP_URL` divergence. That finding is what prompted the user's closure-time reversal of the APP_URL default to `baseball.localhost:8001` (see History). With the default restored to `baseball.localhost:8001`: `.env.example:162,166,167` already documents exactly that value (no longer stale), and APP_URL / WEBAUTHN_ORIGIN / WEBAUTHN_RP_ID all align on `baseball.localhost` (the "must match" invariant holds). Trigger 5 therefore **no longer fires** and **no docs-writer dispatch is needed**. (The `docs/` references to `baseball.localhost` — agent-browsability-workflow.md, app-troubleshooting.md, docker-compose — are the Traefik routing host on port 8000, not the APP_URL default; they were UNAFFECTED throughout and remain correct.)

### Context-Layer Assessment (`.claude/rules/context-layer-assessment.md`)
Per-trigger verdicts:
1. **New convention/pattern/constraint — YES.** The epic created new canonical single-source seams that new code MUST route through (to prevent exactly the drift this epic fixed from recurring): `is_gc_uuid` (`src/gamechanger/url_parser.py`, the single canonical UUID predicate that replaced 4 drifted copies), `get_app_url` (`src/api/helpers.py`, the single APP_URL/link-base source), and `resolve_gc_uuid_by_public_id` (`src/gamechanger/search.py`, the canonical public_id→gc_uuid pagination loop). These are in the same spirit as CLAUDE.md's existing canonical-entry-point list. claude-architect should evaluate adding CLAUDE.md bullets. (The module-private helpers `_plays_scope`, `_total_bases`, `_decode_jwt_payload`, `_missing_table_503`, `_find_k9_alternative`, `_build_merged_lines`/`_reconstruct_env_dict` are localized internal dedup — likely not CLAUDE.md-worthy; CA decides.)
2. **Architectural decision with ongoing implications — no.** Consolidation onto existing patterns; no new technology/structural choice.
3. **Footgun/failure mode/boundary — YES.** Two related, generalizable footguns from the E-247-01 regression: (a) collapsing parallel twin methods (in-memory/disk) into a shared core can silently drop a path's distinct guard/early-return — here the in-memory empty-boxscores early-return — turning `canonical_recompute` into a stat-rewriting DELETE+rebuild on populated DBs; (b) a characterization test for a DELETE+rebuild stat path has NO teeth on a fresh DB — it must seed a POPULATED/stale-disagreeing state (aggregate disagreeing with the per-game sum) to detect an unwanted recompute. Worth codifying (candidate homes: `.claude/rules/data-model.md` Season-Aggregate Parity footgun area, or CLAUDE.md). claude-architect to place.
4. **Agent behavior/routing/coordination — no.**
5. **Domain knowledge for future agents — no.** Semantics preserved; no new baseball/API/data-model knowledge surfaced.
6. **New CLI command/workflow/procedure — no.**

**Disposition**: triggers 1 and 3 fired → **CODIFIED by claude-architect** (2026-06-30, in the epic worktree so it rides the closure patch):
- Trigger 1 — three new CLAUDE.md Architecture canonical-entry-point bullets: `is_gc_uuid` (`src/gamechanger/url_parser.py`), `get_app_url` (`src/api/helpers.py`), `resolve_gc_uuid_by_public_id` (`src/gamechanger/search.py`), in the existing canonical-entry-point style. The module-private dedup helpers (`_plays_scope`, `_total_bases`, `_decode_jwt_payload`, `_missing_table_503`, `_find_k9_alternative`, `_build_merged_lines`/`_reconstruct_env_dict`) were judged not CLAUDE.md-worthy (localized internal dedup).
- Trigger 3 — two bullets in `.claude/rules/data-model.md` (Season-Aggregate Parity): the twin-method-collapse guard-drop footgun (the exact F1 near-miss) and the corollary that an idempotent-recompute characterization test needs a POPULATED, stale-disagreeing fixture rather than a fresh DB.
- (Related, not a context-layer trigger) CLAUDE.md dev-URL standardized to `baseball.localhost:8001` (canonical browse/dev URL + the get_app_url seam bullet), with curl/health staying on `localhost:8001`, keeping the doc coherent with the reverted APP_URL default.
Both closure gates are therefore satisfied: documentation = No impact (after the APP_URL reversal); context-layer = codified. No further context-layer dispatch is owed.
