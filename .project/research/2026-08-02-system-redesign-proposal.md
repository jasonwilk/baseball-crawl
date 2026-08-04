# System Redesign Proposal: From Choreography to Rails

**Date**: 2026-08-02 (amended same day after Codex adversarial review — see §10)
**Author**: fresh-eyes agent (clean context, re-derived from vendor sources + repo evidence)
**Status**: PROPOSAL — nothing in this file has been executed. This file may outlive the decision.

---

## 0. TL;DR

Delete the workflow machinery (dispatch/plan/implement choreography, 7 of 9 agent roles,
the always-on process rules); keep the domain knowledge (path-scoped rules, hooks, the two
agents that know things about baseball and the GameChanger API); replace the epic/story
apparatus with one-page spec files and Claude Code's built-in lifecycle: **plan mode →
spec → fresh session executes → tests → `/code-review`**, with the existing codex-review
skill kept as an operator-invoked second opinion. The main session's
"single-agent-with-subagents-as-tools" proposal is **adopted with two amendments** (§4).
Always-on context drops from ~88KB of process prose to roughly one page plus facts. Step 0
is executable tomorrow morning: two one-file enabling commits, then a real pilot chunk.

---

## 1. What the vendor actually says (fetched 2026-08-02)

### Fetch log (honesty first)

| Source | Status |
|---|---|
| platform.claude.com …/prompting-claude-fable-5 | fetched in full |
| platform.claude.com …/prompting-claude-opus-5 | fetched in full |
| platform.claude.com …/claude-prompting-best-practices | fetched in full (57.6KB, read to end) |
| anthropic.com/engineering/effective-context-engineering-for-ai-agents | fetched (summary). The claude.com/blog URL 404'd; this is the canonical location, found via search |
| code.claude.com/docs/en/sub-agents | fetched (92.7KB; first ~600 lines read — built-ins, frontmatter, tools, memory, permission sections) |
| code.claude.com/docs/en/skills | fetched (72KB; first ~500 lines read — bundled skills, locations, frontmatter, lifecycle) |
| code.claude.com/docs/en/commands (built-in commands + bundled skills) | fetched (summary) |
| code.claude.com/docs/en/best-practices | fetched in full |
| code.claude.com/docs/en/agent-teams | fetched in full |
| code.claude.com/docs/en/hooks-guide | fetched; **preview only skimmed** — the one load-bearing line is quoted below, but I did not read this page to completion |

### The load-bearing findings

**On prescriptive scaffolding (Fable 5 page, verbatim):**
> "Skills developed for prior models are often too prescriptive for Claude Fable 5 and can
> degrade output quality. Review and consider removing older instructions if default
> performance is better." … "Instruction-following is improved enough that you can steer
> most behaviors with a brief instruction rather than enumerating each behavior by name."

**On over-verification (Opus 5 page, verbatim):**
> "If your prompt contains explicit verification instructions … remove them: instructions
> like these cause over-verification on Claude Opus 5, and removing them reduces wasted
> tokens with no loss in quality."

**On CLAUDE.md (Claude Code best-practices page, verbatim):**
> "For each line, ask: 'Would removing this cause Claude to make mistakes?' If not, cut it.
> Bloated CLAUDE.md files cause Claude to ignore your actual instructions!" Named failure
> pattern: "The over-specified CLAUDE.md … Ruthlessly prune. If Claude already does
> something correctly without the instruction, delete it or convert it to a hook."

**On agent teams vs a single session (agent-teams page, verbatim):**
> "Agent teams are experimental and disabled by default." "Agent teams add coordination
> overhead and use significantly more tokens than a single session. … For sequential
> tasks, same-file edits, or work with many dependencies, a single session or subagents
> are more effective."

This repo's dispatch was serial story execution in one shared worktree with heavy
same-file editing — the exact case the vendor names as wrong for teams.

**On context** (context-engineering article): find "the smallest possible set of
high-signal tokens"; system prompts at the "right altitude" (neither brittle hardcoded
logic nor vague platitudes); prefer just-in-time retrieval over pre-loading; sub-agents
exist to return "condensed, distilled summary" results, not to be an org chart.
**On hooks**: "Use hooks for actions that must happen every time with zero exceptions" —
deterministic where instructions are advisory; this validates the one current layer that
demonstrably works. **On review**: the recommended adversarial step is the bundled
`/code-review` skill, with the warning "a reviewer prompted to find gaps will usually
report some … chasing every finding leads to over-engineering" — which describes E-279
(below) precisely.

**Built-ins this repo is reinventing** (commands reference, fetched today):

| Built-in | Home-grown equivalent it replaces |
|---|---|
| `/code-review` (bundled skill; effort levels, `--fix`, `ultra` = multi-agent cloud review) | code-reviewer agent (60.5KB) + the per-story freeze/verdict loop |
| `/security-review`, `/review <pr#>`, `/simplify` | (nothing — pure gains) |
| `/verify`, `/run`, `/run-skill-generator` | ad-hoc "rebuild and health-check" instructions |
| Plan mode + built-in `Plan`/`Explore` subagents | plan skill (48KB) discovery phases |
| `/compact`, `/clear`, `/context`, `/rewind`, checkpoints | context-fundamentals + filesystem-context skills (29.7KB) |
| Auto memory + `memory:` frontmatter on subagents | much of the agent-memory ceremony |
| `/init`, `/memory`, `/doctor`, `/batch`, `/goal` | assorted |

One footgun worth recording: a **project skill named `code-review` silently replaces the
bundled `/code-review`** (skills doc). Our Codex skill is named `codex-review`, so there
is no collision — keep it that way.

---

## 2. What the current system is, and what it measurably cost

### Inventory (measured this session)

| Layer | Size | Notes |
|---|---|---|
| CLAUDE.md | 20.2KB | loads every session, every agent |
| `.claude/rules/` | 35 files, **309KB** | 7 files load on **every** interaction (`paths: "**"`): tool-output-integrity 24.9KB, dispatch-pattern 12.5KB, workflow-discipline 12.1KB, worktree-isolation 7.3KB, agent-routing 6.1KB, agent-team-compliance 3.6KB, vision-signals 1.1KB ≈ **67.6KB always-on** before a single file is touched |
| `.claude/skills/` | 10 skills, ~258KB | implement/SKILL.md alone is **118KB**; plan 48KB |
| `.claude/agents/` | 9 definitions, 195KB | code-reviewer 60.5KB, product-manager 34KB |
| `.claude/hooks/` | 8 scripts | 6 wired in settings.json; small and mechanical |

So a spawned implementer paid ~88KB of CLAUDE.md + universal rules before reading any code,
and a dispatch loaded the 118KB implement skill on top.

### Cost record (E-280 epic, archived; TN-1/TN-2/TN-3 quoted from the epic file)

- Throughput: **1.49 stories/active-hour** (Jul 06–12, Opus 4.8) → **0.49** (Jul 24–29).
- Per-turn pace role-matched: **flat**. The model did not get slower.
- The replication's bridge control shows Opus 5 at **parity or slightly better**; "the
  per-story cost doubled entirely within the Opus 4.8 era." **Process, not model.**
- Audit/meta share of active hours: **~3% → ~35%**.
- `.claude/rules/` grew 165KB (6/27) → 307KB (7/29); median end-of-session main-agent
  context grew **391k → 554k tokens** over the same window.
- E-279 decomposition: 1.00 h/story of which **66% was review and verification**; one story
  was 14 minutes of implementation against a **94-minute verification tail** with 8
  reviewer verdicts; **106 sends/story**; 891k output tokens for a 5-story epic whose
  stories were all shell/markdown/memory edits.

The diagnosis: an economy of verdicts, relays, and delivery confirmations; then rules about
that economy's failure modes; then audits of those rules. Every layer locally rigorous; the
stack is the pathology. E-280's trims helped ~2.4x, but trimming concedes the apparatus.
**What earned its keep:** the hooks (mechanical, cheap, deterministic — exactly what the
vendor says hooks are for), the path-scoped domain rules (they ARE just-in-time retrieval),
the ideas directory, and the domain knowledge inside api-scout and baseball-coach.

---

## 3. Design principles for the replacement

1. **Mechanical rails, model judgment inside them.** Hooks and tests are the rails.
   Everything currently enforced by prose (gates, verdict protocols, "MUST NOT") either
   becomes a hook, a test, or gets deleted.
2. **Built-in over home-grown.** Where Anthropic ships the thing, use theirs, delete ours.
3. **Facts persist; procedures don't.** CLAUDE.md and rules carry facts Claude can't infer
   from code (destructive seams, API gotchas, commands). Procedures live in per-chunk
   specs or in the model's judgment.
4. **The unit of work is a session-sized chunk**, and state between sessions lives in a
   spec file on disk — not in a long conversation, not in a relay between agents.
5. **One verdict per check.** A review runs once, in a fresh context, when the operator
   asks. No standing verification economy.

---

## 4. Verdict on "single agent with subagents as tools"

**Adopt, with two amendments.** The vendor evidence is squarely for it: teams are
experimental, cost more, and are recommended only for genuinely parallel independent work;
this repo's work is sequential and same-file. The local evidence agrees: 106 sends/story
and a 66% verification share were coordination costs, not work.

The honest counterpoint: the Fable 5 page praises parallel subagents and says "separate,
fresh-context verifier subagents tend to outperform self-critique." That is not an
argument for the old dispatch — it is the argument for the two amendments:

- **Amendment 1 — keep two domain subagents, not zero.** `api-scout` and `baseball-coach`
  hold real knowledge (API archaeology, coaching semantics) that benefits from persona +
  project-scoped memory (`memory: project`). Both trimmed hard. Everything else
  (SE/DE/docs/UX/PM/CA/CR roles) is the main session or a built-in subagent.
- **Amendment 2 — fresh-context verification survives as `/code-review`, operator-invoked,
  once per chunk.** The vendor's own reconciliation of "fresh verifiers beat self-critique"
  with "don't build a verification economy": one bundled skill, forked subagent, one pass,
  findings filtered by judgment. Codex stays as the independent second opinion.

Also delete `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` from settings.json. If a genuinely
parallel task appears (competing debugging hypotheses, multi-lens review of a big PR),
teams can be re-enabled for that session in one line — run-first, not a standing capability.

---

## 5. The new lifecycle (what the operator actually types)

**Small task** (you could describe the diff in one sentence): just type it. Claude
implements, runs the affected tests, shows the result. No spec, no ceremony. This retires
"small UI changes still need epics" — the epic was load-bearing because ad-hoc work had no
review step; now `/code-review` is the review step.

**Feature chunk:**

```
1. PLAN      claude (fresh session), Shift+Tab into plan mode:
             "I want X. Interview me about the hard parts, then write
              .project/specs/2026-08-03-x.md"
             → spec ≤ 1 page: goal, files/seams touched, out of scope,
               verification command, empty ## Progress log.
             Optional for big/destructive chunks: "spec review" (codex-spec-review,
             after its Step 3 rewrite — today it parses only epics/ directories).

2. EXECUTE   /clear (or new session):
             "Implement .project/specs/2026-08-03-x.md. Run the verification it names."
             Hooks guard PII/secrets mechanically. Checkpoints and /rewind are the undo.

3. TEST      the spec names the chunk's verification command (/verify or bb checks for
             serving-surface changes). Any chunk touching src/, tests/, or migrations/
             also ends with the FULL suite green (python -m pytest tests/) before
             commit — the old Full-Suite-Green closure gate, carried forward.

4. REVIEW    /code-review            → fix findings that affect correctness; skip the rest
             /security-review        → when the chunk touched auth, serving, or PII surfaces
             "codex review"          → second opinion, operator-invoked, when wanted
             /simplify               → optional quality pass

5. COMMIT    Operator approves the commit (existing preference stands). The pii-hook
             success line check stays.
```

**Session hygiene (what a chunk is):** a chunk is what one session finishes comfortably —
roughly single-digit files and one verification command. Leave a session at a boundary,
not at exhaustion: when the statusline context bar goes yellow (~70%), or after two failed
corrections on the same issue (vendor rule), write two lines into the spec's `## Progress`
(done / next / surprises), `/clear`, and resume from the spec in a fresh session. Prefer
fresh-session-from-spec over compaction (vendor: models "are extremely effective at
discovering state from the local filesystem"). The spec is the state carrier.

**Specs replace epics.** One markdown file per chunk in `.project/specs/`, ≤ a page, with a
`Status:` line; done specs move to `.project/specs/done/`. `.project/specs/` is scanned by
the PII gate (Step 0's scanner fix — today `.project/` sits in `SKIP_PATHS`, a documented
gap with a prior real-name incident, IDEA-102), and the spec template opens with "no real
names — placeholder taxonomy per `.claude/rules/api-docs.md`". The ideas directory stays.
No stories, no READY gates, no status ownership — the operator's queue is the specs
directory. In-flight epics (Epic B tail, E-274/E-275) finish or convert; nothing new
enters `epics/`.

**Lessons go to memory, not to new rules.** Auto-memory and the two kept agents' memory
dirs absorb what the 8-trigger assessment used to force into rules. A lesson becomes a
rule line only after it has bitten twice. Prune on `/doctor` runs, not via a gate.

---

## 6. Disposition table

### CLAUDE.md — REWRITE to ~1 page + pointers
Keep: project purpose (3 sentences), the two destructive-action boundaries (`bb report
generate` deletes; `bb db purge-scouting` flags), the ingestion-fidelity north star (1
paragraph), tech stack line, GC API gotchas (the 5 bullets), commands pointer, security
rules, git conventions incl. the pii-hook line. Delete: Workflows section, Agent Ecosystem
table, dispatch references, the strategic-frame essay (pointer to ROADMAP/VISION
suffices). Target ≤ 6KB.

### Rules — the seven always-on files are the problem; the path-scoped ones are the model
| File | Disposition | What we lose |
|---|---|---|
| dispatch-pattern.md (12.5KB, `**`) | **DELETE** | The dispatch role model and its lessons. Acceptable: the thing it governs is gone. |
| agent-routing.md (6.1KB, `**`) | **DELETE** | Routing table for deleted roles; model-escalation notes (fold one line into memory). |
| agent-team-compliance.md (3.6KB, `**`) | **DELETE** | Guarantees around explicit agent-naming. If the operator names api-scout/coach, the harness spawns them anyway. |
| workflow-discipline.md (12.1KB, `**`) | **DELETE** | READY/authorization/consultation gates — epic-machinery. Its Full-Suite-Green closure gate is NOT lost: it moves into the lifecycle (§5 step 3). |
| worktree-isolation.md (7.3KB, `**`) | **DELETE** | Worktree constraints for a dispatch model that no longer exists. |
| tool-output-integrity.md (24.9KB, `**`) | **REPLACE** with `tool-discipline.md`, ≤ 15 lines | The full pathology catalogue. Keep only what bites outside dispatch: grep finds candidates / only a Read rules; an unexpected count is a cross-check trigger; the garbled-vs-moved differential (harness flakiness is real, documented in E-231); prose you write about code is a claim to verify. The rest documented one system's failure modes and dies with it. |
| vision-signals.md (1.1KB, `**`) | **KEEP** | — |
| doc-sweep.md (9.3KB) | **DELETE**; fold "token grep + synonyms + read" into tool-discipline.md as one line | The retired-claims taxonomy. Real loss, small: it mostly governed sweeping the process prose we are deleting. |
| context-layer-assessment.md (12.3KB), context-layer-guard.md (4.6KB), project-management.md (2.4KB) | **DELETE** (Step 1; spec conventions = 5 lines in the spec template) | The closure gates and epic templates. |
| documentation.md (2.4KB) | **TRIM** to ownership table + staleness convention | PM's mandatory doc assessment. |
| ideas-workflow.md (3.7KB) | **KEEP** (trim the numbering ceremony) | — |
| **All 22 path-scoped domain rules** (canonical-seams, data-model, testing, key-metrics, gc-uuid-bridge, http-discipline, auth-module, pii-safety, proxy-boundary, migrations, api-docs, pitch-rules, perspective-provenance, architecture-subsystems, display-philosophy, admin-ui, app-troubleshooting, devcontainer, dependency-management, browser-render-testing, jinja-safety, python-style) | **KEEP** — this is just-in-time context done right | Not "untouched": several reference deleted roles/files (ideas-workflow → PM; gc-uuid-bridge → PM; testing.md → tool-output-integrity; devcontainer.md → code-reviewer). Each deleting commit's reference sweep (§7) scrubs these. Second-pass trim later for canonical-seams 26.7KB, data-model 31.7KB, testing 15.5KB. |

### Skills
| Skill | Disposition | What we lose |
|---|---|---|
| implement (118KB) | **DELETE** | The entire dispatch procedure: freeze/verdict loop, staging boundary, closure sequence, remediation circuit breakers. This is the point. |
| plan (48KB) | **DELETE** — plan mode + interview→spec replaces it | Team-based discovery, automatic spec-review chaining, READY gate. Codex spec review survives as an operator-invoked skill. |
| codex-review (22.8KB) | **KEEP** (operator requirement) — but it is NOT standalone today: its script **fails closed without `.claude/agents/code-reviewer.md`**, and the skill cites workflow-discipline.md, agent-routing.md, and the CLAUDE.md Agent Ecosystem table. Step 2 single-sources those needs INTO the skill (checklist copied into its directory, triage rewritten to "main session fixes real findings") before those files are deleted. Ensure `disable-model-invocation: true`. | — |
| codex-spec-review (10.7KB) | **KEEP, rewritten at Step 3**: today it resolves only `epics/` directories (requires `epic.md`) and routes triage through PM, so it cannot read the new spec files until rewritten. | — |
| ingest-endpoint (18.1KB) | **KEEP** — real, time-sensitive domain workflow. Step 2 rewrites its phase-2 to hand findings to the main session instead of the deleted claude-architect. | — |
| workflow-help (3.1KB) | **REPLACE** — regenerate a one-page cheat sheet after migration | — |
| agent-standards (4.6KB) | **DELETE** | Agent-design methodology for an ecosystem that shrinks to two. |
| context-fundamentals (16.5KB), filesystem-context (13.2KB), multi-agent-patterns (3.5KB) | **DELETE** — home-grown restatements of vendor docs, the exact "too prescriptive for this model generation" case | A few local observations; anything that bit twice goes to memory. |

### Agents
| Agent | Disposition | What we lose |
|---|---|---|
| code-reviewer (60.5KB) | **DELETE** → bundled `/code-review` + codex-review (after Step 2 single-sources what codex-review reads from this file) | The repo-tuned adversarial checklist and the every-story guarantee. Mitigation: `/code-review` runs as a fork and inherits session context including path rules; the destructive-seam facts live in CLAUDE.md and canonical-seams.md, which is where they belong. |
| product-manager (34KB) | **DELETE** | Status ownership, epic stewardship, curate-mode persona. The operator is the PM of a solo repo; vision curation becomes "read vision-signals.md together in a session." |
| claude-architect (13.4KB) | **DELETE** | A steward for a layer that will be ~10 small files. Main session edits `.claude/` directly. |
| software-engineer (16.9KB), data-engineer (16.3KB), docs-writer (12.8KB), ux-designer (14.9KB) | **DELETE** | Role personas. The main session does the work; Explore/general-purpose handle delegation. |
| api-scout (15KB) | **KEEP**, trim to ≤ 5KB, add `memory: project` | — |
| baseball-coach (10.8KB) | **KEEP**, trim to ≤ 5KB, add `memory: project` | — |
| agent-memory of deleted agents | **ARCHIVE** to `.project/archive/agent-memory/` | Nothing loads it once the agents are gone; archiving keeps it greppable. |

### Hooks (the part that earned its keep)
| Hook | Disposition |
|---|---|
| pii-check.sh, secret-read-guard.sh | **KEEP** — exactly what hooks are for |
| edit-verify.sh | **KEEP** — cheap PostToolUse readback against real, documented transport flakiness |
| statusline.sh | **KEEP** — the context bar is the chunk-boundary instrument |
| worktree-guard.sh | **REPLACE at Step 0** with a ~20-line write-safety guard: keep the `..`-segment denial (worktree-guard.sh:92) and outside-repo write denial; drop dispatch mode and the implementation-path denylist. It is a write barrier and path-traversal control, not a cleanliness preference — and as wired today it blocks the Step 0 pilot's `src/` writes, so the swap is the migration's first move. |
| epic-archive-check.sh | **DELETE** (epic machinery) |
| context-ratchet.sh | **DELETE** — the gate was already retired by operator ruling; `/context` and `wc` cover the diagnostic |
| dispatch-telemetry.py | **DELETE** |
| settings.json | Edit: remove deleted hooks; **remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`** |

---

## 7. Migration — small reversible steps, one commit each

Standing rule for every deleting commit: end it with a **reference sweep** — grep the
deleted file/role names across the kept layer (rules, skills, CLAUDE.md) and scrub or
reword each hit. Kept files reference deleted ones today (§6, rules table).

**Step 0 — tomorrow morning, ~1 hour. Two one-file enabling commits, then the pilot.**
(a) Swap `worktree-guard.sh`'s body for the ~20-line write-safety guard (§6, hooks table) —
without this, the still-wired hook denies the main-checkout `src/` writes the pilot needs.
(b) Narrow the scanner's `SKIP_PATHS` (`src/safety/pii_patterns.py:164-168`): replace the
blanket `".project/"` entry with the legacy subdirs (`archive/`, `ideas/`, `templates/`,
`research/`) so `.project/specs/` is scanned; run the scanner's tests. Both are
operator-approved and `git revert`-able. Then pick one real pending chunk (an Epic B
slice) and run the new loop end to end: plan-mode interview → spec → `/clear` → implement
→ tests → `/code-review` → commit, avoiding the old trigger phrases ("plan"/"implement
E-NNN" still load the old skills). Revert = revert (a) and (b); the pilot's own commit is
ordinary product work with its own revert — it is not "nothing to revert."

**Step 1 — kill the always-on load.**
One commit: `git rm` dispatch-pattern, agent-routing, agent-team-compliance,
workflow-discipline, worktree-isolation, doc-sweep, project-management,
context-layer-assessment, context-layer-guard; write the ≤15-line `tool-discipline.md`
replacing tool-output-integrity; rewrite CLAUDE.md to the one-pager; remove the
team-experiment env var from settings.json. Highest-value single commit (~95KB off every
interaction). Revert = `git revert`.

**Step 2 — retire the choreography.**
One commit: FIRST single-source codex-review (copy the checklist/config it reads from
code-reviewer.md into the skill's own directory; strip its references to the deleted
layer) and rewrite ingest-endpoint phase-2 (findings go to the main session); THEN delete
the implement, plan, agent-standards, context-fundamentals, filesystem-context,
multi-agent-patterns skills and the 7 agent definitions; archive their agent-memory;
delete epic-archive-check, context-ratchet, dispatch-telemetry and edit settings.json;
regenerate workflow-help; trim api-scout and baseball-coach, adding `memory: project`.

**Step 3 — specs live.**
Create `.project/specs/` with a ≤30-line template (goal / files / out of scope /
verification / progress; first line: no real names — placeholder taxonomy per
api-docs.md). Rewrite codex-spec-review's input resolution to take a spec file path.
New work enters as specs; `epics/` is frozen. Trim documentation.md and ideas-workflow.md.

**Step 4 — week two, after ~3 real chunks.**
Second-pass trim of the keeper rules (canonical-seams, data-model, testing) against
"would removing this line cause a mistake?"; run `/doctor`; regenerate the cheat sheet
from what actually got used. Adjust anything Step 0–3 got wrong — this is the run-first
feedback loop, not a formality.

---

## 8. What we lose — stated plainly

1. **The every-story adversarial gate.** Review becomes operator-invoked; if you don't run
   `/code-review`, nothing reviews. E-279 measured the old gate at 8 verdicts and a
   94-minute tail on a 14-minute story, and the vendor's caveat ("chasing every finding
   leads to over-engineering") says it was miscalibrated, not just expensive.
2. **The epic/story audit trail.** Specs + git history are lighter and less structured.
   "Which story introduced X" becomes "which commit/spec."
3. **Status and process ownership.** No PM guaranteeing gates fire. The operator's
   discipline replaces the state machine — including remembering to run the full suite
   and `/code-review`; nothing fires them automatically now.
4. **The tool-output-integrity catalogue**, reduced to 15 lines. Most of it described
   inter-agent relay pathology that cannot occur without inter-agent relays; the recurring
   part (harness flakiness, grep narrowing) is what the 15 lines keep.
5. **Most of worktree-guard.** It was a mechanical write barrier with path-traversal
   denial, not a cleanliness preference. The simplified guard keeps the path-safety core;
   genuinely lost is the structural bar on main-checkout implementation writes.
   Checkpoints, `/rewind`, and git are the recovery story.
6. **Automated closure assessments** (documentation gate, 8-trigger context-layer gate,
   deletion-side eviction sweeps). Replaced by memory + the per-commit reference sweep +
   a periodic `/doctor`/trim habit — strictly weaker, deliberately so.

Kept, worth saying: the hooks, the PII discipline (**extended** to specs by Step 0(b)),
the full-suite-green gate (now a lifecycle rule, §5 step 3), the domain rules and ideas
pipeline (kept with a reference scrub — not untouched), Codex review, the vision
documents, and the ingestion-fidelity north star.

---

## 9. Why this isn't another constitution

The whole standing agreement fits on a page, below. Everything else is a fact file
(loaded by path, priced individually), a mechanical rail (hooks, tests), or a disposable
per-chunk artifact (spec). The old system couldn't fit on a page because it encoded
*procedure* as standing prose; the replacement leaves procedure to the model inside rails,
which is what the current model generation is documented to want.

### Appendix: the one-page operating agreement (draft)

```
HOW WORK GETS DONE HERE

CHUNK LIFECYCLE -- every chunk walks these steps, and the session states
its current step whenever it reports. Small change (one-sentence diff):
just ask; skip to step 4 with "small change: no spec".
  1 SPEC         plan mode → interview → .project/specs/<date>-<slug>.md
                 (≤1 page: goal, files, out-of-scope, verification
                 commands, progress log; person names never appear)
  2 SPEC-REVIEW  codex spec review (mandatory when big or destructive)
  3 EXECUTE      FRESH session, from the spec. A spec is a CLAIM -- audit
                 it against the repo before building on it. The spec, not
                 the chat, carries state. Leave at boundaries: context bar
                 yellow or two failed corrections → update progress log,
                 step 9.
  4 VERIFY       the spec's named commands; code chunks (src/tests/
                 migrations) need the FULL suite green. No green, no done.
  5 REVIEW       /code-review; add /security-review on auth/serving/PII/
                 deletes; /simplify optional, always BEFORE /code-review
                 (its fixes need reviewing too); codex review as a second
                 opinion on request. Docs-only chunks: PII gates alone.
  6 SCAN         PII-scan the staged diff (python3 src/safety/
                 pii_scanner.py --staged); compare scanned-count to
                 staged-count -- SKIP_PATHS blinds the scanner to whole
                 trees (.claude/ among them); skipped staged files get a
                 manual pass with a positive control.
  7 APPROVE      operator reads the staged diff. Stage by explicit PATH,
                 never add -A; re-diff after staging.
  8 COMMIT       the [pii-hook] line is the receipt, not the first check.
  9 HANDOFF      flip the spec's Status line BEFORE staging, so it rides
                 the chunk's own commit: "COMPLETE (this commit)" or
                 "PARKED + why" -- no hash needed, git log on the spec
                 file supplies it. Only post-commit steps (a backfill, a
                 migration run) earn a second small results commit, and
                 THAT one cites hashes. Then: what landed / what's
                 carried and where / the exact next-session prompt /
                 literal last line: "Type /clear now, then paste the
                 prompt above."
 10 CLEAR        operator types /clear, on a clean tree or a written
                 progress note. A fork is never a substitute.

PRINCIPLES
A. Operator approves all commits.
B. A fork is the SAME BRAIN, not a second worker: never fork to
   parallelize; read-only tangents only, closed after. A finished session
   answers no new questions -- new question, new session. Discovered
   work exits as a spec stub, not as more work in this session.
C. Questions to the operator are SELF-CONTAINED: no terms, tiers, or
   options the operator hasn't been shown; subagent language is defined
   on relay.
D. Subagents: Explore for search, api-scout for API archaeology,
   baseball-coach for coaching semantics, /code-review's fork for review.
   Don't delegate what a handful of tool calls finishes.
E. Lessons go to memory; a lesson becomes a rule only after it bites
   twice, promoted at the per-3-chunk audit, never mid-flight.
   Destructive seams stay in CLAUDE.md: report generation DELETES;
   purge-scouting wipes 20 tables.
F. The per-3-chunk audit also does housekeeping: every spec in
   .project/specs/ must read COMPLETE, PARKED, or be owned by a live
   chunk -- anything else gets a decision; and any session older than
   the last audit gets closed.
G. A clean result counts only with a POSITIVE CONTROL: prove the
   instrument can fail before trusting its pass. A scan, probe, or
   gate that cannot be shown failing proves nothing.
```

---

## 10. Codex adversarial review — findings and dispositions (2026-08-02)

Codex reviewed the execution plan (direction not relitigated). The review file carries
**nine** citation-backed findings (3 P1, 4 P2, 2 P3 — the relay said eight; the artifact
wins). All nine accepted; every citation re-verified against the repo before amending.

| # | Finding | What changed in this proposal |
|---|---|---|
| P1-1 | Step 0 not executable: worktree-guard mode 2 denies the pilot's `src/` writes | Step 0(a) guard swap added as the migration's first move; ordering fixed |
| P1-2 | codex-review fails closed without code-reviewer.md; cites 3 other deleted files | Step 2 single-sources its needs into the skill BEFORE the deletions; §6 rows updated |
| P1-3 | `.project/specs/` sits on the documented ungated PII surface (SKIP_PATHS covers `.project/`; prior real-minor-name incident, IDEA-102) | Step 0(b): narrow SKIP_PATHS so specs/ is scanned; spec template opens with the no-real-names rule |
| P2-1 | codex-spec-review resolves only `epics/` dirs — can't review the new artifact | Disposition → "rewritten at Step 3"; §5 notes the gap until then |
| P2-2 | Three declared rule deletions and the ingest-endpoint rewrite appeared in no migration step | Added to Steps 1 and 2 |
| P2-3 | Full-Suite-Green closure gate missing from the new loop and the loss ledger | Carried forward into §5 step 3 and the one-pager; §8 credits it as kept, not lost |
| P2-4 | worktree-guard loss understated (write barrier + path traversal, not cleanliness) | Disposition DELETE → REPLACE with 20-line write-safety guard; §8 item 5 rewritten |
| P3-1 | "Revert = nothing to revert" overclaimed — the pilot lands real product code | Step 0 revert wording corrected |
| P3-2 | "Untouched"/"Nothing now" overstated — kept rules reference deleted roles/files | Per-commit reference-sweep rule added (§7 preamble); §6 and §8 claims softened |
