# Model-behavior reference (DRAFT — seed for claude-architect's memory)

Source: the four vendor prompting guides (platform.claude.com, fetched 2026-07-26)
+ this repo's measured data (2026-07-25/26 audit + P1). Intended home:
`.claude/agent-memory/claude-architect/model-behavior-reference.md`. Re-check the
vendor pages when any model in the fleet changes.

## The architecture rule this reference serves

FACTS IN THE LAYER, BEHAVIOR IN THE AGENT DEFINITION. CLAUDE.md/rules carry
model-independent truth (API quirks, canonical seams, invariants, relay and
construction discipline — needed by EVERY model per local evidence). Behavioral
coaching is model-specific and lives in agent definitions, where model+effort are
pinned in frontmatter. When frontmatter changes, re-tune the definition against
this reference. The main session has no definition: its per-model tuning is the
HARNESS's job (Claude Code injects model-specific system prompts), so do not add
main-session behavior coaching to CLAUDE.md.

## Per-model deltas that matter to this repo

**Opus 4.8** (legacy baseline; the layer was tuned for it)
- Favors reasoning over tool calls -> the verify/cross-check/read-back injunctions
  were LOAD-BEARING for it. Spawns FEWER subagents by default (needs encouragement).
- Literal instruction following, esp. at low effort; strict effort respect.
- Review-bar literalism (see shared traps).

**Opus 5** (current dispatch workhorse)
- Self-verifies unprompted; explicit verification instructions and legacy
  scaffolding COMPOUND -> over-verification, wasted tokens ("remove them").
- Expands task scope; constrain narrow tasks explicitly (vendor snippet).
- Delegates readily; cap: "do not use subagents to verify your own work; keep
  spawn counts low."
- Narrates self-corrections more (metric confound: correction-count != error-count).
- Best mode: complete spec up front, left to run. Effort: low/medium strong;
  re-sweep carried-over defaults.
- LOCAL EVIDENCE: does NOT self-verify INHERITED/relayed claims (9 relay defects
  in P1, 16-25 errors in the 07-25 session) -> relay discipline stays for it.

**Sonnet 5** (narrow domain/consult work; best measured delivery discipline here)
- Calibrates length to task; more agentic than 4.6; literal instruction following
  ("does not silently generalize an instruction... state the scope explicitly").
- Strict effort respect; low-effort under-thinking risk on complex tasks — raise
  effort rather than prompting around it. Tokenizer ~30% more tokens/text — revisit
  max_tokens-sensitive assumptions.
- LOCAL EVIDENCE: 2/2 unprompted delivery in the audited session, 2/4 here;
  caught inherited falsehoods; retracted own error when challenged.

**Fable 5** (audits, adversarial review, hardest problems)
- "Skills developed for prior models are often too prescriptive... can degrade
  output quality" — review which instructions are still needed.
- Strong instruction following: ONE brief instruction beats enumerating behaviors.
- Long turns by default; overplanning guard: "when you have enough information to
  act, act." Anti-fabrication on long runs: "audit each claim against a tool
  result" (vendor-tested, near-eliminates fabricated status).
- Fresh-context verifier subagents OUTPERFORM self-critique (vendor) — matches
  this repo's external-verifier pattern.
- Give the reason, not only the request. Provide a memory surface.
- Do NOT instruct it to echo/transcribe its reasoning (refusal-category trigger).
- Safety classifiers: offensive-cyber/bio domains refuse; irrelevant to this repo.

## Shared traps (all current models)

- REVIEW-BAR LITERALISM (documented for 4.8, Opus 5, Sonnet 5): "only report
  high-severity / be conservative / don't nitpick" -> silent under-reporting.
  Finding stage asks for EVERYTHING + confidence/severity; filter downstream.
  ACTION: audit `.claude/agents/code-reviewer.md` + review skills for this wording.
- Effort defaults carried across model generations are stale by definition;
  re-sweep on migration (A8).
- Positive examples of desired style beat prohibitions, on every model.

## Application checklist for CA

1. Per-agent: does the definition's coaching match its pinned model per this
   reference? (E.g., a "double-check your work" line is right for a 4.8 agent,
   wrong for an Opus 5 agent.)
2. Layer edits: is this sentence a FACT (stays) or BEHAVIOR (moves to definitions)?
3. Model migration of any agent: re-tune definition + effort in the same change.
4. Validation for layer prunes: one table-read by the fleet's main model
   ("which of these instructions would you over-comply with?") before commit.
