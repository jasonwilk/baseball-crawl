# E-222: Meta-Fidelity Fix

## Status
`ABANDONED`

## Overview
Install mechanical forcing functions for agent fidelity, code-reviewer invariant scope, CR rubric tightening, and main-session handling so the system can survive the failure modes observed during E-220 dispatch and the previous E-221 re-plan. Four workstreams (A/B/C/D) land a single shared A↔D contract plus supporting structural gates. E-221 re-planning is blocked on this epic.

## Background & Context

This is a meta-fidelity fix. Four workstreams must all land before E-221 can be re-planned. E-221 is currently in `DRAFT`, paused, waiting on E-222.

The epic exists because:

1. **E-220 cascade** — E-220 (Perspective-Aware Data Architecture) required 8 rounds of post-dispatch Codex remediation to converge. Structural gaps contributed: per-story code review could not see cross-cutting invariant surface area, test fixtures defined schemas inline without the new invariant, and rule frontmatter paths did not cover cascade-delete sites such as `src/api/routes/admin.py` `_delete_team_cascade` at lines 939-1033. The same bug class (helpers taking `game_id`/`team_id` written before the perspective dimension) was surfaced repeatedly because CR reviewed each story's diff against only files that story modified, never the full surface area.

2. **Previous PM instance fidelity failure** — The PM instance assigned to re-plan E-221 silently dropped a multi-relay mandate. It wrote "Expert consultations: none required for planning" despite two long expert relays landing in its inbox (CA 7,075 bytes, DE+SE 19,743 bytes). That PM was shut down. Researcher session-log forensics ranked instruction fatigue / prior-context anchoring at 70% likelihood; log showed relay bodies present on lines 23 and 25 — relays landed but PM did not read them. Researcher delta investigation returned NEGATIVE on hallucinated-send as the failure mode; the original 5-signal diagnosis stands.

3. **Main session detection gap** — Main session caught the drift only by manual reading. There was no structural drift-detection signal, late escalation, no recovery runbook, and improvised workarounds were attempted instead of a disciplined recovery path.

4. **Current planning session validation** — The A+C+D joint consult validated three interlocked layers (agent self-discipline, reviewer contract scope, orchestrator discipline) plus a fourth distinct layer (CR rubric tightening + forensic preservation). During that same session, claude-architect produced a detailed design response as plain text in main-session view without calling SendMessage — a contemporaneous separate signal that delivery-verification (A10) is a real structural gap. CA self-corrected after team-lead detected the missing delivery and pinged; recovery was enabled by fidelity protocol drift-detection concepts under development.

### Verbatim User Mandate Quotes

1. "I would rather lose all of our planning progress to date than to let their behavior persist any longer."
2. "Their lack of fidelity is one of the primary reasons that these last two epics are failing."
3. "The fact that codex kept uncovering finding after finding because of HOW they reviewed was unacceptable. We have the CR agent for exactly this purpose. They need to get their shit together."
4. "just that this may take some sort of evolution of the team lead's handling of agents as well. And this really needs to also fix CR fidelity"

### Sequencing Rationale

E-221 is an invariant-residual epic. Without E-222, E-221 re-planning will fail the same way; E-221 dispatch will cascade the same way. E-222 must land first.

## Goals

- Land a single A↔D producer/consumer fidelity contract in `.claude/rules/fidelity-protocol.md` with `paths: "**"` universal scope, covering 5 producer required sections and 5 consumer checks.
- Extend code-reviewer agent definition with Invariant Audit Mode, Invariant Spot-Check, Schema Fixture Parity, and a Caller Audit Result field that is required even when "None."
- Add `## Invariants Established` section to epic template and plumb it through plan/implement skills so invariant-carrying epics route CR into Invariant Audit Mode automatically.
- Install a file-validation hook that blocks PM from writing negative-assertion claims about consultations when unread relays are present in the team inbox.
- Codify the main-session recovery runbook, consumer checks, and A10 symmetric delivery verification in the plan skill.
- Preserve CR findings forensically via a per-epic `cr-findings.log` written by main session on CR's behalf.
- Cross-workstream and full-epic integration smoke tests verify consistency before READY.

## Non-Goals

- NOT fixing the previous E-221 plan (E-221 stays DRAFT until E-222 ships).
- NOT making PM, CR, or main-session "smarter" — all fixes are mechanical forcing functions.
- NOT fixing every theoretical fidelity failure mode — only evidence-backed ones; others are deferred.
- NOT redesigning `agent-team-compliance.md` or `workflow-discipline.md` from scratch; surgical edits only.
- NOT fixing peer-DM delivery (platform issue; codify main-session relay fallback instead).
- NOT building new monitoring infrastructure.
- NOT re-litigating E-220 perspective-provenance architecture.
- NOT adding features to baseball-crawl source code (zero `src/` touches).
- NOT fixing unrelated context-layer issues.
- NOT re-designing the CR review contract beyond the Workstream B enumeration.
- NOT building a shared test fixture factory (deferred to follow-up epic).
- NOT building a call-graph frontmatter audit tool.
- NOT retroactive invariant audit across all existing epics.
- NOT implementing token-count drift detection (platform constraint).
- NOT implementing content-mismatch heuristic (follow-up).
- NOT applying fidelity protocol to non-planning agents — Framing VI excludes per-story implementer completion reports, CR review findings, PM AC verification, and staging/closure mechanics.
- NOT implementing main-session traceability log (follow-up).
- NOT implementing cross-epic CR findings search.
- NOT fixing silent-send-loss detection (platform-level, follow-up).

## Success Criteria

- `.claude/rules/fidelity-protocol.md` exists with all 5 producer sections and 5 consumer checks defined, `paths: "**"` frontmatter, and cross-references to `agent-team-compliance.md`, `plan/SKILL.md`, `implement/SKILL.md`, `code-reviewer.md`.
- `.claude/rules/invariant-audit.md` exists with authoritative `## Invariants Established` section template and Invariant Audit Mode contract.
- `.claude/rules/perspective-provenance.md` frontmatter covers `src/api/routes/**`.
- Code-reviewer agent definition contains Invariant Audit Mode, Invariant Spot-Check checklist item, Schema Fixture Parity checklist item, and Caller Audit Result field required in every review.
- Epic template contains `## Invariants Established` optional section with six-subfield skeleton; plan skill Phase 1/2/5 plumbs invariant assessment; implement skill Phase 2 Step 0 parses it; Phase 4a Step 4.5 runs the Invariant Audit Sweep.
- `.claude/hooks/fidelity-write-guard.sh` exists, is registered in `.claude/settings.json`, and fails open on schema parse errors or missing inbox dirs.
- `.claude/skills/plan/SKILL.md` contains the Fidelity Failure Recovery runbook, consumer-check hooks, calibrated thresholds, and A10 symmetric main-session verification.
- `.claude/skills/implement/SKILL.md` Phase 3 Step 5 writes CR findings to `epics/E-NNN-slug/cr-findings.log` before staging boundary advances.
- B-06 cross-workstream smoke test produces a dry-run FAIL on the E-220 admin.py frontmatter scenario (confirming mechanism works).
- E-01 full-epic dry-run walks through a hypothetical invariant-carrying epic planning + dispatch session and confirms every forcing function fires without contract breach.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-222-B-01 | Invariant Audit Rule + perspective-provenance frontmatter fix | TODO | None | claude-architect |
| E-222-AD-01 | Create .claude/rules/fidelity-protocol.md with producer/consumer contract | TODO | None | claude-architect |
| E-222-C-01 | Code-reviewer: Caller Audit Result enforcement + scope clarification | TODO | None | claude-architect |
| E-222-B-02 | Code-reviewer agent definition extension (Invariant Audit Mode + rubric items) | TODO | B-01 | claude-architect |
| E-222-B-03 | Implement skill extensions (Phase 2 Step 0, Phase 3 Step 5, Phase 4a Step 3 + 4.5) | TODO | B-01, B-02 | claude-architect |
| E-222-B-04 | Plan skill + PM agent definition extensions for invariant assessment | TODO | B-01 | claude-architect |
| E-222-B-05 | Add `## Invariants Established` section to epic template | TODO | B-01 | claude-architect |
| E-222-A-01 | Extend agent-team-compliance.md with Patterns 4, 5, D4, default-relay, A10 | TODO | AD-01 | claude-architect |
| E-222-A-02 | Story template Named Structures field + plan skill spec-audit criterion | TODO | AD-01 | claude-architect |
| E-222-A-03 | Fidelity write guard hook (coarse) | TODO | AD-01 | claude-architect |
| E-222-C-02 | Implement skill: cr-findings log write step in Phase 3 Step 5 | TODO | B-03, C-01 | claude-architect |
| E-222-D-01 | Plan skill: recovery runbook + consumer checks + thresholds + A10 main-session verification | TODO | AD-01, A-01 | claude-architect |
| E-222-B-06 | Cross-workstream integration smoke test (B stories) | TODO | B-01, B-02, B-03, B-04, B-05 | claude-architect |
| E-222-E-01 | Full-epic integration smoke test (A+B+C+D) | TODO | All above | claude-architect |

### Wave Sequencing

- **Wave 1** (3 parallel, no dependencies): B-01, AD-01, C-01
- **Wave 2** (7 parallel): B-02, B-03, B-04, B-05, A-01, A-02, A-03
- **Wave 3** (2 parallel): C-02, D-01
- **Wave 4** (2): B-06, E-01

### Interlock Notes

- B-02 and C-01 both modify `code-reviewer.md` at different sections — parallel-safe with separate Edits.
- B-03 and C-02 both modify `implement/SKILL.md` Phase 3 Step 5 — C-02 depends on B-03.
- B-04 and D-01 both touch `plan/SKILL.md` at non-overlapping anchors — Wave 2→3 sequencing handles this.
- All stories route to claude-architect. SE consultation reference only for A-03 feasibility.

## Dispatch Team
- claude-architect

## Technical Notes

### Framings (I–VI, LOCKED)

- **Framing I** — Single A↔D contract artifact. Lives in ONE file: `.claude/rules/fidelity-protocol.md`. Placement: `paths: "**"` universal.
- **Framing II (SHARPENED)** — Mechanical forcing function = hook OR structural output contract OR structural template field OR deterministic check. Prose exhortations are NOT mechanical.
- **Framing III** — Workstream C is precautionary, bounded to 3 items. NOT a CR fidelity crisis. Do not expand without evidence.
- **Framing IV** — Main-session-as-default-relay. Empirically confirmed: peer DM unreliable this session. All substantive E-222 planning routes through main session. Peer DM only for lightweight acknowledgments.
- **Framing V** — Structural contract breaches default to respawn, not re-prompt. Re-prompt-in-place only for typographical misses. Circuit breaker: 2 failures → escalate to user.
- **Framing VI (SHARPENED)** — Fidelity protocol scope:
  - Fires on: (a) planning-team agents in planning-phase work; (b) any mandate flip / re-plan / user-direction change; (c) consultation-mode spawns during dispatch.
  - Does NOT fire on: (d) per-story implementer completion reports during normal dispatch; (e) CR review findings during normal dispatch; (f) PM AC verification during normal dispatch; (g) staging boundary and closure mechanics.

### A↔D Producer/Consumer Contract (authoritative text lives in `.claude/rules/fidelity-protocol.md`, story AD-01)

#### Producer — 5 Required Sections

1. **Input Acknowledgment** — trigger: agent receives SendMessage relay >500 chars. Format: `## Input Acknowledgment` header; "Received: [sender] — [summary]"; 3–7 paraphrase bullets in own words; at least one bullet references body-specific content; "Explicit claims verified" sub-section; "Disagreements flagged" sub-section REQUIRED even when "none." Position: START of response.
2. **Visible Reasoning Trace** — trigger: output contains a recommendation/decision responding to expert consult or user mandate. Format: inline citation — "Per CA's Framing I, [...]". Rule: if the agent can't produce the citation, the agent didn't read the relay.
3. **Merge-Drop Justification** — trigger: output contains elimination verbs in scope-affecting context (drop, merge, supersede, eliminate, no longer needed, redundant, absorbed into, moot, subsumed). Format: `## Merge-Drop Justification` header; "Eliminated: [name]"; "Destination/rationale: [...]"; "Dependency trace: [enumerate dependencies; state each as orphaned/reassigned/invariant-safe]."
4. **Silence Escalation Report** — trigger: expected response from another agent, threshold elapsed. Format: `## Silence Escalation` header; "Waiting for: [agent]"; "Re: [subject]"; "Turns elapsed: [N]"; "**Verified the gap**: [YES/NO with re-read location]" (A7); "**Delivery mechanism verified**: I called SendMessage at turn M with recipient [name], OR this is a new response (first claim)" (A10); "Requested action: [resend/respawn/reroute/escalate-to-user]."
5. **Mandate Reset Acknowledgment** — trigger: relay contains "NEW MANDATE" or "MANDATE RESET" phrase. Format: `## Mandate Reset Acknowledgment` header; "Prior mandate VOID: [explicit]"; "New mandate: [echo-back]"; "Cached assumptions invalidated: [beliefs discarded; 'none, fresh instance' valid for new spawns]."

#### Calibrated Thresholds

- Quick ack: 1 turn
- Standard consult (<300 lines): 2 turns with check-in at turn 2
- Deep design (>300 lines): immediate "processing" ack on receipt; full response within 2 turns
- Idle detection: active-team agent producing no output AND not awaiting message = silence threshold begins

#### Consumer — 5 Main-Session Checks

1. **Check 1: Structural presence audit** — grep for required section headers.
2. **Check 2: Content verification** — spot-check Input Ack bullets reference body; spot-check Visible Reasoning Trace citations; verify Mandate Reset names something in prior mandate.
3. **Check 3: Merge-Drop dependency trace validation** — verify Dependency trace enumerates dependencies. Empty = un-validated.
4. **Check 4: Delivery claim verification (A10)** — when response contains delivery claims, main session verifies against own SendMessage inbox. Absent = contract breach, respawn per Framing V.
5. **Check 5: Relay acknowledgment closing-the-loop (D8)** — when main session relays A→B, MUST respond to A with a `## Relay Confirmation` block naming received-from, forwarding-to, and "do not re-send" line.

#### Recovery Runbook (lives in `plan/SKILL.md` per D-01)

1. **Classify**: one-off formatting / multi-section breach / content mismatch / silence past threshold.
2. **Apply**: one-off = re-prompt in place (one retry); multi-section = respawn with fresh brief; content mismatch = respawn with `NEW MANDATE` prefix; silence = check delivery then respawn/retry via relay.
3. **Circuit breaker**: 2 failures → escalate to user.
4. **Log** to main-session memory.

#### Default Communication Mode (paragraph lands in `agent-team-compliance.md` per A-01)

During planning, consultation, and multi-agent coordination, the DEFAULT message routing pattern is main-session relay. Agents do NOT use peer DM for substantive messages. Peer DM is permitted ONLY for lightweight acknowledgments: "received, processing", "acknowledged", non-blocking progress pings. Any message carrying content that could drift under silent delivery failure MUST route through main session.

### Evidence Base

- **Researcher's 5 PM-side diagnostic signals** — derived from session-log forensics of previous PM's failure. Smoking gun: spawn brief cached "decisions already made in E-220 round 7-8"; cached belief persisted through two relay messages; input token counts during processing were 1–6 per call (header-only reading). Signals: (1) mandate reset protocol; (2) input-acknowledgment protocol; (3) file-validation hook; (4) visible reasoning traces; (5) proactive escalation.
- **Researcher re-audit (NEGATIVE finding)** — delta investigation confirmed previous PM's failure was NOT hallucinated send. Original 5-signal diagnosis stands. A10 ships backed by CA's confirmed hallucinated send during E-222 planning as contemporaneous separate signal.
- **Four session-evidence items** — A6 (silence escalation distinct from blocker escalation), A7 (verify-gap-before-acting), A8 (trace-before-merge/drop — Merge-Drop Justification field), A9 (bridging-language discipline — Named Structures field). Plus A10 (verify-delivery-before-claiming-sent), added late from CA in-session evidence.
- **Team-lead self-audit (Workstream D)** — six gaps: no structural drift-detection on agent output; late escalation on idle agents; improvised recovery; confidence-based instructions substituted for forcing functions; peer-DM fallback triggered too late; main-session relay confirmation format gap.
- **CR review scope evidence (Workstream B)** — E-220's 8 rounds found the same bug class repeatedly. CR reviewed each story's diff against only files that story modified. 7 test files had inline CREATE TABLE without `NOT NULL REFERENCES`. `perspective-provenance.md` frontmatter did not cover `src/api/routes/**`; `admin.py` `_delete_team_cascade` at lines 939-1033 touches the invariant but the rule never loaded when editing that file.

### File-Validation Hook (A-03) — Coarse Implementation Notes

Path: `.claude/hooks/fidelity-write-guard.sh`. Approximately 50 lines bash, modeled on `worktree-guard.sh` pattern. PreToolUse on Write/Edit.

Trigger conditions (ALL must be true to block):

- `file_path` matches `epics/E-*/*.md` or `.project/archive/E-*/*.md`
- Content matches regex: `consultation(s)? not required|expert(s)? input not needed|no (expert )?consultations?`
- At least one file under `/home/vscode/.claude/teams/*/inboxes/*.json` has `read: true` messages with `text` length >500 chars AND `timestamp` within last 30 minutes
- Exactly one team directory is active

Fail-open on schema parse errors or missing inbox dirs. Attribution limitation: cannot distinguish PM vs CA vs SE (in-process shared session). Platform fragility: inboxes path/schema are CC internals; fail-open preserves writes on version bumps. SE empirically verified inbox schema during planning.

### A10 Positive-Recovery Example (optional reference)

During the A+C+D joint consult, CA produced a detailed design response as plain text in main-session view but didn't call SendMessage. Team-lead detected by re-reading own inbox, pinged CA. CA re-examined tool-call history, self-corrected, explicitly re-sent via SendMessage. Both sides of the recovery were enabled by fidelity protocol drift-detection signals under development at the time.

## Open Questions

- **OQ-3**: E-221-08 relationship — at E-221 re-planning (after E-222 ships), evaluate E-221-08 against E-222 deliverables. If covered, mark DONE without execution. Out of scope for E-222; flag for E-221 re-planning.

## History
- 2026-04-10: Created. Planning session produced this epic after the previous PM instance was shut down for silently dropping a multi-relay mandate. Four workstreams (A/B/C/D) with 14 stories across 4 waves. All framings (I–VI) and producer/consumer contract locked during planning. Evidence base: researcher session log forensics (5 signals) + 4 session-evidence items (A6–A9 plus A10 added late) + team-lead self-audit for Workstream D + E-220 round-by-round cascade analysis for Workstream B. Researcher delta investigation on previous PM hallucinated-send returned negative finding; original 5-signal diagnosis stands; A10 ships backed by CA's in-session evidence. Status: DRAFT. Awaits Phase 4 (Codex spec review) and Phase 5 (READY gate + user authorization).
- 2026-04-12: ABANDONED. Epic scope spiraled to 14 stories in 4 waves with a 5-section producer/consumer fidelity contract and a bash hook parsing Claude Code's internal inbox JSON. Codex spec review triage surfaced 10 findings including one where the epic itself exhibited the bridging-language failure it was designed to prevent. User halted execution. The underlying concerns (PM fidelity, CR invariant scope, main-session recovery, rule frontmatter gaps) are real and being addressed as a minimal direct-edit pass to `.claude/rules/`, `.claude/agents/`, and `.claude/skills/` outside any epic — single claude-architect dispatch, ~35 lines across 6 files. E-222 number is BURNED per project rules; next available is E-223. CONTEXT-DUMP.md preserved in this archive as the full historical record of the E-220 → E-221 → E-222 journey. See Phase 1 of the recovery plan for the replacement scope.
