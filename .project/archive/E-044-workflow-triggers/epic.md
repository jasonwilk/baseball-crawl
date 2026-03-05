# E-044: Workflow Trigger Phrases

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add three trigger-phrase workflows to the agent ecosystem so the team lead automatically recognizes "spec review", "implement", and "review epic" commands and routes them through the correct multi-agent coordination pattern. Each workflow is modeled after the existing ingest-endpoint skill: a CLAUDE.md Workflows entry for detection, plus a skill file with the full procedure.

## Background & Context
Today the team lead does not have pre-wired workflows for common multi-agent coordination patterns. The user must manually explain who to spawn and what to do each time. The ingest-endpoint skill proved this pattern works well: CLAUDE.md lists the trigger phrase, the skill file defines the multi-phase workflow, and the team lead follows it without guessing.

Three workflows are needed:
1. **Spec review** -- run codex spec review on an epic, then have domain experts and PM review findings together.
2. **Post-dev epic review** -- after implementation, run codex code review, then have the implementing team review findings.
3. **Implement** -- dispatch an epic using team composition metadata defined in the epic itself.

Expert consultation: No separate consultation required. This is context-layer work implemented by claude-architect, and the design follows established patterns (ingest-endpoint skill, dispatch-pattern.md, CLAUDE.md Workflows) that claude-architect built. Design decisions documented in Technical Notes below.

## Goals
- Team lead recognizes "spec review E-NNN" and executes a structured spec review workflow
- Team lead recognizes "review epic E-NNN" and executes a post-dev code review workflow
- Team lead recognizes "implement E-NNN" and dispatches the epic using team composition from the epic file
- "implement E-NNN and review" chains implementation with post-dev review
- Epic template includes a Dispatch Team section so epics define their own team composition

## Non-Goals
- Changing how codex-review.sh or codex-spec-review.sh scripts work (they are fine as-is)
- Modifying agent definitions beyond what is needed for workflow recognition
- Automating codex finding resolution (humans decide what to fix/dismiss/defer)
- Changing the PM's dispatch coordination role (PM still owns status management)

## Success Criteria
- A user saying "spec review E-042" triggers the spec-review skill without additional explanation
- A user saying "review epic E-042" triggers the post-dev review skill without additional explanation
- A user saying "implement E-042" triggers the implement skill, and PM reads team composition from the epic
- A user saying "implement E-042 and review" chains both implement and review workflows
- All three skills follow the ingest-endpoint structural pattern (CLAUDE.md entry + skill file)
- Epic template includes a Dispatch Team section with clear usage guidance

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-044-01 | Epic template: Dispatch Team section | DONE | None | claude-architect |
| E-044-02 | Spec review workflow skill | DONE | None | claude-architect |
| E-044-03 | Post-dev review workflow skill | DONE | None | claude-architect |
| E-044-04 | Implement workflow skill | DONE | E-044-01 | claude-architect |
| E-044-05 | CLAUDE.md Workflows entries | DONE | E-044-02, E-044-03, E-044-04 | claude-architect |

## Technical Notes

### Design Decisions

**Pattern choice: Skills + CLAUDE.md Workflows entries.** This follows the proven ingest-endpoint model. CLAUDE.md Workflows section is the trigger detection point (team lead reads this automatically). Each trigger maps to a skill file with the full procedure. This is the simplest approach that works.

**Trigger phrases:**
- "spec review" / "spec review E-NNN" -- runs codex spec review, then team reviews findings
- "review epic" / "review epic E-NNN" -- post-dev code review (distinct from "spec review")
- "implement E-NNN" / "implement epic E-NNN" -- dispatch the epic
- "implement E-NNN and review" -- chain implement + review epic

**Team composition in epics:** Add a `## Dispatch Team` section to the epic template between Stories and Technical Notes. Format:

```markdown
## Dispatch Team
<!-- Which agents should be on the dispatch team for this epic? PM is always included automatically. -->
- software-engineer
- data-engineer
```

This is advisory metadata. PM still makes routing decisions per dispatch-pattern.md, but the epic author (usually PM) declares intent at planning time. The implement skill reads this section. If the section is missing or empty, PM falls back to the existing Agent Selection table in dispatch-pattern.md.

**Dispatch-pattern.md update:** Add a paragraph to the "Agent Selection for Dispatch" section explaining that epics may include a Dispatch Team section, and PM should prefer it when present. This does not replace the routing table -- it supplements it.

**Spec review workflow phases:**
1. Team lead runs `./scripts/codex-spec-review.sh` on the target epic directory
2. Team lead spawns PM + relevant domain experts (determined by epic domain -- baseball-coach for coaching epics, data-engineer for schema epics, etc.)
3. Team reviews codex findings together
4. PM updates the epic based on consensus (refine, dismiss, or defer each finding)

**Post-dev review workflow phases:**
1. Team lead runs `./scripts/codex-review.sh uncommitted` (or appropriate mode based on context)
2. Team lead spawns PM + the implementing agents who would work on the epic (read from Dispatch Team section)
3. Team reviews codex findings together
4. Fixes applied or findings documented

**Implement workflow phases:**
1. Team lead reads the epic's Dispatch Team section
2. Team lead spawns PM with the dispatch request
3. PM coordinates as usual per dispatch-pattern.md
4. If "and review" modifier is present, PM chains into the review epic workflow after all stories are DONE (before the closure sequence)

### File Paths

**Skills to create:**
- `.claude/skills/spec-review/SKILL.md`
- `.claude/skills/review-epic/SKILL.md`
- `.claude/skills/implement/SKILL.md`

**Files to modify:**
- `CLAUDE.md` (Workflows section -- add three entries)
- `.project/templates/epic-template.md` (add Dispatch Team section)
- `.claude/rules/dispatch-pattern.md` (reference Dispatch Team section in Agent Selection)

### Structural Notes

All skill files should follow the ingest-endpoint structure:
1. Activation Triggers (trigger phrases)
2. Purpose (one paragraph)
3. Prerequisites (what must be true before executing)
4. Phases (numbered, with agent assignments)
5. Workflow Summary (ASCII flow diagram)
6. Edge Cases
7. Anti-Patterns

The team lead is the executor of these skills -- it reads the skill file and follows the procedure. Skills do NOT change the team lead's identity or role; they give it a procedure to follow.

## Open Questions
- None remaining after design analysis.

## History
- 2026-03-05: Created. Design decisions based on ingest-endpoint pattern analysis and dispatch-pattern.md review.
- 2026-03-05: Epic set to ACTIVE. Dispatching Group 1 stories (E-044-01, E-044-02, E-044-03) in parallel to claude-architect.
- 2026-03-05: All 5 stories verified DONE. Epic COMPLETED. Three workflow skills created (spec-review, review-epic, implement), epic template updated with Dispatch Team section, dispatch-pattern.md updated, CLAUDE.md Workflows section expanded with three new entries. No documentation impact (context-layer only, no admin/coaching docs affected).
