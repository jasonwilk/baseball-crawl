# E-140: Planning Skill

## Status
`READY`

## Overview
Formalize Jason's planning workflow (plan → spec review → triage → refine → READY) as a skill at `.claude/skills/plan/SKILL.md`. Today the 5-step planning process is entirely ad-hoc -- Jason manually spawns teams, invokes spec review, triages findings, refines, and sets READY across multiple separate interactions. This skill codifies those steps into a repeatable, enforceable workflow that the main session loads on planning triggers.

## Background & Context
Analysis across 137+ epics reveals Jason follows a consistent planning pattern:

1. **Plan with relevant team members** -- spawn a team (PM + domain experts), discuss requirements, PM writes epic/stories
2. **Codex spec review** -- run headless or generate prompt, get findings
3. **Triage findings** -- fix valid findings, dismiss only false positives
4. **Refine with team** -- continue or respawn team, incorporate codex findings, tighten ACs
5. **Mark READY** -- PM sets status after refinement is complete

This cycle sometimes repeats (spec review → triage → refine → spec review again) for complex epics.

**Gaps in current workflow:**
- No standard team composition guidance for planning (dispatch has the Dispatch Team section and routing table; planning has nothing)
- No "refinement" phase in any skill -- the phase where PM incorporates findings and tightens ACs is entirely ad-hoc
- No checkpoint between "findings triaged" and "refinement complete" -- the post-incorporation consistency sweep exists on paper but has no procedural enforcement
- The unified team lifecycle (consult → refine → dispatch in one team) is a validated user preference but no skill implements it
- No automation for the spec review → triage → refine loop

**What already exists:**
- `codex-spec-review` skill handles the spec review step (headless and prompt-gen paths)
- PM agent definition contains the quality checklist, consultation triggers, and post-incorporation consistency sweep
- `implement` skill handles dispatch (Phase 1 onward)
- `workflow-discipline.md` contains the READY gate and dispatch authorization gate
- `agent-routing.md` contains the routing table for dispatch team composition

Expert consultation: claude-architect (context-layer skill architecture -- CA assessed skill boundaries, phase design, and implement skill handoff mechanics during the E-planning-workflow team session). PM provided workflow analysis across 137+ epics. Both contributions are reflected in the Technical Notes.

## Goals
- The main session loads the plan skill on planning triggers and follows its phases
- Team composition is suggested based on the user's domain description, not manual recall
- Spec review is automatically chained after PM completes the DRAFT epic
- Post-refinement consistency sweep is procedurally enforced, not optional
- The spec review → triage → refine loop is codified with clear entry/exit conditions
- "Plan and dispatch" compound trigger chains into the implement skill after READY
- The dispatch authorization gate is preserved -- planning stops at READY unless the user explicitly authorizes dispatch

## Non-Goals
- Automating expert consultation content (experts think, PM packages -- the skill orchestrates the process, not the substance)
- Consolidating scattered rules into the skill file (rules stay where they are; skill references them)
- Modifying the codex-spec-review skill (it works as-is; the plan skill chains it)
- Modifying the implement skill's core dispatch phases (E-140-05 adds a handoff trigger, not new dispatch logic)
- Replacing PM judgment with automation (the skill provides structure, not decisions)

## Success Criteria
- Jason can say "plan an epic for X" and get a structured planning session with suggested team composition
- Codex spec review runs automatically after PM completes DRAFT stories (no manual "spec review E-NNN" needed)
- Post-refinement consistency sweep catches value drift across story files
- "Plan and dispatch E-NNN" produces a READY epic and seamlessly chains into dispatch
- The planning workflow completes in fewer manual interactions than today's ad-hoc process

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-140-01 | Core plan skill file | TODO | None | claude-architect |
| E-140-02 | Team composition logic | TODO | E-140-01 | claude-architect |
| E-140-03 | Spec review integration | TODO | E-140-02 | claude-architect |
| E-140-04 | Consistency sweep automation | TODO | E-140-03 | claude-architect |
| E-140-05 | Implement skill handoff | TODO | E-140-04 | claude-architect |
| E-140-06 | PM agent definition updates | TODO | E-140-05 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Skill Structure Convention
The plan skill follows the same structural conventions as the implement skill:
- Activation Triggers section with trigger phrases
- Purpose section explaining what the skill does
- Prerequisites section with pre-checks
- Numbered Phases with Steps
- Workflow Summary (ASCII flowchart)
- Edge Cases section
- Anti-Patterns section

Reference: `.claude/skills/implement/SKILL.md` for the canonical skill structure.

### TN-2: Phase Architecture
Six phases, each with clear entry/exit conditions:

**Phase 0: Team Formation**
- Main session parses user request for domain signals
- Suggests team composition based on domain (see TN-3)
- User confirms or adjusts
- Creates team, spawns PM + domain experts
- Implementing-type domain experts (software-engineer, data-engineer, docs-writer) are spawned in consultation mode (per `workflow-discipline.md` Consultation Mode Constraint)
- Primary-capacity agents (api-scout, baseball-coach, claude-architect) are spawned WITHOUT consultation mode -- they produce artifacts as their normal function (per `workflow-discipline.md` "When to declare consultation mode" guidance)
- PM is spawned without consultation mode (PM produces artifacts as its normal function)

**Phase 1: Discovery**
- PM operates in discover mode
- Consults domain experts on the team for requirements
- Produces problem statement, constraints, open questions
- May produce an idea file if scope is too unclear for an epic

**Phase 2: Planning**
- PM operates in plan mode
- Writes DRAFT epic and stories with expert input
- Runs quality checklist (from PM agent definition)
- Epic remains DRAFT at end of this phase

**Phase 3: Spec Review**
- Automatically runs the codex-spec-review script (headless path, per TN-7)
- If clean: proceed to Phase 5 (READY)
- If findings: present to user, PM triages with domain experts on the team
- Each finding gets a disposition: ACCEPT (fix it) or DISMISS (false positive only)
- Accepted findings route to PM for incorporation

**Phase 4: Refinement**
- PM incorporates accepted findings into epic/stories
- Runs post-incorporation consistency sweep (see TN-5)
- User decides whether to re-run spec review (loop to Phase 3) or proceed
- If re-running: Phase 3 executes again with the refined artifacts

**Phase 5: READY Gate**
- PM sets epic status to READY
- Presents epic summary to user
- **STOP** -- dispatch requires separate authorization
- Exception: if the user used "plan and dispatch" compound trigger, chain into implement skill (see TN-6)

### TN-3: Team Composition Suggestions
The skill suggests a planning team based on domain signals in the user's request. These are suggestions, not mandates -- the user confirms or adjusts.

| Domain Signal | Keywords / Patterns | Suggested Team |
|--------------|-------------------|----------------|
| Database / schema / ETL / migration | "schema", "migration", "ETL", "database", "table", "column" | PM + data-engineer |
| Dashboard / UI / display | "dashboard", "page", "column", "display", "UI", "template" | PM + software-engineer + baseball-coach |
| API / endpoints / crawling | "API", "endpoint", "crawl", "fetch", "GameChanger" | PM + api-scout |
| Agent infra / rules / skills | "agent", "rule", "skill", "hook", "CLAUDE.md", "context layer" | PM + claude-architect |
| Coaching / stats / scouting | "coach", "stat", "scouting", "lineup", "report" | PM + baseball-coach |
| Security / auth / credentials | "auth", "credential", "security", "token", "login" | PM + software-engineer |
| Multi-domain or unclear | No clear single domain | PM + ask user which experts to include |

When the user explicitly names agents in their request (e.g., "plan this with SE and DE"), those names override the suggestion table. If the user names 2+ agents, this is a Pattern 1 (Explicit Team Request) per `agent-team-compliance.md` -- use TeamCreate. If the user names a single agent, this is a Pattern 2 (Explicit Consultation Directive) -- spawn that agent.

### TN-4: Activation Triggers
Planning triggers (load this skill):
- "plan E-NNN", "plan an epic for X", "plan epic for X"
- "create an epic for X", "write stories for X"
- "let's plan X", "design an epic for X"
- Any request that implies creating a new epic with stories

Compound triggers (plan then dispatch):
- "plan and dispatch X", "plan and execute X"
- "create an epic and start it", "define and execute X"
- "plan and implement X"

Non-triggers (do NOT load this skill):
- "spec review E-NNN" → codex-spec-review skill
- "implement E-NNN" / "start E-NNN" / "dispatch E-NNN" → implement skill
- "clarify E-NNN" / "refine E-NNN" → PM clarify mode (no skill needed)
- "triage" → PM triage mode (no skill needed)

### TN-5: Post-Incorporation Consistency Sweep
After PM incorporates spec review findings, the skill enforces a consistency sweep:

1. PM lists every value changed during incorporation (counts, env var names, field names, file paths, status categories)
2. PM greps the epic directory for each changed value to find all occurrences
3. PM verifies the new value is consistent everywhere it appears -- epic file, all story files, Technical Notes
4. If a fix in one file requires a corresponding update in another, PM applies both before proceeding

This sweep already exists in the PM quality checklist but is manual and skippable. The skill makes it a required gate before proceeding to Phase 5 or looping to Phase 3.

### TN-6: Implement Skill Handoff
When the user uses a compound trigger ("plan and dispatch"), the plan skill chains into the implement skill after Phase 5:

1. Plan skill completes Phase 5 (epic is READY)
2. Plan skill signals that dispatch is authorized (compound trigger serves as dispatch authorization)
3. Main session loads the implement skill
4. Implement skill begins at its Prerequisites check (epic exists, status is READY)
5. The planning team is already active -- implement skill reuses agents where possible

The unified team lifecycle means agents who consulted during planning already have context when they implement. The main session does NOT tear down the planning team before creating a dispatch team -- it transitions the existing team.

Team transition mechanics:
- PM stays (already on the team, transitions from planning role to dispatch role)
- Domain experts who are also implementers (e.g., SE consulted during planning, SE implements during dispatch) stay and transition from consultation mode to implementation mode
- Domain experts who are NOT implementers (e.g., baseball-coach consulted but doesn't implement) can be shut down or kept for advisory
- Code-reviewer is spawned fresh (not needed during planning)
- New implementer types not on the planning team are spawned as needed

### TN-7: Spec Review Invocation
The skill invokes codex-spec-review headless path by running the script directly:

```
timeout 600 ./scripts/codex-spec-review.sh <epic-dir>
```

This is the same invocation the codex-spec-review skill uses. The plan skill does NOT load the codex-spec-review skill -- it runs the underlying script to avoid skill-nesting complexity. The plan skill handles the output parsing and triage routing itself.

### TN-8: Circuit Breaker
The spec review → refine loop has a circuit breaker: maximum 3 iterations. If the 3rd spec review still has findings, the skill presents the remaining findings to the user and asks how to proceed:
- (a) Fix remaining findings and mark READY anyway
- (b) Continue refining (resets circuit breaker)
- (c) Leave as DRAFT and stop

### TN-9: Boundaries
- The skill owns the process (phases, gates, transitions)
- The PM agent definition owns PM capabilities (quality checklist, consultation triggers, anti-patterns)
- Scattered rules stay where they are (`workflow-discipline.md`, `agent-routing.md`, `agent-team-compliance.md`) -- the skill references them, does not duplicate them
- The skill does NOT modify the codex-spec-review skill or the implement skill's core phases

## Open Questions
None -- all design decisions resolved during team consultation.

## History
- 2026-03-19: Created by PM during E-planning-workflow team session. Based on analysis of Jason's actual planning workflow across 137+ epics and CA's architectural assessment.
- 2026-03-19: Codex spec review returned 7 findings (4 P1, 3 P2). All fixed: (1) serialized stories 01→02→03→04→05→06 to eliminate shared-file conflicts on SKILL.md, (2) narrowed consultation mode to implementing-type agents only per workflow-discipline.md, (3) expanded E-140-05 AC-3 to cover all implement skill sections assuming fresh team, (4) recorded actual CA consultation in Background, (5) replaced vague "same scope" prerequisite with user escalation path, (6) added AC-5 to E-140-06 for reconciling PM's "Optional: Codex Spec Review" section, (7) corrected agent-team-compliance pattern reference from Pattern 2 to Pattern 1+2.
- 2026-03-19: PM holistic review found 3 additional issues, all fixed: TN-2/TN-7 contradiction (skill vs script), stale Files comment in E-140-05, missing Handoff Context in stories 02/04/05. CA holistic review returned clean (2 minor informational items, no changes needed). Status set to READY.
