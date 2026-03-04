# Ideas Backlog

This directory holds pre-epic ideas: directions, problems, and future plans that are worth remembering but are not yet ready to be structured as epics.

An idea becomes an epic when:
1. A dependency clears (e.g., a blocking epic completes)
2. The pain becomes real (we hit the problem the idea was meant to solve)
3. A strategic decision makes it a priority

Ideas do NOT have stories, acceptance criteria, or assignees. They are low-friction captures.

## Review Cadence
Review this list every 90 days, or when completing an epic. Ask:
- Is any CANDIDATE now unblocked?
- Should any CANDIDATE be promoted or discarded?
- Are there ideas we've already solved implicitly?

## Index

| ID | Title | Status | Review By |
|----|-------|--------|-----------|
| [IDEA-001](IDEA-001-local-cloudflare-dev-container.md) | Local Cloudflare Dev Container | DISCARDED | 2026-02-28 -- superseded by E-009 |
| [IDEA-002](IDEA-002-web-scraping-fallback.md) | Web Scraping Fallback Strategy | CANDIDATE | 2026-05-29 |
| [IDEA-003](IDEA-003-github-epics.md) | Work Management as Agent Interface | CANDIDATE | 2026-05-29 |
| [IDEA-004](IDEA-004-pii-protection.md) | Hard Data Boundaries and PII Protection | PROMOTED | 2026-03-02 -- promoted to E-019 |
| [IDEA-005](IDEA-005-intent-nodes.md) | Directory-Scoped Intent Nodes at src/ Module Boundaries | CANDIDATE | 2026-06-01 |
| [IDEA-006](IDEA-006-epic-lanes-convention.md) | Epic Lanes Convention for Multi-Workstream Epics | CANDIDATE | 2026-06-01 |
| [IDEA-007](IDEA-007-dispatch-coordinator-guardrail.md) | Dispatch Coordinator Guardrail -- Prevent Team-Lead-as-PM Bypass | CANDIDATE | 2026-06-02 |
| [IDEA-008](IDEA-008-plays-and-line-scores.md) | Pitch-by-Pitch Plays and Inning Line Scores Crawling | CANDIDATE | 2026-06-02 |
| [IDEA-009](IDEA-009-per-player-game-stats-spray-charts.md) | Per-Player Per-Game Stats and Spray Charts | CANDIDATE | 2026-06-02 |

## Status Definitions

| Status | Meaning |
|--------|---------|
| `CANDIDATE` | Active idea, worth revisiting |
| `PROMOTED` | Became an epic -- see Notes in the idea file for the epic ID |
| `DEFERRED` | Set aside deliberately -- includes reason and re-review date |
| `DISCARDED` | Decided against -- includes reason |

## Adding a New Idea

1. Copy `/.project/templates/idea-template.md`
2. Name it `IDEA-NNN-short-slug.md` (next number in sequence)
3. Fill in all sections
4. Add a row to the index table above
