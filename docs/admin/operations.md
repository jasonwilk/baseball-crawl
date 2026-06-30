# Operations

This guide covers deploying, maintaining, and troubleshooting the baseball-crawl production stack.

## Deployment Overview

The production stack runs on a home Linux server and is exposed to the internet via a Cloudflare Tunnel. There is no traditional server management (no Nginx, no Let's Encrypt, no port forwarding).

```
Internet  -->  Cloudflare (SSL, Zero Trust Access)  -->  Cloudflare Tunnel
    -->  Traefik (reverse proxy)  -->  FastAPI app  -->  SQLite (data/app.db)
```

**Services** (defined in `docker-compose.yml`):

| Service | Image | Role |
|---------|-------|------|
| `app` | Built from `Dockerfile` | FastAPI application. Runs migrations on startup, then starts Uvicorn on port 8000. |
| `traefik` | `traefik:v3` | Reverse proxy. Routes by `Host` header using Docker labels. Starts only after the app health check passes. |
| `cloudflared` | `cloudflare/cloudflared:latest` | Cloudflare Tunnel connector. Reads `CLOUDFLARE_TUNNEL_TOKEN` from `.env`. Starts only after the app health check passes. |

**Starting the stack**:

```bash
docker compose up -d
```

**Stopping the stack**:

```bash
docker compose down
```

**Rebuilding after code changes**:

```bash
docker compose up -d --build app
```

For the full Cloudflare Tunnel and Zero Trust Access setup, see [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md).

## Feature Flags

Feature flags are set as environment variables in `.env`. Values `1`, `true`, or `yes` (case-insensitive) enable the flag; anything else or absent disables it.

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_PREDICTED_STARTER` | off | Shows the Most Likely Arms section on standalone scouting reports. Temporary flag while the rest-days fix (E-214) is verified in production. Remove once verified stable. |

**Post-merge spot-check**: If `FEATURE_PREDICTED_STARTER` is enabled alongside an LLM key, open one generated report for a youth or travel opponent and verify the narrative block contains no program-specific brand names. One-time check after deploying E-243.

## Data Maintenance

### Back-Filling Appearance Order (`bb data backfill-appearance-order`)

`bb data backfill-appearance-order` populates the `appearance_order` column on existing `player_game_pitching` rows. It walks cached boxscore JSON files on disk to determine the order in which pitchers appeared in each game (1 = starter, 2+ = relievers in order of entry), then updates any row where `appearance_order IS NULL`.

Run this command once after deploying Migration 015 on a database that has historical pitching data:

```bash
bb data backfill-appearance-order
```

**Output:**

```
Backfill Summary:
  Games processed: 42
  Rows updated: 87
  Games skipped (no cached file): 3
  Games with errors: 0
```

After the backfill completes, regenerate any standalone reports for affected opponents to reflect updated GS/GR counts.

**Idempotent**: Safe to run multiple times -- only rows with `appearance_order IS NULL` are updated. Games with no cached boxscore file on disk are skipped and counted in "Games skipped".

**Custom database path**:

```bash
bb data backfill-appearance-order --db /path/to/app.db
```

### Reloading Annotated Pitches (`bb data reload-annotated-pitches`)

`bb data reload-annotated-pitches` re-derives pitch-level data for already-loaded games from stored play text, without re-fetching anything from the GameChanger API. It reclassifies pitches that were previously dropped because they carried a trailing type or velocity annotation (e.g., `"Strike (Fastball, 72mph)"`), and recomputes the derived pitch flags (`pitch_count`, `is_first_pitch_strike`) in place.

Run this command once on a database with historical plays data loaded before E-245:

```bash
bb data reload-annotated-pitches
```

**What it corrects**: The parser previously silently dropped annotated pitches (pitches with a trailing type or velocity suffix), causing `pitch_count` undercounts and unreliable `is_first_pitch_strike` values. After this pass, FPS% and pitch-count stats reflect all recorded pitches.

**Idempotent**: Safe to run multiple times. Only rows whose computed values change are updated.

### Fixing Self-Game Rows (`bb data fix-self-games`)

`bb data fix-self-games` corrects games where the home team and away team resolved to the same entry -- an opponent-resolution bug that causes a team's stats to appear as though they played themselves. The command re-fetches the affected games' boxscores from GameChanger and re-derives the corrupted rows in place.

**Default mode is dry-run** (detects self-games, makes no changes):

```bash
bb data fix-self-games
```

**Execute mode** applies corrections:

```bash
bb data fix-self-games --execute
```

The command exits 0 only when zero self-games remain after the run. A non-zero exit in dry-run mode means self-games were detected; in execute mode it means not all could be resolved (re-run or investigate the affected games manually).

**When to run**: Once, if you suspect historical data includes self-game rows. Dry-run first to assess scope, then `--execute` to apply.

### Deduplicating Player Entries (`bb data dedup-players`)

*Last updated: 2026-06-30 | Source: E-249 (connected-component dedup + fork refusal)*

`bb data dedup-players` detects and merges same-team duplicate player entries caused by cross-perspective UUID mismatch. It groups candidates into connected components and collapses unambiguous ones, but **refuses ambiguous forks** -- leaving them unmerged for manual review rather than silently mis-merging. Use `--dry-run` (default) to preview, then `--execute` to apply.

```bash
bb data dedup-players          # dry run
bb data dedup-players --execute  # apply merges
```

Optional scope filters: `--team-id` and `--season-id` narrow detection to a single team or season.

**Refused forks (review after every run).** A "fork" is a connected component where a short stub name (e.g. "O") prefix-matches two or more *different* fuller names (e.g. "Oliver" and "Owen"). These components are intentionally left unmerged -- every member survives with no data changed. Refused forks appear in the dry-run preview table and in the `--execute` summary output. On `--execute`, the command also emits one WARN-level log line per refused fork naming the team and the conflicting names. Check the dry-run output or application logs for refused forks after each run; these are the duplicates that need a manual judgment call before they can be resolved.

**Non-zero exit on failure.** If any component merge fails during `--execute`, the command prints the error and exits non-zero. A zero exit on execute means every collapsible component succeeded (refused forks are not failures -- they are intentional deferrals). Check the exit code in any scripted context.

**Season aggregates are committed.** After all merges complete, `--execute` recomputes and commits season aggregates for every affected team/season scope. The commit is explicit -- aggregates are not silently discarded on connection close.

### Reconciliation Pipeline (`bb data reconcile`)

`bb data reconcile` compares plays-derived stat aggregates against boxscore ground truth and (optionally) corrects pitcher attribution errors. It is an operator diagnostic and repair tool.

**Note**: The plays ingestion pipeline was removed in E-239. Reconciliation applies only to historical data with plays loaded pre-E-239.

**Default mode is dry-run** (detection only): reads plays and boxscore data from the database, computes discrepancies, writes results to `reconciliation_discrepancies`, and prints a summary. No stat data is modified.

**Commands**:

```bash
# Detect discrepancies across all completed games (dry-run)
bb data reconcile

# Apply pitcher attribution corrections
bb data reconcile --execute

# Detect (or correct) a single game -- prints verbose per-signal breakdown
bb data reconcile --game-id abc123
bb data reconcile --game-id abc123 --execute

# Show aggregate stats from all reconciliation records stored in the database
bb data reconcile --summary
```

**What the engine does**: For each completed game that has plays data loaded, it aggregates plays-derived stats (hits, strikeouts, walks, HBP, at-bats, pitch counts, total strikes) per pitcher and per batter, then compares them against the corresponding boxscore values. Each comparison is classified:

| Status | Meaning |
|--------|---------|
| `MATCH` | Plays-derived value equals boxscore value |
| `CORRECTABLE` | Mismatch caused by an identifiable pitcher attribution error -- can be fixed by reassigning `plays.pitcher_id` |
| `CORRECTED` | Was `CORRECTABLE`; correction was applied in execute mode |
| `AMBIGUOUS` | Mismatch exists but the engine cannot determine the correct pitcher with confidence |
| `UNCORRECTABLE` | Mismatch exists and no correction path is available |

**Detection mode output** (dry-run, all games):

```
Reconciliation Summary
  Total games processed: N
  Games skipped (no plays): N
  Games with all signals matching: N
  Games with correctable pitcher errors: N
  Games with ambiguous errors: N

  Pitcher Signals:
    pitcher_hits: M/N match (X.X%)
    ...
  Batter Signals:
    batter_strikeouts: M/N match (X.X%)
    ...
  Game-Level Signals:
    game_total_runs: M/N match (X.X%)
    ...

  Status Distribution:
    MATCH: N (X.X%)
    CORRECTABLE: N (X.X%)
    ...
```

**Execute mode output** (all games):

Shows corrected/unchanged/remaining-ambiguity counts and total plays reassigned, plus a before → after comparison for each pitcher signal showing match rates pre- and post-correction.

**Single-game output** (`--game-id`): Prints one line per signal showing status breakdown and total count. Verbose enough for per-game diagnosis.

**`--summary` flag**: Reads aggregate stats from all `reconciliation_discrepancies` rows in the database (across all runs). Useful for tracking correction effectiveness over time. Does not re-run detection.

**Idempotency**: Each run is identified by a `run_id` UUID. Results are upserted into `reconciliation_discrepancies` using the UNIQUE constraint on `(run_id, game_id, team_id, player_id, signal_name)`. Re-running on the same games produces a new `run_id` and new rows.

## Morning-Run Scheduled Reports

*Last updated: 2026-06-20 | Source: E-240 (morning-run scheduled reports)*

`bb report morning-run` is a cron-invoked command that runs each morning and generates a fresh scouting report for every LSB team's game scheduled on that date. It is the forward operational surface of the system: the crontab is the config, the operator's job is to keep opponent mappings current, and the end-of-run summary email is the heartbeat.

### What morning-run does

For each team URL passed as an argument, the command:

1. Verifies credentials once (preflight check) before touching any team data.
2. Reads the team's GameChanger schedule and opponent registry.
3. Filters to games whose LOCAL date matches the target date (today by default).
4. For each upcoming opponent on that date, runs the resolution ladder to find the opponent's `public_id`.
5. For auto-resolved opponents, calls the existing `generate_report` pipeline -- the same pipeline as `bb report generate`.
6. Records each slot's outcome to `scheduled_report_runs` and sends operator alerts.

Execution is strictly sequential -- one process, a plain loop over teams then opponents. One opponent's failure does not abort the rest of the run.

### Crontab configuration

The variadic team URLs are the only per-season configuration. Edit the crontab once at the start of each season to add or change the team URLs.

**Example crontab line** (6 AM server time, Monday--Saturday):

```cron
0 6 * * 1-6 bb report morning-run \
  https://web.gc.com/teams/lsb-varsity-2026 \
  https://web.gc.com/teams/lsb-jv-2026 \
  https://web.gc.com/teams/lsb-freshman-2026
```

A 6 AM default is appropriate for most weekday high school and Legion games (4--7 PM starts): the reports are ready hours before game time. Adjust the time zone on the server if the cron daemon runs in UTC.

### --date override for early-start games

Tournaments with 9 AM or earlier starts may need reports the night before. Use `--date` to run for a specific date:

```bash
bb report morning-run --date 2026-06-21 \
  https://web.gc.com/teams/lsb-varsity-2026 \
  https://web.gc.com/teams/lsb-jv-2026
```

The `--date` flag accepts `YYYY-MM-DD`. Run this manually the evening before an early-start tournament day.

### --dry-run: eyeball verification before trusting a new mapping

`--dry-run` resolves opponents and prints per-slot results but generates **no reports** and writes **no run records**. Use it to verify that the resolution ladder is finding the right teams, especially after running `bb report map-opponent` for a new opponent.

```bash
bb report morning-run --dry-run \
  https://web.gc.com/teams/lsb-varsity-2026
```

**Example dry-run output:**

```
RESOLVED Lincoln Southeast (opponent_id=abc123) -> Lincoln Southeast HS [public_id: lincoln-southeast-hs-2026] — record 8-4
UNRESOLVED Slumpbuster Tournament (opponent_id=def456) — needs `bb report map-opponent def456 <PASTE-GC-TEAM-URL>`
deferred_placeholder BYE (opponent_id=ghi789)

Morning run complete (1 team(s)): 0 generated, 0 failed, 1 unresolved, 1 deferred, 0 skipped, 0 denied (403).
```

**What to eyeball on a RESOLVED line**: confirm that the resolved team name and W-L record look right for the opponent you expect. If the mapping resolved to the wrong team, use `bb report map-opponent` to correct it (the ladder's auto-resolution may have matched a name-alike team).

### Operator resolution queue (map-opponent)

When an opponent cannot be auto-resolved, it enters the operator queue. The `bb report map-opponent` command resolves it.

**How an opponent becomes unresolved-but-mappable**: the opponent was entered in GameChanger via team lookup (so a `root_team_id` is available as a stable key), but the resolution ladder could not find a `public_id` match automatically. This is the expected path for opponents the system has never seen before.

**When the operator gets notified**: at runtime, the CLI prints a prominent UNRESOLVED line with a template command. For non-dry-run runs, an email alert is also sent to `ADMIN_EMAIL` carrying the same template.

**Positive mapping** (opponent is on GameChanger -- the normal case):

1. Look up the team on [web.gc.com](https://web.gc.com) and copy the team URL from the browser.
2. Run:

```bash
bb report map-opponent <root_team_id> <PASTE-GC-TEAM-URL>
```

The `root_team_id` is pre-filled in the CLI output and the email alert -- copy it from there. The URL may be a full GameChanger team URL or a bare `public_id` slug; both are accepted.

**Negative mapping** (opponent is genuinely not on GameChanger -- no report possible):

```bash
bb report map-opponent <root_team_id> --no-presence
```

This records an operator-declared "no presence" for the opponent. On future runs the ladder will recognize this and skip report generation without prompting again.

**How many rows get updated**: `opponent_links` is keyed on `(our_team_id, root_team_id)` -- one row per LSB team that faces the opponent. A single `bb report map-opponent` call updates **all pending rows** for that `root_team_id` at once, across every LSB team. You do not need to run it separately per team.

**Re-run after mapping**: the mapping takes effect on the next run. For same-day resolution, run `bb report morning-run` (without `--dry-run`) after mapping, or use `bb report generate <public_id>` to generate the report directly.

### Expected operator queue size

The operator map queue is larger than auto-resolution alone implies, for two reasons that are correct by design:

**Per-team-opponent pairing.** `opponent_links` is keyed on `(our_team_id, root_team_id)`. One real opponent that faces multiple LSB teams (e.g. both Varsity and JV play Lincoln Northeast) must be mapped once per LSB team. The mapping command resolves all pending rows for that `root_team_id` in one call, but each pairing produces its own initial unresolved entry.

**Tournament and bracket names.** Bracket entries (e.g. "Slumpbuster", "Pool A Challenge") that do not match the `BYE` / `TBD` placeholder pattern fall through to the operator queue by design. An unknown bracket opponent genuinely cannot be scouted -- there is no team to look up. Use `--no-presence` for these so the system stops prompting for them.

These are expected conditions, not defects.

### Reading the end-of-run summary email

The end-of-run summary is **always sent** at the end of every non-aborted morning run (when `ADMIN_EMAIL` is configured in `.env`). Its **absence** is the missed-run signal -- if no email arrived by mid-morning on a game day, the cron job did not run.

**Email subject line:**

```
[morning-run] Summary: N generated, N failed, N unresolved
```

**Email body fields:**

| Field | What it means |
|-------|--------------|
| `Reports generated` | Opponents fully resolved and reports successfully built |
| `Generation failures` | Resolved opponents for which report generation failed (auth, network, etc.) |
| `Unresolved (need mapping)` | Genuine unresolved-but-mappable opponents that need `bb report map-opponent` |

The body also includes per-opponent detail lines and, when any team returned a 403, a `denied` line. When **every** team was denied (403), the detail line escalates to a prominent warning:

```
WARNING: ALL N team(s) were denied (403) — likely a systematic auth/version-pin problem,
NOT 'no games today'. Check credentials and the crawler Accept version pins.
```

This warning means the preflight check passed (credentials were valid at startup) but the team-data crawlers failed on every team. This is the FALSE-403 pattern: a misconfigured crawler version pin that passes the preflight `/me/user` check but fails the team-data endpoints. It is **not** the same as "no games today." Investigate the crawler `Accept` version pins or refresh credentials.

**When ADMIN_EMAIL is not set**: operator alerts (including the end-of-run summary and unresolved-opponent alerts) are skipped with a log warning. Email is a side channel -- its absence does not abort or affect the run. Set `ADMIN_EMAIL` in `.env` to receive alerts.

### Credential failure (preflight check)

Before touching any team data, `morning-run` verifies that GameChanger credentials are live by calling a lightweight authenticated endpoint. If this preflight check fails -- token refresh and login fallback both exhausted -- the run aborts immediately and sends a preflight-failure alert to `ADMIN_EMAIL`:

```
[morning-run] Preflight credential check FAILED — run aborted
```

**Action**: refresh credentials (`bb creds import` or `bb creds setup web`) and re-run manually, or wait for the next scheduled run after credentials are restored.

A per-team 403 (ForbiddenError) is distinct from a preflight failure and is not treated as an auth expiry: the team is skipped and counted in the `denied` tally, but the run continues for other teams.

### Idempotency

Re-running `morning-run` on the same date is safe. For each `(own_team_id, opponent_root_team_id, game_date)` slot, if a prior run already generated a non-expired report, the re-run skips regeneration (`delivery_status = skipped`). A slot is only regenerated when its prior report has expired or was never generated successfully.

---



### Migration 015: Appearance Order Column

Migration `migrations/015_add_appearance_order.sql` adds a single nullable column to `player_game_pitching`:

| Column | Type | Purpose |
|--------|------|---------|
| `appearance_order` | `INTEGER` (nullable) | Pitcher entry order within a game. 1 = starter; 2, 3, … = relievers in order of entry. NULL on historical rows until backfill runs. |

**Backfill required for historical data**: Rows written before this migration have `appearance_order = NULL`. Run `bb data backfill-appearance-order` once to populate them from cached boxscore JSON. New rows written by the game loader after this migration are populated at load time.

The migration is applied automatically on container startup.

### Migration 012: Reconciliation Discrepancies Schema

Migration `migrations/012_reconciliation_discrepancies.sql` adds the `reconciliation_discrepancies` table and three indexes to support the plays-vs-boxscore reconciliation engine.

**Table: `reconciliation_discrepancies`** (one row per signal per player per team per run)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PK` | Auto-increment internal key |
| `game_id` | `TEXT` | FK to `games(game_id)` |
| `run_id` | `TEXT` | UUID assigned to each reconciliation run. Groups all rows produced by one `bb data reconcile` invocation. |
| `team_id` | `INTEGER` | FK to `teams(id)` |
| `player_id` | `TEXT` | Player identifier. Uses `__game__` sentinel string for game-level signals (not player-scoped). |
| `signal_name` | `TEXT` | Name of the comparison (e.g., `pitcher_hits`, `batter_strikeouts`, `game_total_runs`) |
| `category` | `TEXT` | Signal category (`pitcher`, `batter`, or `game`) |
| `boxscore_value` | `INTEGER` | Boxscore ground-truth value; nullable if absent |
| `plays_value` | `INTEGER` | Plays-derived aggregate value; nullable if absent |
| `delta` | `INTEGER` | `plays_value - boxscore_value`; nullable when either source is absent |
| `status` | `TEXT` | One of `MATCH`, `CORRECTABLE`, `CORRECTED`, `AMBIGUOUS`, `UNCORRECTABLE` |
| `correction_detail` | `TEXT` | Human-readable description of what was corrected or why correction failed; nullable |
| `created_at` | `TEXT` | UTC timestamp of the run (`datetime('now')`) |

UNIQUE constraint on `(run_id, game_id, team_id, player_id, signal_name)`.

**Indexes added**:

| Index | Column | Notes |
|-------|--------|-------|
| `idx_recon_game_id` | `game_id` | Per-game discrepancy lookups |
| `idx_recon_run_id` | `run_id` | Per-run result retrieval (used by `--summary`) |
| `idx_recon_status` | `status` | Status-filtered queries (e.g., all CORRECTABLE rows) |

The migration is applied automatically on container startup. The table is populated solely by `bb data reconcile`.

### Migration 009: Plays and Play Events Schema

Migration `migrations/009_plays_play_events.sql` adds two tables for play-by-play data. The plays ingestion pipeline was removed in E-239; these tables remain in the schema and existing rows remain readable.

**Table: `plays`** (one row per plate appearance)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PK` | Auto-increment internal key |
| `game_id` | `TEXT` | FK to `games(game_id)` |
| `play_order` | `INTEGER` | Sequential position within the game |
| `inning` | `INTEGER` | Inning number |
| `half` | `TEXT` | `'top'` or `'bottom'` |
| `season_id` | `TEXT` | FK to `seasons(season_id)` |
| `batting_team_id` | `INTEGER` | FK to `teams(id)` -- the team at bat |
| `batter_id` | `TEXT` | FK to `players(player_id)` |
| `pitcher_id` | `TEXT` | FK to `players(player_id)`; nullable (absent on some abandoned PAs) |
| `outcome` | `TEXT` | Plate-appearance result string (e.g., `'Single'`, `'Strikeout'`) |
| `pitch_count` | `INTEGER` | Total pitches in the plate appearance |
| `is_first_pitch_strike` | `INTEGER` | 1 if the first pitch was a strike (FPS); 0 otherwise |
| `is_qab` | `INTEGER` | 1 if the plate appearance meets Quality At-Bat criteria; 0 otherwise |
| `home_score` | `INTEGER` | Score at end of plate appearance (nullable) |
| `away_score` | `INTEGER` | Score at end of plate appearance (nullable) |
| `did_score_change` | `INTEGER` | 1 if a run scored on this play (nullable) |
| `outs_after` | `INTEGER` | Outs recorded after this play (nullable) |
| `did_outs_change` | `INTEGER` | 1 if an out was recorded on this play (nullable) |

UNIQUE constraint on `(game_id, play_order)`.

**Table: `play_events`** (one row per event within a plate appearance)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PK` | Auto-increment internal key |
| `play_id` | `INTEGER` | FK to `plays(id)` |
| `event_order` | `INTEGER` | Sequence position within the plate appearance |
| `event_type` | `TEXT` | `'pitch'`, `'baserunner'`, `'substitution'`, or `'other'` |
| `pitch_result` | `TEXT` | One of `'ball'`, `'strike_looking'`, `'strike_swinging'`, `'foul'`, `'foul_tip'`, `'in_play'`; null for non-pitch events |
| `is_first_pitch` | `INTEGER` | 1 if this is the first pitch event in the plate appearance |
| `raw_template` | `TEXT` | Raw GC template string from the API (nullable; useful for debugging) |

UNIQUE constraint on `(play_id, event_order)`.

### Migration 006: Spray Chart Schema Additions

Migration `migrations/006_spray_charts_indexes.sql` adds three columns and three indexes to the `spray_charts` table (which existed in the base schema but was unpopulated):

| Addition | Type | Purpose |
|----------|------|---------|
| `event_gc_id` column | `TEXT` | GC UUID per ball-in-play event. UNIQUE -- enables `INSERT OR IGNORE` idempotency. |
| `created_at_ms` column | `INTEGER` | API's `createdAt` timestamp in Unix milliseconds. |
| `season_id` column | `TEXT` | Season identifier (e.g., `2026`). Enables per-season filtering per the fresh-start philosophy. |
| `idx_spray_charts_event_gc_id` index | UNIQUE | On `event_gc_id`. Enforces idempotency at the DB level. |
| `idx_spray_charts_player` index | | On `(player_id, team_id, season_id)`. Serves player profile and per-player chart queries. |
| `idx_spray_charts_game` index | | On `game_id`. Serves game-level spray queries. |

The migration is applied automatically on container startup by `migrations/apply_migrations.py`. The table was unpopulated when this migration was written -- no backfill was needed.

## Standalone Reports

Standalone reports are shareable, frozen scouting snapshots generated on demand for any GameChanger team. They do not require a database-tracked team. Manage them at `/admin/reports`.

### Generating a Report

From the admin Reports page, paste a GameChanger public URL or public ID slug and click **Generate**. The system crawls the team's schedule and stats, renders a self-contained HTML file, and saves it to `data/reports/`. Generation typically takes 10-30 seconds depending on how many games the team has played.

**CLI alternative**:

```bash
bb report generate <public_id>
```

Reports expire 14 days after generation. After expiry, the link returns a 404 and the row is eligible for cleanup.

### Listing Reports

```bash
bb report list
```

Shows all generated reports with their public ID, expiry date, and file status.

### Deleting a Report

Click **Delete** on any report row in the admin Reports page. A confirmation dialog appears before the deletion runs.

**What happens when you delete a report** depends on whether the associated team has other data in the system:

When all four conditions below are true, deletion is a **full cascade** -- the report, the HTML file, and the team row plus all its associated data are removed in a single transaction:

| Condition | What it checks |
|-----------|---------------|
| Team is not active (`is_active = 0`) | Active teams are never auto-deleted |
| No `team_opponents` links | Team is not linked as an opponent to any of your tracked teams |
| No other reports reference this team | This was the only report for this team |
| No shared games with tracked teams | No game rows in the DB link this team to a member team |

If **any** condition fails, deletion is a **report-only** operation: only the report row and the `data/reports/` HTML file are removed. The team and its stats remain in the database.

This behavior is automatic -- no operator decision is required. The system applies the guard conditions and does the right thing.

**Typical use case**: A report generated for a tournament team that is not on your schedule will usually satisfy all four conditions. Deleting the report cleans up the team data completely. A report generated for a team that is linked via `team_opponents` will only remove the report file -- the scouting data stays.

### Verifying Scouting Aggregate Integrity (`bb report verify-aggregates`)

`bb report verify-aggregates` is a read-only diagnostic that checks whether stored scouting season aggregates are consistent with the underlying per-game data. It recomputes each team/season's `boxscore_only` aggregates from the `player_game_batting` and `player_game_pitching` rows, then diffs them against the corresponding `player_season_batting` and `player_season_pitching` rows. Mismatches are reported per player, team, season, and column.

```bash
bb report verify-aggregates
```

**When to run**:
- As an ad-hoc data-integrity diagnostic after a report generation run you suspect may have produced inconsistent aggregates.
- Before the Epic C payload-first-loader cutover: run against a copy of the production database to confirm aggregate consistency before the pipeline changes are applied.

**Reading the output**:
- **Empty mismatch list + clean success message + exit 0**: aggregates are consistent. No action needed.
- **Non-empty mismatch list + exit 1**: each flagged row shows the player, team, season, column name, stored value, and recomputed value. Re-generating the report for the affected team(s) will refresh the stored aggregates.

**Scope**: Covers `boxscore_only` (scouting) aggregates only -- those derived from per-game boxscore data. Season rows loaded from the GameChanger season-stats endpoint (`full` and `supplemented` membership types) are intentionally excluded; they are not derived from per-game data and cannot be verified by recomputation.

**Read-only**: This command never writes to `player_season_*` tables. It is safe to run against production at any time.

### Cleaning Up Expired Report Files (`bb report cleanup`)

`bb report cleanup` removes the on-disk HTML files for expired reports -- those whose `expires_at` timestamp is in the past. It is a targeted disk-reclamation sweep: the HTML file is unlinked and `report_path` is nulled on the database row, but the row itself is kept. After cleanup, expired reports still appear in `bb report list` and `/admin/reports` with `Expired` status, and any coach who opens a stale link still gets the existing 404 page.

```bash
bb report cleanup
```

**When to run**:
- After a period of high report volume to reclaim disk space in `data/reports/`.
- As a manual sweep if disk usage grows unexpectedly -- check with `du -sh data/reports/` first.
- There is no urgency: the same cleanup runs opportunistically at the start of every `bb report generate` invocation (failure-swallowed -- it never delays or blocks generation).

**Reading the output**:
- **"Cleanup complete — removed N expired report file(s)."**: Always printed, including the zero case (`N = 0` means nothing to clean up). N > 0 confirms files were unlinked.
- **"N file(s) could not be removed (left in place for a later sweep; see logs)."**: Printed to stderr when one or more files could not be unlinked. Per-file detail goes to the application log, not stdout. The sweep continues and the command still exits 0. Investigate if the same file persists across runs.
- **Non-zero exit**: Only if `cleanup_expired_reports()` itself raises an unexpected exception. Treat as a bug and report.

**Row retention**: Database rows are never deleted by this command. `reports.report_path` is set to NULL for each cleaned row. The row, its run record, and all status/expiry metadata remain intact. To remove a report row entirely, use the **Delete** action in `/admin/reports` or see [Deleting a Report](#deleting-a-report) above.

### Report Generation Run Records

Every standalone report generation writes a companion row to `report_generation_runs` (Migration 002). This row gives per-stage visibility into what happened: which stages ran, which succeeded or failed, how many games were covered, and whether any data-quality trust flags fired.

#### The `report_generation_runs` table

One row per generation, linked 1:1 to `reports(id)` with `ON DELETE CASCADE` (deleting a report removes its run record automatically).

| Column | What it records |
|--------|----------------|
| `overall_status` | Lifecycle status of the generation: `running` (in flight) → `completed` or `failed` |
| `crawl_status` / `load_status` | Per-stage status: `completed`, `partial` (some success but errors or incomplete expected set), or `failed`. Applies to all stage columns below. |
| `boxscores_fetched` | Count of boxscore payloads fetched during the crawl stage (NULL = stage did not run / pre-migration) |
| `load_errors` | Count of per-player load errors during the load stage (NULL = stage did not run / pre-migration) |
| `gc_uuid_status` | UUID resolution result: `resolved` (spray charts available) or `unavailable` |
| `spray_status` / `spray_games_with_data` | Spray chart stage status and count of distinct games with offensive spray rows loaded (NULL = stage did not run / pre-migration) |
| `plays_status` / `plays_games_expected` / `plays_games_covered` | Plays/pitch-detail stage status and coverage (covered/expected) |
| `plays_errors` | Count of per-game errors during the plays stage (NULL = stage did not run / pre-migration) |
| `reconciliation_status` / `discrepancies_found` / `discrepancies_corrected` | Pitcher-attribution reconciliation pass result |
| `enrichment_status` | Tier-2 LLM enrichment result: `success`, `unavailable-no-key`, or `failed` |
| `completed_games` (M) | Distinct completed games on the fetched schedule -- games with a final score played to date |
| `completed_games_with_data` (N) | Distinct completed games for which at least one player stat row was loaded; N ≤ M |
| `season_id_used` | The canonical season slug (`seasons` FK) used for this generation |
| `identity_match_method` | `anchor` (team matched by gc_uuid or public_id) or `name_only` (matched by name+season only) |
| `error_stage` / `error_message` | Stage name and error message when the generation failed |

**N vs M -- why they differ**: M counts games with a final score on the schedule. N counts only games from which player stat rows were actually loaded for this team. A scouted opponent often has a public final score (M ≥ 1) but no GC scorebook (N = 0). The report footer's "Through {date} (N of M games)" and freshness date both anchor to N, not M, so "N of M games" literally means "games with scouting data out of games played."

#### `/admin/reports` -- per-stage detail and trust badges

Each report row in the admin Reports page shows the full run record inline when a run record exists (legacy reports before Migration 002 show no pipeline detail).

**Pipeline detail line** (rendered in small gray text below the report title):

```
Pipeline: crawl {status} ({boxscores_fetched} fetched) · load {status} ({load_errors} errors) · gc_uuid {status} · spray {status} ({spray_games_with_data} games) · plays {status} ({covered}/{expected}, {plays_errors} errors) · recon {status} ({corrected}/{found}) · enrich {status}
Games: {N} of {M} with data · season {season_id}
```

The four new count columns (`boxscores_fetched`, `load_errors`, `plays_errors`, `spray_games_with_data`) are NULL for reports generated before Migration 003 (E-236); those fields show as blank in the pipeline detail line.

**Operator-only trust-flag badges** (orange, below the pipeline line):

| Badge | What triggered it | Tooltip text |
|-------|------------------|-------------|
| `name-only match` | `identity_match_method = 'name_only'` — team matched by name + season with no gc_uuid/public_id anchor | "Team matched by name only — no gc_uuid/public_id anchor (possible wrong-team risk)" |

**Operator "degraded" indicator** (orange, shown alongside the status badge when `overall_status = 'completed'` but one or more per-stage statuses are `partial` or `failed`):

The report is shareable and coaches can open it, but some pipeline stages had errors or produced incomplete data. This badge is computed at read time from the per-stage status columns — it is not stored in the database. It is **operator-only** and never appears on the coach-facing report page.

**Status column badges**:

| Badge | Meaning |
|-------|---------|
| Ready (green) | Generation completed; report is shareable |
| Ready + Degraded (green + orange) | Completed and shareable, but one or more pipeline stages were partial or failed — operator should review the pipeline detail line |
| Generating... (yellow) | Pipeline still running |
| Failed (red) | Pipeline encountered a fatal error |
| No games (amber) | Generation completed but found N = 0 games with scouting data (see below) |
| Expired (gray) | Past the 14-day expiry window |

#### `bb report list` -- run columns in CLI output

`bb report list` uses the same `list_reports_with_runs` join as the admin UI. Each entry now includes the full `report_generation_runs` column set (all NULL for pre-Migration-002 reports) plus `error_message` from the `reports` table itself. Per-stage status, trust flags, and error details are all accessible in CLI output.

#### The `no_games` terminal outcome

When a generation completes the crawl and load stages successfully but finds N = 0 (zero completed games with player stat data), it produces a **`no_games`** outcome. The page content now distinguishes two cases:

| Case | Condition | Coach-facing page message |
|------|-----------|--------------------------|
| **No games on record** | M = 0 (no completed games on the schedule at all) | "No completed games found for {team} this season. If this looks wrong, verify the team URL and try again." |
| **Games played, no box score data** | M > 0 but N = 0 (games have a final score but no GC scorebook) | "No box score data is available for {team}'s {M} games yet. GameChanger may not have scorebook entries for this team." |

In both cases:
- `reports.status` is set to `no_games`.
- The run record's `overall_status` is `completed` (not `failed`) — the pipeline ran correctly; no data is a data condition, not a pipeline error.
- The **View** and **Copy link** actions in `/admin/reports` are active — the link is shareable.
- `bb report generate` exits **0** and prints the shareable URL (prior to E-236 it exited 1 for `no_games` outcomes).

**Hard-FAILED outcome (all boxscores blocked)**: If M > 0 completed games exist but every boxscore fetch returned a blocked/403/auth-expiry response (i.e., `boxscores_fetched = 0` with M > 0), the report **hard-fails** rather than producing a `no_games` page. The `overall_status` is set to `failed`, no shareable page is written, and `bb report generate` exits 1. This is operator-actionable: re-authenticate (`bb creds login`) and re-run, or verify the team's GC access level.

This situation (genuine `no_games`) is normal for early-season teams, teams with a public schedule but no GC scorebook, or an incorrect team URL. It is not a bug.

#### Coach-footer ↔ operator linkage

The coach-facing report footer (visible to anyone with the report link) shows a generic degraded-confidence line when the name-only identity match flag is set:

> ⚠️ Data accuracy may be limited. Contact your operator to verify before the game.

This line appears **only** when `identity_match_method = 'name_only'`. The footer never names the specific flag — coaches see only the generic warning and are directed to contact the operator.

The **operator** sees the specific flag(s) as orange badges in `/admin/reports`. When a coach reaches out citing the degraded-confidence warning, check the report row in the admin UI to see which badge(s) are shown, then investigate using the table below:

| Operator flag | Root cause | How to investigate |
|--------------|-----------|-------------------|
| **name-only match** | `ensure_team_row_with_provenance()` matched the team to an existing DB row by name + season year only, with no gc_uuid or public_id anchor. The wrong team could be matched if two teams share a name in the same season. | Check whether `public_id` on the matched team row matches the URL you generated the report for: `sqlite3 data/app.db "SELECT id, name, season_year, public_id, gc_uuid FROM teams WHERE id = <team_id>"`. If the public_id is wrong or missing, the report may have used a different team's row. |

---

## User Role Management

The admin UI enforces role-based access. Two roles exist:

| Role | Access |
|------|--------|
| `admin` | Full access: reports management, user management. |
| `user` | Read-only: standalone reports (via shared link). Cannot access admin routes. |

### Granting Admin Access

Admin access is granted via either of two mechanisms (both are checked):

1. **`ADMIN_EMAIL` environment variable** (bootstrap path): If the authenticated user's email matches `ADMIN_EMAIL` in `.env`, they receive admin access regardless of their database role. Use this to bootstrap the first admin account.

2. **Database role** (ongoing): Set `role = 'admin'` on the user's row. Once set, the user has permanent admin access even if `ADMIN_EMAIL` is changed or removed.

To promote a user to admin via SQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';  <!-- pii-ok -->
```

After promotion, the user's Role column on the Users page shows `admin`.

### Role Field in User Forms

The **Users** page (`/admin/users`) displays a **Role** column. The **Add User** form and **Edit User** form both include a Role field (radio: Admin / User, default: User).

**Self-demotion guard**: An admin cannot set their own role to `user` via the edit form -- a server-side validation error prevents accidental lockout.

### Revoking Admin Access

Change the user's role to `user` on the Edit User page (`/admin/users/{id}/edit`). The change takes effect immediately on the next request.

---

## Credential Rotation

### GameChanger API Tokens

GameChanger credentials expire frequently. When API calls start failing with authentication errors:

1. Log in to [web.gc.com](https://web.gc.com) in a browser.
2. Open DevTools -> Network tab -> copy any API request as cURL.
3. Save to `secrets/gamechanger-curl.txt` (or pass inline with `--curl`).
4. Run:

```bash
python scripts/refresh_credentials.py
```

Also available as `bb creds import`.

5. Verify with the smoke test:

```bash
python scripts/smoke_test.py
```

6. If the app is running, restart it to pick up the new `.env` values:

```bash
docker compose restart app
```

**Auto-recovery note**: If `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` are present in the Docker environment (i.e., set in `.env` and passed through by Docker Compose), the system automatically performs the full login flow when the refresh token expires. This means routine refresh-token expiry does not require manual intervention -- the next sync or API call triggers re-authentication automatically. Keep these credentials in `.env` for ongoing resilience, not just one-time setup.

### Cloudflare Service Tokens

Cloudflare Access service tokens (`CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`) have an expiry set at creation time (typically 1 year). To rotate:

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) -> Access -> Service Tokens.
2. Create a new token (or refresh the existing one).
3. Update `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` in `.env` on the server.
4. Restart the stack: `docker compose restart`.
5. Verify API access through the tunnel.

The Cloudflare Tunnel token (`CLOUDFLARE_TUNNEL_TOKEN`) does not expire unless revoked.

## Database Backup and Restore

### Backup

Create a timestamped copy of the database:

```bash
python scripts/backup_db.py
```

Also available as `bb db backup`.

This copies `data/app.db` to `data/backups/app-<timestamp>.db`. The backups directory is created automatically and is git-ignored.

### Restore

To restore from a backup:

```bash
# 1. Stop the application
docker compose down

# 2. Replace the database with the backup
cp data/backups/app-2026-03-02T140000.db data/app.db

# 3. Restart the application
docker compose up -d
```

### Verify a Restore

```bash
sqlite3 data/app.db "PRAGMA integrity_check; PRAGMA journal_mode;"
```

A healthy database returns `ok` and `wal`.

### Development Database Reset

For local development, drop and recreate the database with seed data:

```bash
python scripts/reset_dev_db.py
```

Also available as `bb db reset`.

This script has a production safety guard: if `APP_ENV=production`, the `--force` flag is required.

For full details, see [docs/database-restore.md](../database-restore.md).

## Troubleshooting

### App is unreachable

1. **Check Docker is running**: `docker info` -- an error means the Docker daemon is down.
2. **Check container status**: `docker compose ps` -- the `app` service must show `Up`.
3. **Check app logs**: `docker compose logs app` -- look for startup errors or migration failures.
4. **Check port conflicts**: `lsof -i :8001` -- if occupied, stop the conflicting process.
5. **Restart the app**: `docker compose restart app`, then `curl -s http://localhost:8001/health`.

### Health check returns 503

The health endpoint (`GET /health`) returns 503 when the database is unreachable or uninitialized:

```json
{"status": "error", "db": "error"}
```

- Verify the database file exists at `data/app.db`.
- Check if migrations have been applied: `sqlite3 data/app.db "SELECT * FROM _migrations;"`.
- The app container mounts `./data:/app/data` -- make sure the host directory exists and is writable.

### GameChanger API errors

- **Credential expired**: Run `python scripts/refresh_credentials.py` (or `bb creds import`) and then `python scripts/smoke_test.py`.
- **Rate limited**: The HTTP session factory handles rate limiting automatically with 1--1.5 second delays between requests. If you hit rate limits, increase the delay: adjust `min_delay_ms` and `jitter_ms` in `src/http/session.py`.
- **Unknown endpoint error**: Check [docs/api/README.md](../api/README.md) for the current endpoint documentation.

### Cloudflare Tunnel not connecting

- Check cloudflared logs: `docker compose logs cloudflared`.
- Verify `CLOUDFLARE_TUNNEL_TOKEN` is set in `.env`.
- In the Cloudflare dashboard (Networks -> Tunnels), the tunnel status should show Healthy.
- See [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md) for detailed troubleshooting.

### Database is corrupted

1. Backup the current state (even if corrupted): `cp data/app.db data/app.db.corrupted`
2. Check integrity: `sqlite3 data/app.db "PRAGMA integrity_check;"`
3. If integrity check fails, restore from a backup (see above).
4. If no backup exists, reset the database: `python scripts/reset_dev_db.py` (or `bb db reset`)

## Monitoring

The production stack is lightweight and does not include a dedicated monitoring service. Use the following manual checks:

### Health Endpoint

```bash
curl -s http://localhost:8001/health
# or through the tunnel:
curl -s https://[CONFIGURE: your domain here]/health
```

Expected: `{"status": "ok", "db": "connected"}` with HTTP 200.

### Docker Compose Logs

```bash
# All services
docker compose logs

# Follow live logs for the app
docker compose logs -f app

# Last 50 lines from a specific service
docker compose logs --tail=50 cloudflared
```

### Container Status

```bash
docker compose ps
```

All services should show status `Up`. The app service should also show `(healthy)`.

### Database Size

```bash
ls -lh data/app.db
```

For the expected data volume (~30 games x 4 teams x a few seasons), the database should remain well under 100 MB.

---

*Last updated: 2026-06-29 | Source: E-245 (bb data reload-annotated-pitches and bb data fix-self-games commands), E-243 (feature flag description: Most Likely Arms; post-merge spot-check note), E-241-05 (removed season_fallback run-record row, badge, coach-footer mention, and operator investigation row; removed derive_season_id_for_team_with_fallback() from operator table; updated season_id examples to year-only), E-240 (morning-run scheduled reports section), E-238 (bb report cleanup subsection), E-236 (partial per-stage status, boxscores_fetched/load_errors/plays_errors/spray_games_with_data columns, degraded badge, all-boxscores-blocked hard-fail, two-case no_games page, bb report generate exit-0 for no_games), E-235 (report generation run records, no_games outcome, trust-flag badges, coach-footer operator linkage), E-234 (bb report verify-aggregates), E-221 (team delete cross-perspective gate, cascade consolidation, retention flash message), E-199 (standalone reports section, cascade-delete behavior), E-198 (bb data reconcile, migration 012), E-195 (plays pipeline, migration 009, validate_plays_stats.py), E-173 (resolution write-through, auto-scout after linking, unified Find on GC resolve page), E-155 (duplicate team detection and merge UI), E-055 (unified CLI), E-028-03 (original), E-239 (removed dashboard, member-sync, opponent-discovery, programs management, opponent mapping, spray chart pipeline, plays pipeline, bb data scout/dedup/repair-opponents sections; reports-first reframe)*
