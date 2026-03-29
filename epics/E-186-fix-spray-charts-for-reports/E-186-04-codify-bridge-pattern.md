# E-186-04: Codify public_id-to-gc_uuid Bridge Pattern

## Epic
[E-186: Fix Spray Charts for Standalone Reports](epic.md)

## Status
`TODO`

## Description
After this story is complete, the public_id-to-gc_uuid resolution pattern (POST /search + public_id filtering) is codified in the context layer so that agents working on gc_uuid resolution instinctively reach for this approach. The pattern is documented with its verification evidence, constraints, and usage guidance.

## Context
The user explicitly wants the bridge pattern "hardened into consciousness" after two epics built on false premises about gc_uuid availability. The pattern is: when you have a `public_id` but need a `gc_uuid`, search by team name via `POST /search`, filter hits by `public_id` exact match, and extract the `id` field. This was verified live on 2026-03-29 (see `.project/research/spray-endpoint-asymmetry.md`). Without context-layer codification, future agents will not know this resolution path exists and may repeat the mistakes of E-158 and E-176.

## Acceptance Criteria
- [ ] **AC-1**: A context-layer file documents the public_id-to-gc_uuid bridge pattern including: when to use it, the API call sequence, the public_id filtering step, the conditional storage rule, and the edge case where search returns no match.
- [ ] **AC-2**: `CLAUDE.md` GameChanger API section references the bridge pattern with enough context that an agent encountering a gc_uuid resolution need knows to look for it. This should be a concise pointer (one to two sentences), not a full procedure.
- [ ] **AC-3**: The `POST /search` endpoint documentation in `docs/api/endpoints/` (if it exists) or API index references the bridge pattern as a use case.
- [ ] **AC-4**: The context-layer file includes the 2026-03-29 verification evidence (team name, public_id, resolved gc_uuid) so agents can trust the pattern without re-verifying.
- [ ] **AC-5**: The pattern documentation explicitly warns against the false premise that led to E-158/E-176: do NOT assume the spray endpoint returns both teams' data regardless of UUID.

## Technical Approach
Determine the best placement for the bridge pattern documentation. Options include a new rule file, an addition to an existing API doc, or CLAUDE.md expansion. Consult the context-layer placement framework in `.claude/rules/context-layer-guard.md` for guidance. The pattern should fire when an agent touches gc_uuid resolution code, so scoped rules with appropriate `paths:` frontmatter may be the right delivery mechanism. Reference the corrected API documentation from E-186-03.

## Dependencies
- **Blocked by**: E-186-03 (corrected docs to reference)
- **Blocks**: None

## Files to Create or Modify
- Determined by claude-architect based on placement analysis. Likely candidates:
  - `CLAUDE.md` (brief pointer in GameChanger API section)
  - A new or existing rule file in `.claude/rules/`
  - `docs/api/endpoints/post-search.md` or `docs/api/README.md` (if search endpoint doc exists)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `POST /search` endpoint is already used in `src/gamechanger/resolvers/gc_uuid_resolver.py` (Tier 3), but without `public_id` filtering. The bridge pattern is a refinement: same API call, but with an exact `public_id` match rather than fuzzy name matching.
- The Content-Type for POST /search is `application/vnd.gc.com.post_search+json; version=0.0.0`.
- Search response shape: `{"hits": [{"result": {"id": "<gc_uuid>", "public_id": "<public_id>", ...}}, ...]}`.
