# E-239-06: Context-Layer Cleanup (Rules + CLAUDE.md, Reports-Only)

## Epic
[E-239: Decouple Pipeline Imports, Then Remove the Unused Surfaces](epic.md)

## Status
`TODO`

## Description
After this story is complete, the context layer (CLAUDE.md, `.claude/rules/*`, `.claude/skills/plan/SKILL.md`) and `docs/ROADMAP.md` §0 describe only the reports-first surviving system: stale parity/pipeline rules are removed or rewritten, the command list is trimmed, `quarantine.md` and `scouting-data-flows.md` are deleted (the latter after migrating its surviving conventions), and no rule `paths:` frontmatter references a deleted file.

## Context
All `.claude/` edits route to claude-architect (agent-routing.md Routing Precedence), so the full context-layer cleanup is consolidated into this single story, gated on the code-removal stories so the docs match the final surviving surface. The complete scope is Technical Notes §I (from the CA recon). The `quarantine.md` deletion is safe because the high-value `resolve_unlinked()` follow→bridge→unfollow ban is already fully documented in `gc-uuid-bridge.md` (L45-55), and E-239-05 deletes `opponent_resolver.py` entirely, so the in-code path is gone. `src/pipeline` is fully deleted (E-239-04), so the `perspective-provenance.md` `src/pipeline/**` `paths:` entry is dangling and must be removed.

## Acceptance Criteria
- [ ] **AC-1**: CLAUDE.md edits per Technical Notes §I — delete the "Scouting pipeline parity (FROZEN)" bullet, the "Pipeline caller convention" bullet, and the `finalize_opponent_resolution` canonical bullet; rewrite the shared-query bullet to reports-only; update the L21 strategic-frame note. (The `docs/ROADMAP.md` §0 D2 → COMPLETED flip is NOT in this story — it is a PM/main epic-closure action per the §0 tracking convention; CR Minor note.)
- [ ] **AC-2**: Command-list trim per Technical Notes §I — CLAUDE.md's command section drops the deleted `bb data` commands and ALL `--crawler`/`--loader` documentation, keeps the surviving commands, and the `backfill-appearance-order` footgun line is repointed from `bb data scout` to `canonical_recompute`/`bb report verify-aggregates`.
- [ ] **AC-3**: `scouting-data-flows.md` is deleted AFTER its surviving reports-only conventions (the `/reports/{slug}` serve rules, no `team_opponents` dependency, 14-day expiry, self-contained `src/reports/`) are migrated into the `architecture-subsystems.md` Reports Package section. The CLAUDE.md L128 pointer to the deleted `scouting-data-flows.md` is explicitly removed/repointed (CA finding S5a).
- [ ] **AC-4**: `admin-ui.md` is rewritten to reports-admin-only (the "Post-Cascade Probe for Retention UI" subsection SURVIVES, retargeted to the report-delete flow). **Its `paths:` frontmatter entry `src/api/routes/admin.py` is REPOINTED to the new reports-admin module created in E-239-01 (CA) — otherwise the rewritten rule never loads when an agent edits the surviving admin code.** Surgical edits land on `perspective-provenance.md` (delete the "Own-Team Pipeline (Disk Cache)" subsection, trim the member-team clause, REMOVE the dangling `src/pipeline/**` `paths:` entry), `key-metrics.md` (pitching-workload note → reports-only), `architecture-subsystems.md` (Background Pipeline Trigger + Scouting Pipeline sections; ALSO delete the "Canonical Opponent Resolution (Detail)" section since `finalize_opponent_resolution` is removed, and drop the `/dashboard/charts/` references in the "Chart Rendering" and "Spray Chart Pipeline" sections while KEEPING the spray-renderer description — CA finding S5b), and `data-model.md` (reword the two `bb data scout` references in "Plays pipeline dedup gap" to `bb data dedup-players`; inert-table descriptions stay).
- [ ] **AC-4b** (CA finding S4 — the `quarantine.md`-delete "zero loss" depends on these): `.claude/rules/gc-uuid-bridge.md`'s BANNED-PATH section is rewritten **self-contained** — both dangling `quarantine.md` pointers (L47, L55) are dropped, the ban is reframed to "do NOT REINTRODUCE the follow→bridge→unfollow pattern" (the `opponent_resolver.py` code is deleted in E-239-05), and the in-code deprecation-banner sentence is dropped. `.claude/rules/agent-routing.md` L30 (which references the deleted `quarantine.md` and the no-longer-existent "quarantined surfaces", and loads on `paths: "**"`) is removed or rewritten.
- [ ] **AC-5**: `quarantine.md` is deleted (its ban survives in `gc-uuid-bridge.md`); the "what was removed" record lives in this epic's History + ROADMAP §0, not a live rule.
- [ ] **AC-6**: No rule `paths:` frontmatter references a deleted file. The COMPLETE grep-verified set (CA exhaustive sweep 2026-06-16; excludes `quarantine.md`/`scouting-data-flows.md` which are deleted whole): `architecture-subsystems.md` (`src/pipeline/**` — TWO separate lines — + `src/api/routes/dashboard.py`), `display-philosophy.md` (`dashboard.py`), `pitch-rules.md` (`dashboard.py` + the two `templates/dashboard/*.html` entries: opponent_detail, opponent_print), `http-discipline.md` (`src/pipeline/**` [Codex C5] + `scripts/*crawl*` [CA — `scripts/crawl.py` deleted in 04]), and `perspective-provenance.md` (`src/pipeline/**`, also AC-4). Remove the deleted-path entries only, keep the bodies.
- [ ] **AC-6b** (OVER-DELETION GUARD — CA): do NOT remove the `src/gamechanger/crawlers/**` or `src/gamechanger/loaders/**` `paths:` globs anywhere they appear (`architecture-subsystems.md`, `data-model.md`, `key-metrics.md`, `perspective-provenance.md`) — they look deletion-adjacent but STILL MATCH survivors (scouting/plays crawlers; game/plays/scouting loaders). They MUST stay.
- [ ] **AC-6c** (pre-existing, no-pre-existing-excuse): while editing `http-discipline.md` frontmatter, also remove its already-dangling `scripts/*fetch*` entry (matches no current file — NOT D2-caused, fixed in the same pass per the no-pre-existing-excuse discipline).
- [ ] **AC-6d**: the "Dashboard / UI / display" routing row in `.claude/skills/plan/SKILL.md` is repointed to the reports UI or dropped. No hook code changes.
- [ ] **AC-7**: Every claim remaining in the edited context-layer files matches the post-E-239-05 code surface — no reference to a deleted module/route/command/symbol survives except as an explicit "removed in E-239" historical note (consistency sweep). Full suite green (no test references a broken doc anchor).

## Technical Approach
Work from Technical Notes §I as the checklist. Migrate the surviving conventions into `architecture-subsystems.md` BEFORE deleting `scouting-data-flows.md`. Grep the context layer for references to each deleted symbol/path/command to find every occurrence (consistency sweep). Documentation/context-layer work only — no `src/`, `tests/`, or `migrations/` edits.

## Dependencies
- **Blocked by**: E-239-02, E-239-03, E-239-04, E-239-05 (docs match the final surviving surface)
- **Blocks**: None

## Files to Create or Modify
- MODIFY `CLAUDE.md` (parity/pipeline bullets, shared-query bullet, command list + footgun line, L21 frame, L128 scouting-data-flows pointer)
- MODIFY `.claude/rules/architecture-subsystems.md` (migrate reports-only conventions; rewrite trigger/scouting sections; delete Canonical Opponent Resolution section; drop `/dashboard/charts/` refs; clean `paths:`)
- DELETE `.claude/rules/scouting-data-flows.md` (after migration)
- DELETE `.claude/rules/quarantine.md`
- MODIFY `.claude/rules/gc-uuid-bridge.md` (rewrite BANNED-PATH section self-contained; drop quarantine.md pointers)
- MODIFY `.claude/rules/agent-routing.md` (remove/rewrite L30 quarantine pointer + stale "quarantined surfaces")
- MODIFY `.claude/rules/admin-ui.md` (rewrite to reports-admin-only; keep Post-Cascade Probe; REPOINT `paths:` `src/api/routes/admin.py` → the new E-239-01 reports-admin module)
- MODIFY `.claude/rules/perspective-provenance.md` (delete disk-cache subsection; trim member clause; remove `src/pipeline/**` `paths:` entry)
- MODIFY `.claude/rules/key-metrics.md` (pitching-workload note → reports-only)
- MODIFY `.claude/rules/data-model.md` (`bb data scout` → `bb data dedup-players`)
- MODIFY `.claude/rules/display-philosophy.md` (clean dangling `dashboard.py` `paths:` entry, keep body)
- MODIFY `.claude/rules/pitch-rules.md` (clean dangling `dashboard.py` + two `templates/dashboard/*.html` `paths:` entries, keep body)
- MODIFY `.claude/rules/http-discipline.md` (clean dangling `paths:` entries: `src/pipeline/**` [Codex C5] + `scripts/*crawl*` [CA] + the pre-existing `scripts/*fetch*` [AC-6c]; keep body)
- NOTE (AC-6b over-deletion guard): do NOT remove `src/gamechanger/crawlers/**` or `src/gamechanger/loaders/**` `paths:` globs from any rule — they match survivors
- MODIFY `.claude/skills/plan/SKILL.md` (repoint/drop the dashboard routing row)
- NOTE: the `docs/ROADMAP.md` §0 D2 → COMPLETED flip is a PM/main epic-closure action, NOT part of this story

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Context-layer files match the post-removal code surface (consistency sweep done)
- [ ] No regressions in existing tests

## Notes
Routed to claude-architect per agent-routing.md Routing Precedence (any `.claude/` edit). Consolidating all context-layer edits here keeps a single reviewer and avoids putting context-layer edits inside the SE/DE deletion stories.
