# E-255-08: data-engineer own-memory truth sweep

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`TODO`

## Description
After this story is complete, data-engineer's own memory (`.claude/agent-memory/data-engineer/`) describes current reality: token refresh IS programmatically possible, the backup mechanism is the real one (not Litestream), the Core Entity Model names only existing tables, and the `season_aggregate_writers` note reflects that no live caller writes `full`/`supplemented` rows post-E-239.

## Context
Own-memory edit routed to data-engineer under the own-memory carve-out, scoped from DE's own docket recon (relayed via main), proposed as ONE story across the four DE memory files. The `PlayerTeamSeason` mappings in `endpoint-schema-notes.md` and `MEMORY.md` were already scrubbed in E-250 — do NOT redo. The Core Entity ghost-table fix (item 3 below) shares the ghost-entity list with baseball-coach memory (E-255-07) and the DE charter (E-255-03) — keep all three consistent per epic TN-7.

## Acceptance Criteria
- [ ] **AC-1**: Given `etl-patterns.md` L5-8 asserting "Programmatic refresh NOT possible: unknown signing key" (now FALSE — `src/gamechanger/signing.py` implements the gc-signature HMAC-SHA256 with a known Base64 client key, and `token_manager.py` auto-refreshes before expiry), when corrected, then a grep of `etl-patterns.md` for `not possible`, `unknown signing key`, `unknown key` returns zero hits, and the text points to `token_manager.py` + `signing.py`. **Do NOT assert a new specific token lifetime** (unmeasured) — the downstream "14 days / batch within lifetime / without expiring mid-run" framing is dropped, not replaced with a new number.
- [ ] **AC-2**: Given `MEMORY.md` L7's nonexistent "Litestream backup", when corrected, then a grep of `.claude/agent-memory/data-engineer/` for `litestream` (case-insensitive) returns zero hits and the text names the real mechanism (`scripts/backup_db.py` file backup).
- [ ] **AC-3**: Given `MEMORY.md` L44-60's Core Entity Model listing the ghost tables `Lineup`/`PlateAppearance`/`PitchingAppearance` (none exist in the squashed schema `migrations/001_initial_schema.sql`; real tables are `player_game_batting`/`player_game_pitching`/`plays`/`play_events`), when corrected by REPLACING the ghost names with the real tables (commit to replacement, not conceptual-relabeling — a relabel would keep the token and fail the check), then a grep of `MEMORY.md` for `PlateAppearance|PitchingAppearance|Lineup` returns zero hits. The already-correct player/cross-team wording is left unchanged. Consistency: matches E-255-07 (coach memory) and E-255-03 (DE charter pointer) per TN-7.
- [ ] **AC-4**: Given `season_aggregate_writers.md`'s deleted-caller list (`SeasonStatsLoader` in `season_stats_loader.py` and member-sync Hook-2 in `trigger.py` were both DELETED in E-239), when corrected, then the file no longer describes those as live writers and notes that no writer produces `full`/`supplemented` rows post-E-239 (those enums are now READ-only — guarded in `season_aggregates.py`, ranked in `player_dedup.py`); the live recompute callers named are the surviving ones (`src/cli/data.py`, `player_dedup.py`, `scouting_loader.py`).
- [ ] **AC-5**: Given `MEMORY.md` L10-18's migration inventory says "next migration is 009 / 001–008" (stale — live set is 001–010, next = 011), when corrected, then the inventory matches `ls migrations/` (the same phantom-migration class story 01 fixes elsewhere; `MEMORY.md` is a touched file so the epic's "zero stale migration tokens in touched files" criterion applies) — prefer dropping the concrete number per the self-rotting/glob-authoritative convention.
- [ ] **AC-6**: Given the re-verify mandate, when any cited item is found already-fixed, the story notes record it as discharged and the prose is left unchanged.

## Technical Approach
Read each memory file in full. Verify the caller list against current `src/` (the deleted vs surviving writers) and the entity set against `migrations/001_initial_schema.sql`. The broader `data-engineer.md` agent-def Core Entities table refresh is IDEA-092 (out of scope) — this story is the DE *memory* files only; keep the narrow charter pointer (E-255-03) consistent.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/data-engineer/etl-patterns.md`
- `.claude/agent-memory/data-engineer/MEMORY.md`
- `.claude/agent-memory/data-engineer/season_aggregate_writers.md`

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The three grep checks (AC-1/2/3) return zero hits
- [ ] No new token lifetime asserted (AC-1 caveat)
- [ ] Ghost-entity list consistent with coach memory + DE charter (TN-7)
- [ ] `PlayerTeamSeason` NOT re-touched (already done in E-250)

## Notes
Confirm exact memory filenames by listing `.claude/agent-memory/data-engineer/`. IDEA-092 (broader data-engineer.md Core Entities table) is explicitly out of scope; the narrow charter pointer fix lives in E-255-03.
