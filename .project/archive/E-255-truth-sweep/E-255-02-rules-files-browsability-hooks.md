# E-255-02: Rules-file truth corrections + delete agent-browsability doc + hooks README

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`

## Description
After this story is complete, the remaining rules files (`testing.md`, `key-metrics.md`, `gc-uuid-bridge.md`, `api-docs.md`) describe current reality, `.claude/hooks/README.md`'s hook-failure description matches the E-251-04 behavior change, and the obsolete `docs/agent-browsability-workflow.md` is removed (with its lone stale reference in IDEA-010 flagged for PM cleanup). Two agentic-flow-review hook fixes are also folded in (routed here 2026-07-07 as scope-adds in this story's hooks domain): the `edit-verify.sh` memory-path false-positive carve-out and a new `secret-read-guard.sh`.

## Context
Second claude-architect cluster — rules files NOT in E-255-01, plus two discrete removals/reconciliations. File-disjoint from E-255-01/03 (TN-3). Three corrections depend on facts settled by E-255-R-01 (testing.md `team_season` shape, `pitches_7d` semantics, gc-uuid E-211 self-heal) — do not guess. `docs/agent-browsability-workflow.md` was confirmed to still exist during discovery; CA recon confirms its only inbound references are archived epics + IDEA-010 (safe to delete; flag IDEA-010).

## Acceptance Criteria
- [ ] **AC-1**: Given `testing.md` L94/L109's worked example nesting year at `team_season.season.year` (which contradicts `data-model.md` L18's flat shape), when corrected to the E-255-R-01 verified shape, then the worked example uses the actual **`GET /public/teams/{public_id}`** response shape (doc `get-public-teams-public_id.md`, consistent with R-01 AC-2 + story 04 AC-6 — NOT the bridge `public-team-profile` doc, which has no `team_season`) and the "spec wins" guidance reflects current authority conventions. (CA fixes both testing.md here and data-model.md in E-255-01 to the same verified shape.)
- [ ] **AC-2**: Given `key-metrics.md`'s `pitches_7d` NULL/0 semantics are INVERTED vs the shipped code (DE confirmed via `get_pitching_workload()` `src/api/db.py` L205-209: **`0` = no outings in the 7-day window** (LEFT JOIN miss), **`NULL` = had outing(s) but ALL pitch counts unrecorded / unknown**, `SUM` = normal — the file currently documents the inverse) and its GS member-path line, when corrected to the E-255-R-01-recorded direction, then `key-metrics.md` states that CORRECT direction explicitly (the implementer must NOT copy the existing inverted prose), notes that a NULL `pitches_7d` must never be read as zero-risk (it is unknown/unrecorded, not "no load" — the renderer already shows "?p", so this is doc belt-and-suspenders), and the GS description matches the current `appearance_order`-derived path. NOTE: the audit's "Longitudinal bullet" is ALREADY gone — verify and exclude.
- [ ] **AC-3**: Given `gc-uuid-bridge.md`'s Storage Rule (L94 "never overwrite existing gc_uuid") that contradicts the deliberate E-211 self-heal overwrite, when reconciled to the E-255-R-01 verified E-211 behavior, then the Storage Rule text is consistent with the self-heal overwrite (no contradiction).
- [ ] **AC-4**: Given `.claude/rules/api-docs.md`'s structure counts (audit: says "89 files") and flow-doc list (says 1, live = 4: opponent-resolution, opponent-scouting, plays-ingestion, spray-chart-rendering), when reconciled against the canonical phrasing api-scout sets in E-255-04, then the count reads **"120 files (119 endpoints + 1 web-routes reference)"** (matching `docs/api/README.md` exactly — NOT a flat "120 endpoints") and all four flow docs are referenced.
- [ ] **AC-5**: Given `.claude/hooks/README.md`'s stale "fail open" prose (L130-135, stale post-E-251-04), when reconciled against the ACTUAL current hook behavior (CA verifies the hook's real failure mode before rewriting), then the README describes the true current failure mode.
- [ ] **AC-6**: Given `docs/agent-browsability-workflow.md` (a workflow doc for a superseded process), when this story completes, then the file no longer exists and a grep for `agent-browsability-workflow` across the LIVE surface — the context layer + `docs/`, EXCLUDING this epic's own spec files (`epics/E-255-truth-sweep/`) and `.project/archive/` (both legitimately retain the token as spec/history) — returns zero references. The lone live reference in `.project/ideas/IDEA-010-*.md` is cleaned by E-255-06 AC-2b (ideas are PM-owned), so it too is zero after the epic runs.
- [ ] **AC-7** (agentic-flow-review item 3 / §4.2, routed here 2026-07-07 — hooks are this story's domain): Given `.claude/hooks/edit-verify.sh` false-positive-blocks every agent-memory Write because the harness injects `originSessionId` frontmatter after the write (making byte-equality structurally impossible; all 11 corpus blocks were this false positive), when a memory-path carve-out is added, then the hook early-exits (or applies a substring predicate) for paths matching `*/projects/*/memory/*` and `*/.claude/agent-memory/*`, and on a genuine (non-carve-out) mismatch the block reason includes the byte-length delta and the recovery step.
- [ ] **AC-8** (agentic-flow-review item 13 / §4.2, routed here 2026-07-07): Given nothing currently stops a `cat .env` or a Read of `secrets/**` from pulling live GameChanger tokens into context (the only credential control fires at commit-time, which reads never reach), when a new `.claude/hooks/secret-read-guard.sh` is created and wired into `.claude/settings.json`, then Read and Bash operations targeting `**/.env*` and `secrets/**` are denied, EXCLUDING `*.example` files (which carry no secrets).

## Technical Approach
Read each file in full; re-verify per TN-1. Consume `.project/research/E-255-verified-facts.md` (E-255-R-01) for AC-1/2/3. Use api-scout's canonical count (E-255-04) for AC-4. Verify the hook's actual behavior before rewriting AC-5. Delete the browsability doc; sweep for live inbound links.

## Dependencies
- **Blocked by**: E-255-R-01 (testing.md shape, pitches_7d, E-211 self-heal), E-255-04 (canonical endpoint count for api-docs.md)
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/testing.md`
- `.claude/rules/key-metrics.md`
- `.claude/rules/gc-uuid-bridge.md`
- `.claude/rules/api-docs.md`
- `.claude/hooks/README.md`
- `docs/agent-browsability-workflow.md` (DELETE)
- `.claude/hooks/edit-verify.sh` (AC-7: memory-path carve-out)
- `.claude/hooks/secret-read-guard.sh` (AC-8: NEW hook)
- `.claude/settings.json` (AC-8: wire the secret-read guard)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `docs/agent-browsability-workflow.md` deleted; only historical inbound links remain; IDEA-010 flagged to PM
- [ ] Counts consistent with E-255-04; facts consistent with E-255-R-01
- [ ] Discharged-already items (Longitudinal bullet) recorded in story notes
- [ ] `edit-verify.sh` memory-path carve-out added (AC-7); `secret-read-guard.sh` created + wired (AC-8)

## Notes
CA flagged three fact-dependencies (pitches_7d, E-211 self-heal, team_season shape) — all sourced from E-255-R-01, not guessed. The IDEA-010 reference cleanup is routed to PM (E-255-06) because `.project/ideas/` is PM-owned.
