# E-109-01: Add tmux Rename Convention with Workflow Stages

## Epic
[E-109: tmux Window Rename for All Epic Sessions](epic.md)

## Status
`TODO`

## Description
After this story is complete, CLAUDE.md's Terminal Modes section will document the convention that any epic-related session in Heavy mode should rename the tmux window to `"E-NNN stage"` (e.g., `E-107 refine`, `E-107 dispatch`) at the start of the session, before any work begins. The implement skill's Phase 0 will be updated to use the new format (`"E-NNN dispatch"` instead of just `"E-NNN"`).

## Context
E-090 added `tmux rename-window "E-NNN"` to the implement skill's Phase 0 for dispatch sessions. Two gaps exist: (1) non-dispatch sessions (refinement, triage, spec review) bypass the implement skill and get no rename, and (2) even dispatch sessions don't show the workflow stage. This story establishes the general convention in CLAUDE.md with stage names and updates the implement skill to align with it.

## Acceptance Criteria
- [ ] **AC-1**: The CLAUDE.md Terminal Modes section (within or immediately after the Heavy mode setup steps) contains a convention statement that when starting an epic-related session in Heavy mode, the main session should rename the tmux window to `"E-NNN stage"` at the start of the session, before any work begins.
- [ ] **AC-2**: The convention includes the guarded one-liner inline: `{ [ -n "$TMUX" ] && command -v tmux >/dev/null 2>&1 && tmux rename-window "E-NNN stage" 2>/dev/null; } || true` (with a note to substitute the actual epic ID and stage).
- [ ] **AC-3**: The convention lists the known stages: `refine` (refinement/consultation/planning), `triage` (spec review triage), `spec-review` (Codex spec review), `dispatch` (implementation dispatch), `code-review` (Codex code review). Includes a note that new stages should use short hyphenated names.
- [ ] **AC-4**: The convention states this applies to all epic-related sessions, whether team-based or headless, not just dispatch.
- [ ] **AC-5**: The implement skill's Phase 0 (`.claude/skills/implement/SKILL.md`) is updated to use `"E-NNN dispatch"` instead of `"E-NNN"` throughout -- including the prose description, command example, substitution note, and Workflow Summary diagram. After the update, no occurrence of the old epic-ID-only format remains in Phase 0.
- [ ] **AC-6**: No new files created. Only `CLAUDE.md` and `.claude/skills/implement/SKILL.md` are modified.

## Technical Approach
Two context-layer files are modified. CLAUDE.md Terminal Modes section gets a short paragraph (2-3 sentences + stage table + one-liner) placed after the Heavy mode setup steps and before the host/container split note. The implement skill's Phase 0 is updated to use `"E-NNN dispatch"` instead of `"E-NNN"` throughout -- prose description, command example, substitution note, and Workflow Summary diagram. No occurrence of the old epic-ID-only format should remain in Phase 0 after the update.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` -- add tmux rename convention with stages to Terminal Modes section
- `.claude/skills/implement/SKILL.md` -- update Phase 0 window name from `"E-NNN"` to `"E-NNN dispatch"`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass

## Notes
- Architect consultation (2026-03-15): CLAUDE.md Terminal Modes is the natural home. dispatch-pattern.md rejected (dispatch-scoped). Rule file rejected (too lightweight).
- The one-liner is the same guard pattern from E-090, extended with a stage placeholder.
- Known stages derived from actual project workflows: refine, triage, spec-review, dispatch, code-review.
