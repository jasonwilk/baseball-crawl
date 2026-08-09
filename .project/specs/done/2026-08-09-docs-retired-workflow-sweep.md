<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Sweep `docs/` for the retired PM/epic/dispatch workflow

**Date**: 2026-08-09 · **Status**: `COMPLETE (this commit)`
**Source**: `.project/specs/README.md` NEXT — "Sweep `docs/` for the retired workflow — now
unblocked, the agents are gone." Deliberately out of migration Steps 1–3's scope.

## Goal

After this chunk, no live operator-facing or model-facing surface teaches the retired
PM/epic/dispatch workflow as if it were current. An operator opening `docs/admin/` is no longer
told to talk to a `product-manager`, to invoke agents by `@name`, to look in an `epics/` tree, or
to run a procedure owned by a `code-reviewer` at "epic closure". Every surviving mention of that
vocabulary is either a historical record that says so, or a path that resolves.

The trees that are *records* — `docs/ROADMAP.md`, `.project/archive/**`, `.project/research/**`,
`.project/decisions/**`, `reviews/**` — keep their vocabulary. This chunk changes what the project
**instructs**, never what it **remembers**. The one place that line is hard to draw is a record
containing an imperative sentence; see step 2.

## The sweep is re-run, not inherited

The march entry enumerated concrete targets. Per its own instruction they were treated as a
CLAIM.

**Method — file-then-read** (`.claude/rules/tool-discipline.md`, the rule added by `902fb1e`
mid-chunk). The sweep was run three times and only the third method held:

| Pass | Method | Result |
|---|---|---|
| 1 | Line-level term-grep + synonym expansion | 5 sites beyond the march entry. Files were *counted*, not opened. |
| 2 | `codex-spec-review` | **+3** — all three in files pass 1 had already counted. |
| 3 | **Coarse subsystem tokens → enumerate FILES (114, deliberately over-matched) → read each file's relevant sections** | **+4** — in `.claude/rules/devcontainer.md`, a third and fourth site inside `.claude/rules/testing.md`, `scripts/codex-review.sh`, and a stranded fallback in a file already being edited. |

That is 5 → 8 → 12, the same undercount curve the rule was written about. **The next session
inherits pass 3's inventory, not a term list**: if you need to re-verify, enumerate files with
coarse tokens and read them. A line-level grep for the terms below will reproduce pass 1.

Three results that session must not re-derive:

**CORRECTED — the four "DEAD `epics/` pointers" are not dead.** All four resolve to two files
(three of the pointers cite E-075), and both files exist:

```
.project/archive/E-075-mobile-credential-capture/R-01-findings.md   EXISTS
.project/archive/E-002-data-ingestion/E-002-R-01.md                 EXISTS
```

They are STALE PATHS from the 2026-08-08 freeze move, not dangling references. **The fix is
repointing, not deletion** — deleting them would destroy a live pointer to a real record.

**CONFIRMED — `context-ratchet.sh` does not exist.** Absent from `.claude/hooks/` on disk and
absent from `git ls-files .claude/hooks/`. `agent-guide.md:102`'s "survives" is false. (Tested
both ways, per tool-discipline: an exit code is not a presence test.)

**Five live surfaces the march entry never named.** `terminal-guide.md` is the one that matters
for method — it was found only by synonym expansion, because its section headings contain neither
"epic" nor "dispatch":

| Site | What it teaches that is false |
|---|---|
| `docs/admin/terminal-guide.md:208-218` | A "Terminal Modes" table with an **Agent Teams** column — "Standard multi-agent work: dispatching epics, running the PM and implementing agents together". Also `:185,189` ("Run Claude Code in tmux mode (for Agent Teams)"). |
| `docs/admin/architecture.md:70` | Directory-tree block lists `epics/` as a live directory; `.project/` glossed "Archive, ideas, research, templates" — `specs/`, the live surface, is missing. |
| `docs/safe-data-handling.md:15,63,66,316` | "Create a subdirectory for your current epic"; a skip-list row `\| epics/ \| Active epic and story files \|`; "Planning artifacts (`epics/` and `.project/`)"; `Save to /ephemeral/<epic>/`. |
| `.claude/skills/codex-review/SKILL.md:3` | Frontmatter trigger phrases "review epic", "review epic E-NNN", "codex review E-NNN" — model-facing invocation vocabulary for a tree that is frozen. |
| `.claude/rules/dependency-management.md:86` | "change it in all four locations atomically and reference the story in the commit". |

**Three more from pass 2 (codex-spec-review)** — all model-facing live instructions, all in files
pass 1 had counted without opening:

| Site | What it teaches that is false |
|---|---|
| `.claude/agents/baseball-coach.md:140` | Live agent definition: record "Domain consultation outcomes -- questions asked, requirements produced, **epic/story references**". |
| `.claude/rules/testing.md:57,61` | "not just the tests named in the **story's** 'Files to Create or Modify'"; "**Story-scoped** test lists are written during planning". `:57` is imperative instruction; `:61` opens the E-085 evidence paragraph. |
| `.claude/skills/ingest-endpoint/SKILL.md:113,121` | "unblocks any **stories** mentioned in the findings"; "Any research questions answered or **stories** unblocked". **Same numbered block as the `:112` repoint** — fixing 112 and leaving 113 is precisely the insertion-orphans-the-neighbour defect. |

**Four more from pass 3 (file-then-read)** — note that two of them are *additional sites inside
files already on the edit list*, which is exactly what a term-list inventory cannot see:

| Site | What it teaches that is false |
|---|---|
| `.claude/rules/devcontainer.md:114` | "`SKIP_BROWSER_TESTS` is a cross-**story** pinned literal -- the browser test reads this exact token; do not rename it." Live instruction; the do-not-rename warning is load-bearing and must survive. |
| `.claude/rules/testing.md:73` | "Run the discovered test files in addition to any **story-scoped** tests" — a THIRD site in a file pass 2 had already opened at `:57,61`. |
| `scripts/codex-review.sh:47,210,212,220-223` | **Non-executable lines in a live script** — `:210,212,220-223` are `#` comments; **`:47` is `usage()` heredoc text**, i.e. `--help` output. They frame the `--workdir` path as "Epic worktree mode" whose working tree "contains all accumulated **story patches** (applied via `git apply` and staged via `git add -A`)". The `--workdir` mechanism is live and correct — worktrees survive (principle H). The patch-application flow it describes is the deleted dispatch machinery, so the text would mislead the next maintainer. See step 6 for why the comment/heredoc split matters. |
| `.claude/skills/ingest-endpoint/SKILL.md:395` | "If the research spike file **has been archived or deleted**, skip the research relevance check." This is the fallback for the `:112` pointer. Once `:112` resolves to the archive, the fallback's premise shifts under it — the stranded-neighbour class, found only by reading the file rather than the line. |

Plus two `Story:` staleness footers where the convention (`.claude/rules/documentation.md:42`) is
`Source:` — `cloudflare-access-setup.md:365`, `terminal-guide.md:277` — and three further
archive-path pointers in `.claude/agent-memory/baseball-coach/`.

**One factual defect found in passing, inside a table this chunk edits anyway.**
`docs/safe-data-handling.md:60` documents the scanner skip-list as a blanket `.project/`. That is
stale: `src/safety/pii_patterns.py:182-199` narrowed it on 2026-08-02 to four subdirs
(`archive/`, `ideas/`, `research/`, `templates/`) precisely so `.project/specs/` **is** scanned.
The doc currently tells a reader their spec is unscanned when it is not. Fixed here because it is
the adjacent row of the same table; it is a doc-vs-code truth fix, not a code change.

**Ruled out after reading — these name a deleted agent but are correct.** Do not "fix" them:

- `.claude/agents/api-scout.md:179`, `.claude/rules/testing.md:25` — cite
  `.project/archive/agent-memory/claude-architect/…` and `…/software-engineer/…`. Both targets
  verified present. The role name is part of a resolving path. ⚠ `testing.md` is BOTH: `:25` is
  KEEP, `:57,61,73` are EDIT. Do not let one verdict cover the file.
- `docs/admin/operations.md:565`, `.project/specs/2026-08-04-root-team-id-namespace-collision.md:53`
  — provenance records ("docs-writer disclosed…", "(claude-architect)"). Criterion-vs-evidence:
  they record who did something, they do not instruct.
- `.claude/skills/codex-review/SKILL.md:77`, `codex-spec-review/SKILL.md:66` — "in the E-230
  dispatch a triage question was fired off a ~2KB preview". Evidence for why the rule exists.
- `scripts/proxy-endpoints.sh:207`, `proxy-report.sh:179`, `proxy-review.sh:161` — `# Dispatch` is
  a shell argument-dispatch comment. Unrelated sense of the word.
- `scripts/check_doc_pii.sh:57,166` — `epics/E-999/…` is a deliberate hypothetical nested lookalike
  in a comment about path anchoring; `:166` uses `epics` as the worked example of a scan root that
  yields no exclusion. Both explain a *design property* of a security harness. Rewriting example
  strings inside a PII gate's comments buys nothing and risks the explanation. KEEP.
- `.claude/rules/pii-safety.md:52` (section heading "planning/idea/**epic** artifacts are UNGATED")
  — same coupling as `:50,54`: it describes `SKIP_PATHS` as the code stands. Moves with the code,
  in the scanner chunk.
- `.project/specs/2026-08-04-docs-api-redacted-prefix-corpus.md:37` — a verbatim QUOTATION of
  `pii-safety.md:54`. Accurate while that line is unchanged; it goes stale in the scanner chunk,
  and stub 1 says so.
- `.claude/agent-memory/baseball-coach/MEMORY.md:13` — "## Epic Consultations", a heading over a
  list of dated historical consultations. Record.
- `.claude/agents/api-scout.md:154`, `.claude/agents/baseball-coach.md:130` — "(epic E-280, TN-19)"
  citing where a measurement came from. Provenance.
- `.claude/skills/ingest-endpoint/SKILL.md:111` — "CHECK research **spike** relevance". "Spike" is
  retired as a live work-type, but the archived file genuinely *is* a research spike document, so
  the noun is accurate as a description of the artifact. Considered and KEPT — do not churn it.

## Files

**Deleted**

- `docs/admin/agent-guide.md` — 124 lines; 19 deleted-agent references, a 9-row table of which 7
  rows name agents that no longer exist, the `@name` invocation block, the epic/story state
  machine, the review-tier system, and the false ratchet claim. Nothing in it is salvageable.

**Edited — inbound links to the deleted file (an insertion or deletion strands what points AT it)**

- `docs/admin/README.md:16` — drop the Agent Guide table row.
- `docs/admin/architecture.md:18` — the "Agent ecosystem" row's `See [Agent Guide](agent-guide.md)`
  repoints to `CLAUDE.md`.

**Edited — retired workflow prose**

- `docs/admin/architecture.md:70-72` — directory tree: drop `epics/`, correct the `.project/` gloss
  to name `specs/`.
- `docs/admin/terminal-guide.md:185,189,208-218,277` — Agent Teams column and dispatch framing;
  `Story:` → `Source:`.
- `docs/admin/production-deployment.md:503-508,539,558,564` — the smoke procedure's trigger/owner.
- `docs/admin/operations.md:171,299` — "**Closure check**", "The epic closure smoke asserts".
- `docs/admin/codex-guide.md:17,62` — "the Claude PM system"; "read the active epic or story files".
- `docs/admin/cloudflare-access-setup.md:365` — `Story:` → `Source:`.
- `docs/safe-data-handling.md:15,60,63,66,316` — per-epic ephemeral naming, the skip-list table
  (both the `epics/` row and the stale `.project/` row), the planning-artifacts paragraph.
- `docs/vision-signals.md:15` — "on ux-designer's refocused docket".
- `docs/ROADMAP.md` — header line, plus three instruction-mood spots (see step 2). The 61
  historical references are untouched.
- `.claude/skills/codex-review/SKILL.md:3` — frontmatter trigger phrases.
- `.claude/rules/dependency-management.md:86` — "reference the story in the commit".
- `.claude/agents/baseball-coach.md:140` — "epic/story references" in the memory-recording list.
- `.claude/rules/testing.md:57,61,73` — story-scoped test-list framing. **`:25` stays as written.**
- `.claude/rules/devcontainer.md:114` — "cross-story pinned literal".
- `.claude/skills/ingest-endpoint/SKILL.md:113,121,395` — "stories unblocked" and the stranded
  archived-or-deleted fallback; same file as the `:112` repoint.

**Edited — non-executable lines only (see step 6)**

- `scripts/codex-review.sh` — `:210,212,220-223` are `#` comments; **`:47` is NOT a comment**, it
  is a line inside the `cat >&2 <<EOF` heredoc in `usage()`, i.e. operator-visible `--help`
  output. Both are inert, but they are inert for different reasons and step 9 checks them
  differently.

**Edited — stale `epics/` paths repointed to `.project/archive/…` (7 sites, all targets verified)**

- `docs/api/auth.md:489`, `docs/api/endpoints/post-auth.md:322` → `E-075-mobile-credential-capture/R-01-findings.md`
- `.claude/skills/ingest-endpoint/SKILL.md:112` → `E-002-data-ingestion/E-002-R-01.md`
- `.claude/agent-memory/api-scout/mobile-auth-notes.md:53` → E-075
- `.claude/agent-memory/baseball-coach/e257_reconciliation_scoreboard_review.md:99` → `E-257-reconciliation-scoreboard/epic.md`
- `.claude/agent-memory/baseball-coach/e267_reconcile_at_load_review.md:13` → `E-267-reconcile-against-fresh-crawl/`
- `.claude/agent-memory/baseball-coach/idea-217-record-header-consultation.md:93` → `E-278-game-identity/epic.md`

**Edited — bookkeeping**

- `.project/specs/README.md` — strike this entry from NEXT; add the step-9 stubs.
- This spec — Status flip at step 7.

## The work

**1. Delete `docs/admin/agent-guide.md` and repoint its two inbound links.** Ruled by the operator
2026-08-09: the file has no salvageable core. The live system is two subagents (`api-scout`,
`baseball-coach`, both defined in `.claude/agents/`) and a chunk lifecycle that already lives in
`CLAUDE.md`; a replacement page would be a second copy of what `CLAUDE.md` says, and a second copy
is this repo's recurring defect. Drop the `docs/admin/README.md` row entirely rather than
repointing it — the row's description ("The AI agent ecosystem: what it is, how to work with it,
and how to request work") describes nothing that now exists. `architecture.md:18` keeps its row and
repoints, because "the project is developed through Claude Code sessions" is still true.

**2. `docs/ROADMAP.md`: header line + three instruction-mood spots.** It self-declares at `:4-9`
as "EXECUTED … retained as the reference record … read them as history", so its 61 `epic` /
14 `story` / 2 `dispatch` references are evidence, not instruction. Rewriting them would falsify
the record: the slices really were planned as epics behind dispatch gates. Add one sentence to the
existing header block saying the epic/story/dispatch vocabulary throughout is the retired
workflow's, preserved as written; the live process is `CLAUDE.md`.

⚠ **This step exceeds what the operator approved on 2026-08-09, deliberately, and the operator
should strike it if unwanted.** The ruling was "one header line, leave the record honest," on the
premise that the body carries retired *vocabulary*. The codex-spec-review found the premise
incomplete: three spots are written in the **imperative present**, which a header disclaimer does
not neutralize, and which read as live instruction to anyone arriving by deep link or grep:

- `:21-25` — "**Convention**: this table is updated at two moments — at an epic's **planning
  commit** … and at **epic closure**."
- `:37-39` — the status-value ladder, ending "A slice may span more than one epic; **add rows as
  needed**."
- `:538-539` — "6. **Normal workflow applies**: each epic goes through 'plan an epic for X' →
  codex spec review → READY → explicit dispatch authorization."

Fix by **mood only**: put each into the past tense as the convention that governed the roadmap
while it ran. Do not renumber, do not restate in current terms, do not touch the surrounding
prose or any other line. Three edits, and the record still says what it said. Recorded here rather
than folded in silently because it changes the shape of an operator ruling.

**3. `docs/admin/production-deployment.md:503-564` — keep the procedure, rewrite the trigger.**
The procedure is LIVE, verified: `.smoke-fixture` is present at the repo root (gitignored, matching
what `:513-529` describes) and `scripts/smoke_test.py` is tracked. Only its framing is retired.
Three specific falsehoods to remove:

- `:507` cites `.claude/skills/implement/SKILL.md` — that skill is deleted. Remove the citation;
  do not replace it with another skill path.
- `:505` "Every epic closure that touches a runtime or build-input surface" — restate as an
  operator-run check before a commit touching a runtime or build-input surface.
- `:564` "normally run by the code-reviewer as part of epic closure" — restate as operator-run.

Retitle away from "Closure Runtime Smoke (Step 1d)" and drop the "Step 1d" back-references at
`:511` and `:545`, which point into the deleted skill's step numbering. Keep every technical
detail: the fixture format, the plays-coverage requirement, the preflight list, the check order.
`:539,558` already describe the ratchet gate in the past tense and are accurate — leave them.

**Deliberately NOT done here**: making the smoke check a named step in the `CLAUDE.md` lifecycle.
That is a byte-cap trade (23 bytes of headroom) and principle I sends it to the operator, not to a
session. It leaves as a stub.

**4. Repoint the 7 stale `epics/` paths.** Mechanical: `epics/X` → `.project/archive/X`. Confirm
each target with `test -e` before editing, not after.

Two scope notes the next session should not relitigate:

- `docs/api/**` is api-scout's tree per `.claude/rules/documentation.md`. A stale path is a
  **defect**, not an endpoint fact, so the two sites there are fixed directly rather than routed
  through the agent. The factual endpoint claims on those lines are untouched.
- `.claude/agent-memory/**` is normally exempt as a historical record. All four pointers are
  in scope by operator ruling, on the reasoning that changing a path so it resolves **preserves**
  the record's claim — the opposite of rewriting it. This is a path fix and nothing else: do not
  touch the surrounding prose, the role names, or the E-numbers.

**5. Rewrite the remaining prose.** Each site's replacement must be a true statement about the
current system, not a deletion that leaves a dangling clause:

- `terminal-guide.md`: the file stays — tmux and ZSH are real devcontainer setup. Drop the
  **Agent Teams** column from the Terminal Modes table and rewrite the three mode descriptions in
  terms of what an operator actually chooses between (VS Code terminal vs. iTerm2+tmux, and why
  tmux survives a disconnect). `:185,189` lose the "(for Agent Teams)" framing; the
  `claude --dangerously-skip-permissions` command itself is unchanged.
- `operations.md:171`: "**Closure check**" → phrasing tied to the actual trigger, which
  `CLAUDE.md`'s north star already states (run `bb report reconcile-scoreboard` before and after
  an ingestion change). `:299`: "The epic closure smoke asserts exactly this" → point at the
  renamed smoke procedure from step 3. **These two must be written after step 3 lands**, so the
  name they cite exists.
- `codex-guide.md:17` "without recreating the Claude PM system" → "…the Claude context layer".
  `:62` "read the active epic or story files when the task is scoped" → read the active spec in
  `.project/specs/`.
- `safe-data-handling.md`: `:15` per-epic ephemeral subdirectory → per-chunk, named for the
  spec slug; update the `ephemeral/E-005/` examples to match. `:63` skip-list row for `epics/` →
  removed. `:60` the `.project/` row → corrected to the four real subdirs, with the point that
  `.project/specs/` is scanned. `:66` "Planning artifacts (`epics/` and `.project/`)" → the
  surviving trees only. `:316` `/ephemeral/<epic>/` → matches `:15`.
- `vision-signals.md:15`: "on ux-designer's refocused docket" → report-layout work, unowned. The
  signal's content is a record of what was said and does not change; only the ownership clause,
  which asserts a live docket held by a deleted agent.
- `.claude/skills/codex-review/SKILL.md:3`: drop "review epic", "review epic E-NNN", "codex review
  E-NNN" from the trigger list. **Preserve the mode discriminator sentence verbatim** — "The
  ABSENCE of the word 'spec' is the mode discriminator" is what separates this skill from
  `codex-spec-review`, and it is load-bearing. Removing triggers only narrows; confirm the
  remaining phrases still cover "codex review" and "code review".
- `.claude/rules/dependency-management.md:86`: "reference the story in the commit" → the spec.
- `.claude/agents/baseball-coach.md:140`: "epic/story references" → spec references. One list item.
- `.claude/rules/testing.md:57,61`: `:57` "the tests named in the story's 'Files to Create or
  Modify'" → the spec's Files list. `:61` opens the E-085 evidence paragraph, so keep the story
  the paragraph tells — change only the framing noun ("Story-scoped test lists" → spec-scoped),
  and leave the E-085 narrative, including "the story-scoped tests", as the record of what
  happened. **`:25` is untouched.**
- `.claude/skills/ingest-endpoint/SKILL.md:113,121`: "unblocks any stories mentioned in the
  findings" and "Any research questions answered or stories unblocked" → open work in the
  archived findings. Do these **in the same edit as the `:112` repoint** — they are the same
  numbered block, and after any addition run `git diff HEAD -- <file> | grep '^-'` to confirm no
  neighbouring line was displaced. Then `:395`: once `:112` points at a path that RESOLVES, the
  "if the research spike file has been archived or deleted, skip the check" fallback is describing
  a state that no longer applies — restate it as the genuine remaining case (the archived file is
  unreadable or its questions are exhausted). Leave `:111`'s "research spike" noun alone.
- `.claude/rules/devcontainer.md:114`: "cross-story pinned literal" → cross-chunk. **Preserve
  "the browser test reads this exact token; do not rename it"** — that clause is the point of the
  sentence and is unrelated to the workflow.

**6. `scripts/codex-review.sh` — non-executable lines only.** **Operator-ruled IN, 2026-08-09**:
`scripts/` is neither `docs/` nor `src/`, the edits cannot regress behavior, so the chunk stays
effectively docs-only and owes no `/code-review` or `/security-review`. Included because the text
teaches a mechanism that no longer exists and would mislead the next maintainer of this script.

⚠ **The ruling was given on the premise "comments only", and that premise is inaccurate for one
of the six sites.** Know which is which before editing:

- `:210` "Epic worktree mode" → worktree mode. `#` comment.
- `:212` "large removal epics" → large removal chunks. `#` comment.
- `:220-223` — drop the sentence describing "accumulated **story patches** (applied via
  `git apply` and staged via `git add -A`)"; that flow was the dispatch machinery. **Keep the
  load-bearing claim it wrapped**: a single `git diff main` from the worktree captures everything,
  so no separate `--cached` pass is needed. `#` comments.
- `:47` "exhaust Codex's budget on large removal **epics**" — **NOT a comment.** It is a line
  inside the `cat >&2 <<EOF` heredoc in `usage()`, so it is operator-visible `--help` output.
  Editing it changes what `codex-review.sh --help` prints. Still inert, but it is a user-facing
  string, and a naive "all changed lines start with `#`" check FAILS on it.

The `--workdir` mechanism itself is live and correct — worktrees survive (principle H). **Do not
touch one executable line**; Verification step 9 proves that, and it has a behavioral leg
precisely because the `#`-prefix test alone would be both wrong here and weak in general (a
`# shellcheck disable=` line is a comment that changes behavior; this file has none today, which
was checked, but do not rely on that if the file has moved on).

**7. Documentation assessment** (`.claude/rules/documentation.md`, mandatory before approval).
Every edited `docs/` file gets its `Last updated` / `Source` footer refreshed to `2026-08-09 |
Source: 2026-08-09-docs-retired-workflow-sweep`, appended to the existing provenance chain rather
than replacing it. The two `Story:` footers become `Source:` in the same pass.

## Out of scope

- **`.project/archive/`, `.project/research/`, `.project/decisions/`, `reviews/`** — historical
  records; they keep role names and pre-freeze `epics/` paths as written.
- **`docs/ROADMAP.md`'s body** — record, see step 2.
- **The five ruled-out sites** enumerated above. They are correct as written.
- **The two INERT `epics/` entries in security controls** — `src/safety/pii_patterns.py:188`
  (`SKIP_PATHS`) and `.githooks/pre-commit:125` (`GATE_TREES`). Neither can match: nothing can be
  staged under a tree that does not exist. Operator-ruled 2026-08-09 to ride the **existing
  scanner-hardening chunk** (the `pii_scanner --staged` rename blindness in STANDING RESIDUALS,
  which already owes its own spec and a `/security-review`) rather than earn their own review
  chain. Recorded as stub 1.
  **Coupling to respect**: `.claude/rules/pii-safety.md:50,54` restates `SKIP_PATHS` *accurately as
  the code stands today*. Leaving both untouched keeps doc and code CONSISTENT; editing either
  alone breaks that. So `pii-safety.md`'s `epics/**` authoring clause moves with the code, in that
  chunk — not here.
- **Making the smoke check a lifecycle step in `CLAUDE.md`** — byte-cap trade, stub 2.

## Verification

Run from the repo root, in order. Steps 2 and 5 exclude `.claude/agent-memory`; step 3 includes
it deliberately. Read each pathspec — they are not interchangeable.

1. **Positive control FIRST — prove the instrument can fail** (principle G; this session's own
   first sweep loop returned a silent empty from a mis-scoped pathspec, and a mis-scoped zero is
   shape-identical to a real zero):
   ```
   git grep -cIiE 'perspective' -- docs .claude scripts .githooks CLAUDE.md ':!.claude/agent-memory'
   ```
   MUST print a nonempty list of files. If it prints nothing, the pathspec is broken and every
   clean result below is vacuous — stop and fix the invocation before reading step 2.

2. **Deleted-agent names are gone from live instruction surfaces:**
   ```
   git grep -nIE 'claude-architect|code-reviewer|data-engineer|docs-writer|product-manager|software-engineer|ux-designer' \
     -- docs .claude scripts .githooks CLAUDE.md ':!.claude/agent-memory'
   ```
   Expected: **exactly three files**, all ruled KEEP — `.claude/agents/api-scout.md:179` and
   `.claude/rules/testing.md:25` (archive paths), and `docs/admin/operations.md:565` (provenance
   footer). Any other hit is unfinished work. **Baseline before the chunk: 6 files** — the three
   above plus `docs/admin/agent-guide.md` (deleted here), `docs/admin/production-deployment.md`
   (`:564` fixed here), `docs/vision-signals.md` (`:15` fixed here). Measured 2026-08-09 with
   this exact pathspec. (A pre-review draft of this step said "two hits" and "8 files"; both were
   wrong — the 8 came from a wider pathspec that included `.project/specs`.)

3. **No `epics/` path pointer survives anywhere outside the archive:**
   ```
   git grep -nIE '(^|[^.a-z/])epics/' -- docs .claude scripts .githooks CLAUDE.md
   ```
   The matcher hits PROSE as well as paths, so the expected set is not "nothing" — it is this
   exact list, every member of which was read and ruled KEEP on 2026-08-09. Enumerate, do not
   eyeball a count:

   | Surviving hit | Why it stays |
   |---|---|
   | `scripts/check_doc_pii.sh:57` | `epics/E-999/…` — a deliberate nested-lookalike hypothetical in a comment about path anchoring. |
   | `.githooks/pre-commit:118,125` | Inert `GATE_TREES` entry — out of scope, rides the scanner chunk (stub 1). |
   | `.claude/rules/pii-safety.md:50,54` | Restates `SKIP_PATHS` accurately as the code stands — moves WITH the code, not here. |
   | `docs/vision-signals.md:27` | "named examples pasted into epics/commits/transcripts" — prose inside a recorded signal, not a path. |
   | `docs/admin/operations.md:1087` | Provenance footer, already past-tense ("retired with the `epics/` freeze"). |

   Everything else must be gone, including `docs/admin/agent-guide.md:96` (goes with the file).
   Note this grep DOES include `.claude/agent-memory` — all four pointers there must be gone.
   (A pre-review draft omitted the last two rows, which made this step unsatisfiable as written.)

4. **Every repointed target resolves.** For each of the 7, `test -e <target>` exits 0. Run it as a
   loop that prints `EXISTS`/`MISSING` per path and read the output — do not trust the loop's
   aggregate exit code.

5. **No inbound link to the deleted file:**
   ```
   git grep -nI 'agent-guide' -- docs .claude scripts CLAUDE.md
   ```
   Expected: no output. Guarded by step 1's control.

6. **The deletion stranded nothing else** (a deletion is the mirror of the insertion case):
   ```
   git diff HEAD --stat
   ```
   Read it against the Files list above — every path present, no path absent, no surprise path.

7. **`context-ratchet.sh` is still claimed by nobody:**
   ```
   git grep -nI 'context-ratchet' -- docs .claude scripts CLAUDE.md
   ```
   Expected: no output. (Pre-chunk baseline: one hit, `agent-guide.md:102`.)

8. **PII gates — step 6 of the lifecycle, and this chunk's only review gate.** Docs-only: no
   `src/`, `tests/`, or `migrations/` change, so no full-suite gate and no `/code-review`.
   ```
   python3 src/safety/pii_scanner.py --staged
   ```
   Then compare the scanned-count against the staged-count. **They will not match, and that is
   expected**: `SKIP_PATHS` contains `.claude/`, so the scanner is blind to it *even when files are
   passed as explicit arguments* — a silent RC=0 over a `.claude/` file is vacuous, not clean
   (STANDING RESIDUALS, verified 2026-08-06). This chunk stages **ten** `.claude/**` files:
   2 skills (`codex-review`, `ingest-endpoint`), 3 rules (`dependency-management`, `testing`,
   `devcontainer`), 1 agent (`baseball-coach`), 4 agent-memory. **Count them off the Files list,
   not off this sentence** — earlier drafts said six, then nine, and were wrong both times.
   Give each a MANUAL read with a positive control — confirm the scanner flags a known-bad string
   placed in a scratch copy OUTSIDE `.claude/` first, so you know the pattern set works, then read
   all ten by eye.
   Also note `pii_scanner --staged` is BLIND TO RENAMES (`--diff-filter=ACM` vs the hook's `ACMR`).
   This chunk has one deletion and no renames, so the gap does not bite here — but do not
   generalize the clean result.

9. **`scripts/codex-review.sh` changed no executable line** — step 6's entire safety argument, and
   the operator's ruling rests on it. Three legs, because no one of them is sufficient:

   a. **Syntax**: `bash -n scripts/codex-review.sh`, expect exit 0.

   b. **Read the diff.** It is a handful of lines. Every changed line must be either a `#` comment
      or inside the `usage()` heredoc. **Do not automate this with a `^[+-]\s*#` filter** — `:47`
      is heredoc text and would trip it, so a passing grep would mean the edit was wrong and a
      failing grep would mean it was right. Read it.

   c. **Behavioral leg — the one that actually discriminates.** Capture the usage output before
      and after and diff the two:
      ```
      git stash && scripts/codex-review.sh > /tmp/usage-before.txt 2>&1; git stash pop
      scripts/codex-review.sh > /tmp/usage-after.txt 2>&1
      diff /tmp/usage-before.txt /tmp/usage-after.txt
      ```
      Expected: exactly one changed line, the intended `:47` wording, and nothing else. **Positive
      control**: confirm `usage-before.txt` is non-empty and contains the word `Usage` — an
      empty-vs-empty diff is clean-looking and proves nothing, which is how this leg fails
      silently.

10. **Re-run the sweep by the pass-3 method, not by term list** (`.claude/rules/tool-discipline.md`).
    Enumerate files with the coarse token set, subtract the ones this spec ruled KEEP, and read
    what remains:
    ```
    git grep -lIiE 'epic|story|stories|dispatch|agent|workflow|closure|product.manager|architect|reviewer|engineer|designer|spike|backlog|ratchet|worktree|handoff|consult' \
      -- docs .claude scripts .githooks .project/specs .project/templates CLAUDE.md \
      ':!docs/api/endpoints' ':!.project/specs/done'
    ```
    Pre-chunk this returned **114 files** (measured 2026-08-09). The count will not drop much —
    the tokens are coarse on purpose and most hits are unrelated senses. **The count is not the
    test.** The test is that every file it lists is either already ruled in this spec or, on
    reading its relevant sections, carries nothing about the retired workflow. Steps 2, 3, 5 and 7
    are the narrow confirmations; this step is the one that would have caught passes 1 and 2's
    misses, so do not skip it because they came back clean.

11. **Commit receipt**: confirm `[pii-hook] PII scan passed.` prints. Its ABSENCE is the alarm.

## Progress log

- **2026-08-09** — Spec written. Sweep re-run rather than inherited: the march entry's target list
  was an undercount for the fourth chunk running (5 live surfaces added at this point, 8 after the
  review; `terminal-guide.md`'s Agent Teams section reachable only by synonym expansion), and one
  of its claims was wrong in a
  way that would have caused damage — the four "DEAD `epics/` pointers" have live targets under
  `.project/archive/`, so the instruction to treat them as dead would have deleted working
  references. Four operator rulings recorded in "The work" (steps 1, 2, 3, and the scanner-chunk
  routing in Out of scope).
- **2026-08-09** — `codex-spec-review.sh` run (gpt-5.4, xhigh). **Six findings, all verified
  against the repo and all folded in** — none dismissed. Two were inventory misses, four were
  defects in my own verification section:
  - *P1, scope*: three live model-facing instruction sites missing —
    `.claude/agents/baseball-coach.md:140`, `.claude/rules/testing.md:57,61`,
    `.claude/skills/ingest-endpoint/SKILL.md:113,121`. All three files appeared in my count-greps
    and I never opened the lines. The ingest-endpoint one sits in the same numbered block as a
    repoint this spec already makes.
  - *P1, ROADMAP*: "one header line" was insufficient — `:21-25`, `:37-39`, `:538-539` are
    imperative-present instructions, not vocabulary. Folded in as a mood-only fix and **flagged in
    step 2 as exceeding the operator's ruling**, for the operator to strike.
  - *P1, verification 3*: the `epics/` matcher hits prose, so the step was unsatisfiable as
    written (`docs/vision-signals.md:27`, `docs/admin/operations.md:1087`). Replaced the
    expected-result with a read-and-ruled enumeration.
  - *P2, verification 2*: said "exactly two hits" then named three; baseline "8 files" was wrong
    (6, re-measured with the step's own pathspec).
  - *P2, verification 8*: `.claude/**` staged count was six; it is nine.

  Note the pattern across four of the six: the spec was internally inconsistent in places where I
  had counted rather than read. The march-entry undercount this spec was written to correct was
  reproduced inside the correction.
- **2026-08-09** — Operator ruled `scripts/codex-review.sh` **IN**: the edits cannot regress
  behavior, so the chunk stays effectively docs-only and owes no extra review. Correction made
  while recording it: the ruling was asked for on the premise "comments only", and `:47` is not a
  comment — it is `usage()` heredoc text, i.e. `--help` output. The ruling survives (a usage string
  is equally inert) but the verification did not: step 9's original `^[+-]\s*#` filter would have
  flagged the one line the edit is supposed to change, inverting pass and fail. Replaced with a
  three-leg check whose discriminating leg is a before/after diff of the actual usage output.
  Same defect class as the codex review's step-3 finding — a verification command written from
  the shape of the claim rather than from the file.
- **2026-08-09** — `902fb1e` landed mid-chunk, adding the **sweep by FILE, then READ** rule, and
  the operator directed this spec's sweep section to comply. Re-ran the sweep by that method:
  coarse subsystem tokens enumerated **114 candidate files**, each read at its relevant sections.
  **Four more sites**, taking the total 5 → 8 → 12:
  - `.claude/rules/devcontainer.md:114` ("cross-story pinned literal").
  - `.claude/rules/testing.md:73` — a THIRD site in a file the review had already opened at 57/61.
  - `scripts/codex-review.sh:47,210,212,220-223` — text describing the deleted dispatch
    patch-flow inside a live script.
  - `.claude/skills/ingest-endpoint/SKILL.md:395` — a fallback stranded by the `:112` repoint this
    spec already makes.

  Two of the four sit inside files that were ALREADY on the edit list, which is the finding that
  matters: a term-list inventory is blind to a second claim in a file it has already "handled."
  The rule's premise reproduced exactly — and the method that found these is now Verification
  step 10, so the next session re-runs the sweep rather than trusting this inventory. (This pass
  also moved verification 8's `.claude/**` staged count from nine to **ten** — `devcontainer.md`.
  The count has now been wrong three times; count it off the Files list.)
- **2026-08-09 — EXECUTED.** Audit first: every cited line was where the spec said, all five
  repoint targets resolved, and V2's 6-file baseline reproduced exactly. Three spec claims did
  not survive the audit, none load-bearing:
  - **V10's pre-chunk baseline is 112 files, not 114** (111 at `902fb1e`). The count is not the
    test, per the step's own text, but the figure was wrong.
  - **`.githooks/pre-commit:125` never matches V3's grep.** The line is `for tree in epics
    .project; do` — `epics` with no slash. The row's substance (inert, rides the scanner chunk)
    stands; only the line cite was unsatisfiable.
  - **`production-deployment.md`'s "Step 1d" back-reference is at `:514`, not `:511`.**
- **2026-08-09 — Operator ruled ROADMAP (step 2): header sentence + a one-line note under §0 and
  §6, NO line surgery.** The audit found the spec's premise incomplete in the opposite direction
  from the codex review: §6 is a six-item list and **all six** items are imperative-present, not
  just item 6. Past-tensing one would have left the list internally inconsistent. The section
  notes neutralize all six and touch no recorded line.
- **2026-08-09 — Verification 10 found SIX more sites, taking the total 5 → 8 → 12 → 18.** Run by
  the pass-3 method with a word-boundary matcher (a positive control confirmed the matcher fires)
  after the substring artifacts were isolated — `story`⊂`history` and `closure`⊂`disclosure`
  accounted for most of the coarse hits, and ruling on them unopened would have been an
  OR-pattern violation:
  - `ephemeral/README.md` — "Create a subdirectory named after your current epic". Live
    instruction, and `safe-data-handling.md:22` points AT it as "the full convention", so fixing
    the pointer without the target would have left the two docs contradicting.
  - `.claude/rules/devcontainer.md:85,106` — "closure-gate tests", "the non-interactive closure
    pytest". A **second and third** site in a file the spec had already opened at `:114`.
  - `.claude/rules/dependency-management.md:46` — "Derive the artifact set from this table, not
    from a story's 'Files to Modify' list". Live imperative; a **second** site in a file the spec
    had already opened at `:86`. The incident clause naming the implementer/PM/reviewer is left as
    the record of what happened.
  - `docs/admin/operations.md:309` — "Vestige, until a follow-up story removes it".
  - `.claude/rules/python-style.md:20` — the quoted rationalization "this story does not edit that
    function", inside live instruction.

  **Four of the six sat inside files already on the edit list.** That is the same blind spot that
  produced passes 1 and 2, reproduced by an inventory that had already been corrected twice for
  precisely it — including once by a pass whose whole point was to catch it. The inbound inventory
  was not evidence; only the re-run was.
- **2026-08-09 — Three judgment calls, recorded rather than silently taken:**
  - `scripts/codex-review.sh:58` — the `--help` example path
    `/tmp/.worktrees/baseball-crawl-E-137`. LEFT AS IS: worktrees are live (principle H) and an
    E-numbered directory name reads as an arbitrary illustration, not an instruction. Changing it
    would also have added a second line to Verification 9c's usage diff.
  - `docs/api/auth.md` and `docs/api/endpoints/post-auth.md` provenance NOT refreshed. The change
    there is a mechanical path repair in api-scout's tree; `post-auth.md` has no `Last updated`
    field at all, and touching `auth.md`'s `Source: E-182` would misattribute endpoint content.
  - `docs/safe-data-handling.md` had **no** `Last updated` footer despite the rule requiring one;
    one was added, since the file was being materially edited. `docs/ROADMAP.md` and
    `docs/vision-signals.md` still have none and were left alone — a record with its own dated
    header block, and a dated-entry parking lot.
- **2026-08-09 — Verification results.** V1 control 19 files (nonempty). V2 exactly 3 files, all
  ruled KEEP. V3 the ruled set, plus two NEW hits that are this chunk's own provenance footers
  (`architecture.md:266`, `safe-data-handling.md:338`) — past-tense records of a removal, ruled
  KEEP as the same class as `operations.md:1087`. V4 all 5 targets EXISTS. V5, V7 empty. V6 no
  surprise path. V9 all three legs: `bash -n` rc=0, diff read by eye (every changed line a `#`
  comment or the `:47` heredoc), and the usage diff exactly one line with a confirmed non-empty
  `Usage`-bearing baseline. V10 re-run as above. No `src/`, `tests/`, or `migrations/` change, so
  no full-suite gate.
