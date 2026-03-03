---
paths:
  - "epics/**"
  - ".project/**"
---

# Project Management Rules

## Epics and Stories

- Epic and story files MUST follow the templates in `/.project/templates/`
- NEVER skip template sections -- every section must be filled in or explicitly marked N/A with a reason
- Acceptance criteria MUST be testable -- no vague language like "works well" or "is fast"
- Use Given/When/Then format for acceptance criteria when describing behavior
- Use checklist format for acceptance criteria when describing deliverables
- Every story MUST list the files it will create or modify
- Stories that touch the same files MUST have explicit dependency ordering
- NEVER delete an epic directory -- archive it to `/.project/archive/`
- COMPLETED or ABANDONED epics MUST be archived (moved from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`) before the next commit -- archiving is immediate, not deferred
- NEVER reuse an epic or story number
- Keep the story table in `epic.md` in sync with individual story file statuses
- Update the PM memory file (`/.claude/agent-memory/product-manager/MEMORY.md`) when creating or closing epics

## Ideas Workflow

Ideas are directions or problems worth tracking that are NOT yet ready to be structured as epics. They live in `/.project/ideas/`.

**Capture as an idea (not an epic) when:**
- Scope is vague or acceptance criteria cannot yet be written
- A dependency must clear before real planning is possible
- The pain has not been felt yet

**Promote an idea to an epic when:**
- A blocking dependency clears
- The project hits the pain the idea was meant to solve
- The user makes it a strategic priority

**Review ideas:**
- Every time an epic completes or is abandoned -- check `/.project/ideas/README.md`
- Every 90 days (each idea file contains a "Review by" date)
- Ask: Is any CANDIDATE now unblocked? Should it be promoted, deferred, or discarded?

**Adding an idea:**
1. Copy `/.project/templates/idea-template.md`
2. Name it `IDEA-NNN-short-slug.md` (next sequential number, never reused)
3. Fill in all sections
4. Add a row to `/.project/ideas/README.md`
5. Update the next available idea number in `/.claude/agent-memory/product-manager/MEMORY.md`

**Ideas do NOT have stories, acceptance criteria, or assignees.** Keep them lightweight. If you find yourself writing acceptance criteria for an idea, stop -- you are writing an epic.
