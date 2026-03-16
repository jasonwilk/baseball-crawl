---
paths:
  - ".project/ideas/**"
  - ".project/templates/idea-template.md"
  - "epics/**"
---

# Ideas Workflow Rules

## Ideas vs. Epics

Ideas and epics serve different purposes. Do not conflate them.

| | Idea | Epic |
|---|---|---|
| **Purpose** | Capture a direction or problem worth remembering | Define executable work with stories and acceptance criteria |
| **Structure** | Lightweight: summary, why, timing, blockers, questions | Full spec: goals, non-goals, stories, success criteria |
| **Granularity** | Vague is fine -- "we should probably do X someday" | Specific enough for agents to execute without clarification |
| **Assignees** | Never | Stories have assignees |
| **Status** | CANDIDATE / PROMOTED / DEFERRED / DISCARDED | DRAFT / ACTIVE / BLOCKED / COMPLETED / ABANDONED |

## When to Create an Idea vs. an Epic

**Create an IDEA when:**
- The concept has unresolved dependencies or blockers
- We do not yet know enough to write stories with real acceptance criteria
- The timing is "later" or "when we feel the pain"
- It came up in conversation and we want to capture it before it is forgotten
- A research spike would be needed before we could even scope the work

**Create an EPIC when:**
- The work is unblocked and ready to be structured into stories
- We can write concrete acceptance criteria right now
- It is the next (or near-next) priority

**Rule of thumb:** If you cannot write at least two stories with testable acceptance criteria, it is an idea, not an epic.

## Adding Ideas

- Anyone (user or any agent) can propose an idea
- The **product-manager** agent is responsible for writing the idea file using the template at `/.project/templates/idea-template.md`
- Name: `IDEA-NNN-short-slug.md` (sequential, never reused)
- Add a row to the index in `/.project/ideas/README.md`
- Ideas start as `CANDIDATE`

## Promotion Criteria

An idea gets promoted to an epic when ALL of the following are true:

1. **At least one trigger fires:**
   - A blocking dependency clears (e.g., a prerequisite epic completes)
   - We hit the pain the idea was meant to solve (real friction, not hypothetical)
   - A strategic decision makes it the next priority

2. **We can write stories:** The idea is understood well enough to define at least two stories with testable acceptance criteria. If not, write a research spike first.

3. **It passes the "next" test:** We would actually start working on it in the near term, not just "someday."

**When promoting:**
- Change the idea's status to `PROMOTED`
- Add a note in the idea file linking to the new epic (e.g., "Promoted to E-005")
- Update the index in `/.project/ideas/README.md`
- The epic should reference the original idea in its Background & Context section

## Review Cadence

- **Every 90 days**, or **when completing an epic** -- whichever comes first
- During review, ask:
  - Is any CANDIDATE now unblocked?
  - Should any CANDIDATE be promoted or discarded?
  - Have we solved any idea implicitly through other work?
  - Are there new ideas that should be captured?
- Update `Last reviewed` and `Review by` dates in each idea file reviewed

## DEFERRED and DISCARDED Ideas

- **DEFERRED**: Set aside deliberately. MUST include a reason and a re-review date. Still appears in index.
- **DISCARDED**: Decided against. MUST include a reason so the idea is not re-proposed. Still appears in index (prevents rediscovery loops).

## Cross-Referencing

- When creating a new epic, check `/.project/ideas/README.md` for related CANDIDATE ideas that could be promoted or absorbed
- When completing an epic, review the ideas backlog for newly unblocked candidates
- Ideas may reference each other in their Notes section if they are related
