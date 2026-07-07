# E-258: Review-System Hardening — DRAFT STUB

## Status
`DRAFT`
<!-- Capture stub for the last AGENTIC-FLOW-REVIEW.md §6 package without a home: items 4-7 + 25,
     the review-system hardening cluster. Registration-level scope with absorbed items copied in;
     full spec (stories/ACs) left for the planning session. Refine to READY before dispatch.
     Do NOT dispatch a DRAFT. -->

## Overview
The 2026-07-07 agentic-flow review found that the reviewer stack catches reviewer-quality defects well but leaks whole classes of *structural* defects — integration drift (review scope), test-integrity (no execution authority), doc drift (CR skipped on context-layer epics), concurrency, and security (no rubric). This epic hardens the review system against those classes: it adds the missing rubric edits to the code-reviewer, restructures the implement skill so a combined-diff review actually runs on the default "implement E-NNN" path, gates context-layer epics behind a real review pass, single-sources the Codex rubric off the CR checklist so the two reviewers stop drifting, and installs a process check to re-measure whether the remaining rubric spend is earning its keep. Everything here is context-layer work.

## Provenance
- **Not a CE-numbered audit epic.** The platform-audit CE program (CE-1..CE-6) maps to E-251..E-256; this cluster is sourced from the separate 2026-07-07 **AGENTIC-FLOW-REVIEW.md** (repo root, uncommitted reference), §6 Proposed Change List rows 4, 5, 6, 7, and 25 — plus row 2 (codex-review tooling, an "immediate"-tier item routed here 2026-07-07 because it shares the codex-review neighborhood with item 7) — with detail in §3.4 (rubric edits), §3.5 (structural/process edits), §3.6 (tooling), and §3.3 (the routing-era test that motivates item 25).
- **Owner**: claude-architect (all files are context-layer — `code-reviewer.md`, `implement/SKILL.md`, `codex-review/SKILL.md`, `.project/codex-review.md`, plan/context-layer rules) + product-manager (the item-25 process AC).
- **Size**: M (estimate — refine).
- **Sequence**: see "Sequencing + collision constraints" below.

## Scope (absorbed items copied in, source AGENTIC-FLOW-REVIEW.md §3.3/§3.4/§3.5 + §6 rows 4-7+25)

### Item 4 — CR rubric additions (`.claude/agents/code-reviewer.md`; §3.4)
The nine rubric edits, targeting gap classes 1/3/4/7/8/9 (~114 verified findings):
1. **Consumer-audit step** (class 1): for any signature/dimension/invariant change, grep-enumerate all call sites, mirror paths, and duplicate constant lists and check each explicitly. Codify the project **twin-path checklist**: `game_loader ↔ scouting_loader`, `detect ↔ cleanup` mirrors, `recompute ↔ parity` column sets — the same pairs recur.
2. **Adversarial assertion rubric** (class 3): for each new/changed test, ask "what wrong implementation would still pass this?"; require element-pinned/scoped assertions and a demonstrated fail-then-pass for bug-regression tests.
3. **Edge-case enumeration per changed function** (class 4): null/empty/malformed, error propagation, and for refactors diff the OLD function's branches against the new (the E-247 lesson). Behavior-preserving epics require populated-DB characterization tests, not fresh-DB goldens.
4. **Standing concurrency question** (class 8): "who else can write this row between my read and my write?" — admin UI + CLI + cron is now three SQLite writers. Every read-check-write must be atomic and rowcount-gated; every shared-connection error path must rollback.
5. **Security trigger** (class 9): any story touching auth, credentials, or PII paths gets an explicit security rubric pass (replay, TOCTOU, fail-open vs fail-closed, PII in ALL artifact types).
6. **Self-load fallback for API/migration context**: replace "Do not load endpoint docs/migration files independently" with — if the assignment omits the section but the diff shows GC field access or new column references, self-load the docs rather than silently no-op'ing both E-147 checklist items.
7. **Cumulative migration baseline**: build the schema baseline from all `migrations/*.sql` in the tree plus `git diff --cached main`, never the current-story unstaged diff alone.
8. **No truncated reads in integration review**: prohibit `| head` / `| tail` pipes on diff/grep reads (E-239's self-admitted miss cause), and require an actual pytest run for any epic whose diff touches `tests/` at the closure integration pass.
9. **Verbatim test evidence**: the implementer's `## Test Results` must include the exact pytest summary line and command; CR cross-checks claimed test files against its grep-discovered import set.

### Item 5 — implement-skill structural edits (`.claude/skills/implement/SKILL.md`; §3.5)
- **Unconditional CR integration review at closure** (Phase 4a → Phase 5, between the invariant audit and the full-suite gate): today a plain "implement E-NNN" — the user's documented default — gets NO combined-diff review; only Codex (4b) stays gated on "and review." Make the combined-diff CR pass unconditional.
- **Fix the CR→Codex→CR ordering**: CR approves, Codex finds, CR reverses itself (E-239, E-251, E-253). Either run Codex before the CR integration pass so CR adjudicates a real finding list, or drop the separate 4a pass on Codex-bound epics and use CR purely as finding-validator/remediation reviewer.
- **Mechanical Invariant-Audit triggers** (Step 1a): the only mode that sweeps untouched files is currently triggered by the one actor barred from reading code. Add a checklist evaluable from permitted artifacts — NOT NULL/FK migration in diff, canonical-helper signature change in Technical Notes, new required field on a core INSERT → audit fires.
- **AC×surface matrix** (class 6): joint PM+CR checklist item — for each conditional AC ("only when X", vocabulary mappings), enumerate every render/call/error path and verify the condition at each.
- **Migration rubric** (class 7, dormant): enumerate live-DB data states and dry-run migrations against a production DB copy with before/after scope assertions — keep as a standing item so dormancy doesn't become recurrence when migrations return.

### Item 6 — context-layer review gate (§3.5)
Context-layer epics get a mandatory Codex-or-CR pass instead of PM-AC-verification-only; doc sweeps pair token-grep with a semantic read of the touched sections plus synonym expansion. Closes the 16-finding class that reached Codex with zero prior review.

### Item 7 — single-source the Codex rubric (§3.5)
`.project/codex-review.md` is a manually-synced abbreviation of CR's checklist and already lags it (SQL-scope and multi-scope-aggregate items have no Codex counterpart). Have `codex-review/SKILL.md` embed the CR Bug Pattern Checklist from `code-reviewer.md` at prompt-assembly time; reduce `.project/codex-review.md` to Codex-specific priorities.

### Item 2 — codex-review tooling hardening (`scripts/codex-review.sh`, `.claude/skills/codex-review/SKILL.md`; §3.6; routed here 2026-07-07)
An "immediate"-tier §6 row (row 2) folded into this epic because it lives in the same codex-review neighborhood as item 7. Tee the Codex output to a deterministic file and print `RESULT_FILE=` + `wc -l` + `tail -n1`; update the codex-review skill's read-receipt to consume that file rather than relying on a manual redirect (44/48 invocations skipped the manual redirect; 2 fabrication incidents resulted). Default the WORKDIR diff to `--diff-filter=ACMR` so pure deletions don't burn Codex's 20-minute budget (on the largest epics — E-239's 2.57M-char diff — Codex silently degrades to static-only, losing its test sweep exactly where integration risk peaks); note in the skill that Codex's pytest sweep is best-effort and Phase 5 Step 1b is the authoritative test gate.

### Item 25 — post-E-251 gap re-measurement (§3.3; PM-owned process AC)
After ~5 post-E-251 epics close under the now-mandatory canonical scorecard schema, PM re-tallies the CR-vs-Codex gap and reports whether the routing-era hypothesis held — reviewer-quality classes narrow (bare `general-purpose` spawns were replaced by defined agents at E-251), structural classes do not. This is the empirical check on whether the item-4/5/6/7 rubric spend is earning its keep; it calibrates further rubric investment.

## Sequencing + collision constraints
- **STRICTLY AFTER E-255.** E-255's stale-READY AC (E-255-06 AC-6) wires into `implement/SKILL.md` Prerequisites, and E-255-03 AC-5b edits `.claude/rules/tool-output-integrity.md` — E-258 touches `implement/SKILL.md` too. Two epics must never edit one file concurrently, so E-258 waits for E-255 to land.
- **RECOMMENDED before E-257 and E-256**, so their dispatches run under the hardened review system.
- **REQUIRED before E-256 specifically**: E-256's closure-runtime-smoke carve-out edits `.claude/agents/code-reviewer.md` (a named second Test-Execution-Constraint exception), the same file E-258's item-4 rubric edits touch — they must not run concurrently, and E-258 should land first so the carve-out is added onto the hardened rubric.
- **Net sequence: E-255 → E-258 → E-257 → E-256.**

## Dispatch Team
- **claude-architect** — all context-layer files (rubric, implement skill, codex-review skill, `.project/codex-review.md`, context-layer review-gate rule).
- **product-manager** — the item-25 process AC (gap re-measurement).
- **code-reviewer (consulted at planning, via main-session relay)** — the rubric describes the code-reviewer's own job, so it should get a voice in shaping items 4/5. Consultation only; CR does not own stories here.

## Refinement Notes (for the future planning session)
- Decide story boundaries: item 4 (rubric) and item 5 (implement-skill) both touch high-traffic context-layer files — sequence them so no two stories edit `code-reviewer.md` or `implement/SKILL.md` concurrently.
- Item 25 is a process/measurement AC, not a file edit — decide whether it lands as a recorded-verdict checklist item (like the doc/context-layer gates) or a scheduled PM sweep, and confirm the "~5 post-E-251 epics with canonical scorecard schema" precondition is met before it can execute (it may need to defer past this epic's own closure).
- Confirm the CR→Codex→CR ordering fix (item 5) does not conflict with any ordering assumption E-255's or E-256's SKILL.md edits introduce — re-check after E-255 lands.
- Coordinate with E-256: its smoke carve-out and this epic's item-4 rubric both edit `code-reviewer.md`; the strict E-258-before-E-256 order above exists to keep those edits serial.

## History
- 2026-07-07: Created as a DRAFT capture stub to home the AGENTIC-FLOW-REVIEW.md §6 review-system hardening package (rows 4-7 + 25) — the last §6 cluster without an epic. Not refined; not dispatchable until taken to READY. Sequence recorded: E-255 → E-258 → E-257 → E-256.
- 2026-07-07: Item 2 (codex-review tooling hardening, §3.6 — deterministic-file tee + read-receipt + `--diff-filter=ACMR` default) routed in as an added absorbed item; it was an "immediate"-tier §6 row homed here for codex-review-neighborhood cohesion with item 7.
