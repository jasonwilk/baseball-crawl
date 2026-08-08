# Migration Step 2 — retire the choreography

**Status**: COMPLETE (this commit)
**Source**: `.project/research/2026-08-02-system-redesign-proposal.md` §7 Step 2; `.project/specs/README.md` NOW.

## Goal

Delete the multi-agent choreography layer — 7 agent definitions and the 4 skills that existed to
teach agents how to be agents — after first making the two surviving workflows that read those
files stand on their own. Every accepted residual in `.project/specs/README.md` §"Accepted
residuals from Step 1" expires in this chunk.

**Order is load-bearing and is the whole risk of the chunk.** `scripts/codex-review.sh:92-113`
fails closed if `.claude/agents/code-reviewer.md` is absent, and re-validates four HTML-comment
delimiter markers inside it before extracting two checklists. Deleting the agents before Phase A
lands breaks code review outright. Phase A, then B, then C — one commit.

## ⛔ DO NOT TOUCH — the six historical-attribution sites

**The reference sweep WILL match all six of these. Walk past every one.** They name a deleted
agent as the party who *found* or *decided* something. They are provenance records, not pointers:
nothing breaks when the agent is gone, and rewriting them destroys the record of who established
the fact. Read each, confirm it is attribution, leave it exactly as-is.

| Site | What it records |
|---|---|
| `migrations/005_scheduled_report_runs.sql:20` | a `data-engineer` finding pinned in TN-6 |
| `src/db/purge_scouting.py:20` | the TN-8 partition, `data-engineer` owned |
| `src/db/purge_scouting.py:91` | a "do not correct these" note attributed to `data-engineer` |
| `tests/test_orphan_reclamation.py:1147` | a measurement made under `code-reviewer`'s ac5a mutation |
| `tests/test_orphan_reclamation.py:1177` | coverage measured by `code-reviewer` |
| `.claude/agent-memory/api-scout/operational-notes.md:25` | "Fixed by `claude-architect`" |
| `.claude/agent-memory/baseball-coach/coaching-decisions.md:15` | "Decisions established with `data-engineer`" |
| `.claude/agent-memory/baseball-coach/pitcher-outings-scouting-consultation.md:44` | a historical routing note |

**The one that looks identical but is NOT attribution**:
`.claude/agent-memory/baseball-coach/deep-scout-signal-catalog.md:12` is a live *instruction*
("when PM or claude-architect scopes a Deep Scout epic…"), sitting two lines from a genuine
attribution at `:10` in the same file. Scrub `:12`, leave `:10`. Distinguish by whether the
sentence tells a future reader to DO something.

## Verified premises (audited against the repo, 2026-08-06)

- `scripts/codex-review.sh:27-31,92-113,121-146` — fail-closed dependency on `code-reviewer.md`
  plus the 4-marker contract and `extract_block()`. Confirmed by read, not grep.
- Checklist extents in `.claude/agents/code-reviewer.md`: Bug Pattern `135-171`, Security
  `193-260` (marker lines inclusive). Read in full.
- `.claude/skills/codex-review/SKILL.md` also names `code-reviewer.md` on the prompt-generation
  path (`195, 204, 207`), in Edge Cases (`277`) and Anti-Pattern 3 (`300`); and points at the
  dying `context-fundamentals` skill at `79`, and at a now-2-agent `.claude/agents/` roster at
  `87, 298`.
- `.claude/skills/ingest-endpoint/SKILL.md` routes Phase 2 to `claude-architect` (frontmatter
  `3`, and `298-338`, `366-372`, anti-patterns `414-415`), and its Phase-2 body names four
  agent-memory paths (`316-320`), two of which are being archived.
- `.claude/settings.json` wires `epic-archive-check.sh` as a `PreToolUse`/`Bash` hook;
  `.claude/hooks/README.md:182-213` documents it.
- **The Step 1 residual list under-counted the dangling-reference surface, and so did this spec's
  first draft.** The full set, after the spec review below:
  `.claude/rules/testing.md:25` (points at `software-engineer`'s memory file — archived here),
  `.claude/rules/pii-safety.md:40` (cites `code-reviewer.md §4g`),
  `.claude/rules/devcontainer.md:101`, `.claude/rules/documentation.md:20,23,25,51,58,64`,
  `.claude/rules/ideas-workflow.md:41`,
  `.claude/skills/codex-spec-review/SKILL.md:69,78,81,117,157`,
  `.claude/skills/codex-review/SKILL.md:203,206` (alongside the already-listed 195/204/207),
  `.claude/skills/ingest-endpoint/SKILL.md:15` (the Purpose paragraph, not just Phase 2),
  `src/reports/recon_scoreboard.py:176` (a LIVE path into `data-engineer`'s memory — same class as
  `testing.md:25`, and the only such path in `src/`),
  `.claude/agent-memory/baseball-coach/deep-scout-signal-catalog.md:12` (a live routing
  instruction — "when PM or claude-architect scopes a Deep Scout epic" — inside a KEPT agent's
  memory), and `scripts/check_archive_refs.sh:107-110`.
- Already done by Step 1, do NOT redo: `workflow-help` is regenerated; `api-scout` and
  `baseball-coach` already carry `memory: project`.
- `.claude/rules/pitch-rules.md` (3 sites) points at `baseball-coach`'s memory — that agent is
  KEPT, its memory stays, these references are correct and must NOT be touched.

## Operator decisions taken at spec time

1. **Checklist copy = verbatim-plus-scrub.** Copy both blocks faithfully; scrub only references
   that name deleted machinery. Do not trim checks during a move.
2. **Agent trim = cut only what dangles.** No byte target. Deeper trims need evidence, not a
   number; they belong to Step 4.
3. **Archive-reference gate = leave wired.** `scripts/check_archive_refs.sh`,
   `.githooks/pre-commit`, and `tests/test_archive_refs_gate.py` are dead epic machinery but
   harmless; deletion is a later cleanup, not this chunk. **AMENDED after spec review**: the
   operator chose *scrub the role names but leave it wired*. That is not the cheap half it looked
   like — `tests/test_archive_refs_gate.py:161-172` hard-asserts the four literal role strings
   appear in the script's stderr, so scrubbing `check_archive_refs.sh:107-110` turns the suite RED
   and drags a test rewrite (and a dead acceptance criterion: "a hit is adjudicated by its owner")
   into the chunk. The operator's stated intent was to keep epic machinery out of this chunk, so
   **the script and its test are left ENTIRELY untouched** and the role names die with the gate at
   the later cleanup. Recorded as a residual, and flagged to the operator as a changed decision.
4. **CLAUDE.md lifecycle step 5 gains a line**: `/code-review` and `/security-review` are
   OPERATOR-TYPED — a session cannot invoke them and must stop and ask.

## Files

### Phase A — single-source FIRST (nothing may be deleted before this is green)

- **NEW** `.claude/skills/codex-review/bug-pattern-checklist.md` — verbatim copy of
  `code-reviewer.md:136-170` (content between the markers), plus a one-line header naming the file
  and its consumer. Scrub: `during Step 3` / `per Step 2 item 8` (a deleted agent's procedure) →
  the equivalent statement about reviewing every changed file; `the implementer's completion
  report` → `the chunk's spec progress log`. Every reworded sentence is a new claim — re-resolve
  each against the repo before writing it.
- **NEW** `.claude/skills/codex-review/security-checklist.md` — same treatment for
  `code-reviewer.md:194-259`.
- **Cross-references INSIDE the copied blocks — re-resolve all six, two are already wrong.**
  Survive as written, do not touch: `.claude/rules/browser-render-testing.md`,
  `.claude/rules/testing.md`, `docs/api/endpoints/`, `migrations/*.sql`. **Broken by Step 1's
  rewrite and must be fixed while copying**: the API-field-contract check says "see CLAUDE.md
  GameChanger API *section*" and Credential Hygiene says "Violation of *Security Rules* in
  CLAUDE.md" — CLAUDE.md has neither section today. It has a single `## Facts` heading (`:113`)
  carrying bolded `**GameChanger API**` (`:121`) and `**Security.**` (`:135`) items. Point at
  those. Also scrub "the review assignment" / "the `## Behavioral Changes` section in the review
  assignment" — dispatch machinery with no successor; the diff itself is the trigger now.
- **EDIT** `.project/codex-review.md` — **the third source, and the first draft of this spec
  missed it entirely.** This rubric is embedded VERBATIM into every Codex prompt, and its
  block-quote under "Review Priorities" plus priority 3 both tell Codex the checklists are
  "single-sourced live from `.claude/agents/code-reviewer.md` (the authoritative rubric)". After
  Phase B that is a live instruction naming a deleted file, shipped in the prompt — not mere
  documentation. Repoint both to the two new skill-directory files. While here, `Setup` item 2
  ("if the change is tied to a story, read the story file and its parent epic's Technical Notes")
  is dead choreography inside a live rubric — replace with the chunk's spec under
  `.project/specs/`.
- **EDIT** `scripts/codex-review.sh` — repoint the checklist source from
  `.claude/agents/code-reviewer.md` to the two new files. **Drop the 4-marker validation
  (`92-113`) and `extract_block()` (`121-128`) entirely** — whole-file reads need no delimiters,
  which is the simplification the move buys. **Keep the fail-closed property**: missing OR empty
  checklist file → error to stderr + `exit 1`. Update the comment block at `21-31` to describe
  what the script now actually does.
- **EDIT** `.claude/skills/codex-review/SKILL.md` — repoint `195/203/204/206/207/277/300` at the
  new files (`203` and `206` are the prompt-block HEADINGS, `204`/`207` the content placeholders —
  both halves name `code-reviewer.md`); drop the `context-fundamentals` pointer at `79` (keep the
  budget caution, lose the dead link); reword `87`/`298` for a roster that is now `api-scout` +
  `baseball-coach`. **Add `disable-model-invocation: true` to the frontmatter** — a Step 1
  residual that expires here.
- **EDIT** `.claude/skills/ingest-endpoint/SKILL.md` — rewrite Phase 2 so findings go to the
  SESSION, not a spawned agent: frontmatter description, **the Purpose paragraph at `15`**, the
  Phase-2 heading and body (`298-338`), the workflow-summary block (`366-372`), and anti-patterns
  2 and 3. The Phase-2 memory checklist (`316-320`) keeps `api-scout` and `baseball-coach` only;
  the `data-engineer` and `software-engineer` entries go. Phase 1 (api-scout, time-sensitive) is
  UNCHANGED — do not touch it.
- **EDIT** `.claude/agents/api-scout.md` (`144-154`) and `.claude/agents/baseball-coach.md`
  (`134-141`) — **this lands in Phase A, not C, and the reason is ordering**: both files' "Skill
  References" sections instruct the agent to LOAD `filesystem-context`, `multi-agent-patterns`
  and `context-fundamentals`, all of which Phase B deletes. Cutting them after the delete leaves a
  working tree in which a live agent points at four missing files. Cut ONLY the sections whose
  content references deleted agents, deleted skills, or the dispatch model (Skill References,
  Inter-Agent Coordination, and any Report Schema / Memory prose naming them). Domain content
  stays. No byte target (operator decision 2).

### Phase B — deletions

- `git rm` `.claude/agents/{claude-architect,code-reviewer,product-manager,software-engineer,data-engineer,docs-writer,ux-designer}.md`
- `git rm -r` `.claude/skills/{agent-standards,context-fundamentals,filesystem-context,multi-agent-patterns}/`
- `git mv` the 7 corresponding `.claude/agent-memory/<agent>/` dirs →
  `.project/archive/agent-memory/<agent>/`. **`api-scout/` and `baseball-coach/` stay put** — both
  agents survive and `.claude/rules/pitch-rules.md` reads the coach's memory at 3 sites.
- `git rm` `.claude/hooks/epic-archive-check.sh`; remove its stanza from `.claude/settings.json`;
  remove its section from `.claude/hooks/README.md:182-213`.

### Phase C — reference sweep

- Scrub the under-counted sites listed above. `testing.md:25` and
  `src/reports/recon_scoreboard.py:176` repoint to the ARCHIVED path; `pii-safety.md:40` repoints
  §4g to `security-checklist.md`; `devcontainer.md:101` rewords to lifecycle step 4 VERIFY;
  `documentation.md`, `ideas-workflow.md`, `codex-spec-review/SKILL.md` (`69,78,81,117,157`) and
  `.claude/agent-memory/baseball-coach/deep-scout-signal-catalog.md:12` lose role names with no
  structural rewrite. **`scripts/check_archive_refs.sh` is NOT touched** (decision 3, amended).
  `recon_scoreboard.py` is a comment-only edit — it changes no behavior, but it does put the chunk
  in `src/`, which makes the full suite mandatory rather than merely prudent.
- `CLAUDE.md` — lifecycle step 5 gains the operator-typed line. **Cap is 11,264 bytes; the file is
  at 10,585, so 679 bytes of headroom. Measure after editing.**
- `.project/specs/README.md` — step 9 update: NOW cleared, Step 3 promoted, the whole "Accepted
  residuals from Step 1" section retired, new residuals recorded. Two of those residuals are
  bookkeeping-only and must be closed EXPLICITLY, not assumed: `disable-model-invocation` (a real
  frontmatter edit, in Phase A) and the "curate the vision has no owning agent" line — that one
  needs NO file edit, because `.claude/rules/vision-signals.md` already carries the trigger phrase
  and the do-not-edit-VISION.md rule with no agent named. Verified by read; retire the README
  bullet.

## Out of scope

- Deleting `scripts/check_archive_refs.sh`, `.githooks/pre-commit`'s archive stanza, or
  `tests/test_archive_refs_gate.py` (operator decision 3 — later cleanup).
- Everything in Step 3: the spec template, rewriting `codex-spec-review`'s input resolution, the
  `specs/done/` convention, freezing `epics/`, the structural trim of `documentation.md` and
  `ideas-workflow.md`.
- The `docs/` sweep for the retired workflow (a separate NEXT item, ~110 references across 18
  files, best sequenced after this chunk).
- Ruling on **E-263 Deep Scout (READY)** — the one epic dir carrying real product work. Step 3
  freezes `epics/`; that ruling is owed before then, not here.
- Deeper `api-scout` / `baseball-coach` trims against a byte target (Step 4, with evidence).
- Any `src/`, `migrations/`, or product behavior change.

## Verification

Run in order. Redirect pytest to a file and capture `$?` separately — never trust a piped exit
code.

1. **Phase A gate, positive control FIRST** (principle G — prove the instrument can fail).
   The script checks `codex` on PATH (`:68`) and `.project/codex-review.md` (`:77`) BEFORE it
   reaches the checklist files, so **establish those two pass first** or a non-zero RC proves
   nothing about the checklist gate. Then probe BOTH failure modes the spec claims, because a
   rewrite that checks only existence passes the missing-file probe and still ships an empty
   security rubric:
   - **missing**: `mv .../security-checklist.md /tmp/` → RC non-zero, missing-checklist message.
   - **empty**: `: > .../security-checklist.md` → RC non-zero, empty-checklist message. This is
     the probe that actually discriminates the two implementations.
   - **restore and confirm PASS** — a probe run in one direction only is not a probe. Diff the
     assembled prompt against a pre-change capture and confirm both checklist bodies are present
     and byte-identical to the old extraction. Only then proceed to Phase B.

   ⚠ **THE PASS LEG HAS A HOLE THAT READS AS A PASS — this is the one to get right.** The
   checklist gate runs at the top of the script, but `assemble_review_prompt` is reached only
   after mode dispatch, and `uncommitted` mode exits FIRST on an empty diff:
   `generate_uncommitted_diff` returns empty → `"No uncommitted changes to review."` → `exit 0`
   (`scripts/codex-review.sh:300-304`). **On a clean tree the script therefore returns RC=0 having
   never assembled a prompt or read a single byte of either checklist.** A green there certifies
   nothing about the rewrite. The pass leg REQUIRES a non-empty diff in the tree when it runs —
   stage something first — and the evidence is the assembled prompt text, never the exit code.
2. `grep -rnE "claude-architect|code-reviewer|product-manager|software-engineer|data-engineer|docs-writer|ux-designer|agent-standards|context-fundamentals|filesystem-context|multi-agent-patterns|epic-archive-check" . --exclude-dir=.git --exclude-dir=.project/archive --exclude-dir=data`
   — **repo-wide, not the four dirs the first draft named**; the misses that the spec review found
   were all outside them (`src/`, `tests/`, `migrations/`, kept agent-memory). Permitted survivors:
   the archived-path repointings, `.githooks/pre-commit` and `scripts/check_archive_refs.sh` +
   `tests/test_archive_refs_gate.py` (out of scope), and every entry on the HISTORICAL ATTRIBUTION
   list above. Read every hit; do not rule on the count.
3. Synonym pass, not just tokens: grep for `dispatch`, `spawn`, `the PM`, `implementing agent`,
   `agent team` across `CLAUDE.md`, `.claude/rules/`, `.claude/skills/` and read the touched
   sections. A retirement strands the prose that depended on it without sharing its words.
4. `wc -c CLAUDE.md` → ≤ 11264.
5. `python -m pytest tests/ > /tmp/step2-suite.txt 2>&1; echo "RC=$?"` then read the file for the
   summary line. **Mandatory, not prudent**: the chunk touches `src/reports/recon_scoreboard.py`.
   `tests/test_archive_refs_gate.py:161-172` is the specific test that would go red if anyone
   scrubs `check_archive_refs.sh` after all — treat a failure there as the signal that decision 3
   was violated, not as a flaky test.
6. Step 6 SCAN: `python3 src/safety/pii_scanner.py --staged`, then compare scanned-count to
   staged-count. **`.claude/` is blind to BOTH instruments** (standing residual): every staged
   `.claude/` file needs a manual pass, and a silent RC=0 there is vacuous, not clean.
   **PREDICT THE GAP BEFORE YOU SEE IT, or the comparison becomes theatre.** `SKIP_PATHS`
   (`src/safety/pii_patterns.py`) contains BOTH `.claude/` and `.project/archive/`, and the
   agent-memory move stages several hundred files that travel from one skipped tree straight into
   the other. So this chunk's scanned-count will be a small fraction of its staged-count **by
   construction**. Read that correctly in both directions: it is NOT a newly-opened hole (net PII
   posture is unchanged — the content was unscanned before the move and is unscanned after), and
   it is NOT clean (nothing was inspected). The manual pass is owed on the moved content exactly
   as it would have been owed in place. Run the positive control on `.project/specs/` — planting a
   known-bad line there returns RC=1, so a clean result on the files that ARE scanned is real.

## Progress log

- 2026-08-06 — Spec written. Repo audit completed before drafting: the fail-closed dependency,
  both checklist extents, and the dangling-reference surface were read, not inherited. Three
  operator decisions taken (see above) plus the CLAUDE.md step-5 addition.
- 2026-08-06 — **SPEC-REVIEW run** (headless `codex exec`, codex-cli 0.145.0, adversarial against
  the repo). Six findings, **all six independently verified against the repo by this session and
  all six ACCEPTED**; none dismissed. Its confirmation that the `codex-review.sh` premises check
  out is corroboration, not new information — those were read before drafting.
  1. *High* — `tests/test_archive_refs_gate.py:161-172` hard-asserts the four role strings that
     decision 3's scrub would have removed. **Changed decision 3**: the script and its test are now
     left entirely untouched. This is the finding that most changes the chunk.
  2. *High* — two Step-1 residuals were unplanned: `disable-model-invocation` (now a Phase A
     frontmatter edit) and the curate-the-vision owner line (verified as already satisfied by
     `vision-signals.md`; a README retirement, no file edit).
  3. *High* — the sweep surface was still under-counted and the verification grep was scoped to
     four dirs that could not see the misses. Sweep is now repo-wide; `recon_scoreboard.py:176`
     and `deep-scout-signal-catalog.md:12` added; a HISTORICAL ATTRIBUTION list added so the
     sweep does not churn provenance records.
  4. *Medium* — under-enumerated lines inside files already in scope (`codex-review` 203/206,
     `codex-spec-review` 81/117/157, `ingest-endpoint` 15). All added.
  5. *Medium* — the positive control could not discriminate a rewrite that checks existence but
     not emptiness, and did not establish the script's two earlier prerequisites. Both fixed;
     a restore-and-PASS leg and a byte-identical prompt diff added.
  6. *Low* — Phase B deleted skills that Phase C's kept-agent trim still pointed at. The
     kept-agent trim moved from Phase C to Phase A.

- 2026-08-06 — **Own adversarial pass, run after Codex and deliberately aimed at what Codex did
  not open.** Codex audited references, line numbers, phase order and verification; it never
  opened the rubric file, the checklist bodies' own cross-references, the script's control FLOW
  (as against its guard block), or the scanner's behavior under this chunk's specific staging
  shape. Four findings, all verified, all folded in:
  - *High* — **`.project/codex-review.md` is a THIRD source naming `code-reviewer.md`**, missed by
    both the first draft and Codex. It is embedded verbatim in every Codex prompt, so after Phase
    B it would ship a live instruction pointing at a deleted file. Now a Phase A edit.
  - *High* — **the pass leg of the positive control can return RC=0 without reading either
    checklist.** `uncommitted` mode exits at `:300-304` on an empty diff, before
    `assemble_review_prompt` is ever reached. A clean tree makes the whole probe vacuous. The
    verification now requires a non-empty diff and takes the assembled prompt, not the exit code,
    as the evidence.
  - *Medium* — **the copied checklists carry two cross-references Step 1 already broke**
    ("CLAUDE.md GameChanger API section", "Security Rules in CLAUDE.md" — neither exists; CLAUDE.md
    has one `## Facts` heading with bolded items). Copying verbatim would have shipped them.
    Enumerated all six in-block cross-references: four survive untouched, two are fixed.
  - *Medium* — **the agent-memory move produces a scanned-vs-staged gap that is shape-identical to
    a real blinding.** Both `.claude/` and `.project/archive/` are in `SKIP_PATHS`, so hundreds of
    files move from one skipped tree to another. Step 6 now predicts the gap and states what it
    does and does not mean, so the comparison cannot be waved through as "expected".
  - Checked and CLEARED, recorded so it is not re-audited: `.claude/settings.local.json` carries
    permissions and plugin flags only — no hook wiring, nothing this chunk touches.

  Status OPEN → ready to EXECUTE in a fresh session.

- 2026-08-06 — **EXECUTED.** Phase A green before anything was deleted; then B, then C. Full suite
  **4434 passed, RC=0** (unpiped, RC captured separately). `wc -c CLAUDE.md` = **10,661 / 11,264**
  (603 bytes headroom).

  **Phase A gate — positive control, all four legs.** Prerequisites established FIRST (`codex` on
  PATH, `.project/codex-review.md` present), so a non-zero RC could only come from the checklist
  gate. Probed with a stub `codex` on PATH that dumps stdin, against a NON-EMPTY diff — the spec's
  warned-about hole (`uncommitted` mode exits 0 at `:300-304` on a clean tree, having read neither
  checklist) was avoided, and the evidence taken was the assembled prompt, never the exit code.
  *missing* → RC=1, "checklist file not found", no prompt assembled. *empty* (`: >`) → RC=1,
  "checklist file is empty", no prompt assembled — the leg that discriminates an existence-only
  rewrite. *restored* → RC=0, prompt assembled, security block byte-identical to the pre-probe
  capture.

  **Checklist copy verified against the OLD extraction, not by eye.** Ran the pre-change script
  from a pristine `git archive HEAD` tree and diffed its extracted blocks against the new files:
  bug-pattern **18 lines vs 18**, security **45 vs 45** — no check dropped — with exactly 14
  changed lines, every one an enumerated scrub. Both Step-1-broken cross-references fixed
  ("CLAUDE.md GameChanger API section" and "Security Rules in CLAUDE.md" → the bolded
  **GameChanger API** / **Security.** items under `## Facts`); the four sound ones untouched.

  **The six historical-attribution sites were all matched by the sweep and all left as-is**, and
  the lookalike two lines away behaved as the spec predicted: `deep-scout-signal-catalog.md:12`
  (live routing instruction) is scrubbed and `:10` (attribution) survives, which the post-change
  sweep confirms by showing `:10` and not `:12`.

  **Decision 3 held**: `check_archive_refs.sh`, `.githooks/pre-commit`'s archive stanza and
  `tests/test_archive_refs_gate.py` were not touched; that test file passes (28 tests).

  ### Operator decision taken during execution — the doc-PII gate blocked the archive move

  Not anticipated by the spec or either review pass. `.githooks/pre-commit` runs
  `check_doc_pii.sh` over the WHOLE `.project/` tree whenever any `.project/` file is staged, and
  this chunk always stages `.project/specs/`. `.project/` passed clean (RC=0) before the move;
  **probed before running it**, the move made it RC=1 on **7 lines in 6 files** — team/program
  names only (no player names, UUIDs, public_ids or emails), 4 of the 7 anchoring real evidence
  (a name→classification table, a bracket-precedence example). The gate has no override and no
  suppression marker, so step 8 would have been blocked. The content is ungated today only
  because the gate is scoped to `epics/` + `.project/` and the memory lived in `.claude/`.

  **Operator ruling: narrow that directory out of the gate — "nothing should land in it that
  wasn't already committed."** Implemented as a POST-FILTER on grep's PATH field
  (`ARCHIVE_EXCLUDE_RE`), deliberately not `--exclude-dir`, which matches a BASENAME and would
  also blind the gate to a LIVE `.claude/agent-memory/`. Three self-test legs added inside the
  harness (excluded hit dropped; ordinary hit survives; content-that-spells-the-path survives) and
  three pytest tests (`TestArchivedAgentMemoryExclusion`).

  Mutation-proven, per test rather than as a count: **exclusion removed** → only test 1 fails
  (tests 2-3 are outside the blast radius; their passing says nothing); **widened to
  `.project/archive/`** → only test 2 fails, and it is load-bearing because **the harness
  self-test stays GREEN (exit 0) under that mutant**; **anchor dropped** → all three fail via the
  self-test's exit 2, so test 3 corroborates rather than owns that direction. End-to-end proof:
  the real 104-file staged move now passes the gate the hook actually runs, against a
  `git checkout-index` snapshot of the index (`.project` RC=0, `epics` RC=0). Documented in
  `.claude/rules/pii-safety.md`. **This puts a security gate in the diff, so step 5 owes
  `/security-review` as well as `/code-review`.**

  ### Found during execution, beyond the spec's enumeration — all fixed

  - `.claude/agents/api-scout.md` Model Adapter cited
    `.claude/agent-memory/claude-architect/model-behavior-reference.md`, a path this chunk
    archives. Same class as `testing.md:25` / `recon_scoreboard.py:176`; repointed with them.
  - `.github/workflows/ci.yml:12` — a live CI comment naming `code-reviewer` and the deleted
    `implement/SKILL.md`. Reworded to lifecycle step 4 VERIFY.
  - `.claude/rules/devcontainer.md:99,126` — two more "Step 1d" references beyond the `:101` the
    spec named. Exactly the class verification step 3 exists to catch: stranded prose sharing none
    of the sweep's words.
  - `.claude/skills/ingest-endpoint/SKILL.md:33` — "no PM intermediation needed".
  - `.claude/skills/codex-spec-review/SKILL.md` — `77`, `79`, `193` carried roster/spawn prose the
    spec's line list (`69,78,81,117,157`) did not name.
  - `.project/codex-spec-review.md` — the spec-review twin of the `.project/codex-review.md`
    finding: a live rubric naming `product-manager.md` as a file to READ. Role names scrubbed so
    this commit adds no new dangling pointer; the structural rewrite stays Step 3's.
  - A self-test fixture I first named `data-engineer/` inside `check_doc_pii.sh` would have
    polluted every future sweep with a false hit; renamed to `retired-agent/`.

  ### Sweep result

  Repo-wide over tracked files, `.project/archive` excluded: every surviving hit is a permitted
  survivor — the 8 attribution sites, the 3 archived-path repointings, decision 3's untouched
  gate + test, the specs describing this work, and the deferred trees (`docs/`, `epics/`,
  `.project/{ideas,research,decisions,templates}`, `reviews/`). Read, not counted.

- 2026-08-07 — **CODEX REVIEW (headless, `uncommitted`) — 2 findings, both VALID, both FIXED.**
  Read-receipt: `RESULT_FILE` 7 lines, last line the reviewer's own pytest note; both findings
  digested before triage. The run also exercised the rewritten script end-to-end.

  1. *P1 Bugs* — **the new checklist gate did not actually fail closed on a PARTIAL file.** `-f`
     plus `-s` passes a file truncated to just its provenance HTML comment, which then `cat`s an
     EMPTY rubric into the prompt at RC=0. **Reproduced independently before fixing**: truncating
     `security-checklist.md` to its 3-line header shipped a security section containing only that
     header, RC=0. This is the same existence-only defect the spec warned about, one layer up —
     and neither the missing nor the empty probe can see it, which is why review caught it and
     the positive control did not. **FIXED**: added `substantive_line_count()` (non-blank lines
     outside HTML comments) and a `MIN_CHECKLIST_LINES=5` floor. Re-measured with RC captured
     directly, not through a pipe — missing / comment-only / blank-line-only / truly-empty all
     RC=1 with distinct messages, restored RC=0 shipping 48 security lines. The floor is
     documented in the script as a **gross-truncation tripwire, not a completeness proof**:
     nothing short of a checksum can tell a complete checklist from one missing three checks.
  2. *P3 Security* — **the archive carve-out was a permanent fail-open, not a one-time move
     exception.** Correct, and the sharper form of something I flagged only as a shape: the
     operator's invariant ("nothing lands there that wasn't already committed") was written down
     and enforced by nothing, so any later edit under `.project/archive/agent-memory/**` would
     commit unscanned. **FIXED**: `.githooks/pre-commit` gained a **frozen-archive invariant**
     gate — a staged file under that prefix is admissible exactly when its BLOB already exists in
     HEAD. Placed above the missing-scanner skip (that skip `exit 0`s past everything below it).
     The test is on the blob, **never on git's rename detection**, which is a heuristic and must
     not be load-bearing in a safety gate: verified that this commit's own 104 moves pass both
     with rename detection on (0 candidates) and forced off (104 candidates, 0 not-in-HEAD).

  Four new tests (`TestFrozenArchiveInvariant`), and `TestArchivedAgentMemoryExclusion`'s first
  test was **reworked** — the new gate correctly refused it, because it staged content straight
  into the archive rather than moving it in. That is the gate working, not a regression; the test
  now seeds the realistic way. All mutants re-run after the rework and per-test outcomes recorded
  in both class docstrings; the pre-rework mutation run is marked superseded rather than left to
  read as current.

- 2026-08-07 — **Correction: `INGESTION-BUGS-HANDOFF.md` is NOT tracked**, contrary to what the
  first execution report and a Step 2 residual claimed. `git ls-files` returns no entry, it is
  absent from `HEAD`, `git log --all` finds 0 commits touching it, and it is excluded via
  `.git/info/exclude:20`. The error: `git ls-files <path> && echo TRACKED` reads an EXIT CODE as a
  presence test, and `ls-files` exits 0 on no match. It surfaced only in the first
  filesystem-walking sweep, which sees ignored files; the `git ls-files`-based sweep never listed
  it. The false residual has been removed from `.project/specs/README.md`. No action needed.

- 2026-08-08 — **SECURITY REVIEW + CODE REVIEW. 5 findings, all VALID, all FIXED.** Two of them
  were defects in the remediation from the previous entry, which is the argument for running both.

  **SEC-1 *HIGH* — the frozen-archive gate had a live bypass, and my own comment asserted it did
  not.** The enumeration used `--diff-filter=AM` WITHOUT `--no-renames`. Git scores a move-AND-edit
  as `R<score>`, and `--diff-filter=AM` drops renames, so the candidate set came back EMPTY and
  edited content landed in the one tree no PII gate sweeps (`.project/archive/` is in `SKIP_PATHS`
  AND excluded from the byte-gate). Reproduced: an 8-line file moved in with one line appended
  scores `R058` and enumerates as NOTHING under AM-with-renames, versus the destination path under
  `--no-renames` — where its blob is correctly absent from HEAD. **All 104 moves in this very
  commit are `R`, so the gate was silent on the commit it was written for.** The prose defect is
  the lesson: I wrote "the test is on the BLOB, not on git's rename detection", which was true of
  the TEST and false of the ENUMERATION feeding it — a claim about half the mechanism, stated
  about the whole. **FIXED** with `--no-renames` (what the neighbouring archive-refs gate already
  does, and documents). Comment and `pii-safety.md` corrected to say what is actually true.

  **SEC-2 *MEDIUM* — the byte-gate exclusion was strictly WIDER than the gate protecting it.**
  `^[^:]*\.project/archive/agent-memory/` matched SUFFIX-wise, so
  `epics/E-999/.project/archive/agent-memory/x.md` was dropped — while the enforcing gate anchors
  its prefix test at the REPO ROOT and never classified that nested lookalike as a candidate.
  Neither instrument covered it. **FIXED**: the prefix is now derived from the scan root
  (`${TARGET%/}/archive/agent-memory/`, only when the root IS a `.project` tree) and matched
  LITERALLY at position 1 of the path field via `awk index()` — so a scan root containing a regex
  metacharacter cannot alter it either.

  **SEC-3 *LOW* — two fail-open shapes in the same block**: candidates were re-split from a
  newline-joined string (a path containing a newline fragments and resolves to no blob), and
  `git ls-files -- "$p"` treats its argument as a GLOB (verified: `d/a?b.md` resolves to two
  blobs, and a multi-line `$_blob` then satisfies `grep -qxF` on either). **FIXED**: NUL-safe
  bash array end to end, `:(literal)` pathspec magic, and an unresolvable path now BLOCKS rather
  than `continue`s — per this repo's own "a missing safety signal defaults to REFUSE" rule.

  **CR-1 *MEDIUM* — I silently deleted a pre-existing assertion.** Inserting the new test class
  landed it BETWEEN `test_non_planning_paths_do_not_invoke_the_gate`'s two asserts, orphaning
  `assert "[doc-pii:" not in _output(result)`; I then removed the orphan as a "stray contradictory
  line" and **misattributed it to an external writer**. Without it that test is a tautology —
  a commit where the gate DID run and passed also exits 0. **RESTORED** with a comment saying why
  it is load-bearing. `git diff HEAD -- tests/test_doc_pii_hook.py` now shows ZERO removed lines,
  which is the check that would have caught this at the time.

  **CR-2 *LOW*** — `codex-spec-review` lacked `disable-model-invocation: true` while CLAUDE.md
  step 2 says "don't use it" and its description auto-triggers on wording step 2 itself uses.
  **FIXED**; both review skills now carry the flag.

  Mutation-proved from a VERIFIED baseline (the first attempt was measured against a torn file —
  see below — and is discarded). Each mutant fails exactly its own test, nothing else:
  `--no-renames` dropped → `test_move_with_an_edit_is_blocked`; `:(literal)` → bare glob →
  `test_glob_character_in_path_does_not_launder_the_blob_check`; exclusion disabled →
  `test_identifier_arriving_by_move_does_not_block`; widened to the whole archive →
  `test_exclusion_does_not_reach_the_rest_of_the_archive`; suffix-wise →
  `test_nested_lookalike_directory_is_not_excluded`. Re-verified this commit's 104 moves pass the
  corrected gate (104 candidates under `--no-renames`, 0 violations).

  **Self-test gap found while re-measuring**: leg (d) asserted the WRONG fixture survived, so the
  harness could not catch the suffix-wise mutant at all — only the pytest test could. Corrected;
  the mutant now drives `check_doc_pii.sh` to exit 2 as intended.

  **Tool-discipline note, recorded because the differential mattered.** Mid-review the
  `--no-renames` fix vanished from disk and a mutation run reported a torn file. Both causes were
  live: the `/code-review` fork was running its OWN mutation probe on the same file and its
  restore collided with mine. It disclosed this unprompted. Two consequences: a mutation
  measurement taken while a sibling writes the target is worthless (the backup captured the
  mutated state, so every "restore" re-applied it), and the protocol's assert-the-mutation-applied
  step must be paired with an assert-the-BASELINE-is-intact step before the control run. Both were
  added on the re-run.
