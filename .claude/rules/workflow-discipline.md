# Workflow Discipline

## Epic READY Gate

An epic MUST have status `READY` or `ACTIVE` before any of its stories can be dispatched. A `DRAFT` epic is not dispatchable. The product-manager (PM) sets `READY` after refinement is complete.

## Dispatch Authorization Gate

Marking an epic READY and dispatching it are separate actions. After the PM sets an epic to READY, the PM MUST present the epic to the user and wait for explicit dispatch authorization. Planning and dispatch MUST NOT chain automatically. Phrases like "define the epic," "create the epic," "plan the epic," and "write stories for X" are plan-mode requests -- they do NOT authorize dispatch. Compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch," "create the epic and start it") authorize both planning and dispatch in sequence.

## Consultation Compliance Gate

When the user explicitly requests that PM collaborate with a specific agent during epic formation (e.g., "work with SE on this," "consult data-engineer before writing stories"), the PM MUST invoke that agent via Task tool and incorporate their input before writing stories. If the PM cannot spawn the requested agent (spawning is one-level-deep -- a platform constraint), the PM MUST escalate to the user with specific questions for the named agent. The PM MUST NOT substitute its own judgment for the requested expert's input. The PM MUST NOT skip the consultation because spawning is unavailable. The PM MUST NOT set the epic to READY until the requested consultation is complete.

This gate applies to explicit user directives only -- not to the domain-triggered consultations in the PM's Consultation Triggers table, which are advisory.

This gate exists in workflow-discipline.md (loaded for all agents) in addition to the PM agent definition (loaded only for PM), so the main session can also flag violations. This is intentional defense-in-depth.

**Cross-reference**: `.claude/rules/agent-team-compliance.md` extends the consultation compliance concept beyond PM epic formation to all agents and all interaction types. This gate governs PM behavior during epic formation specifically; the agent-team-compliance rules govern the main session and all agents during ad-hoc team requests and consultation directives. Both files are loaded on every interaction (`paths: "**"`).

## Work Authorization Gate

Implementing agents MUST NOT begin any implementation work without a referenced story file in the task prompt. The story file must have `Status: TODO` or `Status: IN_PROGRESS`. If no story reference is found, refuse the task.

**Post-review remediation exception**: When a code review (whether an "and review" chain on an ACTIVE epic with all stories DONE, or a standalone post-dev review) identifies findings for remediation, the review session's authority substitutes for a story reference. This exception authorizes remediation ONLY for findings explicitly routed by the main session from a specific review's output. Implementers cannot self-authorize remediation by citing this exception -- the main session must route each finding explicitly.

## Consultation Mode Constraint

An agent is in consultation mode when its spawn prompt includes the consultation mode convention phrase defined in the Spawning Convention subsection below. This constraint is activated by the presence of that phrase -- not by the absence of a story reference.

### What Consultation-Mode Agents MUST NOT Do

- **Create, modify, or delete files** in `src/`, `tests/`, `migrations/`, `scripts/`, or `docs/`.
- **Modify epic or story files** (`epics/**`, `.project/archive/**`).
- **Run implementation-verification commands** (`pytest`, `docker compose`).

Note: `.claude/` paths are intentionally excluded from this prohibition because consultation-mode agents may write to their own agent memory (`.claude/agent-memory/<agent-name>/`).

If a consultation-mode agent identifies implementable work, it MUST report the recommendation to the spawner via SendMessage rather than implementing it.

### What Consultation-Mode Agents MAY Do

- **Read any file** in the repository.
- **Write to own agent memory** (`.claude/agent-memory/<agent-name>/`).
- **Produce recommendations** via SendMessage to the spawner.
- **Create files in `.project/research/`** when explicitly asked by the spawner.

### How the Two Authorization Gates Complement Each Other

- **Work Authorization Gate**: Covers dispatch. Requires a story reference. Structural (opt-out -- all implementing agents are bound unless they have a story).
- **Consultation Mode Constraint**: Covers advisory spawns. Triggered by mode declaration. Structural (opt-in by spawner, mandatory compliance by agent).

The two gates are mutually exclusive by spawn type: a dispatch spawn includes a story reference without the consultation mode phrase; a consultation spawn includes the consultation mode phrase without a story reference. If both are present in a spawn prompt, the Consultation Mode Constraint takes precedence (more restrictive).

### Spawning Convention

Consultation spawn prompts MUST include the following phrase:

> **Consultation mode: do not create or modify implementation files or planning artifacts**

This phrase is the sole trigger that activates the Consultation Mode Constraint. Semantically equivalent phrasing (e.g., "advisory only," "read-only consultation," "don't write code") does NOT activate it -- the exact phrase above is required.

**When to declare consultation mode:**

- **SHOULD declare** when spawning implementing-type agents (software-engineer, data-engineer, docs-writer) for advisory input during planning or formation.
- **NOT declared** when spawning agents in their primary capacity: PM for planning, api-scout for exploration, baseball-coach for domain consultation, claude-architect for context-layer work. These agents produce artifacts (epics, endpoint docs, domain requirements, context-layer files) as part of their normal function -- consultation mode would conflict with legitimate output.

## Workflow Routing Rule

Work-initiation requests follow two phases: **planning** (`user -> PM`) and **dispatch** (`user/main session -> implementing agent`). PM plans epics and refines stories. When the user authorizes dispatch, the main session creates the dispatch team and spawns implementers, code-reviewer, and PM. The main session is the spawner and router -- it assigns stories, routes completion reports, manages merge-back and cascade, and escalates to the user. PM is spawned as a teammate during dispatch for status management (story/epic status transitions) and AC verification ("did they build what was specified"). The code-reviewer is the quality gate for code stories. Both PM and code-reviewer must approve before merge-back (PM is authoritative on ACs -- see the implement skill for disagreement resolution). The main session **MUST NOT** create, modify, or delete any file, or verify acceptance criteria. The main session's only direct file operations are git commands (`git merge`, `git mv`, `git add`, `git commit`) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`). All other file operations are dispatched to the appropriate agent. See `/.claude/rules/dispatch-pattern.md` for an overview and `/.claude/skills/implement/SKILL.md` for full dispatch procedures.

## PM Task Types

The PM operates in six modes: **discover**, **plan**, **clarify**, **triage**, **close**, and **curate**.

## Direct-Routing Exceptions

These agents may be invoked directly without PM intermediation:

- **api-scout**: Exploratory API work, endpoint discovery, credential management.
- **baseball-coach**: Domain consultation, coaching requirements, stat validation.
- **claude-architect**: Agent infrastructure, CLAUDE.md edits, rules, skills.

## Documentation Assessment Gate

Epic completion requires a documentation impact assessment per `.claude/rules/documentation.md`. The main session MUST review the epic's scope against documentation update triggers after all stories are DONE and before archiving the epic. If any trigger fires, docs-writer is dispatched before the epic can be archived.

## Context-Layer Assessment Gate

Epic completion requires a context-layer impact assessment per `.claude/rules/context-layer-assessment.md`. The main session MUST evaluate all six triggers with explicit per-trigger yes/no verdicts after all stories are DONE and before archiving the epic. All verdicts are recorded in the epic's History section. If any trigger fires, claude-architect is dispatched to codify the findings before the epic can be archived.

## Dispatch Failure Protocol

When dispatch fails (Agent tool unavailable, team creation fails, no eligible stories), the main session must follow this protocol:

1. **Report the failure to the user** with the specific reason.
2. **Ask the user how to proceed.** The user decides the next step.
3. **Never improvise a workaround** -- do not dispatch directly, do not ask PM to implement, do not attempt a different routing path. This is an escalation, not a retry.
