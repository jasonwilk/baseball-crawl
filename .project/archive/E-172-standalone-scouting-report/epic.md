# E-172: Standalone Scouting Report Generator

## Status
`COMPLETED`

## Overview
Add a standalone scouting report generator that produces shareable, no-login-required links. The operator pastes a GameChanger team URL, the system crawls the team's public data, and generates a self-contained HTML report with embedded spray charts. The report is served at a public URL that anyone can open and print — no authentication required. This is a parallel path to the main opponent system, designed for minimal friction: paste URL → get link.

## Background & Context
The main dashboard system requires teams to be linked as opponents with games, auth sessions, and full pipeline setup. That's too much friction when the operator just needs to paste a GameChanger URL and get a printable report to text to a coach before a game. This feature provides a quick scouting report path while the main opponent workflow is being built out.

**What already exists that this builds on:**
- The scouting pipeline (`bb data scout`) already crawls schedule, roster, boxscores, and spray charts for any team by `public_id`
- The print template (`dashboard/opponent_print.html`) demonstrates the right report layout with pitching, batting, and spray charts
- The spray chart renderer (`src/charts/spray.py`) generates PNG spray charts from DB data
- `POST /search` can resolve a team name to `gc_uuid` + `public_id` (needed for spray chart crawling)
- `ensure_team_row()` can create tracked team rows
- `parse_team_url()` extracts `public_id` from GC URLs

**What blocks the current path (why this feature is needed):**
- The print view requires `_check_opponent_authorization` (team must appear in games with a permitted team)
- Spray chart image routes require an authenticated session
- The whole dashboard flow requires logging in

**User-confirmed design decisions:**
- **Snapshot model**: reports are frozen at generation time
- **14-day expiration**: reports auto-expire after two weeks
- **Regeneration creates a new link**: pasting the same URL again produces a fresh report with a new slug; old reports remain until expiry
- **Both admin page AND CLI command** for generation

**Expert consultations completed:**
- **baseball-coach**: Data freshness timestamp is non-negotiable for shared reports. Recent form (last 5 game results) is high value for one line of content. Small sample size flags needed since recipients may not know the data depth. Mobile-readable layout essential since links are texted. Deferred to future work: SB%/K%/BB% stat column additions, pitcher workload, coach's notes field, head-to-head history.
- **software-engineer**: Scouting pipeline (`ScoutingCrawler` + `ScoutingLoader`) works on arbitrary teams by `public_id` — no `team_opponents` dependency. Recommends calling crawler/loader directly (synchronous) rather than `run_scouting_sync` (fire-and-forget). Print template is already standalone (no `base.html` inheritance). Fork template rather than conditional blocks.
- **ux-designer**: Single admin page with URL input + report list table below. Readonly input field for URL sharing (no clipboard JS needed). Async generation with status badges (same pattern as team sync). No auto-refresh.

## Goals
- Operator can paste a GameChanger URL and get a shareable link within minutes
- Shareable link requires no login to view — anyone with the link can see the report
- Report is printable (clean print layout, no navigation chrome)
- Report includes pitching stats, batting stats, spray charts, team record, roster, recent form, and data freshness timestamp
- Both admin UI and CLI paths for generation
- Reports auto-expire after 14 days

## Non-Goals
- Live/dynamic reports (this is snapshot-only by design)
- Integration with the main opponent/dashboard system (this is a parallel path)
- Report editing or annotation by coaches
- Batch generation (one URL at a time is sufficient)
- Custom report layouts or per-team templates
- PDF export (browser print-to-PDF is sufficient)
- New stat columns (SB%, K%/BB% per batter) — affects the main dashboard too, separate epic
- Pitcher workload/days rest — requires query-time computation, separate feature
- Coach's notes field — adds editing UI and DB fields, separate feature
- Head-to-head history — requires linking to our games, contradicts "standalone" goal

## Success Criteria
- An operator pastes a GameChanger team URL in the admin page or CLI, waits a few minutes, and receives a shareable link
- A coach opening the link on a phone or laptop sees a complete, readable scouting report without logging in
- Printing the report from the browser produces clean output suitable for a dugout binder
- Reports auto-expire after 14 days and return 404 after expiry
- Regenerating a report for the same team creates a new independent link

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-172-01 | Reports schema + self-contained HTML renderer | DONE | None | - |
| E-172-02 | Report generation pipeline + CLI command | DONE | E-172-01 | - |
| E-172-03 | Public serving route | DONE | E-172-02 | - |
| E-172-04 | Admin reports page | DONE | E-172-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Self-Contained HTML Approach
Reports are generated as self-contained HTML files with all data inlined:
- Spray charts rendered via `src/charts/spray.py` and embedded as base64 data URIs (`<img src="data:image/png;base64,...">`)
- All stats, roster, and team info rendered directly in the HTML
- Print-friendly CSS (no navigation chrome, clean tables, page-break hints)
- No external dependencies — the HTML file can be saved locally and still displays correctly

This avoids the complexity of public routes for images, auth bypass for spray charts, or dynamic rendering.

### TN-2: Reports Table Schema (Migration 008)
```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generating',
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    expires_at TEXT NOT NULL,
    report_path TEXT,
    error_message TEXT
);
CREATE INDEX idx_reports_slug ON reports(slug);
CREATE INDEX idx_reports_team_id ON reports(team_id);
```

- `slug`: URL-safe random string (16 chars via `secrets.token_urlsafe(12)`) used in the public URL
- `status`: `generating` | `ready` | `failed`
- `expires_at`: `generated_at` + 14 days
- `report_path`: relative path under `data/` (e.g., `reports/<slug>.html`)

### TN-3: Generation Pipeline Steps
1. Parse GC URL to extract `public_id` (via `parse_team_url()` in `src/gamechanger/utils.py`)
2. Call `ensure_team_row()` with `membership_type='tracked'` to create or find the team row
3. Create a `reports` row with `status='generating'` and compute `expires_at` (14 days from now)
4. Run the scouting pipeline **synchronously** by calling `ScoutingCrawler.scout_team(public_id)` and `ScoutingLoader.load_team(team_id)` directly (NOT via `run_scouting_sync`, which is fire-and-forget). Per SE consultation: the report generation is a "wait for data, then render" workflow.
5. Query stats from DB: roster, season batting, season pitching, team record, schedule (for recent form), spray chart data
6. Call the renderer to produce self-contained HTML with base64-embedded spray charts
7. Save HTML to `data/reports/<slug>.html`
8. Update reports row: `status='ready'`, `report_path='reports/<slug>.html'`

On failure at any step after row creation, update: `status='failed'`, `error_message=<reason>`.

The scouting pipeline requires auth credentials (for boxscores via the authenticated endpoint). Spray chart crawling requires `gc_uuid` (resolved via `POST /search` or the public team profile bridge if available). If `gc_uuid` cannot be resolved, spray charts are omitted from the report (non-fatal).

### TN-4: Report Content Sections
The report HTML includes (adapted from the existing print template layout):
1. **Header**: Team name, season year, record (W-L), data freshness line: "Stats through [most recent game date] · [N] games"
2. **Recent form**: Last 5 game results as a compact one-liner (e.g., "W 7-3, L 2-4, W 5-1, W 8-0, W 3-2"). One line, no stat tables — just outcomes. Data sourced from the team's schedule (already crawled by ScoutingCrawler).
3. **Pitching section**: Season pitching stats table (IP, ERA, K, BB, H, HR, K/9, BB/9, WHIP, etc.)
4. **Batting section**: Season batting stats table (AVG, OBP, SLG, AB, H, 2B, 3B, HR, RBI, BB, K, SB, etc.)
5. **Spray charts**: Per-player spray chart images (base64 embedded PNGs), subject to 10-BIP minimum threshold
6. **Roster**: Player list with jersey numbers and positions
7. **Footer**: "Generated by bbstats.ai on [date]. Expires [date]." Print/Save button (screen only).

**Small sample size flags**: Stats based on fewer than 20 PA (batting) or 15 IP (pitching) should display a visible indicator (e.g., asterisk with footnote "* Small sample size"). Per coaching consultation: recipients who don't know the data depth may over-interpret thin stats.

**Layout**: Print-first (landscape tables) with mobile-responsive CSS. A `@media screen and (max-width: 640px)` block reduces table font size and padding so tables don't overflow on phone screens. The print layout stays landscape. This dual approach covers the two primary delivery scenarios: printed for the dugout binder, or opened on a phone via texted link.

Print CSS: `@media print` rules hide UI elements (print button), set clean margins, use `page-break-inside: avoid` on tables and chart sections.

### TN-5: Public Route Design
`GET /reports/<slug>`:
- No authentication required (route is NOT behind auth middleware)
- Query `reports` table by slug
- If not found or expired (`datetime.utcnow() > expires_at`): return 404
- If `status != 'ready'`: return 404 (generating/failed reports are not publicly served)
- Read HTML file from `data/<report_path>` and serve with `Content-Type: text/html`

### TN-6: Regeneration and Expiration
- Each generation creates a new `reports` row with a new slug, regardless of whether a report for the same team already exists. No dedup or overwrite.
- Old reports remain accessible until they expire (14 days from their own generation time).
- Expiration is checked at serve time (lazy). No background cleanup job is needed for now.

### TN-7: Admin Page Patterns (per UXD)
- URL input + "Generate Report" button at top of `/admin/reports` page, report list table below (same-page layout)
- Shareable URL shown as a readonly `<input type="text">` per report row — native select-all on focus, no JavaScript clipboard API needed
- Status badges match existing admin patterns: "Generating..." (yellow), "Ready" (green), "Failed" (red), "Expired" (gray)
- No auto-refresh on the page. Operator refreshes manually to check status (same pattern as team sync)
- "Reports" tab added to admin sub-nav

## Open Questions
None — all design decisions confirmed by user, all expert consultations incorporated.

## Review Scorecard

### Planning Reviews
- **Internal PM review**: Passed (quality checklist, dependency graph, file overlap analysis)
- **Expert consultations**: Completed (baseball-coach, software-engineer, ux-designer). DE consultation skipped — single-table schema with no complexity.
- **Codex spec review**: Skipped — well-defined scope with full expert consultation, 4 straightforward stories, no cross-cutting concerns.

### Implementation Reviews
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-172-01 | 2 | 2 | 0 |
| Per-story CR — E-172-02 | 8 | 8 | 0 |
| Per-story CR — E-172-03 | 1 | 1 | 0 |
| Per-story CR — E-172-04 | 3 | 1 | 2 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 6 | 4 | 2 |
| **Total** | **21** | **17** | **4** |

### PM AC Verification
- E-172-01: 9/9 PASS
- E-172-02: 9/9 PASS
- E-172-03: 7/7 PASS
- E-172-04: 9/9 PASS (minor deviation: AC-4 uses Copy Link button instead of readonly input per TN-7; functionally equivalent)
- **Total: 34/34 ACs PASS**

## History
- 2026-03-28: Created. Replaces previous E-172 scope (opponent workflow fix — that work is deferred, captured as IDEA-053).
- 2026-03-28: Expert feedback incorporated (coach, SE, UXD). Added: data freshness line, recent form, sample size flags, mobile-responsive layout, synchronous pipeline call, readonly URL input pattern.
- 2026-03-28: Set to READY. Internal and Codex review skipped — well-defined scope with full expert consultation.
- 2026-03-28: All 4 stories DONE. 82 tests passing. 21 review findings (17 accepted, 4 dismissed). 34/34 ACs verified. Epic COMPLETED.

### Documentation Assessment
New user-facing feature with CLI commands (`bb report generate`, `bb report list`), admin page (`/admin/reports`), and public route (`/reports/<slug>`). **Trigger fires**: new feature ships. Docs-writer should update admin documentation to cover the reports workflow.

### Context-Layer Assessment
1. **New agent capability or behavior?** No — no new agents or agent behavior changes.
2. **New rules, conventions, or constraints?** No — follows existing patterns (BackgroundTasks, admin auth, public route exclusion).
3. **New or modified skills?** No.
4. **New or modified hooks?** No.
5. **CLAUDE.md updates needed?** Yes — new `src/reports/` package (renderer + generator), migration 008 (`reports` table), `bb report` CLI command group, `/reports/<slug>` public route (no auth, lazy expiration), `/admin/reports` admin page. Architecture section should document the reports pipeline. Next migration number advances to 009.
6. **Agent memory updates?** Yes — PM memory: epic status, next migration number (009).

**Triggers fired**: 5 (CLAUDE.md), 6 (agent memory). Claude-architect should codify CLAUDE.md updates before archiving.

### Ideas Backlog Review
No CANDIDATE ideas are newly unblocked by E-172. IDEA-037 (Scouting Report Redesign) is tangentially related but covers the main dashboard scouting report, not standalone reports — remains CANDIDATE.

### Vision Signals
~30 unprocessed signals in `docs/vision-signals.md` (last curation: 2026-03-13). Advisory: consider "curate the vision" when convenient.
