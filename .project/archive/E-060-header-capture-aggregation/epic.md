# E-060: Stabilize Header-Capture Aggregation

## Status
`COMPLETED`

## Overview
Replace the "latest request wins" overwrite in `HeaderCapture.request()` with deterministic first-seen-wins aggregation so that `proxy-refresh-headers.py` output is independent of request order. This eliminates a race condition where the final header snapshot depends on whichever GameChanger request happened to arrive last.

## Background & Context
`HeaderCapture.request()` (line 209 of `proxy/addons/header_capture.py`) stores captured headers per source with a full-dict overwrite: `self._captured_by_source[source] = headers`. If two requests from the same source carry slightly different header sets (e.g., one includes `Accept` while another does not), the report depends on which request was last -- a non-deterministic outcome. This makes `proxy-refresh-headers.py` output unstable: running the same capture session with requests in a different order can produce different `src/http/headers.py` content.

The user explicitly requested this fix to prevent race conditions. No expert consultation required -- this is pure proxy infrastructure with a well-scoped code change.

## Goals
- Header capture aggregation is deterministic regardless of request order within a session
- Running the same set of requests in any order produces identical `header-report.json` output
- Conflicts (same key, different values across requests) are logged for operator visibility

## Non-Goals
- Changing the `proxy-refresh-headers.py` consumer (it already handles the report format correctly)
- Modifying the parity diff logic (`compute_header_diff`, `build_report`)
- Adding cross-session aggregation (each proxy session starts fresh)

## Success Criteria
- Given N requests from the same source with varying header subsets, the captured dict is the union of all seen keys with first-seen values winning
- Given two requests with different values for the same header key, the first-seen value is retained and a warning is logged
- The `header-report.json` output is identical regardless of request ordering

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-060-01 | First-seen-wins header aggregation with conflict logging | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### Current Behavior (line 209)
```python
self._captured_by_source[source] = headers
```
Full overwrite on every request. Last request wins.

### Target Behavior
```python
if source not in self._captured_by_source:
    self._captured_by_source[source] = headers
else:
    existing = self._captured_by_source[source]
    for key, value in headers.items():
        if key not in existing:
            existing[key] = value
        elif existing[key] != value:
            log.warning(
                "header_capture: conflict for source=%s key=%r: "
                "keeping %r, ignoring %r",
                source, key, existing[key], value,
            )
```
First-seen value wins per key per source. Conflicts logged at WARNING level.

### Files Involved
- `proxy/addons/header_capture.py` -- aggregation logic change (~15-20 lines)
- `tests/test_proxy/test_header_capture.py` -- new order-independence and conflict-logging tests; update existing `test_latest_headers_overwrite_previous` for first-seen-wins

### Testing Strategy
Tests should construct a `HeaderCapture` instance, feed it mock flows in varying orders, and assert:
1. The aggregated dict is the union of all keys
2. First-seen values win when conflicts exist
3. Warning is logged on conflict
4. Request order does not change the final dict

## Open Questions
None.

## History
- 2026-03-06: Created. Straight to READY -- small, well-scoped, no expert consultation needed.
- 2026-03-06: SE review refinements applied. (1) Fixed test file path to `tests/test_proxy/test_header_capture.py`. (2) AC-6 updated: `test_latest_headers_overwrite_previous` asserts old overwrite behavior and must be updated/replaced. (3) AC-2 rewritten to focus on set-equality + first-seen-wins invariant instead of misleading dict literal. Epic remains READY.
- 2026-03-06: E-060-01 DONE. SE replaced single-line overwrite with first-seen-wins merge loop (~13 lines). 4 new tests added (exceeds AC-5 minimum of 3). `test_latest_headers_overwrite_previous` replaced with `test_first_seen_wins_on_conflicting_values`. Module and class docstrings updated. All 36 tests pass. No documentation impact. Epic COMPLETED.
