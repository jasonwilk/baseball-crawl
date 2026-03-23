# E-149: Review Methodology Retro and Gap-Filling

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Systematically close the code-review methodology gaps exposed by E-147 and E-148 implementations. Codex found 18 substantive findings across 8 review rounds that the code-reviewer missed entirely. This epic adds the missing rubric items, enriches the CR assignment context, and aligns the testing rule and Codex rubric so all three review layers (CR, implementer self-check, Codex) share the same checklist vocabulary.

## Background & Context
E-147 (Team Season Year) had 6 Codex code review rounds producing 13 substantive findings (rounds 1-5), all accepted. E-148 (Review Cycle Reordering) had 2 Codex rounds producing 5 findings, all accepted. Every finding was something the per-story code-reviewer could have caught with better instructions and context.

A full retro with the team (architect, SE, CR self-assessment) identified the root causes:

- **CR's rubric has no cross-referencing instructions.** The rubric tells CR to review "every file listed in the Files Changed section" but never instructs it to look beyond that list -- at callers, API endpoint docs, migration files, or docstrings on unchanged functions.
- **CR's assignment message provides no domain context.** The per-story assignment includes the story file and epic TNs but not which API endpoints are involved, which migrations exist, or which functions changed behavior.
- **The testing rule and Codex rubric have gaps.** The testing rule covers test scope discovery but not test-validates-spec (tests that mirror buggy code). The Codex rubric (`codex-review.md`) is a lightweight version of the CR rubric and lacks the detailed checklist items.

Expert consultation completed:
- **claude-architect** (retro lead): Root cause analysis across all 18 findings, fix design mapped to specific artifacts. Designed the 3-story structure.
- **code-reviewer** (self-assessment): Confirmed 5 of 6 gap categories NOT covered by current rubric. #1 request: caller audit. Also needs API field contract, function contract preservation, deploy-time safety procedure step.
- **software-engineer** (practitioner input): Confirmed grep is sufficient for caller audit in this codebase. Provided practical procedures for deploy-time safety, API contract verification, and enhanced test scope discovery.

## Goals
- CR catches caller-impact bugs, API field path errors, function contract violations, and deploy-time safety issues during per-story review -- not deferred to Codex
- CR assignment messages include domain-specific context (API endpoints, migration files) so CR knows where to cross-reference
- Implementer completion reports include behavioral change declarations so CR knows when to expand scope
- Testing rule covers test-validates-spec pattern (test must verify against the spec, not mirror the implementation)
- Codex rubric aligned with CR rubric so both review layers use the same checklist vocabulary

## Non-Goals
- Changes to per-story review mechanics in the implement skill (circuit breaker, round structure, triage flow)
- Changes to the integration review or its scope
- Adding automated tooling (linters, static analysis) -- this epic is about instructions and context
- Changes to the CR agent's tool access or model
- Context-layer story review by CR (E-148 findings 14 and 16 are context-layer; CR skips those by design)

## Success Criteria
- The CR agent definition contains checklist items for all in-scope gap categories identified in the retro (6 new items + 1 enhancement)
- The implement skill's CR assignment template includes structured context fields for API endpoints, migration files, and behavioral changes
- The implementer completion report template includes a "Behavioral Changes" section declaring changed function signatures/return types
- The testing rule includes a test-validates-spec clause
- The Codex rubric contains inline summaries of the CR rubric's checklist items (CR agent def is single source of truth; Codex gets self-contained abbreviated versions)
- Regression test: applying the updated rubric to the E-147 finding catalog, each finding maps to at least one checklist item

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-149-01 | CR agent definition: bug pattern checklist expansion | DONE | None | - |
| E-149-02 | Implement skill: assignment template and completion report enrichment | DONE | E-149-01 | - |
| E-149-03 | Testing rule and Codex rubric alignment | DONE | E-149-01 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Finding Catalog (Retro Evidence)

18 substantive Codex findings across E-147 (13) and E-148 (5) that CR missed.

#### E-147 Findings (13 substantive, 6 rounds)

| # | Finding | Gap Type | Root Cause |
|---|---------|----------|------------|
| 1 | Wrong API field path (`team_season.year` used for authenticated endpoint; correct is `season_year`) | API contract | CR didn't cross-reference endpoint docs |
| 2 | Test mocks wrong shape matching the bug | Test-validates-bug | Test written to match implementation, not spec |
| 3 | `_resolve_year_and_team()` fallback divergence (pre-existing function not updated) | Pre-existing code interaction | CR reviewed new code but not unchanged interacting functions |
| 4 | Missing vendor Accept header on API call | API contract | CR didn't cross-reference endpoint spec for required headers |
| 5 | Cohort/season_id mismatch (year filtering without season resolution) | Pre-existing code interaction | CR reviewed filtering but not season_id resolution |
| 6 | CLI scouting pipeline doesn't heal season_year (only trigger.py path covered) | Caller/entry-point audit | CR didn't check all entry points |
| 7 | Missing test for cohort/season consistency | Test gap (follows #5) | - |
| 8 | No test for CLI scouting heal | Test gap (follows #6) | - |
| 9 | Deploy-time regression (code references column before migration runs) | Deploy-time safety | CR didn't check column dependencies vs migration state |
| 10 | `get_team_year_map()` contract broken (docstring promise dropped in rewrite) | Function contract | CR didn't compare docstring promises vs implementation |
| 11 | Stale ID fallback creates phantom teams (remediation introduced new bug) | Remediation regression | Remediation fix too broad; didn't analyze edge cases |
| 12 | CLI `bb data scout` hard-depends on migration 004 (no OperationalError guard) | Deploy-time safety | Remediation didn't inherit safety pattern from earlier fix |
| 13 | Pre-migration test gap for CLI path | Test gap (follows #12) | - |

#### E-148 Findings (5, 2 rounds)

| # | Finding | Gap Type | Root Cause |
|---|---------|----------|------------|
| 14 | Step 7a commit on main breaks Step 8's diff | Git mechanics | CR didn't trace git operation sequence (context-layer) |
| 15 | `cr_spawned` flag set before spawn succeeds | Flag/state timing | Flag timing logic error (context-layer) |
| 16 | Holistic findings routing gap | Data flow tracing | CR didn't trace where findings end up (context-layer) |
| 17 | Stale Phase 1 orientation text | Stale cross-reference | (context-layer, SHOULD FIX) |
| 18 | Scorecard example contradicts prose | Stale cross-reference | (context-layer, SHOULD FIX) |

**Note:** Findings 14 and 16 are context-layer-only and NOT in scope for this epic. Findings 15, 17, and 18 were originally classified as context-layer but are addressed via extensions: finding 15 through the Status lifecycle extension (in-memory flags, TN-3 item 7), and findings 17-18 through the stale prose reference sweep (caller audit sub-clause, TN-3 item 1). The context-layer review gap for findings 14 and 16 is a separate concern.

### TN-2: Gap Type Classification

| Gap Type | Findings | Count | Fix Artifact |
|----------|----------|-------|-------------|
| API contract (headers, field paths) | 1, 4 | 2 | CR rubric (Story 01) |
| Function contract preservation | 10, 11 | 2 | CR rubric (Story 01) |
| Semantic sibling (pre-existing parallel code) | 3, 5 | 2 | CR rubric (Story 01) |
| Caller/entry-point audit | 6, 8 | 2 | CR rubric (Story 01) |
| Deploy-time safety | 9, 12, 13 | 3 | CR rubric (Story 01) |
| Remediation-introduced regression | 11, 12 | 2 | CR rubric (Story 01) |
| Test-validates-bug | 2, 7, 13 | 3 | Testing rule (Story 03) |
| Flag/state timing logic | 15 | 1 | CR rubric -- Status lifecycle extension (Story 01) |
| Stale cross-reference | 17, 18 | 2 | CR rubric -- Caller audit stale prose sweep (Story 01) |
| Git mechanics tracing | 14 | 1 | Out of scope (context-layer) |
| Data flow tracing | 16 | 1 | Out of scope (context-layer) |

### TN-3: CR Rubric Changes (Story 01)

New/enhanced items for the Bug Pattern Checklist in the CR agent definition:

1. **Caller audit**: For every function/method whose signature, return type, or externally-observable behavior changes, grep `src/`, `scripts/`, `tests/`, and `templates/` for all callers. Read each caller and verify it remains correct. For dataclass changes, also grep for field access patterns. **Trigger sources**: (a) check the Behavioral Changes field in the review assignment (if present) -- run the caller audit for each declared function; (b) independently scan the diff for functions where the new implementation diverges from prior externally-observable behavior. **Semantic sibling extension**: After identifying callers, also search the same module and related modules for functions that implement similar behavior (same parameter names, same return type, same concern). If changed code introduces a new behavioral pattern (e.g., a new way to resolve a value), check whether parallel functions exist that implement the old pattern and should be updated to match. **Stale prose reference sweep**: When a function or constant is renamed, removed, or has its behavior significantly changed, also grep docstrings, comments, and `docs/` for references to the old name or behavior that need updating. (Addresses findings 3, 5, 6, 10, 11, 17, 18)

2. **API field contract**: When code reads fields from GameChanger API responses, cross-reference accessed field paths against `docs/api/endpoints/`. Verify field exists at documented path, correct endpoint variant is used (authenticated vs public have different schemas), and required headers are included. (Addresses findings 1, 4)

3. **Function contract preservation**: When a function is rewritten or significantly modified, compare the new implementation against its docstring, type hints, and any documented behavioral guarantees. Verify all promises are still honored (return type, return value semantics, side effects, error behavior). (Addresses findings 10, 11)

4. **Deploy-time safety**: For every new column reference in changed code (SELECT, INSERT, UPDATE, template render), verify the column exists in the current migration set. Read `migrations/*.sql` files to build the schema baseline. For new migrations, verify the migration number is sequential. For new columns on existing tables, verify Python code handles NULL (new columns default to NULL for existing rows unless DEFAULT specified). (Addresses findings 9, 12, 13)

5. **Remediation regression guard**: When reviewing Round 2 fixes (remediation of prior findings), apply the SAME checklist items to the fix code. Remediation code is new code -- it can introduce the same bug classes as original code. Specifically: if finding N was "missing X guard," verify the fix adds X guard AND doesn't introduce a Y bug. (Addresses findings 11, 12)

6. **Test-validates-spec** (cross-reference with Story 03): When reviewing test fixtures and mocks, verify they match the authoritative spec (API endpoint doc, migration schema, docstring contract) -- not the implementation under test. A test that mocks the wrong data shape passes vacuously. (Addresses finding 2)

7. **Status lifecycle extension** (enhancement to existing item): Extend the existing "Status lifecycle" checklist item to cover in-memory flags and booleans, not just database status writes. When changed code sets a flag or boolean that gates downstream behavior (e.g., `cr_spawned = True`), verify the flag is set only AFTER the gated operation succeeds. If the operation can fail and the flag is set before the attempt, downstream code may act on a stale flag. (Addresses finding 15)

### TN-4: Assignment Template Changes (Story 02)

The implement skill's CR assignment template currently includes: story file text, epic TNs, Files Changed list, test results, review round number. Add structured context fields:

1. **API endpoints touched**: List of `docs/api/endpoints/*.md` files relevant to the story (derived per TN-4a heuristics). CR should load these during Step 2 context loading.

2. **Migration files**: List of `migrations/*.sql` files. Always included when the story touches database code. CR should load these during Step 2 to build schema baseline.

3. **Behavioral changes declared by implementer**: From the implementer's completion report (see TN-4b). Lists functions whose signature, return type, or observable behavior changed. CR uses this to trigger the caller audit checklist item. **This is a supplement to CR's own caller audit, not a replacement** -- CR still independently scans the diff for non-obvious behavioral changes that the implementer may not have recognized.

The completion report template lives in the implementer spawn context's `**Completion**` paragraph (Phase 3 Step 4, ~line 214 of `implement/SKILL.md`), where `## Files Changed` and `## Test Results` are already defined. The new `## Behavioral Changes` section is added alongside them.

### TN-4a: Derivation Heuristics for Context Fields

The main session uses these heuristics to decide which context fields to include in the CR assignment. Check both the story's "Files to Create or Modify" and the implementer's Files Changed list:

- **API endpoints**: Include when any file is under `src/gamechanger/crawlers/`, `src/gamechanger/loaders/`, `src/gamechanger/client.py`, or `src/pipeline/` (modules that parse API responses, make HTTP calls, or orchestrate API-dependent pipelines). `src/gamechanger/config.py`, `src/gamechanger/types.py`, and similar utility modules do NOT trigger this field. **Specificity**: Derive specific endpoint docs from the story's Technical Approach or description (e.g., if the story mentions "public team endpoint," include `docs/api/endpoints/public-team.md`). If specific endpoints cannot be determined, include all files matching `docs/api/endpoints/*.md` -- the full set is better than nothing.
- **Migration files**: Include when any file is under `src/api/`, `src/gamechanger/loaders/`, `src/db/`, `src/pipeline/`, `migrations/`, or templates referencing database columns.

### TN-4b: Behavioral Changes Definition and Policy

**What counts as a behavioral change**: Any change to a function's signature (added/removed/reordered parameters, changed types), return type, raised exceptions, or documented side effects. Internal refactors that preserve the function's contract (same inputs produce same outputs, same side effects, same error behavior) are NOT behavioral changes.

**Always-present policy**: The `## Behavioral Changes` section is always present in completion reports. When no behavioral changes occurred, the implementer writes "None." This makes it explicit that the implementer considered the question, rather than forgot the section.

**Format**:

```
## Behavioral Changes
- `function_name()` in `file.py`: [what changed -- new param, different return type, changed semantics]
```

Or when none:

```
## Behavioral Changes
None
```

### TN-5: Testing Rule Changes (Story 03)

Add a **Test-validates-spec** clause to `.claude/rules/testing.md`:

When writing tests that mock external data (API responses, database query results, file contents), verify the mock data matches the authoritative spec -- not the implementation under test. Sources of truth: `docs/api/endpoints/` for API response shapes, `migrations/*.sql` for database schemas, function docstrings for return value contracts. A test whose mock data mirrors a buggy implementation passes vacuously and provides false confidence.

### TN-6: Codex Rubric Alignment (Story 03)

The Codex rubric (`.project/codex-review.md`) is a lightweight version of the CR rubric. The codex-review skill embeds the rubric content directly in the prompt (the model does not have file access in ephemeral mode). Therefore, a cross-reference to `.claude/agents/code-reviewer.md` would be dead text -- Codex cannot follow file references.

Instead, add a new priority item with **inline summaries** of each checklist item (one sentence each, not full text). The CR agent definition remains the authoritative source; the Codex rubric carries abbreviated versions sufficient to trigger the check during review:

```
7. **Extended bug pattern checks** (abbreviated from `.claude/agents/code-reviewer.md` Bug Pattern Checklist):
   - Caller audit: grep for callers of any changed function; verify callers remain correct; check semantic siblings and stale prose references
   - API field contract: cross-reference API field paths against docs/api/endpoints/
   - Function contract preservation: verify docstring/type-hint promises still hold after rewrites
   - Deploy-time safety: verify new column references exist in migrations/*.sql
   - Remediation regression guard: apply full checklist to Round 2 fix code
   - Test-validates-spec: verify test mocks match the spec, not the implementation
   - Status lifecycle (extended): verify in-memory flags/booleans set only after gated operation succeeds
```

When the CR rubric's checklist items are updated in the future, the Codex rubric summaries should be updated to match. The abbreviated format minimizes drift surface while keeping Codex functional.

### TN-7: Regression Test Matrix

After all stories are complete, the following matrix should hold -- each finding maps to at least one checklist item that would have caught it:

| Finding | Catching Checklist Item |
|---------|------------------------|
| 1 (wrong API field path) | API field contract |
| 2 (test mocks wrong shape) | Test-validates-spec |
| 3 (pre-existing function divergence) | Caller audit (semantic sibling extension) |
| 4 (missing vendor Accept header) | API field contract |
| 5 (cohort/season_id mismatch) | Caller audit (semantic sibling extension) |
| 6 (CLI scouting not covered) | Caller audit |
| 9 (deploy-time column reference) | Deploy-time safety |
| 10 (docstring contract broken) | Function contract preservation |
| 11 (phantom teams from broad fix) | Remediation regression guard |
| 12 (CLI migration dependency) | Deploy-time safety + Remediation regression guard |
| 15 (flag set before spawn succeeds) | Status lifecycle extension (in-memory flags) |
| 17 (stale orientation text) | Caller audit (stale prose reference sweep) |
| 18 (scorecard example contradicts prose) | Caller audit (stale prose reference sweep) |

Findings 7, 8, 13 are test gaps that follow from their parent findings. Findings 14, 16 are context-layer interaction patterns (git mechanics, data flow tracing) that remain out of scope -- they require tracing multi-step procedural interactions in skill files, which is a different class of review than code review.

**Note on findings 3 and 5**: These are "semantic sibling" bugs -- pre-existing parallel code that should have been updated to match new behavior. The caller audit's semantic sibling extension addresses this class, but it requires semantic understanding (recognizing that two functions handle the same concern differently), not just mechanical grep. This is the hardest class of bug for a reviewer to catch systematically. The semantic sibling extension is the best available instruction; it may not catch every instance.

**Regression matrix verification**: PM verifies this matrix at epic closure by confirming each in-scope finding maps to at least one checklist item in the shipped artifacts. This is a PM closure gate, not a story AC.

## Open Questions
None -- all resolved during team consultation.

## History
- 2026-03-23: Created. Full team retro with architect (retro lead), CR (self-assessment), SE (practitioner input). 18 findings cataloged, 11 gap types classified, 6 in-scope gap types mapped to 3 stories.
- 2026-03-23: Set to READY after 8 review passes (27 findings, 21 accepted, 6 dismissed).
- 2026-03-23: COMPLETED. All 3 stories DONE. Added 6 new + 1 enhanced Bug Pattern Checklist items to CR rubric (caller audit, API field contract, function contract preservation, deploy-time safety, remediation regression guard, test-validates-spec, status lifecycle extension). Enriched implement skill with structured CR assignment context (API endpoints, migration files, behavioral changes) and implementer completion report template. Added test-validates-spec clause to testing rule. Aligned Codex rubric with CR checklist via inline summaries. TN-7 regression test matrix verified: all 13 in-scope findings map to shipped checklist items.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic (Architect + SE + CR) | 14 | 11 | 3 |
| Internal iteration 2 -- CR spec audit | 3 | 2 | 1 |
| Internal iteration 2 -- Architect holistic | 0 | 0 | 0 |
| Internal iteration 3 -- CR + PM + Architect | 0 | 0 | 0 |
| Context-fundamentals (Architect) | 0 | 0 | 0 |
| Codex iteration 1 | 2 | 2 | 0 |
| Codex iteration 2 | 4 | 2 | 2 |
| Per-story PM AC verification -- E-149-01 | 0 | 0 | 0 |
| Per-story PM AC verification -- E-149-02 | 0 | 0 | 0 |
| Per-story PM AC verification -- E-149-03 | 0 | 0 | 0 |
| CR integration review | 2 | 2 | 0 |
| Codex code review | 2 | 2 | 0 |
| **Total** | **31** | **25** | **6** |

### Documentation Assessment
No documentation impact. This epic modifies only context-layer files (agent definitions, rules, skills, rubric). No `docs/admin/` or `docs/coaching/` updates required.

### Context-Layer Assessment
All changes are context-layer by nature -- the entire epic delivers context-layer artifacts. Per-trigger verdicts:
1. **New or changed agent behavior**: YES -- CR agent definition expanded with 7 checklist items. Satisfied by E-149-01.
2. **New or changed rules**: YES -- testing rule updated with test-validates-spec clause. Satisfied by E-149-03.
3. **New or changed skills**: YES -- implement skill enriched with assignment template and completion report changes. Satisfied by E-149-02.
4. **New or changed hooks**: NO.
5. **CLAUDE.md updates needed**: NO -- no new conventions, commands, or architecture changes requiring CLAUDE.md update.
6. **Agent memory updates needed**: NO -- no new patterns or decisions requiring agent memory codification beyond what the epic itself delivers.

No separate architect dispatch needed -- the epic's own deliverables ARE the context-layer changes.
