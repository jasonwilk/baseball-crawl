# IDEA-101: Close the `bb db reset` production-guard whitespace bypass

## Status
`CANDIDATE`

## Summary
`src/db/reset.py:49` guards the destructive `bb db reset` against running in production with `os.environ.get("APP_ENV", "development").lower() == "production"`. `.lower()` normalizes casing but NOT surrounding whitespace, so `APP_ENV=" production "` evaluates as non-production and the destructive reset proceeds WITHOUT requiring `--force`. This is the same fail-open class E-254-01 eliminated for the app's security-gate sites (cookie `Secure`, dev-bypass, CSRF, email) by introducing the strict-normalized `src/api/helpers.py::is_production()` (which does `.strip().lower()`). `reset.py` was OUT of E-254's AC-5/TN-2 consumer set — that set was scoped to app-layer security-gate sites, and `reset.py` is a CLI/DB utility, not an app security gate — so this is a deliberate follow-up, not a within-epic omission.

## Why It Matters
The guard protects an IRREVERSIBLE, destructive operation (a full DB reset). A whitespace-variant `APP_ENV` in a production shell would let a reset run without the `--force` speed bump the guard is meant to impose. Low likelihood (requires a malformed `APP_ENV`), but the blast radius is total, and the canonical fix now exists.

## Rough Timing
Someday / low urgency, but security-flavored (destructive-op guard). Promote if `reset.py` is next touched, or fold into a broader prod-detection sweep. Cross-references the still-open [[IDEA-098-unify-prod-detection-is-production]] (unify remaining inline `APP_ENV` reads through the seam).

## Dependencies & Blockers
- [ ] None hard. `is_production()` already exists and is now strict-normalized (E-254-01).

## Open Questions
- **Layering tension (carry forward)**: [[IDEA-098-unify-prod-detection-is-production]] Open-Question #3 explicitly said to LEAVE `reset.py` alone because a DB utility arguably should NOT import from `src/api/helpers` (layering). That objection was a *consistency-refactor* judgment; CR reframes this as a *security* fail-open, which changes the calculus. The implementer decides the fix shape — either (a) apply the same `.strip().lower()` normalization inline in `reset.py` (no cross-layer import), or (b) relocate `is_production()` to a lower-layer module both `api/` and `db/` may import. Do NOT assume the import is the answer; the inline `.strip().lower()` may be the lighter fix that respects the layering boundary.
- IDEA-098's csrf.py portion and the `auth.py` dev-bypass fold it cautioned against are now DISCHARGED by E-254-01 — IDEA-098 is partly stale and should be re-scoped or closed at its next review.

## Notes
Surfaced as CR's out-of-scope SHOULD-FIX #2 during the E-254-01 dispatch review (2026-07-07). Same whitespace-bypass class as the audit's `auth.py:93` finding that E-254 fixed. Domain: software-engineer (or data-engineer, given `db/` placement). Anchors: `src/db/reset.py:49`, `src/api/helpers.py::is_production()`.

---
Created: 2026-07-07
Last reviewed: 2026-07-07
Review by: 2026-10-05
