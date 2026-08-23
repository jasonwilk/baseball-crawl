# Opponent identity resolution — the evidence ladder

**2026-08-22.** Method as actually used to resolve 51 name-only opponent teams to crawlable
`public_id`s for the exit-sheet cohort crawl (42 auto-verified, 9 escalated, all 51 resolved).
Developed across the in-devcontainer session, the operator, and the host session; recorded
here because the productized crawl (`bb report exit-sheets`, Track 2) and any future bulk
resolution needs it. Team names and team-scoped ids only; no player identifiers.

## The ladder, strongest evidence first

1. **Already crawled** — the team's full season is in the DB. Skip; zero ambiguity.
2. **Reciprocal schedule + exact score match** (PRIMARY; run on every candidate before any
   escalation): fetch the candidate's own public schedule
   (`GET /public/teams/{public_id}/games`, no auth) and look for a game on the disputed date
   whose score mirrors our own DB record. Near-certain identity proof — it is the candidate's
   OWN record showing the same real game, not an inference from ours.
3. **Roster overlap** (candidate-finder and tiebreak, never standalone proof): last-name +
   first-initial intersection between our observed opponent players and the candidate's
   public roster (≥50%, ≥3 names, 20% margin). In a batch of 51 it produced 6 ties and 3
   false negatives (0% overlap on the CORRECT team) — good for proposing candidates and for
   picking the more-complete of two duplicate listings, unreliable alone.
4. **Operator reverse-schedule check by eye** — the manual form of rung 2; it is what
   prompted automating rung 2. Start at rung 2 instead.
5. **Operator-supplied GameChanger URL** — the hard floor for teams absent from every search
   result. The API's documented limitation is real: manually-typed opponents never added via
   team lookup are unindexed and unfindable by search, full stop.

## Failure modes measured in this batch

- **Roster-overlap ties are usually one club listed twice on GC** — a complete listing plus
  an unscored/incomplete duplicate stub — not two different clubs. Rung 2 on both candidates
  separates them instantly (the real one has the scored mirrored game).
- **Near-zero overlap on the correct team happens** (0/10, 0/29 observed) when our observed
  player set for that opponent is thin or their roster listing is incomplete. Overlap-only
  designs wrongly reject correct matches.
- **Schedule names can be unrelated to GC canonical names**: a summer opponent recorded as
  "Millard West Juniors" is "SportClips Wildcats 2026 16U" on GameChanger. No string
  similarity survives that; only rung 2 or rung 5 resolves it.
- **public_id collisions across the runlist**: two locally-named opponent rows can resolve to
  ONE real team (schedule aliases). Check for this BEFORE crawling: a second crawl of the
  same public_id adds no data (a crawl loads the team's full schedule regardless of which
  alias triggered it) and its only effect is triggering the opponent-identity-divergence
  stub-merge — one of the repo's named destructive seams — which should never ride silently
  inside a mechanical batch. Operator ruling this batch: skip the duplicate crawls, leave the
  stub rows for the dedup machinery to handle deliberately.

## The redesign lesson

Skip "overlap-only, escalate ties to the operator" entirely: run the reciprocal-score check
on every search candidate first. In this batch that would have resolved 3 of the 9
escalations with no operator involvement and rendered the rest immediately legible as
"genuinely unindexed — need a URL" instead of numeric ties requiring interpretation.
Ordering: evidence FROM the candidate's own record > inference from OUR observations >
operator judgment > operator-sourced URL as the floor.
