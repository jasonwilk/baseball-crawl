# E-052: Proxy Data Lifecycle

## Status
`DRAFT`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Give the mitmproxy capture pipeline an intentional data lifecycle: session-scoped log files, ingestion tracking, and archive-on-stop semantics. Today, endpoint logs grow forever, header reports overwrite silently, and there is no way to know what has been reviewed vs. what is new. This epic makes every proxy session a discrete, traceable unit of work.

## Background & Context
The proxy addon pipeline (E-039, migrated in E-048) produces three data streams:

1. **Endpoint log** (`endpoint-log.jsonl`) -- append-only JSONL of every GC API request. Grows indefinitely with no rotation or session boundaries. Consumed ad-hoc via `scripts/proxy-endpoints.sh`.
2. **Header report** (`header-report.json`) -- overwritten on each GC request with the latest parity snapshot. No history preserved. Consumed via `scripts/proxy-report.sh`.
3. **Credentials** -- auto-merged to `.env` by `credential_extractor.py`. Already well-handled; no changes needed.

The operator's workflow is: start proxy, browse GameChanger on iPhone, stop proxy, then examine captures. But there is no concept of a "session" -- all captures blend together across start/stop cycles. There is no tracking of which endpoint discoveries have been reviewed and fed into `docs/gamechanger-api.md`, so the operator cannot tell new discoveries from old noise.

The user's stated goal: "make it intentional."

**No expert consultation required** -- this is pure infrastructure/tooling for the proxy pipeline. The coaching value chain (proxy captures -> API spec -> crawlers -> database -> dashboard) is already established; this epic improves the capture-to-spec leg.

## Goals
- Every proxy start/stop cycle produces a discrete, timestamped session directory
- Endpoint logs and header reports are scoped to their session
- The operator can see which sessions have been reviewed and which have new discoveries
- Report scripts work against both individual sessions and aggregate views
- Stopping the proxy cleanly closes the session with summary metadata

## Non-Goals
- Automated ingestion into `docs/gamechanger-api.md` (that remains a human + api-scout workflow)
- Changes to the credential extraction pipeline (already works well)
- Proxy addon logic changes beyond output path routing (no new capture types)
- Session-based filtering in the mitmweb UI
- Database storage of proxy captures (files are fine for this volume)

## Success Criteria
- `start.sh` creates a new session directory; `stop.sh` finalizes it with metadata
- Endpoint log and header report land in the session directory, not a shared flat file
- `proxy-endpoints.sh` and `proxy-report.sh` work against sessions (default: latest; flag: specific or all)
- A session manifest tracks reviewed/unreviewed status
- Old `proxy/data/endpoint-log.jsonl` and `proxy/data/header-report.json` are replaced by session-scoped equivalents

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-052-01 | Session directory structure and start/stop lifecycle | TODO | None | - |
| E-052-02 | Route addon output to active session | TODO | E-052-01 | - |
| E-052-03 | Session manifest and review tracking | TODO | E-052-01 | - |
| E-052-04 | Migrate report scripts to session-aware mode | TODO | E-052-02, E-052-03 | - |
| E-052-05 | Stop-time session summary | TODO | E-052-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Session Directory Layout

```
proxy/data/
  sessions/
    2026-03-06_143022/          # One dir per start.sh invocation
      endpoint-log.jsonl        # Endpoint discoveries for this session
      header-report.json        # Final header parity snapshot for this session
      session.json              # Session metadata (see below)
    2026-03-06_160511/
      ...
  current -> sessions/2026-03-06_160511   # Symlink to active session (removed on stop)
```

### Session Metadata (`session.json`)

Created by `start.sh`, finalized by `stop.sh`:

```json
{
  "session_id": "2026-03-06_143022",
  "profile": "mobile",
  "started_at": "2026-03-06T14:30:22Z",
  "stopped_at": "2026-03-06T15:01:44Z",
  "status": "closed",
  "endpoint_count": 47,
  "reviewed": false,
  "review_notes": ""
}
```

- `status`: `"active"` while proxy is running, `"closed"` after `stop.sh`
- `reviewed`: set to `true` by the operator (manually or via a review command)
- On `start.sh`: create dir, write `session.json` with `status: "active"`, `stopped_at: null`
- On `stop.sh`: update `session.json` with `stopped_at`, `status: "closed"`, `endpoint_count`

### Addon Output Routing

Addons currently use hardcoded paths (`/app/proxy/data/endpoint-log.jsonl`, `/app/proxy/data/header-report.json`). The new approach:

- Set an environment variable `PROXY_SESSION_DIR` when starting the container (e.g., `/app/proxy/data/sessions/2026-03-06_143022`)
- Each addon reads `PROXY_SESSION_DIR` to determine its output path; falls back to `proxy/data/` for backward compatibility
- `start.sh` creates the session dir and passes `PROXY_SESSION_DIR` to `docker compose up`
- The `current` symlink is a convenience for scripts; addons use the env var directly

### Report Script Migration

Current scripts read from fixed paths. Updated behavior:

- **Default (no args)**: read from `proxy/data/current/` symlink (latest session)
- **`--session <id>`**: read from a specific session directory
- **`--all`**: aggregate across all sessions (useful for `proxy-endpoints.sh` deduplication)
- **`--unreviewed`**: aggregate across sessions where `reviewed: false` (the key "what's new?" query)

### Review Workflow

Lightweight by design. The operator's flow:

1. Run `proxy-endpoints.sh --unreviewed` to see new endpoint discoveries
2. Review and feed interesting findings to api-scout (existing manual workflow)
3. Mark sessions as reviewed: `proxy-review.sh <session-id>` (sets `reviewed: true` in `session.json`)
4. Or mark all: `proxy-review.sh --all`

This does NOT automate the api-scout step. It just tracks what has been looked at.

### Backward Compatibility

- The flat files `proxy/data/endpoint-log.jsonl` and `proxy/data/header-report.json` will be removed after migration
- If `PROXY_SESSION_DIR` is not set, addons fall back to the old paths (defensive, but not a supported mode)
- E-051 (cert persistence) is independent -- it touches `proxy/certs/`, not `proxy/data/`

### File Impact Summary

| File | Stories |
|------|---------|
| `proxy/start.sh` | 01 |
| `proxy/stop.sh` | 01, 05 |
| `proxy/docker-compose.yml` | 01 |
| `proxy/addons/endpoint_logger.py` | 02 |
| `proxy/addons/header_capture.py` | 02 |
| `proxy/addons/loader.py` | 02 (if addon init changes needed) |
| `scripts/proxy-endpoints.sh` | 04 |
| `scripts/proxy-report.sh` | 04 |
| `scripts/proxy-review.sh` (new) | 03 |
| `proxy/data/sessions/` (new dir) | 01 |
| `tests/test_endpoint_logger.py` | 02 |
| `tests/test_header_capture.py` | 02 |

## Open Questions
- Should we set a retention policy (auto-delete sessions older than N days)? Leaning no -- disk is cheap and session count will be low (a few per week at most). Revisit if it becomes a problem.
- Should `proxy-review.sh` accept free-form notes (`--notes "found new /teams endpoint"`)? The `review_notes` field is in the schema for this, but the review script could start simple (just set `reviewed: true`) and add notes later.

## History
- 2026-03-06: Created (DRAFT). No expert consultation required -- pure proxy infrastructure tooling.
