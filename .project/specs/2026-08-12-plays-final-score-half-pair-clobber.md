<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# A half-derived plays final score NULLs its stored counterpart

**Date**: 2026-08-12 · **Status**: `STUB` — found and verified, not scoped. **Source**: codex
review of the opponent-roster-dedup chunk (2026-08-12), which reviewed the committed range as
well as the working tree. Routed out rather than bundled, on the operator's ruling: it is the
plays chunk's code, and its RED test belongs with the plays work.

## Why you should care

**It is latent TODAY and the full regenerate is what fires it.** All 2,464 `game_perspectives`
rows are NULL right now (the backfill stub `2026-08-11-plays-final-score-backfill.md` records the
same fact), so nothing has been clobbered yet. The first thing that will re-derive these columns
at scale is the full regenerate in the "Regeneration hazard — RULED 2026-08-12" sequence — so
this wants to land BEFORE that regenerate, not after it. Landing it after means the regenerate
writes the damage this fixes.

## The defect, verified in code

`PlaysLoader._persist_final_score` (`src/gamechanger/loaders/plays_loader.py:~246-258`) writes the
pair with:

```sql
ON CONFLICT(game_id, perspective_team_id) DO UPDATE SET
    plays_final_home_score = excluded.plays_final_home_score,
    plays_final_away_score = excluded.plays_final_away_score
WHERE excluded.plays_final_home_score IS NOT NULL
   OR excluded.plays_final_away_score IS NOT NULL
```

Both columns are assigned from `excluded` unconditionally, and the guard is `OR`. So an
`excluded` pair of `(5, NULL)` landing on a stored `(NULL, 7)` writes `(5, NULL)` — **a real
stored away score becomes NULL.**

A half-pair is representable, not hypothetical: `PlaysParser._derive_final_score` ends with
`return play.get("home_score"), play.get("away_score")` — two INDEPENDENT `.get`s on the first
non-inert play, so a payload carrying one score key and not the other yields exactly that shape.
Whether real payloads do this is **UNMEASURED** — that is the first question this chunk owes.

It also contradicts the function's own docstring three lines above, which promises the
all-or-nothing behavior the `OR` does not deliver: *"The pair is written together because both
values come from the SAME play; per-column COALESCE would mix a fresh value with a stale one"*
and *"the write is one-way"*.

## The likely fix, and why it is not obviously one character

`OR` → `AND` makes the write all-or-nothing as documented, and is the shape the docstring already
describes. But `AND` also means a half-derived pair writes NOTHING, discarding a real score we
did derive. Decide deliberately between:

- **`AND`** — all-or-nothing, matches the docstring, discards a known half.
- **Per-column guards** — write each column only when its own `excluded` value is non-NULL. This
  is the "mix a fresh value with a stale one" case the docstring explicitly REJECTS; if it is
  chosen anyway, that docstring must change with it, and the reasoning for the reversal recorded.

⚠ **`NULL` is load-bearing provenance on these columns** (`.claude/rules/data-model.md`): NULL
means "not derived", and it must stay distinguishable from a real 0. Any fix that makes a NULL
mean two different things is worse than the defect.

## Verification owed

1. A RED test driving the half-pair through `_persist_final_score` onto a populated row.
2. Measure whether a half-derived pair occurs in real payloads before choosing the fix — the
   choice above turns on it.
3. Full suite (touches `src/`).
4. Whether the sibling backfill stub should absorb this rather than run separately.
