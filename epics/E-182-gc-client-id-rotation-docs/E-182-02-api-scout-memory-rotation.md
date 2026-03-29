# E-182-02: Add Client ID Rotation to api-scout Memory

## Epic
[E-182: Document GC Client ID Rotation Behavior](epic.md)

## Status
`TODO`

## Description
After this story is complete, api-scout's agent memory will contain a reference-type file documenting that GC client IDs are not stable across deployments. Future api-scout sessions will know that client IDs rotate and should never be assumed permanent.

## Context
api-scout's MEMORY.md mentions mobile client IDs rotating with app updates (line 16) but does not record web client ID rotation as a durable operational pattern. This story adds a dedicated memory file so that future sessions have this knowledge without needing to re-discover it from auth docs.

## Acceptance Criteria
- [ ] **AC-1**: A file exists at `.claude/agent-memory/api-scout/client-id-rotation.md` with frontmatter: `name: GC Client ID Rotation`, `type: reference`, and a description indicating client IDs are not stable across deployments.
- [ ] **AC-2**: The file content documents: (a) web client IDs/keys are bundle-embedded and rotate on GC JS redeployments, (b) mobile client IDs are version-specific and rotate with iOS app updates, (c) the implication for agents (never assume client ID permanence), and (d) current values live in `.env` -- specifically names `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB`, and notes that `GAMECHANGER_CLIENT_KEY_MOBILE` is unknown/commented out.
- [ ] **AC-3**: `.claude/agent-memory/api-scout/MEMORY.md` contains a one-line index entry for the new file, placed under the existing "Topic File Index" section.
- [ ] **AC-4**: The index entry is under 150 characters and follows the established format: `- [Title](file.md) -- one-line hook`.

## Technical Approach
Per claude-architect's guidance during discovery: use `reference` type (durable fact, not time-bound state), place the MEMORY.md entry under "Topic File Index", and keep content factual and actionable. See epic Technical Notes "Story 2: Memory File Structure" for the full specification.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/api-scout/client-id-rotation.md` (create)
- `.claude/agent-memory/api-scout/MEMORY.md` (modify -- add index entry under Topic File Index)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Memory file follows agent memory conventions
- [ ] Docs-only story -- no tests required

## Notes
- Routed to claude-architect per the context-layer routing rule (agent memory files are context-layer).
