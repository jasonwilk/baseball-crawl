# Software Engineer -- Agent Memory

## Project Code Conventions

### Python Style
See CLAUDE.md Code Style section and `.claude/rules/python-style.md`.
- Conventional commits: `feat(E-NNN-SS):`, `fix(E-NNN-SS):`, `test(E-NNN-SS):`, etc.

### Data Handling
- Parse defensively: missing fields produce warnings, not crashes
- Loaders must be idempotent -- re-running the same data must not create duplicates

## Key File Paths

### Source Code
- `src/` -- all source modules (crawlers, parsers, loaders, utilities)
- `src/http/session.py` -- HTTP session factory (`create_session()`). ALWAYS use this for HTTP clients.
- `tests/` -- all test files, mirroring `src/` structure
- `scripts/` -- utility and operational scripts (e.g., `scripts/refresh_credentials.py`)

### Data and Docs
- `data/` -- local dev data outputs, SQLite database (`data/app.db`)
- `data/raw/` -- raw API response samples (gitignored). Inventory: game-summaries (2 pages), me-teams, me-user (PII-redacted), player-stats (80 records, 387 KB), schedule (228 events, 134 KB), team-detail (own + opponent), boxscore (13 KB, both teams), game-plays (37 KB, 58 plays), public-team-profile, public-team-games (32 records, 25.7 KB), public-team-games-preview (prefer `/games` sample), opponents (70 records, 17 KB), public-game-details (~500 bytes), players-roster (20 players, LSB JV, 2.3 KB), best-game-stream-id (58 bytes), team-users (PII-redacted, no coaching value), public-team-profile-id (~20 bytes), auth-refresh (annotated schema, no live tokens)
- `docs/` -- API specs and documentation
- `docs/api/README.md` -- API documentation index; per-endpoint files in `docs/api/endpoints/`
- `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary for all GameChanger stat abbreviations. Reference when parsing season-stats response fields.

### API Parsing Quirks
- `/me/teams` and `/teams/{team_id}` `ngb` field: **JSON-encoded string**, not a native JSON array. Must double-parse: `json.loads(team["ngb"])`.

### Project Management
- `epics/` -- active epics and story files
- `migrations/` -- numbered SQL migration files (`001_*.sql`, `002_*.sql`, etc.)

## Testing Rules
See `.claude/rules/testing.md`.
- Test data files go in `tests/fixtures/` or inline in the test.

## Working as a Dispatched Subagent

- [dispatch-git-gotchas.md](dispatch-git-gotchas.md) -- `git rm` stages the deletion, hiding it from CR's unstaged `git diff` (hid 97 lines in E-256-03); new untracked files are invisible to `git diff --stat`; mid-epic the baseline is `git show :<file>`, never `HEAD:<file>`; **`TaskUpdate` with `owner` SENDS a real `task_assignment` — it is not a notepad; the body is the task's STORED description, frozen at creation and broadcast as current, so it rebroadcasts stale spec claims under a fresh timestamp (E-277: a false authorization incident, then a phantom "S03-6 not landed" that triggered a stop-work order). Never tidy a task list you do not lead; re-read a description before setting `owner`**
- [feedback_dead_symbol_deletion.md](feedback_dead_symbol_deletion.md) -- A lint-flagged unused binding can be an unfinished intent (found the WebAuthn `exclude_credentials` gap, E-256-08). Check for evidence outside the code; delete by literal block, never by symbol name (two `all_dates`, one live)

## Topic File Index

- [endpoint-parsing-notes.md](endpoint-parsing-notes.md) -- Detailed parsing guidance for all GameChanger API endpoints: token health check, credential management (two-token architecture, JWT fields, headers), team-detail, pagination, player-stats, schedule (location polymorphism, full-day format), opponents (three UUID semantics), boxscore (asymmetric keys, sparse extras, batting order), plays (UUID templates, pitch sequences, lineup changes, edge cases), bridge endpoints, roster (URL pattern warning), public endpoints (no-auth client, record key normalization, avatar_url patterns)
- [app-conventions.md](app-conventions.md) -- Database conventions (ip_outs, FK-safe orphans, splits), security rules, FastAPI patterns (response_model=None, Form, middleware), auth system (E-023: SessionMiddleware, magic links, DEV_USER_EMAIL bypass), test database pattern (auth-aware schema)
- [module-global-seams.md](module-global-seams.md) -- Moving a function re-binds every module global it reads (`get_connection`, `_REPO_ROOT`) to the NEW module — detaching test patches. A seam behind a swallowed exception detaches with ZERO failures. Inject the dependency; never use failures as the search method.
- [name-matching-gotchas.md](name-matching-gotchas.md) -- Free-text team/age_group matching fails SILENTLY to a suppressed card or wrong rest table: `\b` does not fire against `_` (`high_freshman`), plurals need `s?` (`\breserve\b` missed "Reserves"), first-match tables hide precedence (`varsity` beats `legion`); reconstruct the OLD table and diff to find the real blast radius
- [scouting-load-seams.md](scouting-load-seams.md) -- `dedup_team_players` is scoped to the SCOUTED team, so the opponent boxscore block has no dedup closer in ANY shape (name which block before claiming dedup closes an id-churn hazard); `_upsert_game_and_stats` is `GameLoader`'s per-game entry point (**`GameLoader`** has no `_load_game` — but `PlaysLoader` does, so the name reads as right and a subclass override of it silently never fires); on the reconcile paths a CRASH looks like a REFUSAL **under the row count**, so the row count witnesses neither — `LoadResult.errors` discriminates, but four of five swallow sites never increment it (IDEA-189)
- [reclamation-guard-gotchas.md](reclamation-guard-gotchas.md) -- Running a `NOT EXISTS` keep-root clause present-vs-removed CANNOT prove it a no-op (every clause shows the same signature once you seed its column) — only a production-WRITER audit can; `SQLITE_LIMIT_VARIABLE_NUMBER` is 250000 here so chunking tests are vacuous without `setlimit(999)`; `cleanup_expired_reports` has TWO independent commits on a borrowed connection; a guard raising inside a swallowing `try` is not a guard
- [testing-gotchas.md](testing-gotchas.md) -- In an epic worktree `pytest` loads WORKTREE src (`_EditableFinder` is appended after `PathFinder`; needs `tests/__init__.py` + repo root on `sys.path`) — the spawn note says otherwise and is wrong; never trust a `pytest | tail` exit code (capture real RC); seven ways a tool silently misreports a count (`$(git ls-files)` doesn't word-split; ruff `include` filters walks not explicit paths; `.pyc` invisible to `git status`; **markup moved not content: `**emphasis**`, blockquote nesting, phrase across a line break; plus a finding-record carrying every token of the defect it records — unexpected count in EITHER direction is a cross-check trigger, never a finding**) + verbatim recovery of sent messages from `subagents/*.jsonl`; ruff parses `# noqa` in prose; `db.backup()` onto the same path deadlocks in test_report_generator.py
