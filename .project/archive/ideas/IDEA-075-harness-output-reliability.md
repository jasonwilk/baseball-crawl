# IDEA-075: Harness Output-Reliability Fix (stop the garble/drop/silent-edit thrash)

**Status**: PROMOTED
<!-- CANDIDATE / PROMOTED / DEFERRED / DISCARDED -->
Promoted to E-231 (harness-output-reliability) on 2026-06-07.

**Last reviewed**: 2026-05-31
**Review by**: 2026-08-29

## Summary

During multi-agent dispatch the tool I/O channel intermittently (a) returns **empty** output, (b) returns **garbled/stale** output (wrong line numbers, fabricated content, a different file's bytes, commands echoed instead of executed), and (c) reports Write/Edit **"success" on edits that did not fully land** (silent partial-edit failure). This is an **agent-infrastructure / harness reliability** problem, not an individual-agent behavior problem — and a durable memory ("read before you assert") is necessary but **insufficient**, because under a flaky channel an agent can read carefully and still act on garbage. claude-architect should plan an actual structural fix.

## Why (The Problem or Opportunity)

In the E-230 dispatch (2026-05-31) this flakiness caused **repeated, expensive thrash across every agent** (main session, PM, CR, CA, SE):
- The main session **dismissed/mischaracterized a Codex review before reading the actual findings** (fired a triage question off a 2KB preview of a 373KB persisted result, called 4 valid findings "2 LOW already-adjudicated"). Caught and corrected, but only after the wrong framing nearly reached a decision.
- PM raised, then retracted, **two phantom AC-6 defects** and a **phantom trailing-line** alarm — all garbled-read artifacts.
- CR **fabricated a warnings breakdown** (invented `utcnow`/pytest-config warnings not in the log), then corrected to the real 2 Starlette deprecations.
- SE reported a **"(6 games) test-isolation leak"** that was pure garbled-output noise (disproven by file-captured re-runs), plus multiple miscounted greps.
- CA hit **silent Edit failures** and dark read-backs, repeatedly unable to self-verify correct edits.
- The main session also **mischaracterized its own grep output** by composing relay messages in the same tool-batch as the commands whose output they reported (stating expected values, not actual).

The compensating disciplines that *worked* — write-output-to-a-file-then-read-it-back, grep-relay (main session runs the grep for a dark agent), re-read-to-self-consistency, prove-teeth-by-breaking-then-restoring, never-report-a-number-not-just-seen — are all **manual workarounds**. They cost enormous coordination overhead and they fail silently when an agent forgets them. The opportunity: make the harness either reliable or **self-defending**, so correctness doesn't depend on every agent remembering to distrust their own tools.

## Timing / Trigger

Revisit/promote when: the next multi-agent dispatch shows the same garble/drop/silent-edit pattern (confirming it's systemic, not a one-day blip), OR if the thrash recurs at a cost that outweighs the fix. Plan it before the next large epic dispatch if the flakiness persists. Not urgent if the channel proves stable on the next run — but do not discard without confirming it was a transient environment issue.

## Blockers / Dependencies

- Need to determine whether the root cause is (a) an Anthropic/Claude Code harness bug worth reporting upstream, (b) a local resource/load condition (the "system is experiencing high load" notices suggest concurrency/load — possibly too many concurrent agents/tool calls), or (c) a devcontainer/FS quirk. Diagnosis gates the fix shape.
- claude-architect owns the design (agent infrastructure / hooks / skills). Per the user (2026-05-31): they want **CA to plan an actual harness fix**, explicitly NOT just a memory.

## Open Questions

- Is the garbling correlated with output size (the 373KB Codex result, large diffs) and/or with concurrency (4 active agents)? If load-correlated, would **capping concurrent agents/tool-calls** during dispatch reduce it?
- Can we codify the working workarounds into **tooling** rather than discipline? E.g.:
  - a verified-read helper/skill that always writes to a temp file and reads back, retrying until two reads agree (self-consistency check);
  - a **post-Edit verification hook** that re-reads the edited region and fails loudly if the new_string isn't present (catches silent partial-edit failures deterministically);
  - a retry-on-empty wrapper for Read/Bash that re-issues when output is empty/echoed;
  - a "results must come from output already in context" lint for relay messages (don't co-batch a report with the command it reports).
- Should reviewer findings (Codex/CR) be **force-read-to-completion** before any triage tool can be invoked — a structural gate, not a guideline?
- Is the right altitude a **harness/config change** (concurrency caps, output handling) or a **skill/hook layer** that makes agents robust regardless? Possibly both.

## Notes

A behavioral memory was captured this session (`feedback_read_findings_before_triage.md` in the main session's memory: read findings to completion before characterizing; never co-batch a decision/relay with the command that feeds it; quote actual output, not expected; sweep the whole pattern not just cited lines). PM also logged sibling lessons (clean-re-read-before-defect; don't-rationalize-weak-assertions). This idea is the **structural complement** to those memories — the user's point is that memories alone won't stop the thrash; the harness/tooling needs an actual fix.

## Related

- Memory: `feedback_read_findings_before_triage.md` (main session), PM's `feedback_clean_reread_before_defect.md` + `feedback_dont_rationalize_weak_assertions.md` (committed in E-230, `2fb6e00`).
- E-230 (the dispatch where this surfaced; `.project/archive/E-230-test-suite-fix/`).
- IDEA-072 (RTK Compression Retrospective Audit) — adjacent "masked/distorted output hid problems" theme.
