# IDEA-079: Narrow `except Exception:` Around `_build_opponent_context` to Specific Failure Modes

## Status
`CANDIDATE`

## Summary
The bundle assembler currently wraps `_build_opponent_context()` in a broad `try: ... except Exception:` so any failure becomes a WARNING log + empty page-4 slots. Narrow this to specific known failure modes (e.g., `sqlite3.OperationalError` for schema mismatches, `KeyError` for missing aggregate rows) so that unknown / structural failures surface clearly instead of silently re-introducing the F2 symptom (empty slots) for that bundle.

## Why It Matters
E-229-08 codex finding F2 was "page-4 slots 3 & 4 render empty." The fix added the missing helpers + kwarg threading. To make the fix robust against future regressions, SE wrapped the new payload assembly in a broad `except Exception:` at `src/reports/positioning_bundle.py:768-784`. The handler catches everything → WARNING log → returns empty dict → downstream `.get("compass_key_svg", "")` defaults to empty strings → silently re-introduces F2 (slot 3 + 4 empty) for that bundle.

The non-fatal pattern is correct for transient / data-shape issues (no aggregate rows yet for a brand-new opponent, partial-write retry, etc.). The breadth is wrong for code-integrity issues: a schema mismatch, a misnamed column, or a logic regression in `_build_opponent_context()` should NOT silently swallow into the empty-slots state F2 originally surfaced — it should surface clearly so the next reviewer can catch it without a second codex round.

A narrower handler — one that catches known transient failure modes and lets structural errors propagate — preserves both the resilience and the visibility.

## Acceptance Criteria Sketch
- The handler catches only specific enumerated exception types we expect (e.g., `sqlite3.OperationalError`, `KeyError`).
- A new test asserts that a schema mismatch RAISES (i.e., is NOT swallowed into empty slots).
- The existing non-fatal-on-data-shape test still passes.

## Rough Timing
Small (~10 lines + 1-2 tests). Trigger to promote:
- Observed empty page-4 slots in a real-world bundle after E-229 merges to main, especially if root cause is hard to find because the WARNING log was insufficient.
- A second similar broad-handler pattern is added to the bundle assembler (codification + sweep moment).

## Dependencies & Blockers
- [ ] E-229 closure merges to `epic/E-228-defensive-positioning-cards` (so the handler exists as the modification target)

## Open Questions
- Which exception classes are "known transient" for this code path? (Likely `sqlite3.OperationalError` for schema drift during migrations; possibly `KeyError` for partial-write rows; possibly `decimal.InvalidOperation` for stat-computation edge cases.)
- Should the WARNING log include the exception class name + repr so operators can tell silent-swallow apart from genuine empty-context (no aggregate rows)?
- Is the same broad-handler pattern in any sibling renderer (prep page, call sheet, cards) that should be narrowed at the same time?

## Notes
Source: code-reviewer non-blocking finding during E-229 codex pre-closure remediation review (2026-05-18). Affected location at time of capture: `src/reports/positioning_bundle.py:768-784` (the `_build_opponent_context` call site wrapped in `try: ... except Exception:`).

---
Created: 2026-05-18
Last reviewed: 2026-05-18
Review by: 2026-08-16
