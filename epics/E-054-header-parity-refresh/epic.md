# E-054: Header Parity Refresh from MITM Captures

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Make mitmproxy captures the authoritative source of truth for the header fingerprints in `src/http/headers.py`. Today, the parity report (`proxy-report.sh`) shows drift between captured headers and our static dicts, but nothing acts on it. After this epic, a single command after a proxy session will update `BROWSER_HEADERS` and `MOBILE_HEADERS` to match reality -- keeping our scraping sessions in exact parity with real browser and app sessions.

## Background & Context
The dual-header system (`BROWSER_HEADERS` + `MOBILE_HEADERS` in `src/http/headers.py`) was established in E-049. Header values were set from real captures at the time (Chrome 145, iOS Odyssey 2026.7.0), but they are static snapshots. As Chrome auto-updates, as GameChanger releases new iOS app versions, and as the app adds new custom headers, these dicts will drift from reality.

The capture infrastructure already exists:
- `header_capture.py` addon records all non-credential headers per traffic source and writes `proxy/data/header-report.json`
- `proxy-report.sh` renders a human-readable diff between captured headers and canonical `BROWSER_HEADERS`
- But the diff is informational only -- nothing closes the loop by updating `headers.py`

The operator's stated goal: "The MITM capture should be the authoritative source. Make it automatic so I don't have to think about it."

No expert consultation required -- this is a well-understood sync pipeline. The header capture addon and parity diff logic already exist; the only new work is a script that writes the diff back into `headers.py`.

## Goals
- A single command updates `src/http/headers.py` from the latest proxy capture
- Certain headers are excluded from auto-update (credentials, per-request headers)
- The operator can see what changed before committing
- The workflow is frictionless: capture traffic, run one command, headers are current

## Non-Goals
- Fully automatic header updates on `stop.sh` (too aggressive -- operator should see what changed before it lands in source code)
- Updating `docs/gamechanger-api.md` automatically (header changes are minor; doc updates can be manual)
- Changing what the header capture addon *captures* (it already captures what we need). However, the parity *comparison* logic is fixed to diff each source against the correct canonical dict (web vs. BROWSER_HEADERS, ios vs. MOBILE_HEADERS).
- Per-session header tracking (that is E-052's concern; this epic works with whatever capture data is available)
- Handling header *ordering* (dicts are unordered; HTTP header order is not fingerprint-relevant for our use case)

## Success Criteria
- `scripts/proxy-refresh-headers.py` reads the latest header capture report and updates `src/http/headers.py` to match
- Credential headers, per-request headers, and connection-level headers are excluded from the update
- The script shows a clear diff of what changed before writing
- After running the script, `proxy-report.sh` shows zero drift for the updated profile(s)
- The module docstring's "Source" comment in `headers.py` is updated with the refresh date

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-054-01 | Header refresh script | TODO | None | - |
| E-054-02 | Operator integration and workflow docs | TODO | E-054-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Header Refresh Script Design

The script (`scripts/proxy-refresh-headers.sh` or `scripts/proxy-refresh-headers.py`) reads the header report JSON and writes updated Python dicts back to `src/http/headers.py`.

**Why a Python script (not bash)**: The output is a Python source file with specific formatting (dict literals, multi-line strings for User-Agent). Python's `ast` or template-based generation is more reliable than `jq` + `sed` for producing correctly formatted Python.

**Input**: `proxy/data/header-report.json` (or, if E-052 has landed, `proxy/data/current/header-report.json` via the session symlink). The script should try the session-aware path first, then fall back to the flat path.

**Excluded headers** (never written to `headers.py`):
- Credential headers: `gc-token`, `gc-device-id`, `gc-signature`, `gc-app-name`, `cookie` (already excluded by `header_capture.py`)
- Per-request/endpoint headers: `content-type`, `accept` (these vary per API call; set by `GameChangerClient`, not the session)
- Connection-level headers: `host`, `connection`, `content-length`, `transfer-encoding`, etc. (already excluded by `_SKIP_DIFF_HEADERS` in `header_capture.py`)
- GameChanger action headers: `gc-user-action-id`, `gc-user-action`, `x-pagination` (per-request, not fingerprint)

**Source-to-profile mapping**: The header report groups headers by `detect_source` result (`"web"`, `"ios"`, `"unknown"`). The mapping to `headers.py` dicts:
- `"web"` source -> `BROWSER_HEADERS`
- `"ios"` source -> `MOBILE_HEADERS`
- `"unknown"` source -> ignored (do not update either dict from unknown traffic)

**Output format**: The script rewrites `src/http/headers.py` preserving:
- The module docstring (update the "Source" date line)
- The `from __future__ import annotations` import
- The dict variable names (`BROWSER_HEADERS`, `MOBILE_HEADERS`)
- Multi-line string formatting for long values (e.g., User-Agent)

### Workflow

1. Operator runs mitmproxy and captures GameChanger traffic
2. Operator stops mitmproxy (or leaves it running -- report is written on each request)
3. Operator runs `scripts/proxy-refresh-headers.py`
4. Script reads the header report, computes the diff, shows what will change
5. Script writes updated `src/http/headers.py`
6. Operator reviews the git diff and commits

The script is **not** wired into `stop.sh`. It is a separate, intentional step. The operator runs it when they want to refresh headers, not on every proxy stop. (A future enhancement could add a `stop.sh` hint: "Header drift detected -- run proxy-refresh-headers.py to update.")

### Header Capture Addon Parity Fix (included in E-054-01)

The `header_capture.py` addon currently diffs captured headers against `BROWSER_HEADERS` only (not `MOBILE_HEADERS`). The `build_report` function always compares against `browser_headers` regardless of source. This means the parity report for iOS traffic compares against Chrome headers -- not useful.

**Fix**: Update `build_report` (and the `HeaderCapture` class that calls it) to accept both `BROWSER_HEADERS` and `MOBILE_HEADERS`, and diff each source against the correct canonical dict. The mapping: `"web"` -> `BROWSER_HEADERS`, `"ios"` -> `MOBILE_HEADERS`, `"unknown"` -> `BROWSER_HEADERS` (best guess). This also makes `proxy-report.sh` output more accurate.

### E-055 Note

The refresh script will eventually be wrapped by E-055's unified `bb` CLI. That is a separate epic; no dependency here.

### File Impact Summary

| File | Stories |
|------|---------|
| `scripts/proxy-refresh-headers.py` (new) | 01 |
| `src/http/headers.py` (output target) | 01 |
| `proxy/addons/header_capture.py` | 01 (fix parity comparison: diff each source against correct canonical dict) |
| `tests/test_proxy_refresh_headers.py` (new) | 01 |
| `CLAUDE.md` | 02 |
| `docs/admin/mitmproxy-guide.md` | 02 |

## Open Questions
None -- all resolved during refinement (see History).

## History
- 2026-03-06: Created (DRAFT). No expert consultation required -- header sync pipeline built on existing capture infrastructure.
- 2026-03-06: Refined to READY. Resolved: (1) Dry-run default with `--apply` confirmed. (2) `header_capture.py` parity fix included in E-054-01 (diff each source against correct canonical dict). (3) E-052 interaction handled via path fallback (try session-aware first, then flat).
- 2026-03-06: Applied holistic review triage findings: P2-3: Fixed test file paths in E-054-01 to match `tests/test_proxy/` layout.
