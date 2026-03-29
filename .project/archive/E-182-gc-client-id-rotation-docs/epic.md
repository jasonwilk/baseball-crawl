# E-182: Document GC Client ID Rotation Behavior

## Status
`COMPLETED`

## Overview
Document GameChanger's web client ID and key rotation as a known, recurring operational event. The auth docs currently cover extraction mechanics but do not frame rotation as a durable behavior pattern with a clear symptom-diagnosis-recovery workflow. This epic closes that gap and records the knowledge in api-scout's agent memory so future sessions never assume client IDs are permanent.

## Background & Context
We confirmed that GameChanger's web `gc-client-id` and client key (`GAMECHANGER_CLIENT_KEY_WEB`) are embedded in the JS bundle (`index.{hash}.js` on `web.gc.com`) and rotate whenever GC redeploys. The existing `docs/api/auth.md` has a "Client Key Extraction" section (lines 269-358) covering the `bb creds extract-key` command and manual extraction via DevTools. Line 24 notes client ID/key "only changes on app deploys." However, there is no dedicated section framing rotation as a recurring operational event -- the symptom pattern (auth failures with valid tokens), the diagnostic path (distinguishing stale key from expired refresh token), and the recovery workflow are scattered across subsections rather than presented as a cohesive operational runbook.

Additionally, api-scout's agent memory does not record that client IDs are unstable. Mobile client ID rotation is mentioned in `MEMORY.md` (line 16) but web rotation is not documented as a durable operational pattern.

No expert consultation required beyond api-scout (API knowledge owner) and claude-architect (agent memory pattern owner), both already consulted during discovery.

## Goals
- Document client ID rotation as a named operational event in `docs/api/auth.md` with symptom, diagnosis, and recovery steps
- Record the instability of client IDs in api-scout's agent memory so future sessions do not assume permanence

## Non-Goals
- Automated detection or alerting for stale client keys (future work if needed)
- Changes to the `bb creds extract-key` command itself (already working)
- Mobile client key extraction (unknown, tracked separately)
- Any code changes

## Success Criteria
- `docs/api/auth.md` contains a dedicated section on client ID rotation that a first-time reader can follow from symptom to resolution
- api-scout's memory includes a reference-type file documenting client ID instability
- No existing content in `auth.md` is duplicated -- specifically, the existing "How to Know the Key Is Stale", "Automated Extraction", "Manual Extraction", and "Verification" subsections are referenced by heading name, not restated

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-182-01 | Document Client ID Rotation in Auth Docs | DONE | None | - |
| E-182-02 | Add Client ID Rotation to api-scout Memory | DONE | None | - |

## Dispatch Team
- api-scout
- claude-architect

## Technical Notes

### Story 1: Auth Docs Placement
The new content should be added as a subsection within the existing "Client Key Extraction" section of `docs/api/auth.md` (currently lines 269-358). The section already covers extraction mechanics; the new subsection adds the operational framing: why extraction is needed (rotation), how to recognize it (symptom), how to confirm it (diagnosis), and how to fix it (recovery). The goal is to consolidate, not duplicate -- reference existing subsections ("How to Know the Key Is Stale", "Automated Extraction", "Manual Extraction", "Verification") rather than restating their content.

The "Credential tier durability" table (line 21-24) already notes client ID/key "only changes on app deploys," and the Required Credentials table (lines 254-255) describes `GAMECHANGER_CLIENT_ID_WEB` as "Stable UUID" and `GAMECHANGER_CLIENT_KEY_WEB` as "static." These existing permanence claims must be updated to acknowledge rotation (e.g., "stable between GC redeployments"). The new rotation subsection should expand on the operational implications.

### Key Diagnostic Nuance (api-scout confirmed)
The server returns the **same HTTP 401** for both a stale client key AND an expired refresh token. The current code maps 401 to `CredentialExpiredError`, producing a misleading "Refresh token rejected" / "Credentials expired" message. The new docs section must make this ambiguity explicit and provide the diagnostic path: if `bb creds check` shows the refresh token within its 14-day window but refresh calls still fail, suspect a stale client key first.

### Recovery Path (api-scout confirmed)
1. `bb creds extract-key --apply` -- fetches live JS bundle, parses `EDEN_AUTH_CLIENT_KEY`, updates `.env`
2. `bb creds check --profile web` -- verify Client Key section shows `[OK]`
3. `bb creds refresh --profile web` -- confirm token refresh succeeds end-to-end

Dry-run mode (`bb creds extract-key` without `--apply`) shows what would change without writing.

### Story 2: Memory File Structure
Per claude-architect's guidance:
- **File**: `.claude/agent-memory/api-scout/client-id-rotation.md`
- **Type**: `reference` (durable technical fact, not time-bound project state)
- **MEMORY.md placement**: Under the existing "Topic File Index" section, as a one-liner index entry
- **Content**: Factual and actionable -- state the rotation behavior, the implication for agents (never assume permanence), and where current values live (`.env` variables)

### Mobile Parallel (api-scout confirmed)
Mobile client IDs are version-specific and rotate with iOS app updates (same pattern, different platform). Key difference: **mobile client key cannot be programmatically extracted** -- it's embedded in the iOS binary and would require binary analysis. The `bb creds extract-key` command only covers the web bundle. Mobile programmatic refresh is NOT POSSIBLE without the mobile client key. The auth docs rotation subsection should mention the mobile rotation parallel (net-new framing) and reference the existing "Mobile Profile Differences" section (auth.md lines 411-471) for details rather than restating them. The memory file should cover both web and mobile.

## Open Questions
None -- scope is clear and well-bounded.

## History
- 2026-03-29: Created. Expert consultation: claude-architect (memory file structure -- reference type, Credential Lifecycle placement), api-scout (all 6 technical points confirmed -- rotation trigger, symptom pattern with 401 ambiguity nuance, recovery path, unpredictable frequency, dual-value scope, mobile parallel with extraction limitation).
- 2026-03-29: COMPLETED. Both stories delivered. Per-story CR E-182-01: NOT APPROVED round 1 (2 MUST FIX, 1 SHOULD FIX -- all fixed), APPROVED round 2. E-182-02 context-layer-only, CR skipped. All ACs verified.
- **Documentation assessment**: No additional impact -- the epic deliverables ARE the documentation.
- **Context-layer assessment**:
  - New agent capability or tool pattern introduced? **No** -- no new agent capabilities.
  - New rule, convention, or workflow constraint discovered? **No** -- rotation was known; this documents it.
  - CLAUDE.md or agent definition needs updating? **No** -- auth.md is the right home for this content.
  - New skill or hook needed? **No**.
  - Agent memory pattern changed? **Yes** -- E-182-02 already delivered the api-scout memory file. No additional codification needed.
  - Routing or dispatch pattern affected? **No**.
- No unprocessed vision signals observed during dispatch.
- 2026-03-29: Set to ACTIVE, dispatch begun.
- 2026-03-29: Set to READY after 4 review passes (2 internal, 2 Codex). 15 findings accepted, 5 dismissed. Key refinements: AC-2 narrowed to net-new content only, permanence claim reconciliation added (AC-4), mobile parallel tightened to reference existing section, env vars named explicitly, "Manual Extraction" aligned across all references, cascade drift caught and fixed.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 4 | 3 |
| Internal iteration 1 -- Holistic team (PM 4, api-scout 0, CA 1) | 5 | 5 | 0 |
| Codex iteration 1 | 4 | 3 | 1 |
| Codex iteration 2 | 4 | 3 | 1 |
| Per-story CR -- E-182-01 | 3 | 3 | 0 |
| **Total** | **23** | **18** | **5** |
