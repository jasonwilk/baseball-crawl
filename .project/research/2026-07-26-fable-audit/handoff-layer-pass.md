# Consolidated layer pass — handoff (supersedes handoff-P4-memory-prune.md and
# handoff-P5-ratchet-demotion.md as the single CA-led pass; run AFTER E-276 closes)

Invoke claude-architect (CA leads; PM consults on the ratchet scope call). THIS
BRIEF IS A RELAY — verify every claim against the cited files; the file wins.
Inputs, all committed under `.project/research/2026-07-26-fable-audit/`:
`workflow-amendment-list.md` (A/B tiers + measurement caveats),
`model-behavior-reference-v2.md` (the four-tier architecture + checklist),
`claude-self-read-findings.md` (passage-level prune/keep inventories),
`codex-review-output.md` + `codex-sol-review-output.md` (external reviews),
plus the four vendor guides (re-fetch; dated 2026-07-26).

## Deliverables, in order

1. **Install the reference**: model-behavior-reference-v2 -> CA memory as
   `model-behavior-reference.md` (apply v2's own provenance-tag structure;
   record dated alias->model resolutions per checklist item 3).
2. **Ratchet demotion** (operator decision, standing): reconcile-scoreboard
   becomes a pure diagnostic — gate/baseline/closure-exception machinery
   removed; `self_games == 0` keeps a named standalone home; E-256 closure-smoke
   coupling checked before cutting; CLAUDE.md's reconcile-scoreboard passage and
   Operating-Principle gate-mechanics collapse to ~3 lines. Sweep per
   doc-sweep.md INCLUDING the judgments-that-depended test (PM memory
   operator-followups, closure skills carry ratchet procedure without the
   token "ratchet").
3. **Surgical prune under the four-tier test** (v2 "Architecture"): per
   passage — tier? who loads it (paths-scope before always-load)? mid-section
   splits allowed. Start from claude-self-read-findings.md's ranked lists.
   NEVER prune tier-2 shared policy (relay discipline, destructive-action
   boundaries, evidence-before-claims) under tier-4 authority — the
   verification taxonomy in v2 is binding. Every removal cites its defect +
   recurrence artifact + re-check point (amendment G3/M7). Sonnet visibility
   check on every shared-file change: consultation agents load ONLY layer +
   own definition.
4. **Codify A1-A6** from workflow-amendment-list.md (each carries citations):
   brief-is-a-relay/file-wins + delivery-channel clause -> dispatch-pattern.md
   and skill spawn templates; counterexample-before-READY for safety absolutes
   -> spec-review + code-reviewer checklists; discovery-artifact-precedes-
   planning -> plan skill prerequisites; context-drain protocol + post-compact
   re-grounding (A5+A6) -> dispatch-pattern.md. Also fix the stale "spawning is
   one-level-deep — a platform constraint" line in workflow-discipline.md
   [LOCAL-EVAL 2026-07-25: depth-2 spawns worked; grade-48b's children].
5. **Per-agent adapter + execution-profile audit** (A8 + v2 checklist 1/3):
   every agent's (model alias, dated resolution, effort incl. the three
   effort-less sonnet agents, thinking default, tool surface) reviewed against
   the reference; Opus 5 agents lose type-1 self-recheck lines and gain
   scope-constraint; any Fable-pinned agent gains ground-progress-claims;
   cross-model commissions rule (checklist 7) recorded.
6. **Memory prune** (old P4, last): stale-list seeds in
   handoff-P4-memory-prune.md still apply, PLUS the residue of everything this
   pass retires. Deletion list -> operator approval BEFORE executing.
   Net-negative lines expected for the whole pass.

## MANDATE SCALED UP (operator, 2026-07-26): restructure-to-vendor-shape, not
## surgical prune

Deliverable 3 becomes REHOME + PRUNE: target end-state is the vendor shape —
CLAUDE.md = brief repo description + genuine gotchas + pointers; long
Commands/Architecture blocks -> paths-scoped rules and on-demand reference
files; tool quirks -> tool-adjacent placement (the ugrep quirk bit the E-276
dispatch TWICE despite its rules paragraph — salience dilution, not missing
content; CR's AST workaround shows the knowledge works when retrieved);
duplications -> single placement; DELETE only scaffolding/conflict classes,
each with defect + recurrence citation; anything uncitable is REHOMED, never
deleted. Coordinate with E-276-05's shipped CLAUDE.md rewrite — no double-edit.

Deliverable 6 becomes NEAR-COMPLETE memory prune: durable copies of the good
lessons now live in committed rules + this research dir — memory entries
duplicating them are redundant drafts (vendor auto-memory rule applied
retroactively). Reset aggressively; selectively re-bootstrap per the Fable
memory guidance; deletion list to the operator before execution.

## Vendor method addendum (claude.com blog: "The new rules of context
## engineering for Claude 5 generation models", fetched 2026-07-26)

Binds deliverable 3's METHOD; all [VENDOR]:
- "Unhobbling": over-constraint itself degrades 5-gen models — CONFLICTING or
  overlapping guidance forces excessive deliberation. The prune hunts a second
  class beyond self-recheck scaffolding: instruction PAIRS in tension.
- Progressive disclosure = the vendor-named who-loads-this test: detailed
  verification/review guidance belongs in SKILLS selectively activated;
  CLAUDE.md "briefly describes what your repo is for," gotchas over inferables.
- Repetition -> single placement: deliberate defense-in-depth duplication is an
  old-generation pattern; keep only where two AUDIENCES (not two reminders)
  need it.
- Examples -> interface design: prefer expressive parameter enums over
  exhaustive worked examples in skills/tools.
- Run `claude doctor` as a DIAGNOSTIC INPUT before deliverable 3 — second
  opinion, not autopilot; accepted suggestions still need citations.

## Procedure-fidelity fixes for the implement skill (defect-cited, E-276
## dispatch, n=2 in one epic — add as deliverable 4b)

The dispatch hub skipped Phase 4 (Codex) and then closure steps 7-11, both
while able to quote the omitted step; its own diagnosis: "I treated the
procedure as a list of things to report on rather than a sequence to execute."
Root pattern: procedures executed from post-compact/ambient memory are RELAYED
procedures. Fixes, both end-state-shaped (file-wins for procedures):
(a) Phase-5 entry precondition: if the review modifier is active, verify the
    Codex findings artifact EXISTS before the closure integration review; if
    absent, run Phase 4 now.
(b) Closure completion = a CHECKED END-STATE, not a step list: the skill's
    final step requires command-output evidence — `git worktree list` shows
    main only; epic branch deleted; epic dir archived; `git status` clean;
    team shut down — before "closure complete" may be reported.
(c) Note for dispatch-pattern.md: the hub had "no second party checking my
    sequencing" (its words) — every artifact role has a verifier; the
    orchestrator's PROCEDURE does not. The navigator/sub-lead pairing covers
    this (the navigator independently flagged the un-removed worktree before
    the operator asked); name sequencing-check as part of that role.

## Constraints

- Freeze discipline: every change defect- or vendor-cited (the citations are in
  the inputs; no uncited edits ride along).
- Validation (v2 checklist 4, scoped): one table-read per affected model class
  of the pruned layer + watch steering/selfcorr telemetry at the next epic of
  each class. No eval-matrix machinery.
- Commit shape: one commit per deliverable (1-6), operator approves each diff;
  expect the pass overall to REMOVE more bytes than it adds.
- The E-276-05 story will already have rewritten CLAUDE.md's reconcile
  paragraphs — coordinate; do not double-edit.
