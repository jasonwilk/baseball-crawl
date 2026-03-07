---
paths:
  - "docs/**"
  - "epics/**"
  - ".project/archive/**"
---

# Documentation Rules

## Directory Structure

- `docs/admin/` -- operator and developer documentation (setup, deployment, troubleshooting)
- `docs/coaching/` -- end-user documentation for coaching staff (how-to guides, reference)
- `docs/` root -- agent-maintained reference files (API specs, architecture docs); these stay in place

## Documentation Ownership

| Docs | Owner |
|------|-------|
| `docs/admin/`, `docs/coaching/` | docs-writer |
| `docs/api/**` | api-scout |
| Other `docs/` root files | The agent that created them |
| Agent definitions, CLAUDE.md, rules, skills | claude-architect |

docs-writer may reference but MUST NOT modify agent-maintained docs in `docs/` root.

## Update Triggers

Documentation MUST be updated when any of these occur:

1. A new feature or endpoint ships
2. Architecture or deployment configuration changes
3. A new agent is created or an existing agent is materially modified
4. Database schema changes (new tables, column changes, migrations)
5. An epic completes that changes how the system works or how users interact with it

## Staleness Convention

Every documentation file MUST include near the top:

- **Last updated**: date (YYYY-MM-DD)
- **Source**: epic/story ID that produced or last modified the content

Files not updated in 90+ days MUST be reviewed when their domain area changes.

## Mandatory Documentation Assessment (PM Responsibility)

When completing any epic, the PM MUST perform a documentation assessment **after all stories are DONE and before archiving the epic**:

1. Review the epic's scope against the update triggers above.
2. **If any trigger fires**: create a documentation update task and dispatch it to docs-writer before archiving.
3. **If no trigger fires**: record "No documentation impact" in the epic's History section.

This step is mandatory, not optional. An epic MUST NOT be archived until the documentation assessment is complete and any required doc updates are dispatched.

## Documentation Update Task Format

When dispatching a doc update to docs-writer, the PM provides:

- **What changed**: epic ID and one-sentence summary
- **Which docs are affected**: specific file paths in `docs/admin/` or `docs/coaching/`
- **What needs updating**: new content, revised content, or removal of stale content

This is a lightweight dispatch (direct message to docs-writer), not a full story.
