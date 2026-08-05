# Opponent Resolution Flow

> **Last updated:** 2026-08-04 | **Source:** E-240-02; access level, population rate and end-to-end chain validation from the 2026-08-03 identifier-resolution probes

How to resolve an opponent from the authenticated API into identifiers usable across both authenticated and public endpoints.

> **Scope note (2026-06-17, E-240-02):** This doc describes the *reusable*
> resolution mechanism only -- **Pass 1** (the `opponents` registry →
> `GET /teams/{progenitor_team_id}` progenitor chain) plus the **`POST /search`
> name fallback**. The deleted machinery that older revisions described -- the
> admin resolve UI (`/admin/opponents/{link_id}/resolve`), the two-pass
> `opponent_resolver.py` / `opponent_seeder.py` modules, and the
> `bb data resolve-opponents` command -- was **removed in E-239** and is gone
> from the repo. The follow→bridge→unfollow path is **BANNED**, not "legacy"
> (`.claude/rules/gc-uuid-bridge.md`). The morning-run scheduled-report flow
> (E-240) consumes exactly this Pass 1 + search mechanism as its rung-(a) /
> rung-(c) resolution ladder.

## The Resolution Chain

### Pass 1: Progenitor Chain (Primary)

#### Step 1: Get the opponent list

**Endpoint:** [`GET /teams/{team_id}/opponents`](../endpoints/get-teams-team_id-opponents.md)

Returns the full opponent registry for a team. Each record contains three UUID fields with different semantics:

| Field | Purpose |
|-------|---------|
| `root_team_id` | Local registry key. Use with `/teams/{team_id}/opponent/{root_team_id}`, roster, avatar. |
| `owning_team_id` | Always equals the path `team_id`. Informational only. |
| `progenitor_team_id` | **Canonical GC team UUID.** **Absent on a median ~30-38% of a team's records, ranging 0-100% by team** (two 2026-08 samples, teams only; see Resolution Statistics). This is the key to step 2. |

Filter out `is_hidden=true` records (duplicates/bad entries).

**The key is OMITTED, not null**, on a hand-typed opponent. Test key presence (`"progenitor_team_id" in record`) or use `record.get("progenitor_team_id")` -- do not test `is None` against a key that will not be there.

**No association is required to read this registry (verified 2026-08-03, independently re-verified 2026-08-04).** A valid `gc-token` is the only gate: **21/21** unassociated teams returned 200 with the full field set, plus 6/6 a further hop out, and a disjoint **24/24** sample of stranger teams replicated it — with the `public-team-profile-id` 403 control reproduced **10/10**, so a refusal is demonstrably producible. Registry resolution is therefore a **bulk** operation -- one **paginated** fetch per team -- not a per-game lookup. ⚠ **Send `x-pagination: true`**: the bare call silently truncates at 100 records with no `x-next-page` and no error. See [`GET /teams/{team_id}/opponents`](../endpoints/get-teams-team_id-opponents.md) for the truncation detail and for the control that distinguishes this access finding from a permissive instrument.

#### Step 2: Get team metadata via progenitor_team_id

**Endpoint:** [`GET /teams/{progenitor_team_id}`](../endpoints/get-teams-team_id.md)

Call the team detail endpoint using `progenitor_team_id` as the `team_id` path parameter. The response includes `public_id` -- the slug needed for public endpoints.

This works because `progenitor_team_id` is a canonical GC team UUID, and `/teams/{team_id}` does not require the team to be the user's own — a `progenitor_team_id` drawn from an opponents registry resolved **18/18** and **20/20** on two independent samples.

> ⚠ **`/teams/{team_id}` does NOT accept "any valid team UUID" (corrected 2026-08-04).** On 24 ids drawn from `POST /search`, **8 (33%) returned 404** — because **all 8 were ORGANIZATIONS, not teams**. An organization id is not a team id, so `GET /teams/{org_id}` 404s. Controls: `GET /organizations/{id}` returned **200 on 8/8** of them and **404 on 3/3** real teams.
>
> **Filter search hits on the envelope `type` (`"team"` vs `"organization"`)** — not on `result.type`, which is present only on organizations and absent on teams, so testing it inverts the check. Organizations are **15.5% of search hits (19.5% of baseball hits)** and **carry a `public_id`**, so filtering by `public_id` alone can select one.
>
> Since `resolve_gc_uuid_by_public_id` yields `POST /search` `result.id` *as* the `gc_uuid`, **a stored `gc_uuid` can be an organization id.** That is not a dead or corrupt id and not a retryable error — it is the **wrong entity class**, detectable at resolution time from a field already in the search response. Step 2 is reliable *from a registry `progenitor_team_id`* (18/18, 20/20); it is not reliable from an arbitrary search-sourced UUID.

#### Step 3: Use public_id for public endpoints

With the `public_id` from step 2, the following unauthenticated endpoints become available:

- [`GET /public/teams/{public_id}`](../endpoints/get-public-teams-public_id.md) -- team profile, record, staff
- [`GET /public/teams/{public_id}/games`](../endpoints/get-public-teams-public_id-games.md) -- game schedule with scores
- [`GET /public/game-stream-processing/{game_stream_id}/details`](../endpoints/get-public-game-stream-processing-game_stream_id-details.md) -- inning-by-inning line scores

### Pass 2: POST /search Fallback (Null-Progenitor Opponents)

Opponents with no `progenitor_team_id` key (**median ~30-38% of a team's records, 0-100% by team** — see Resolution Statistics) cannot be resolved through the progenitor chain. The **POST /search fallback** runs after the progenitor chain completes, targeting only unlinked opponents (no existing `resolution_method`, not hidden).

**Endpoint:** [`POST /search`](../endpoints/post-search.md)

#### Auto-Accept Criteria

All three conditions must be true for automatic resolution:

1. **Exact name match** (case-insensitive) between `opponent_links.opponent_name` and `result.name`
2. **Season year match**: `result.season.year` matches the member team's `season_year`
3. **Single result**: Exactly one result remains after both filters

If 0 or 2+ results match after filtering, the opponent is left unlinked for one-time operator mapping via `bb report map-opponent` (the deleted admin UI's replacement).

#### What POST /search Returns

Each search hit provides both key identifiers needed for resolution:

- `result.id` -- the `progenitor_team_id` (canonical GC team UUID, stored as `gc_uuid`)
- `result.public_id` -- the public slug for unauthenticated endpoints

This means search-resolved opponents skip the progenitor chain entirely -- a single API call yields both identifiers.

> ⚠ **FILTER ON THE ENVELOPE `type` FIRST — search returns ORGANIZATIONS as well as teams (2026-08-04).** The hit envelope carries `type` ∈ `{"team", "organization"}`. Organizations are **15.5% of all hits and 19.5% of baseball hits** (n=599) — not marginal.
>
> **Neither identifier above discriminates.** Organizations carry a `public_id` (93/93), so **auto-accept criterion 3 ("exactly one result") can settle on an organization**, and an org `public_id` fed to the public pipeline 404s (3/3 measured). `season`, `avatar_url` and `location` are equally non-discriminating.
>
> Test the **envelope** `type`, not `result.type` — the latter is present only on organizations and absent on teams, so the check inverts. Coextensive cross-checks: orgs have `number_of_players: null` (93/93) and `staff: null` (93/93); teams have both populated (506/506).
>
> The three auto-accept conditions in the section above assume every hit is a team.
>
> ✅ **IMPLEMENTED (2026-08-04).** Entity-class filtering now runs ahead of them, via the shared predicate `is_team_hit()` in `src/gamechanger/search.py`, applied per hit at both consumers:
> - `_resolve_via_search()` (`src/gamechanger/opponent_ladder.py`, rung (c)) **drops organization hits BEFORE** the single-result count, so criterion 3 is now "exactly one **team**". An all-organization result set filters to zero teams and falls through to the operator queue, exactly as a zero-hit result does.
> - `resolve_gc_uuid_by_public_id()` (`src/gamechanger/search.py`) checks `public_id` first and entity class second, **skipping** a non-team match with a WARNING and continuing to page.
>
> The predicate is deliberately NOT applied inside `search_teams_by_name()`: that function's raw `hits` length is the has-more-pages signal, so filtering at the source would make a filtered full page read as partial and strand a team whose match sits on a later page.

#### Resolution Method

Search-resolved opponents are recorded with `resolution_method='search'`,
distinguishing them from progenitor-chain resolutions (`'progenitor'`).

> **Removed (E-239):** Earlier revisions described an **admin resolve UI**
> (`/admin/opponents/{link_id}/resolve`) as the manual path for opponents that
> neither the progenitor chain nor the search fallback could resolve. That UI and
> its route were **deleted in E-239** along with the rest of the
> opponent-management surface; there is no admin resolve workflow in the repo.
> The replacement operator path in the scheduled-report flow (E-240) is the
> `bb report map-opponent <root_team_id> <public_id|GC team URL>` CLI command,
> which UPDATEs the pending `opponent_links` row with an operator-supplied
> mapping (or marks it `--no-presence`). The `resolution_method='operator'` value
> records an operator mapping.

## WARNING: Bridge Endpoints Restricted to "Followed" Teams Only

Both bridge endpoints are restricted and **cannot be used for opponent resolution**:

- [`GET /teams/{team_id}/public-team-profile-id`](../endpoints/get-teams-team_id-public-team-profile-id.md) -- UUID to public_id. Returns HTTP 403 for opponent UUIDs (confirmed 2026-03-09).
- [`GET /teams/public/{public_id}/id`](../endpoints/get-teams-public-public_id-id.md) -- public_id to UUID. Returns HTTP 403 for opponent public_ids (confirmed 2026-03-11).

Both bridges only work for **teams the authenticated user follows** (operator-reported 2026-03-12). The exact association types that permit access (coaching/admin membership, explicitly followed, bookmarked) have not been independently verified, but the 403 behavioral outcome for opponent teams is confirmed via curl and proxy capture.

**Do NOT use either bridge endpoint for opponent resolution.** The chain above (opponents list -> team detail via progenitor_team_id -> public_id from team metadata) is the correct path -- it requires no follow association.

**Note:** Following can be automated via [`POST /teams/{team_id}/follow`](../endpoints/post-teams-team_id-follow.md) (204 No Content, "follow as fan"). This unlocks bridge endpoints and other follow-gated authenticated data. However, following is not needed for resolution itself, and it is also **not required for the scouting pipeline** -- the public-endpoint scouting chain (schedule, roster, boxscores) works without any follow association (confirmed on unfollowed team, 2026-03-12). See [opponent-scouting.md](opponent-scouting.md#following-not-required).

## Null-Progenitor Fallback

**A median ~30-38% of a team's opponents have no `progenitor_team_id`, ranging
0-100% by team** (two 2026-08 samples, teams only; see Resolution Statistics for
why the record-weighted aggregate is the wrong planning number). The key is
omitted, not null, on manually-typed opponents. Two resolution paths apply, in order:

1. **POST /search fallback (automated)**: After the progenitor chain completes,
   run `POST /search` (via `search_teams_by_name()`) for each unlinked opponent,
   **dropping organization hits** (`is_team_hit()`) and then auto-accepting only
   on an unambiguous single **team** match. This is the primary automated
   fallback.
2. **Operator mapping (manual)**: Opponents the search fallback cannot resolve
   (0 or 2+ team matches, an all-organization result set, or genuinely
   unindexed teams) are surfaced to the operator
   and mapped once via `bb report map-opponent <root_team_id> <public_id|GC team URL>`
   (E-240). This replaces the deleted admin resolve UI.

> **BANNED path -- do NOT use.** The **follow → bridge → unfollow** pattern
> (former `resolve_unlinked()` / `_follow_bridge_unfollow()`, run via
> `bb data resolve-opponents`) is **deleted and banned**, not "legacy" or
> "experimental." It followed against `root_team_id` (the WRONG namespace --
> `root_team_id` is not a `gc_uuid`) and *mutated external GameChanger follow
> state* (a `POST /follow`, the bridge call, then best-effort unfollow `DELETE`s),
> so a failed cycle could leave the account following teams it never intended to.
> The module and command were removed in E-239. New work MUST NOT reintroduce
> this path -- see `.claude/rules/gc-uuid-bridge.md` ("BANNED PATH") and route any
> such need to PM. The correct fallbacks are the read-only `POST /search` bridge
> and operator-pasted GC team URLs for unindexed teams.

## Resolution Statistics

Opponents resolve through these methods:

| Category | Method | Resolution Method Value |
|----------|--------|------------------------|
| Progenitor chain (Pass 1) | Automated via `progenitor_team_id` → team metadata | `'progenitor'` |
| POST /search fallback (Pass 2) | Automated via unambiguous single name match | `'search'` |
| Operator mapping | Manual via `bb report map-opponent` (replaces deleted admin UI) | `'operator'` |
| Unresolved | No match found; awaiting operator mapping | (none) |

**Population rate -- size against the PER-TEAM distribution, not the aggregate (2026-08):**

| Sample | Teams | Records | Record-weighted missing | Per-team missing: median (range) |
|---|---|---|---|---|
| A (scouted teams, from our DB) | 21 | 852 visible / 874 raw | 33.6% | **30.0%** (0–58.7%) |
| B (disjoint, from search, **teams only**) | 16 | — | 41.3% bare · 62.6% truncation-corrected · 31.4% outlier-dropped | **38.3%** (0–100%) |

**The two samples agree** once entity class is controlled for: per-team median missing 30.0% vs 38.3%.

⚰ **WITHDRAWN 2026-08-04** — this section previously claimed the two distributions disagreed sharply (medians 30.0% vs 7.4%). **Artifact.** Sample B as first reported mixed **8 organizations** in with 16 teams, and organizations are **100% linked** (131/131), so 8 of its 10 "0% missing" entries were not teams at all. Cleaned, the disagreement vanishes.

**Why this matters beyond the number:** `POST /search` returns a **heterogeneous** result set, and because organizations are uniformly linked they bias any linked-share statistic computed over unfiltered search output. **Filter on the envelope `type` before computing anything about teams** (see step 2's warning).

**Sample A is not org-diluted** — its teams came from our own database and all 28 stored `gc_uuid`s return 200 on `GET /teams/{id}` (28/28). Do not "correct" it.

**Still prefer the per-team median to the aggregate:** one team supplies **508 of 694** missing records when fully paged, which is what moves B's rate across 31.4% / 41.3% / 62.6%.

**Which denominator:** these are over records as returned. `src/gamechanger/crawlers/opponents.py` does **not** filter `is_hidden`, so a crawler author's denominator is the raw count (hidden was 22/874 in A, 2/823 in B).

A scheduler must still treat the fallback as a first-class path — but half the teams in sample B needed it barely or not at all, so per-team variance, not a single rate, is the thing to design around.

⚰ **RETIRED 2026-08-03** -- `~14%` was stated as the null-progenitor rate in **five** places in this file (the step-1 field table, the Pass-2 lead, the Null-Progenitor Fallback lead, this section's closing sentence, and the Three ID Types summary) and in **two** more in [opponent-scouting.md](opponent-scouting.md). All seven are corrected. That figure came from the single-team baseline preserved immediately below, and it **understated the real fallback load by more than 2x**. Do not reintroduce it as a planning number.

Historical baseline, preserved as the single-team observation it was (2026-03-04, one team, 70 opponents):

| Category | Count | Percentage |
|----------|-------|------------|
| Auto-resolved (progenitor_team_id present) | ~60/70 | ~86% |
| Null progenitor (candidates for search fallback) | ~10/70 | ~14% |

The search fallback is expected to resolve a portion of the no-progenitor opponents, leaving ambiguous cases (0 or 2+ matches) and genuinely unindexed teams for one-time operator mapping via `bb report map-opponent`. **How large a portion is bounded by the finding two sections below: on the linked records observed so far, the chain bought no search reach the name path did not already have. That is an observed outcome with an untested mechanism, not a proof — read that section before relying on it.**

## End-to-End Validation of the Chain (2026-08-03)

The chain was run whole, starting from the identifier a game record actually gives you -- the UUID-form opponent key in a boxscore payload, which is a `root_team_id` (see [`GET /game-stream-processing/{event_id}/boxscore`](../endpoints/get-game-stream-processing-event_id-boxscore.md)):

```
boxscore UUID-form key  (== root_team_id == pregame_data.opponent_id)
  -> join GET /teams/{scouted_team_gc_uuid}/opponents on root_team_id  -> progenitor_team_id
  -> GET /teams/{progenitor_team_id}                                   -> public_id
```

Sample: 24 boxscores across 8 scouted teams with no user association. 23 classified (1 was a cross-perspective twin, a known sampling artifact, not a chain failure); 18 UUID-form opponent keys, 5 slug-form.

| Hop | Result |
|-----|--------|
| boxscore UUID key matched a registry `root_team_id` | **18/18** |
| matched record carried `progenitor_team_id` | **18/18** |
| `GET /teams/{progenitor}` returned 200 with a `public_id` | **18/18** |
| singular `/opponent/{root_team_id}` agreed with the bulk registry | **6/6** |

**A slug-form boxscore key is already a `public_id`** and needs no chain -- it matched no registry `root_team_id` (0/5), as expected, because it is not in that namespace.

**Known ceiling, unchanged by any of this:** a hand-typed opponent has **no `progenitor_team_id` at all**, so no amount of registry access manufactures one. The chain resolves the linked population only.

## The Chain Does NOT Extend Reach Past `POST /search` (refuted 2026-08-03)

**Hypothesis tested and REFUTED:** *"a registry entry does not depend on GC's search index, so a team `POST /search` cannot find may still be resolvable via `progenitor_team_id`."*

- Of 16 chain-resolved teams, **16/16 were also findable by `POST /search`** on the canonical name from `GET /teams/{progenitor}`.
- **10/10** were findable using the coach's **local registry label** as the query, because for a linked opponent GC copies the canonical name into the registry entry -- label was byte-identical to canonical **10/10**.

**Status: OBSERVED OUTCOME, UNTESTED MECHANISM.** The outcome replicated (16/16, and 10/10 on an independent sample), but the *explanation* has not been established.

⚰ **DOWNGRADED 2026-08-04.** This section previously asserted the populations coincide *"by construction"* because a record carries `progenitor_team_id` **precisely because** someone found that team in search — and instructed readers **"do not re-run this probe."** Both overreached, and the instruction has been removed: it forecloses an open question.

**Two link paths that could set `progenitor_team_id` were never excluded**, because ruling them out requires **write actions nobody has performed**:

1. [`GET /search/opponent-import`](../endpoints/get-search-opponent-import.md) — a separately documented import path.
2. League / organization schedule links, which may associate teams without a manual search.

**And the test is close to tautological.** Querying a name-indexed search with a team's own exact canonical name is nearly guaranteed to find it, so a 16/16 hit rate is weak evidence *for the proposed mechanism* even though it is solid evidence *about the outcome*.

**What to rely on:** for the linked population as observed, the chain buys no additional search reach. **What remains open:** whether a linked record can exist for a team that search cannot find — which depends on whether a non-search path can set `progenitor_team_id`. Re-running this against records created through path 1 or 2 above would be informative.

**Keep the two failure modes distinct** -- they select the same records here but are different things: *search-index absence* (the team is not indexed) and *hand-typed entry* (the coach never used lookup). Conflating them overstates what either fallback can recover.

### What the chain IS worth (measured)

Reach is not the payoff. These three are:

1. **Determinism.** Only **7/16** name searches returned exactly one hit; the rest returned 2-25, two saturating at 25. Disambiguating those requires the `public_id` you are trying to resolve in the first place. The chain returns exactly one answer, **16/16**.
2. **It needs no name.** It runs from a `root_team_id` alone -- which is what a boxscore key or `pregame_data.opponent_id` hands you. The search path cannot start without a name.
3. **It clears rows search left behind.** 2 of the 3 `opponent_links` rows with `public_id IS NULL` resolved on the first attempt; the third carried a malformed non-UUID `root_team_id` sentinel and returned **HTTP 500**.

## Three ID Types Summary

| ID | Source | Purpose |
|----|--------|---------|
| `root_team_id` | `GET /teams/{team_id}/opponents` | Local identifier from GC's opponent registry |
| `progenitor_team_id` | `GET /teams/{team_id}/opponents` | Canonical GC team UUID; key **absent** on a median ~30-38% of a team's records (0-100% by team, teams only, 2026-08) |
| `public_id` | `GET /teams/{progenitor_team_id}` response or `POST /search` result | Public slug for unauthenticated endpoints |

## See Also

- [opponent-scouting.md](opponent-scouting.md) -- How to use `public_id` to retrieve game schedules, player rosters, per-game boxscores, and compute season aggregates
- [`POST /search`](../endpoints/post-search.md) -- Endpoint spec for the team search used in the automated name fallback (Pass 2)
- [`.claude/rules/gc-uuid-bridge.md`](../../../.claude/rules/gc-uuid-bridge.md) -- The bridge pattern, the reverse `GET /teams/{gc_uuid}` rung-(a) bridge, and the BANNED follow→bridge→unfollow path
