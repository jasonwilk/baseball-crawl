# E-262: Post-Program Housekeeping — Audit Residuals, Fold-In Ideas, and Live Bugs

## Status
`READY` (set 2026-07-12)
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- READY set 2026-07-12 after internal review (CR + holistic SE/CA/docs-writer/api-scout) and Codex spec review (iter 1) incorporated, quality checklist passed, no open questions. 60-day READY-freshness clock starts 2026-07-12. -->

## Overview
A single low-risk housekeeping epic that clears the enumerated tail left by the 2026-07 platform program: 7 in-scope audit residuals from the endgame sweep (one of the original 8 was dropped in review as mischaracterized), 10 mechanical fold-in ideas (2 of the 12 triaged were dropped as already-resolved), and 4 code-verified live bugs. Every item is a mechanical fix to an existing surface — no new features, no new process machinery, no scope growth.

## Background & Context
The 2026-07 platform program (E-250..E-260) closed at commit 519e0cd. The endgame sweep (`.project/research/2026-07-12-program-endgame-sweep.md`) enumerated everything still open: §1 listed 12 unresolved platform-audit residuals (operator-ratified disposition: #1–#9 → one small housekeeping epic; #10–#11 → idea captures, now filed as IDEA-129/130; #12 → an operator decision, not a story). A post-construction ideas-ledger triage additionally surfaced 12 mechanical fold-in ideas and 4 re-verified live bugs suitable for the same epic (of the 12 fold-ins, 10 were folded and 2 dropped in review as already-resolved; of the 8 audit residuals brought here, 1 was dropped as mischaracterized — see Goals/History). This epic is that housekeeping epic.

**Expert consultation.** No pre-story consultation required — every item was pre-diagnosed with a verified code/doc anchor during the endgame sweep and ledger triage (sources cited per story). Domain experts (SE, CA, docs-writer, api-scout, DE) are available via the main session during the review phases if any item proves larger than a mechanical fix.

**Meta-layer freeze (E-260).** The context layer is FROZEN except defect-cited changes. Every context-layer edit in this epic (CLAUDE.md, `.claude/rules/`, `.claude/skills/`) cites a concrete falsehood, staleness, or a live-observed gate failure — the citation is recorded per story so the freeze discipline is visible. This epic adds NO new process machinery; it only corrects things that are already wrong or stale. (The one context-layer item that turned out to be already-fixed enrichment rather than a live defect — IDEA-092 — was DROPPED during review precisely to hold this line.)

## Goals
- Clear the 7 in-scope platform-audit residuals (#1–#4, #7–#9) with mechanical fixes. (Audit #6 was dropped in review — mischaracterized; see History.)
- Fold in the 10 mechanical ideas (IDEA-010, 022, 105, 107, 111, 113, 114, 117, 118, 128) as targeted corrections to their named anchors. (IDEA-078 and IDEA-092 were dropped during planning review — both already resolved by prior epics; see History.)
- Fix the 4 code-verified live bugs (IDEA-122, 123, 126, 127).
- Keep every change single-agent-clean (each story lands with exactly one agent type) and free of scope growth.

## Non-Goals
- **No new process machinery** — the meta-layer freeze holds; only defect-cited corrections.
- **No forward features** — the deferred idea directions (IDEA-129 write-only raw archive, IDEA-130 refresh-token persistence) are captures only, not built here.
- **Not the `FEATURE_PREDICTED_STARTER` decision** (audit residual #12) — that is an operator decision to record, not an implementable story.
- **Not the excluded/related ideas** — IDEA-109 (smoke_test retarget), IDEA-112 (PII suppressor narrowing) are siblings out of scope; audit #5 (SE-memory falsehood) was already fixed directly this session.
- **Not E-261's territory** — E-261 (Cross-Perspective Game-Dedup Fidelity, READY, parked) does NOT edit `.claude/rules/perspective-provenance.md`; this epic's story 05 makes the IDEA-128 edits to that rule with no expected overlap.
- **No schema migrations** — the DE story (04) is a code rename/fold only; it does not add or alter any `migrations/*.sql`.
- **Not the coaching-docs rewrite** — IDEA-078's premise was already delivered by E-239 (the coaching docs are reports-first; `scouting-reports.md` no longer exists). Story 08 was ABANDONED and IDEA-078 DISCARDED during review; no docs/coaching work is in scope.
- **Not a data-engineer.md entity-table rewrite** — IDEA-092's cited hallucination anchors were already stripped by E-250-04; the residual "fuller refresh" is freeze-barred enrichment. Dropped from story 05; IDEA-092 DISCARDED.

## Success Criteria
- All 8 active stories (01–07, 09; 08 ABANDONED) DONE and code-reviewed; full test suite green at closure.
- Each folded idea (010, 022, 105, 107, 111, 113, 114, 117, 118, 122, 123, 126, 127, 128) flipped to PROMOTED → E-262 in both its idea file and the README index row; the two dropped ideas (078, 092) flipped to DISCARDED.
- Each context-layer story records its defect citation in the story file.
- No net-new context-layer growth beyond what the corrections require (context ratchet holds, or any growth is operator-signed at closure).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-262-01 | CLI behavioral audit fixes (dedup flag, reload exit code, bb status db-path) | TODO | None | software-engineer |
| E-262-02 | Cosmetic hygiene sweep (loader docstrings, test pragma, empty package, compose comment) | TODO | None | software-engineer |
| E-262-03 | Live source bugs (league-level range form, name-only badge sequencing) | TODO | None | software-engineer |
| E-262-04 | Rename/fold season_aggregates.py post-cutover | TODO | None | data-engineer |
| E-262-05 | Context-layer truth & staleness corrections | TODO | None | claude-architect |
| E-262-06 | Step 1d preflight & gate-ordering corrections (creds-profile + generate/reconcile order) | TODO | None | claude-architect |
| E-262-07 | Admin docs hygiene (port map, schema changelog, creds-recovery recipe, Step 1d doc sync) | TODO | E-262-06 (AC-4 only) | docs-writer |
| E-262-08 | Coaching docs reports-first rewrite | ABANDONED | None | — (dropped: premise resolved by E-239) |
| E-262-09 | docs/api cleanup (path-variable rename, scouting-flow stat audit, age_group note) | TODO | None | api-scout |

## Dispatch Team
- software-engineer
- data-engineer
- claude-architect
- docs-writer
- api-scout

## Technical Notes

### Provenance and defect citations (per item)
Every item traces to a hand-verified source. Anchors and citations live in each story's Context/Notes. Canonical sources: the endgame sweep §1 residual table (`.project/research/2026-07-12-program-endgame-sweep.md`) and the individual idea files under `.project/ideas/`.

### Meta-layer freeze compliance
Context-layer stories (05, 06) and the docs/api story (09) qualify as defect-cited under the E-260 freeze because each names a concrete falsehood, stale figure, or live-observed gate failure. No story introduces new rules, skills, hooks, or process gates — corrections only. This is recorded per story.

### Story independence / file isolation
Stories were partitioned so no two stories touch the same file. Test-file targets are enumerated concretely (verified disjoint per Codex P2) — the enumerated set is the verifiable floor; implementers still grep for additional importers per `.claude/rules/testing.md` (false-negatives are the risk):
- Story 01: `src/cli/data.py`, `src/cli/status.py`; tests `tests/test_cli_data.py`, `tests/test_cli_status.py`.
- Story 02: five loader docstrings (`src/gamechanger/loaders/scouting_loader.py`, `plays_loader.py`, `plays_reload.py`, `game_loader.py`, `scouting_spray_loader.py`) + two crawler docstrings (`src/gamechanger/crawlers/scouting.py`, `scouting_spray.py`), `tests/test_crawlers/` (delete), `docker-compose.yml`. (`tests/test_no_inline_schemas.py` removed — audit #6 dropped in review. SE verified the 2 crawler files don't collide with stories 03/04.)
- Story 03: `src/reports/starter_prediction.py`, `src/reports/generator.py`, `src/db/teams.py`; tests `tests/test_league_detection.py`, `tests/test_starter_prediction.py`, `tests/test_report_generator.py`, `tests/test_ensure_team_row.py`, `tests/test_admin_reports.py`. (`src/cli/creds.py` removed — IDEA-122 re-scoped to story 06; no story now touches creds.py.)
- Story 04: `src/db/season_aggregates.py`, `src/api/db.py`; tests `tests/test_season_projection.py`, `tests/test_season_query_cutover.py`, `tests/test_gs_mixed_appearance_order.py`, `tests/fixtures/parity_consistent.sql`. (Importer surface verified by SE + Codex.)
- Story 05: `CLAUDE.md`, `.claude/skills/multi-agent-patterns/SKILL.md`, `.claude/skills/context-fundamentals/SKILL.md`, `.claude/rules/perspective-provenance.md`. (data-engineer.md dropped — IDEA-092 removed in review.)
- Story 06: `.claude/skills/implement/SKILL.md` (both the IDEA-122 creds-profile preflight edit and the IDEA-123 ordering edit are in this one Step 1d file).
- Story 07: `docs/admin/getting-started.md`, `docs/admin/architecture.md`, `docs/admin/operations.md`, `docs/admin/production-deployment.md` (the last is the AC-4 Step 1d sync, `Blocked by: E-262-06`).
- Story 08: ABANDONED (no files — dropped in review).
- Story 09: `docs/api/endpoints/get-game-stream-processing-*` (rename + link sweep), `docs/api/flows/opponent-scouting.md`, `docs/api/endpoints/get-public-teams-public_id.md`, `docs/api/README.md`, + inbound `see_also`/prose refs in 6 sibling endpoint docs (see story 09 for the enumerated blast radius).

The three test sets (story 01 cli-tests, story 03 report/starter/team tests, story 04 season tests) are disjoint — the file-isolation claim holds. IDEA-126 spans two agents by design: the detection fix is SE (story 03, `starter_prediction.py`) and the companion `age_group` field-doc note is api-scout (story 09, `docs/api/`). No shared file, so no dependency ordering is needed. The one cross-story dependency is story 07 AC-4 ← story 06 (doc mirrors the settled skill text); satisfied automatically by serial dispatch.

### Idea-promotion bookkeeping
On epic finalization (READY), each folded idea is flipped CANDIDATE → PROMOTED (→ E-262-SS) in both the idea file Status section and the `.project/ideas/README.md` index row, per the standard promotion convention.

## Open Questions
_Both open questions are now RESOLVED — no open questions remain (pre-dispatch blocker cleared)._
- **IDEA-123 fix mechanism — RESOLVED (operator decision, 2026-07-12).** The grounded-frequency read is DISSOLVED. Root fix = fixture stability: the `.smoke-fixture` generate target MUST be a terminal GC team page (a completed season that gains no further games) with high play-by-play coverage; keep the existing generate → reconcile order (a static corpus makes the post-generate reading measure only the epic's own derivation effect, and the existing ratchet already encodes the operator's directional principle); one operator-owned bootstrap re-snapshot when the fixture is pinned. Reorder-only would just move the false-fail to the next closure; re-snapshot-every-closure is a recurring operator burden — the terminal fixture removes the drift at the root, so no measurement is needed. Operator's fixture pick + rationale are in story 06 Notes (the GC identifier stays in the gitignored `.smoke-fixture` file, never in tracked text). See story 06 AC-2/3/4.
- **IDEA-122 exit-code contract — RESOLVED (SE+CA consult, 2026-07-12).** The original "SE root fix = make `bb creds check` exit non-zero" direction was settled the OTHER way after both SE and CA verified the code: the single-profile and all-dead-multi paths already exit non-zero; the only false-green is the MIXED multi-profile case (valid mobile masks dead web), and the "any valid = usable" contract must hold — so there is NO correct `creds.py` change. The fix is skill-side: the Step 1d preflight calls `bb creds check --profile web` (the profile the smoke's `generate` uses). IDEA-122 moved from story 03 to story 06 (AC-1). This is a ready-now one-token fix with no remaining open question.

## History
- 2026-07-12: **READY.** Refinement complete — internal review (CR spec audit + holistic SE/CA/docs-writer/api-scout) and Codex spec review (iter 1) both incorporated; quality checklist passed; no open questions remain; docs-writer confirmed the story-07 landing. 60-day READY-freshness clock starts today.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 — Holistic team (SE/CA/DW/api-scout) | 19 | 19 | 0 |
| Codex iteration 1 | 2 | 2 | 0 |
| **Total** | **25** | **25** | **0** |

Holistic breakdown: api-scout 2, docs-writer 4, claude-architect 5, software-engineer 8. Every finding was verified correct against live code — zero dismissed. Several counted "findings" were correctness-confirmations that validated a story/item as-is (docs-writer's IDEA-105, SE's IDEA-126 + story-04 importer surface); all are recorded as accepted. Convergent findings across passes (IDEA-092 flagged by both CR-1 and CA-F1; IDEA-118/114 anchors by both CR and CA) are counted per-pass. Net scope outcome: several folded ideas/audit residuals turned out already-fixed or mis-premised and were dropped (IDEA-078, IDEA-092, audit #6) — the correct housekeeping outcome.

- 2026-07-12: Created (DRAFT). Scope ratified by the operator at the 2026-07 program endgame sweep: 8 audit residuals + 12 fold-in ideas + 4 live bugs.
- 2026-07-12: **Codex spec-review incorporation (iter 1/2, team-lead-gated).** Two findings, both ACCEPT. **P1 (propagation):** story 06's settled Step 1d fix is mirrored in `docs/admin/production-deployment.md:503` (the skill defers to it as the authoritative operator-facing procedure), so the sync was added as story 07 AC-4 (`docs/admin/production-deployment.md` in Files) with `Blocked by: E-262-06` — landed in story 07 (docs-writer) not story 06 (CA) to keep one-agent-per-story; landing confirmed with docs-writer. **P2 (file isolation):** the open-ended "Test files under tests/" / "Any importer modules" targets in stories 01/03/04 were replaced with the concrete, disjoint test-file lists (verified against the repo + SE's story-04 surface) in each story's Files and the epic isolation table, with a Test Scope Discovery pointer. Rubric otherwise passed. First cross-story dependency introduced (07 AC-4 ← 06), satisfied by serial dispatch.
- 2026-07-12: **IDEA-123 mechanism SETTLED by operator decision** — the grounded-frequency read is dissolved. Root fix is a terminal static `.smoke-fixture` corpus (completed-season GC team page, high play-by-play coverage, SAME season year to avoid a second `seasons` row); keep generate → reconcile order; one operator-owned bootstrap re-snapshot. Story 06 AC-2/3/4 rewritten to the settled design + a bootstrap plays-coverage check; both epic Open Questions (123 mechanism, 122 landing) now CLOSED, clearing the pre-dispatch blocker. Operator's fixture identifier kept out of tracked text (gitignored `.smoke-fixture`).
- 2026-07-12: Second-round incorporation (CR spec audit + software-engineer holistic review, gated by team-lead). **Audit #6 DROPPED** from story 02 — SE verified the flagged "whole-file pragma" in `test_no_inline_schemas.py` is a NECESSARY `_SELF_EXEMPT` (the guard file contains literal "CREATE TABLE" and would flag itself); no actionable defect (mirrors the 078/092 stale-premise pattern). **IDEA-122 RE-SCOPED from story 03 to story 06** — SE+CA verified there is no correct `creds.py` fix (single-profile/all-dead already exit non-zero; only mixed multi-profile false-greens; "any valid = usable" contract must hold), so the fix is skill-side (`bb creds check --profile web` preflight in `implement/SKILL.md`); story 06 retitled and now carries 122 (AC-1) + 123 (AC-2/3/4) as two distinct concerns; story 03 → 126+127, `creds.py` dropped. Story 02 #4 scope corrected (2 of 7 docstrings are in `crawlers/`, added to Files + isolation table); #8 reworded off the false "deleted dashboard port" premise (8180:8080 is the live Traefik dashboard). Story 01 gained the `_DB_PATH` import-time impl note. Story 03 IDEA-127 gained the NULL-public_id guard + refreshed anchors (`:1627`). Audit residuals 8→7. All CR findings closed (1/2/3 already incorporated in the first round; 4 informational). No finding dismissed — all correct.
- 2026-07-12: Planning-review incorporation (api-scout, docs-writer, claude-architect holistic reviews). Net changes: (1) **Story 08 ABANDONED + IDEA-078 DISCARDED** — coaching-docs rewrite premise already delivered by E-239 (`scouting-reports.md` renamed to `standalone-reports.md`; README already reports-first; verified clean by docs-writer). (2) **IDEA-092 dropped from story 05 + DISCARDED** — data-engineer.md hallucination cells already stripped by E-250-04; residual is freeze-barred enrichment (CA F1). (3) Story 05 anchors corrected: IDEA-114 → `report.py:530` (CA F5), IDEA-118 narrowed to the two leftover ambient figures `:28`/`:193` (CA F4). (4) Story 06 citation reworded (gate did not actually false-FAIL, reasoned hazard; CA F2) + grounded-frequency read made a pre-dispatch requirement (CA F3, worktrees lack the DB/CLI) — SUPERSEDED the same day by the operator's terminal-fixture decision (see the later History entry), which DISSOLVED this requirement entirely. (5) Story 07: IDEA-010 narrowed to verify-only + mitmproxy-clause dropped, IDEA-111 anchor corrected from dead `:884` to the `## Credential Rotation` section ~`:717-746` (docs-writer). (6) Story 09: AC-2 tightened to the endpoint-fidelity boundary + AC-1 rename token-scoped with the enumerated 8-file blast radius (api-scout). Fold-in count: 12 → 10; active stories: 9 → 8 (08 ABANDONED). Meta-lesson captured to PM feedback memory: re-verify an idea's target files still exist and still show the defect before folding it into a housekeeping epic (2-of-4 docs-story premises were stale here).
