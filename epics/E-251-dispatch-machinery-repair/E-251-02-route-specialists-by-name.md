# E-251-02: Route SE/DE/api-scout dispatch stories by name (F-H4)

## Epic
[E-251: Dispatch-Machinery Repair](../E-251-dispatch-machinery-repair/epic.md)

## Status
`TODO`

## Description
After this story is complete, the Agent Selection routing table dispatches Python-implementation, DB-schema, and API-exploration stories to their named agents (`software-engineer`, `data-engineer`, `api-scout`) instead of bare `general-purpose` spawns. This ensures each specialist's definition, Pre-Submission Checklist, model/effort frontmatter, and agent memory load during dispatch.

## Context
This is audit finding **F-H4** (HIGH). A `general-purpose` spawn never loads the named agent's definition, checklist (written to catch recurring bug classes), model/effort frontmatter, or memory — so the three highest-volume implementation story domains run un-instrumented at default model/effort. The rest of the same table already routes by name (context-layer→claude-architect, docs→docs-writer, UI→ux-designer); these three rows are the inconsistency. Per epic TN-3.

## Acceptance Criteria
- [ ] **AC-1**: In `.claude/rules/agent-routing.md`'s "Agent Selection for Dispatch" table, the `Python implementation, crawlers, parsers, tests` row's Agent Type is `software-engineer`, the `Database schema, SQL migrations, ETL` row's Agent Type is `data-engineer`, and the `API exploration, endpoint docs` row's Agent Type is `api-scout` — no longer `general-purpose`.
- [ ] **AC-2**: Any surrounding prose that explained the old `general-purpose` (role in prompt) mechanism is reconciled so the table and its explanation agree (no lingering claim that these domains spawn `general-purpose`). CA determines whether the "role in prompt" phrasing is dropped or rewritten.
- [ ] **AC-3**: The change is consistent with how the rest of the table already routes by named agent and with the dispatch-pattern rule (`.claude/rules/dispatch-pattern.md`); no other routing rule is left contradicting the corrected table. If a cross-reference elsewhere in `.claude/**` still asserts `general-purpose` for these domains, CA reconciles or flags it.
- [ ] **AC-4**: `grep -n "general-purpose" .claude/rules/agent-routing.md` returns no line that routes SE/DE/api-scout story domains to `general-purpose` (an incidental mention in unrelated prose, if any survives, is acceptable only if it does not assign these domains).

## Technical Approach
Per epic TN-3. Edit the three table cells to the named agents and reconcile the adjacent explanatory prose. This is the audit's "three cell edits" quick win; CA verifies no other routing surface still asserts `general-purpose` for these domains.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/agent-routing.md` — route the three implementation-domain rows to named agents; reconcile adjacent prose

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Self-contained fix (audit file is uncommitted). Audit ref: §2 HIGH F-H4 (`.claude/rules/agent-routing.md:12`); §5 Quick Wins ("Route SE/DE/api-scout by name in agent-routing.md — three cell edits").
