# Search returns two entity classes — filter for teams

**Date:** 2026-08-04 · **Status:** COMPLETE (this commit) — the entity-class filter is
implemented at both call sites, with the shared predicate `is_team_hit()` in
`src/gamechanger/search.py`. Committed on branch `worktree-search-entity-class-filter` in the
worktree `.claude/worktrees/search-entity-class-filter`; **not yet merged to `main`, and not
pushed** — the operator merges at the end. See the final Progress log entry.
**Source:** live probes 2026-08-03/04 (~630 calls, read-only, web profile)

## Goal

`POST /search` returns a **heterogeneous** result set. Each hit's **envelope** carries
`type` ∈ `{"team", "organization"}`. Two call sites consume search hits and filter only
on `public_id`, so an **organization** can be selected where a team is required.

Add an entity-class check at both. This is the first behavioral change to come out of
the boxscore/registry investigation; everything before it was documentation.

## The finding (measured, do not re-derive)

- Envelope `type` separates the classes perfectly at **n=599 hits** (506 team / 93 org).
- **`GET /teams/{org_id}` → 404.** An organization id is not a team id. Controls both
  ways: `GET /organizations/{id}` → **200 on 8/8** orgs and **404 on 3/3** teams.
- Predictive power at scale: **58/58 orgs → 404, 86/86 teams → 200.** PPV/NPV 1.00.
  **Honest bound:** rule of three gives a ~5.2% / ~3.5% 95% ceiling on the error rate —
  *no counterexample yet*, not proven.
- **Base rate is not marginal: 15.5% of search hits are organizations (19.5% among
  baseball hits).**
- **Organizations carry a `public_id`** (93/93), so a `public_id`-only filter cannot
  exclude them. An org `public_id` fed to the public pipeline 404s (3/3).
- Key sets are **disjoint and OMITTED, not null** — teams always carry
  `number_of_players` + `staff` and never `type`/`tournament_dates`; orgs are the
  inverse. Same key-omission convention as `progenitor_team_id`; `is None` is the wrong
  test.

## Files

- `src/gamechanger/search.py` — `resolve_gc_uuid_by_public_id` filters on
  `result.get("public_id") != public_id` with no type check, then yields `result.id`
  **as the `gc_uuid`**.
- `src/gamechanger/opponent_ladder.py` — rung (c) `_resolve_via_search` gates on
  `len(hits) != 1` then takes `hits[0]`. ⚠ **The uniqueness guard gives NO protection
  AGAINST AN ORGANIZATION** — it fires exactly when a name matches one thing, which is when
  an org name matches uniquely. Measured: 2 of 15 org names returned a single hit; both were
  the org. Scope that precisely: the guard is NOT useless and is NOT to be weakened — it is
  what prevents a multi-hit wrong-team auto-resolve, and it stays exactly as it is. It simply
  cannot discriminate entity class, which is a different job.
  *(Symbol name corrected 2026-08-04 by spec review: this file previously called the function
  `resolve_public_id_by_search`, which does not exist.)*
- `tests/` — new cases (see Verification).

## Design

Require the **envelope's** `type == "team"`.

⚠ **Check the envelope, NOT `result.type`.** `result.type` is the ORG SUBTYPE
(`travel` / `tournament` / `league`) and is **absent on teams** — testing it inverts the
check and rejects every real team.

Prefer an explicit shared predicate over two inline checks; both sites want the same
rule and this repo's recurring defect is a second copy that drifts.

⚰ **RESOLVED 2026-08-04 — do not re-open. The question below is answered in the Progress
log; read that before acting on this paragraph.** Site A = **skip-and-continue**; rung (c) =
**drop org hits, then require exactly one TEAM**. Retained as the record of what was asked.

> Open design question for planning: **skip** a non-team hit and keep paging, or **refuse**
> the resolution outright? Skip-and-continue is probably right for
> `resolve_gc_uuid_by_public_id` (an org sharing a `public_id` with the sought team is not
> a reason to abandon the search), but rung (c)'s uniqueness contract may want refusal.
> Decide deliberately.

## Out of scope

- The mechanism is settled — do NOT re-probe it.
- No change to `is_gc_uuid`.
- No historical repair, across **BOTH** durable stores — this note originally covered
  `teams.gc_uuid` only and missed the second (see Progress log):
  1. `teams.gc_uuid` — **28/28 stored values are teams today.**
  2. `opponent_links` — **10 rows, 0 of them `search`-method**, so rung (c) has never
     written a durable row in this DB.
  Verify both still hold before assuming it.
- The wider organization exploration (below) — separate work.

## Verification

- A search-hit fixture containing an org and a team with the SAME `public_id` → only the
  team is yielded.
- Rung (c) with a single org hit → does not return the org's `public_id`.
- **A test that fails if someone "fixes" the check to `result.type`** — that inversion is
  the likeliest wrong edit, and it must not pass.
- Fixtures must mirror the real shape: **keys OMITTED, not null** (teams have no `type`
  key at all).
- `python -m pytest tests/ > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then read
  the file. **Never pipe pytest.** Full suite green before commit.

## Follow-on — organizations are barely documented

The operator wants to probe this properly and view real examples in the UI. Known so far:

- `GET /organizations/{id}` → 200, carries `type` (`travel`/`tournament`/`league`).
- `GET /organizations/{id}/opponents` → **byte-identical** registry to the `/teams/`
  path (2/2). The `/teams/` prefix serves org ids **without validating entity class** —
  which is why these ids looked alive.
- `GET /organizations/{id}/avatar-image` → 200/404 tracking avatar presence (2/2).
- `tournament_dates` (start/end pair) on 45/93 orgs, 0/506 teams.
- Existing docs: `get-organizations-org_id-opponents.md`,
  `get-organizations-org_id-opponent-players.md`.

**All three of those questions were ANSWERED 2026-08-04** — see
`.claude/agent-memory/api-scout/organization-scope.md` and the endpoint docs corrected in the
same pass. Summary: 12 live org sub-resources (22 team-analogs 404); **orgs DO enumerate their
member teams, including for organizations we have no relationship with (27/27), with ids
pre-resolved in both namespaces**; and org registries are **NOT** a better bulk source — the
org `/opponents` list is the org's own membership roster, with ZERO overlap against member
teams' real opponent registries (3/3). The bulk lever is `/organizations/{id}/opponent-players`,
which routes around the roster 403. Follow-on work is stubbed in
`2026-08-04-org-team-discovery-and-roster-ingest.md`.

## Also flagged, feeds the Tier 2 audit

`/teams/{id}/players` returned **403 on both** orgs and teams (3/3 controls) — it is
association-gated and does not discriminate entity class. **Our March-2026 doc claim
that `GET /teams/{root_team_id}/players` returns 200 for opponent ids did NOT reproduce
on non-associated ids.** Flagged as needing re-verification, not asserted wrong.

## Progress log

- **2026-08-04** — Stub written from the probe evidence. Both defects confirmed by
  direct read of the two call sites. No code written. Needs planning: the skip-vs-refuse
  decision, and whether the shared predicate lives in `search.py` or alongside
  `is_gc_uuid`.
- **2026-08-04 (later)** — **PARKED by the operator.** Planning reached a knowledge gate: the
  rung-(c) policy cannot be chosen without knowing what an organization *is*, and the operator
  ruled *"I want to look at orgs and tell you what they are. Then I want to probe the edges to
  see if we can find our way in"* — declining both a spec-with-a-hole and a split that would
  ship half the fix. Nothing in `src/` was touched.

  **Two of the three planning questions are now SETTLED and must not be re-derived:**
  1. **Where the predicate lives** — `src/gamechanger/search.py`, applied **per hit at each
     call site**, and ⚠ **never inside `search_teams_by_name`**:
     `resolve_gc_uuid_by_public_id` reads `len(hits) < _SEARCH_PAGE_SIZE` (25) as *"no more
     pages"*, so at a 15.5% org rate a filtered full page returns ~21, reads as partial, and
     **silently strands any team whose match sits on page 2+**. Filtering at the source would
     also make an all-org page look empty and fire a spurious normalized retry.
  2. **`resolve_gc_uuid_by_public_id` (site A) — skip-and-continue**, ordering the checks
     `public_id` first and entity-class second, so the ~1-in-6 background org noise skips
     silently while an org carrying the *exact* sought `public_id` is discarded with a WARNING.
     This site does not depend on what orgs turn out to be.

  **Still open — rung (c) only:** drop org hits then require one team / refuse whenever an org
  appears / resolve *through* the org. The org research adds a consideration that did not
  exist when this file was written: **an org hit is usually a NAME COLLISION, not the umbrella
  of the team beside it** — only **4 of 70** co-occurring org hits had a same-page team in
  their member list (`Showdown` 0/21, `League` 0/22). ⚠ That is a **LOWER bound, not a rate**
  (the test only sees membership when the member team ranks on the same page), so it refutes
  "orgs are umbrellas" without licensing the reverse claim that any given org is unrelated.

  **No historical repair is owed** — re-measured this session: `opponent_links` holds 10 rows
  (7 `progenitor`, 3 pending, **0 `search`**), so rung (c) has never written a durable row in
  this DB. The original out-of-scope note covered `teams.gc_uuid` only and missed this store.
- **2026-08-04 (later still)** — **UNPARKED. The gate was already closed when it was set.**

  What an organization IS, now settled: GameChanger's **container for a group of teams**,
  with a closed subtype enum read from the app's own source — `league`, `tournament`, `travel`.
  It carries the cross-team surfaces (standings, team-records, events, game-summaries, users,
  pitch-count-report) and enumerates its members. **Membership is many-to-many** — one team was
  observed in a tournament org and a league org simultaneously, so "which org does this team
  belong to" has no single answer.

  **Why that closed the gate:** the rung-(c) question was never *"what is an organization"* —
  it was *"when an org and a team come back from the same query, is the org that team's
  umbrella?"* That is a fact about search results, and it was measured: **4 of 70**. Opening
  the same orgs in a browser could not have moved that number. The park was set on a question
  the evidence in hand had already answered.

  **DECISION for rung (c): drop org hits, then require exactly one TEAM.** Refusing whenever an
  org appears would punt the `Showdown`/`League`-shaped queries — 43 orgs, ~0 of them umbrellas
  — to the operator queue for nothing, which is strictly worse than today. The team-side
  uniqueness bar is unchanged, so no new wrong-auto-resolve mode is introduced. An all-org
  result set filters to zero teams and falls to rung (d), exactly as a zero-hit does today.

  ⚠ **Bound, carried deliberately:** 4-of-70 is a **LOWER bound on umbrella relationships**,
  not a rate — the test only detects membership when the member team happens to rank on the
  same 25-hit page. It refutes "an org hit is the umbrella"; it does **not** support the
  reverse claim that a given org is unrelated to a given team. Both readings favor the decision
  above, which is why the open bound does not reopen the decision.

  **Third option, considered and NOT taken:** resolving *through* the org (an org hit is a lead
  — enumerate its member teams and match by name). Real, and newly possible, but it is a new
  ladder rung rather than an entity-class filter, and 4-of-70 says it would fire almost never.
  Captured in `2026-08-04-org-team-discovery-and-roster-ingest.md`; do not build it here.
- **2026-08-04 (executed)** — **COMPLETE.** Shared predicate `is_team_hit()` added to
  `src/gamechanger/search.py` (reads the ENVELOPE `type`, fail-closed on absent/unknown), applied
  per hit at both call sites and deliberately NOT inside `search_teams_by_name`. Site A checks
  `public_id` first and entity class second, skipping a non-team match with a WARNING and
  continuing to page. Rung (c) `_resolve_via_search` drops org hits, then requires exactly one
  TEAM — the team-side uniqueness bar is unchanged.

  **Verification.** Full suite **4419 passed, RC=0**. Two mutants, each restored from a
  scratchpad copy (never from the index) with `__pycache__` cleared around every run and the
  mutation asserted applied:
  - `result.type` inversion (the edit the spec names as likeliest) → **7 tests failed**, including
    the dedicated `test_is_team_hit_reads_envelope_type_not_result_type`.
  - predicate → always-`True` (the pre-fix regression) → **7 tests failed**, including
    `test_search_single_organization_hit_does_not_resolve`.

  **No historical repair, re-confirmed read-only against the live DB this session:** 28 stored
  `gc_uuid`s; `opponent_links` = 10 rows (7 `progenitor`, 3 pending, **0 `search`**). Counts only
  — entity class was NOT re-probed, per this spec's out-of-scope bar.

  **Spec review (headless `codex exec`, per the operating agreement's step 2)** found 6 issues.
  Fixed here: the settled-question-still-posed-as-open Design paragraph (now tombstoned), the
  nonexistent symbol `resolve_public_id_by_search`, the Out-of-scope note that covered only
  `teams.gc_uuid`, and the over-broad "uniqueness guard gives NO protection" sentence (now scoped
  to entity class, with the bar's real job stated so a later refactor does not drop it). It also
  caught a stale fixture the execution plan had missed
  (`TestResolveGcUuidIntegration::test_resolved_gc_uuid_persisted_and_passed_to_spray`).

  **Two items deliberately NOT resolved here**, both flagged to the operator:
  1. **`OMITTED` vs `null`** — this spec says orgs' team-only keys are omitted;
     `docs/api/endpoints/post-search.md` says `number_of_players`/`staff` are `null`. Same probe,
     two phrasings, one wrong. Unsettleable without re-probing (barred) — the proxy corpus holds
     no captured `/search` body. **No behavioral impact**: the predicate reads only the envelope,
     and nothing tests those keys. Fixtures follow this spec (omitted); both docs left untouched.
  2. **Rung (c) auto-accept drift** — `docs/api/flows/opponent-resolution.md` documents two
     filters (exact name, season year) the code has never had. Pre-existing, not caused here;
     stubbed as `2026-08-04-rung-c-auto-accept-criteria-drift.md` rather than silently resolved
     in either direction.
- **2026-08-04 (`/code-review`)** — 4 findings, all verified against the repo and all fixed. The
  MEDIUM is the one worth carrying forward:

  **⚠ Dropping organizations WIDENS rung (c)'s auto-accept surface — this spec previously
  claimed it did not.** The retired sentence: *"The team-side uniqueness bar is unchanged, so no
  new wrong-auto-resolve mode is introduced."* The bar's PREDICATE is unchanged; its POPULATION
  is narrower, so one team beside N organizations now auto-resolves where the raw count sent it
  to the operator queue. The decision STANDS — it is the operator's, and refusing would punt the
  Showdown/League-shaped queries for nothing — but the safety claim defending it was one-sided
  and is now stated in both directions at the function, the module docstring, and the call site.
  Two aggravators recorded with it: the result is **terminal** (`resolve_opponent` treats any
  non-NULL `resolution_method` as cached, so a wrong resolve never re-surfaces), and the
  documented name/season filters that would catch a wrong single hit **do not exist**, so the
  team count is the entire gate.

  Also fixed: a **false claim I authored** in the `is_team_hit` docstring — *"Only bare
  `GET /organizations/{id}` and `/avatar-image` validate entity class"* dropped the source's
  *"org paths"* scoping and so implied `GET /teams/{org_id}` does not 404, contradicting the
  58/58 measurement cited two files away; the real argument rests on the SUB-resources
  (`/teams/{org_id}/opponents` serves a byte-identical registry). An all-organization result set
  now logs **WARNING**, not DEBUG — it is newly reachable and is also how a class-wide failure
  (renamed envelope type, third entity class) would present, which at DEBUG is
  indistinguishable from an unindexed team; pinned by a test, proven to discriminate by a
  warning→debug mutation. And three stale *"unambiguous single match"* sites the first sweep
  missed (module docstring, call-site comment, flow-doc body) now say *single TEAM match*.

  Full suite re-run after all fixes: **4419 passed, RC=0**.
- **2026-08-04 (paused before commit)** — Operator paused at step 7. **Exact state, so this
  resumes without re-deriving anything:**

  - **Where:** worktree `.claude/worktrees/search-entity-class-filter`, branch
    `worktree-search-entity-class-filter`, based on `255be02`. **Nothing committed, nothing
    pushed.**
  - ⚠ **`main` MOVES while this is parked** — it advanced twice during this one session
    (`255be02` → `768544d` → `91a8c36`, operator docs commits). Do NOT record or trust a `main`
    hash here; compute `git merge-base HEAD main` at landing time. That base is what the closure
    patch must diff from — a bare-`main` diff silently reverts whatever landed meanwhile.
  - **Staged:** all 11 files; working tree otherwise clean, no untracked stragglers.
  - **Steps done:** 3 EXECUTE, 4 VERIFY (4419 passed, RC=0, unpiped), 5 REVIEW (`/code-review`,
    4 findings, all verified and all fixed), 6 SCAN (11/11 files PII-covered — 9 auto-scanned,
    and the 2 `.claude/rules/` files SKIP_PATHS blinds the scanner to were manually scanned
    after a positive control was proven to fire).
  - **Steps remaining at the time of the pause:** 7 APPROVE, 8 COMMIT, then the merge to `main`.
    Steps 7 and 8 are now DONE — see the entry below. **The merge is deliberately NOT done**;
    the operator merges at the end.
  - **Open operator decision, deliberately left open:** the `/code-review` MEDIUM retired the
    premise *"no new wrong-auto-resolve mode is introduced"* that partly supported the settled
    rung (c) decision. The decision was not changed. Whether the retired premise changes the
    call is the operator's, and is the one thing a resuming session must NOT decide on its own.
    Detail in `2026-08-04-rung-c-auto-accept-criteria-drift.md`.
- **2026-08-05 — COMMITTED.** Operator approved at step 7; committed at step 8 on branch
  `worktree-search-entity-class-filter` in the worktree. **Not merged to `main` and not pushed**
  — the operator merges at the end, per their standing instruction on this chunk.

  **What remains, and the one hazard in it:** the merge must diff from
  `git merge-base HEAD main`, **never bare `main`**. `main` advanced twice while this chunk was
  in flight (three distinct hashes observed in one session, all operator docs commits), so a
  `main`-based patch would silently revert work nobody here touched. Do not record a `main` hash
  anywhere; recompute the merge-base at merge time. After merging, remove the worktree and the
  branch.

  The rung (c) decision above remains open and is unaffected by the commit — committing the
  code did not settle it.
