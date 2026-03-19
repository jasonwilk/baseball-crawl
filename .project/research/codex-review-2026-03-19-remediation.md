# Codex Review Remediation -- E-132 (2026-03-19)

**Epic**: E-132 (Fix Opponent Names Showing as UUIDs on Player Detail Page)
**Date**: 2026-03-19
**Review mode**: Uncommitted
**Status**: Complete -- all findings fixed

## Findings Tracker

| # | Finding | Severity | Disposition | Notes |
|---|---------|----------|-------------|-------|
| P1-1 | UUID-only boxscores mislabel both UUIDs with opponent name | P1 | FIXED | scouting_loader + backfill refactored |
| P1-2 | Backfill skips schedule-only team directories | P1 | FIXED | backfill discovers from opponents.json AND schedule.json |
| P2-1 | No UUID-only boxscore e2e test for scouting path | P2 | FIXED | 2 new tests in test_scouting_loader.py |
| P2-2 | No schedule-only or two-UUID backfill tests | P2 | FIXED | 4 new tests in test_backfill.py |

## Detail

### P1-1: UUID-only boxscores mislabel both UUIDs with opponent name
- **Disposition**: FIXED
- **Change summary**: `scouting_loader.py` -- `_record_uuid_from_boxscore_path()` now accepts `own_gc_uuid` param and skips own-team UUID; when gc_uuid=None with multiple keys, falls back to UUID-as-name for all. `backfill.py` -- `_merge_scouting_dir()` refactored to two-pass strategy excluding scouted team's own UUID from lookup.

### P1-2: Backfill skips schedule-only team directories
- **Disposition**: FIXED
- **Change summary**: `backfill.py` -- `build_name_lookup_from_raw_data()` now discovers team dirs from both `opponents.json` AND `schedule.json` globs.

### P2-1: No UUID-only boxscore end-to-end test for scouting path
- **Disposition**: FIXED
- **Change summary**: `test_scouting_loader.py` -- 2 new tests covering UUID-only boxscore path with opponent names (gc_uuid known and gc_uuid=None cases).

### P2-2: No schedule-only or two-UUID backfill tests
- **Disposition**: FIXED
- **Change summary**: `test_backfill.py` -- 4 new tests covering schedule-only dir discovery and multi-UUID scouting boxscore exclusion.

## Disposition Key

- **FIXED**: Finding addressed by implementer
- **DISMISSED**: Finding reviewed and determined not actionable (with reason)
- **FALSE POSITIVE**: Finding does not apply to the actual code (with reason)
