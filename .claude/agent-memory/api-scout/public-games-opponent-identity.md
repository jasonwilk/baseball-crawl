---
name: public-games-opponent-identity
description: GET /public/teams/{public_id}/games carries opponent NAME only (no public_id/root/progenitor); now returns upcoming games too. Refutes scheduler auto-resolve assumption.
metadata:
  type: project
---

# Public games endpoint: opponent identity verification (2026-06-12)

Verified live against team `WThfCgtHecNF` (34 records) for the morning-of-game scheduled-report design (FORWARD_PLAN.md Epic E).

**Fact:** `GET /public/teams/{public_id}/games` `opponent_team` carries `name` + optional `avatar_url` ONLY. No `public_id`, no `root_team_id`, no `progenitor_team_id`, no slug -- for ANY game, completed or upcoming, regardless of GC opponent entry mode (manual typing vs team lookup).

**Why:** The own-team public schedule cannot auto-resolve an opponent's `public_id`. The dual entry-mode signal (`progenitor_team_id` present=lookup, absent=manual) lives only in authenticated `GET /teams/{team_id}/opponents` + `/opponent/{opponent_id}`, and even there is a UUID not a slug. Authenticated `game-summaries.game_stream.opponent_id` is also a UUID (root namespace), not a public_id.

**How to apply:** A scheduler fed from the own-team public schedule must resolve opponents by `name` (POST /search, gc-uuid bridge, with name-match ambiguity + punctuation quirk) or fall back to operator input. There is NO public-schedule signal distinguishing manual vs lookup entries -- the public payload is mode-blind.

**Secondary correction (same probe):** This endpoint now returns UPCOMING/scheduled games too (game_status null, future start_ts, no score/has_videos_available), not "completed only" as the doc previously claimed. Earlier 32-record sample (QTiLIb2Lui3b, 2026-03-04) was likely a team with no upcoming games at capture time.

Doc updated: `docs/api/endpoints/get-public-teams-public_id-games.md` (added Opponent Identity section, caveats, upcoming-game example, fixed Known Limitations). See [[exploration-findings]] for opponent ID hierarchy context.

## Authenticated entry-mode signal + bridge (verified 2026-06-12, team qKrZuhgV6eke)

Where the manual-vs-lookup signal actually lives: **authenticated `GET /teams/{gc_uuid}/opponents`**. `progenitor_team_id` present = team-lookup (search-linked, auto-resolvable); **absent (key omitted, not null)** = manual entry. Use `o.get("progenitor_team_id")`.

Second data point on Epic E auto/manual ratio: Bennington D1 Training Reserves = **13/49 search-linked, 36/49 manual (~27% auto)**. Combined with the first public-schedule probe: a large fraction of opponents are manual and need name-based resolution or operator input.

Ground truth confirmed: game b5c0e6c2's opponent "Gretna" (root_team_id a8ab985f) had NO progenitor_team_id -> manual entry, as operator hypothesized. A game's `pregame_data.opponent_id` is in the **root_team_id** namespace; join it to `root_team_id` in the opponents list to read that record's progenitor.

**progenitor_team_id -> public_id bridge (CONFIRMED working path for NON-managed opponents):**
- WORKS: `GET /teams/{progenitor_team_id}` (Accept team:read) returns `public_id` directly. Feed that to `bb report generate`. Verified Berthoud Badgers 15U.
- 403: `GET /teams/{progenitor_team_id}/public-team-profile-id` -> Forbidden for non-managed teams (managed-only).

**Search gotcha:** the canonical INDEXED team name can differ from the web URL slug. "2026 Summer Bennington D1 Training Reserves" (slug) vs "Bennington D1 Training Reserves" (indexed) -- search on slug returned 0 hits; search on indexed name (from `GET /public/teams/{public_id}` name field) returned the match. The public profile's `id` field echoes the public_id slug, NOT a UUID. See [[search-endpoint-notes]].

Doc updated: `docs/api/endpoints/get-teams-team_id-opponents.md` (Entry-Mode Signal section, bridge subsection, redacted manual+lookup example, Known Limitations).

## Multi-team linked-vs-manual variance + ACCESS MATRIX (verified 2026-06-12, 4 LSB summer teams)

Operator pushback ("most coaches search-link") tested against his 4 LSB summer teams. Linked share VARIES WIDELY (27%-100%) -- no single typical ratio:
- Five Star Bath (role manager+family): 23/23 linked (100%)
- Braxter (fan): 16/32 linked (50%)
- Epp Foundation Jr (fan): 27/54 linked (50%)
- Lincoln Hotel 18U (fan): 25/33 linked (76%)
- Aggregate 4 LSB: 91/142 linked (64%). Bennington (prior probe) = 13/49 (27%).
Verdict: heavy search-linking is COMMON for LSB but not universal; Bennington's 73%-manual was a low outlier, not impossible. The manual share tracks opponents NOT in GC's searchable index (HS varsity programs: Bellevue West, Millard West, Elkhorn South) -- unindexed, so unlinkable by anyone.

**ACCESS MATRIX (overturns the relayed "manager-only" assumption):** `GET /teams/{gc_uuid}/opponents` returns 200 with FULL data (incl. progenitor_team_id) at FAN/follower level -- not just manager. Verified: 1 manager team + 3 fan teams all 200, identical field set, no degradation. So Epic-E rung-(a) auto-resolution works for any FOLLOWED team, not only managed teams. (Roles read from `GET /me/teams?include=user_team_associations`; needs Accept team:list version=0.10.0 -- wrong version 403s, looks like a permission error.) The relayed claim that opponents would 403 on family/follower teams was FALSE -- API is ground truth, coordinator relay carried no authority.

**Cross-team sibling recovery does NOT work (negative finding):** 15 opponent names shared across 2+ LSB teams, but 0 were manual-on-one / linked-on-sibling. Shared names are uniformly linked-everywhere or manual-everywhere. Scheduler cannot borrow a sibling's progenitor_team_id -- manual entries are unindexed, not merely un-linked-by-this-coach.

Doc updated again: `docs/api/endpoints/get-teams-team_id-opponents.md` (Authentication/Access Level section with role matrix; softened ratio claim to a 5-team variance table; cross-team negative finding).

## Placeholder/TBD share of manual entries (verified 2026-06-12, 4 LSB teams)

Operator hypothesis: many manual entries are TBD/bracket placeholders (re-check near game time, not operator-input failures). TESTED -- largely NOT borne out for LSB:
- Of 51 manual entries: ~46 real teams, ~3 placeholder (event labels "Papio Tournament" x2, "Tri-Cities Tournament"), ~2 ambiguous (short/odd tokens "East", "Carpet" -- likely truncated real names). ZERO classic TBD/TBA/"Winner Game N"/seed entries.
- Effective auto-resolution barely moves: excluding placeholders, 91/139 real opponents linked = 65% (vs 64% raw). ~46-48 real teams still need search/operator resolution.

**NO STRUCTURAL PLACEHOLDER FLAG (Task-4 confirmed):** manual records carry ONLY {root_team_id, owning_team_id, name, is_hidden} -- the ONLY difference from a linked record is absence of progenitor_team_id. No event_type, no is_tbd, no game-link field. Placeholder detection is name-heuristic ONLY (TBD|TBA|Winner|Loser|Seed|Game N|Pool|Bracket|Tournament|Invitational|Classic|Showcase).

**Opponent registry is CUMULATIVE/historical, not schedule-synced:** Most registry-manual names map to NO current schedule game (e.g., Braxter has 13/16 manual registry names absent from its schedule). Registry accumulates entries across seasons/renames; scheduled-game opponent_name often differs from registry name (game says "Gretna Post 216 Reserve", registry says "Gretna"). => Scheduler should resolve opponents from the GAME/schedule record (pregame_data.opponent_name + opponent_id->root_team_id->registry progenitor lookup), NOT by iterating the whole registry. The registry is a join target, not the work queue.

Recommendation for Epic E placeholder handling: a light name-pattern detector (TBD/seed/bracket/tournament regex) → DEFER + re-poll near game time rather than queue for operator input. But expect this to catch only a tiny slice (~6% here); the real cost is unindexed real teams, which need search-or-ask. Doc updated: added Placeholder note + structural-flag absence to the opponents endpoint doc.
