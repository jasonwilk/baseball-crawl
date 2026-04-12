---
paths:
  - "src/gamechanger/loaders/**"
  - "src/gamechanger/parsers/**"
  - "src/reports/**"
  - "src/pipeline/**"
  - "src/db/**"
  - "src/cli/**"
  - "src/api/routes/**"
  - "src/api/db.py"
  - "src/reconciliation/**"
---

# Perspective Provenance

## Core Invariant

Every per-player stat INSERT (`player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`) MUST include `perspective_team_id` -- the `teams.id` of the team whose API call produced the data. This is a NOT NULL column with no default; omitting it causes a hard insertion error.

Season aggregate tables (`player_season_batting`, `player_season_pitching`) do NOT carry `perspective_team_id`. Perspective filtering happens at aggregation time via `WHERE perspective_team_id = ?` in the query.

## Why This Exists

GameChanger returns different player UUIDs, player names (initials vs. full), and structural keys depending on which team's API perspective is used. Loading the same game from two team perspectives produces two valid but distinct sets of player data. Without perspective tagging, these sets collide silently, creating phantom duplicates and corrupted aggregates. Four prior epics (E-211, E-215, E-216, E-219) attempted symptom-level fixes before E-220 established perspective provenance as the structural solution.

## MUST Constraints

1. **Every stat INSERT includes `perspective_team_id`**. The value is always the team whose credentials or `public_id` were used to fetch the data from the API. For member-team pipelines, this is the member team's `teams.id`. For scouting pipelines, this is the scouted team's `teams.id`.

2. **UNIQUE constraints include `perspective_team_id`**. The same `(game_id, player_id)` pair can legitimately appear twice with different perspectives. ON CONFLICT clauses must reference the full constraint including `perspective_team_id`.

3. **Season aggregates filter by perspective**. `_compute_season_aggregates()` and any future aggregation queries MUST include `WHERE perspective_team_id = ?` to prevent double-counting when the same game has been loaded from multiple perspectives.

4. **New loaders follow this pattern**. Any new loader that INSERTs into the four stat tables must accept `perspective_team_id` and pass it through to every INSERT. There is no opt-out.

5. **`game_perspectives` junction table tracks loaded perspectives**. After loading stat data for a game, the loader records `(game_id, perspective_team_id)` in `game_perspectives`. This enables idempotency checks and perspective-aware queries.

## Perspective-Specific vs. Stable Fields (Reference)

Per API Scout analysis (E-220 TN-6):

| Category | Fields |
|----------|--------|
| **Stable** | `event_id` (= `game_stream.game_id`), stat numbers (scores, batting/pitching lines) |
| **Perspective-specific** | player UUIDs, player names (initials vs. full), `home_away`, `owning_team_score`/`opponent_team_score` labels, boxscore top-level keys (slug vs. UUID), `team_players` keys in plays data, `game_stream.opponent_id` |
| **Uncertain** | Public games `id` field -- treat as potentially perspective-specific |

When assessing a new endpoint or data source, classify each field against this table. Perspective-specific fields require `perspective_team_id` tagging; stable fields do not.

## Pipeline Patterns

### Scouting and Reports Pipelines (In-Memory)

The scouting pipeline and report generator use in-memory crawl-to-load with no disk intermediary. Crawlers return data structures directly to loaders, eliminating stale-file contamination. Game IDs come from crawl results, not filesystem globs.

### Own-Team Pipeline (Disk Cache)

The member-team pipeline retains disk caching (`data/raw/`) because crawl and load are separate CLI invocations. Perspective tagging on every INSERT prevents contamination even when files from different runs coexist on disk.

### Plays Pipeline

The plays loader uses whole-game idempotency (`SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1`). Combined with `GameLoader._find_duplicate_game()` collapsing cross-perspective games to a single `game_id`, the second load of the same perspective is skipped. Different perspectives of the same game each get their own plays rows.

## Code Review Checklist

When reviewing code that touches stat tables or loaders:

- [ ] Every INSERT into `player_game_batting`, `player_game_pitching`, `spray_charts`, or `plays` includes `perspective_team_id`
- [ ] ON CONFLICT clauses reference the full UNIQUE constraint including `perspective_team_id`
- [ ] Aggregation queries filter by `perspective_team_id` where appropriate
- [ ] New fields are classified as stable or perspective-specific per the reference table
- [ ] `game_perspectives` is updated after loading stat data
- [ ] Scouting/reports crawl-to-load uses in-memory data, not disk reads
