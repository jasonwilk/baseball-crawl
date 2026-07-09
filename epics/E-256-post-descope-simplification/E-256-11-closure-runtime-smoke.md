# E-256-11: Closure runtime smoke (Step 1d)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, `implement/SKILL.md` defines a Phase 5 **Step 1d "closure runtime smoke"** (wired into Step 8 as sub-step 5b), and `code-reviewer.md` carries the two carve-outs that authorize the code-reviewer to run it. This is the reports flow's first live runtime gate at closure — the thing that would have caught a physically-impossible FPS stat and a rest-day UTC bug that both shipped through green closures.

## Context
Design is claude-architect's (per `feedback_domain_expert_designs`: CA designs the story, PM frames the ACs). The full constraint set is Technical Notes §2 (Step 1d not 1c) and §3 (design constraints). The load-bearing points: it runs in the **main checkout post-apply** against the **live dev DB** (a fixture DB passes vacuously); `bb report generate` runs **before** `reconcile-scoreboard`; the fixture is a gitignored **`.smoke-fixture`** file (NOT `.env`, which the secret-read-guard hook would make unreadable); **env-FAIL escalates and holds the closure, epic-FAIL remediates**; and **CR self-evaluates the trigger** via its own `git diff --cached --stat main`. It consumes story 05's printed reference date as the headline invariant.

## Acceptance Criteria
- [ ] **AC-1**: Given `implement/SKILL.md`, when this story is complete, then a Phase 5 **Step 1d "closure runtime smoke"** is defined and wired into Step 8 as sub-step **5b**, conditional on the epic's staged diff touching any trigger path in Technical Notes §3 (`src/reports/`, `src/db/`, `src/api/`, `src/gamechanger/loaders/`, `src/gamechanger/parsers/`, `migrations/`).
- [ ] **AC-2**: Given Step 1d, when it is defined, then it specifies (per Technical Notes §3): runs in the main checkout post-apply against the live dev DB; the smoke reads the two-field `.smoke-fixture` (`generate=<public_id>` and `morning-run=<lsb-url-1> <lsb-url-2> …`, parsed via `grep '^generate='` / `'^morning-run='`); `bb report generate <generate-field public_id>` runs BEFORE `bb report reconcile-scoreboard`; asserts the headline invariant (`reference_date` == today in operating tz, read from story 05's printed line); runs `curl /health`; folds in `reconcile-scoreboard`'s axis counters (`self_games` == 0, `dropped_pitch_events`, `no_plays_units`); and runs `bb report morning-run --dry-run <morning-run-field urls>` **asserting exit 0 ONLY** (the resolve-and-preview path ran without crashing — do NOT assert games-found or slots-resolved). The morning-run step writes nothing and is **order-independent** — run it any time after `curl /health`, NOT inside the `generate`→`reconcile-scoreboard` ordering.
- [ ] **AC-2b**: Given the morning-run step's honest limitation, when Step 1d is defined, then the skill text STATES that on an arbitrary closure date the LSB teams usually have no games, so the resolution ladder does not fire and `--dry-run` skips the real-run alerting preflight — what morning-run reliably gates is the **entry-point wiring + schedule-read API path + `operating_today()` timezone-filter plumbing** (a genuine forward-feature surface `generate` never touches, but shallower than the resolution ladder). Do NOT deepen it with a hardcoded `--date` (that bakes a real date into a committed file).
- [ ] **AC-3**: Given Step 1d, when it is defined, then `bb report verify-aggregates` is named as a **HARD sub-check for loader/aggregate epics** (guarding the cache-staleness window that E-256's own closure sits inside — Technical Notes §1), with the honest limitation stated in the skill text that whole-game plays idempotency means the scoreboard cannot see an ingestion-parser change until data is re-ingested.
- [ ] **AC-4**: Given Step 1d, when it is defined, then it opens with a **preflight** (`.smoke-fixture` present AND both `generate=` and `morning-run=` fields non-empty; stack up; creds live; baseline exists) whose failure **escalates to the user and holds the closure** and does **NOT** enter the remediation loop (a missing/empty fixture field is an env-FAIL, not an epic-FAIL); only post-preflight failures are epic-FAILs that route into the Phase 4a remediation loop like a red suite.
- [ ] **AC-5**: Given `.claude/agents/code-reviewer.md`, when this story is complete, then it carries BOTH required carve-outs (Technical Notes §3): a named second exception in the **Test-Execution-Constraint** (beside the closure-pytest carve-out), AND an exception to **Anti-Pattern #5's read-only Bash allowlist** authorizing the DB-mutating `bb report generate`.
- [ ] **AC-6**: Given the trigger evaluation, when Step 1d runs, then the **code-reviewer** performs the `git diff --cached --stat main` read itself and reports "not triggered" when no trigger path matches — the main session does not perform that read (a `dispatch-pattern.md` domain-work boundary).
- [ ] **AC-7**: Given the Step 1d skill text, when this story is complete, then it **references** `docs/admin/production-deployment.md` as the smoke-procedure doc (the doc CONTENT is written by story 10, docs-writer — this story does NOT edit `docs/admin/`, per CA's Q1 routing rule), and this story adds `.smoke-fixture` to `.gitignore` and documents the **two-field** `.smoke-fixture` convention in the skill text (`generate=<public_id>` + `morning-run=<lsb-url…>`, both LSB's own real identifiers, both gitignored, NEITHER committed; NOT stored in `.env`).

## Technical Approach
CA designs the exact skill prose and carve-out wording. This story's deliverables are all CA-owned (`implement/SKILL.md`, `code-reviewer.md`, `.gitignore`) — the `docs/admin/production-deployment.md` smoke-procedure CONTENT is factored out to story 10 (docs-writer) per Q1 routing; this story only POINTS to it. The two carve-outs are non-optional: authorizing `bb report generate` in the Test-Execution-Constraint but not in Anti-Pattern #5's read-only Bash allowlist would leave CR barred from running the very command the smoke requires (Technical Notes §3). Ensure the `.smoke-fixture` name does not collide with the secret-read-guard's `.env*`/`secrets/**` deny patterns.

## Dependencies
- **Blocked by**: E-256-05 (Step 1d's headline invariant asserts on the reference date `bb report generate` prints); **E-256-06** (same-file collision on `.gitignore` — story 06 does the `data/seeds/` negation cleanup, then this story adds the `.smoke-fixture` entry; ordering prevents a merge conflict on that file).
- **Blocks**: E-256-10 (story 10 documents the Step 1d smoke procedure + two-field `.smoke-fixture` convention this story designs — story 10 consumes this story's design output, so it must follow; the round-1 note "coordination, not a blocking edge" is superseded by the Codex round-2 P1 finding that 10 genuinely depends on 11's design)

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (Phase 5 Step 1d + Step 8 sub-step 5b)
- `.claude/agents/code-reviewer.md` (two carve-outs)
- `.gitignore` (add `.smoke-fixture`)
- (NOT `docs/admin/production-deployment.md` — the smoke-procedure doc content is story 10's, per Q1 routing; this story only references it.)

## Agent Hint
claude-architect

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Context-layer edits are internally consistent (Step 1c vs 1d numbering correct throughout)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
E-259 will later strike the `verify-aggregates` HARD sub-check (AC-3) when it retires that command — that is E-259's deletion-side eviction, explicitly NOT a substitution (there is no left-hand side to check post-cutover). Do not pre-empt it here.
