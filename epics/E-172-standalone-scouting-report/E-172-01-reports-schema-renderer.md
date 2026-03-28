# E-172-01: Reports Schema + Self-Contained HTML Renderer

## Epic
[E-172: Standalone Scouting Report Generator](epic.md)

## Status
`TODO`

## Description
After this story is complete, a `reports` table exists in the database (migration 008) and a renderer module can produce a self-contained HTML scouting report from team stats data. The HTML includes all stats, roster, and spray charts embedded as base64 PNGs — no external dependencies. This is the foundation that the generation pipeline (E-172-02) and serving route (E-172-03) build on.

## Context
The standalone report feature needs two foundational pieces: a place to track report metadata (the `reports` table) and a way to turn raw stats into a printable HTML page (the renderer). The renderer adapts the layout from the existing print template (`dashboard/opponent_print.html`) but produces a standalone HTML file with no template inheritance, no auth context, and spray charts inlined as base64 data URIs rather than served via authenticated image routes.

## Acceptance Criteria
- [ ] **AC-1**: Migration 008 creates the `reports` table per TN-2 in the epic. The table includes: `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `slug` (TEXT UNIQUE NOT NULL), `team_id` (INTEGER NOT NULL, FK to teams), `title` (TEXT NOT NULL), `status` (TEXT NOT NULL, default 'generating'), `generated_at` (TEXT NOT NULL), `expires_at` (TEXT NOT NULL), `report_path` (TEXT), `error_message` (TEXT). Indexes exist on `slug` and `team_id`.
- [ ] **AC-2**: A renderer module exists that accepts a data dict containing team info, season pitching stats, season batting stats, roster, schedule (recent games), and spray chart data, and returns a complete HTML string. The HTML is self-contained (no external CSS/JS/image URLs).
- [ ] **AC-3**: Spray charts in the rendered HTML are embedded as base64 data URIs (`<img src="data:image/png;base64,...">`). The renderer calls the existing `src/charts/spray.py` rendering functions to produce PNG bytes, then base64-encodes them. Players below the 10-BIP threshold are excluded from spray charts (consistent with the existing display threshold).
- [ ] **AC-4**: The rendered HTML includes a print-friendly layout with mobile-responsive CSS per TN-4: `@media print` rules hide non-content UI elements, set clean margins, and use `page-break-inside: avoid` on stat tables and spray chart sections. A `@media screen and (max-width: 640px)` block reduces table font size and padding so tables are readable on phone screens without horizontal scrolling.
- [ ] **AC-5**: The rendered HTML includes all sections per TN-4: header (team name, season year, record, data freshness line), recent form (last 5 game results), pitching stats table, batting stats table, per-player spray charts, roster (jersey numbers, positions), and footer with generation and expiration dates plus a Print/Save button (screen only).
- [ ] **AC-6**: The header includes a data freshness line: "Stats through [most recent game date] · [N] games." The generation date is separate from the data freshness date — the freshness date reflects the most recent game in the data, not when the report was rendered.
- [ ] **AC-7**: Stats based on fewer than 20 PA (batting) or 15 IP (pitching) display a small sample size indicator (e.g., asterisk or dagger with a footnote). Per coaching consultation: shared report recipients may over-interpret thin stats without a visible caveat.
- [ ] **AC-8**: The renderer gracefully handles missing data: if spray chart data is empty or absent, the spray charts section is omitted (not an error). If pitching or batting stats are empty, the section renders with a "No data available" message rather than an empty table. If schedule data is absent, the recent form section is omitted.
- [ ] **AC-9**: Tests verify: (a) the renderer produces valid HTML containing expected sections when given complete data, (b) spray charts appear as base64 data URIs, (c) missing spray chart data results in the section being omitted, (d) missing stats produce a "No data available" message, (e) data freshness line appears in header, (f) small sample indicator appears for low-PA/IP players.

## Technical Approach
The migration is straightforward SQL (single CREATE TABLE + two CREATE INDEX). The renderer is a new module that uses Jinja2 to render a standalone template. The template is NOT the same file as `opponent_print.html` — it's a new template designed for standalone use (no `{% extends %}`, no dashboard macros, inline CSS or `<style>` block). The renderer function takes a typed data dict and returns an HTML string. For spray charts, it imports the rendering function from `src/charts/spray.py`, calls it to get PNG bytes, and base64-encodes the result. The data dict structure should match what the generation pipeline (E-172-02) will query from the database.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-172-02 (needs schema + renderer), E-172-03 (needs schema for slug lookup)

## Files to Create or Modify
- `migrations/008_reports.sql` — new migration creating the `reports` table
- `src/reports/__init__.py` — package init
- `src/reports/renderer.py` — renderer module (render function + Jinja2 template rendering)
- `src/api/templates/reports/scouting_report.html` — standalone Jinja2 template for the report
- `tests/test_report_renderer.py` — renderer unit tests

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-172-02**: The renderer module's public function signature and expected data dict shape. E-172-02 must query data from the DB and assemble it into this dict format.
- **Produces for E-172-03**: The `reports` table schema, specifically the `slug`, `status`, `expires_at`, and `report_path` columns used for serving.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `data/reports/` directory for storing generated HTML files does not need to be created by this story — the generation pipeline (E-172-02) will create it on first use.
- The renderer should use Tailwind-like utility classes in inline styles or a `<style>` block — NOT a CDN link to Tailwind CSS (self-contained means no external URLs).
- The stat columns in the pitching and batting tables should match the columns shown in the existing opponent scouting view for consistency with what coaches are used to seeing.
- The "recent form" section is a compact one-liner showing last 5 game results (e.g., "W 7-3, L 2-4, W 5-1, W 8-0, W 3-2"). Data comes from the team's schedule (already crawled). This is high-value, low-effort per coaching consultation.
- The mobile CSS should NOT change the print layout — `@media screen and (max-width: 640px)` is screen-only by definition, so print stays landscape.
