# E-112: Context Layer Optimization

## Status
`READY`

## Overview
Reduce ambient context layer load from ~980 lines to ~635 lines (35% reduction) to improve agent accuracy by mitigating "lost in the middle" effects. Also fix silent MEMORY.md truncation that causes 5 agents to operate on incomplete memory.

## Background & Context
Three rounds of architect evaluation (2026-03-15) identified that the ambient context layer has grown significantly since the last baseline (2026-03-03). Key findings:

1. **MEMORY.md truncation**: 5 of 6 agents have MEMORY.md files exceeding the 200-line limit. Content beyond line 200 is silently dropped -- agents lose their most valuable memory entries (coaching decisions, ETL patterns, DB conventions, security rules).
2. **CLAUDE.md bloat**: Several sections duplicate content that exists in scoped rules or docs (proxy boundary, script aliases, terminal modes, auth architecture).
3. **Universal rules with narrow scope**: `dispatch-pattern.md` (221 lines) and `worktree-isolation.md` (67 lines) load on every interaction but are only relevant during dispatch (~10-20% of interactions). The implement skill already contains equivalent content.

The architect produced a 6-step migration plan ordered by safety. Steps 2-4 (all CLAUDE.md trims) are combined into one story since they edit the same file.

**Safety invariants preserved**: `workflow-discipline.md` (96 lines) and `agent-team-compliance.md` (59 lines) are explicitly NOT touched -- these are safety-critical rules with documented failure history (6 prior epics). `vision-signals.md` (29 lines) is also kept as-is (trivial cost, genuinely ambient).

## Goals
- Fix silent MEMORY.md truncation for 5 agents so all memory content is accessible
- Reduce CLAUDE.md ambient load by ~131 lines through deduplication and compression
- Migrate ~255 lines of dispatch-only content from universal rules to dispatch-scoped delivery
- Achieve ~35% total ambient context reduction without degrading any agent capability

## Non-Goals
- Modifying `workflow-discipline.md`, `agent-team-compliance.md`, or `vision-signals.md`
- Changing agent behavior or capabilities (this is a context delivery optimization, not a behavior change)
- Restructuring the implement skill or agent definitions
- Reducing the implement skill's own size (it's dispatch-scoped, not ambient)

## Success Criteria
- All 6 agent MEMORY.md files are under 150 lines (index only), with detailed content in topic files
- CLAUDE.md is ~131 lines shorter with no information loss (all content preserved in scoped locations)
- `dispatch-pattern.md` is a ~25-line stub (routing table + pointer), down from 221 lines
- `worktree-isolation.md` is a ~5-line stub (critical prohibitions + pointer), down from 67 lines
- All existing tests pass (no regressions)
- Agent behavior is unchanged -- optimized delivery, not changed content

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-112-01 | Fix MEMORY.md Truncation for 5 Agents | TODO | None | claude-architect |
| E-112-02 | CLAUDE.md Content Trim | TODO | None | claude-architect |
| E-112-03 | dispatch-pattern.md Migration to Dispatch Scope | TODO | None | claude-architect |
| E-112-04 | worktree-isolation.md Migration to Dispatch Scope | TODO | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Safety Verdicts (from architect evaluation)
| Step | Target | Verdict | Notes |
|------|--------|---------|-------|
| 1 | Agent MEMORY.md files | GREEN | Pure improvement, zero degradation risk |
| 2 | CLAUDE.md Proxy Boundary | GREEN | Content already covered by scoped `proxy-boundary.md` rule |
| 3 | CLAUDE.md Scripts/Terminal/Shell/Codex | GREEN | All duplicate or niche reference content |
| 4 | CLAUDE.md GameChanger API | GREEN | Detail already in `docs/api/auth.md` |
| 5 | dispatch-pattern.md | YELLOW→GREEN | Safe with mitigations: create `agent-routing.md` BEFORE removing content; add dispatch trigger to implement skill |
| 6 | worktree-isolation.md | YELLOW→GREEN | Safe with stub retaining critical prohibitions |
| -- | workflow-discipline.md | RED (NOT MOVING) | Dispatch Authorization Gate must fire BEFORE dispatch trigger. Historical bugs E-047, E-056. |
| -- | agent-team-compliance.md | RED (NOT MOVING) | Safety invariant. Six epics failed to fix this. |
| -- | vision-signals.md | RED (NOT MOVING) | Trivial cost, genuinely ambient. |

### MEMORY.md Restructuring Pattern
Each over-limit MEMORY.md becomes a concise index (target: under 150 lines) pointing to topic files in the same agent-memory directory. Topic files contain the detailed content that was previously inline. The index uses the same format as the existing MEMORY.md convention (links + brief descriptions).

Agents over the limit:
- baseball-coach: 290 lines (coaching decisions list at line 274 is invisible)
- data-engineer: 265 lines (loses ETL patterns, pagination, token scheduling)
- software-engineer: 258 lines (loses DB conventions, auth patterns, testing rules)
- api-scout: 224 lines (loses boxscore facts, JWT tips, security rules)
- product-manager: 203 lines (archived epics list is extraction target)

### CLAUDE.md Trim Targets
All trims replace verbose inline content with compact summaries + pointers to existing scoped locations:
- **Proxy Boundary** (~37 lines → ~5 lines): Already duplicated by `.claude/rules/proxy-boundary.md`
- **Script Aliases** (~23 lines → ~2 lines): Every entry duplicates a `bb` command listed above
- **Terminal Modes** (~36 lines → ~5 lines): Detail only needed during dispatch (in implement skill)
- **Shell Environment** (~8 lines → ~3 lines): Compress
- **Codex Bootstrap** (~11 lines → ~3 lines): Compress
- **GameChanger API auth paragraph** (~45 lines → ~2 lines + pointer): Detail in `docs/api/auth.md`

### dispatch-pattern.md Migration
- Extract the Agent Selection routing table (~20 lines) to a new standalone universal rule `.claude/rules/agent-routing.md`
- Replace remaining ~195 lines with a ~5-line stub pointing to the implement skill as the source of truth
- The implement skill already contains all dispatch procedure content
- **Mitigation**: Add "dispatch story E-NNN-SS" to implement skill triggers. Create `agent-routing.md` BEFORE removing dispatch-pattern content.

### worktree-isolation.md Migration
- Replace 67 lines with ~5-line stub retaining the 3 critical "MUST NOT" categories (no Docker, no credentials, no branch management)
- Full constraints are already injected via spawn prompt by the implement skill
- The stub serves as a safety net for any edge case where the skill injection is missed

### Execution Constraints
All stories modify context-layer files exclusively. Per the context-layer exception in dispatch-pattern.md, they run in the main checkout (no worktree isolation) and are serialized. Recommended execution order matches story numbering (priority order), but each story is independently safe.

## Open Questions
None -- architect evaluation resolved all open questions across 3 rounds.

## History
- 2026-03-15: Created from architect's context layer optimization evaluation (3 rounds). No expert consultation required -- architect evaluation serves as the technical foundation. PM role is purely structural (packaging the plan into stories).
