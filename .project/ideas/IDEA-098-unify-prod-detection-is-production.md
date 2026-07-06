# IDEA-098: Unify production-detection through the is_production() seam

## Status
`CANDIDATE`

## Summary
E-252-03 introduced `src/api/helpers.py::is_production()` as the single-source production-detection seam (`APP_ENV == "production"`, development default) and repointed `routes/auth.py::_is_dev_mode` to `not is_production()`. But `csrf.py:135` still uses the inline `os.environ.get("APP_ENV", "development") == "production"` idiom. This idea narrows that remaining inline idiom to route through the seam, so prod-detection is read one way everywhere.

## Why It Matters
Single-source prod-detection removes a class of drift bug: today a change to how "production" is determined must be made in multiple places, and one can be missed. Consolidating on `is_production()` makes the semantics auditable in one spot (relevant because prod-detection gates security-sensitive behavior like cookie `secure` flags and the email tri-state).

## Rough Timing
Someday / low urgency — a small consistency refactor. Promote if a broader "prod-detection sweep" is undertaken, or opportunistically when csrf.py is next touched.

## Dependencies & Blockers
- [ ] None hard. `is_production()` already exists (E-252-03).

## Open Questions
- Scope is narrowly `csrf.py:135`. Carry these CAVEATS so a future implementer does NOT over-reach (all confirmed during the E-252 Phase 4b review):
  - `auth.py:355` uses case-insensitive `.lower()` for its check — DIFFERENT semantics; it must NOT be folded into `is_production()` (which is exact-match).
  - `main.py` only LOGS `app_env` (no boolean predicate to unify).
  - `reset.py` is a DB utility that arguably should NOT import from `api/helpers` (layering) — leave it.

## Notes
Surfaced by the Phase 4b Codex review of E-252 (P5-adjacent) and confirmed by CR. E-252-03 explicitly scoped csrf.py/main.py unification OUT. Domain: software-engineer. Anchors: `src/api/csrf.py:135`, `src/api/helpers.py::is_production()`. One of three E-252 closure follow-up candidates (with [[IDEA-097-team-resolver-proxy-pacing-posture]] and [[IDEA-099-busy-timeout-non-triad-writers]]).

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
