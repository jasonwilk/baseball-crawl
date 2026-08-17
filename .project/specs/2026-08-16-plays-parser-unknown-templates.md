<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Plays parser drops six `at_plate_details` templates it does not recognize

**Date**: 2026-08-16 · **Status**: `STUB` — measured from the restore-run log; needs a small
parser chunk. North-star work (byte-identical play ingestion): every dropped template is play
content GameChanger shows that we silently discard.
**Source**: trainer log sweep of `ephemeral/2026-08-16-report-restore/regenerate-20260816-204714.log`.
Counts below are from the 34-of-71 snapshot — re-derive from the FULL log before speccing.

## Measured firings (34 teams)

| template | firings | note |
|---|---|---|
| `Score changed to N-N` | 15 | scorekeeper manual score edit |
| `Special pinch runner UUID in for UUID` | 6 | a REAL substitution event, dropped — the parser is not even interpolating the placeholders |
| `UUID out on appeal at home` | 5 | appeal outs dropped outright |
| `UUID out on appeal at Nst` | 4 | " |
| `UUID out on appeal at Nnd` | 2 | " |
| `Count changed to N-N` | 1 | scorekeeper count edit |

Log shape: `WARNING src.gamechanger.parsers.plays_parser: Unknown at_plate_details template: game_id=... play_order=... template='...'`

## Why you should care

Appeal outs are OUTS — dropping them desyncs the play-derived out count for the half-inning,
which feeds the final-score derivation the half-pair chunk just made load-bearing. The pinch
runner substitution affects who is on base for every subsequent play. Both are exactly the
"closer to byte-identical" class, and both have a known template shape sitting in the log.

## Full-run update (2026-08-17) and a SECOND, worse parser gap

Template firings grew 46 → **108** over the full 71-team run (same six templates). And the
tail surfaced a heavier sibling this chunk should own too: **19 firings of
`Could not extract batter_id for game=... play_order=...; skipping.`** — that one drops the
WHOLE play, not one detail field. Same file, same fix pass.

## Out of scope

Whatever the FULL log adds to the template list rides this same chunk; new template classes
discovered later get their own measurement first.

## Progress log

- **2026-08-16** — Stubbed from the trainer's log sweep during the 71-team restore run.
