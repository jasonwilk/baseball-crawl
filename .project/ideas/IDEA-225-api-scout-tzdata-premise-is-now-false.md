# IDEA-225: api-scout's timezone note rests on a premise E-278 falsified

## Status
`CANDIDATE` — **routed to api-scout; nobody else may fix it.**

## Summary

`.claude/agent-memory/api-scout/public-games-timezone-and-fullday.md` states that **"the
`tzdata` PyPI package is not installed."** That was true when written and is **false as of
E-278-04**, which declared `tzdata` in `requirements.in`, `requirements.txt`,
`requirements-dev.txt` and `pyproject.toml`.

**The severity is in the position of the claim, not its size: it is the premise the whole
section rests on.** The section's reasoning about which timezone strings resolve, and what
happens when one does not, is built on top of it — so a reader who accepts the premise
inherits conclusions that no longer follow. `US/Central`, `US/Pacific`, `US/Eastern`,
`US/Arizona` and `Canada/Eastern` all resolve now.

Found by code-reviewer's Step 1a invariant audit at E-278 closure. **api-scout was not on
that dispatch team**, and the own-memory carve-out reserves the directory to api-scout, so
it could not be corrected in the epic that falsified it.

## ⚠️ One qualifier that must survive the correction

**The fix does not reach production until the app image is rebuilt.** `python:3.13-slim`
omits the tzdata backward links and the Dockerfile apt-installs only `curl` and `sqlite3`,
so declaring the dependency fixed dev and CI immediately while the running production
container kept deriving UTC dates for aliased rows. Verified inside the running container
during E-278 planning. **A correction that simply flips "not installed" to "installed" would
be wrong for production until that rebuild lands** — and would be the more dangerous error,
because it reads as reassuring.

## Why It Matters

api-scout is the agent that adjudicates payload-field semantics, and this file is where it
would look before ruling on a timezone question. A false premise at the top of a reasoning
chain is the worst position for one: every conclusion below it still *reads* sound, and
nothing in the file signals that its foundation moved.

The claim is also the kind that decays **silently and asymmetrically** — a dependency
appearing is invisible to anyone reading the note, whereas a dependency disappearing would
break tests loudly.

## Rough Timing

**Next time api-scout is spawned for any reason** — it is a small correction to a file
api-scout already owns and should ride whatever brings it back. No urgency: the underlying
code is fixed, and the note misleads only on timezone-resolution questions.

## Dependencies & Blockers
- [ ] **Requires api-scout.** Own-memory carve-out.

## Open Questions

- **Does the note's `is_full_day` half need anything?** E-278-04 made `is_full_day` load-bearing
  — it is now read at ingest and switches the date-derivation path — where previously it was
  documented but read by nothing. That is a promotion in status rather than a falsification,
  but the note may describe it as unused.

## Notes

Found 2026-07-28 by code-reviewer during the E-278 Step 1a invariant audit. Same defect class
as [[IDEA-224]] (data-engineer) and [[IDEA-226]] (baseball-coach), all three found in one
audit, none fixable by the epic that caused them.

Worth recording as the pattern rather than three coincidences: **an epic that changes a
dependency, a field's semantics, or a degradation path will falsify claims in the memory of
agents who are not on its dispatch team, and no gate detects it.** See [[IDEA-204]].

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
