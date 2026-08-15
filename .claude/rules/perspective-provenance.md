---
paths:
  - "src/gamechanger/loaders/**"
  - "src/gamechanger/parsers/**"
  - "src/reports/**"
  - "src/db/**"
  - "src/cli/**"
  - "src/api/routes/**"
  - "src/api/db.py"
  - "src/reconciliation/**"
---

# Perspective Provenance

## Core Invariant

Every per-player stat INSERT (`player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`) MUST include `perspective_team_id` -- the `teams.id` of the team whose API call produced the data. This is a NOT NULL column with no default; omitting it causes a hard insertion error.

There are no stored season-aggregate tables (E-259 retired `player_season_batting`/`player_season_pitching`); season totals are derived at query time by SUMming the per-game tables, which DO carry `perspective_team_id`. Perspective filtering therefore happens in the aggregating query via `WHERE perspective_team_id = ?` -- omitting it double-counts.

## Why This Exists

GameChanger returns different player UUIDs, player names (initials vs. full), and structural keys depending on which team's API perspective is used. Loading the same game from two team perspectives produces two valid but distinct sets of player data. Without perspective tagging, these sets collide silently, creating phantom duplicates and corrupted aggregates. Four prior epics (E-211, E-215, E-216, E-219) attempted symptom-level fixes before E-220 established perspective provenance as the structural solution.

## MUST Constraints

1. **Every stat INSERT includes `perspective_team_id`**. The value is always the team whose credentials or `public_id` were used to fetch the data from the API -- for the scouting/reports pipeline, the scouted team's `teams.id`.

2. **UNIQUE constraints include `perspective_team_id`**. The same `(game_id, player_id)` pair can legitimately appear twice with different perspectives. ON CONFLICT clauses must reference the full constraint including `perspective_team_id`.

3. **Season aggregates filter by perspective**. The query-time season readers `get_season_batting` / `get_season_pitching` (`src/api/db.py`) and any future aggregation query over the per-game tables MUST include `WHERE perspective_team_id = ?` to prevent double-counting when the same game has been loaded from multiple perspectives. This was the #1 hazard of the E-259 query-time cutover -- a season sum that omits the filter silently doubles a player's line with nothing crashing (guarded by a dedicated two-perspective test).

4. **New loaders follow this pattern**. Any new loader that INSERTs into the four stat tables must accept `perspective_team_id` and pass it through to every INSERT. There is no opt-out.

5. **`game_perspectives` junction table tracks loaded perspectives**. After loading stat data for a game, the loader records `(game_id, perspective_team_id)` in `game_perspectives`. This enables idempotency checks and perspective-aware queries.

## Perspective-Specific vs. Stable Fields (Reference)

Per API Scout analysis (E-220 TN-6):

| Category | Fields |
|----------|--------|
| **Stable** | `event_id` (= `game_stream.game_id`), stat numbers (scores¹, batting/pitching lines) |
| **Perspective-specific** | player UUIDs, player names (initials vs. full), `home_away`, `owning_team_score`/`opponent_team_score` labels, boxscore top-level keys (slug vs. UUID), `team_players` keys in plays data, `game_stream.opponent_id`, public games `id` (the `id` field returned by `GET /public/teams/{public_id}/games`) -- the same real game gets a different `id` per team's schedule; post-E-239 the public path is its **sole** populator, so this is now **definitively** perspective-specific (was "Uncertain"). The stable cross-perspective key is `event_id` (= `game_stream.game_id`) in the Stable row above. |

¹ Scores are stable across the **two authenticated perspectives** of a single game. They are NOT guaranteed byte-identical across independent PUBLIC scorebooks of the same game -- two separately-kept scorebooks can disagree by a run (E-261 observed 12-4 vs 12-5). Treat a cross-source public score as near-stable, not byte-identical.

When assessing a new endpoint or data source, classify each field against this table. Perspective-specific fields require `perspective_team_id` tagging; stable fields do not.

## Pipeline Patterns

### Scouting and Reports Pipelines (In-Memory)

The scouting pipeline and report generator use in-memory crawl-to-load with no disk intermediary. Crawlers return data structures directly to loaders, eliminating stale-file contamination. Game IDs come from crawl results, not filesystem globs.

### Plays Pipeline

The plays loader uses whole-game idempotency (`SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1`). Combined with `GameLoader._find_duplicate_game()` collapsing cross-perspective games to a single `game_id`, the second load of the same perspective is skipped. Different perspectives of the same game each get their own plays rows. The same collapse means a deduped game's event id has no `games` row — generator stages keyed off source event ids must remap through `LoadResult.redirect_map` (see `.claude/rules/architecture-subsystems.md`, Reports Package, E-244). ⚠️ Since 2026-08-15 that map is NOT cross-perspective-only and its keys are not always the incoming source id: TWO routes hard-delete a row and key an entry on a deleted id — the opponent-identity divergence **promotion** (deleting the canonical), and the ordinary **redirect** when its in-pipeline twin merge deletes a pre-existing source row. Both also rewrite entries POINTING AT the deleted row so a chain does not strand. Read a key as "does not resolve to a `games` row", never as "belonged to another perspective".

## Code Review Checklist

When reviewing code that touches stat tables or loaders:

- [ ] Every INSERT into `player_game_batting`, `player_game_pitching`, `spray_charts`, or `plays` includes `perspective_team_id`
- [ ] ON CONFLICT clauses reference the full UNIQUE constraint including `perspective_team_id`
- [ ] Aggregation queries filter by `perspective_team_id` where appropriate
- [ ] New fields are classified as stable or perspective-specific per the reference table
- [ ] `game_perspectives` is updated after loading stat data
- [ ] Scouting/reports crawl-to-load uses in-memory data, not disk reads
