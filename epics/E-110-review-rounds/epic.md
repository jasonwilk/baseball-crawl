# E-110: Iterative Review Rounds Convention

## Status
`DRAFT`

## Overview
Codify the iterative review/refinement rounds pattern into a documented skill so the main session has a clear procedural reference when the user requests multi-round quality loops (e.g., "3 rounds of refinement" or "review with 2 rounds"). The pattern wraps existing skills (codex-spec-review, codex-review) and the code-reviewer agent -- it does not replace them.

## Background & Context
The user has been running an effective but undocumented iterative pattern: run a review, triage findings with a team, apply fixes, respawn agents with fresh context windows, and repeat for N rounds. This pattern has two variants -- refinement rounds (pre-dispatch, on spec/planning artifacts) and review rounds (post-implementation, on finished code). Both share the same core loop structure but differ in which review tool runs and who triages. Without documentation, the main session has no reference for orchestrating this loop correctly, and new conversations must rediscover the pattern each time.

CA consulted (2026-03-15): Recommended a single skill file (`.claude/skills/review-rounds/SKILL.md`) covering both variants, plus a CLAUDE.md Workflows entry. One skill rather than two because the core loop is identical -- only the inner tools and triage participants differ. A rule file was rejected because this is a procedural workflow, not a constraint. CLAUDE.md-only was rejected because the procedural detail exceeds what belongs in always-loaded context.

No expert consultation required beyond CA -- this is a pure process/workflow epic codifying an existing user practice.

## Goals
- Document the iterative review/refinement loop so the main session can follow it without rediscovering the pattern
- Preserve early-exit-on-clean-review as a first-class convention (don't burn rounds when nothing to fix)
- Make the respawn-for-fresh-context step explicit so context drift doesn't accumulate across rounds
- Keep the convention lightweight -- wrap existing skills, don't duplicate or modify them

## Non-Goals
- Modifying the codex-spec-review or codex-review skills (they remain single-run tools)
- Modifying the implement skill or dispatch-pattern.md (review rounds are orthogonal to dispatch)
- Programmatic enforcement of round counts or early exit (this is a convention, not automation)
- Building new review tooling or scripts

## Success Criteria
- A skill file exists that the main session can load when the user requests review rounds
- The skill covers both variants (refinement and review) without duplication
- CLAUDE.md Workflows section has a trigger entry for review rounds
- Existing skills and rules are not modified

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-110-01 | Review Rounds Skill File | TODO | None | - |
| E-110-02 | CLAUDE.md Workflows Entry | TODO | E-110-01 | - |

## Dispatch Team
- claude-architect

## Technical Notes
- **Single skill, two sections**: The skill file has a shared Core Loop section and two variant sections (Refinement Rounds and Review Rounds). The core loop covers round counting, early exit on clean review, and respawn mechanics. Each variant section specifies which inner tools run and who triages.
- **Wrapping, not modifying**: The skill references codex-spec-review, codex-review, and the code-reviewer agent by name but does not modify their files. It is a wrapper convention.
- **Main session orchestrates**: The main session is the persistent agent across rounds (it doesn't get respawned). It tracks round count, invokes inner skills, spawns/respawns triage teams, and checks the early-exit condition.
- **Respawn mechanics**: Between rounds, agents are shut down and respawned with fresh context windows. This prevents context drift from accumulated edits and findings. The main session carries the round state.
- **Trigger phrase patterns**: "N rounds of refinement", "refine N times", "review with N rounds", "N rounds of review", and similar variations. The skill should detect the round count from the phrase. If no count is provided, the main session asks the user.
- **Discriminator**: The round count in the trigger phrase ("N rounds of...") is the mode discriminator between review-rounds and the single-run review skills (codex-spec-review, codex-review). Without a round count or the word "rounds", the single-run skills apply. This mirrors how codex-spec-review uses the word "spec" as its discriminator.
- **Implement skill boundary**: The implement skill's Phase 4 "and review" modifier chains a single post-implementation code review. Review-rounds is a standalone workflow invoked independently -- it is not a modifier on implement's "and review" chain, and the two should not be conflated.

## Open Questions
- None

## History
- 2026-03-15: Created. CA consulted on artifact placement -- recommended single skill + CLAUDE.md entry.
- 2026-03-15: Codex spec review round 1. 5 findings (2×P1, 1×P2, 2×P3). 3 refined: AC-6 early-exit boundary clarified (per-step -- if first review is clean, skip remaining steps and exit; PM+CA consensus after initial disagreement resolved in favor of per-step), AC-9 anti-pattern narrowed ("alone" qualifier added), AC-4 format criterion aligned to actual Workflows entry format. 2 dismissed: DoD convention check (P3, standard guidance for CA), DoD regression check (P3, verified by diff).
- 2026-03-15: PM+CA team refinement pass. 4 refinements applied: (1) AC-2 extended -- missing round count triggers user prompt instead of guessing, (2) AC-5 clarified -- review rounds variant requires main session to spawn implementer for round 1, (3) AC-6 sharpened -- "clean" defined as zero findings of any severity (no MUST FIX/SHOULD FIX for code-reviewer, "no findings" for Codex), (4) discriminator note added to Technical Notes -- round count distinguishes review-rounds from single-run skills.
- 2026-03-15: Codex spec review round 2. 2 findings (1×P1, 1×P2). 1 refined: E-110-02 AC-4 corrected "bold trigger phrase" to "bold workflow label" to match actual CLAUDE.md Workflows format. 1 dismissed: E-110-01 AC-5 review input contract (P1) -- the skill wraps existing tools by reference; input contracts are defined in each tool's own file, and duplicating them would create maintenance coupling. AC-5 already specifies what the section must cover (inner tools, participants, review target); how to invoke each tool is the architect's domain.
- 2026-03-15: Final refinement pass. 2 changes: (1) Added closing synthesis step -- AC-3 step (7) + new AC-10 requiring the main session to present a synthesis to the user after all rounds complete (summarize refinements, flag unresolved items, confirm before proceeding). The main session is the only agent that persists across rounds and has the full picture. (2) Added implement skill boundary clarification to Technical Notes -- review-rounds is a standalone workflow, not a modifier on implement's Phase 4 "and review" chain.
