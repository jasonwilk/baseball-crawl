# Layer pass — handoff part 3 (written 2026-07-26, successor CA)

Covers the state of **D5, D6 and 3b** at the point where both remaining
deliverables sit at operator gates. Written because the shared task list **lost
its contents once already this session** — tasks #6/#7/#8, which the part-2
handoff named as the authority on scope, did not exist when this instance
started. The committed record is the only thing that survived. Assume the same
can happen again.

## D5 — DONE and STAGED, not committed

Nine files, +259/−7, staged in the main checkout. Awaiting an operator-approved
commit relayed through the team lead.

A commissioned Fable 5 reviewer passed four of five blocks in the charter diff
and raised two items, both since fixed. It removed a **maintenance carve-out**
I had written into the closing sentence of the charter's gate paragraph — the
only latitude-granting text in the diff, traceable to neither source, and sitting
in exactly the position `tool-output-integrity.md` warns about. The operator will
rule on it separately. And it caught that the operator's **part (b)**
(model-awareness as a named responsibility) was missing; it is now charter
responsibility 7, worded no wider than the clarification. That omission is a
relay defect worth remembering: the committed handoff's deliverable-5 line does
not carry part (b), which existed only in task #6, so a scope reconstructed from
the handoff alone is incomplete and does not announce itself as incomplete.

**D5 committed as `983ca8b` on 2026-07-26**, 9 files, +272/−7.

### The maintenance carve-out: REJECTED by the operator, pending evidence

Recorded here so a future re-add starts from the exact text rather than from
someone's memory of it. The sentence, which I had written as the closing
generalization of the charter's gate paragraph, was:

> Editing this file to fix a stale fact, a broken path, or a wrong claim is
> ordinary maintenance and needs no gate; the gate is about scope, not about
> touching the file.

**Disposition:** reviewed by a commissioned Fable 5 reviewer, flagged as the only
latitude-granting text in the diff and traceable to neither source (task #6 nor
the handoff), removed from the staged diff before commit, and then **REJECTED by
the operator on 2026-07-26 until friction evidence accumulates.** It is therefore
absent from `983ca8b` by decision, not by oversight — do not "restore" it as a
missing piece.

The reviewer's objection is the part worth carrying: under the sourced
arrangement the REVIEWER classifies a self-edit; under the carve-out the AUTHOR
does. It also carried an `[Operator ruling, 2026-07-26]` citation at paragraph
end that covered the gate, not the carve-out — borrowed authority.

**What a future re-add needs:** its own operator citation, plus documented
instances of the gate costing more than it returns. The case to make is
empirical — cite the specific occasions where a stale-fact fix was delayed or
inflated by the gate — and it should be made by whoever pays that cost, not by
the agent whose latitude increases.

Two things a successor must not re-derive:

1. **The removal half of D5 came back EMPTY, and that is the finding.** D5 said
   Opus 5 agents "lose type-1 self-recheck lines." Three grep passes over all
   nine definitions (literal vendor phrasings plus two synonym expansions) found
   no generic self-recheck scaffolding to remove. What the greps surfaced were
   things that must NOT be pruned: PM's relay-echo and AC verification (types 2
   and 3), api-scout's re-verify-a-changed-endpoint (a check on the API, not on
   itself), and SE's pre-completion checklist (each item names a specific bug
   class that escaped a prior review). **The scaffolding this pass was hunting
   lives in the shared always-loaded rule files — which is 3b's territory.** Do
   not re-run this sweep against the agent definitions expecting a different
   answer.
2. **The gate on `.claude/agents/claude-architect.md` is unresolved.** Its diff
   is staged with the other eight, which means a `git commit` sweeps it past the
   review. If D5's remainder lands first, `git restore --staged
   .claude/agents/claude-architect.md`.

Corrected fact worth carrying: the vendor URLs implied by the reference **404**.
The live paths are
`platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-<model>`.
All the snippets D5 needed are now transcribed verbatim into
`model-behavior-reference.md`, so no re-fetch should be necessary.

## D6 — EXECUTED and COMMITTED (`4584192`), scoped to the always-loaded tier

The operator approved the narrower scope argued in `d6-memory-prune-deletion-list.md`
(that file stays as the record): prune the nine `MEMORY.md` files, which are the
only agent-memory files that cost context, and defer the 107 inert topic files to
a separate pass with a higher bar. Read the list file's opening section before
re-opening any of this — it argues why the aggressive-reset case rests on hygiene
rather than context cost.

Headline: **`claude-architect/MEMORY.md` went 20,123 → 12,901 bytes**, under the
read-limit hook's 17,100 ask, almost entirely by collapsing one 8,554-byte bullet
that restated all 27 sections of its own `epic-codifications.md`. All five
code-reviewer "Mandatory Review Checks" proved to be in `code-reviewer.md` with
their defect citations, so none needed promoting; the section became a tombstone
saying they moved and remain mandatory, because a bare deletion is
indistinguishable from a retirement to the next reader.

Three stale claims were fixed as approved riders, each found by hitting it: the
PM-Bash staleness fallback in `workflow-discipline.md`, the false
raw-to-processed pipeline at `etl-patterns.md:20`, and the commit-verification
string in CLAUDE.md — see the incident below, because I got that third one's
rationale wrong and the correction is `7568bff`.

**Still unaudited, and the natural next pass:** the 107 topic files, named at the
bottom of the deletion-list file. The largest untouched block is the per-epic
consultation records under `baseball-coach/` (nine files, ~78 KB) and
`product-manager/`.

## 3b — NOT STARTED

> **⚠ CORRECTION, added after the task files were recovered from disk.** The
> summary below was reconstructed from the committed handoff before task #8 was
> found, and it is INCOMPLETE. **Read
> `/home/vscode/.claude/tasks/session-4aca143d/8.json` in full before starting.**
> Three things it carries that the reconstruction got wrong or missed: the fourth
> file is **`workflow-discipline.md`** (gate-stack duplication, flagged-not-urged,
> keep only where two AUDIENCES need it) and NOT CLAUDE.md's purge paragraph; a
> **do-NOT-prune** note that `dispatch-pattern.md`'s concurrency advisory is a
> delegation cap of exactly the shape the Opus 5 vendor page prescribes; and a
> **mandatory who-loads-this check on every change**. Treat the section below as
> orientation, not as scope.
>
> **⚠ BUT VERIFY 8.json's OWN paths CLAIM — it does not hold.** The task says
> "all four files are `paths: '**'` (always-loaded) except `testing.md`". Read
> against the live frontmatter on 2026-07-26, that is right for ONE of the four:
>
> | File | Actual frontmatter | 8.json |
> |---|---|---|
> | `tool-output-integrity.md` | `paths: "**"` | correct |
> | `testing.md` | `paths: tests/**, src/**` | correct |
> | `doc-sweep.md` | `paths: docs/**, .claude/**, epics/**, .project/**` | **WRONG — it is path-scoped, not always-loaded** |
> | `workflow-discipline.md` | **no frontmatter at all** | **unverifiable as stated — there is no `paths:` key to read** |
>
> Two consequences, and they cut in opposite directions. **`doc-sweep.md` is
> already progressive-disclosure compliant**, so the always-loaded-cost argument
> for dosing it does not apply — it loads only when someone touches `docs/`,
> `.claude/`, `epics/` or `.project/`, which is the mechanism working as
> designed. Any case for dosing it has to rest on over-compliance alone.
> And **`workflow-discipline.md` asserts in its own prose that it is "loaded on
> every interaction (`paths: '**'`)" while declaring no frontmatter** — the
> behaviour matches (it does load) but the declaration is absent, so a
> who-loads-this check performed by reading `paths:` has nothing to read on the
> one file whose finding is about duplication across loaders. Fixing that
> declaration is a candidate 3b rider; it was left alone as outside D5.

Scope as first reconstructed (retained for orientation):

Four always-loaded files carry a **keep-the-fact / dose-the-procedure** shape,
per `claude-self-read-findings.md` (the passage-level self-read inventories):

- **`doc-sweep.md`** — the retired-claims TAXONOMY is truth, keep it; the
  4-pass mandatory PROCEDURE plus its unconditional gate ("ran only step 1 =
  report as a gap") is behavior, and reads as a mandate to run a full sweep on a
  one-line typo fix.
- **`testing.md`** — the `__pycache__` `(mtime, size)` invalidation FACT is
  non-derivable, keep it; the mutation protocol built on it is behavior.
- **`tool-output-integrity.md`** — the GATE is well-scoped, keep it; the
  enumerated COMMAND MENU in the response protocol reads as a procedure and
  produces defensive cross-checking of clean reads. **This is now the largest
  always-loaded file in the repo at 21.0KB, larger than the restructured
  CLAUDE.md.**
- **`CLAUDE.md`** — the purge-scouting paragraph, whose density reads as a
  mandate to trace every clause before acting anywhere near purge or reconcile.

**BINDING GUARDRAIL, and the reason the operator deferred this to a fresh
instance: never prune type-2 or type-3 verification — checks on inherited or
relayed claims, and orchestrator-assigned independent reviewers — under type-1
(generic self-recheck) authority.** The taxonomy is in
`model-behavior-reference.md`. Every removal cites its defect, its recurrence
artifact, and its re-check point. A wrong cut here removes a verification class
that has been catching real defects, which is why this must not run on a tight
context.

One asset D5 left behind that 3b should use: the six new `## Model Adapter`
sections each state, in the agent's own definition, that the type-1 removal does
not reach types 2 and 3. So the shared-file dosing has a per-agent backstop that
did not exist when 3b was scoped.

**Two things from the context-engineering blog, which D5 read as a primary and
recorded in `model-behavior-reference.md` as the fifth vendor source.** First,
the vendor's prescription for a lengthy instruction is to *"create a verification
skill and reference it from your CLAUDE.md"* — so **a dosed procedure moves to a
skill; it does not go in the bin**, and 3b should be a rehome with a small
residue rather than a deletion pass. Second, and pulling the other way: read
alone, that blog licenses cutting much harder than the verification taxonomy
allows, because its 80%-removal result carries no carve-out for relay checks or
reviewer gates. **The type-2/type-3 keep is repo-local evidence, not vendor
doctrine** — E-276's nine relay defects, E-270's seven, the navigator's three.
Cite the local evidence when you keep something and the blog when you cut
something, and do not let either speak for the other.

## Two loose ends still owned by others (unchanged from part 2)

1. **An idea for PM to file:** delete the vestigial reconciliation gate code in
   `src/reports/recon_scoreboard.py` (the gate retired 2026-07-26; ~180 lines
   plus tests and the baseline JSON). Keep `compute_scoreboard`, `to_json_dict`,
   and the stat-definition constants.
2. **A docs-writer paragraph:** `docs/admin/operations.md` states the E-276
   roster inversion but omits the one-run-window / dedup-reliance disclosure, so
   a runbook reader wrongly infers the player-line grain is safe under sustained
   churn.

## Method notes, inherited plus what this pass added

The part-2 notes still hold (synonym pass earns its keep; two ratchets share a
vocabulary; verify a rehome; read the changed region back — I used the last one
and all six adapter sections landed at the intended section boundary).

Added here: **a memory line and the rule that supersedes it often share no
vocabulary**, so a grep finds one and not the other — two of D6's three
wrong-content findings were phrased in words the other did not contain. And **a
duplicate that has DRIFTED is more dangerous than one that has not, while
looking less so**: it reads as independent confirmation of a rule it actually
contradicts.

### The `[pii-scan]` incident — read this before 3b, it is the whole argument in miniature

**What happened.** CLAUDE.md told every agent to verify that a `[pii-scan]`
confirmation appears after committing. D5's commit output did not contain it. I
grepped `.githooks/` and `.claude/hooks/`, found `[pii-hook]` eight times and
`[pii-scan]` zero times, and concluded the string was never emitted — writing
into CLAUDE.md that it was "a string `.githooks/pre-commit` has never emitted, so
the check it asks for could only ever fail." The very next commit printed
`[pii-scan] Scanned 1 file(s), 0 violations.` It is emitted by
`src/safety/pii_scanner.py`, the Python scanner the hook pipes into, which my
grep never covered. Corrected in `7568bff`.

**Three things it demonstrates, all of which 3b is about.**

1. **An unexpected absence is a cross-check trigger, not a finding.** I had a
   genuine observation (the string really was missing from D5's output) and a
   genuine grep result. Both were true. The conclusion drawn from them was false,
   because the search scope was narrower than the claim.
2. **The tidy closing generalization is where the defect lands.** The narrow
   sentence — "the shell file does not contain this string" — was correct. The
   confident generalization appended to it was not. That is exactly the position
   `tool-output-integrity.md` warns about, and I produced it while holding that
   rule in context.
3. **The coincidence is what made it survive.** Had `[pii-scan]` appeared in D5's
   output, the bad grep would have been caught instantly. It did not appear,
   because the scanner filters and none of D5's nine `.claude/` files qualified.
   A real observation lined up behind a wrong inference and certified it.

**Why this binds 3b specifically.** 3b's job is to trim procedural scaffolding
from the always-loaded rules on the grounds that Opus 5 does not need to be told
to check its own work. This incident is a defect that no amount of self-checking
would have caught — the author was confident, the evidence looked consistent, and
the error was in the SCOPE of a search rather than in the care taken. **What
caught it was a tool emitting evidence that it had operated** (the commit
printing what the scanner actually said), and, twice more in the same session, a
mechanical exact-match: an Edit refused a `should not` / `must not` mismatch that
my context had rendered wrong, and a splice script aborted on a byte-count
assertion. Type-1 self-recheck prose caught none of these; instruments did. Trim
accordingly — the prose that tells an agent to be careful is the cheapest thing
to cut, and the checks that make an instrument SHOW ITS WORK are the last.
