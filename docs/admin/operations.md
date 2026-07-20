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

For the full Cloudflare Tunnel and Zero Trust Access setup, see [cloudflare-access-setup.md](cloudflare-access-setup.md).

## Feature Flags

Feature flags are set as environment variables in `.env`. Values `1`, `true`, or `yes` (case-insensitive) enable the flag; anything else or absent disables it.

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_PREDICTED_STARTER` | off | Shows the Most Likely Arms section on standalone scouting reports. Temporary flag while the rest-days fix (E-214) is verified in production. Remove once verified stable. |
| `FEATURE_PITCHER_OUTINGS` | off | Shows the per-pitcher Outings Breakdown section (game-by-game outing log + season rate line) on standalone scouting reports. Off by default until proven; see the coaching how-to `docs/coaching/pitcher-outings-breakdown.md`. Source: E-265. |

**Post-merge spot-check**: If `FEATURE_PREDICTED_STARTER` is enabled alongside an LLM key, open one generated report for a youth or travel opponent and verify the narrative block contains no program-specific brand names. One-time check after deploying E-243.

## Data Maintenance

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

### Backfilling Game Dates (`bb data backfill-game-dates`)

*Last updated: 2026-07-06 | Source: E-253 (E-253-11)*

`bb data backfill-game-dates` re-derives the venue-local `game_date` for existing `games` rows from the recoverable UTC instant (`start_time`), correcting a historical mis-derivation where an evening game filed under the *next* day's UTC date -- skewing rest-days math, the 7-day rolling window, and cross-perspective dedup at UTC midnight. E-253-04 fixed the derivation going forward for newly-loaded games; this command corrects existing rows.

**Three-tier re-derivation model**:

1. `start_time` present + `timezone` present -> clean re-derivation via the venue-local converter (`derive_local_date`).
2. `start_time` present, `timezone` NULL -> re-derive using the operating-timezone default (`OPERATING_TIMEZONE` env, default `America/Chicago`).
3. `start_time` NULL -> no recoverable instant. The row is left **untouched** and counted/reported as skipped -- the command never fabricates a date.

**Default mode is dry-run** (previews changes, writes nothing):

```bash
bb data backfill-game-dates
```

**Execute mode** applies corrections:

```bash
bb data backfill-game-dates --execute
```

**Output:**

```
game_date Backfill Summary (DRY-RUN):
  Games processed: 214
  Rows that WOULD be updated: 31
  Rows already correct: 178
  Skipped (start_time NULL, un-correctable): 5
  Skipped (start_time unparseable): 0

Dry-run only. Re-run with --execute to apply the corrections.
```

**Idempotent**: Safe to run multiple times -- only rows whose re-derived date differs from the stored value are updated, so a second run is a no-op. Mirrors the `bb data reload-annotated-pitches` (E-245) operator-maintenance precedent -- `bb data backfill-appearance-order`, the command this note originally cited, was removed in E-256.

**Does not re-run dedup**: This command corrects stored `game_date` values only. It does not re-run player or game dedup. A corrected date that shifts a game's 7-day rolling-window membership is the intended correction, not a regression.

**Custom database path**:

```bash
bb data backfill-game-dates --db /path/to/app.db
```

**When to run**: Once, on the live database, as a one-time post-E-253-04 correction of historical rows. Run the dry-run first to preview the scope of changes, then `--execute` to apply.

### Merging Duplicate Game Rows (`bb data merge-duplicate-games`)

*Last updated: 2026-07-13 | Source: E-261 (E-261-04)*

`bb data merge-duplicate-games` is a one-time operator repair pass over a database already damaged by two cross-perspective dedup defects: the same real-world game persisted twice under different `game_id` values (once per team perspective that loaded it), and `game_stream_id` values clobbered by the pre-fix redirect. It runs two repair actions in one pass:

1. **Merges duplicate game pairs.** Detects historical cross-perspective duplicate `games` rows -- grouped by `(season_id, game_date, unordered team pair)`, the same natural key the live loader dedups on -- and merges each clean pair via the canonical `merge_duplicate_game` helper (`src/db/game_merge.py`). A pair is only merged when it passes offline same-game corroboration: disjoint single perspectives, scores within a 1-run tolerance on one side (with the other side exact), and near-matching play counts. All three are required.
2. **Restores poisoned `game_stream_id` values.** A tracked-perspective game is self-keyed (`game_stream_id == game_id`) before the redirect bug; the pre-fix clobber overwrote some of these with a different game's id. Rows whose poisoned value corroborates as an actual redirect source (another row's `game_id`, or a source id merged away earlier in the same run) are reset to `game_stream_id = game_id`. Member-perspective games are never touched.

**Default mode is dry-run** (prints the merge plan and stream-id restores, writes nothing):

```bash
bb data merge-duplicate-games
```

**Execute mode** applies the merges and restores:

```bash
bb data merge-duplicate-games --execute
```

**Refusals are not failures.** An ambiguous group -- three or more rows sharing the same date/team-pair key (a possible doubleheader), or a two-row pair that fails the offline corroboration checks -- is left unmerged and reported, never guessed at. Refused groups appear in the dry-run preview and, on `--execute`, each produces one WARN-level log line. A run with refusals but no failures still exits 0.

**Continue-per-item failure model.** Each merge and each stream-id restore runs under its own try/except with a per-item rollback on error (mirrors `bb data fix-self-games`). One failed item does not abort the rest of the run, but the command exits non-zero if any item failed.

**When to run**: as a one-time historical cleanup after seeing a degraded or erroring report attributable to duplicate games (the reports admin UI showing a doubled-up game, or a report generation error tracing back to a duplicate `games` row), or proactively once after upgrading past E-261 to clean up damage from the fixed defect. Dry-run first to review the plan, then `--execute` to apply.

**Closure check**: run `bb report reconcile-scoreboard` before and after, per the [Reconciliation Scoreboard](#reconciliation-scoreboard-bb-report-reconcile-scoreboard) one-way ratchet below -- merging duplicate games should hold steady or improve `no_plays_units` as perspectives consolidate onto a single game row; it must never regress a gated stat.

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

**No post-merge aggregate step.** Season aggregates are derived at query time from per-game rows since the E-259 cutover (there is no stored `player_season_*` table to recompute or commit) -- `--execute` commits each merged component as it goes and stops there.

### Reconciliation Pipeline (`bb data reconcile`)

`bb data reconcile` compares plays-derived stat aggregates against boxscore ground truth and (optionally) corrects pitcher attribution errors. It is an operator diagnostic and repair tool.

**Note**: The plays ingestion pipeline is alive -- every report generation runs it (parser in `src/gamechanger/parsers/plays_parser.py`, loader in `src/gamechanger/loaders/plays_loader.py`; E-245 repaired pitch-annotation handling in place). Reconciliation applies to any completed game with plays data loaded, current or historical.

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

### Reconciliation Scoreboard (`bb report reconcile-scoreboard`)

*Last updated: 2026-07-09 | Source: E-257 (reconciliation scoreboard)*

`bb report reconcile-scoreboard` is the standing, repeatable **measurement** of how faithfully the plays-derived stats reconstruct GameChanger's official box scores -- the concrete metric behind CLAUDE.md's north-star Operating Principle ("Always Get Closer to Byte-Identical Play Ingestion"). It replaces the one-off manual `recon.sql` baseline from E-245 with a standing command. Read-only: it never writes to the database.

**Do not confuse this with `bb data reconcile` above.** They measure/do different things:

| | `bb data reconcile` | `bb report reconcile-scoreboard` |
|---|---|---|
| Purpose | Corrective **engine** -- detects and (optionally) fixes pitcher attribution errors | **Measurement + gate** -- tracks plays-vs-boxscore fidelity over time and blocks a regression |
| Writes to the DB? | Yes, in `--execute` mode (reassigns `plays.pitcher_id`) | Never -- always read-only |
| Output | Per-game/per-signal discrepancy detail, stored in `reconciliation_discrepancies` | A fidelity scoreboard (per-stat exact% / abs-Δ) + three axis counters, diffed against a committed baseline |

**What it computes**: per-stat fidelity for pitching (`BF`, `SO`, `BB`, `H`, `HBP`) and batting (`AB`, `H`, `BB`, `SO`, `HBP`) -- each as `exact%` (share of units where the plays-derived value equals the boxscore value) and `abs-Δ` (sum of absolute differences) -- plus three axis counters, the north-star "trend toward zero" targets:

| Axis counter | Meaning |
|---|---|
| `dropped_pitch_events` | Annotated pitches stranded as `event_type='other'` (the E-245 parser gap) |
| `no_plays_units` | Boxscore units (pitcher or batter) with zero matching plays rows -- the coverage gap |
| `self_games` | Games where `home_team_id == away_team_id` -- an opponent-resolution failure |

Batting `AB` and `H` are labeled in the table as carrying a known residual (quick-scored/abandoned-PA scorekeeper noise) -- this label is informational and is never suppressed.

**Commands**:

```bash
# Human-readable table + gate verdict
bb report reconcile-scoreboard

# Machine-readable JSON to stdout (table suppressed; gate verdict goes to stderr)
bb report reconcile-scoreboard --json

# Overwrite the committed baseline with this run's values
bb report reconcile-scoreboard --update-baseline
```

**The gate**: every non-`--update-baseline` run diffs the fresh scoreboard against a committed baseline JSON at `.project/baselines/reconciliation-scoreboard.json` and exits non-zero on a regression. It is a **one-way ratchet** -- only a *worsening* number trips it; an improvement or holding steady always passes. It fires on:
- A rise in abs-Δ for any gated stat: batting `{AB, H, BB, SO}`, pitching `{H, SO, BB}`.
- A rise in either ratcheted axis counter: `dropped_pitch_events`, `no_plays_units`.
- `self_games > 0` -- gated as a **hard zero**, independent of the baseline (a self-game is always a bug, never an acceptable floor).

`BF` and `HBP` are shown in the table as context but are not gated. Pitch-level fidelity is covered via the `dropped_pitch_events` counter rather than blended into the stat ratchet.

**Baseline lifecycle** (the operator owns every snapshot -- no agent auto-refreshes the baseline):

1. **First use**: the gate has nothing to diff against until a baseline exists. Run `bb report reconcile-scoreboard --update-baseline` against the live DB, review the written `.project/baselines/reconciliation-scoreboard.json`, and commit it. Until this file is committed, every gated run exits non-zero (code 3) with a bootstrap message rather than passing silently.
2. **Ongoing**: run the gate before and after any ingestion, parser, or reconciliation change. If a fix legitimately improved a number, re-snapshot with `--update-baseline`, review the JSON commit diff (this diff is the human review point -- it shows exactly which floor moved and by how much), and commit it so the improved number becomes the new floor.

**Exit codes**:

| Code | Meaning |
|---|---|
| `0` | Pass -- no gated regression |
| `1` | Gated regression, OR a run precondition failed (e.g. database not found) |
| `3` | No committed baseline exists yet (first-use bootstrap) |
| `4` | Committed baseline is present but malformed or missing an expected value |

**When to run**: this is a manual operator diagnostic, not a CI gate -- the live database is not available in CI. Run it around any change to play ingestion, parsing, or reconciliation logic, per CLAUDE.md's Operating Principle that every such change must move plays-derived stats closer to (never further from) GameChanger's official box scores.

## Morning-Run Scheduled Reports

*Last updated: 2026-06-20 | Source: E-240 (morning-run scheduled reports)*

`bb report morning-run` is a cron-invoked command that runs each morning and generates a fresh scouting report for every LSB team's game scheduled on that date. It is the forward operational surface of the system: the crontab is the config, the operator's job is to keep opponent mappings current, and the end-of-run summary email is the heartbeat.

### What morning-run does

For each team URL passed as an argument, the command:

1. For non-dry-run invocations, validates that the operator-alert channel can deliver (aborts before touching any team data if not -- see [Alerting-channel preflight](#alerting-channel-preflight-non-dry-run-only) below).
2. Verifies credentials once (preflight check) before touching any team data.
3. Reads the team's GameChanger schedule and opponent registry.
4. Filters to games whose LOCAL date matches the target date (today by default -- the venue-local operating date; see the timezone note below).
5. For each upcoming opponent on that date, runs the resolution ladder to find the opponent's `public_id`.
6. For auto-resolved opponents, calls the existing `generate_report` pipeline -- the same pipeline as `bb report generate`.
7. Records each slot's outcome to `scheduled_report_runs` and sends operator alerts.

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

A 6 AM default is appropriate for most weekday high school and Legion games (4--7 PM starts): the reports are ready hours before game time.

**Timezone note**: the default target date (used whenever `--date` is omitted) is the venue-local operating date, not the container's UTC date. Production containers run on UTC, so without this a run late in the venue's evening would otherwise default to tomorrow's games. Set `OPERATING_TIMEZONE` in `.env` to an IANA timezone name (e.g. `America/Chicago`, `America/New_York`) to control it; it defaults to `America/Chicago` when unset. An invalid timezone value logs a warning and falls back to the default rather than crashing. `--date YYYY-MM-DD` always overrides the computed default regardless of `OPERATING_TIMEZONE`.

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

### Alerting-channel preflight (non-dry-run only)

Before touching any team data, a non-dry-run invocation validates that the operator-alert channel -- the end-of-run summary's delivery path -- can actually deliver. If it cannot, the run aborts immediately with a non-zero exit and a clear error message, instead of running to completion behind a silently-dead heartbeat.

The channel is misconfigured when:

- `ADMIN_EMAIL` is unset -- there is no operator recipient, so every alert (including the summary) would be skipped.
- In production (`APP_ENV=production`): `MAILGUN_API_KEY` or `MAILGUN_DOMAIN` is unset -- Mailgun requires both to actually send. (In development, stdout logging is a valid delivery path when Mailgun is not configured, so only a missing `ADMIN_EMAIL` fails this check there.)

`--dry-run` skips this check entirely -- it sends no summary, so there is no channel to validate.

### Reading the end-of-run summary email

The end-of-run summary is **always attempted** at the end of every non-dry-run morning run -- including when the run body crashes partway through. The send is wrapped so a crash still triggers a summary, with the failure surfaced in its detail lines, and the send is retried once before being declared failed. Its **absence** (or a non-zero exit from the command -- see Exit codes below) is the missed-run signal -- if no email arrived by mid-morning on a game day, the cron job did not run cleanly.

In production, an unconfigured Mailgun (`MAILGUN_API_KEY` unset) is treated as a failed send rather than a false "sent" -- the alerting-channel preflight above should catch this before the run even starts, but the summary send itself no longer reports success for a message it could only log to stdout.

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

**Action**: refresh credentials (`bb creds refresh`; if the refresh token itself is dead, `bb creds import` or `bb creds setup web`) and re-run manually, or wait for the next scheduled run after credentials are restored.

A per-team 403 (ForbiddenError) is distinct from a preflight failure and is not treated as an auth expiry: the team is skipped and counted in the `denied` tally, but the run continues for other teams.

### Exit codes

`bb report morning-run` exits non-zero in any of the following cases, so a cron wrapper or monitor can key on the exit code as a run-health signal (previously the command exited 0 regardless of outcome):

| Condition | Exit code |
|-----------|-----------|
| Database not found at the resolved path | 1 |
| Alerting channel misconfigured (preflight, non-dry-run only) | 1 |
| GameChanger credentials not configured | 1 |
| Preflight credential check failed | 1 |
| The run body raised an unexpected exception | 1 |
| The end-of-run summary email failed to send after one retry (non-dry-run only) | 1 |
| Invalid `--date` value | 2 |
| Normal completion (per-opponent failures are counted but do not fail the run) | 0 |

A non-zero exit and a missing summary email are two independent signals of a run that needs investigation -- either one is enough to act on.

### Idempotency

Re-running `morning-run` on the same date is safe. For each `(own_team_id, opponent_root_team_id, game_date)` slot, if a prior run already generated a non-expired report, the re-run skips regeneration (`delivery_status = skipped`). A slot is only regenerated when its prior report has expired or was never generated successfully.

---

## Schema Migrations

Migrations are numbered SQL files in `migrations/`, applied automatically in order by `migrations/apply_migrations.py` on every container startup. Applied migrations are tracked by filename in `_migrations` (`sqlite3 data/app.db "SELECT * FROM _migrations;"`), so re-running the app never re-applies one. The current set is `001`-`011`:

| Migration | File | What it does |
|-----------|------|---------------|
| 001 | `001_initial_schema.sql` | The full schema (E-220 rewrite). Squashed every prior migration -- including the pre-E-220 numbering that some historical epic notes in this repo still cite -- into one baseline file. Covers every table, including `appearance_order`, `plays`/`play_events`, `reconciliation_discrepancies`, and the `spray_charts` columns described below under 009. |
| 002 | `002_report_generation_runs.sql` | Adds `report_generation_runs` (per-stage report telemetry). See [Report Generation Run Records](#report-generation-run-records) below. |
| 003 | `003_report_run_count_columns.sql` | Adds four count columns to `report_generation_runs`: `boxscores_fetched`, `load_errors`, `plays_errors`, `spray_games_with_data`. See [Report Generation Run Records](#report-generation-run-records) below. |
| 004 | `004_webauthn_challenge_store.sql` | Adds `webauthn_challenges`, a TTL'd DB-backed passkey-challenge store. Replaces two in-process module-global dicts so passkey login survives multiple Uvicorn workers and app restarts mid-login. |
| 005 | `005_scheduled_report_runs.sql` | Adds `scheduled_report_runs` (one row per morning-run scheduled slot, recording resolution outcome and delivery status). See [Morning-Run Scheduled Reports](#morning-run-scheduled-reports) above. |
| 006 | `006_drop_season_fallback.sql` | Drops the unused `report_generation_runs.season_fallback` column, part of the E-241 cross-season-machinery de-scope. |
| 007 | `007_play_events_pitch_columns.sql` | Adds `pitch_type` and `pitch_speed_mph` to `play_events`. `bb data reload-annotated-pitches` (above) populates these for historical rows; new rows are populated at load time. |
| 008 | `008_drop_identity_opponent_season_type.sql` | Drops dead cross-season/identity schema: `players.gc_athlete_profile_id` (the de-scoped cross-team identity anchor), the `team_opponents` table (write-orphaned since E-239), and `seasons.season_type` (a write-only constant column). |
| 009 | `009_spray_chart_type_unique.sql` | Widens the `spray_charts` UNIQUE constraint to `(event_gc_id, perspective_team_id, chart_type)`. Fixes a bug where the `offensive` and `defensive` rows for the same ball-in-play event collided on the old two-column key, silently dropping the defensive row. No backfill needed -- coverage self-heals on the next report generation. |
| 010 | `010_game_dedup_backstop.sql` | Adds a partial UNIQUE index on `games(game_stream_id)` (non-null only) as a backstop against a cross-process race (admin UI + CLI + morning-run cron all writing the same SQLite file) that could otherwise create duplicate rows for the same real game. |
| 011 | `011_drop_season_aggregate_tables.sql` | Drops the stored `player_season_batting` / `player_season_pitching` tables. The season line is now derived at query time from the per-game tables (`src.api.db.get_season_batting` / `get_season_pitching`) -- E-259's query-time cutover retired every writer, so the stored tables were a pure derived cache with zero readers left. The migration refuses (rolls back, no `_migrations` row) if either table holds a non-re-derivable member (`full`/`supplemented`) row at apply time. `bb report verify-aggregates`, the stored-vs-recomputed parity diagnostic these tables existed to support, is retired along with them -- there is no longer a stored copy to drift from the per-game data. |

Full column-level schema history, including the pre-E-220 migration numbering that some epic notes reference, is in [architecture.md: Schema Changes](architecture.md#schema-changes).

## Standalone Reports

Standalone reports are shareable, frozen scouting snapshots generated on demand for any GameChanger team. They do not require a database-tracked team. Manage them at `/admin/reports`.

### Generating a Report

From the admin Reports page, paste a GameChanger public URL or public ID slug and click **Generate**. The system crawls the team's schedule and stats, renders a self-contained HTML file, and saves it to `data/reports/`. Generation typically takes 10-30 seconds depending on how many games the team has played.

**CLI alternative**:

```bash
bb report generate <public_id>
```

Reports expire 14 days after generation. After expiry, the link returns a 404 and the row is eligible for cleanup.

### Reconcile-at-Load: Generating a Report Can Now Delete Stale Data

*Last updated: 2026-07-20 | Source: E-267 (reconcile-at-load against the fresh crawl)*

**Generating a report is now a destructive operation.** Every report generation calls `ScoutingLoader.load_team()`, which re-scouts the opponent's GameChanger data and loads it. As of E-267, that same load now reconciles the freshly-crawled data against what is already in the database and hard-deletes anything the fresh crawl no longer contains, across three grains:

- **Game grain** -- a game the fresh schedule no longer lists is retired: the `games` row and its full child surface (batting/pitching lines, play-by-play events, spray charts, and reconciliation records) are hard-deleted.
- **Player-line grain** -- a per-player batting or pitching stat row the fresh boxscore no longer lists is retired.
- **Roster grain** -- a roster player the fresh roster crawl no longer lists is retired from the roster display. Their season stat lines are untouched -- season stats are independent of roster membership.

This corrects an accumulate-only bug where removed games, dropped stat lines, and departed players used to persist forever, silently inflating query-time season aggregates and W-L records. It is the fix, not a new failure mode -- but it changes report generation's risk profile: previously read-and-write-forward only, generating a report can now remove rows a prior run loaded.

**Forward-only, not a repair.** The reconcile only compares the current re-scout against what is already loaded. It never rewrites or retroactively corrects data loaded before E-267 shipped. To start from a clean data slate instead, see [Purging Scouting and Report Data](#purging-scouting-and-report-data-bb-db-purge-scouting) below.

**Bias to refuse.** A retire happens only when the fresh crawl is corroborated healthy -- it fetched successfully, returned a non-empty payload, and did not shrink catastrophically against what is already loaded (the roster grain applies its own stricter absolute cap of two departures per run in addition to the shrink ratio, since a 12-15 player roster tolerates almost no slack). Any doubt keeps the existing data untouched and logs a WARNING explaining the refusal -- a transient failure, a postponed game, or a partial/degraded crawl never causes data loss. A rescheduled game (moved date, same real game) is matched and updated in place rather than treated as a removal.

**Fidelity gate.** Reconcile changes are validated against the [Reconciliation Scoreboard](#reconciliation-scoreboard-bb-report-reconcile-scoreboard) above -- a retire correction should hold or improve plays-vs-boxscore fidelity; it must never regress it.

**Known, deliberate limitations** (not defects):

- **A game loaded from both team perspectives is never retired.** If a removed/voided game is in the database because both LSB's crawl and the opponent's own crawl loaded it, the game-grain retire refuses to delete it -- hard-deleting the `games` row would destroy the other team's data too. The game persists in recent form, season lines, W-L, and the freshness count until cleaned up separately. This cannot create a safety gap: a stale extra game can only ADD an appearance to workload/rest-day tracking, never hide one, so it can never mask a needed rest day -- the error direction is strictly toward more caution. This refusal is not purely a cost, either: the same still-another-perspective check also guards a game whose id looks absent from its own team's fresh schedule for a reason unrelated to removal -- a cross-perspective twin merge (E-261) can leave a game stored under the *other* perspective's id -- catching it before a hard delete would fire. A future change that narrows this refusal to close the limitation above would also remove that protection. Tracked as a possible follow-on (IDEA-154).
- **Roster departures are only reconciled on a load that produced boxscores.** A team with no completed games yet keeps its full prior roster. This is deliberate and fail-safe -- a stale roster is never a wrongly-deleted one. In practice it is not visible for a genuinely new preseason team, since a team with zero completed games gets the "no games" page rather than a full report; do not expect a preseason roster cut to disappear from the grid before the team has played.
- **A stale "Through {date}" line or an unexpectedly high N is possible in a narrow case** where a prior player-line row cannot be matched against any block in a re-scout payload. This is a pre-existing predicate gap (IDEA-156), not introduced by this epic, and it never affects a stat *value* -- season lines, workload, and pitching history are all correctly scoped by team -- only the reported game count and freshness date can drift in that one narrow case.

### Report Plausibility Warnings

*Last updated: 2026-07-09 | Source: E-257 (E-257-03)*

At generation time, the report generator range-checks the team-level headline pitching/batting rates and logs an operator-facing WARNING (via the `logging` module) when a rate falls outside a plausible band:

- First-pitch-strike% outside 30-75%
- Pitches-per-PA outside 3.0-4.5

The WARNING names the rate, its value, and the expected range, ending with "review before sharing." It is **advisory only** -- the report still renders and ships unchanged; there is no auto-clamp and no render block.

**What to do**: treat a WARNING as "double-check this report before sharing it," not as an error to fix. It reproduces the human-eyeball catch that first flagged an 18x-off first-pitch-strike rate in a shipped report -- open the report and confirm the flagged rate looks right (or investigate the underlying game data) before handing it to a coach.

**Scope**: the check covers team aggregate rates only -- not per-pitcher or per-batter rows -- by design, since per-player checking would flag legitimate small-sample relievers as false positives.

This guard complements, and does not replace, the batch [Reconciliation Scoreboard](#reconciliation-scoreboard-bb-report-reconcile-scoreboard) diagnostic above: the scoreboard measures fidelity across the whole database on a schedule the operator controls, while this guard flags a single implausible report the moment it is generated.

### Listing Reports

```bash
bb report list
```

Shows all generated reports with their public ID, expiry date, and file status.

### Deleting a Report

Click **Delete** on any report row in the admin Reports page. A confirmation dialog appears before the deletion runs.

**What happens when you delete a report** depends on whether the associated team has other data in the system:

When both conditions below are true, deletion is a **full cascade** -- the report, the HTML file, and the team row plus all its associated data are removed in a single transaction:

| Condition | What it checks |
|-----------|---------------|
| Team is not active (`is_active = 0`) | Active teams are never auto-deleted |
| No other reports reference this team | This was the only report for this team |

If **either** condition fails, deletion is a **report-only** operation: only the report row and the `data/reports/` HTML file are removed. The team and its stats remain in the database.

This behavior is automatic -- no operator decision is required. The system applies these two guard conditions on every delete.

**Typical use case**: A report generated for a tournament team that is not on your schedule will usually satisfy both conditions. Deleting the report cleans up the team data completely. A report generated for a team that another active report still references will only remove the report file -- the scouting data stays.

These two guards check exactly what their names say (team inactivity and no other referencing report) -- they are not a complete guarantee against deleting a team whose games are shared with another team's data.

**CAUTION -- shared-game teams are not yet fully protected.** The cascade has no guard against deleting a team whose games are shared with another tracked team's data (a shared-game/live-reports eligibility check is planned but not yet implemented -- tracked in CE-3/E-253). Until that guard lands, do not delete reports for a team you know shares games with another team in the system; verify manually first if you are unsure.

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

**Hard-FAILED outcome (all boxscores blocked)**: If M > 0 completed games exist but every boxscore fetch returned a blocked/403/auth-expiry response (i.e., `boxscores_fetched = 0` with M > 0), the report **hard-fails** rather than producing a `no_games` page. The `overall_status` is set to `failed`, no shareable page is written, and `bb report generate` exits 1. This is operator-actionable: re-authenticate (`bb creds refresh`; if the refresh token itself is dead, `bb creds import` or `bb creds setup web`) and re-run, or verify the team's GC access level.

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
4. Import:

```bash
bb creds import
```

5. Verify:

```bash
bb creds check --profile web
```

`bb creds check --profile web` is an end-to-end liveness probe (`GET /me/user`, plus local JWT-expiry and client-key diagnostics) for the profile this recipe just imported -- a clean run confirms the new web credentials work; no separate smoke test is needed. Use `--profile web` here, not the bare multi-profile `bb creds check`: bare `bb creds check` exits 0 if **any** profile is valid, so a healthy mobile profile can mask a broken web import -- and the report/scouting flow runs on the web profile.

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

Create a timestamped copy of the database. The script is installed only inside the app container, so invoke it via `docker compose exec`:

```bash
docker compose exec -T app python scripts/backup_db.py
```

Also available as `bb db backup`.

This copies `data/app.db` to `data/backups/app-<timestamp>.db`. The backups directory is created automatically and is git-ignored.

**This must run on a schedule, and its output must be copied off the host disk.** `data/backups/` lives inside the same host-mounted `./data` volume as `app.db` -- a backup left there is destroyed alongside the database on disk loss. See [production-deployment.md: Routine backup](production-deployment.md#routine-backup) for the required daily cron cadence and the off-host copy step.

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

For local development, drop and recreate the database. The result is empty -- no seed data is loaded (E-228):

```bash
python scripts/reset_dev_db.py
```

Also available as `bb db reset`.

This script has a production safety guard: if `APP_ENV=production`, the `--force` flag is required.

For full details, see [docs/database-restore.md](../database-restore.md).

### Purging Scouting and Report Data (`bb db purge-scouting`)

*Last updated: 2026-07-20 | Source: E-267 (E-267-06: purge scouting/report data, preserve identity + auth)*

`bb db purge-scouting` is the clean-slate command for a **live** database: it deletes every scouting and report row (games, players, teams, seasons, rosters, plays, spray charts, reports, and 12 related tables -- 20 tables total) in one transaction, while leaving user identity and authentication intact so coaches stay logged in across the wipe. Use it to start from a clean data slate -- for example, after upgrading to E-267 to clear out data from before the reconcile-at-load fix landed -- rather than repairing historical rows one at a time. Use `bb db reset` instead when destroying logins is acceptable (typically local dev only).

```bash
bb db purge-scouting
```

**What survives**: `users`, `passkey_credentials`, `magic_link_tokens`, `sessions`, `webauthn_challenges`, the `programs` bootstrap row, and `_migrations`. Logins, passkeys, and active sessions are unaffected.

**What is purged**: `reports`, `report_generation_runs`, `scheduled_report_runs`, `games`, `game_perspectives`, `player_game_batting`, `player_game_pitching`, `plays`, `play_events`, `spray_charts`, `reconciliation_discrepancies`, `team_rosters`, `scouting_runs`, `opponent_links`, `crawl_jobs`, `coaching_assignments`, `user_team_access`, `teams`, `players`, `seasons`.

**`user_team_access` is purged, not preserved -- read this before running on a database with non-admin users.** Login survives (users, passkeys, magic links, and sessions are all kept), but non-admin **team-access grants** are deleted along with everything else. A non-admin user loses access to every team until re-granted; grants are not automatically restored as teams regenerate on a later re-scout. Admins are unaffected -- an admin sees every team regardless of `user_team_access`.

**Production is refused by default**, mirroring `bb db reset`:

```bash
bb db purge-scouting --force
```

Without `--force` against a production database, the command refuses and exits non-zero. This check normalizes `APP_ENV` (case and whitespace), so a variant like `" Production "` is still caught, not just the exact string `production`.

**Report HTML files are unlinked -- all of them, not just expired ones.** Every purged report's on-disk HTML file in `data/reports/` is removed as part of the purge (`bb report cleanup` above only removes files for *expired* reports; this command removes them all, since every report row is about to be deleted). The unlink step runs *after* the database transaction commits, so a crash between commit and unlink can leave orphaned HTML files with no corresponding database row. **If a purge is interrupted after confirmation but before it finishes, manually sweep `data/reports/` for orphaned files** -- nothing else will ever clean them up automatically, since `bb report cleanup`'s `cleanup_expired_reports()` works off `reports` rows, and the purge has already deleted them.

**Single transaction.** All 20 tables are deleted inside one transaction -- a mid-purge database failure rolls back cleanly and the database is left unchanged (only the post-commit file-unlink step carries the orphan risk described above).

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

- **Credential expired**: Run `bb creds import` and then `bb creds check --profile web`. See [Credential Rotation](#credential-rotation) above.
- **Rate limited**: The HTTP session factory handles rate limiting automatically with 1--1.5 second delays between requests. If you hit rate limits, increase the delay: adjust `min_delay_ms` and `jitter_ms` in `src/http/session.py`.
- **Unknown endpoint error**: Check [docs/api/README.md](../api/README.md) for the current endpoint documentation.

### Cloudflare Tunnel not connecting

- Check cloudflared logs: `docker compose logs cloudflared`.
- Verify `CLOUDFLARE_TUNNEL_TOKEN` is set in `.env`.
- In the Cloudflare dashboard (Networks -> Tunnels), the tunnel status should show Healthy.
- See [cloudflare-access-setup.md](cloudflare-access-setup.md) for detailed troubleshooting.

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

*Last updated: 2026-07-20 | Source: E-267 (E-267-05: documented the forward reconcile-at-load behavior in Standalone Reports -- report generation is now destructive, its bias-to-refuse posture, and the deliberate cross-perspective/preseason-roster/stale-freshness limitations -- and added the `bb db purge-scouting` clean-slate command section under Database Backup and Restore), E-261 (E-261-04: bb data merge-duplicate-games -- offline duplicate-game merge + poisoned game_stream_id restore), E-259 (E-259-06: removed the "Verifying Scouting Aggregate Integrity" section -- `bb report verify-aggregates` and the stored `player_season_*` tables it checked were retired in E-259-03/04; corrected the `bb data dedup-players` post-merge description now that season aggregates are query-time-derived, not recomputed-and-committed; added migration 011 to the Schema Migrations table), E-256-10 (struck the deleted `bb data backfill-appearance-order` runbook section -- the command was removed in E-256-02 -- and re-pointed the `backfill-game-dates` precedent reference to `bb data reload-annotated-pitches`; added the required-cadence + off-host-copy cross-reference to the backup section), E-253 (E-253-11: bb data backfill-game-dates), E-252 (morning-run OPERATING_TIMEZONE default date, alerting-channel preflight, non-zero exit-code contract, always-attempted summary email), E-250-05 (delete-report cascade updated from four guards to the two that survive migration 008's `team_opponents` drop -- removed the `team_opponents`-links and shared-games conditions), E-245 (bb data reload-annotated-pitches and bb data fix-self-games commands), E-243 (feature flag description: Most Likely Arms; post-merge spot-check note), E-241-05 (removed season_fallback run-record row, badge, coach-footer mention, and operator investigation row; removed derive_season_id_for_team_with_fallback() from operator table; updated season_id examples to year-only), E-240 (morning-run scheduled reports section), E-238 (bb report cleanup subsection), E-236 (partial per-stage status, boxscores_fetched/load_errors/plays_errors/spray_games_with_data columns, degraded badge, all-boxscores-blocked hard-fail, two-case no_games page, bb report generate exit-0 for no_games), E-235 (report generation run records, no_games outcome, trust-flag badges, coach-footer operator linkage), E-234 (bb report verify-aggregates), E-221 (team delete cross-perspective gate, cascade consolidation, retention flash message), E-199 (standalone reports section, cascade-delete behavior), E-198 (bb data reconcile, migration 012), E-195 (plays pipeline, migration 009, validate_plays_stats.py), E-173 (resolution write-through, auto-scout after linking, unified Find on GC resolve page), E-155 (duplicate team detection and merge UI), E-055 (unified CLI), E-028-03 (original), E-239 (removed dashboard, member-sync, opponent-discovery, programs management, opponent mapping, bb data scout/dedup/repair-opponents sections; reports-first reframe -- the plays and spray chart pipelines were NOT removed by E-239 and remain live), E-255-05 (Truth Sweep: replaced the phantom Migration 015/012/009/006 write-ups with a Schema Migrations table matching the real 001-010 files; corrected the false "plays pipeline removed in E-239" claim -- it is alive; fixed the `bb creds login` recovery reference -- no such subcommand, `bb creds refresh` first-line with `bb creds import`/`bb creds setup web` fallback; corrected "seed data" to "empty" for `bb db reset`; fixed the same-dir cloudflare-access-setup.md link now that both runbooks live in docs/admin/), E-262-07 (collapsed the GameChanger API Tokens credential-recovery recipe to `bb creds import` + `bb creds check --profile web` as the primary steps, dropping the docker-compose-exec-wrapped `refresh_credentials.py`/`smoke_test.py` script invocations as redundant; matched the Troubleshooting section's credential-expired one-liner to the same recipe; post-review remediation pinned the verify step to `--profile web` -- bare `bb creds check` exits 0 on any valid profile and can mask a broken web import, the same mixed-profile mask AC-4's Step 1d preflight fix already guards against)*
