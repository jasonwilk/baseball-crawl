# E-182-01: Document Client ID Rotation in Auth Docs

## Epic
[E-182: Document GC Client ID Rotation Behavior](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/api/auth.md` will contain a dedicated subsection documenting client ID and key rotation as a recurring operational event. A first-time reader encountering auth failures will be able to follow a clear path from symptom recognition through diagnosis to recovery, without needing to piece together information from scattered subsections.

## Context
The auth docs already cover extraction mechanics (`bb creds extract-key`, manual DevTools extraction, verification steps) and mention that client ID/key "only changes on app deploys." What's missing is the operational framing: rotation as a named event with a symptom pattern, a diagnostic path that distinguishes it from expired refresh tokens, and a concise recovery workflow. This story adds that framing while referencing existing subsections to avoid duplication.

## Acceptance Criteria
- [ ] **AC-1**: The existing "Client Key Extraction" section in `docs/api/auth.md` is enriched with a rotation-as-event framing subsection (e.g., "Client ID Rotation" or similar) that introduces the concept of rotation as a recurring operational event before the existing extraction mechanics.
- [ ] **AC-2**: The new subsection adds only net-new content that does not already exist in auth.md: (a) the rotation trigger framed as a named operational event (GC JS bundle redeployment changes the `EDEN_AUTH_CLIENT_KEY` composite string), (b) a reference to the existing "How to Know the Key Is Stale" subsection for symptom and diagnostic details (not restating its content), (c) the mobile parallel (iOS client IDs also rotate with app updates -- state this rotation framing as net-new, and reference the existing "Mobile Profile Differences" section for details rather than restating them), and (d) a brief recovery pointer referencing existing "Automated Extraction" and "Verification" subsections by heading name.
- [ ] **AC-3**: No content from existing subsections ("How to Know the Key Is Stale", "Automated Extraction", "Manual Extraction", "Verification") is duplicated -- the new content references them by heading name.
- [ ] **AC-4**: Existing permanence claims in auth.md are updated to acknowledge rotation: the Required Credentials table descriptions for `GAMECHANGER_CLIENT_ID_WEB` ("Stable UUID") and `GAMECHANGER_CLIENT_KEY_WEB` ("static") and the Credential tier durability table entry ("only changes on app deploys") are revised to indicate these values are stable between GC redeployments but do rotate (e.g., "stable between GC redeployments" rather than "Stable UUID" or "static").
- [ ] **AC-5**: `Last updated` and `Source` staleness markers are added or updated at the top of `auth.md` (file-level) per `/.claude/rules/documentation.md` conventions.

## Technical Approach
The new content belongs within the existing "Client Key Extraction" section of `docs/api/auth.md`. The existing subsections cover the "how" (extraction mechanics); this story adds the "why and when" (rotation as an operational event). The challenge is consolidation -- the "How to Know the Key Is Stale" subsection already covers symptoms partially, so the new content should frame these as part of a cohesive rotation event rather than restating them. See epic Technical Notes "Story 1: Auth Docs Placement" for placement details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/api/auth.md` (modify -- add rotation subsection within Client Key Extraction)

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing auth.md content
- [ ] Docs-only story -- no tests required

## Notes
- The existing "Credential tier durability" table (auth.md line 21-24) already notes "only changes on app deploys" -- the new section expands on this operational reality.
- This is a docs-only story. No code changes, no tests.
