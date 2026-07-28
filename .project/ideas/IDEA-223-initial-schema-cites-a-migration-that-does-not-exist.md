# IDEA-223: `001_initial_schema.sql` attributes two columns to a migration that does not exist

## Status
`CANDIDATE`

## Summary
`migrations/001_initial_schema.sql` says `games.start_time` and `games.timezone` come
"from migration 014" in four places. There is no migration 013 or 014 — the set tops out
at `012`, and both columns are defined in `001_initial_schema.sql` itself. Two of the four
are inline in the `games` DDL, so they surface in `.schema games` output.

## Why It Matters

**This is a defect generator, not just a stale comment.** It has already produced one real
error: an expert report cited "(migration 014)" as the columns' provenance during E-278
planning. That was initially logged as the report's mistake — until api-scout traced it and
found the repo had handed it over. Correcting a downstream citation leaves the generator
running: the next agent to open the canonical schema file, or to run `.schema games` on
those columns, makes the identical error with no reason to doubt it.

Exact locations, verified independently three times (PM, api-scout, code-reviewer):

- line 135 — `-- start_time: ISO 8601 datetime (from migration 014).`
- line 136 — `-- timezone: IANA timezone identifier (from migration 014).`
- line 147 — `start_time     TEXT,     -- ISO 8601 datetime (from 014)`
- line 148 — `timezone       TEXT,     -- IANA timezone (from 014)`

## Rough Timing

No urgency — the columns are real and correctly defined; only the provenance claim is
false. Promote when data-engineer is next in `migrations/` for any reason, or when a
context-layer pass is correcting stale prose in `.claude/rules/data-model.md`.

## Dependencies & Blockers

- [ ] **Needs a data-engineer ruling on WHERE the correction goes**, which is the whole
      question. See Open Questions.

## Open Questions

- **Does the fix edit the applied migration, or somewhere else?** DE's standing ruling
  (`.claude/agent-memory/data-engineer/migration-immutability-basis.md`, E-277) says keep
  the strict append-only reading and *"correct stale prose where readers actually look
  (`.claude/rules/data-model.md`), and let the applied migration stand as a record of what
  was applied."* Applied literally that leaves the generator running in the schema file —
  a reader running `.schema games` never sees `data-model.md`. So the real question is
  whether this case is the exception DE's ruling anticipates, or whether the mitigation is
  a correcting note elsewhere and the schema comment stands. **DE's call, not PM's.**
- If the answer is "correct it in place", does that need a narrow, recorded carve-out so it
  does not become the general "comments may be edited when judged inert" precedent DE's
  ruling is specifically guarding against?

## Notes

**Filed after a PM reversal, recorded so the reasoning is not repeated.** E-278-04 briefly
carried this as AC-9 with a PM-granted routing exception letting an SE-only team edit the
comments. The rationale was that `apply_migrations.py` tracks by filename with no checksum,
so a comment edit is inert. **DE had already established that exact fact and ruled it
insufficient** — the durable reason being that no mechanical boundary separates an inert
comment from one documenting DDL semantics (a CHECK vocabulary, a DEFAULT, an FK's
`ON DELETE` choice). AC-9 and the exception were both withdrawn.

Two transferable points. **Mechanical unenforceability is not permission** — "nothing will
catch this" is not evidence that a change is safe. And **decision routing binds PM too**:
migrations are DE's domain, DE had ruled, and a PM scope call does not override a domain
owner inside their own domain.

The counter-argument that motivated folding it into an epic in the first place still stands
as a real cost, and is recorded here so it is weighed rather than rediscovered: **an idea
filed for a stale comment tends to outlive the epic that would have made it cheap.** That
is why this file carries the exact line numbers and the full reasoning — so whoever picks
it up spends no time re-deriving any of it.

Related: [[IDEA-215]] (a docstring describing behavior the code does not have — same
prose-defect class, same module family).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
