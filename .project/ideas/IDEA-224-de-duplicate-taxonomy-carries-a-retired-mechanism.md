# IDEA-224: data-engineer's duplicate-class taxonomy carries a mechanism E-278 retired

## Status
`CANDIDATE` — **routed to data-engineer; nobody else may fix it.**

## Summary

`.claude/agent-memory/data-engineer/game_duplicate_class_taxonomy.md` describes the
date-split duplicate class in terms E-278-04 retired. Found by code-reviewer's Step 1a
invariant audit at E-278 closure. **data-engineer was not on that dispatch team**, and the
own-memory carve-out in `.claude/rules/agent-routing.md` reserves an agent's memory
directory to that agent — so this could not be fixed in the epic that falsified it, and a
note in a completion message would have evaporated with the dispatch. Hence an idea.

**Three distinct shapes, which is why a single find-and-replace will not do it:**

1. **A stale attribute name**, `GameSummaryEntry.last_scoring_update`, with two rotted line
   citations. The field is now `date_source_instant` (E-278-05) and the old token survives
   nowhere in `src/` or `tests/`.
2. **A section header encoding the retired claim itself** — a fallback that "returns UTC
   instead of failing closed." That behavior is gone: `derive_local_date` now returns `None`
   on an unresolvable zone and `_derive_game_date` stores a sentinel rather than a
   UTC-sliced date. A header is a claim, and this one is now false.
3. **`:68-69` is now exactly BACKWARDS** — it describes the pre-E-278 degradation direction.

## ⚠️ The trap: one paragraph must NOT be corrected

**The 24-row measurement in the same section is EVIDENCE and must be preserved.**
It records what was observed in a specific population at a specific time. A tidying pass
that corrects the mechanism prose and "updates" the adjacent figure would destroy a record
while fixing a sentence — the exact failure the criterion-vs-evidence cut in
`.claude/rules/tool-output-integrity.md` exists to prevent, sitting two paragraphs apart in
one file.

Note also that E-278 produced **three** different alias-row counts against **three different
populations** (24 dev stored rows / 8 of 16 prod rows / 29 of 1064 reachable events). They
must not be reconciled into one number, and a corrector who assumes the 24 is stale because
another number exists would be wrong.

## Why It Matters

Agent-memory files are loaded as authoritative context by the agent that owns them. A
taxonomy describing a mechanism that no longer exists will be applied by data-engineer to
the next duplicate-class question — and the failure is silent, because the file reads as
settled prior work rather than as a claim needing verification. The specific hazard is shape
3: prose that is *backwards* does not merely fail to help, it actively argues for the wrong
direction.

This is also a worked instance of a general gap: **`scripts/check_doc_pii.sh` and the
context-ratchet both watch `.claude/`, but nothing detects an agent-memory claim that the
code has falsified.** Only a human or an audit that happens to brush the file will find it.

## Rough Timing

**Next time data-engineer is spawned for any reason.** It is a small, self-contained
correction to a file DE already owns, and it should ride whatever brings DE back rather than
justifying its own dispatch. There is no urgency: the false claims mislead only on
duplicate-class work, and E-278 already fixed the underlying code.

## Dependencies & Blockers
- [ ] **Requires data-engineer.** The own-memory carve-out reserves this directory to DE;
      claude-architect's context-layer authority does not extend into another agent's memory.

## Open Questions

- **Is the taxonomy's CLASS SCHEME still right, or only its mechanism prose?** E-278
  established that date-split twins arise from **two** independent mechanisms with opposite
  polarity (an unresolvable timezone alias, +1 day; a full-day date marker localized as an
  instant, −1 day). The taxonomy predates the second. Whether that is a new class or a
  sub-case of the existing one is DE's call, and it is a more interesting question than the
  prose fix.

## Notes

Found 2026-07-28 by code-reviewer during the E-278 Step 1a invariant audit — by a **semantic
read**, not a token grep. Shape 2 (the section header) carries none of the identifiers a
grep would search for, and step 1 of `.claude/rules/doc-sweep.md`'s procedure would have
reported this file clean.

Related: [[IDEA-225]] and [[IDEA-226]] are the same defect class in api-scout's and
baseball-coach's memory, found in the same audit. [[IDEA-218]] is the underlying duplicate
class, now `RESOLVED`. [[IDEA-204]] records the broader gap that agent-memory sits outside
automated gate coverage.

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
