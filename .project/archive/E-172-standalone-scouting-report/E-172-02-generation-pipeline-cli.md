# E-172-02: Report Generation Pipeline + CLI Command

## Epic
[E-172: Standalone Scouting Report Generator](epic.md)

## Status
`DONE`

## Description
After this story is complete, an operator can run `bb report generate <gc-url>` to crawl a team's public data, generate a self-contained HTML scouting report, and save it to disk. The command prints the public URL for the report. A `bb report list` command shows all generated reports with their status and links.

## Context
This story wires together the scouting pipeline and the renderer from E-172-01 into an end-to-end generation pipeline. The pipeline parses a GC URL, ensures the team exists in the DB, runs the scouting crawl/load, queries the resulting stats, renders the HTML, and saves it. The CLI is the first usable interface — the admin page (E-172-04) comes later with the same underlying pipeline.

## Acceptance Criteria
- [ ] **AC-1**: A generation function exists that, given a GameChanger team URL string, executes the full pipeline per TN-3: parse URL → ensure team row → create reports row → run scouting pipeline synchronously (calling ScoutingCrawler + ScoutingLoader directly, not via `run_scouting_sync`) → query stats → render HTML → save file → update reports row.
- [ ] **AC-2**: The generation function creates a `reports` row with `status='generating'` before starting the pipeline. On success, the row is updated to `status='ready'` with `report_path` set. On failure, the row is updated to `status='failed'` with `error_message` set. The `expires_at` is set to 14 days after `generated_at`.
- [ ] **AC-3**: The `slug` for each report is generated via `secrets.token_urlsafe(12)` (producing a 16-character URL-safe string). Each generation creates a new slug regardless of whether the same team URL was used before, per TN-6.
- [ ] **AC-4**: The HTML file is saved to `data/reports/<slug>.html`. The `data/reports/` directory is created automatically if it does not exist.
- [ ] **AC-5**: `bb report generate <gc-url>` runs the generation pipeline synchronously (blocking until complete). On success, it prints the public URL (e.g., `https://bbstats.ai/reports/<slug>`) and the report title. On failure, it prints the error message.
- [ ] **AC-6**: `bb report list` displays a table of all reports with columns: title, status, generated date, expires date, and public URL. Expired reports are shown with an "expired" label. Reports are sorted by `generated_at` descending (newest first).
- [ ] **AC-7**: If `gc_uuid` cannot be resolved for the team (needed for spray chart crawling), the generation pipeline continues without spray charts rather than failing. A warning is logged and the report is generated without the spray chart section.
- [ ] **AC-8**: If the scouting pipeline encounters a `CredentialExpiredError`, the generation function catches it, sets `status='failed'` with a clear error message ("Authentication credentials expired — refresh with `bb creds setup web`"), and does not leave the report in `generating` state.
- [ ] **AC-9**: Tests verify: (a) successful generation creates a report file and updates the DB row to 'ready', (b) failed generation sets 'failed' with error message, (c) CLI prints the public URL on success, (d) `bb report list` displays report rows.

## Technical Approach
The generation pipeline is a new module that orchestrates existing components. URL parsing uses `parse_team_url()`. Team creation uses `ensure_team_row()` with `membership_type='tracked'`. The scouting pipeline calls `ScoutingCrawler.scout_team(public_id)` and `ScoutingLoader.load_team(team_id)` directly — synchronous, inline (per SE consultation: report generation is "wait for data, then render," not fire-and-forget). After crawl/load, stats are queried from the DB (season batting, season pitching, roster, schedule/recent games, spray charts for the team). The renderer from E-172-01 is called with the assembled data dict. The CLI commands are added as a new command group in the `bb` CLI using Typer, following the existing patterns in `src/cli/`.

## Dependencies
- **Blocked by**: E-172-01 (needs `reports` table schema and renderer module)
- **Blocks**: E-172-03 (needs generated reports to serve), E-172-04 (admin page triggers generation)

## Files to Create or Modify
- `src/reports/generator.py` — generation pipeline orchestrator
- `src/cli/report.py` — `bb report` command group (generate + list subcommands)
- `src/cli/main.py` — register the report command group (if CLI entry point aggregates groups here)
- `tests/test_report_generator.py` — generation pipeline tests
- `tests/test_cli_report.py` — CLI command tests

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-172-03**: Generated report files in `data/reports/` and `reports` rows with `status='ready'` and valid `report_path`, which the public route needs to serve.
- **Produces for E-172-04**: The generation function's signature and behavior, which the admin page's background task will call.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The CLI runs the generation synchronously (blocks until done). The admin page (E-172-04) will call the same function via BackgroundTask for async generation.
- The `data/reports/` directory is inside the Docker volume mount (`./data/`), so generated reports persist across container restarts.
- The public URL printed by the CLI should use the `BASE_URL` env var if available, falling back to `http://localhost:8001` for dev. The exact URL format is `/reports/<slug>`.
- The scouting pipeline creates its own DB connection internally (same pattern as `run_scouting_sync`). The generation function should also create its own connection for the report row management and stats queries.
