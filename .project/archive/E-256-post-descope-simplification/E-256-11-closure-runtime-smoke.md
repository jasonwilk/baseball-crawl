# E-256-11: Closure runtime smoke (Step 1d)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

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
- [ ] **AC-4b** (PM-routed during dispatch, from story 07's AC verification): Given that a closure patch may change the app's **dependencies or build inputs**, when Step 1d is defined, then BOTH of the following hold, because otherwise the smoke silently certifies a stale image:
  - **The preflight's "stack up" is a REBUILD, not a start.** Step 1d must bring the stack up with a rebuild (per `.claude/rules/app-troubleshooting.md`'s standing "after changing `src/`, `migrations/`, `Dockerfile`, `docker-compose.yml`, or `requirements.txt`, rebuild and verify the health check" rule) whenever the staged diff touches a build input. Starting a stale image and passing `curl /health` proves the OLD image is healthy and asserts nothing about the change under closure. E-256 is the live example: story 07 crosses a starlette **major** version (0.41.3 → 1.3.1), and `pytest` never exercises uvicorn/FastAPI app **startup**.
  - **The §3 trigger-path list gains the build inputs**: `requirements.txt`, `requirements.in`, `requirements-dev.txt`, `requirements-dev.in`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.python-version`. As §3 stands, a **pure dependency-refresh epic would not trigger Step 1d at all** — precisely the epic class whose runtime risk `pytest` cannot see, since the suite exercises the app in-process via TestClient and never boots the image. That is an inverted gate.
- [ ] **AC-4c** (PM-routed during dispatch, from CR's story-07 finding): Given a closure patch that changes `requirements.txt` / `requirements-dev.txt`, when the closure gates run in the **main checkout**, then `implement/SKILL.md` requires the main-checkout Python environment to be **reinstalled from the patched lockfile** (`pip install -r requirements-dev.txt`, plus the editable install per the devcontainer's `--no-deps -e .` convention) **before** the Step 1b full-suite gate and before Step 1d. Rationale: the epic worktree cannot install into the main checkout, so **nothing currently forces the reinstall** — Step 1b would run the epic's code against the *pre-epic* dependency set and pass green, certifying a stack the epic does not ship. This is the same vacuous-gate class as Technical Notes §3's fresh-fixture-DB warning.

  **This clause is NOT redundant with AC-4b.** AC-4b rebuilds the **Docker image**, which fixes the app the `curl /health` check hits. But `bb report generate` / `morning-run` / `verify-aggregates` / `reconcile-scoreboard` all run on the **local interpreter**, not inside the image — so a stale local env means Step 1d exercises the CLI against the old dependency set (e.g. the old jinja2 that renders the report) even after a correct image rebuild. Both clauses are required, and neither implies the other. State the distinction in the skill text, or a future reader will delete one as duplicative.
- [ ] **AC-5**: Given `.claude/agents/code-reviewer.md`, when this story is complete, then it carries BOTH required carve-outs (Technical Notes §3): a named second exception in the **Test-Execution-Constraint** (beside the closure-pytest carve-out), AND an exception to **Anti-Pattern #5's read-only Bash allowlist** authorizing the DB-mutating `bb report generate`.
- [ ] **AC-6**: Given the trigger evaluation, when Step 1d runs, then the **code-reviewer** performs the `git diff --cached --stat main` read itself and reports "not triggered" when no trigger path matches — the main session does not perform that read (a `dispatch-pattern.md` domain-work boundary).
- [ ] **AC-7**: Given the Step 1d skill text, when this story is complete, then it **references** `docs/admin/production-deployment.md` as the smoke-procedure doc (the doc CONTENT is written by story 10, docs-writer — this story does NOT edit `docs/admin/`, per CA's Q1 routing rule), and this story adds `.smoke-fixture` to `.gitignore` and documents the **two-field** `.smoke-fixture` convention in the skill text (`generate=<public_id>` + `morning-run=<lsb-url…>`, both LSB's own real identifiers, both gitignored, NEITHER committed; NOT stored in `.env`).

## PM AC-Verification (dispatch, 2026-07-09)
**AC-1..AC-7 all PASS** (verified against `implement/SKILL.md` Step 1d + Step 8 sub-steps 4b/5b, `code-reviewer.md` carve-outs, and `.gitignore`). CR reviewing in parallel.

**AC-6 RULING — CA's merge-base adaptation ACCEPTED (PASS).** AC-6's literal text named `git diff --cached --stat main`; CA implemented `git diff --cached --stat $(git merge-base epic/E-NNN main)`. This is accepted as satisfying AC-6, for the same spec-authoring reason story 07 established: **when an AC names a specific mechanism in its rationale, the AC must remain satisfiable by an OUTCOME check — the named mechanism is the part most likely to be wrong.** AC-6's OUTCOME is "the trigger reflects the epic's own changes so Step 1d fires iff the epic touched a runtime surface." The merge-base base serves that outcome; the literal `main` would **false-fire** on main's post-branch divergence (post-E-260, main carries work the epic branch never touched — those files show as spurious deletions under a `main` base and could trip a trigger path the epic never touched). AC-6's two actual requirements — (1) CR performs the read itself, not the main session; (2) reports "not triggered" on no match — are both met (`code-reviewer.md:312`, `SKILL.md:474,636`). **Not a miss.**

**Two review findings, BOTH DISMISSED (disagreement resolution recorded):**

1. **`SKILL.md:480` "same base the closure patch uses at sub-step 3" — DISMISSED as a FALSE POSITIVE.** PM initially flagged this as the epic's false-why defect class: the parenthetical claims the trigger reads against sub-step 3's base, but the worktree copy's sub-step 3 (`:624`) reads `git diff ... main`, not merge-base. **The flag was against the STALE pre-E-260 worktree copy, not the shipped artifact.** CR ran `git show main:.claude/skills/implement/SKILL.md` (the check PM could not run from the worktree) and confirmed main's POST-E-260 sub-step 3 ALREADY reads `git diff --binary --cached $(git merge-base epic/E-NNN main)` — merge-base. Story 11 does NOT modify sub-step 3, so the closure 3-way apply keeps main's merge-base version; in the MERGED/SHIPPED tree both sub-step 3 and the Step 1d trigger use merge-base, making CA's `:480` claim **TRUE post-merge**. The E-260 landmine (worktree branched pre-E-260, so its sub-step 3 still says `main`) fooled the read. Not the false-why class — the claim is true in the file that ships. No CA round; no fix.
2. **CR's own SHOULD — `SKILL.md:650` "User rejects" enumeration does not list sub-step 5b — DISMISSED per CR's own recommendation.** That list enumerates the git-REVERTIBLE closure actions; sub-step 5b (Step 1d smoke) produces only a dev-DB mutation with **no git footprint to reverse**, so adding it to the revert enumeration would mislead.

**The GENUINE inconsistency survives as a captured idea, NOT a story-11 finding:** sub-step 9's present-diff still reads `--stat main` while sub-step 3 reads merge-base — **both in E-260's shipped skill**, so it is a post-E-260 closure-mechanics residual, out of scope for story 11's Step-1d work. Captured as **IDEA-119** (`reconcile-closure-sequence-diff-base-to-merge-base`, CA-owned).

**Net: both gates approve story 11, zero valid findings.**

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
