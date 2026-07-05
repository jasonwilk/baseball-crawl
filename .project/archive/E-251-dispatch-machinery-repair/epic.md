# E-251: Dispatch-Machinery Repair

## Status
`COMPLETED`

## Overview
Repair the dispatch/context-layer machinery that governs how every future epic executes, before any epic (including E-250) is dispatched. Two of these defects are load-bearing: the implement skill's closure failure paths are broken as written (the red-suite recovery loop deadlocks for any epic that adds a file, and the abort path silently destroys ancillary edits), and the routing table sends the three highest-volume story domains to bare `general-purpose` spawns that never load the specialist agent definitions, checklists, model/effort specs, or memory. The remaining items are smaller correctness fixes in the hooks and skill/context prose. This epic makes the dispatch machinery trustworthy so it does not degrade or break the epics sequenced behind it.

## Background & Context
Source: the 2026-07-03 adversarial full-platform audit (`PLATFORM-AUDIT.md`, repo root, deliberately **UNCOMMITTED** — do not commit or modify it). The audit's §1 Executive Summary item 3 states these defects "touch every future epic" and "should be fixed *before* E-250 is dispatched." The recommended sequence (§4) puts this epic FIRST, before anything is dispatched, because F-H4/F-H5 "degrade or break every subsequent epic's execution, including E-250's own closure."

Every fix below was pre-specified and adversarially verified in the audit. This epic does NOT re-derive the findings; it structures the vetted inventory into well-formed context-layer stories. Because the audit file is uncommitted and could disappear, each story quotes the specific defect and fix into its own AC/spec text so the epic is self-contained.

**Bootstrapping note**: E-251-01 modifies `.claude/skills/implement/SKILL.md` — the very skill that governs dispatch closure. The broken paths only fire on a red closure suite or an operator abort; a context-layer epic with a green suite exercises neither, so dispatching E-251 through the current (pre-fix) skill is low-risk. The fixes land for every subsequent epic.

**No expert consultation required** — this is context-layer repair work owned entirely by claude-architect, working from an adversarially-verified inventory. Per the domain-expert-designs convention (`.claude/agent-memory/product-manager/feedback_domain_expert_designs.md`), claude-architect owns the exact edits within `.claude/**`; the stories frame grep-verifiable / behavior-verifiable outcomes and name the files. Line numbers cited below are from the audit's verification pass and may have drifted — CA locates the current occurrences (the same convention E-250 TN-7 used).

## Goals
- Make the implement skill's closure failure paths executable: the red-suite recovery loop must work for epics that add files, and the abort path must not destroy staged ancillary edits.
- Route SE/DE/api-scout dispatch stories to their named agents so specialist definitions, checklists, model/effort frontmatter, and memory load during dispatch.
- Remove the software-engineer.md self-contradiction on story-status ownership.
- Harden the hooks: worktree-guard path normalization, commit-interception `git -C` coverage, and honest pii-check failure labeling.
- Correct stale skill/context prose: codex-review closure step routing to Phase 5 (currently misdirected at a Phase 4a/4b re-entry), plan-skill artifact-staging glob, filesystem-context dispatch model, context-fundamentals phantom citation.

## Non-Goals
- Any change to `src/`, `tests/`, `migrations/`, `scripts/`, or `docs/` — all fixes live under `.claude/**`.
- The broader context-layer / API-doc / runbook truth sweep (audit CE-5) — out of scope here; this epic is only the dispatch-machinery slice.
- Any behavioral change to what the hooks/skills are supposed to enforce — these are correctness fixes to make each control do what it already claims to do, not policy changes.
- Committing or altering `PLATFORM-AUDIT.md`.

## Success Criteria
- The implement skill's red-suite reset and abort-path reset both use an undo mechanism that correctly reverses a patch containing newly-added files, and the abort path no longer destroys staged ancillary (vision-signals/ideas) edits; the prose describing each reset is accurate.
- `.claude/rules/agent-routing.md`'s Agent Selection table routes the Python-implementation, DB-schema, and API-exploration rows to `software-engineer`, `data-engineer`, and `api-scout` respectively (not bare `general-purpose`).
- `.claude/agents/software-engineer.md` contains no instruction to update story statuses; it is internally consistent with the never-own-statuses rule stated elsewhere in the same file and in the agent ecosystem.
- `worktree-guard.sh` normalizes paths so a double-slash form cannot bypass the guard in either mode; the commit-interception logic covers `git -C` invocation forms; `pii-check.sh` distinguishes a scanner infrastructure failure from an actual PII detection in its reporting.
- The codex-review skill's closure step routes control to Phase 5 (closure) after the Codex pass — not a re-entry into or reordering of Phase 4a/4b; the plan skill's artifact-staging step stages file-form research artifacts; filesystem-context no longer teaches the obsolete PM-dispatches-implementers model; context-fundamentals no longer cites a nonexistent CLAUDE.md "Workflow" section.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-251-01 | Implement-skill closure-path repair (F-H5 + abort-path ancillary destruction) | DONE | None | claude-architect |
| E-251-02 | Route SE/DE/api-scout dispatch stories by name (F-H4) | DONE | None | claude-architect |
| E-251-03 | Remove software-engineer.md status-ownership contradiction | DONE | None | claude-architect |
| E-251-04 | Hook hardening: worktree-guard normalization, commit-regex gaps, pii-check labeling | DONE | None | claude-architect |
| E-251-05 | Skill/context prose corrections (codex-review closure→Phase 5, plan glob, filesystem-context, context-fundamentals) | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

<!-- Every story is context-layer work (.claude/**) and routes to claude-architect per
     the Routing Precedence rule in .claude/rules/agent-routing.md. code-reviewer and
     product-manager are spawned as dispatch infrastructure, not listed here. -->

## Technical Notes

### TN-1: Every story is context-layer; claude-architect owns the exact edits
All five stories touch only `.claude/**` files, so per the Routing Precedence rule (`.claude/rules/agent-routing.md`) they route to claude-architect regardless of any other signal. Per the domain-expert-designs convention, the stories frame grep-verifiable / behavior-verifiable OUTCOMES (what must be true after) and name the files; CA determines the precise wording and locates the current occurrences. The line numbers in the ACs are from the audit's verification pass against the working tree on 2026-07-03 and may have drifted.

### TN-2: The two implement-skill closure defects (E-251-01), verbatim from the audit
`.claude/skills/implement/SKILL.md` has two closure-sequence resets that are broken for any epic that ADDS a file:

- **F-H5 (red-suite reset, ~sub-step 5)**: On a red full-suite gate the documented reset is `git reset HEAD && git checkout -- .`. `git checkout -- .` only restores tracked files to HEAD; files the applied patch CREATED are untracked, so they survive the reset. The subsequent re-apply (`git apply --check --3way`) then errors ("does not exist in index" / already-present), and the remediation loop deadlocks — inviting ad-hoc git surgery on main. The audit verified the fix: use `git apply -R --3way /tmp/E-NNN-epic.patch` as the symmetric undo (it reverses the patch including created files). The same defect dirties the abort path.
- **Abort-path ancillary destruction (~sub-step 9 reject path (c), "abort")**: the reset does `git reset HEAD` then `git checkout -- .`, described as restoring "the main checkout to its pre-Step 8 state." That claim is false in two ways: (i) `git checkout -- .` reverts ALL tracked modifications to HEAD, so the staged-but-uncommitted Step 7a vision-signals/ideas edits (which legitimately predate Step 8) are irreversibly destroyed rather than preserved; (ii) patch-created untracked files are left behind. The fix: the abort must REVERSE the three Step-8 closure actions individually — the applied patch (symmetric `git apply -R --3way` of the epic patch, handling created files), the archive rename (`git mv` back), and the sub-step-7 PM-memory Active→Archived flip — while LEAVING ALL Step 7a ancillary edits (vision-signals, ideas, AND `.claude/agent-memory/` PM-memory edits) in place, then correct the "pre-Step 8 state" prose to describe exactly that. **The sub-step-7 flip must be reversed, NOT preserved** (CA design-review correction 2026-07-04): it is a Step-8 closure artifact, so leaving it while `git apply -R` flips `epic.md` back to ACTIVE would leave PM memory saying "Archived" against an ACTIVE epic — an inconsistent state. **The reversal is a SURGICAL PM-driven section-move** (Phase 4b Codex remediation, finding ②, 2026-07-05): PM moves the epic from Archived back to Active in its own MEMORY.md, editing only the sub-step-7 lines — NOT a whole-file `git checkout -- MEMORY.md`, which would destroy any Step 7a PM-memory edit made to the same file. All Step 7a edits survive; only the flip is undone.

Both fixes land in the same story because they are the same file and the same class of defect; CA determines the exact command sequence and the accompanying prose. The correctness gate is that a red-suite closure on an add-a-file epic could recover, and an abort reverses all three Step-8 actions (the sub-step-7 flip via a surgical PM-driven section-move, not a whole-file checkout) while preserving ALL Step 7a ancillary edits (vision-signals, ideas, and PM memory) — the code-reviewer verifies the reset logic and prose are self-consistent.

### TN-3: F-H4 routing fix (E-251-02), verbatim from the audit
`.claude/rules/agent-routing.md`'s "Agent Selection for Dispatch" table currently maps three rows to `general-purpose`:
- `Python implementation, crawlers, parsers, tests` → `` `general-purpose` (software-engineer role in prompt) ``
- `Database schema, SQL migrations, ETL` → `` `general-purpose` (data-engineer role in prompt) ``
- `API exploration, endpoint docs` → `` `general-purpose` (api-scout role in prompt) ``
A `general-purpose` spawn never loads the named agent's definition, Pre-Submission Checklist (written to catch recurring bug classes), model/effort frontmatter, or agent memory — so the highest-volume implementation stories run un-instrumented at default model/effort. The fix is to route these rows to the named agents (`software-engineer`, `data-engineer`, `api-scout`), consistent with the rest of the table (which already routes context-layer→claude-architect, docs→docs-writer, UI→ux-designer by name). CA reconciles any surrounding prose (e.g., the "role in prompt" phrasing and any dispatch-pattern references) so the table and its explanation agree.

### TN-4: SE status-ownership contradiction (E-251-03), verbatim from the audit
`.claude/agents/software-engineer.md` contradicts itself: an early section (audit cites ~L80-81) instructs the SE to update story statuses (e.g., steps 5-6 of a work procedure), while a later section (~L157) and the project's agent-ecosystem rule both state that implementers NEVER own status transitions (PM owns statuses during dispatch — see `.claude/agent-memory/product-manager/feedback_pm_owns_statuses.md`). The fix is to delete the status-update steps so the file is internally consistent with the never-own-statuses rule. CA locates the exact steps and removes them, adjusting any step numbering left dangling.

### TN-5: Hook hardening (E-251-04), verbatim from the audit
Three independent hook correctness defects, all in `.claude/hooks/`:
- **worktree-guard path normalization**: `worktree-guard.sh` does no path normalization, so a double-slash path form (e.g. `src//foo.py`) bypasses the guard in BOTH modes (dispatch-active and no-dispatch). Fix: normalize paths before the guard comparison so equivalent path forms cannot slip past.
- **commit-interception `git -C` gap**: the commit-interception regex(es) miss `git -C <dir> commit` invocation forms, and the epic-archive gate (`epic-archive-check.sh`) has no second layer to catch what the regex misses. Fix: broaden the interception to cover `git -C` forms.
- **pii-check failure labeling**: `pii-check.sh` reports every scanner infrastructure failure (scanner crash, missing interpreter, etc.) as "PII detected," conflating "the scanner broke" with "the scanner found a credential." Fix: distinguish an infrastructure/scanner failure from an actual detection in the reported message and (as CA judges appropriate) the exit semantics.
CA determines the exact normalization approach, regex form, and failure-labeling wording. The correctness gate: a double-slash path is blocked where its single-slash form would be; a `git -C` commit form is intercepted where the plain form would be; and a scanner infra failure is not mislabeled as a PII hit.

### TN-6: Skill/context prose corrections (E-251-05), verbatim from the audit
Four stale-prose/citation defects across skill and context-fundamentals files:
- **codex-review closure destination**: the codex-review skill's closure step (audit cites Step 7 / ~line 151) points at the wrong phase. A literal 4a/4b swap is WRONG (CA design-review correction 2026-07-04): Phase 4a = CR, Phase 4b = Codex, and the codex-review skill IS the Codex (4b) pass — after it, control proceeds to **Phase 5 (closure)**, never back to a CR phase. Fix: rewrite the step so its destination is Phase 5.
- **plan-skill artifact-staging glob**: the plan skill's Step 2a staging glob uses a trailing-slash directory form that never stages FILE-form research artifacts (a research artifact saved as a single `.md` file, not a directory, is silently not staged with the READY commit). Fix: make the staging cover file-form artifacts.
- **filesystem-context dispatch model**: `.claude/skills/filesystem-context/SKILL.md` teaches the obsolete "PM dispatches implementers" model; the current model is that the main session spawns/routes during dispatch (PM owns statuses + AC verification). Fix: update the prose to the current dispatch model.
- **context-fundamentals phantom citation**: `.claude/skills/context-fundamentals/SKILL.md` cites a nonexistent CLAUDE.md "Workflow" section. Fix: correct or remove the dangling citation to point at content that exists.
CA locates the current occurrences and determines the precise wording.

## Open Questions
- None blocking. The inventory is adversarially verified; per-fix correctness gates are baked into the ACs and verified by code-reviewer against the current file state.

## History
- 2026-07-05: **COMPLETED** (closure bookkeeping; COMPLETED status flip authored at the closure-merge staging step). All 5 context-layer stories DONE, repairing the dispatch machinery ahead of every subsequent epic (CE-1, dispatched FIRST per the platform audit §4 sequence). Delivered: (01) implement-skill closure-path repair — F-H5 red-suite reset now uses `git apply -R --3way` (reverses patch-created files, no deadlock) + abort-path ancillary-destruction fix, incl. the Phase-4b surgical-reversal refinement (sub-step-7 PM-memory flip reversed by a PM-driven section-move, ALL Step 7a edits preserved); (02) F-H4 — routing table sends Python/DB/API rows to `software-engineer`/`data-engineer`/`api-scout` by name (specialist defs, checklists, model/effort, memory now load); (03) software-engineer.md status-ownership contradiction removed (work procedure clean 1-4 + affirmative never-own line, consistent with L157); (04) hook hardening — worktree-guard double-slash normalization (both modes), `git -C` commit-interception in BOTH pii-check.sh and epic-archive-check.sh, pii-check output-pattern-based infra-vs-detection labeling (fail-closed preserved); (05) skill/context prose — codex-review closure→Phase 5, plan Step 2a file-form artifact staging glob, filesystem-context current dispatch model (full span), context-fundamentals phantom CLAUDE.md "Workflow" citation removed. No `src/`/`tests/`/`migrations/`/`scripts/`/`docs/` changes.

  **Review Scorecard:**
  | Gate | Rounds | Findings | Resolution |
  |------|--------|----------|------------|
  | Per-story code review | — | — | Skipped (all 5 stories context-layer-only → PM AC-verification alone, per the implement skill) |
  | CR integration review (Phase 4a) | 1 | 0 | APPROVED round 1 |
  | Codex code review (Phase 4b) | 1 | 3 | 1 accepted+fixed (②), 1 dismissed-invalid (①), 1 deferred→CE-5 (③) [*] |
  | CR remediation re-review | 1 | 0 | APPROVED, 0 new findings |
  | External post-staging review — E-251-04 hardening | 1 | 2 | 2 accepted+fixed, 0 deferred [**] |
  | CR re-verify (hardening) | 1 | 0 | APPROVED, 0 MUST FIX |
  | **Total** | — | **5** | 3 fixed, 1 dismissed-invalid, 1 deferred→CE-5 |

  [*] Codex Phase 4b split: ② (VALID) abort-path survivor-set refinement — fixed in skill prose + reconciled across E-251-01 ACs and epic TN-2; ① (INVALID/dismissed) worktree-guard relative-path — guard only acts on absolute main-prefix paths, AC-1 met; ③ (DEFERRED→CE-5) hooks/README.md stale "fail open" prose — pre-existing/out-of-scope for this epic, absorbed by the CE-5 truth sweep.

  [**] Both external post-staging findings were in E-251-04's OWN scope (commit-interception coverage + worktree-guard normalization) and were FOLDED IN before closure rather than deferred — see the 2026-07-05 external-review-fold History entry. Two non-blocking residuals both reviewers accepted as reasonable scope boundaries are captured in the Deferred Work note below.

  **Documentation assessment** (per `.claude/rules/documentation.md`): **No documentation impact.** E-251 modifies only `.claude/**` (context layer) — no operator-facing command, coaching surface, API behavior, or schema changed; nothing in `docs/admin/` or `docs/coaching/` is affected. The hooks/README.md staleness Codex flagged is context-layer (deferred to CE-5), not a docs/admin|coaching item.

  **Context-layer assessment** (per `.claude/rules/context-layer-assessment.md`, six triggers, verdicts from the main session): (1) New convention — NO; (2) Architectural decision — NO; (3) Footgun/boundary — YES (abort-path agent-memory ancillary destruction; worktree-guard guards only absolute main-prefix paths) but codified in-place (fixed skill prose + corrected worktree-guard comment), no additional codification; (4) Agent behavior/routing/coordination — YES (routing by name, closure abort mechanism, SE status ownership) but these ARE the epic's deliverables, all authored by claude-architect in `.claude/**`, codification complete in-place; (5) Domain knowledge — NO; (6) New CLI/workflow/skill — NO. **Net: no separate claude-architect codification pass required — the epic IS the codification.**
- 2026-07-05: External post-staging review fold (E-251-04 hardening). Two findings, both in E-251-04's OWN scope, accepted and folded in before closure (ARCH applied; CR adversarially re-verified → APPROVED, 0 MUST FIX): **FIX 1 (commit-interception coverage)** — the interception regex in BOTH `pii-check.sh` and `epic-archive-check.sh` was broadened to catch space-separated / quoted global-option forms (`--git-dir /x`, `--work-tree /x`, `-C "a b"`, `--namespace ns`) via an explicit flag-list, deliberately shaped to avoid a `git --no-pager commit` false-negative. **FIX 2 (worktree-guard `..` traversal)** — the guard now denies any main-checkout path containing a `..` segment in both modes (fail-closed), also closing an agent-memory allowlist escape (`.claude/agent-memory/../src/...`).

  **Deferred Work (hook-hardening follow-ups — NOT E-255 truth-sweep class):** two non-blocking residuals both reviewers accepted as reasonable scope boundaries — (a) a raw worktree path that climbs OUT via `..` into the main checkout (`/tmp/.worktrees/…/../…`) still passes worktree-guard's early worktree pass-through; a zero-dependency close exists: apply the same `*/../*` reject to raw `/tmp/.worktrees/...` FILE_PATHs before the pass-through. (b) the pre-existing over-intercept where a trailing `\s+commit` with no right boundary matches non-commit commands (`git committed-file.txt`) — fail-safe/harmless (over-blocks, never under-blocks). Captured here durably as an epic-scoped follow-up. IDEA-093 is the verified-next idea number (globbed the live ideas dir; highest is IDEA-092) should the operator prefer backlog visibility; PM judgment is that this History deferred-work note suffices for two low-severity, E-251-04-specific residuals and avoids expanding the closure-commit footprint with a new `.project/ideas/` file.
- 2026-07-05: Phase 4b Codex remediation (during dispatch). Three findings triaged: **② VALID/FIXED** (CR-confirmed) — the E-251-01 abort-path survivor set was refined: the sub-step-7 PM-memory Active→Archived flip is reversed by a SURGICAL PM-driven section-move (PM moves the epic Archived→Active in its own MEMORY.md, editing only the sub-step-7 lines), NOT a whole-file `git checkout -- MEMORY.md` (which would destroy a Step 7a PM-memory edit to the same file); the abort now preserves ALL Step 7a ancillary edits (vision-signals, ideas, AND `.claude/agent-memory/` PM-memory), reverting only the flip. Skill prose fixed by CA; E-251-01 story AC-2/AC-3 + Description and epic TN-2 corrected by PM to match (this supersedes the 2026-07-04 "only Step 7a vision-signals/ideas survive" framing below). **③ DEFERRED → CE-5** — hooks/README.md stale "fail open" prose reconciled as pre-existing/out-of-scope for this epic (truth sweep). **① DISMISSED (invalid)** — worktree-guard relative-path concern: the guard only acts on absolute main-prefix paths, so AC-1 remains met.
- 2026-07-04: claude-architect design review — all five findings validated against live files, 3 AGREE, 2 corrected, dispatch-ready. Corrections applied: (1) E-251-01 abort path — the sub-step-7 PM-memory edit must be REVERTED on abort (it is a Step-8 closure artifact; leaving it while `git apply -R` flips epic.md to ACTIVE is an inconsistent state), so only the Step 7a vision-signals/ideas edits survive and the abort reverses all three Step-8 actions (AC-2/AC-3 + TN-2); (2) E-251-05 AC-1 — the codex-review closure step routes to Phase 5, NOT a 4a/4b swap (the codex-review skill IS the Codex 4b pass; control never returns to a CR phase). Folded in as implementation guidance: E-251-04 (commit-interception regex lives in both pii-check.sh and epic-archive-check.sh; PII infra-vs-detection must pattern-match scanner output, not exit codes) and E-251-05 AC-3 (obsolete PM-dispatch model spans filesystem-context lines 42/95/99-112/190 + stale "Task tool" phrasing; multi-agent-patterns echoes it but stays out of scope → CE-5).
- 2026-07-04: Created and set to READY. Scope is the platform audit's (`PLATFORM-AUDIT.md`) §4 CE-1 row — the dispatch-machinery slice — structured into 5 context-layer stories by PM. Every fix is pre-specified and adversarially verified in the audit; stories quote the specific defect/fix so the epic is self-contained if the (uncommitted) audit file disappears. No expert consultation required (context-layer repair, claude-architect-owned). Dispatch NOT yet authorized — READY gate only; per the audit's recommended sequence this epic is dispatched FIRST, before E-250 or any other epic.
