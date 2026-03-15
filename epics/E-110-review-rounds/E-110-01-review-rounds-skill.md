# E-110-01: Review Rounds Skill File

## Epic
[E-110: Iterative Review Rounds Convention](epic.md)

## Status
`TODO`

## Description
After this story is complete, a skill file at `.claude/skills/review-rounds/SKILL.md` will document the iterative review/refinement rounds pattern. The skill covers both variants (refinement rounds for spec artifacts and review rounds for implementation code) in a single file with a shared core loop. The main session loads this skill when the user requests multi-round quality loops and follows its procedural steps.

## Context
The user runs iterative review loops manually -- running a review, triaging findings with a team, applying fixes, respawning agents for fresh context, and repeating. This pattern is effective but undocumented, forcing the main session to rediscover it each conversation. This story creates the authoritative reference.

## Acceptance Criteria
- [ ] **AC-1**: A file exists at `.claude/skills/review-rounds/SKILL.md` containing the full skill definition.
- [ ] **AC-2**: The skill has an Activation Triggers section listing trigger phrases that include a round count (e.g., "N rounds of refinement", "refine N times", "review with N rounds", "N rounds of review"). If the user's phrase does not include a round count (e.g., "review rounds on E-100"), the main session asks the user how many rounds to run before proceeding.
- [ ] **AC-3**: The skill has a Core Loop section documenting the shared loop structure: (1) run review, (2) evaluate findings -- if clean, exit early, (3) triage findings with team, (4) apply fixes, (5) respawn agents with fresh context, (6) repeat until rounds exhausted, (7) present closing synthesis to user.
- [ ] **AC-4**: The skill has a Refinement Rounds section specifying: inner tool is codex-spec-review skill, triage team is PM + domain experts (spawned fresh each round), fix team is PM + experts, review target is epic/story spec files.
- [ ] **AC-5**: The skill has a Review Rounds section specifying: inner tools are code-reviewer agent then codex-review skill (sequential within each round), triage is main session + implementer, fix agent is the implementer, review target is implementation code. The main session spawns an implementer agent (SE, DE, etc. as appropriate for the code under review) for round 1; subsequent rounds respawn per AC-7.
- [ ] **AC-6**: The early-exit rule is explicit: early exit is evaluated after each review step within a round. If a review step comes back clean -- zero findings of any severity (no MUST FIX and no SHOULD FIX for code-reviewer; "no findings" for Codex) -- the loop stops immediately. Remaining review steps in that round and remaining rounds are skipped.
- [ ] **AC-7**: The respawn convention is explicit: between rounds, triage/fix agents are shut down and respawned with fresh context windows. The main session persists across rounds and tracks round state.
- [ ] **AC-8**: The skill explicitly states it wraps existing skills (codex-spec-review, codex-review) and the code-reviewer agent without modifying them. It references them by name/path.
- [ ] **AC-9**: The skill includes an Anti-Patterns section that prohibits: modifying wrapped skills, skipping respawn between rounds, continuing rounds after a clean review, the main session performing review or triage alone without spawning the required participant agents (implementer for review rounds, PM + domain experts for refinement rounds), and carrying findings forward across rounds without resolution (each round's triage must reach terminal state -- FIXED or DISMISSED -- before the next round begins).
- [ ] **AC-10**: The skill has a Closing Synthesis section: after all rounds complete (whether by early exit or round exhaustion), the main session presents a synthesis to the user summarizing refinements applied across all rounds, flagging any items raised but not formally resolved, and asking if the user has concerns before proceeding. The main session is the only agent that persists across all rounds and has the full picture -- this step is its responsibility.
- [ ] **AC-11**: The Refinement Rounds section includes a READY Gate step: after the closing synthesis (AC-10), the main session offers to mark the epic status from DRAFT to READY. If the user confirms, the main session updates the epic file status. If the user declines or raises concerns, the workflow ends without a status change. This step applies only to the refinement rounds variant (not review rounds). The main session performs the status update directly -- PM is not spawned for this mechanical step.

## Technical Approach
The skill file follows the established pattern of other skills in `.claude/skills/` (e.g., codex-spec-review, codex-review). It is a procedural reference document, not executable code. The two variants share a core loop structure documented once, with variant-specific sections for the differing inner tools and participants. The architect should study the existing skill files for format conventions.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-110-02

## Files to Create or Modify
- `.claude/skills/review-rounds/SKILL.md` (create)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-110-02**: The skill file path (`.claude/skills/review-rounds/SKILL.md`) and the activation trigger phrases, which E-110-02 needs to write the CLAUDE.md Workflows entry.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Skill file follows conventions of existing skills in `.claude/skills/`
- [ ] No modifications to existing skill files or rule files

## Notes
- The skill is a convention document -- the main session follows it as a procedural reference, not as programmatic automation.
- CA recommended this structure: single skill with shared core loop + two variant sections.
