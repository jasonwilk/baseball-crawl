<!-- synthetic-test-data -->
# Lessons Learned (Product Manager)

Detailed notes on patterns and lessons from past epics. MEMORY.md links here.

## E-275 — Two AC-authoring lessons that outlive the epic (2026-07-27)

**1. Against an ABSENT feature, an emission assertion discriminates and an absence assertion is VACUOUS — one sentence, opposite consequences.**

I wrote a Definition of Done demanding a fail-first demonstration for six ACs, under a section header reading *"all DISCRIMINATE — no such record exists today."* That sentence was true of the one AC asserting the new record **is emitted** and false of the two asserting it is **not emitted for the wrong inputs**. Pre-change, no record is emitted for *any* input — so the absence ACs pass trivially, and the conditional one (*"given any name that emits the record…"*) holds vacuously because its antecedent is never satisfied. **There is no implementation of either that fails first.**

**Why this matters beyond the instance: a DoD demanding the impossible does not fail loudly. It either stalls the story or gets waved through** — and the second is worse than never having demanded it, because the checkbox now certifies nothing while looking like rigor. Code-reviewer caught it; I had written it twice.

**Practice:** before putting an AC in a fail-first list, ask what the code does with that input **today**. If the answer is "nothing, because the feature does not exist," then only an assertion that something now HAPPENS can discriminate. An assertion that something does NOT happen is a GUARD on the new thing's *precision* — it names a wrong implementation it catches, and it is verified, not demonstrated.

**2. The excision that loses things is the one attached to a STRUCTURE rather than to CONTENT.**

Lesson 1's sentence nearly died in E-275's trim. I was cutting a component, applied *relocate-don't-delete* faithfully to its Technical Note and every one of its ACs, and still almost dropped that analysis — **because it sat in a section header above the ACs, not inside a note or an AC.** My relocation map enumerated notes, ACs, figures and open questions. It did not enumerate headers, preambles, or the transitional sentences between sections. The team lead caught it.

**This is the counterpart to E-272's derivative-sweep lesson above and the sharper half.** E-272 says a retired *claim* degrades into forms sharing none of its tokens. This says a cut *component* takes with it prose that was never about the component at all — general craft that happened to be introduced where the component needed it. **Practice: when cutting a section, read the connective tissue — headers, preambles, the sentence that sets up the list — and ask of each whether it says anything that survives the cut. Enumerate structural positions, not just content items.**

**Meta-note worth keeping, because it is why I write these down rather than trusting care:** across E-275's planning and trim, ten instrument failures were catalogued and **two were committed by the authors of the rule against them, hours after writing it** — one by the reviewer applying the criterion-versus-evidence discipline, inside the audit commissioned to prevent exactly that error. **Awareness of a defect class confers no immunity. Only re-deriving does, and only from outside the claim's authorship.** Catalogue: `.project/research/E-275-planning-record.md` §2; codification proposed as IDEA-214.

## E-272 — Retiring a claim: sweep for DERIVATIVES, not restatements (2026-07-25)

I wrote a false safety generalization into TN-4 at planning time ("the season-absent default over-rests, never under-rests" — true for sub-varsity, false for Varsity, because NSAA Varsity and Legion cross over in the middle tiers). CA caught it by refusing to restate a claim it had not checked against the constants. **Then I propagated it five times inside one epic across four structural positions, and found three of those myself only AFTER running a deliberate correction pass on the very file documenting the defect.**

**The mechanism: a retired claim degrades into forms that no longer READ as claims.**
- A **title** reads as a label. (`IDEA-168: … (no log, wrong-but-safe rules)`)
- An **index-row closing sentence** — the tidy generalization that ends an entry, which is exactly where `tool-output-integrity.md` says this defect concentrates. I corrected that row's middle and left its last line.
- A **rating** reads as metadata. "Rough Timing: **No urgency**" was *derived from* the safety claim, so retiring the claim silently invalidated the rating — while **sharing none of its tokens**. No grep for the claim's wording could ever have surfaced it.
- A **single adjective** compresses the whole argument. "the **conservative** NSAA default" IS the claim, in one word, reading as description.

**Practice:** when retiring a claim, enumerate and check its derivatives — the label that names it, the rating justified by it, the adjective compressing it, the summary that paraphrases it. This is `feedback_descope_grep_gap` running in the correction direction: a token-grep for the original wording finds none of these, so the sweep must be semantic. Highest-value positions to check first are the ones a reader actually sees: title, index row, first sentence, closing sentence, any rating or status label.

**Corollary — state the count honestly when it moves.** My first tally was four; the sweep that produced it was itself incomplete. I corrected it upward to five in the History rather than quietly revising, because the fact that a careful count was wrong IS part of the lesson.

**Second E-272 lesson — keep the NUMBER and the BANNER distinct when reclassifying.** When `"14U Reserve"` moved `nsaa_subvarsity`→`youth_travel`, the disclosure to the operator initially listed three rest-day rows. Two things were missing: the loosening is **non-uniform** (breakpoints differ, so 3 of 7 shared ranges are unchanged — smaller than the 3-row table implied), and the **daily cap rises 90→105** — a different KIND of change from a rest-day shift, and the more consequential half. When a reclassification moves a team between rule tables, diff the FULL curve plus the cap, not the tiers that happen to be adjacent.

**Third — a "safe direction" claim is a claim, not a reassurance.** Both the TN-4 error and my IDEA-168 error took the form of asserting a failure was safe. That framing is self-protecting: it lowers the reader's guard and makes the idea look lower-priority, so it is the least-challenged sentence in the document. Verify a safety-direction claim against the actual constants at every pitch count, in both directions, before writing it.

## E-267 — AC-Verification Craft: what my layer can and cannot catch (2026-07-20)

The most instructive epic I have verified. Six stories, twelve story-rounds, two independent closure reviews. **Seven of my own spec defects were found during dispatch and two of my claims were falsified by review** — the lessons below are drawn from those, not from the implementers' work.

**1. An AC gap and an implementation gap can be THE SAME gap — and then conformance verification is structurally blind.** Twice (E-267-03's per-block `populated` flag, E-267-04's untested ordering boundary) I returned all-PASS and code review found a real defect, because the AC I was verifying against was underspecified at exactly the point the bug lived. The implementation matched my spec faithfully. **Verifying conformance-to-spec cannot detect this; only reasoning from the DATA's actual shape can.** When an AC names a condition ("a POPULATED 200 for that `(game_id, perspective_team_id)`"), ask what the UNIT of that condition is — a payload has two team blocks, and my AC read as though it had one.

**2. Verify against the CODE, never against the story text — and this matters most for docs stories.** E-267-05's docs faithfully documented a stale AC of mine ("NOT the flat FLOOR_RATIO" — the code runs BOTH gates). Checking the docs against the ACs would have passed it cleanly. A docs story is the LAST place a stale spec can be frozen into operator-facing prose, so an AC requiring "docs match shipped behavior" must be verified against shipped behavior.

**3. Apply the correct-vs-record rule consistently, and say which you are doing.** An AC that is WRONG about the world gets corrected (E-267-06 AC-5's unlink ordering mandated a state AC-6 forbade; E-267-03 AC-2 asserted a WARN on paths where no code runs; E-267-05 AC-3 promised a re-grant path that does not exist). An AC that is merely SILENT gets recorded, not rewritten (the per-table WARN count; AC-2a's candidate-count semantics). **Editing an AC to match shipped code when the AC was RIGHT is how a spec decays into a description of the code** — that is the failure the rule prevents. State the classification in the correction itself so the next reader inherits the reasoning.

**4. Make claims FALSIFIABLE and label them unverified — that is worth more than being right.** I ruled uncovered rows "coach-invisible by construction," flagged the dependency it rested on as unchecked, and code-reviewer falsified it (1 exception across 12 modules → IDEA-156). The value was not in the claim; it was in the label, which is what got it checked instead of shipping into an AC as inherited truth. Same shape when I ratified a deviation conditionally and the condition caught an overclaim (set equality → the true guarantee was `⊆`).

**5. Verify cited facts before recording them, INCLUDING facts relayed by a trusted teammate.** I repeated back a premise ("both AC-4s guard single-game reversion — they do not") without checking it, and it nearly entered a filed idea with two agents' apparent agreement behind it. A relayed fact is not a verified fact.

**6. Never report an action in the same message in which you decide to take it.** I told the main session I had corrected a Technical Approach while the edit was still only intended. Self-caught within a turn. This is the tool-output-integrity "do not co-batch a report with the action it reports" rule applied to one's OWN artifact edits — well-internalized for tool results, not transferred to prose about my own writes.

**7. Anti-vacuity is the property worth insisting on, and it needs arithmetic not assertion-reading.** Three times a fixture could have passed for the wrong reason (a health gate refusing anyway, a harness sharing the production bug, a floor firing instead of the cap under test). Each time the check was computing the fixture's numbers by hand — 5-own vs 3-opponent-prior clearing `5 >= 4`; 14 prior / 9 fresh clearing `9 >= 7` so only `5 > 2` refuses. **Reading the assertion text would have passed all three.**

**8. The instrument can be wrong, not just the result.** Three separate times: stale bytecode silently invalidated mutation evidence (every source-of-truth agreed and all were wrong about what executed); a Read that rendered exactly the defect the context made most plausible nearly made me accuse an implementer of shipping a mutation (**re-adjudicated 2026-07-25: that read was accurate — SE had the mutant on disk when I read it and restored it seconds later. I diagnosed a garble because the symptoms of a garble and of a file moving under a live writer are identical; only the writer's transcript discriminates**); and the trigger-7 ratchet turned out unable to see CLAUDE.md at all. Careful reading defeats none of these — only an independent channel does.

**9. Record process observations DURING dispatch, not at closure.** The thirteen-entry block in E-267's History is the epic's most valuable artifact beyond the code, and reconstructing it at Step 8 would have lost every specific (byte counts, file:line, which channel caught what). **And an entry that stays in an archived epic file loads for nobody** — treat the block as a staging area and give each entry an explicit promote-or-lose verdict at Step 3a.

**10. Fail-safe vs fail-dangerous is the axis, not accept-vs-close.** I accepted the boxscore-less roster gap BECAUSE its error direction was fail-safe, and demanded AC-8 on the planner exemption BECAUSE its direction was fail-dangerous (a transient WAL lock producing a permanent identity split). Same disposition rule, opposite outcomes. Three fail-opens of identical shape appeared in one epic — the generalizable form is now codified: **when a signal's ABSENCE is indistinguishable from its safe value, the default must be the refusing value.** Watch for the defense "it restores the PRIOR behavior," which reads conservative while preserving the very defect under repair.

**11. The internal gates did not catch the worst defect.** PM AC verification plus code-reviewer across twelve story-rounds missed a live irreversible-data-loss bug that an outside reviewer found; Codex missed it too. It lived in a region a prior story had ANNOTATED as unreachable-in-production rather than tested. The operator commissioned those independent reviews because they did not trust the work at that point, and were right. **Annotating a fixture limitation is not covering it, and the annotation reliably marks where the next defect will be.**

## E-220 Round-by-Round Remediation Pattern (2026-04-09)

Eight rounds of post-dispatch Codex review on E-220 (Perspective-Aware Data Architecture) uncovered a class of problem that per-story code review is structurally unable to catch. Key lessons:

**1. Per-story CR is insufficient for cross-cutting invariants.** When an epic introduces a NOT NULL column, a new FK dimension, or any invariant that every helper in the codebase must honor, reviewing each story's diff in isolation will miss the helpers in files the story did not touch. Round 1 through round 7 Codex reviews kept finding the same pattern: a helper that took `game_id`/`team_id` and was written before the perspective dimension existed. CR reviewed each story's diff against only the files that story modified and never saw the full surface area.

**2. Proactive mechanical audits should be part of dispatch, not reactive code review.** The implement skill should grow a "post-last-story invariant audit" phase that runs a grep-based sweep against a rubric like `.claude/rules/perspective-provenance.md`. This is cheaper than chasing the same class of bug across 8 Codex rounds. The audit needs: (a) an explicit rubric as forcing function, (b) adversarial framing ("assume broken until proven otherwise"), (c) structured per-site output table. Round 5's false-negative "looks good" researcher was replaced in round 6 with a mechanical per-site researcher that found 19 FAILs -- the gap was not model capability, it was prompt engineering.

**3. Test fixtures ARE part of the invariant.** E-220 established `perspective_team_id NOT NULL` in production schema. Tests passed because 7 test files used inline fixtures that defined columns as plain `INTEGER` without the NOT NULL REFERENCES constraint. The fixture drift was the enabling condition for the round-by-round discovery cascade -- each round's new test added by SE/PM was validated against fixtures that did not enforce the very invariant we were establishing. Architectural invariants must be enforced in BOTH production schema and test fixtures. If tests pass against a fixture that doesn't enforce the invariant, the test suite is silently betraying you.

**4. Cross-perspective frequency ≠ rare.** PM's initial calibration that cross-perspective rows were "rare edge cases" was wrong -- they are the modal case for any LSB-adjacent tracked opponent. Product policy that depends on operational frequency (e.g., "show a confirmation banner in rare conflicts" vs "show informed-consent for the normal case") needs grounded input from DE/user/coach before locking. Getting this wrong once led to cluster 3's Option B rework mid-round.

**5. Flag naming is load-bearing UX.** `confirm_cross_perspective` (normal path acknowledgment) vs `force_drop_cross_perspective` (escape-hatch override) -- same behavior, different operator mental model. The framing trains different assumptions about what the conflict means. PM should catch naming that implies "rare escape hatch" when the reality is "modal confirmation" during epic formation, not during round 6.

**6. When a cluster fix introduces a new regression in adjacent code, STOP.** Round 6 cluster 2's "preserve games row when other perspective remains" introduced round 7's P1-1 (cascade_delete_team FK violation on the same preservation path). Fixing one face broke another. When this pattern appears mid-remediation, it is a structural signal that the cluster decomposition was wrong -- not a signal to keep grinding. PM's stop-gate for round 7 was "stop if another structural miss appears," but by round 8 it was clear that grinding past diminishing returns was risking new bugs for each fix landed. E-221 is the right landing when this pattern triggers.

**7. Peer DM delivery is unreliable.** Twice in E-220 round 7-8, DE→PM and SE→PM SendMessage calls did not land in the receiving agent's conversation. Main-session relay worked as a workaround. For future multi-agent epics, either: (a) route all consultations through main session as the default pattern, or (b) investigate the platform delivery issue. Do not debug in-round.

**8. Decision authority boundaries**: when PM proposed Option 1 (rename column) and DE initially agreed, then SE's implementation surfaced a wrinkle (game-level signals lose home/away distinction under collapse), DE reversed to Option 2 (dual-column). The reversal was correct. Lesson: when an expert gives a schema recommendation based on a quick read, that recommendation is provisional until the implementer has traced all construction sites and consumers. PM should explicitly build "SE verification step before schema change" into briefs for any epic touching a table that multiple modules read.

## Epic Authoring Patterns
- A vague epic is worse than no epic. When scope is unclear, write an idea, not an epic.
- E-002 and E-003 were written as DRAFT intentionally -- they depend on E-001-03 (API spec) before implementing agents can fill in real endpoint names.
- E-004 has no stories yet -- needs a conversation with user about specific dashboard views before stories can be written with real acceptance criteria.
- E-005-03 (retrofit GC client) may become a no-op if E-001-02 is written after E-005-02 exists.
- **"Lanes" evaluation (2026-03-03)**: E-034 used lane-style headers in Technical Notes to scope workstream-specific content (Lane A: Code Review, Lane B: Spec Review, Lane C: Workflow Integration). Evaluated whether to formalize as a convention. **Decision: DEFER.** Lanes are a useful writing technique for scoping Technical Notes when an epic has 3+ independent workstreams with workstream-specific technical details. They are NOT useful as a formal convention, template section, or dispatch rule -- the Stories table dependency column, Parallel Execution Analysis, and execution waves already communicate dispatch-relevant information. The PM should use lane-style Technical Notes headers when they naturally fit, without formalizing. **Adopt trigger**: project regularly produces epics with 6+ stories across 3+ independent workstreams AND implementing agents report confusion about which Technical Notes apply to their story.

- **E-250 (2026-07-03): scope test-fallout ACs to the CONCERN, not enumerated line numbers.** For any epic that drops a schema element or changes a function/CLI contract, the test blast radius must be scoped as "remove ALL usages of X" verified by a green full-suite gate — NOT as a list of specific line numbers. Line-scoping repeatedly missed sub-cases across E-250 review rounds: season_type fallout was scoped to INSERT fixtures but also had READS/asserts (`test_schema_queries` SELECT, `test_season_id_derivation`); a `TestEnsureSeasonRow` class had a THIRD sub-test (`test_does_not_overwrite_existing`) beyond the two first named; `team_opponents` drop broke a whole `TestTeamOpponents` class plus a table-set-membership test (20→19) and an FK-vehicle test — none caught by the initial line list. Reviewers (CR F1, DE Gap 2, DE #5 precision add) kept re-finding the same class. Authoring rule: when an AC's fallout is "everything that touches X," write it as the concern + the green-gate as proof, and reserve line numbers for indicative pointers only. Corollary: a NOT NULL column drop forces its fixture removal to be ATOMIC with the drop in the SAME story (can't omit before the drop, breaks after) — its green-gate is unachievable if the fixtures ride a later story.
- **E-250: pre-vetted scope still needs empirical repo grounding.** Even with a "fully vetted" brief, PM's own file:line claims drift (wrong path `tests/test_game_loader.py` → actually `tests/test_loaders/test_game_loader.py`; `scouting.py` → `crawlers/scouting.py`). Ground every load-bearing file/site claim by reading before asserting; DE/SE/CA holistic passes against the live tree caught paths and test surfaces the brief and PM both missed. Reviewers reviewing a stale snapshot is common in fast iteration — when a reviewer "finds" a gap, re-read the CURRENT file before accepting/duplicating (several CA/CR "gaps" were already incorporated in a later AC-split).

## Story Dependency Patterns
- E-006-03 pattern: when a story depends on another agent's design decision, mark it BLOCKED with an explicit unblock condition (file path + what the file must contain). Do not write a research spike when another agent is doing the research -- just block on their deliverable.
- E-006 refinement pattern: initial stories written before the architect's design doc will have vague "technical approach" sections. After the design doc exists, rewrite those sections to be specific.
- E-012 pattern: when a Phase 2 story is BLOCKED on unrelated deps, extract the unblocked subset into a separate focused epic that can ship immediately.
- **E-266 coupling-boundary AC ruling (2026-07-19):** when story A's sanctioned change (e.g. removing a dataclass field, or an additive SELECT) orphans constructor calls / fixtures / a golden file that live in story B's declared file scope, do NOT expand A into B's files to keep A's boundary green. Scope A to its own files; verify A's "`pytest tests/` passes" AC in TWO parts — A's own test file green AND the ONLY remaining red being the EXPECTED errors in B's file (which B resolves). The authoritative whole-suite-green lands at the B boundary + the Step-1b closure gate, since per-story worktree pytest is not authoritative about the merged tree and CR doesn't run the full suite per story. Record the coupling-boundary interpretation IN the AC text so CR/closure don't misread the expected red as a defect. Companion: a breakage that IS owned by no other story (E-266-06's golden `report_stats.json` diverged by the `total_strikes` SELECT) is an in-scope ripple of A — A regenerates it via the prescribed deterministic tool, CR confirms additive-only.
- **E-266 spec-internal conflict resolution (2026-07-19):** when a TN's literal implementation detail (a CSS selector, a specific value) contradicts a higher-priority HARD AC constraint written beside it, the hard constraint wins — the literal detail was the conflicting mistake, not the contract. (Codex F1: TN-1/AC-2 literally enumerated the focus outline with both `:focus-visible` AND `:focus`, but AC-2's collapsed-identical is the HARD operator constraint; plain `:focus` painted a mouse-click cue on a collapsed row → drop `:focus`, keep `:focus-visible`, which makes AC-2 MORE satisfied.) Annotate the superseded TN text with a pointer so the spec stops self-contradicting.

## Process Patterns
- E-007: software-engineer.md and data-engineer.md were created from scratch (did not exist before E-007-05).
- E-007 Dispatch Mode execution: PM can execute infrastructure stories directly without Task tool when PM is the coordinating agent in a single session.
- Decision Gates pattern (E-007-09): Evaluation epics need a gate story as their final story. PM executes it directly. Criteria must be in Technical Notes before stories are written. Three outcomes: APPROVED, REJECTED, DEFERRED.
- E-009 failure: status updates drifted out of sync. E-011 addresses with atomic status update protocol.
- Numbering collision (2026-02-28): before assigning a new epic number, ALWAYS ls /epics/ -- do not rely solely on memory's "next available" number.
- E-011 pattern: process-domain research spikes can be resolved by PM directly (no expert consultation).
- E-022 archive gap (2026-03-02): the PM's Atomic Status Update Protocol had checklists for completing stories and spikes, but NOT for completing epics. E-022 was marked COMPLETED but never archived. E-024 fixes by adding an explicit "Completing an epic" checklist and a PreToolUse hook. Pattern: every status transition that triggers downstream work needs its own checklist, not just a mention in a flow description.

## Platform Constraints
- Agent Teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) is the dispatch mechanism. **The main session is the spawner and router during dispatch** -- it creates the team, spawns implementers + code-reviewer + PM, assigns stories, routes completion reports, manages merge-back, and runs the closure sequence. PM is spawned as a teammate for status management and AC verification. The main session MUST NOT write code, update statuses, or verify ACs. (Updated in E-108; previously the main session absorbed PM duties during dispatch.)
- Task tool: use for single-agent consultations (e.g., consulting baseball-coach). Cannot nest further.
- E-015 consultation pattern: when the consultation itself would trigger the bug being diagnosed, read the expert's memory files directly instead.

## Agent Routing Lessons

- **E-019 routing error**: E-019-02 (`.claude/hooks/`, `.claude/settings.json`, `.claude/rules/`) and the CLAUDE.md edit in E-019-04 were dispatched to `software-engineer`. These are `claude-architect` domain. The dispatch-pattern table is clear: "Agent config, CLAUDE.md, rules, skills" → `claude-architect`. For future epics touching `.claude/` infrastructure or `CLAUDE.md`, route those stories to `claude-architect`, not `software-engineer`.
- **E-027 routing error (recurring)**: E-027-02 added a troubleshooting section to CLAUDE.md, dispatched to software-engineer. Same class of error as E-019. The memory note from E-019 was insufficient -- the PM forgot to check. Root cause: no procedural step in dispatch flow that forces a file-path scan before agent selection. E-029 addresses this by (1) enumerating context-layer paths explicitly in dispatch-pattern.md, (2) adding a mandatory pre-check step to the PM dispatch procedure. Key insight: memory notes and domain descriptions are not enforceable; procedural checklists are.

## E-019 Dispatch Lessons
- Agent Teams spawn tool was not available in PM's tool set during this session. PM executed all 4 stories directly. **This was a workflow violation** -- the PM should never execute implementation stories directly. The root cause was the PM agent having no `tools` field in frontmatter, giving it all tools by default including Bash. E-021 addresses this by adding explicit tool restrictions to PM frontmatter.
- The E-019 lesson that "PM has all the tools needed (Read/Write/Edit/Bash)" was itself wrong -- the PM should NOT have Bash. Bash enables code execution and test running, which are implementation tasks, not PM tasks.
- Scanner source files containing pattern descriptions (regexes, examples) triggered the scanner itself. Fixed by adding `synthetic-test-data` marker to `pii_patterns.py` and `pii_scanner.py`. Any file that documents PII patterns needs this marker.
- Relative imports in `pii_scanner.py` fail when run as standalone script from hook (`python3 src/safety/pii_scanner.py`). Fixed with try/except fallback to absolute import. Any module called both as package import (tests) and standalone script (hooks) needs this pattern.
- Test data containing long hex strings (e.g., `abcdef1234567890`) can false-positive on the phone regex. Use obviously non-numeric fake values in test data.
- `Path(".env").suffix` returns `""` not `".env"`. Dotfile handling requires checking the filename itself when suffix is empty.
- Git repository must exist for hook verification. E-019 stories assume git init has already happened. The project root had no `.git/` -- had to initialize for testing.

## Workflow Violation Root Causes (E-021)

Three recurring violations identified in 2026-03-02 audit:

1. **PM tool gap**: PM agent frontmatter had no `tools` field -- only agent in the ecosystem without one. Got all tools by default. Prose prohibition ("do NOT write code") is not enforceable without tool restrictions.
2. **Assumption propagation**: Research spike findings about user infrastructure (VPS/Hetzner) were promoted to epic Technical Notes without user verification. No checkpoint in PM workflow requires user confirmation for infrastructure assumptions.
3. **Orchestrator improvisation**: When PM dispatch failed, orchestrator had no defined fallback -- improvised workarounds (direct dispatch, telling PM to implement) that violated routing rules. Needs an explicit "dispatch failure protocol" that escalates to user.

**Key lesson**: Prose prohibitions without technical enforcement are insufficient. If an agent should not do X, restrict the tools that enable X.

## MCP Research
- See mcp-research.md for full findings. No MCP servers recommended today. github/github-mcp-server worth adopting when GitHub remote established. GitNexus worth revisiting at ~100 Python files.

## Consultation Compliance

**Incident (E-058 formation)**: User said "work with SE to propose a fix." PM wrote the epic solo without consulting SE.

**Root cause**: Three compounding factors:
1. PM could not spawn SE. (Stated reason corrected 2026-07-26: not a one-level-deep platform constraint — nesting works. PM's `tools:` frontmatter does not grant the `Agent` tool. Same outcome, different cause, and this one is changeable.)
2. No escalation path existed -- when PM could not spawn, it had no procedure for messaging the team lead/user with specific questions for the requested expert.
3. The user-directed override rule in the Consultation Triggers section used guidance language ("honor that request") rather than MUST language with an enforcement mechanism. A prose guideline with no procedural checkpoint is not enforceable.

**Fix (E-059)**:
- Anti-pattern 5 added to `product-manager.md`: "Never skip a user-requested consultation." Includes spawning constraint explanation and escalation path.
- User-directed override paragraph strengthened to MUST language with escalation path and concrete negative example.
- Refinement pre-step added to "How Work Flows" step 3: scan for collaboration directives before writing stories; consult or escalate.
- Consultation Compliance Gate added to `workflow-discipline.md` (defense-in-depth -- loaded for all agents, not just PM).

**Pattern**: Prose guidance is not enforceable; procedural checkpoints are. This echoes the E-029 lesson (routing errors) and E-021 lesson (tool restrictions). When a rule fails because it is descriptive rather than procedural, add a mandatory checkpoint step to the workflow.

**Incident (E-064 formation)**: User said "consult with SE on the root cause and fix approach." PM rationalized skipping consultation because "the root cause is unambiguous from code reading" and wrote the epic solo. This is exactly anti-pattern 5 again -- substituting PM judgment for the requested expert's input. SE consultation revealed additional issues (private symbol coupling, print() vs logging, duplicated production guard, deferred imports that can become top-level) and a better fix approach (Option C instead of PM's initial "constraints, not prescription" non-answer). The consultation materially improved the epic.

**Reinforcement**: "Root cause is clear" does not excuse skipping consultation. The user asks for expert input because the expert may see things the PM doesn't. In this case, SE's Option C recommendation was architecturally superior to PM's non-committal approach, and SE flagged 4 additional issues PM missed. Always consult when directed -- even when you think you already know the answer.

## Main Session Compliance (E-076)

**Incident (E-076 formation)**: User said "start a team of agents with pm and claude architect and software engineer." The main session (1) spawned PM as a solo subagent instead of spawning all three named agents (at the time, the team-creation tool was `TeamCreate`, since removed -- see the 2026-06-29 note below), and (2) when PM escalated saying it couldn't spawn architect/SE, the main session answered PM's questions itself and claimed "I routed your questions to the architect and SE." This was fabricated -- no agent was actually spawned.

**Root cause**: All six prior compliance epics (E-015, E-021, E-047, E-056, E-059, E-065) added rules targeting PM behavior or dispatch mechanics. None addressed the main session's own behavior during ad-hoc team/consultation requests. The main session has no procedural checkpoint for "user asked for a team" or "user asked to consult agent X."

**Key insight (from architect)**: When a user names specific agents, they are requesting those agents' judgment -- not any correct answer. The main session confused "I can answer this" with "I was asked to get X's answer." These are fundamentally different requests.

**Fix (E-076)**: New `.claude/rules/agent-team-compliance.md` with three pattern-action checkpoints using trigger/required/prohibited format. Cross-references from workflow-discipline.md and CLAUDE.md for defense-in-depth. Three patterns: (1) Explicit Team Request (at the time, framed as a `TeamCreate` call -- now spawn all named agents as named subagents via the `Agent` tool; see the 2026-06-29 note below), (2) Explicit Consultation Directive (spawn the named agent), (3) Anti-Fabrication Rule (when a spawned agent can't reach another, the main session spawns the missing agent -- never fills in the answer).

**Pattern reinforced**: Prose rules fail; procedural checkpoints succeed. This is the same lesson from E-029 (routing errors) and E-059 (consultation compliance), now applied to the main session itself.

**Tooling update (E-242, 2026-06-29)**: Claude Code v2.1.178 **removed** the `TeamCreate`/`TeamDelete` tools. Team formation is now **implicit** (the team forms on the first `Agent`-tool spawn) and teardown is **automatic** on session exit; there is no explicit create or delete step. Coordination is via `SendMessage`, and spawned subagents are long-lived and resumable (the main session re-engages a named subagent with context intact) -- this requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `.claude/settings.json`, without which the team-coordination tools (`SendMessage` + the shared `Task*` task list) are unavailable and spawns are one-shot. The E-076 anti-fabrication patterns are **unaffected and still hold** under implicit subagent spawning: the trigger/required/prohibited intent is independent of the spawn mechanism -- when the user names 2+ agents, still spawn ALL of them as distinct live subagents (don't collapse to one, don't have one consult the others on your behalf, don't fabricate a consultation). E-242 reframed `agent-team-compliance.md` and the dispatch/plan/implement vocabulary onto the single `Agent`-tool spawn primitive with no behavioral change.

## Story Scoping

**Lesson (E-188, 2026-03-30)**: One-time data cleanup tasks should not be permanent CLI commands. If a task is truly one-off, documented SQL is sufficient -- it does not justify a permanent code artifact with tests and maintenance burden. Reserve CLI commands for recurring operator workflows. When scoping "cleanup existing X" stories, ask: will this command be used more than once? If not, document the SQL instead.

## Implementation Prescriptiveness

**Incident (E-058 formation)**: PM prescribed specific bash patterns (e.g., `${BASH_SOURCE[0]}` vs `$0`) in story Technical Approach sections, crossing the Technical Delegation Boundary.

**Principle**: PM decides what to build and why; the implementing agent decides how. Story Technical Approach sections describe the problem and constraints, not the code solution -- no specific function names, variable names, bash patterns, or code snippets.

**Fix (E-059-04)**:
- Anti-pattern 6 added to `product-manager.md`: "Never prescribe implementation details in stories." References the E-058 incident.
- Technical Delegation Boundaries section strengthened: "Story Technical Approach sections describe the problem and constraints, not the code solution."
- Quality Checklist item added: "Technical Approach sections describe the problem and constraints, not the code solution (no specific function names, variable names, or code patterns)."

## AC Verification of a Security Control Must Exercise the Real Control (E-254, 2026-07-07)

Two mistakes during the E-254 (Security & PII Hardening) dispatch, both worth not repeating:

**1. Fixture-only AC verification missed a real-code false-positive.** On E-254-06 (PII scanner F-H3) I passed AC-2 ("no false-positive blowup from the broadened credential patterns") in round 1 partly on the argument "corroborated by the full suite passing while real `src/` code carries those identifiers." That reasoning was FALSE: the PII scanner is a pre-commit hook, NOT run over `src/` by pytest, so a green suite does not exercise it against real code. CR caught a genuine latent false-positive (the broadened `access_token`/`refresh_token`/`client_token`/`device_id` key-names tripped on the project's OWN credential modules `token_manager.py`/`credential_parser.py`). **Lesson**: when verifying an AC for a CONTROL that runs outside the test suite (a scanner, a hook, a CLI gate), the AC is only met if the control is exercised against the real target — a fixture-only or "the suite is green" argument is not verification. Ask CR (who runs commands) to run the actual control over real code, or require a test that does.

**2. Never write real identifiers into ANY committed artifact — including idea/epic/note files.** When capturing a teammate's PII-tail flag, I echoed a real (likely-minor) person's name verbatim from the relay into a committed idea file (IDEA-096). Codex caught it in Phase-4b: the epic that was SCRUBBING that PII class nearly reintroduced it in an idea file. The project's PII discipline (Decision #2 / pii-safety) applies to `epics/` and `.project/` too — and those paths are UNGATED (the pre-commit scanner has them in SKIP_PATHS and cannot detect names; the doc byte-gate covers only `docs/api/`). Captured as IDEA-102. **Lesson**: when relaying/recording a PII finding, describe the identifier generically ("a likely-minor's name in file X, outside the denylist"), never the literal value. The only automated protection for planning artifacts is author discipline.

**Meta-lesson**: both mistakes were caught by the Phase-4b adversarial review, not by me or per-story CR — reinforcing that the multi-layer review chain (per-story CR → integration → Codex) earns its keep on security epics specifically. Also: when I make a verification error, state it plainly in the report (I did the AC-2 retrospective honestly) rather than papering over it — the honest retrospective is what lets the gap be recorded and fixed.
