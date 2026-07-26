# Sub-lead dispatch experiment (P2 first, then P3 if P2 passes)

Precondition: P1 landed + verified + clean tree. Navigator (this session) spawns ONE
named agent per epic that runs the implement workflow one level down.

## Sub-lead spawn prompt skeleton (fill epic specifics at spawn time)

- You are dispatch-lead for <epic>. Run `.claude/skills/implement/SKILL.md` faithfully:
  you take the MAIN-SESSION role described there (worktree lifecycle, spawn PM +
  implementers + code-reviewer yourself, route reviews, staging boundary, closure
  sequence). All standing rules bind: dispatch-pattern.md roles, worktree-isolation.md,
  agent-routing.md, PM owns statuses/ACs, code-reviewer gates every story.
- DEVIATIONS from the skill (they exist because you are one level down):
  1. Closure-commit approval: you do NOT commit. At the staged-diff point, send me the
     `git diff --cached --stat` summary and STOP; I relay to the operator; commit only
     on my explicit go. (feedback_closure_commit_approval preserved.)
  2. Anything the skill says to ask the user: ask ME via SendMessage instead.
  3. Delivery contract: report via SendMessage to "main". Per-story boundary: <=3
     sentences (story id, verdict, surprises-or-none). Closure report: <=500 words.
     NEVER paste diffs, test output, or file contents — cite paths, test names, SHAs.
  4. Relay discipline (binding): never report a teammate position as settled without a
     single artifact its author(s) explicitly endorse; when two agents disagree, send
     me both positions, not your synthesis.
- Escalate, never improvise: dispatch failures follow workflow-discipline.md Dispatch
  Failure Protocol, routed to me.
  5. Context-health protocol (from P1, where PM self-reporting low context enabled a
     graceful drain): require every long-lived teammate (PM, code-reviewer) to state
     context pressure when it becomes material; when one reports low, DRAIN it —
     bounded task list, told to stop after, durable state flushed to its on-disk
     files (story statuses, PM memory) — then respawn fresh from disk artifacts if
     more is needed. Never assign open-ended work to an agent that has reported low.
     You (sub-lead) report your own context health in every per-story boundary
     message: one word — ok / tight / low.

## What we measure (fill during run)

| Metric | P2 actual | Notes |
|---|---|---|
| Navigator inbound msgs / bytes from sub-lead | | target: <20 msgs, <15KB |
| Operator interventions needed | | target: kickoff + closure approval only |
| Sub-lead chases needed (idle without delivery) | | delivery clause supposed to fix |
| Skill steps that misfired one level down | | each = a workflow-amendment candidate |
| Hook/permission surprises (worktree-guard mode-1, git ops, PII gate) | | |
| Relay violations (positions forwarded unsettled) | | P1 hub: 5 |
| Verifier verdict vs sub-lead closure claims | | any delta = report-integrity finding |

## Known risks to watch (pre-registered so hiccups classify fast)

1. Worktree-guard: sub-lead's team writes worktree-only; mode-1 blocks main-checkout
   writes machine-wide while the worktree exists — MY edits to scratchpad unaffected,
   but any main-checkout doc write I attempt mid-epic will be denied (expected, fine).
2. Nested spawn depth: sub-lead spawns PM/SE/CR (depth 2). grade-48b proved depth-2
   works for task agents; UNPROVEN: SendMessage team semantics at depth 2 (PM
   long-lived resume, shared task list). If PM-at-depth-2 can't be resumed across
   stories, that's finding #1 and the fallback is sub-lead keeps PM alive continuously.
3. Approval laundering guard: sub-lead cannot approve its own closure; the staged-diff
   pause is load-bearing. If it commits without the pause, halt the experiment —
   that's a critical workflow finding, not a hiccup.
4. Idle-notification storms: teammate idles at depth 2 may notify ME (observed with
   grade-48b's children notifying main). If noisy, note volume; candidate fix is
   sub-lead using plain Agent-tool children rather than named teammates for one-shots.

## Post-experiment deliverable

Same eval as P1 (axes A-D) PLUS a workflow-amendment list: each entry = observed
misfire -> smallest change (spawn-prompt clause vs skill edit vs dispatch-pattern.md
paragraph vs "none, worked as written"). Layer edits only with the misfire as citation.
