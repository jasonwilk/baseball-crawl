# Linear-First Workflow Migration Plan

> Preliminary draft for review.
>
> This document is not an approved workflow, implementation directive, or durable
> process record yet. It is a review draft intended for Claude and other reviewers
> to critique before any final repo documentation or operating instructions are
> adopted.

## Purpose

This plan proposes moving planning, decision capture, and implementation tracking
into Linear as the primary operational system, while reserving repository
documentation for durable architecture, product, API, security, and process
knowledge.

The intent is to make Linear the day-to-day audit trail without turning repo
docs into a dumping ground for one-off planning notes.

## Core Rule

Linear is the planning audit trail.

Repository documentation is updated only when a decision has lasting value beyond
the current project, implementation task, or short-lived coordination thread.

## Operating Model

Linear should become the source of truth for active work:

- Project plans
- Implementation tasks
- Decision history
- Blockers
- Acceptance criteria
- Review status
- Follow-up work

Repository documentation should remain the durable reference layer:

- Architecture decisions
- Public or internal API contracts
- Security-sensitive process
- Product behavior that outlives a ticket
- Recurring engineering workflow

Agents should record decisions in Linear first. If the decision is temporary or
project-scoped, it stays in Linear. If it has durable value, the agent creates a
follow-up documentation task or updates the appropriate repository document as
part of approved scope.

## Recommended Linear Structure

Use this hierarchy:

- Initiative: broad migration or operating-system change
- Project: bounded workflow migration, feature area, or process rollout
- Issue: concrete implementation or planning unit
- Sub-issue: scoped execution step
- Comment or description updates: decision log, tradeoffs, and handoff notes

Each issue should contain:

- Purpose
- Current status
- Acceptance criteria
- Decision notes
- Links to related pull requests or documents
- Follow-up documentation requirement, when applicable

## Decision Handling

Every material decision should be captured in Linear with:

- Decision
- Rationale
- Alternatives considered
- Scope
- Whether repository documentation needs updating

Use this durable decision test:

> Would a future agent or engineer need this after the Linear project is closed?

If yes, create or update durable documentation. If no, keep the decision in
Linear.

## Agent Workflow

Planning agents should:

- Create or update the relevant Linear issue or project.
- Capture decisions in the issue.
- Mark any durable documentation follow-ups.
- Avoid changing repo docs until the plan or scope is approved.

Implementation agents should:

- Read the Linear issue before touching code.
- Confirm acceptance criteria.
- Implement the smallest complete change.
- Update Linear with outcome, tradeoffs, and remaining risks.
- Update repo docs only when required by the durable decision rule.

Review agents should:

- Review against the Linear acceptance criteria.
- Check whether durable decisions were documented appropriately.
- Flag missing documentation follow-ups when needed.
- Avoid expanding scope unless the issue explicitly allows it.

## Documentation Policy

Do not create repo docs for:

- One-off planning choices
- Temporary migration mechanics
- Short-lived coordination notes
- Issue-specific status updates
- Decisions whose usefulness ends with the project

Create or update repo docs for:

- Architecture boundaries
- Recurring workflow rules
- API behavior
- Security process
- Deployment or release process
- Data model decisions
- Durable operational runbooks

## Rollout Plan

### Phase 1: Define the Linear Workflow

- Create the main migration project.
- Define issue templates or conventions.
- Add decision-log expectations.
- Define status rules and ownership.

### Phase 2: Pilot on One Active Project

- Run one real project entirely through Linear.
- Keep repo docs unchanged unless durable updates are clearly needed.
- Track friction points.

### Phase 3: Standardize

- Convert pilot learnings into a lightweight workflow document.
- Add repo documentation only after approval.
- Define examples of Linear-only decisions versus repo-doc-worthy decisions.

### Phase 4: Enforce Through Agent Instructions

- Update agent operating guidance.
- Require Linear-first decision capture.
- Require durable documentation follow-up detection.
- Require implementation agents to check Linear before coding.

## Approval Checkpoints

Before this draft becomes an approved workflow, reviewers should approve:

- Linear hierarchy and naming conventions
- Decision-log format
- Durable documentation rule
- Agent workflow expectations
- Whether this file should become permanent repository documentation

## Open Review Questions

- Should the Linear hierarchy use initiatives, projects, and issues exactly as
  described here, or should any level be collapsed?
- Should decision logs live primarily in issue descriptions, comments, or a
  standardized custom field?
- What criteria should require immediate repo documentation versus a follow-up
  documentation task?
- Should implementation agents be allowed to update docs in the same change, or
  should documentation changes always be separate unless explicitly scoped?
