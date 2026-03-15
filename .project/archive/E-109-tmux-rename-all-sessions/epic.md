# E-109: tmux Window Rename for All Epic Sessions

## Status
`COMPLETED`

## Overview
Extend the tmux window rename convention from dispatch-only to all epic-related sessions, and add workflow stage to the window name. Currently the rename lives only in the implement skill's Phase 0 (E-090) and shows just the epic ID. After this epic, tmux windows show both epic ID and workflow stage (e.g., `E-107 refine`, `E-107 dispatch`).

## Background & Context
E-090 added automatic `tmux rename-window "E-NNN"` to the implement skill's Phase 0. This works for dispatch sessions but has two gaps: (1) non-dispatch sessions (refinement, triage, spec review) bypass the implement skill and get no rename, and (2) even dispatch sessions don't show what workflow stage is active. In Heavy mode with multiple tmux windows, you can't tell at a glance whether a window is doing refinement, spec review, or dispatch for a given epic.

Architect consulted on placement (2026-03-15): recommended CLAUDE.md Terminal Modes section for the general convention.

## Goals
- tmux window shows both epic ID and workflow stage for any epic-related session
- Known stages documented so the naming is consistent across sessions

## Non-Goals
- Adding rename behavior for non-epic team sessions (e.g., ad-hoc research teams with no epic ID)
- Adding any programmatic enforcement (this is a convention, like E-090)
- Inventing new workflow stages -- only document the ones we actually use

## Success Criteria
- CLAUDE.md Terminal Modes section documents the convention with stage names and the one-liner
- The implement skill's Phase 0 uses the new `"E-NNN dispatch"` format
- Known stages are listed so naming is consistent

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-109-01 | Add tmux rename convention with workflow stages | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Placement Decision (architect consultation, 2026-03-15)
**CLAUDE.md Terminal Modes section** is the correct location because:
- The rename is a terminal-mode behavior, not a dispatch behavior
- dispatch-pattern.md is dispatch-scoped; adding non-dispatch conventions dilutes its focus
- CLAUDE.md is loaded every session and Terminal Modes is scannable
- A single sentence with the inline one-liner is sufficient

The implement skill's Phase 0 is updated to use the new `"E-NNN dispatch"` format throughout (prose, command, substitution note, diagram), aligning with the general convention. No occurrence of the old epic-ID-only format should remain in Phase 0 after the update.

### Window Name Format
`"E-NNN stage"` -- epic ID followed by workflow stage. Examples:
- `E-107 refine` -- refinement session
- `E-107 triage` -- spec review triage
- `E-107 spec-review` -- Codex spec review
- `E-107 dispatch` -- implementation dispatch
- `E-107 code-review` -- Codex code review

### The One-Liner
Updated from E-090 to include stage:
```
{ [ -n "$TMUX" ] && command -v tmux >/dev/null 2>&1 && tmux rename-window "E-NNN stage" 2>/dev/null; } || true
```

### Known Stages
| Stage | When |
|-------|------|
| `refine` | Epic refinement, consultation, planning sessions |
| `triage` | Spec review triage |
| `spec-review` | Codex spec review |
| `dispatch` | Implementation dispatch (implement skill) |
| `code-review` | Codex code review |

This list is not exhaustive -- if a new workflow stage emerges, use a short hyphenated name.

## Open Questions
None.

## History
- 2026-03-15: Created. Motivated by observation that non-dispatch team sessions in Heavy mode don't rename the tmux window. Architect consulted on placement -- recommended CLAUDE.md Terminal Modes. 1 story. Epic set to READY.
- 2026-03-15: Refined. Added workflow stage to window name format (e.g., `E-107 refine` instead of just `E-107`). Scope expanded to include implement skill Phase 0 update. 5 known stages documented.
- 2026-03-15: Codex spec review triage (Round 1). F1 (P2, FIX): Broadened AC-5 from targeting two specific occurrences to a completeness predicate covering all Phase 0 text -- prose description, command example, substitution note, and Workflow Summary diagram. F2 (P2, FIX): Dropped two subjective DoD items ("No regressions..." and "Code follows project style") -- ACs already cover everything testable. CA consulted, confirmed both changes.
- 2026-03-15: Codex spec review triage (Round 2). F1 (P2, FIX): Aligned story Technical Approach to match AC-5's broader scope -- was narrowly scoped to "command example and Workflow Summary diagram," now covers all four Phase 0 elements (prose, command, substitution note, diagram). Epic Technical Notes (line 45) already had the broad scope, so no epic-level change needed. CA consulted, no additional concerns -- epic is clean and dispatchable.
- 2026-03-15: Codex spec review triage (Round 3). F1 (P2, FIX): AC-1 said "before team creation" but AC-3 lists spec-review and code-review as known stages -- both are headless (no Agent Teams). Broadened AC-1 from "before team creation" to "at the start of the session, before any work begins." AC-4 updated from "all epic-related team sessions" to "all epic-related sessions, whether team-based or headless." Story Description updated to match. CA consulted, confirmed: the rename is a terminal-mode behavior for operator orientation, not an Agent Teams behavior -- convention should be session-scoped, not team-scoped.
- 2026-03-15: Codex spec review triage (Round 4, final). F1 (P3, FIX): Epic metadata (title, overview, background, goals) still referenced "team sessions" after Round 3 broadened scope to all sessions. Updated all four locations in epic.md plus the story file's epic reference link. CA consulted, confirmed fix and flagged the story-file link as an additional propagation spot. Epic is clean and dispatchable.
- 2026-03-15: E-109-01 DONE. Code-reviewer APPROVED with all 6 ACs passing, zero findings. Epic COMPLETED.

  **Documentation assessment**: No documentation impact. E-109 modified only context-layer files (CLAUDE.md Terminal Modes section and implement skill Phase 0). No new features, endpoints, architecture changes, schema changes, or user-facing behavior changes that would trigger docs updates.

  **Context-layer assessment**:
  1. New convention established? **Yes** -- tmux window rename convention for all epic sessions. Already codified by E-109-01 itself (CLAUDE.md Terminal Modes + implement skill Phase 0). No additional codification needed.
  2. Architectural decision? **No**.
  3. Footgun/boundary discovered? **No**.
  4. Agent behavior/routing change? **No** (convention only, no dispatch or routing changes).
  5. Domain knowledge? **No**.
  6. New CLI command/workflow? **No**.

  Trigger 1 fired but codification is already complete (the story's deliverable IS the context-layer update). No additional claude-architect work required.
