---
name: model-behavior-reference
description: Four-tier context architecture (shared truth / shared policy / role contracts / model adapters), per-model behavioral deltas for Opus 4.8, Opus 5, Sonnet 5 and Fable 5, the verification taxonomy, and the dated alias-to-model register. Consult before any agent-definition, rule, or CLAUDE.md placement decision.
metadata:
  type: reference
---

# Model-behavior reference

Installed 2026-07-26 from `.project/research/2026-07-26-fable-audit/model-behavior-reference-v2.md`
(the reviewed artifact; that file is the immutable research record, this is the
live copy CA maintains). v2 was consolidated from four independent reviews:
Sonnet 5 self-read, Opus 5 fidelity+self-read (ran on claude-opus-5, 29 turns,
verified), gpt-5.4 xhigh, gpt-5.6-sol xhigh. Verdicts: 3x adopt-with-edits, 1x
rethink-the-binary-rule; all blockers incorporated. Supersedes
`model-behavior-reference-draft.md`.

Claim tags used throughout: `[VENDOR page, fetched 2026-07-26]` `[LOCAL-EVAL]`
`[INFERENCE]` `[POLICY]`. A claim's tag is load-bearing — never promote a
`[LOCAL-EVAL]` or `[INFERENCE]` line to vendor authority when citing it.

## The architecture (replaces the facts/behavior binary — 5.6-sol B1, Opus c1, 5.4 B1)

Four tiers, not two:
1. **Shared truth** — domain facts and invariants (API quirks, canonical seams,
   schema semantics). Model-independent. Lives in CLAUDE.md/rules.
2. **Shared policy** — behavior EVERY model must follow: relay/source-grounding
   discipline, destructive-action boundaries, evidence-before-progress-claims,
   authorization gates, canonical-seam usage. Lives in CLAUDE.md/rules. [POLICY,
   backed by LOCAL-EVAL: relay defects observed on opus-5 (9 in E-276 planning),
   opus-4.8 era (E-270 x7), and navigator (fable, 3) — no model exempt.]
3. **Role contracts** — what each agent is responsible for. Lives in agent
   definitions (exists today).
4. **Model adapters** — empirically necessary model-specific coaching ONLY.
   Lives in agent-definition frontmatter+body, per pinned model. The ONLY
   reliably model-matched surface: the harness's injected coaching does not
   reliably match overridden subagent models. [LOCAL-EVAL 2026-07-26: an agent
   running claude-opus-5 (verified via transcript message.model) received a
   Fable 5 identity block + Fable vendor snippets from the harness.]

Placement tests, applied in order: (1) which tier? (2) who loads it? — prefer
paths-scoped rules over always-loaded CLAUDE.md (the repo's `paths:` frontmatter
mechanism IS per-role context compilation; use it — 5.6-sol B2 scoped to repo
size); (3) splits sometimes cut MID-SECTION (doc-sweep taxonomy=truth, its
4-pass procedure=adapter-dosed behavior; __pycache__ fact=truth, its protocol=
behavior) — never treat a rule file as atomic (Opus c2/c3).

Prompting is not a control plane [5.6-sol M5]: safety-critical shared policy is
enforced mechanically where possible (the repo already does: worktree-guard
hook, PII gates, fail-closed scanners, typed purge confirmation); prompts
explain the controls. New shared policy should ask "can a hook/test enforce
this?" before becoming prose.

## The verification taxonomy (5.6-sol M6; resolves Opus-5-vs-Fable tension)

1. Generic self-recheck scaffolding ("double-check your answer", "add a final
   verification step") — REMOVE from Opus 5 adapters [VENDOR opus-5: causes
   over-verification; removal = no quality loss]. Not vendor-documented for
   Sonnet 5 (which self-verifies more readily [VENDOR sonnet-5] but has no
   removal directive) — evaluate, don't assume.
2. Evidence checks on INHERITED/relayed/safety-critical claims — KEEP for all
   models (shared policy). Mechanism [Opus self-read]: "verification triggers on
   authorship, and relayed text doesn't feel authored" — so the trigger must be
   restatement, not authorship.
3. Orchestrator-assigned independent reviewers (writer-verifier, code-reviewer
   gate) — KEEP; vendor-praised on Opus 5 ("effective writer-verifier
   patterns"); distinct from a worker rechecking itself. The cap language
   ("do not use subagents to verify or double-check YOUR OWN work" [VENDOR
   opus-5, exact quote]) must never be read against the review gate.
4. Fable long-run self-verification — ADD to Fable adapters [VENDOR fable-5:
   "Make self-verification explicit in long-run prompts... fresh-context
   verifier subagents TEND TO outperform self-critique"]. Opposite direction
   from Opus 5; per-model, not fleet law.

## Per-model adapters (deltas + execution implications)

**Opus 4.8** (legacy; no agent currently pinned — re-verified 2026-07-26, no
frontmatter in `.claude/agents/` names a 4.8 alias)
- Favors reasoning over tool calls; vendor calls this beneficial; remedy for
  low tool use = raise effort, not prose. [VENDOR opus-4-8] The prior draft's
  "verify-injunctions were load-bearing for 4.8" is [INFERENCE], not vendor.
- Thinking OFF unless set; effort floor guidance "minimum high". Fewer
  subagents by default. Review-bar literalism documented.

**Opus 5** (dispatch workhorse)
- Self-verifies own work unprompted; remove type-1 scaffolding. Expands scope —
  add vendor scope-constraint snippet to adapters. Delegates readily — cap with
  own-work boundary intact. Narrates corrections more (metric confound:
  correction-count != error-count [VENDOR]). Longer responses AND longer
  written files — add length calibration for file-writing agents (PM/CA
  ratchet pressure [INFERENCE]). Thinking ON default; disabling capped at high
  + text-tool-call/XML-leak artifacts when disabled. Best mode: complete spec
  up front, left to run. Effort: high default, move BOTH directions liberally.
- [LOCAL-EVAL] Does NOT self-verify inherited claims (9 relay defects, E-276
  planning); dispatch on settled specs runs at 1/5 steering burden (E-270).

**Sonnet 5** (domain/consult agents)
- Literal instruction following: "does not silently generalize an instruction
  from one item to another, and it does not infer requests you didn't make"
  [VENDOR, full quote — second clause predicts thinning of unprompted-vigilance
  duties (vision-signal capture, flag-to-PM) on Sonnet consultations
  [INFERENCE, Sonnet self-read]]. State generalization scope explicitly.
- More agentic than 4.6, runs self-verification loops readily; NO vendor
  removal directive — leave type-1 out of new adapters but don't sweep
  existing ones without eval. Adaptive thinking ON by default (4.6 was off);
  strict effort respect, low-effort under-thinking risk — raise effort rather
  than prompt around it. New tokenizer ~30% more tokens for same text
  [VENDOR sonnet-5 page, Note block — revisit max_tokens assumptions].
  Remove forced progress-update cadences. Review-bar literalism documented.
- [LOCAL-EVAL, small n, not opportunity-adjusted: 2/2 and 2/4 unprompted
  delivery vs opus 0/6+0/8; hypothesis, not ranking.]

**Fable 5** (audits, adversarial review, hardest problems)
- Prior-model skills "often too prescriptive... can degrade output quality"
  [VENDOR]. One brief instruction steers most behaviors (vendor scopes this to
  steering, not a universal law [5.6-sol M9]). Longer turns; overplanning guard
  snippet; ground-progress-claims snippet (vendor-tested, "nearly eliminated
  fabricated status reports"). USE SUBAGENTS FREQUENTLY, long-lived + async
  preferred [VENDOR — opposite of Opus 5's cap; the repo's resumable named-
  agent dispatch matches Fable guidance]. Unrequested-action risk incl.
  "defensive git-branch backups" [VENDOR — worktree-isolation.md's exact
  territory]. Avoid surfacing context-budget counts (triggers wrap-up offers).
  Give the reason, not only the request. Never instruct reasoning-echo
  (refusal trigger). Safety classifiers: low expected frequency here, but
  benign security work MAY trigger; silent fallback to 4.8 would run a
  Fable-tuned prompt on a different model — log effective model per run;
  treat fallback as a re-dispatch decision, not a silent swap [5.6-sol B4].

## Shared traps

- Review-bar literalism [VENDOR: opus-4-8, opus-5, sonnet-5; Fable INFERRED,
  untested]: coverage-first finding stage bounded by a defect taxonomy
  ("enumerate every plausible defect within the taxonomy, including uncertain
  and low-severity; exclude pure naming/style; attach evidence + confidence +
  severity"), filter/rank downstream. NOT bare "report everything" [5.6-sol M8].
  Repo status: code-reviewer already compliant (two-tier floor) [LOCAL-EVAL].
- Effort defaults: re-sweep on any model transition; directions differ per
  model (4.8 floor-high; opus-5 move both ways; sonnet-5 same default as 4.6).
  "Stale by definition" retracted [Opus F5].
- Positive examples > prohibitions [VENDOR: opus-4-8, opus-5, sonnet-5; not
  stated for Fable].

## Execution-profile register (checklist item 3)

**Alias to model, resolved 2026-07-26** on Claude Code 2.1.220 (`claude doctor`,
native install). Method: spawn `meta.json` `model` field (the alias as written
in agent frontmatter) read against `message.model` in the same agent's
transcript (the model that actually answered). This is the only in-repo way to
verify a resolution — an alias retargets on a zero-line diff, so what a
definition was TUNED against is not recoverable from git.

| Alias in frontmatter | Resolved model | Evidence (2026-07-26 unless noted) |
|---|---|---|
| `sonnet` | `claude-sonnet-5` | baseball-coach + ux-designer spawns, session 16d8be7b (2026-07-25); grade-48a/48b/grade-fb spawns, session 4aca143d |
| `opus` | `claude-opus-5` | api-scout spawn (`scout-p1`), session 16d8be7b (2026-07-25) |
| `opus[1m]` | `claude-opus-5`, 1M-context variant | claude-architect spawn (`ca-toolintegrity`), session 16d8be7b; `message.model` reports the BASE id `claude-opus-5` with no `[1m]` suffix — the suffix appears only in the session environment block. Do not read a bare `claude-opus-5` in a transcript as evidence that the 1M variant was NOT used. |
| `fable` | `claude-fable-5` | `redteam-e276` spawn, session 4aca143d |
| 4.8 aliases | not resolved | No agent pins 4.8; nothing to verify. Re-check if one is ever pinned. |

Re-tune trigger is VENDOR RELEASES + harness updates + guide edits — NOT repo
diffs [Opus G1]. Per-agent effort/thinking/tool-surface audit is a separate
standing obligation; see `agent-design.md` for the current per-agent table.

## Method rules from the context-engineering blog (the FIFTH vendor source)

[VENDOR blog, "The new rules of context engineering for Claude 5 generation
models", claude.com, fetched 2026-07-26.] This source governed the layer pass's
METHOD and was missing from this reference entirely until D5 — seven distinct
term probes against this file returned zero each. The distillation in
`handoff-layer-pass.md` ("Vendor method addendum") nominally bound only that
pass's deliverable 3; these rules in fact govern every placement decision, which
is why they belong here.

- **Over-constraint degrades 5-generation models.** Anthropic *"removed over 80%
  of Claude Code's system prompt for models like Claude Opus 5 and Claude Fable 5
  with no measurable loss."* The named cause is CONFLICTING guidance — their
  worked example is a system prompt carrying "leave documentation as appropriate"
  alongside "DO NOT add comments" in one request. So a prune hunts a second class
  beyond self-recheck scaffolding: **instruction PAIRS in tension.**
- **Progressive disclosure is the vendor's own name for the who-loads-this test.**
  For lengthy instructions the blog's concrete prescription is to *"create a
  verification skill and reference it from your CLAUDE.md"* and rely on deferred
  loading. Note what that means for a dosing pass: **the destination for a dosed
  procedure is a SKILL, not the bin.** [INFERENCE — the blog prescribes a skill
  for a lengthy instruction in general; it never addresses this repo's rule files
  and never mentions deletion, so the not-the-bin half is ours. **Its falsifier
  is concrete and 3b will hit it:** a skill loads on a user intent phrase, a rule
  loads on a path. A procedure that must fire when an agent TOUCHES something —
  `testing.md`'s mutation protocol is `paths: tests/**, src/**` — has no
  intent phrase to hang on, so it cannot be rehomed to a skill and must either
  stay put or be genuinely cut with a citation. Where this inference holds is
  guidance a HUMAN or agent invokes deliberately; where it fails is guidance the
  path glob has to deliver.]
- **Repetition collapses to single placement.** Deliberate defense-in-depth
  duplication is an old-generation pattern; keep it only where two AUDIENCES
  need it, not where one reader needs two reminders. [POLICY — the second clause
  is OURS, not the blog's, which says nothing about when duplication may stay:
  it is the standard `workflow-discipline.md`'s deliberate gate duplication
  meets, and the one D5's six per-agent Model Adapter sections were justified
  against, an agent loading only its own definition.]
- **Examples constrain.** *"Giving examples actually constrains them to a certain
  exploration space."* Prefer expressive interfaces — what parameters does Claude
  have, and can they be more expressive — over exhaustive worked examples.
- **CLAUDE.md shape.** Keep it *"lightweight and briefly describe what your repo
  is for, but spend most of the tokens on gotchas inside of the codebase."* Do
  not state what Claude can discover from the file structure. (Already applied:
  the 2026-07-26 restructure, and `.claude/rules/context-layer-guard.md`.)

**⚠ The tension this source creates with the taxonomy above, stated rather than
reconciled away.** Read alone, this blog licenses cutting much harder than the
verification taxonomy permits — its 80%-removal result carries no carve-out for
relay checks or reviewer gates. **Our type-2/type-3 keep is repo-local evidence,
not vendor doctrine**: it rests on the 9 relay defects in E-276 planning, E-270's
7, and the navigator's 3, which say this fleet does not self-verify INHERITED
claims. Anyone citing the blog to cut relay discipline is citing a source that
never addressed the question. Cite the local evidence when you keep something,
and the blog when you cut something; do not let either speak for the other.

## Application checklist (CA)

1. Per-agent: coaching matches pinned model per this reference. Calibration
   pair [Opus G7]: KEEP for Fable "audit each claim against a tool result";
   REMOVE for Opus 5 "re-verify before responding". Generic-recheck vs
   relay-validation are DIFFERENT types (taxonomy above) — never prune type 2/3
   under type-1 authority.
2. Per shared file: which tier, and WHO LOADS IT (paths-scope before
   always-load). Mid-section splits allowed.
3. Execution profile per agent = model alias + dated alias-to-model resolution
   (register above) + effort + thinking mode + tool surface + fallback posture
   [5.6-sol B4, scoped: we log and date, we don't build a manifest system — git
   history is the manifest at this repo's scale].
4. Prune falsification [Opus G3 + 5.4 M7 + 5.6-sol M7]: every removed passage
   names the defect it was written against + the recurrence artifact +
   re-check point (next closure of that kind). Validation = ONE table-read per
   affected model class (self-report, necessary-not-sufficient) + the
   steering/selfcorr telemetry at the next real epic of each class. No canary
   infrastructure at this scale [POLICY: simple-first].
5. Mixed-model teams [Opus G5]: artifacts authored by one model for another
   state scope explicitly (Sonnet consumers don't generalize); a shared-rule
   removal for one model's benefit is a removal for ALL loaders — run the
   who-loads-this check. Consultation agents load ONLY the always-on layer plus
   their own definition, so a shared-file change is invisible to them unless it
   lands in an always-loaded file or their own definition.
6. Main session [5.4 M2 + 5.6-sol M3, scoped]: harness owns vendor tuning but
   the match is unverifiable in-session; any main-session behavior the repo
   DEPENDS on is written as shared policy (fact-shaped, model-independent),
   never assumed injected. On fleet-main-model change: re-read
   dispatch-pattern concurrency advisory + implement-skill spawn guidance
   against the new model's delegation section [Opus G4].
7. Cross-model commissions (reviews, table-reads, evals): compose each prompt
   against the target model's style guide; record prompt with result
   [operator, 2026-07-26].
8. Memory hygiene [5.6-sol M12, scoped]: agent-memory entries carry date +
   provenance already by convention; add "effective model" to new entries
   recording behavioral lessons; the existing 90-day review + prune passes are
   the governance — no new schema.
9. Dated fetch record: **five vendor sources, not four** — the four per-model
   prompting pages plus the context-engineering blog (see the method-rules
   section above; it was absent from this record until D5 despite having
   governed the layer pass's method). All fetched 2026-07-26, and the Opus 5,
   Sonnet 5 and Fable 5 pages re-fetched later the same day during D5 (the
   verbatim snippets below came from that second fetch). Re-fetch on model
   release, harness major update, or when a claim tagged [VENDOR] is
   load-bearing for a decision. **Use these URLs — the obvious guesses 404.**
   The hub is `platform.claude.com/docs/en/build-with-claude/prompt-engineering/`
   and the per-model pages hang off it as `prompting-claude-opus-5`,
   `prompting-claude-sonnet-5`, `prompting-claude-fable-5`,
   `prompting-claude-opus-4-8`, with `claude-prompting-best-practices` carrying
   the all-model techniques. A `docs.claude.com` URL 302s to a *different host*,
   which WebFetch reports as a redirect rather than following.

## Verbatim vendor snippets (so a placement never needs a re-fetch)

Transcribed 2026-07-26 from the per-model pages named in checklist item 9. These
are the exact strings; quote them as quotes, and if you paraphrase, say you did.

**Opus 5 — scope constraint.** The one installed in this repo's Opus 5 agent
definitions:

> Deliver what was asked, at the scope intended. Make routine judgment calls
> yourself, and check in only when different readings of the request would lead
> to materially different work. If the request seems mistaken or a better
> approach exists, say so in a sentence and continue with the task as asked
> rather than quietly narrowing, widening, or transforming it. Finish the whole
> task, and stop short of actions that are clearly beyond what was asked.

**Opus 5 — the type-1 removal directive, in the vendor's own words** (worth
having exact, because its boundary is the thing people get wrong): *"If your
prompt contains explicit verification instructions ('include a final
verification step for any non-trivial task,' 'use a subagent to verify'), remove
them: instructions like these cause over-verification on Claude Opus 5, and
removing them reduces wasted tokens with no loss in quality. The same applies to
legacy harness scaffolding that adds separate verification steps."* And under
self-correction: *"Avoid instructing re-checks it already performs ('double-check
your answer,' 're-verify before responding')."* **Note what the directive names:
re-checks of the model's OWN work.** It says nothing about checking inherited or
relayed claims, which is the taxonomy's type 2 and stays for every model.

**Opus 5 — subagent cap** (applies to an orchestrator; no agent definition in
this repo grants `Agent`, so this is currently unplaced):

> Delegate to a subagent only for large tasks that are genuinely independent and
> parallelizable, such as a wide multi-file investigation. Do not delegate work
> you can finish yourself in a handful of tool calls, and do not use subagents to
> verify or double-check your own work. If one subagent can complete the task,
> use one rather than several, and keep spawn counts low.

**Opus 5 — written deliverable length** (the PM/CA ratchet-pressure remedy that
was [INFERENCE] in the draft is in fact vendor-stated): *"Match the length of
written documents to what the task needs: cover the substance, but do not pad
with filler sections, redundant summaries, or boilerplate."*

**Opus 5 — review-bar literalism, exact:** *"If your review prompt says 'only
report high-severity issues' or 'be conservative,' the model may follow that
instruction literally and report less; ask it to report everything and filter in
a separate pass instead."* The Sonnet 5 page says the same thing at length and
supplies a coverage-stage prompt; both confirm the repo's existing two-tier
code-reviewer floor rather than asking for a change.

**Fable 5 — ground progress claims** (the clause `agent-routing.md` requires in
every Fable spawn prompt; vendor-tested, *"nearly eliminated fabricated status
reports"*):

> Before reporting progress, audit each claim against a tool result from this
> session. Only report work you can point to evidence for; if something is not
> yet verified, say so explicitly. Report outcomes faithfully: if tests fail, say
> so with the output; if a step was skipped, say that; when something is done and
> verified, state it plainly without hedging.

**Fable 5 — the reason-not-only-the-request shape:** *"I'm working on [the larger
task] for [who it's for]. They need [what the output enables]. With that in mind:
[request]."*

## Two corrections from the D5 re-fetch

1. **Sonnet 5's effort default is `high`, not something lower.** *"On Claude
   Sonnet 5, effort defaults to `high`, the same as on Claude Sonnet 4.6."* This
   closes the standing "three Sonnet agents have no effort field" item as a
   non-defect — see `agent-design.md`'s register for the full disposition. The
   under-thinking risk the same page describes is scoped to `low`: *"on
   moderately complex tasks running at `low` effort there is some risk of
   under-thinking."*
2. **Opus 5's 1M context is the default AND the maximum** — *"Claude Opus 5 has a
   1M token context window as both the default and the maximum"* — which raises a
   question this reference cannot answer: whether the `opus[1m]` alias still
   differs from bare `opus` at all, or is a vestige of when 1M was opt-in. Five
   agents pin `opus[1m]` and api-scout pins `opus`. **Do not "harmonize" them on
   the strength of this quote.** The vendor sentence is about the API model; the
   alias is a harness selector, and the operator's standing feedback is that a
   partial model override strips 1M context. Resolving it needs a spawn-time
   observation, not an inference from a docs page.

## Deliberately NOT adopted (with reasons, so the next reader doesn't re-open)

- Compiled per-role effective contexts / prompt manifests / canary deploys /
  role x model x effort eval matrices [5.6-sol]: right for a fleet product,
  over-machinery for a one-operator repo [POLICY: simple-first]. The
  paths-scoped rules mechanism + telemetry scripts + git history cover the same
  failure modes at this scale. Revisit if the fleet or team grows.
- A repo-owned main-session model adapter injected alongside the harness's
  [5.6-sol M3 full form]: would double-instruct (the documented Opus 5
  compounding trap) — we take checklist 6's fact-shaped-policy route instead.
