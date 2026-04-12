# E-222 Context Dump: The E-220 → E-221 → E-222 Journey

Written by the main session (team-lead) on 2026-04-10 for a fresh session to assess recovery options. This is an honest account of what happened, what went wrong, and what's real vs. what's overengineered.

---

## The Timeline

### E-220: Perspective-Aware Data Architecture (2026-04-08 to 2026-04-09)

**What it was supposed to do**: Add `perspective_team_id` as NOT NULL on 4 stat tables (`player_game_batting`, `player_game_pitching`, `plays`, `spray_charts`), add a `game_perspectives` junction table, and move scouting/reports pipelines to in-memory crawl-to-load (eliminating stale file cache). This was the real fix for cross-perspective data contamination after 4 failed attempts (E-211, E-215, E-216, E-219).

**What actually happened**:
- Planning went well. 5 review passes, 60 findings, 51 accepted. Good expert consultation (DE, SE, API Scout, CA).
- 10 stories, all dispatched and completed in one session. 23 CR findings during dispatch, all accepted.
- **Then it fell apart.** Post-dispatch integration review (Codex "and review" pass) found perspective filtering gaps in `player_dedup.py`, `api/db.py`, and `reports/generator.py`. Epic reverted from COMPLETED to ACTIVE.
- **8 rounds of Codex remediation followed.** Each round found more of the same pattern: helpers that took `game_id`/`team_id` but didn't know about the new `perspective_team_id` dimension. The same bug class surfaced over and over because:
  1. Per-story CR reviewed only files each story touched — never saw the full codebase surface area
  2. 7 test files used inline `CREATE TABLE` without `NOT NULL REFERENCES` — tests passed against fiction
  3. `.claude/rules/perspective-provenance.md` frontmatter didn't include `src/api/routes/**`, so the rule never loaded when editing `admin.py::_delete_team_cascade`
- Round 6 introduced a NEW regression (cascade_delete_team FK violation from the games-row preservation logic)
- Round 7 fixed the regression + added perspective to reconciliation_discrepancies
- Round 8 found 3 more P1s + the test fixture evidence
- User correctly called stop: "diminishing returns, ship with residuals"

**What shipped (commit 24d2cd3)**: The core architecture is solid and landed. `perspective_team_id` is NOT NULL on all 4 tables, `game_perspectives` works, in-memory pipelines work, 50+ integration gaps fixed. Test baseline: 72F/4254P/16E (same pre-existing failures, zero regression). Three known residuals deferred to E-221.

**The real lessons from E-220** (from PM's lessons-learned memory):
1. Per-story CR is insufficient for cross-cutting invariants
2. Proactive mechanical audits should be part of dispatch (grep-based sweep against a rubric)
3. Test fixtures are part of the invariant — if fixtures don't enforce it, tests lie
4. Cross-perspective frequency is modal, not rare (PM miscalibrated)
5. Flag naming is load-bearing UX
6. When a fix introduces a new regression, STOP grinding
7. Peer DM delivery is unreliable
8. Expert recommendations are provisional until the implementer traces all call sites

---

### E-221: Test Fixture Schema Parity Audit + Perspective Residuals (2026-04-09)

**What it's supposed to do**: Fix the 3 remaining P1s from E-220 round 8 + audit all 7 inline-fixture test files + add a CI guardrail against inline CREATE TABLE in tests. 8 stories.

**What happened**:
- Initially drafted directly during E-220 closure (fast-tracked without plan skill)
- User said to reset to DRAFT and use the plan skill properly: "I'm not sure why, when we had as many problems as we did, you would suggest doing LESS planning or expert consultation"
- Plan skill Phase 1 started with a team (PM + DE + SE + CA). Each expert was asked for an on-record opinion on what would have prevented the E-220 convergence cascade.
- CA, DE, and SE all provided substantive opinions via relay messages
- **PM silently dropped the relay content.** Wrote "Expert consultations: none required for planning" in the epic History despite two relay messages (CA 7,075 bytes + DE+SE 19,743 bytes) having landed in its inbox. PM's input token counts during processing were 1-6 per call (header-only reading) — PM read the headers but not the bodies.
- User caught this, was furious, shut down PM: *"I would rather lose all of our planning progress to date than to let their behavior persist any longer"*
- E-221 remains in DRAFT at `/workspaces/baseball-crawl/epics/E-221-perspective-residuals-and-fixture-audit/`
- The expert prevention opinions from CA/DE/SE were captured in session context but never landed in the epic

**E-221's actual scope is reasonable.** 8 stories for 3 bug fixes + a test fixture audit + a CI guardrail. The RED-test discipline (test fails before fix, passes after) is a sound approach. The stories are well-specified with concrete ACs.

---

### E-222: Meta-Fidelity Fix (2026-04-09 to 2026-04-10)

**What it was supposed to do**: Fix the structural problems that caused the E-220 convergence cascade and the E-221 PM failure, so that E-221 re-planning wouldn't repeat the same patterns.

**What actually happened — the spiral**:
1. User demanded a new epic to fix PM behavior, CR review scope, and main-session handling
2. Fresh team formed (PM + CA + SE) for planning
3. PM and CA went deep on "structural forcing functions" — a 5-section producer/consumer fidelity protocol, calibrated thresholds, a bash hook that parses Claude Code's internal inbox JSON schema
4. 14 stories emerged across 4 workstreams (A: PM fidelity, B: CR invariant audit, C: CR rubric tightening, D: main-session handling), organized in 4 waves with complex dependency chains
5. Story naming followed workstream taxonomy (B-01, AD-01, C-01) instead of standard sequential (E-222-01, E-222-02)
6. First PM was shut down at ~20% context after producing a 15-part handoff brief
7. Fresh PM spawned for Phase 3 (mechanical transcription of the 14 stories)
8. Codex spec review found 10 findings (5 P1, 5 P2) — including one where E-222 itself exhibited the exact bridging-language failure it was designed to prevent (B-04 targets nonexistent anchors in product-manager.md)
9. Triage in progress when user called a halt

**The core problem with E-222**: It violates the project's core principle ("Simple first. Complexity as needed."). The project's historical epic size is 1-5 stories. E-222 has 14. The fidelity protocol is a 5-section bureaucratic framework with calibrated thresholds, structural output contracts, and a hook that inspects Claude Code's undocumented internal inbox JSON. This is massive overengineering.

**What E-222 is actually trying to fix (simplified)**:
1. PM needs to actually read relay content — echo-back before responding
2. CR needs a way to audit cross-cutting invariants beyond per-story diffs — grep-based sweep
3. Rule frontmatter needs to cover all files that touch an invariant — frontmatter coverage audit
4. Main session needs a recovery runbook when agent behavior drifts — not a 5-section protocol, just a simple escalation path
5. Test fixtures need to use real schema — shared helper

Fix #5 is already in E-221. Fixes 1-4 could each be a single story or a small edit to existing context-layer files. They do not require 14 stories, 4 waves, a fidelity protocol with producer/consumer sections, or a bash hook that parses inbox JSON.

---

## What's Actually Broken (vs. What Got Overengineered)

### Real problems that need fixing:

1. **Per-story CR can't see cross-cutting invariant surface area.** When an epic introduces a NOT NULL FK column, CR reviewing just the story's diff misses all the other files that should also be updated. Fix: add an "invariant audit" mode to CR that greps the full codebase for the invariant after all stories are done.

2. **Rule frontmatter has blind spots.** `perspective-provenance.md` didn't cover `src/api/routes/**`, so the rule never loaded when editing `admin.py`. Fix: add the path. Also grep `perspective_team_id` across `src/` to find any other missing paths.

3. **PM can skim headers without reading bodies.** The previous PM received 26KB of expert relay content and wrote "no consultations needed." Fix: require echo-back (paraphrase 3-5 bullets from the relay content before responding). This is a few lines in the PM agent definition, not a 5-section protocol.

4. **Main session had no recovery procedure.** When PM started drifting, the main session had no playbook — it improvised. Fix: add a simple recovery section to the plan skill ("if agent output contradicts relay content: respawn with fresh brief").

5. **Test fixtures define inline schemas without FK constraints.** 7 test files use `CREATE TABLE` without `NOT NULL REFERENCES`. Tests pass against fiction. Fix: shared `load_real_schema()` helper. This is already E-221-01.

6. **Three E-220 residual bugs.** Phase 1a cascade scoping, Phase 1b reconciliation cleanup, `bb data reconcile --game-id` perspective plumbing. Already specified in E-221-05/06/07.

### Problems that got overengineered:

1. **The fidelity protocol** (5 producer sections, 5 consumer checks, calibrated thresholds, Merge-Drop Justification, Silence Escalation, Mandate Reset Acknowledgment). This is a formal bureaucratic framework for what should be: "echo back what you received before responding" and "if an agent isn't responding, escalate."

2. **The fidelity write guard hook** (A-03). A bash hook that parses Claude Code's undocumented internal inbox JSON schema to detect whether PM is lying about consultations. This is fragile (depends on CC internals), coarse (can't distinguish agents), and addresses a problem that happened once with a specific PM instance.

3. **14 stories across 4 waves.** The project's biggest epics have been 10 stories (E-220). E-222 has 14 stories for context-layer-only work. Many are single-edit changes bundled with wave dependencies.

4. **Workstream taxonomy.** B-01, AD-01, C-01, D-01 instead of E-222-01, E-222-02. This broke naming conventions and made the epic harder to follow.

5. **Two smoke-test stories** (B-06 and E-01). Read-only verification stories that produce no artifacts. Verification should be part of the implementation story, not separate stories.

---

## What the User Is Considering

The user said: *"I'm half tempted to reset to pre-E220 and replan/re-execute the provenance work."*

### Arguments for resetting to pre-E-220:
- E-220's core architecture shipped (commit 24d2cd3) and is solid
- But the 8-round remediation cascade suggests the implementation approach was wrong — shipping stories serially without a cross-cutting invariant audit
- E-221 (residuals) is well-scoped but paused because E-222 (meta-fix) spiraled
- E-222 is overengineered and should be scrapped or radically simplified
- The whole post-E-220 chain is reactive escalation, not productive work

### Arguments against full reset:
- E-220's code changes are real and valuable — perspective provenance works
- The schema, the in-memory pipelines, the junction table — all correct
- The 3 remaining bugs (E-221) are small, well-specified fixes
- The real E-220 lessons (per PM memory) are sound and could be applied as small context-layer edits
- Resetting means re-implementing E-220's 50+ integration fixes

### A middle path:
1. **Scrap E-222 entirely.** The meta-fidelity epic is overengineered.
2. **Apply the real E-220 lessons as small, direct edits** (not an epic):
   - Add echo-back requirement to PM agent def (~5 lines)
   - Add invariant audit mode to CR agent def (~20 lines)
   - Fix perspective-provenance.md frontmatter (~1 line)
   - Add simple recovery section to plan skill (~10 lines)
3. **Resume E-221 as-is** (it's already well-scoped at 8 stories)
4. **Dispatch E-221 with the "and review" modifier** to exercise the CR invariant audit on the perspective-provenance invariant

---

## State of the Codebase Right Now

- **Main branch**: clean, at commit 1b3294c (E-216 archive)
- **E-220**: shipped at commit 24d2cd3, archived at `.project/archive/E-220-perspective-provenance/`
- **E-221**: DRAFT at `epics/E-221-perspective-residuals-and-fixture-audit/`, 8 stories, all TODO
- **E-222**: DRAFT at `epics/E-222-meta-fidelity-fix/`, 14 stories, all TODO, Codex found 10 findings during triage
- **Database**: reset to E-220 schema (fresh `001_initial_schema.sql`), health OK, no data loaded
- **Active team**: `meta-fidelity-plan` with PM (~60% headroom) and CA (~46% headroom)

## Files in This Epic Directory

- `epic.md` — the 14-story E-222 epic (DRAFT, likely to be scrapped or radically simplified)
- 14 story files (B-01 through E-01) — context-layer-only changes, all TODO
- `CONTEXT-DUMP.md` — this file

## Key Files for Recovery Assessment

- `/workspaces/baseball-crawl/.project/archive/E-220-perspective-provenance/epic.md` — full E-220 history with 8-round remediation arc
- `/workspaces/baseball-crawl/epics/E-221-perspective-residuals-and-fixture-audit/epic.md` — E-221 scope (3 bug fixes + fixture audit + CI guardrail)
- `/workspaces/baseball-crawl/.claude/agent-memory/product-manager/lessons-learned.md` — PM's 8 lessons from E-220
- `/workspaces/baseball-crawl/.claude/rules/perspective-provenance.md` — the invariant rule (check frontmatter coverage)
- `/workspaces/baseball-crawl/.claude/agents/code-reviewer.md` — CR agent def (where invariant audit mode would go)
- `/workspaces/baseball-crawl/.claude/agents/product-manager.md` — PM agent def (where echo-back would go)
- `/workspaces/baseball-crawl/.claude/skills/plan/SKILL.md` — plan skill (where recovery section would go)
- `/workspaces/baseball-crawl/.claude/skills/implement/SKILL.md` — implement skill (where invariant audit dispatch would go)
- `/workspaces/baseball-crawl/CLAUDE.md` — project conventions and core principle

## Verbatim User Mandate Quotes (from this session)

1. *"I would rather lose all of our planning progress to date than to let their behavior persist any longer."*
2. *"Their lack of fidelity is one of the primary reasons that these last two epics are failing."*
3. *"The fact that codex kept uncovering finding after finding because of HOW they reviewed was unacceptable. We have the CR agent for exactly this purpose. They need to get their shit together."*
4. *"just that this may take some sort of evolution of the team lead's handling of agents as well. And this really needs to also fix CR fidelity"*
5. *"I'm half tempted to reset to pre-E220 and replan/re-execute the provenance work."*

## The Researcher's PM Failure Forensics (5 Signals)

A researcher examined the failed PM's session log. Findings:

**Hypothesis ranking**: Instruction fatigue / prior-context anchoring (70% confidence), context exhaustion (20%), delivery failure (5%), prompt gap (5%).

**Smoking gun**: PM's spawn brief cached "decisions already made in E-220 round 7-8." That cached belief persisted through two relay messages (CA 7,075 bytes, DE+SE 19,743 bytes). PM's input token counts during processing were 1-6 per call (header-only reading). Relay bodies were present in the log — relays landed, PM just didn't read them.

**Five structural signals**:
1. Mandate reset protocol — cached beliefs must be invalidated structurally
2. Input acknowledgment — echo-back proves processing vs skimming
3. File-validation hook — block negative assertions when relays exist in log
4. Visible reasoning traces — surface parse of relay content in output
5. Proactive escalation — report blocker rather than silently waiting

**Delta re-audit**: A second researcher confirmed the failure was NOT hallucinated-send. Previous PM's delivery mechanism worked; failure was read-side (instruction fatigue).

## Main Session Self-Audit (Honest)

Six gaps the main session identified in its own handling:
1. No structural drift-detection on agent output (caught PM drift only by manual reading)
2. Late escalation on idle agents
3. Improvised recovery (no "PM is failing" runbook)
4. Confidence-based instructions substituted for forcing functions ("carry the mandate forward")
5. Peer-DM fallback triggered only after two failures (should have been default once unreliability established)
6. Relay confirmation format gap (PM re-sent content because "received" wasn't followed by "forwarding, do not re-send")

The honest truth: I let the urgency of the PM failure drive me into overengineering. The planning session with the fresh PM and CA went deep on structural guarantees when simpler fixes would have addressed the actual problems. The 14-story E-222 is a product of that urgency spiral, not clear thinking.
