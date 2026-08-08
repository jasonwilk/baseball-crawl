# IDEA-073: Full-Suite CI Gate (GitHub Actions or Equivalent)

## Status
`CANDIDATE`

## Summary
A continuous-integration gate that runs the full `pytest` suite on every push / pull request and blocks the merge if any test fails — automated belt-and-suspenders beyond the in-context-layer closure-gate convention that E-230-04 establishes.

## Why It Matters
E-230 fixed 56 test failures that accumulated silently while RTK's output compression hid them, and E-230-04 adds a lightweight context-layer convention (code-reviewer full-suite trigger + a "full suite must be green before an epic is DONE" closure gate) to prevent recurrence. That convention depends on an agent or operator actually running the suite at the right moment. A CI gate makes "the suite is green" a machine-enforced, unskippable fact on every change — catching drift even outside the epic/dispatch workflow (e.g., a direct hotfix, an out-of-band commit). It is the strongest version of "keep it green."

## Rough Timing
Deferred per simple-first. claude-architect assessed it as too heavy for a solo operator right now relative to the in-context-layer convention E-230-04 provides. Promote when: the project gains additional contributors, or commits routinely land outside the agent dispatch workflow, or the E-230-04 convention proves insufficient (a failure accumulates again despite it).

## Dependencies & Blockers
- [ ] E-230-04 (the lightweight closure-gate convention) lands first — this idea is the heavier alternative, evaluated against it.
- [ ] A decision on CI platform/runner for this repo (GitHub Actions assumes a GitHub remote; the project's deployment is a home Linux server + Cloudflare Tunnel, so the CI host is a separate choice).

## Open Questions
- Which CI platform fits a solo-operator, home-server-deployed project (GitHub Actions, a self-hosted runner, a git pre-push hook, or something lighter)?
- Does the full suite (~4400 tests, ~91s locally) run fast and hermetically enough in CI (no real HTTP, no credentials, no `data/`)?
- Does a CI gate duplicate or replace the E-230-04 code-reviewer/closure convention, or sit alongside it as defense-in-depth?
- Is a pre-push git hook a sufficient lighter-weight midpoint before committing to full CI infrastructure?

## Notes
Originating context: E-230 (Fix the 56 Post-RTK Test-Suite Failures). This idea is the deliberately-deferred heavier option; E-230-04 is the lightweight in-context-layer convention chosen for now. Related: [[IDEA-016]] (Codex hardening and validation). The E-229-removed pytest-verbose/exitfirst machinery is NOT to be reintroduced — that was a symptom-level RTK workaround, not a CI gate.

---
Created: 2026-05-31
Last reviewed: 2026-05-31
Review by: 2026-08-29
