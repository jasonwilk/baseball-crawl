# Workflow Discipline

## Epic READY Gate

An epic MUST have status `READY` or `ACTIVE` before any of its stories can be dispatched. A `DRAFT` epic is not dispatchable. The product-manager (PM) sets `READY` after refinement is complete.

## Dispatch Authorization Gate

Marking an epic READY and dispatching it are separate actions. After the PM sets an epic to READY, the PM MUST present the epic to the user and wait for explicit dispatch authorization. Planning and dispatch MUST NOT chain automatically. Phrases like "define the epic," "create the epic," "plan the epic," and "write stories for X" are plan-mode requests -- they do NOT authorize dispatch. Compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch," "create the epic and start it") authorize both planning and dispatch in sequence.

## Consultation Compliance Gate

When the user explicitly requests that PM collaborate with a specific agent during epic formation (e.g., "work with SE on this," "consult data-engineer before writing stories"), the PM MUST invoke that agent via Task tool and incorporate their input before writing stories. If the PM cannot spawn the requested agent (spawning is one-level-deep -- a platform constraint), the PM MUST escalate to the user with specific questions for the named agent. The PM MUST NOT substitute its own judgment for the requested expert's input. The PM MUST NOT skip the consultation because spawning is unavailable. The PM MUST NOT set the epic to READY until the requested consultation is complete.

This gate applies to explicit user directives only -- not to the domain-triggered consultations in the PM's Consultation Triggers table, which are advisory.

This gate exists in workflow-discipline.md (loaded for all agents) in addition to the PM agent definition (loaded only for PM), so the main session can also flag violations. This is intentional defense-in-depth.

## Work Authorization Gate

Implementing agents MUST NOT begin any implementation work without a referenced story file in the task prompt. The story file must have `Status: TODO` or `Status: IN_PROGRESS`. If no story reference is found, refuse the task.

## Workflow Routing Rule

Work-initiation requests follow two phases: **planning** (`user -> PM`) and **dispatch** (`user/main session -> implementing agent`). PM plans epics and refines stories. When the user authorizes dispatch, the main session creates the dispatch team, spawns implementers directly, assigns stories, verifies acceptance criteria, and manages all statuses. PM is not spawned as a teammate during dispatch. See `/.claude/rules/dispatch-pattern.md`.

## PM Task Types

The PM operates in five modes: **discover**, **plan**, **clarify**, **triage**, and **close**.

## Direct-Routing Exceptions

These agents may be invoked directly without PM intermediation:

- **api-scout**: Exploratory API work, endpoint discovery, credential management.
- **baseball-coach**: Domain consultation, coaching requirements, stat validation.
- **claude-architect**: Agent infrastructure, CLAUDE.md edits, rules, skills.

## Documentation Assessment Gate

Epic completion requires a documentation impact assessment per `.claude/rules/documentation.md`. The main session MUST review the epic's scope against documentation update triggers after all stories are DONE and before archiving the epic. If any trigger fires, docs-writer is dispatched before the epic can be archived.

## Dispatch Failure Protocol

When dispatch fails (Agent tool unavailable, team creation fails, no eligible stories), the main session must follow this protocol:

1. **Report the failure to the user** with the specific reason.
2. **Ask the user how to proceed.** The user decides the next step.
3. **Never improvise a workaround** -- do not dispatch directly, do not ask PM to implement, do not attempt a different routing path. This is an escalation, not a retry.
