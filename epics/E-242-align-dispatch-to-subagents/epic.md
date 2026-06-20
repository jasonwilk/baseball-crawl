# E-242: Align Dispatch/Plan/Implement Workflow to Subagent Framing

## Status
`READY`

## Overview
Claude Code v2.1.178 removed the `TeamCreate` / `TeamDelete` tools; multi-agent coordination is now done by spawning named subagents via the `Agent` tool with implicit team formation. Our context layer still instructs agents to call those removed tools, which is a hard breakage. This epic updates the dispatch/plan/implement workflow and supporting rules to current Claude Code guidance — a vocabulary alignment plus removal of two dead tool calls. There is NO change to the dispatch model: PM and code-reviewer stay long-lived and resumable via `SendMessage`, and every routing rule, staging boundary, circuit breaker, closure step, and shutdown ordering stays exactly as written.

## Background & Context
Our agent-team workflow was built around an explicit "create the team" ceremony (`TeamCreate`) and an explicit teardown (`TeamDelete`). As of v2.1.178 those tools no longer exist: the team forms implicitly on the first `Agent`-tool spawn, and teardown is automatic when the session exits. Coordination between the main session and its spawned subagents is via `SendMessage`, and spawned subagents are long-lived and resumable (the main session re-engages a named subagent with its context intact). This resumability depends on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` being set in `.claude/settings.json`; without it the team-coordination tools (`SendMessage` and the shared `Task*` task list) are unavailable and spawns are one-shot.

The strategic decision (confirmed by the user via the main session) is **Option B**: keep the experimental-agent-teams flag enabled, adopt subagent vocabulary, and drop the explicit-team/`TeamCreate` ceremony across the context layer — with no behavioral change to the dispatch model.

This is a context-layer epic. Per the standing convention, **claude-architect (CA) led the design** (the per-file inventory, the canonical replacement glossary, and the design-sensitive preservation calls in Technical Notes). The PM frames acceptance criteria and owns story structure, sizing, dependencies, and the quality checklist.

Two items investigated during design and resolved:
- **Filename**: `agent-team-compliance.md` is KEPT (user-confirmed — no rename). Only in-file prose framing changes.
- **SE/DE frontmatter**: an earlier concern that software-engineer/data-engineer agent definitions were missing `SendMessage`/`Task*` tools was **retracted** — CA re-verified all 9 agents carry them (the earlier flag was a truncated read). No AC is framed around it; it is out of scope.

## Goals
- Remove every instruction to call the removed `TeamCreate` / `TeamDelete` tools from the context layer.
- Standardize the dispatch/plan/implement vocabulary on named-subagent spawning with implicit formation, automatic teardown, and `SendMessage` resumption, per the canonical glossary in Technical Notes.
- State the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` flag dependency once durably in `CLAUDE.md` and the epic Technical Notes (not in every spawn block).
- Correct one behaviorally-wrong line in `multi-agent-patterns/SKILL.md` (parallel-stories vs. serial staging) discovered during design.
- Refresh CA's agent-memory platform facts that are now backwards/stale (nested-teams claim, removed tools).

## Non-Goals
- **No behavioral change** to the dispatch model. PM and code-reviewer remain long-lived; the staging boundary, circuit breakers, closure sequence, shutdown ordering, and all routing rules stay exactly as written.
- No rename of `agent-team-compliance.md` (KEEP — user-confirmed).
- No change to agent-definition frontmatter (the SE/DE concern was retracted as a non-bug).
- No re-litigation of the broader philosophy or routing-chain content of `multi-agent-patterns/SKILL.md` — only the one behaviorally-wrong line (L55) is corrected.
- No change to the explicit `shutdown_request` to PM — that is a real ordered action and stays.

## Success Criteria
- A grep for `TeamCreate` or `TeamDelete` across `CLAUDE.md`, `.claude/rules/`, and `.claude/skills/` returns zero instructional uses (a dated historical note recording their removal is permitted; see TN-5).
- A grep for the literal `[team-name]` placeholder across the touched files returns zero (CA-F2).
- The touched skills and `agent-team-compliance.md` apply the SURGICAL glossary (TN-1): the removed-tool ceremony, the `[team-name]` placeholder, and explicit create/delete-the-team *step* framing are gone, while "team"/"teammate" collective nouns are retained. The reframe of always-loaded rules is length-neutral (TN-10).
- `agent-team-compliance.md` Patterns 1, 2, and 3 retain their anti-fabrication intent and the multi-agent spawn guarantee, reframed onto the single `Agent`-tool spawn primitive (TN-3).
- `CLAUDE.md` carries the durable flag-dependency one-liner exactly once (TN-4).
- `multi-agent-patterns/SKILL.md` L55 states serial execution and points to the implement skill as authoritative (TN-6).
- CA's agent-memory platform facts are corrected (nested-teams direction, removed tools, flag→SendMessage dependency).
- The closure full-suite-green gate passes (no source/test changes are expected; the gate runs unconditionally).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-242-01 | Subagent vocabulary in plan + implement skills | TODO | None | - |
| E-242-02 | Subagent vocabulary in rules + ancillary skills (incl. serial-stories fix) | TODO | None | - |
| E-242-03 | CLAUDE.md flag note + agent-memory platform facts | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Canonical Replacement Glossary (SURGICAL — authoritative; S1 and S2 use identical language)
**Scope is SURGICAL (user-confirmed).** The goal is to fix the MENTAL MODEL — spawn via the `Agent` tool, no ceremony, resumable via `SendMessage` — NOT to ban the word "team." The reframe of the always-loaded rules is a length-neutral phrase swap, not an expansion (see TN-10).

REMOVE / REPLACE — the ONLY targets:
- **Removed tool calls** `TeamCreate` / `TeamDelete` — any instruction to call them.
- **The `[team-name]` placeholder** in spawn contexts → spawn contexts become role-only (e.g., "You are the product-manager subagent.").
- **Explicit team setup-step framing** — a discrete "create the team" / "Use `TeamCreate`" *step* → implicit-formation language: "The team forms implicitly on the first spawn — there is no separate setup step."
- **Explicit team teardown-step framing** — a discrete "delete the team" *step* → "Teardown is automatic when the session exits — there is no explicit delete step." (The explicit `shutdown_request` to PM is a real ordered action and STAYS.)

KEEP — explicitly blessed, do NOT swap:
- The words **"team" and "teammate" as collective nouns** — the platform docs use them and the experimental flag is ON, so we ARE still using agent teams.
- Descriptive prose that mentions a team forming or roles on a team (e.g., a "## Team Roles" heading, or "creates the team" used to *describe* the now-implicit formation rather than to instruct a `TeamCreate` step) — conceptually accurate under implicit formation.
- Incidental "Agent Teams" / "teammate" usages that are not the obsolete dual-primitive either/or (see TN-3 for the one mental-model exception at the `agent-team-compliance.md` intro).

NEW spawn verb (use only where replacing a `TeamCreate`-ceremony sentence): "spawn [the agent(s)] as named subagent(s) via the `Agent` tool." Do NOT scrub every incidental "teammate."

Persistence framing to use where a spawn block needs it: "Spawned subagents are long-lived and resumable: the main session re-engages a named subagent via `SendMessage` with its context intact."

### TN-2: No-Behavioral-Change Invariant
This epic is vocabulary + removal of two dead tool calls ONLY. Every routing rule, staging boundary (`git add -A` after each story passes review), circuit breaker, closure step, and shutdown ordering stays exactly as written. The unified-team-lifecycle handoff and the PM context-recovery fallback continue to exist; they RELY on resumability and are preserved — only their vocabulary is aligned (respawn-with-summary stays as the fallback path; `SendMessage` resumption is the normal path).

### TN-3: `agent-team-compliance.md` — Pattern 1 SURVIVES, reframed (NOT removed)
The file's intent is anti-fabrication (origin: E-076), independent of the spawning mechanism. KEEP the filename. Reframe in-file prose only:
- **Pattern 1 trigger** (2+ agents named): unchanged.
- **Pattern 1 Required action**: OLD "Use Agent Teams. Create the team via TeamCreate and spawn each named agent as a teammate. Assign work through the team." → NEW "Spawn each named agent as a separate named subagent via the `Agent` tool (the team forms implicitly on the first spawn — no setup step). Route work to each via `SendMessage`." The guarantee is preserved: when 2+ agents are named, spawn ALL as distinct live subagents — do not collapse to one, do not have one consult the others on your behalf, do not fabricate.
- **Pattern 1 Prohibited bullets**: under surgical the ONLY necessary change is the stale single-primitive "Task tool" framing (there is one spawn primitive now) — KEEP the blessed "team"/"teammate" wording. Intent preserved: (1) don't spawn one agent and have it consult the others on your behalf; (2) don't collapse a multi-agent request into a single agent or a fabricated consultation; (3) don't silently downgrade without telling the user.
- **Pattern 2 Required action**: the now-moot Teams-vs-Task either/or (one spawn primitive) collapses → "Spawn the named agent as a named subagent via the `Agent` tool." Rest unchanged.
- **Pattern 3** (anti-fabrication): substantively unchanged (reinforced by no-nested-teams: only the lead spawns); light vocabulary alignment only.
- **"User Request Classification" intro (the section above Pattern 1) — MENTAL-MODEL fix, not a word-ban**: it currently frames the decision point as a choice "between Task tool, Agent Teams, or answering directly" — the obsolete DUAL-PRIMITIVE either/or. There is one spawn primitive now, so collapse the either/or to: spawn subagent(s) via the `Agent` tool vs. answering directly. The word "team" is fine; it is the stale "Task tool vs Agent Teams" *choice* that must not survive in this always-loaded (`paths: "**"`) rule. Length-neutral phrase swap (TN-10); exact wording is CA's call.

### TN-4: Flag Dependency (state ONCE — Technical Notes here + CLAUDE.md; NOT in every spawn block)
Canonical text: "Resumable subagents require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (set in `.claude/settings.json`); without it the team-coordination tools (`SendMessage` and the shared `Task*` task list) are unavailable and spawned agents are one-shot." The **durable runtime home** of this statement is the `CLAUDE.md` Agent Ecosystem note (authored in S3, AC-1) — that is the once-canonical source of truth for the flag dependency. This epic file's Technical Notes are the planning-time source; the skill preambles (S1) must point to the durable `CLAUDE.md` location, NOT to this epic file (which is ephemeral and archived at closure), and NOT repeat the flag caveat in every spawn block. (F-Codex-1.)

### TN-5: Removed Tools — Historical Note Permitted
The removed tools were dropped in Claude Code v2.1.178 (implicit formation, automatic teardown). A dated historical note recording this removal is permitted in agent memory; what is prohibited is any remaining *instruction* to call `TeamCreate`/`TeamDelete`.

### TN-6: `multi-agent-patterns/SKILL.md` L55 — Serial-Stories Correction (behavioral fix, in S2)
L55 "Spawn stories in parallel when they have no file conflicts" is behaviorally WRONG — it contradicts the serial staging-boundary dispatch model. Replace with CA's suggested text: "- [ ] Execute stories **serially** — one at a time — letting the staging boundary (`git add -A` after each story passes review) isolate each story's diff. The implement skill (Phase 3) is authoritative on the dispatch loop." GUARDRAIL: correct ONLY L55; do not re-litigate the skill's broader philosophy or routing-chain (those are accurate).

### TN-7: Scope Boundary — Out of Scope
- Filename rename of `agent-team-compliance.md` (KEEP).
- Agent-definition frontmatter changes (SE/DE concern retracted as non-bug — all 9 agents carry `SendMessage` + `Task*`).
- Any behavioral change to dispatch, staging, closure, or shutdown ordering.

### TN-8: `dispatch-pattern.md` — Documented Retain Decision (resolved under SURGICAL)
`dispatch-pattern.md` is an always-loaded (`paths: "**"`) rule. Its L8 ("creates teams, spawns all agents") and L12 ("Creates the epic worktree, creates the team, assigns stories serially") and "## Team Roles" framing use "team"/"creates the team" **descriptively** — they describe the main session forming a team, which is conceptually accurate under implicit formation. Under SURGICAL these are NOT ceremony *instructions* (there is no `TeamCreate` call, no `[team-name]` placeholder, no discrete "create the team" *step* to remove) and are therefore **retained, not edited**. S2 AC-7 records this as an explicit, verifiable decision (the file contains no `TeamCreate`/`TeamDelete`/`[team-name]`), so the retain reads as intentional rather than a missed sweep. Net: no content edit to `dispatch-pattern.md`.

### TN-9: PM-Owned `lessons-learned.md` Closure Work (added in refinement)
The dated tooling note for `product-manager/lessons-learned.md` (recording the v2.1.178 tool removal and that the three anti-fabrication patterns hold under implicit subagent spawning) is handled by PM during epic closure as a normal PM-memory update — NOT by claude-architect in a story. This honors the canonical "PM updates its own memory" routing carve-out. While positioning that note, PM also ensures the inline historical parentheticals in the E-076 narrative (e.g., "(TeamCreate required)" near L108) read clearly as history, not current instruction. This is PM-memory maintenance, not a dispatched deliverable, so it carries no story AC.

### TN-10: Length-Neutral Guardrail for Always-Loaded Rules (context-fundamentals)
The reframe of the always-loaded rules (`agent-team-compliance.md`; `dispatch-pattern.md` is no-edit per TN-8) MUST be **length-neutral — a phrase swap, not an expansion.** Do NOT add persistence/flag exposition to these rules; that single-source content lives once in `CLAUDE.md` (S3, TN-4). The design's affirmed single-source wins are NOT to be "fixed": the glossary lives once (TN-1), the flag note lives once (TN-4), and the L55 serial line points to the implement skill rather than restating it (TN-6).

### Design provenance
The per-file inventory, glossary, and design-sensitive preservation calls in this epic were authored by claude-architect (context-layer domain owner). Line numbers in story Technical Approach sections are locators from CA's inventory at design time and are guidance, not mandate; the implementing agent (claude-architect) verifies the current location of each target before editing.

## Open Questions
- **F-Codex-2 — RESOLVED (2026-06-20, confirmed by claude-code-guide from the Claude Code docs)**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` gates the whole team-coordination surface — BOTH `SendMessage` AND the `Task*` task tools. `SendMessage` gating is EXPLICIT in the subagents doc; `Task*` gating is INFERRED-from-infrastructure (without the flag no team is set up at session start and no team directories are written, and the shared task list lives under a per-team directory, so `Task*` has no backing store) — the docs group "`SendMessage` and the task management tools" as the team-coordination tools. Reconciliation applied (the "add `Task*`" branch): TN-4 + the durable `CLAUDE.md` note (S3 AC-1) + the CA-memory facts (S3 AC-3/AC-4) all now state the team-coordination surface (`SendMessage` + shared `Task*` list); the `[PENDING]` marker on AC-4 is cleared. The durable `CLAUDE.md` note states the fact plainly (no explicit-vs-inferred editorializing — that honest nuance is recorded here only, per TN-10).

## History
- 2026-06-20: Created (DRAFT). Design led by claude-architect; ACs and structure framed by PM. Strategic direction Option B confirmed via main session.
- 2026-06-20: Refined after code-reviewer spec audit + claude-architect holistic review. **User chose SURGICAL scope** (governing): remove ONLY `TeamCreate`/`TeamDelete` ceremony, the `[team-name]` placeholder, and explicit create/delete-the-team *setup/teardown-step* framing; KEEP "team"/"teammate" as blessed collective nouns; fix the mental model, not the word. Triage (all findings accepted, reconciled to surgical): CR-F1 → `agent-team-compliance.md` intro reframed as a length-neutral mental-model fix of the stale "Task tool vs Agent Teams" either/or (TN-3, S2 AC-3a). CR-F2 + F6 → `dispatch-pattern.md` resolves to a documented no-edit retain decision with a verifiable AC, not an edit (TN-8, S2 AC-7). CR-F5 → TN-1 narrowed to bless team/teammate and target only ceremony+placeholder+setup-step (reverses the earlier over-expansion). CR-F3 / CA-F4 → PM-owned `lessons-learned.md` note moved out of S3 to PM closure (TN-9); S3 no longer touches that file. CA-F2 → added `[team-name]`-grep-zero gate to S1 AC-7 and S2 AC-8, and added the implement Workflow Summary block (L620–646) to S1's inventory. CA-F3 → zero-ripple renumber fix in S1 (keep Step 2 as a light no-op step; do not renumber Phase 2; no stale "Skip Steps 1-3" references). Context-fundamentals → length-neutral guardrail for always-loaded rules (TN-10).
- 2026-06-20: CA confirmed both deferred calls — (a) `dispatch-pattern.md` no-edit CONFIRMED; (b) `agent-standards/SKILL.md` L100–101 IS the stale dual-primitive either/or → added definite S2 AC-5a (length-neutral mental-model fix, synthesis-fan-out semantics preserved).
- 2026-06-20: Codex spec review iteration 1 — 5 findings, all accepted. F-Codex-1 → skill-preamble flag pointer repointed from the ephemeral epic/skill TN to the durable `CLAUDE.md` Agent Ecosystem note (TN-4, S1 AC-5 + soft S3→S1 handoff). F-Codex-3 → S1 AC-7 split into an objective grep AC + the TN-2 no-behavioral-change invariant by reference. F-Codex-4 → S2 AC-8 split into an objective grep AC (anti-fabrication → AC-1/2/3; length-neutral → TN-10). F-Codex-5 → S2 AC-7 reframed explicitly as a verification assertion, not a work item. **F-Codex-2 (the one open item)** → AC-4/TN-4 flag-gating inconsistency (`SendMessage`/resumability vs. also `Task*`) flagged PENDING; escalated to the main session for CA's platform-fact ruling (see Open Questions).
- 2026-06-20: **F-Codex-2 RESOLVED + CLOSED** (claude-code-guide confirmed from the docs): the flag gates the whole team-coordination surface — `SendMessage` (explicit in docs) + the shared `Task*` task list (inferred-from-infrastructure: no flag → no team directory → no task backing store). Reconciled via the "add `Task*`" branch: TN-4, the durable `CLAUDE.md` note (S3 AC-1), and the CA-memory facts (S3 AC-3/AC-4) all now state the team-coordination surface; `[PENDING]` cleared on AC-4. The durable note states it plainly; the explicit-vs-inferred nuance is recorded only in Open Questions (TN-10 length-neutral). Spec fully settled — no open items.
- 2026-06-20: **Status → READY.** Spec fully settled; quality checklist passed. Dispatch NOT authorized (stops at READY per the Dispatch Authorization Gate). Review scorecard:

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 6 | 6 | 0 |
| Internal iteration 1 — Holistic team (CA F1–F4 + context-fundamentals guardrail) | 5 | 5 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| **Total** | **16** | **16** | **0** |

All findings accepted/reconciled to the SURGICAL scope; zero dismissed. The CR audit and CA holistic passes overlap on the S3 routing-inversion finding (CR-F3 ≈ CA-F4), counted once per pass.
