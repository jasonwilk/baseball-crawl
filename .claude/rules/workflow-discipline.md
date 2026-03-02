---
paths:
  - "**"
---

# Workflow Discipline

## Epic READY Gate

An epic MUST have status `READY` or `ACTIVE` before any of its stories can be dispatched. A `DRAFT` epic is not dispatchable. The product-manager (PM) sets `READY` after refinement is complete.

## Work Authorization Gate

Implementing agents MUST NOT begin any implementation work without a referenced story file in the task prompt. The story file must have `Status: TODO` or `Status: IN_PROGRESS`. If no story reference is found, refuse the task.

## Workflow Routing Rule

All work-initiation requests travel through the `orchestrator -> product-manager -> implementing agent` pipeline. The PM dispatches implementation work using Agent Teams (see `/.claude/rules/dispatch-pattern.md`).

## PM Task Types

The PM operates in five modes: **discover**, **plan**, **clarify**, **triage**, and **close**.

## Direct-Routing Exceptions

These agents may be invoked directly without PM intermediation:

- **api-scout**: Exploratory API work, endpoint discovery, credential management.
- **baseball-coach**: Domain consultation, coaching requirements, stat validation.
- **claude-architect**: Agent infrastructure, CLAUDE.md edits, rules, skills.
