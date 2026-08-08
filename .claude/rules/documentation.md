---
paths:
  - "docs/**"
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
| `docs/admin/`, `docs/coaching/` | the session |
| `docs/api/**` | api-scout |
| Other `docs/` root files | the session |
| Agent definitions, CLAUDE.md, rules, skills | the session |

`docs/api/**` is the one tree with a non-session owner: api-scout maintains it, so route factual
endpoint changes through that agent rather than editing the specs by hand.

## Update Triggers

Documentation MUST be updated when any of these occur:

1. A new feature or endpoint ships
2. Architecture or deployment configuration changes
3. An agent definition, rule, or skill is created or materially modified
4. Database schema changes (new tables, column changes, migrations)
5. A chunk lands that changes how the system works or how users interact with it

## Staleness Convention

Every documentation file MUST include near the top:

- **Last updated**: date (YYYY-MM-DD)
- **Source**: the spec (or epic ID, for older entries) that produced or last modified the content

Files not updated in 90+ days MUST be reviewed when their domain area changes.

## Mandatory Documentation Assessment

Before closing any chunk, the session MUST perform a documentation assessment **after the work is verified and before the approval step**:

1. Review the chunk's scope against the update triggers above.
2. **If any trigger fires**: make the documentation update part of this chunk, before it closes.
3. **If no trigger fires**: record "No documentation impact" in the spec's progress log.

This step is mandatory, not optional. A chunk MUST NOT close until the documentation assessment is complete and any required doc updates have landed.

## Documentation Update Format

A doc update carries:

- **What changed**: the chunk's spec and a one-sentence summary
- **Which docs are affected**: specific file paths in `docs/admin/` or `docs/coaching/`
- **What needs updating**: new content, revised content, or removal of stale content

This is a lightweight edit inside the chunk, not a separate piece of work.
