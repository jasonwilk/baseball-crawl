# E-250-06: API-doc athlete-profile framing softening

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`DONE`

## Description
After this story is complete, the athlete-profile API docs — and the associated `/me/*` docs that carry cross-season/longitudinal coaching-relevance verdicts (e.g. `get-me-archived-teams.md`, `get-me-associated-players.md`) — no longer frame their coaching relevance as high-value longitudinal / multi-season / cross-season capability. The endpoint SCHEMAS (request/response shapes, field descriptions, auth requirements) are KEPT intact — only the coaching-relevance framing that presents cross-season identity/longitudinal tracking as a live product direction is softened to neutral. Cross-TEAM-in-current-season framing (e.g. `/me/schedule`, org-level rows) is a KEEP and is explicitly fenced off (AC-3, AC-5).

## Context
The athlete-profile endpoints were the API substrate for the abandoned cross-team-identity direction (E-104). Their docs frame them as high-value for longitudinal/multi-season coaching, which now contradicts the permanent non-goals. The schemas remain accurate and worth keeping (the API still returns these shapes); only the product-framing is stale. api-scout owns the API spec and the exact edits.

## Acceptance Criteria
- [ ] **AC-1**: Across the athlete-profile endpoint docs AND the associated `/me/*` docs that carry cross-SEASON/longitudinal coaching-relevance verdicts (per api-scout's inventory — includes `get-me-archived-teams.md` L41 "Coaching relevance: HIGH ... multi-season longitudinal analysis" and `get-me-associated-players.md`), no statement frames the capability as high-value longitudinal / multi-SEASON / cross-SEASON coaching; that framing is softened to neutral (documents what the endpoint returns without asserting it as a live coaching direction). A grep for surviving "multi-season"/"longitudinal" HIGH-relevance verdicts across the in-scope files returns none.
- [ ] **AC-2**: The endpoint SCHEMAS — request parameters, response field tables, auth/header requirements, example payloads — are unchanged.
- [ ] **AC-3**: BOUNDARY (per api-scout prep): cross-TEAM-in-current-season framing is KEPT, not softened. Docs for `/me/schedule`, org-level/roster rows, and any within-current-season cross-team relevance remain as-is — only cross-SEASON / longitudinal coaching-relevance verdicts are reframed. Do not neutralize a doc's value simply because it spans teams; the de-scoped direction is cross-season identity/longitudinal, not current-season cross-team data.
- [ ] **AC-4**: Any cross-reference presenting cross-team *identity across seasons* as a live product direction is removed or neutralized; a note that the direction is de-scoped (per the reports-first reframe) may be added at api-scout's discretion.
- [ ] **AC-5**: README FENCE (over-reach guard): edits to `docs/api/README.md` are limited to L53 (associated-players) and L189 (career-stats) — the two cross-SEASON/longitudinal verdicts. The following README lines are explicitly NOT touched because they are cross-TEAM-in-current-season (in-scope KEEP) or factual: L60 (`/me/schedule` "cross-team unified schedule"), L213 (org-level cross-team), L52 (archived-teams factual description), L66 (teams-summary). An implementer grepping "cross-team" must not over-soften these.

## Technical Approach
api-scout has already produced a precise stale-line list for this softening (per DE/api-scout prep) — apply it, softening only the cross-SEASON/longitudinal coaching-relevance verdicts and honoring the cross-TEAM-in-current-season KEEP boundary (AC-3). Candidate files (api-scout's line list is authoritative on the full set): `docs/api/endpoints/get-athlete-profile-athlete_profile_id.md`, `get-athlete-profile-athlete_profile_id-players.md`, `get-athlete-profile-athlete_profile_id-career-stats.md`, `get-athlete-profile-athlete_profile_id-career-stats-association.md`, `get-me-associated-players.md`, and any longitudinal/multi-season framing in `docs/api/README.md`. Keep all schema/field content.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id.md`
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-players.md`
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats.md`
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats-association.md`
- `docs/api/endpoints/get-me-associated-players.md`
- `docs/api/endpoints/get-me-archived-teams.md` (L41 "Coaching relevance: HIGH ... multi-season longitudinal analysis" — cross-season verdict, softened)
- `docs/api/README.md` (edits FENCED to L53 + L189 per AC-5 — do NOT touch L60/L213/L52/L66)

This file list is CLOSED and complete for READY (Codex #2): these 7 files are the full set api-scout's stale-line inventory identified. If implementation surfaces an eighth file, that is a scope change routed back through PM, not an open-ended catch-all.

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Schema-preserving framing edit only. api-scout has final authority over which `docs/api/**` files carry the stale framing (direct-routing exception domain).

**Deliberate exclusions (api-scout fresh re-sweep, on record so they are not re-flagged):** two nearby `docs/api/` files surfaced on a longitudinal/multi-season/career grep but are NOT in scope — they carry no cross-SEASON coaching-relevance VALUE verdict:
- `get-me-teams.md` L33 — a `see_also` frontmatter reason "(multi-season analysis)"; a cross-reference reason, not a "Coaching relevance" verdict (same class as the athlete-profile see_also links we KEEP). LEAVE.
- `get-players-player_id.md` L61 (`see_also` "cross-team career view" pointer — KEEP per the cross-ref boundary) and L142 ("Coaching relevance: LOW" justified by EFFICIENCY/bulk-retrieval, NOT longitudinal value — does not sell a Non-Goal). LEAVE.
