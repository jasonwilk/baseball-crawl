# Rung (c) auto-accept: the flow doc documents two filters the code does not have

**Date:** 2026-08-04 · **Status:** STUB — needs a product decision, not an implementation.
⚠ **Priority raised the same day**: `/code-review` established that this missing pair is now the
*only* thing standing between a single wrong search hit and a **terminal** wrong auto-resolve.
Read "What the entity-class filter changed" before triaging this as low-stakes cleanup.
**Source:** surfaced by the spec review of `2026-08-04-search-entity-class-filter.md`; sharpened
by the `/code-review` of that chunk. Confirmed by direct read of every artifact cited.
Nothing was changed either way.

## The divergence

`docs/api/flows/opponent-resolution.md` ("Auto-Accept Criteria") states that **all three**
conditions must hold before rung (c) auto-resolves an opponent:

1. **Exact name match** (case-insensitive) between `opponent_links.opponent_name` and `result.name`
2. **Season year match**: `result.season.year` matches the member team's `season_year`
3. **Single result**: exactly one result remains after both filters

`_resolve_via_search()` in `src/gamechanger/opponent_ladder.py` implements **only criterion 3**
(now "exactly one TEAM hit", after the entity-class filter landed). It never compares
`result.name` to the stored opponent name, and never looks at `result.season.year`.

So the auto-accept bar in the code is **looser than the documented one**, and has been for as
long as the doc has said this. The divergence is pre-existing: the entity-class filter did not
create it and did not edit criteria 1 or 2.

⚠ **But do not read that as "this chunk does not affect it" — that inference is false**, and it
is why this file's priority moved. See below.

## What the entity-class filter changed about this

The entity-class chunk changed criterion 3's **population**, and criterion 3 is the only
criterion that exists. Three consequences, all established by the `/code-review` of that chunk:

1. **The accept surface WIDENED.** Before: `len(hits) != 1` — a result set of one team beside
   one organization was 2 hits, and fell to the operator queue. After: `len(team_hits) != 1` —
   the organization is dropped and the lone team **auto-resolves**. The predicate is unchanged;
   the population it counts is narrower. That was a deliberate, operator-settled trade (refusing
   whenever an organization appears would punt the `Showdown`/`League`-shaped queries — 43
   organizations, ~0 of them umbrellas — for nothing), and it stands. It is still a widening.
2. **The missing filters were the backstop for exactly that case.** A wrong single team hit is
   precisely what an exact-name match or a season-year match would catch. With neither
   implemented, **the single-team count is the entire gate.**
3. **The result is TERMINAL.** `resolve_opponent` treats any `opponent_links` row with a
   non-NULL `resolution_method` as cached (`src/gamechanger/opponent_ladder.py`, the
   `existing["resolution_method"] is not None` branch) and returns `from_cache=True` without
   re-attempting. So a wrong auto-resolve is **never retried and never re-surfaces to the
   operator** — it silently feeds scouting reports for the wrong opponent until someone notices
   by eye.

None of this makes the entity-class filter the wrong change — without it the same query would
have resolved to the *organization*, which is strictly worse. It does mean the safety argument
for leaving criteria 1 and 2 unimplemented is weaker than it was this morning.

## Why this was not "just fixed"

The two directions are not equivalent, and picking one is a product call:

- **Implement 1 and 2** — tightens auto-resolution. Fewer wrong-team auto-ingests, more
  opponents punted to the operator queue. Note the name filter interacts badly with the
  punctuation/Unicode-apostrophe quirk already documented in this repo: the indexed canonical
  name uses a curly apostrophe, so a naive exact-match against a stored straight-apostrophe
  name fails on real teams. A season-year filter also assumes `result.season.year` is populated
  and comparable, which is unverified on this path.
- **Correct the doc** — records that the single-team bar is the whole gate. Cheap and honest,
  but it deletes documented intent that may have been deliberate.

Choosing by coin-flip in the middle of an unrelated chunk is how a safety bar gets quietly
loosened or a working path quietly broken, so it was left alone and written down instead.

## What is needed before this is workable

- Which is authoritative — the doc's intent, or the code's behavior?
- If implementing: how many currently auto-resolving opponents would stop auto-resolving?
  Measure before changing; the live DB has **10 `opponent_links` rows, 0 of them `search`-method**
  (re-confirmed read-only 2026-08-04), so there is no production evidence either way yet and the
  real answer is "unknown". **Note what that zero actually means**: rung (c) has never written a
  durable row in this DB, so the widening above has **no known live victims** — and equally, no
  live evidence that it is safe. It is a forward-looking risk on a path that has not fired yet.
- A cheaper third option nobody has costed: leave the gate as-is but make a `search`-method
  resolution **non-terminal** (re-attemptable, or operator-visible for confirmation), which
  removes the stickiness without touching the accept criteria at all. This attacks consequence 3
  rather than consequences 1 and 2, and may be the better value.

## Out of scope

Do not implement any direction from this stub alone.

## Progress log

- **2026-08-04** — Stubbed. No code, no doc edit. Surfaced by spec review; both artifacts read
  directly to confirm the divergence is real and not a stale-doc misreading.
- **2026-08-04 (post-`/code-review`)** — **Priority raised; scope unchanged.** The review of the
  entity-class chunk established that criterion 3's population narrowed, that the accept surface
  therefore widened, and that a `search` resolution is terminal — so these two missing filters
  are the whole remaining gate. Added the "What the entity-class filter changed" section and a
  third candidate direction (make the resolution non-terminal). Corrected this file's own
  inference that the entity-class chunk left the divergence untouched: it left the *criteria*
  untouched and changed what they *guard*. Still no code, still no doc edit, still needs a
  product call.
