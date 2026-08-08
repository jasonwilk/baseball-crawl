# IDEA-137: Corpus-wide docs/api doc-PII certification sweep

## Status
`CANDIDATE`

## Summary
Multiple `docs/api/` files carry real, un-redacted GameChanger identifiers (team names, full UUIDs, public_id slugs) committed to the repo — pre-existing exposures surfaced during the E-262-09 dispatch. The three identifier classes each need scrubbing, and a name-only grep MISSES the bare UUID/public_id, so a systematic byte-gate certification pass (with the real gitignored denylist) is required to certify `docs/api/` clean.

## Why It Matters
Security rules (CLAUDE.md, IMPORTANT/override) bar real GC identifiers in committed docs, and the doc-PII byte-gate (`scripts/check_doc_pii.sh`) exists precisely to catch names/UUIDs/public_ids the pattern PII scanner cannot. During E-262-09 the team redacted 3 real UUIDs + one real team name in the two files story 09 was actively editing, but api-scout's grep then surfaced the SAME class of exposure already committed in **6 other files story 09 never touched**. Enumerated (verify against current file state before scrubbing):
- **Team name** "Nighthawks Navy" / "Nighthawks Navy AAA 14U" in: `get-teams-team_id-avatar-image.md`, `get-teams-team_id-players.md`, `get-teams-team_id-public-team-profile-id.md`, `get-teams-team_id-opponents.md`, `get-search-opponent-import.md`, `get-teams-public-public_id-id.md`.
- **Full UUID** `14fd6cb6-...` (a `progenitor_team_id`) at `get-teams-team_id-public-team-profile-id.md:12,34,144` + `get-teams-team_id-avatar-image.md:37`.
- **public_id slug** `smgRExWHuBJJ` at `get-teams-team_id-public-team-profile-id.md:144` + `get-teams-public-public_id-id.md:36`.

These cannot be certified clean from an epic worktree because the real denylist (`secrets/pii-denylist.txt` via `PII_DENYLIST_FILE`) is gitignored and absent from worktrees. Redact each to the established `<8char-prefix>-REDACTED` convention (UUIDs) / a synthetic-or-redacted placeholder (names/public_ids), preserving any dated live-test observations.

## Rough Timing
Near-term — this is a genuine standing PII exposure in committed docs. Operator should run the certification pass with the real denylist; the scrub itself is mechanical and api-scout-owned (docs/api tree).

## Dependencies & Blockers
- [ ] Requires the real gitignored denylist (`PII_DENYLIST_FILE` / `secrets/pii-denylist.txt`) — operator-run, not worktree-runnable.

## Open Questions
- Should the scrub extend beyond `docs/api/` to a full `docs/` corpus sweep (the byte-gate takes a tree arg — `scripts/check_doc_pii.sh docs/`)? The `docs/api/` exposure is confirmed; other trees are unassessed.
- Is "Nighthawks Navy" an LSB team or an opponent? Either way it is a real GC identifier and must be redacted, but the answer informs whether the denylist already covers it.

## Notes
Source: E-262-09 dispatch (2026-07-13) — the PII safety gate on story 09 surfaced 3 real UUIDs + a team name in the two files being edited (all remediated in-epic), then api-scout's corpus grep found the enumerated pre-existing exposures above in 6 sibling files. All OUT of E-262-09 scope (story 09 never touched them). Recommended action: operator runs `scripts/check_doc_pii.sh docs/api` (and possibly `docs/`) with the real denylist to certify + scrub. Related: `.claude/rules/pii-safety.md` (the byte-gate + coverage footgun), IDEA-004 (PII protection, PROMOTED → E-019). Domain: api-scout (docs/api tree) + operator (denylist).

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
