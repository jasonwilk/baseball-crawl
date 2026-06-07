# E-231: Harness Output-Reliability -- Detect, Defend, and Report

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
During multi-agent dispatch, the tool I/O channel intermittently returns empty, truncated, or garbled output and reports Edit/Write "success" on edits that did not fully land. The transport bug itself is Anthropic/Claude-Code-internal and cannot be fixed from this repository. This epic builds a deterministic **detect-and-defend** layer (an always-loaded output-integrity discipline rule, a PostToolUse Edit/Write verification hook, a force-read-before-triage gate, and a relay-integrity rule for the orchestrator-relay surface) plus an honest **upstream bug-report artifact** for the part we cannot fix.

## Background & Context
This epic promotes IDEA-075 (`/.project/ideas/IDEA-075-harness-output-reliability.md`). During the E-230 dispatch (2026-05-31), the tool channel flakiness caused repeated, expensive thrash across every agent (main session, PM, CR, CA, SE): a Codex review was mischaracterized off a 2KB preview of a 373KB persisted result; PM raised then retracted phantom AC defects; CR fabricated a warnings breakdown; SE reported a garbled-output "test-isolation leak"; CA hit silent Edit failures and dark read-backs. The compensating disciplines that worked -- write-to-file-then-read-back, grep-relay, re-read-to-self-consistency, never-report-a-number-not-just-seen -- were all manual workarounds that fail silently when an agent forgets them.

A behavioral memory was captured (the read-findings-before-triage lesson), but a memory is necessary and **insufficient**: under a flaky channel, an agent can read carefully and still act on garbage. This epic is the structural complement -- it makes correctness less dependent on every agent remembering to distrust their own tools.

This very planning session reproduced the bug severely (intermittent empty Reads and a stale-line-number Read on the PM channel, recovering on retry), providing primary evidence for the upstream report in E-231-04.

## Goals
- Establish an always-loaded output-integrity discipline rule that names the failure taxonomy (empty / truncated / garbled) and prescribes independent-channel cross-check, retry, and escalation -- and prohibits asserting unseen content or co-batching a report with the command it reports.
- Ship a PostToolUse Edit/Write verification hook that catches the silent partial-edit-success class -- the one failure mode with no behavioral workaround -- while distinguishing transient flakiness (retry, do not hard-fail legitimate edits) from a genuinely-absent edit (loud/blocking failure).
- Convert the existing read-findings-before-triage memory into a structural pre-triage read-receipt gate in the review skills.
- Produce an honest upstream bug-report artifact capturing the failure taxonomy and this-session reproduction for filing with Anthropic / Claude Code.

## Non-Goals
- **Fixing the transport bug.** The root cause is Anthropic/Claude-Code-internal; we cannot make Read reliable. We detect and defend; we do not repair the channel.
- **Concurrency capping.** No `maxConcurrent` knob is configurable in the harness (CA-verified). Capping concurrent agents/tool-calls during dispatch is out of scope for this epic's deterministic core.
- **Catching garbled-but-nonempty output in a hook.** A hook can detect empty-Read and edit-didn't-land, but cannot reliably detect garbled-but-nonempty output (wrong line numbers on a real file's content). That gap is covered by the discipline rule (E-231-01), not by tooling.
- **Diagnosis spike.** No Story 0 root-cause investigation -- the posture is settled (transport-layer bursty drop/corruption) and the deterministic core is built now.

## Success Criteria
- The output-integrity rule file exists, is loaded on `paths: "**"`, names the three failure modes, prescribes independent-channel cross-check, and prohibits asserting unseen content and co-batching report+command.
- A PostToolUse hook is registered in `.claude/settings.json` with an `Edit|Write` matcher, re-reads the target, and correctly distinguishes transient-empty (retry, no hard-fail) from real-absent (loud/blocking), verified against present / absent / transient-empty cases.
- Both review skills (`codex-review`, `codex-spec-review`) carry a required pre-triage read-receipt gate.
- An upstream bug-report artifact exists documenting the failure taxonomy, repro context, and this-session evidence.
- A no-relay-of-unread-content rule exists in `.claude/rules/dispatch-pattern.md` (peer-checkable, not a deterministic gate), with cross-pointers at the plan/implement finding-relay steps, covering the orchestrator-relay surface that the in-skill triage gate and the always-loaded assert-unseen prohibition do not reach.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-231-01 | Output-integrity discipline rule | TODO | None | - |
| E-231-02 | PostToolUse Edit/Write verification hook (anchor) | TODO | None | - |
| E-231-03 | Force-read-findings-before-triage gate | TODO | None | - |
| E-231-04 | Upstream harness bug-report artifact | TODO | None | - |
| E-231-05 | Relay-integrity rule (no relay of unread content) | TODO | None | - |

## Dispatch Team
- claude-architect (owner -- implements all five stories)
- software-engineer (advisory only -- consulted on the E-231-02 verification predicate; no story routes to SE)

## Technical Notes

### Root-cause posture (settled, not under investigation)
Harness/transport-layer **bursty output drop and corruption**: empty returns AND garbled output (wrong line numbers -- observed Read showing line counts 19→17→18 while `cat -n` showed clean 1-31 on the same file) AND tail truncation, hitting even zero-IO commands like bare `echo`, recovering on retry, under concurrent multi-agent dispatch. We cannot fix transport. We build deterministic detection + discipline + an upstream report.

### Feasibility facts (CA-verified live)
- Existing hooks are ALL PreToolUse, registered in `settings.json`: Bash→[`pii-check.sh`, `epic-archive-check.sh`], Write→`worktree-guard.sh`, Edit→`worktree-guard.sh`. **No PostToolUse hook exists** -- E-231-02 introduces the first one (greenfield).
- PostToolUse hooks CAN read both `tool_input` and `tool_response` on stdin -- Edit-verification is feasible.
- Concurrency cap is NOT configurable (no `maxConcurrent` knob) -- out of scope (see Non-Goals).
- A hook CAN catch empty-Read and edit-didn't-land but CANNOT catch garbled-but-nonempty -- that gap is the discipline rule's job (E-231-01).

### Corrected hook baseline (CA-supplied; main-session-verified against settings.json + worktree-guard.sh)
Existing hooks are ALL PreToolUse, registered in settings.json: Bash→[pii-check.sh, epic-archive-check.sh], Write→worktree-guard.sh, Edit→worktree-guard.sh. The established pattern: read tool JSON from stdin via `INPUT=$(cat)`, extract fields with jq, and communicate a deny decision via JSON on stdout (`hookSpecificOutput.permissionDecision:"deny"`) while ALWAYS exiting 0 -- non-zero exit is NOT the PreToolUse deny mechanism. Hooks fail open (exit 0) if jq is absent. (Note: pii-check.sh shells out to `python3 -m src.safety.pii_scanner`, but that is the downstream scanner, not the hook's stdin parsing -- hook plumbing is jq.) E-231-02 introduces the FIRST PostToolUse hook; its signal field shape differs from PreToolUse -- see the PostToolUse capability Note below and E-231-02 AC-4/AC-7.

### PostToolUse capability (documented; definitive -- not implementer-determined)
PostToolUse fires AFTER the tool succeeds (the write is already on disk). Per documented semantics (docs blocking table: PostToolUse "Can block? NO"): PostToolUse CANNOT block or roll back the write. `exit 2` only shows stderr to Claude (the tool already ran); top-level `decision:"block"`+`reason` surfaces the reason to the model and halts continuation to the next turn but does NOT prevent/undo the write. PostToolUse uses TOP-LEVEL `decision` (NOT the PreToolUse `hookSpecificOutput.permissionDecision` shape). The E-231-02 hook is therefore **detect-and-signal only**; rollback/prevention is explicitly out of scope.

### Cross-check protocol (referenced by E-231-01 AC-3)
When a target known/expected to be non-empty returns empty/truncated/garbled output: treat it as a FAILURE; cross-check via an independent channel (e.g., `wc -l` / `wc -c` / `sed -n` / `cat -n`, or a second tool such as Read-vs-Glob); retry; if a clean result still cannot be obtained, escalate rather than asserting. When two channels disagree, the clean read wins over a flaky empty/garbled result -- a "no files found" Glob is NOT proof of absence under a flaky channel.

### Detection-vs-tooling division of labor
- **Empty / truncated / silent-partial-edit** -> tooling can catch (hook in E-231-02; cross-check prescription in E-231-01).
- **Garbled-but-nonempty** (wrong line numbers, stale content, another file's bytes, command echoed not executed) -> only catchable by an agent applying the discipline rule (E-231-01); no tool can reliably detect it.

### Hook design constraints (E-231-02)
- Follow the established hook plumbing (Corrected hook baseline above): read stdin JSON via `INPUT=$(cat)`, extract with `jq`. Note the new PostToolUse signal shape differs from PreToolUse (PostToolUse capability Note above).
- Re-read must be cheap (`test -s` + `grep`, not a full diff).
- Transient-empty (re-read empty/unreadable while file should exist) -> retry once, then warn; MUST NOT hard-fail every legitimate edit under flakiness.
- Real-absent (file readable but `new_string` genuinely missing) -> loud detect-and-signal failure: emit JSON `{"decision":"block","reason":"<file>: new_string not found after Edit/Write — edit did not land"}` (top-level `decision`, surfaces the reason + halts next-turn continuation). This does NOT prevent or roll back the already-executed write -- detect-and-signal only (PostToolUse capability Note above).
- Hook's own internal failure (e.g., `jq` absent) -> fail OPEN (must never brick an edit) but ANNOUNCED with one terse "verification unavailable" line, following the existing fail-open-on-missing-jq precedent (E-231-02 AC-9).

### Story independence
All five stories touch disjoint files and have no inter-story dependencies; they may execute in any order. E-231-02 is the anchor (highest value -- the only failure class with no behavioral workaround) but does not block the others. (E-231-05 shares `.claude/rules/dispatch-pattern.md` with the separately-added live Addition-B advisory load-notice line, but the two are distinct paragraphs of content -- relay integrity vs. serialize-under-load advisory -- and do not conflict.)

### Context-fundamentals governing constraint (whole epic)
This is a context-layer epic; ambient-budget cost is a first-class design concern. `.claude/skills/context-fundamentals/SKILL.md` governs every story:
- **Reference, don't duplicate.** New rules/skills cross-reference existing rules and committed memories (e.g., `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`) rather than restating them (CLAUDE.md "rules reference, not duplicate" + the context-fundamentals duplication warning).
- **Earn the always-loaded cost.** The E-231-01 rule is `paths: "**"` (loaded for every agent on every session, on top of the ambient context-layer baseline) -- it must be minimal and tight enough to justify the permanent per-session token cost (E-231-01 AC-7).
- **Lean hooks.** The E-231-02 hook output is injected into context; it must be terse and fire only on real failures. A hook that emits on transient empties (cries wolf) is context poison (E-231-02 AC-8).
- **Completeness, not raw ingestion.** The E-231-03 read-receipt gate requires a complete digest of findings, NOT brute-force ingestion of a large raw blob (a 373KB result would blow the red-zone budget).

### Related memory
The discipline rule (E-231-01) and the triage gate (E-231-03) cross-reference the committed PM memory `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` (clean-reread-before-defect) as their stable repo anchor, and reference the read-findings-before-triage lesson conceptually. The latter's memory file lives in non-version-controlled main-session auto-memory and MUST NOT be linked by path (an implementer in a worktree cannot verify it).

## Open Questions
- None. (Previously open: "can a PostToolUse hook block?" -- now RESOLVED definitively, see Technical Notes "PostToolUse capability": it cannot block or roll back; the hook is detect-and-signal only.)

## History
- 2026-05-31: Created (DRAFT). Promotes IDEA-075. Scope: deterministic detect-and-defend core (~4 stories) + upstream report; transport bug itself is non-fixable and out of scope.
- 2026-05-31: Incorporated Codex spec-review (5 findings, all ACCEPT) + CA's hook deliverables. F1: E-231-04 AC-5 reworded "shipped"→"planned" siblings (preserves any-order independence). F2: cross-refs repointed off non-repo `feedback_read_findings_before_triage.md` to committed `feedback_clean_reread_before_defect.md` + conceptual lesson ref (E-231-01, E-231-03). F3: corrected hook baseline (jq not python3; JSON-with-exit-0 not non-zero; epic-archive-check.sh added; top-level `decision`). F4: PostToolUse-cannot-block recorded as a definitive Technical Note; E-231-02 AC-4/AC-7 made testable. F5: E-231-04 path/owner fixed to `.project/research/E-231-harness-repro/` + claude-architect. Added E-231-02 AC-9 (fail-open-but-announced, CA's independent recommendation). SE labeled advisory-only in Dispatch Team.
- 2026-06-01: Set READY. Post-incorporation consistency sweep clean (no OLD-value drift; all NEW values present; committed cross-ref target `feedback_clean_reread_before_defect.md` confirmed to exist). Quality checklist passed: 4 vertical-slice stories, testable ACs, disjoint files (no parallel conflicts), all stories independent (any-order), expert consultation done (CA design pass + SE advisory on the E-231-02 predicate).
- 2026-06-01: Added E-231-05 (relay-integrity rule) post-READY, growing the epic 4→5 stories. Closes the orchestrator-relay fabrication gap surfaced during this very planning session (review findings composed from unread output relayed as if from Codex, twice) -- a failure class not covered by E-231-03 (in-skill triage gate) or E-231-01 (always-loaded assert-unseen prohibition). CA-designed, PM-framed ACs; user-approved. Reconciled story-count references (Overview, Dispatch Team, Story independence) and added a 5th Success Criteria bullet; consistency sweep clean. E-231-05 did NOT go through the original Codex spec-review pass -- the scorecard's Codex row is left at the original four-story pass to stay honest. Epic stays READY. (Companion decision: the concurrency-cap addition was approved as a separate live advisory load-notice line in `dispatch-pattern.md`, implemented directly by CA outside this epic -- not an E-231 story.)
- 2026-06-07: Codex re-review (5-story) found 3 findings (1 P1, 1 P2, 1 P3), all accepted and fixed: F1 E-231-04 AC-1 reworded to story-local outcome; F2 E-231-05 AC-6 two-vs-three cross-pointer ambiguity resolved; F3 E-231-04 Context 'three'->'four' stories. Epic stays READY.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex spec-review iteration 1 | 5 | 5 | 0 |
| Codex spec-review iteration 2 | 3 | 3 | 0 |
| **Total** | **8** | **8** | **0** |

Notes: Only one review pass ran this session. No internal CR spec-audit pass ran -- CA's design pass and the main session's cross-channel verification substituted. Both READY blockers were P1 Codex findings (F1, F2), both fixed.
