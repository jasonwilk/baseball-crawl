# Migration Step 2 — retire the choreography

**Status**: OPEN — spec-reviewed, ready to EXECUTE
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
