# E-112: Context Layer Optimization

## Status
`COMPLETED`

## Overview
Reduce ambient context layer load from ~980 lines to ~380 lines (61% reduction) and CLAUDE.md from 508 to ~150 lines (70% reduction) through systematic content placement -- moving every section to the delivery mechanism where it belongs (scoped rules, skills, agent defs, or docs). Also fix silent MEMORY.md truncation that causes 5 agents to operate on incomplete memory.

## Background & Context
Three rounds of architect evaluation (2026-03-15) identified that the ambient context layer has grown significantly since the last baseline (2026-03-03). Key findings:

1. **MEMORY.md truncation**: 5 of 6 agents have MEMORY.md files exceeding the 200-line limit. Content beyond line 200 is silently dropped -- agents lose their most valuable memory entries (coaching decisions, ETL patterns, DB conventions, security rules).
2. **CLAUDE.md bloat**: Several sections duplicate content that exists in scoped rules or docs (proxy boundary, script aliases, terminal modes, auth architecture).
3. **Universal rules with narrow scope**: `dispatch-pattern.md` (221 lines) and `worktree-isolation.md` (67 lines) load on every interaction but are only relevant during dispatch (~10-20% of interactions). The implement skill already contains equivalent content.

The architect produced a 6-step migration plan ordered by safety. Steps 2-4 (all CLAUDE.md trims) are combined into one story (E-112-02) since they edit the same file. A subsequent PM+CA placement audit identified ~227 additional lines that belong in scoped rules, captured as E-112-05.

**Safety invariants preserved**: `workflow-discipline.md` (96 lines) and `agent-team-compliance.md` (59 lines) are explicitly NOT touched -- these are safety-critical rules with documented failure history (6 prior epics). `vision-signals.md` (29 lines) is also kept as-is (trivial cost, genuinely ambient).

## Goals
- Fix silent MEMORY.md truncation for 5 agents so all memory content is accessible
- Reduce CLAUDE.md from 508 to ~150 lines (70%) by placing every section in the right delivery mechanism
- Migrate ~255 lines of dispatch-only content from universal rules to dispatch-scoped delivery
- Achieve ~61% total ambient context reduction (980 → ~380 lines) without degrading any agent capability

## Non-Goals
- Modifying `workflow-discipline.md`, `agent-team-compliance.md`, or `vision-signals.md`
- Changing agent behavior or capabilities (this is a context delivery optimization, not a behavior change)
- Restructuring the implement skill's workflow logic or agent definitions (E-112-04 adds worktree constraints to the skill's spawn template, but does not change dispatch behavior)
- Reducing the implement skill's own size (it's dispatch-scoped, not ambient)

## Success Criteria
- All 6 agent MEMORY.md files are under 150 lines (index only), with detailed content in topic files
- CLAUDE.md is ~150 lines or fewer (down from 508), with no information loss (all content preserved in scoped locations)
- `dispatch-pattern.md` is a ~25-line stub (routing table + pointer), down from 221 lines
- `worktree-isolation.md` is a ~5-line stub (critical prohibitions + pointer), down from 67 lines
- True-ambient context load is ~380 lines or fewer (down from ~980)
- All existing tests pass (no regressions)
- Agent behavior is unchanged -- optimized delivery, not changed content

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-112-01 | Fix MEMORY.md Truncation for 5 Agents | DONE | None | claude-architect |
| E-112-02 | CLAUDE.md Content Trim | DONE | None | claude-architect |
| E-112-03 | dispatch-pattern.md Migration to Dispatch Scope | DONE | None | claude-architect |
| E-112-04 | worktree-isolation.md Migration to Dispatch Scope | DONE | None | claude-architect |
| E-112-05 | CLAUDE.md Placement Migration | DONE | E-112-02 | claude-architect |

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
| 6 | worktree-isolation.md | YELLOW→GREEN | Safe with inline-first approach: inline constraints in skill, then stub rule (original assumption corrected in round 2) |
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
- **Terminal Modes** (~36 lines → ~5 lines): Detail in `docs/admin/terminal-guide.md`
- **Shell Environment** (~8 lines → ~3 lines): Compress
- **Codex Bootstrap** (~11 lines → ~3 lines): Compress
- **GameChanger API auth paragraph** (~45 lines → ~2 lines + pointer): Detail in `docs/api/auth.md`

### dispatch-pattern.md Migration
- Extract the Agent Selection routing table (~20 lines) to a new standalone universal rule `.claude/rules/agent-routing.md`
- Replace remaining ~195 lines with a ~5-line stub pointing to the implement skill as the source of truth
- The implement skill already contains all dispatch procedure content (validated round 2), with one gap: migration serialization constraint is missing from the skill and must be added
- **Mitigation**: Add "dispatch story E-NNN-SS" to implement skill triggers. Create `agent-routing.md` BEFORE removing dispatch-pattern content. Add migration serialization constraint to skill.

### worktree-isolation.md Migration
- Inline the full worktree constraint set into the implement skill's spawn context template FIRST (replacing the current file reference), then reduce the rule to a ~5-line stub
- **Corrected assumption**: The original plan assumed the implement skill already inlined worktree constraints. Validation (round 2) discovered the skill REFERENCES the rule file by path ("Review `.claude/rules/worktree-isolation.md`...") rather than inlining. Stubbing the rule without inlining first would break worktree agents. The revised approach: inline in skill first, then stub.
- The stub retains the 3 critical "MUST NOT" categories (no Docker, no credentials, no branch management) as defense-in-depth
- Adding ~40 lines to the dispatch-scoped skill adds 0 ambient cost

### CLAUDE.md Placement Migration (E-112-05)
After E-112-02 trims duplicated content, E-112-05 completes the placement audit by moving remaining sections to their proper delivery mechanisms:

**New scoped rules to create:**
- Dependency management + Python version policy (~45 lines) → scoped to `requirements*`, `pyproject.toml`, `.python-version`, `Dockerfile`, `.devcontainer/devcontainer.json` (Python version sync requires all four locations)
- HTTP request discipline (~28 lines) → scoped to `src/http/**`, `src/gamechanger/**` (absorbs existing `crawling.md`)
- App troubleshooting (~39 lines) → scoped to `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `migrations/**` (tighter than original `src/**` to avoid injecting 39 lines on every source edit; CLAUDE.md retains a 1-line "rebuild after src/ changes" reminder)

**Existing rules to extend:**
- `proxy-boundary.md` ← absorb Bright Data subsection (~40 lines)
- `python-style.md` ← absorb Code Style section (6 lines)

**Pure duplicate removals (no new destination needed):**
- Testing section (4 lines) -- duplicate of `testing.md`
- Ideas content in Project Management section (~20 lines) -- duplicate of ideas workflow in rules
- Main Session Compliance pointer (~6 lines) -- duplicate of `agent-team-compliance.md`
- Workflow Contract (~12 lines) -- duplicate of `workflow-discipline.md`
- Proxy lifecycle commands (~17 lines) -- duplicate of `proxy-boundary.md`

**Relocate:**
- Statusline (10 lines) → `.claude/hooks/README.md`

**Context-fundamentals skill update:**
- Update budget table, worked example, and Decision 1 in `.claude/skills/context-fundamentals/SKILL.md` with post-E-112 actuals. Includes new "Triggered rules" variable component row (~0-400 lines depending on files touched) and MEMORY.md topic file indirection in Decision 1. This is done in E-112-05 (not E-112-02) because only after the final CLAUDE.md story are the numbers stable.

**Placement framework** (what belongs where):
- **CLAUDE.md** = genuinely ambient project identity (purpose, scope, stack, deployment target, security rules, git conventions, key directories)
- **Rules** = universal invariants and safety gates that fire on matching file paths
- **Skills** = triggered workflows loaded on demand
- **Agent defs** = role-scoped knowledge
- **Memory** = learned patterns, operational knowledge

### Execution Constraints
All stories modify context-layer files exclusively. Per the context-layer exception in dispatch-pattern.md, they run in the main checkout (no worktree isolation) and are serialized. Recommended execution order matches story numbering (priority order), but each story is independently safe. E-112-03 and E-112-04 both modify the implement skill but touch different sections; serialization prevents conflicts.

## Open Questions
- Monitor first 2-3 post-dispatch cycles for context regressions -- agents missing information they previously had access to. If regressions appear, widen the affected rule's `paths:` scoping.

## History
- 2026-03-15: Created from architect's context layer optimization evaluation (3 rounds). No expert consultation required -- architect evaluation serves as the technical foundation. PM role is purely structural (packaging the plan into stories).
- 2026-03-15: Expanded scope after PM+CA refinement session. CA performed a systematic placement audit identifying ~227 additional CLAUDE.md lines that belong in scoped rules. Added E-112-05 (CLAUDE.md Placement Migration). Updated targets from 35% to 61% ambient reduction, CLAUDE.md from ~377 to ~150 lines. IDEA-026 created for future work (subdirectory intent nodes, rules consolidation, automated staleness detection).
- 2026-03-15: Second refinement pass (CA+SE validation). CA read every source and destination file to verify plan assumptions. Critical finding: E-112-04's core assumption was false -- the implement skill REFERENCES `worktree-isolation.md` by path, it does not inline constraints. Stubbing the rule as-is would break worktree agents. Resolution: revised E-112-04 to inline constraints in the skill first, then stub the rule. Also identified: (1) migration serialization gap in implement skill (added AC to E-112-03), (2) dependency-management.md needs Dockerfile + devcontainer.json in paths (updated E-112-05 AC-1), (3) app-troubleshooting.md `src/**` scope too broad -- tightened to `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `migrations/**` with 1-line CLAUDE.md reminder (updated E-112-05 AC-3), (4) ideas-workflow.md needs `epics/**` in paths (added E-112-05 AC-12). SE confirmed all amendments are implementation-safe.
- 2026-03-16: Third and fourth refinement passes (context-fundamentals lens + edge cases). Context-fundamentals skill budget update relocated from E-112-02 Notes to E-112-05 AC (final numbers not stable until last story). E-112-04 dependency note corrected (depends on E-112-03 for implement skill frontmatter, not independent). Shared-file note added to Execution Constraints (E-112-03 and E-112-04 both modify implement skill). Open Questions updated with post-dispatch monitoring note.
- 2026-03-16: **COMPLETED.** All 5 stories executed serially by claude-architect in the main checkout (context-layer exception). Key outcomes: (1) All 6 agent MEMORY.md files restructured -- 5 were over the 200-line silent truncation limit, now all under 150 lines with detailed content in topic files. (2) CLAUDE.md reduced from 508 → 152 lines (70% reduction) through systematic placement migration -- every section moved to its proper delivery mechanism. (3) dispatch-pattern.md reduced from 221 → 24 lines (stub pointing to implement skill as source of truth). (4) worktree-isolation.md reduced from 67 → 14 lines (stub with critical prohibitions, full constraints inlined in implement skill). (5) 4 new scoped rules created: dependency-management.md, http-discipline.md (absorbed crawling.md), app-troubleshooting.md, context-layer-guard.md. (6) 2 existing rules extended: proxy-boundary.md (Bright Data), python-style.md (Code Style). (7) Agent routing extracted to standalone rule (agent-routing.md) with dispatch routing table + decision routing table. (8) Implement skill enhanced: single-story dispatch triggers, migration serialization constraint, full worktree constraints inlined in spawn context. (9) context-fundamentals skill updated with measured post-E-112 actuals. Zero information loss -- all content preserved in scoped delivery mechanisms. Total ambient context reduction: ~980 → ~560-870 lines (universal rules + CLAUDE.md baseline, with 0-400 triggered rules loaded only when relevant files are touched).
