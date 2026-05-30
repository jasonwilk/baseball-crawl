# IDEA-072: RTK Compression Retrospective Audit

## Status
`CANDIDATE`

## Summary
RTK (Rust Token Killer) compressed and rewrote the output of many shell commands during the period it was active in this project -- not only `pytest` but also `git status`, `git diff`, `git log`, `ls`, and others. It was discovered to silently hide pytest failures (the documented ~67 silent failures across E-173/E-179). This idea is a retrospective audit of what *else* rtk's compression may have hidden or distorted -- truncated diffs, swallowed error lines, hidden non-zero exit codes, compressed-away warnings -- and whether any work or decisions were made on incomplete output that now need re-verification.

## Why It Matters
The pytest failure masking was caught only because it accumulated into a visible problem (67 failures). RTK applied the same compression to other high-output commands that agents and reviewers relied on to make decisions. If a `git diff` was truncated during a review, a reviewer may have approved a change without seeing all of it. If a non-zero exit code was swallowed, an agent may have reported success on a failed operation. The risk is silent: incorrect decisions made on incomplete information leave no error trail. Knowing the blast radius lets us decide whether any past work needs re-checking and informs how much we trust artifacts produced during the rtk era.

## Rough Timing
After E-229 (rtk mechanical removal) completes -- removal is the clean forward fix; this audit is the backward-looking investigation. No hard deadline. Promote when there is appetite to spend investigation effort, or sooner if a concrete instance of rtk-distorted output surfaces during other work.

## Dependencies & Blockers
- [ ] E-229 (rtk removal) should complete first, so the audit is bounded to a closed time window (the rtk era) rather than a moving target.
- [ ] Need to establish the rtk era's start (E-070 introduced rtk; E-082 added the Codex lane) and end (E-229) to scope which epics/reviews fall inside the window.

## Open Questions
- Which commands did rtk actually rewrite/compress? (`pytest` and the git/ls family are known; the full list needs confirmation from rtk's command coverage, e.g. the AGENTS.md table listed `git status`, `git diff`, `git log`, `ls`.)
- Can rtk swallow a non-zero exit code, or does it only alter stdout/stderr text? (Determines whether "reported success on a failure" is even possible.)
- What is the realistic blast radius -- is this a serious re-verification effort or a quick "spot-check a few high-risk reviews and move on"?
- Is there any durable artifact (logs, session transcripts) from the rtk era that records what raw output *would* have been, or is the only path forward re-running operations against current state?
- Which epics/reviews fall inside the rtk window and involved high-output commands (large diffs, full-suite test runs, multi-file git operations)?

## Notes
- Companion to E-229. E-229 removes rtk going forward; this idea looks backward at what its compression may have hidden.
- The known incident: ~67 pytest failures accumulated silently across E-173 and others because `rtk pytest` showed "No tests collected" for both passing and failing runs without `-v`. That was the trigger for the E-224 pytest guardrails (which E-229 removes).
- The rtk pytest guardrails (`-v` requirement, `-x` prohibition, two PreToolUse hooks) were themselves a *symptom-level* fix for one manifestation of this broader problem; this audit examines the rest of the surface.
- Related captures: [[IDEA-016]] (Codex hardening and validation), [[IDEA-068]] (evaluate main-session dispatch behaviors).

---
Created: 2026-05-30
Last reviewed: 2026-05-30
Review by: 2026-08-28
