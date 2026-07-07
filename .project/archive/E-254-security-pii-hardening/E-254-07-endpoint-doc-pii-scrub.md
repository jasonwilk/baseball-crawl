# E-254-07: Endpoint-doc PII scrub

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/api/` no longer carries these IDENTIFIED real identities: (a) the identified opponent team (full UUIDs, public_ids, name, city, an exact win-loss record) + a real player UUID; (b) the operator's OWN-program identity (own team name/nickname + an own-team public_id); (c) the operator's first name; and (d) **BOTH real MINORS under `docs/api/` — names AND player UUIDs** (the operator's child + an opponent youth player; the highest-sensitivity class, pulled forward per the user decision). All replaced per the api-docs.md placeholder taxonomy and verified by the 22-token byte-gate. Both minors live in files already in the 24-file scope, so scope stays 24 files — only the denylist grew (to 22 tokens). **Scope boundary (NOT an absolute claim)**: this story does NOT guarantee "no real identity anywhere under `docs/api/`" — a real-PII TAIL of ADULT names (opponent/venue/tournament) and unredacted real full UUIDs across ~28 more endpoint docs remains OUT of scope (minors are pulled IN; adults + bulk UUIDs are NOT). That systematic sweep is a deliberate follow-up (IDEA-096), best enforced by a positive "example JSON must use taxonomy placeholders" rule rather than an ever-growing denylist. **The exact real identifiers are NOT written into this committed story (user Decision #2)** — they live in the uncommitted, gitignored real denylist `secrets/pii-denylist.txt` (api-scout-owned); only the PII-free harness (`scripts/check_doc_pii.sh`) and a fake-token example (`scripts/pii-denylist.example.txt`) are committed.

## Context
The audit (F-related, `PLATFORM-AUDIT.md` line 99) reported "15 endpoint docs" committing a real 14U youth team. api-scout's full audit corrected this to **24 files** under `docs/api/` — the real third-party surface (the identified opponent team, real org/event names, and BOTH real minors — the operator's child + an opponent youth player, names AND player UUIDs, pulled forward per the user decision) PLUS, per user Decision #1 (EXPAND), the operator's OWN-program identity (own team name/nickname + own-team public_id) and first name. The api-docs rule was literally written from this data and the docs were never scrubbed; git history retains the old values, so this scrub stops forward propagation.

This is a value-only scrub owned by api-scout. It is cleanly separable from CE-5 / E-255's doc-accuracy sweep (which corrects factual schema/behavior claims) and must sequence BEFORE it so CE-5 works on clean files. See Technical Notes TN-10 for the full scrub rules, taxonomy target, CE-5 boundary, and the sidecar-held denylist.

## Acceptance Criteria
- [ ] **AC-1**: Across the 24 DOC files listed in "Files to Create or Modify" (the `docs/api/` scrub targets; the 2 committed byte-gate scripts are deliverables, not scrub targets), the ENUMERATED real identifiers — the set the 22-token byte-gate (AC-3) checks — are replaced with the approved placeholder taxonomy per TN-10 (`.claude/rules/api-docs.md` §"PII-Safe Placeholder Taxonomy" + "Semi-Identifying Combinations"). **The 22-token byte-gate set IS the definition of this story's coverage** — it spans: the identified opponent team's UUIDs/public_id/name/location/record, the operator's own-program identity (own team name/nickname + own-team public_id) and first name, and BOTH real minors' names (all name-parts) + player UUIDs. This is NOT "remove every UUID in the 24 files": one opponent-TEAM UUID legitimately REMAINS in an in-scope file (it is a team id, not a person, and also lives in an out-of-scope follow-up file → deferred to IDEA-096), so its presence after the scrub is NOT a failure.
- [ ] **AC-2**: BOTH real minors under `docs/api/` are fully scrubbed (highest-sensitivity, pulled forward): the operator's child (name-parts + jersey + player UUID) in `flows/spray-chart-rendering.md` and `get-me-associated-players.md`, and the opponent youth player (name-parts + player UUID) in `get-teams-team_id-opponents-players.md` — all replaced with placeholders. The byte-gate verifies both via name-part tokens + player-UUID prefix gates (exact tokens in the sidecar).
- [ ] **AC-3** (reviewer byte-gate, PII-free): Run `scripts/check_doc_pii.sh <docs-dir>` with the real (uncommitted) denylist via `PII_DENYLIST_FILE` (default `secrets/pii-denylist.txt`, from api-scout). Returns `0`=REAL+0 matches (PASS), `1`=identifier present (FAIL, `file:line` printed), `2`=self-test/malformed (INVALID), `3`=real denylist absent→EXAMPLE MODE (INCONCLUSIVE). Passes iff it prints `REAL mode; 22 patterns loaded` and exits `0`. Exit `2`/`3` MUST NOT be recorded as a passing scrub. Only the PII-free harness + fake `*.example` are committed. (Category set covered by the 22-token gate: BOTH minors' names + player UUIDs; the identified team's UUIDs/public_ids; real own-team & opponent names; location — city/state; org & event names; operator first name; win-loss record. The city/org/event share the opponent's city name, so a single location token subsumes all three; minor names use split name-part tokens — see the sidecar.)
- [ ] **AC-4**: The scrub is value-only — no factual API schema/behavior content is changed (per the api-docs.md Fidelity rule and TN-10), and every scrubbed example JSON block still parses with its keys/structure unchanged (only values swapped). Where a prose caveat cites a real UUID as evidence, the factual claim (e.g. "confirmed across 2 teams") is preserved while the identity is removed.
- [ ] **AC-5**: `status` and `last_confirmed` frontmatter are unchanged in every scrubbed file (a scrub is not a live re-verification, per TN-10).
- [ ] **AC-6**: The three already-clean files (`get-bats-starting-lineups-event_id.md`, `get-bats-starting-lineups-latest-team_id.md`, `get-teams-team_id-lineup-recommendation.md`) are NOT modified — existing approved `*-REDACTED` / `xXxX` placeholders are not re-touched (TN-10).

## Technical Approach
Sweep the 24 files, replacing all real identifying values with the approved taxonomy placeholders per TN-10. Be surgical — change only identifying values; do not re-touch approved `-REDACTED`/`xXxX` placeholders or alter factual API-behavior claims. Prioritize the minor's identity in `flows/spray-chart-rendering.md`. The implementer cautions (do-not-scrub the "all 61 opponent teams" count, season_year→generic year, the staff-example placeholder swap) are in the sidecar. Use the sidecar denylist command block as the self-check before completion. See TN-10.

## Dependencies
- **Blocked by**: None
- **Blocks**: None (but SHOULD sequence before CE-5 / E-255's doc-accuracy sweep — a cross-epic ordering note, not a within-epic dependency)

## Files to Create or Modify
Full-real-UUID files (5):
- `docs/api/endpoints/get-me-teams.md`
- `docs/api/endpoints/get-teams-team_id.md`
- `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md`
- `docs/api/endpoints/get-teams-team_id-players.md`
- `docs/api/endpoints/get-teams-team_id-public-team-profile-id.md`

Name / public_id / record (no full UUID) files (13):
- `docs/api/endpoints/get-public-teams-public_id.md`
- `docs/api/endpoints/get-me-team-tile-team_id.md`
- `docs/api/endpoints/get-me-associated-players.md`
- `docs/api/endpoints/get-teams-team_id-opponents-players.md`
- `docs/api/endpoints/get-teams-team_id-users.md`
- `docs/api/endpoints/get-teams-team_id-users-count.md`
- `docs/api/endpoints/get-me-related-organizations.md`
- `docs/api/endpoints/get-organizations-org_id-teams.md`
- `docs/api/endpoints/get-teams-team_id-opponents.md`
- `docs/api/endpoints/post-teams-team_id-schedule-events.md`
- `docs/api/endpoints/patch-teams-team_id-schedule-events-event_id.md`
- `docs/api/endpoints/get-teams-public-public_id-id.md`
- `docs/api/endpoints/patch-players-player_id.md`

Inline real-public_id-example files (3):
- `docs/api/endpoints/get-teams-public-public_id-access-level.md`
- `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`
- `docs/api/endpoints/web-routes-not-api.md`

Flow docs (2):
- `docs/api/flows/spray-chart-rendering.md` (⚠ named minor — highest priority)
- `docs/api/flows/opponent-scouting.md`

Own-team identity (1, user-approved expansion):
- `docs/api/endpoints/get-teams-public-public_id-players.md` (own-team name/nickname + an own-team public_id reused as an inline example)

Total: **24 doc files**. Additional real opponent names, the own-program name/nickname + own-team public_id, and the operator's first name also live inside several files already listed above (e.g. `get-teams-team_id-opponents.md`, `get-game-stream-processing-game_stream_id-boxscore.md`, `get-me-teams.md`, `get-public-teams-public_id.md`); all are covered by the harness byte-gate. The exact identifier strings are held in the uncommitted `secrets/pii-denylist.txt`, not listed here (Decision #2).

Committed byte-gate deliverables (2 NEW files, PII-free, created in the worktree during this story by api-scout — they ride the closure patch):
- `scripts/check_doc_pii.sh` (the harness — greps a target dir against a denylist file supplied via `PII_DENYLIST_FILE`, machinery-based self-test, exit codes 0/1/2/3 per AC-3)
- `scripts/pii-denylist.example.txt` (fake sentinel tokens — `ZZ__EXAMPLE_*` + prefix `zzzzzzzz`, deliberately unique so EXAMPLE MODE cannot false-trip on real docs; satisfies user requirement R2)

MUST NOT modify (already clean): `docs/api/endpoints/get-bats-starting-lineups-event_id.md`, `docs/api/endpoints/get-bats-starting-lineups-latest-team_id.md`, `docs/api/endpoints/get-teams-team_id-lineup-recommendation.md`.

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
api-scout owns this scrub (it performed the audit and owns `docs/api/**`). The audit's "15" is superseded by 24 (TN-10).

**Scope resolved by user decisions (2026-07-06)**: Decision #1 = EXPAND — the operator's OWN-program identity (own team name/nickname + own-team public_id) and first name ARE scrubbed alongside the third-party + minor identifiers (in-policy: api-docs.md requires placeholders for ALL example teams/people; the own program is public by nature, so this is doc-example hygiene). Decision #2 = CONFIG/CONFIG.EXAMPLE SPLIT — the committed harness (`scripts/check_doc_pii.sh`) + fake example (`scripts/pii-denylist.example.txt`, colocated so the harness auto-resolves it via `$(dirname "$0")/pii-denylist.example.txt`) are PII-free; the exact real identifiers live ONLY in the uncommitted, gitignored `secrets/pii-denylist.txt` (`secrets/` is git-ignored so the dispatch closure `git add -A` can never sweep it). Planning artifacts + committed scripts stay PII-free (mirrors the deliberately-uncommitted `PLATFORM-AUDIT.md`).

**Real denylist pre-staged + run mechanics**: `secrets/pii-denylist.txt` is pre-staged (uncommitted, api-scout-owned). Harness + example are Story-07 dispatch deliverables created in the worktree. Reviewer runs: `PII_DENYLIST_FILE=/workspaces/baseball-crawl/secrets/pii-denylist.txt /tmp/.worktrees/baseball-crawl-E-254/scripts/check_doc_pii.sh /tmp/.worktrees/baseball-crawl-E-254/docs/api` → expect `REAL mode; 22 patterns loaded` … `PASS (REAL, 0 matches)`, exit 0. Post-closure: `scripts/check_doc_pii.sh docs/api`.
**Verifiability (anti-hollow-gate)**: the committed AC fully describes the METHOD (grep categories + exit semantics); only the literal tokens are withheld. The harness self-test is machinery-based (data-independent) so a gutted harness exits `2`, never `0`; it prints `REAL mode; N patterns loaded` (AC requires N>0) and `file:line` on any leak; a missing real denylist exits `3` (EXAMPLE MODE, loud banner) which MUST NOT be recorded as a pass (user R1). The fake example (`ZZ__EXAMPLE_*`/`zzzzzzzz` sentinels) documents the format without any real token (user R2).

Two context-layer follow-ups surfaced (do NOT block this story): a one-line api-docs.md taxonomy addition for bare 8-char UUID prefixes + switching the canonical `<prefix>-REDACTED` placeholder off the real prefix, and promoting the denylist grep into a re-runnable check — both recorded in the epic Open Questions for the closure context-layer assessment.
