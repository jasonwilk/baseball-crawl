# Layer pass — handoff to the successor CA (written 2026-07-26 at drain)

Deliverables 1, 2, 3, 4 and 4b of `handoff-layer-pass.md` are COMMITTED. This
note covers what remains: **D5, D6, and the deferred 3b.** The shared task list
carries each one's full scope — read tasks #6, #7, #8 before this file; they are
the authority and this note is a relay of them.

## What landed (5 commits, in order)

| Commit | Deliverable |
|---|---|
| `8c80287` | D1 — model-behavior reference installed into CA memory + dated alias register |
| `877413e` | D2 — reconciliation ratchet gate retired; scoreboard kept as a pure diagnostic |
| `d76434a` | D3 — CLAUDE.md restructured to vendor shape (59.8KB → 21.7KB) |
| `8cdd0f3` | D4 — A1-A6 codified, Fable-escalation routing, nesting claim corrected at 7 sites |
| `28ef0ac` | D4b — dispatch procedure fidelity as a checked end-state |

Net effect on always-loaded context: **~99KB → ~61KB.**

## What remains

**D5 — per-agent adapter + execution-profile audit (task #6).** Scope is in the
task, including the operator's three-part clarification about auditing
`claude-architect.md` itself.

> **The one arrangement not yet artifact-borne, and the reason this note exists:
> the successor must NOT self-certify the `claude-architect.md` diff.** Stage it,
> then STOP and report to the team lead, who commissions a **Fable 5** reviewer
> before it gates. Review scope is narrow and fixed: *is each added responsibility
> traceable to a cited defect or vendor line, or is any of it self-granted?* The
> prompt is composed per the cross-model commission rule (reason behind the
> request, brief instructions over enumerations, ground-progress-claims clause)
> and recorded with its result. The reasoning: expanding my own charter is
> structurally the documented Opus 5 scope-expansion tendency pointed at itself,
> and no agent definition in this repo has an adversarial reviewer the way code
> does. Operator approved this on 2026-07-26.

Groundwork already done and committed, so do not redo it: the dated alias→model
register is in `model-behavior-reference.md` (`sonnet`→`claude-sonnet-5`,
`opus`→`claude-opus-5`, `opus[1m]`→the 1M variant, `fable`→`claude-fable-5`, no
agent pins 4.8). The three effort-less Sonnet agents are baseball-coach,
docs-writer, ux-designer. Five Opus agents sit at `high`; api-scout at `medium`.
No agent definition grants the `Agent` tool — an operator-ruled deliberate state
("decide later with data", P2/P3 evals counting PM-escalation events), recorded
in `agent-design.md`. Preliminary placement read, still to be confirmed against
the four-tier test: the cross-model commission rule is tier 4 and belongs in
`model-behavior-reference.md`, not in the CA definition — it governs how CA
composes prompts for other models, which is working method, not a role contract
another agent needs to read.

**D6 — near-complete memory prune (task #7).** Deletion list goes to the
operator BEFORE any deletion. One live signal: a PostToolUse hook fires on
`.claude/agent-memory/claude-architect/MEMORY.md` at 20.1KB against a 24.4KB read
limit, asking for compaction under 17.1KB. The bulk is one enormous
"Key Architectural Decisions" bullet that has accreted per-epic codification
summaries; the per-epic detail already lives in `epic-codifications.md`, so the
index line is duplicating its own topic file.

**3b — procedure-dosing mid-section splits (task #8).** Deferred by the operator
to a FRESH instance because tier-2-adjacent surgery must not run on a tight
context. `tool-output-integrity.md` is now the largest always-loaded file at
21.0KB — larger than the restructured CLAUDE.md. Task #8 carries the four files,
the per-file self-read finding, the keep-fact/dose-procedure shape, and the
binding guardrail: never prune type-2 or type-3 verification (relay/inherited
claims, orchestrator-assigned reviewers) under type-1 (generic self-recheck)
authority.

## Two loose ends someone else owns

1. **An idea to file (PM):** delete the vestigial reconciliation gate code —
   `evaluate_gate`, `load_baseline`, `write_baseline`, `default_baseline_path`,
   `GateResult`/`GateViolation`, `BaselineError`, `RATCHETED_AXIS_COUNTERS`, the
   `--update-baseline` flag (~180 lines in `src/reports/recon_scoreboard.py`
   plus the CLI branch and its 0/1/3/4 exit-code contract), the gate tests, and
   `.project/baselines/reconciliation-scoreboard.json`. Keep `compute_scoreboard`,
   `to_json_dict`, and the stat-definition constants. Natural carrier: the next
   `recon_scoreboard.py` touch. Until then the vestige is named explicitly in
   CLAUDE.md and `docs/admin/operations.md` so the layer and the CLI docstring do
   not disagree silently.
2. **A docs-writer paragraph:** `docs/admin/operations.md` states the E-276
   roster inversion but omits the one-run-window / dedup-reliance disclosure, so
   a runbook reader wrongly infers the player-line grain is safe under sustained
   churn. From the hiccup ledger; NOT a ratchet item and deliberately excluded
   from D2's sweep.

## Method notes worth inheriting

- **The synonym pass earns its keep.** D2's token grep missed baseball-coach's
  memory describing when "the gate fires" — no ratchet token in the sentence.
- **Two ratchets share a vocabulary.** The reconciliation ratchet (retired) and
  the context-layer ratchet (`context-ratchet.sh`, trigger 7, alive) — plus
  IDEA-148's longer-name-wins "ratchet". Check which one a hit belongs to.
- **Verify a rehome, do not trust it.** D3 confirmed 26 seams before and after
  and all 29 body lines present verbatim before considering the move done.
- **Read the changed region back.** D4b's Step 12 heading first landed inside
  Step 11's body; an insertion anchored on a nearby string is not an insertion
  at a section boundary, and only reading it back distinguishes them.
