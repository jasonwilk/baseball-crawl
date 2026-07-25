# IDEA-173: Clearing the send cap destroys the data that would justify raising it

## Status
`CANDIDATE`

## Summary
The dispatch send cap has two unblock paths, and they are not equivalent: **raising the threshold preserves the measurement, clearing the counter destroys it.** During E-272 the operator cleared the counter mid-story twice to unblock the main session, and the send-cap log's seven staging-boundary rows for this epic now include two corrupted-low entries (rows 2 and 7 read 2 and 4 against true figures that are higher). If that log exists to accumulate evidence for revisiting the threshold, this epic contributed partly unusable data.

## Why It Matters
This is a self-defeating instrument, and the failure is structural rather than a mistake anyone made.

The cap exists to bound dispatch cost. The log exists to tell us whether the bound is set right. But the fastest way to unblock a live dispatch — clear the counter — is precisely the action that erases the row's evidentiary value, and it is taken under time pressure, mid-story, by an operator who wants work to continue. So the data most likely to be destroyed is the data from the **longest, most send-heavy dispatches** — exactly the runs that would justify a change. The log systematically under-samples its own strongest evidence, and it does so silently: a cleared row looks like a low row, not like a missing one.

E-272 is a decent illustration. It ran four stories across three implementer types with two closure reviews and a Codex pass, so it is a genuinely heavy dispatch — and two of its seven rows now understate what it cost.

Concrete, cheap consequence to avoid: someone later reads the log, sees rows reading 2 and 4, and concludes the 25 threshold is generous. The opposite is true for those rows.

## Rough Timing
No urgency on its own. Natural moments:
- Whenever the 25 threshold is next revisited — this should be resolved BEFORE anyone reasons from the log, not after.
- Alongside any other dispatch-cost-accounting work (E-260's is the existing home for this concern).

## Dependencies & Blockers
- [ ] None technically. Needs a decision on whether the log is intended as an evidence base at all — if it is only an operational counter, there is nothing to fix.

## Open Questions
- **Is the log actually meant to accumulate threshold evidence?** If yes this matters; if it is purely an operational counter with no analytic purpose, close this. Worth settling first — it decides whether there is a problem.
- Can a reset be made **non-destructive** — recording the pre-reset value, or marking the row as reset rather than overwriting it? A row flagged "cleared at N" is still usable data and still unblocks the operator. That looks like the whole fix.
- Should raising the threshold be the *documented default* unblock, with clearing reserved for cases where the count is genuinely wrong? That is a guidance change rather than a code change, and it is nearly free.
- Are the two corrupted E-272 rows recoverable from the message history, or should they be marked unusable? Marking them is fine — a known-bad row is better than a plausible-looking wrong one.

## Notes
Observed and reported by the main session (team-lead) during E-272 closure, explicitly as an observation about the dispatch instrumentation rather than a complaint about being blocked. Captured here rather than left in a message thread because message threads do not survive the epic, and this only pays off the next time someone examines the threshold.

Recorded for the record: the reset was the right operational call each time — it unblocked live work. The problem is that the tooling makes the right operational call and the right measurement call mutually exclusive, which is a design gap, not an operator error.

Related: [[IDEA-161]] (main-session durable record surface — same theme: the orchestrator's own operational behavior leaves no durable trace), and E-260's dispatch-cost-accounting work, which is the natural home if this is promoted.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
