---
name: boxscore-key-form
description: What decides a boxscore top-level key's slug-vs-UUID form is UNKNOWN; "public GC presence" and "linked vs hand-typed" are both REFUTED. A UUID-form opponent key is a local root_team_id, never a canonical gc_uuid.
metadata:
  type: reference
---

# Boxscore / plays top-level key form -- what is and is not established

Measured live 2026-08-03, web profile, read-only, against
`GET /game-stream-processing/{event_id}/boxscore`.

## Sample

**140 games across all 28 scouted perspective teams**, 0 fetch errors. Every payload
had **exactly 2** top-level keys. Sampling was stratified (5 random completed games per
perspective team, fixed seed), games dated 2025-04 through 2026-07.

## ESTABLISHED

- **Key form does NOT mark which side the envelope belongs to.** `slug+UUID` 126/140,
  **`slug+slug` 14/140 = 10.0%**, spread across 9 of the 28 perspective teams. This is
  the claim the docs should carry; shape-based own-vs-opponent detection is what
  discarded 72 opponents' envelopes before `10c32f3`.
- **A UUID-form opponent key is a per-account LOCAL id, not the opponent's canonical
  `gc_uuid`.** It equals `pregame_data.opponent_id` from `GET /events/{event_id}`
  (10/10 in the subsample checked), which equals the `root_team_id` on the scoring
  team's own opponent record (**36/36**). `GET /teams/{that UUID}` returned **404 in
  16/16**, while the same call on four canonical `gc_uuid`s we hold returned 200 with a
  matching `public_id` **4/4** -- so the instrument discriminates and the 404s are real.
  **126/126** UUID-form keys matched no `teams.gc_uuid` in the dev DB. This is the E-211
  `gc_uuid` contamination path; `opponent-scouting.md`'s old "store any UUID
  encountered" guidance was the instruction that caused it, and is retired.
- **A slug-form key IS a real `public_id`**: `GET /public/teams/{slug}` returned 200
  for 6/6 of the slug-form opponent keys tested.
- **`GET /teams/{team_id}/opponent/{opponent_id}` works for NON-MANAGED teams** -- the
  only reachable dual-entry (linked vs hand-typed) signal for a scouted team. See
  [[operational-notes]] and that endpoint's doc.

## REFUTED -- do not reintroduce either

1. **"A team with a public GameChanger presence is slug-keyed, otherwise UUID-keyed"**
   (the mechanism `10c32f3`'s doc sweep asserted). Opponents that we scout by their own
   `public_id` -- so unambiguously public -- came back UUID-keyed. Cleanest instances
   are cross-perspective twins, where the payload owner's opponent is another scouted
   team of ours.
2. **"Linked via GC team lookup -> slug key; typed by hand -> UUID key."** Tested with
   the dual-entry signal above on 36 resolved games: **22 of 24 UUID-keyed opponents
   were LINKED.** Linkage does not predict key form.

The surviving one-way correlations are NOT established and must not be documented as
mechanism: all 12 slug-keyed opponents were linked, and both hand-typed opponents were
UUID-keyed (n=2 -- far too small to mean anything).

**So: treat the form as unpredictable. Classify by IDENTITY only** (own `public_id`,
then own `gc_uuid`; the remaining key is the opponent's), as
`GameLoader._detect_team_keys` does. See [[boxscore-empty-shape]].

## Probe artifact to not misread

8 of the 140 payloads matched NEITHER of the perspective team's identifiers. All 8 were
**cross-perspective twins** (`game_perspectives` lists both teams, but `games`
stores a single `game_stream_id`, which belongs to one side), so the fetch returned the
OTHER team's perspective. That is an artifact of joining perspectives to the stored
stream id -- **not** a loader condition, and not evidence for the rung-4 fallback firing
in production.
