# IDEA-196: Prod roster residue (phantom "Unknown" stub + transposed surname) survives report generation

## Status
`CANDIDATE`

## Summary
A live prod share link for one team renders **19 roster players where GameChanger has 18**. The extra is a phantom entry at jersey **#4** carrying the literal `"Unknown"` sentinel — the nameless-stub marker written by the canonical player upsert (`src/db/players.py`). It appears in the roster list **only**, in no stat table. Separately, one player's surname (**#18**, initials G.O.) is a **two-letter transposition** on prod; GameChanger matches dev's spelling exactly.

**What makes this an idea rather than a cleanup ticket: both defects SURVIVED a full report generation on prod this morning.** Generation does not self-heal either residue, so a nameless stub with a jersey number, once created, persists indefinitely and renders on the coach-facing share link.

## Why It Matters
This is on the **coach-facing surface** — the share link is the product. A phantom player at a real jersey number is a roster a coach could act on, and it is the one artifact we hand to people outside the operator's own workflow. Dev is clean and prod is not, on the same team, both generated 2026-07-26, which means the residue is environment-specific state rather than a computation defect.

**Why neither residue self-heals** — two different mechanisms, and the second is verifiable from the upsert code itself:

- **The stub.** It is reachable via a `team_rosters` row, so orphan reclamation **correctly** declines to touch it — it is not an orphan by the reachability definition. Nothing else deletes it.
- **The transposed surname, and this is a code-level finding rather than an observation.** `ensure_player_row` overwrites a stored name only when the incoming value is **strictly longer** (`src/db/players.py:29`, with the `Unknown`-is-length-0 carve-out at lines 48-60). A two-letter transposition is **exactly the same length as the correct spelling**, so the longer-wins rule can never replace it. **An equal-length misspelling is permanently sticky by design** — no number of re-crawls or regenerations will correct it. That is a property of the canonical upsert, not a prod accident, and it is the reason "just regenerate" is not a fix.

## Rough Timing
Promote when **the operator wants the prod page fixed**, or when **a second `Unknown` stub appears on any report**. The second trigger is the more important one: one stub is a cleanup, a second is evidence of an active creating path.

## Dependencies & Blockers
- [ ] None blocking capture. Half (a) needs an operator decision about tooling (below); half (b) needs investigation nobody has done.

## Open Questions

**Half (a) — the immediate cleanup for this team on prod:**
- **What tool does this safely?** This is genuinely open. `bb data dedup-players` merges same-name duplicates and **will not touch an `Unknown` stub** — different shape, different predicate. Deleting a `team_rosters` row plus a `players` row on production by hand is not a procedure we have, and the surrounding deletion machinery is destructive on two axes. Do not assume an existing command covers this.
- Does correcting the surname require the same manual route, given that regeneration provably cannot fix it (see above)?

**Half (b) — the mechanism, which is the part worth actually understanding:**
- **What code path creates a player row with a jersey number but no name?** Unidentified. That is the question that decides whether this recurs.
- **Why did the stub never receive the real name?** It was relayed to me as "the upsert's real-name-always-wins rule evidently never received the real name on prod's path," and that reading may be right — but there is a second reading the upsert code suggests and it should not be assumed away: the rule is applied **per player row**, so if the real player upserted into a *different* row than the stub, the stub was never a candidate to receive anything and no amount of correct crawling would heal it. Those two readings imply different fixes. Establish which before designing anything.
- **Should generation reconcile roster-sourced names against the crawl every run?** Raised, not answered. Note this brushes against reconcile-at-load's roster grain, which E-276 deliberately left with **no floor gate** on the operator's prefer-delete ruling — so anyone proposing roster reconciliation here must read that design before touching it rather than reinventing a gate that was removed on purpose.

**⛔ Fix design is explicitly OUT OF SCOPE for this capture** — that belongs to whoever promotes it, after the mechanism question is answered.

## Notes
Source: four-agent report evaluation, 2026-07-26, comparing live prod and dev share links for the same team, both generated that day. The roster findings were **adjudicated against GameChanger by api-scout across 4 GETs** — GC's active roster is 18, dev matches exactly, prod shows 19. So GC is the arbiter here, not an inference from our own two environments disagreeing.

**Calculation-evaluation side facts, recorded so they are not lost and not re-investigated:**
- **~314 facts verified clean per environment**, with **identical computation behavior** across prod and dev. The computation layer is not implicated; this is data residue.
- **3 P/BF cells** were consistent with charted-PA gating — **verified-not-defect, no action**. Recorded specifically so a future reader does not re-open them as a finding.

The clean-computation result is what makes the shape of this idea clear: prod and dev compute identically and disagree only on stored roster state, which localizes the problem to how that state was written rather than how it is read.

Related: [[IDEA-185]] (partial `player_id` churn retiring live stat lines — the adjacent "identity written wrong, set arithmetic cannot see it" family), [[IDEA-188]] and [[IDEA-189]] (the `team_rosters` ↔ dedup coupling).

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
