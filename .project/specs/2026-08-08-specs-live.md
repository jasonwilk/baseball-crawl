# Migration Step 3 — specs live

**Date**: 2026-08-08 · **Status**: CHUNK IN FLIGHT — spec reviewed and folded; execution owed in a
fresh session. (`.project/specs/README.md:8` exempts a spec belonging to a chunk in flight from the
four terminal statuses; this is that case, and it is why no terminal status is claimed here.)
**Source**: `.project/specs/README.md` NOW; `.project/research/2026-08-02-system-redesign-proposal.md` §7

**Two commits, do not conflate them.** THIS commit lands the spec only — nothing in the Files
section has been executed. The EXECUTE session, working from the committed spec, does the work and
makes the second commit; that is where step 7 flips this Status to COMPLETE and where the moves in
Files (including this spec's own move into `specs/done/`) actually happen.

## Goal

Retire the planning apparatus of the epic/dispatch system and stand up the surface that replaces
it. Steps 1 and 2 removed the choreography from the context layer; this step removes the
*artifacts* — the epic tree, the ideas apparatus, the four templates that shape them, and the
spec-review machinery that can only read an epic — and leaves one place where work is proposed
(`.project/specs/`), one place where someday-work is parked (`.project/specs/IDEAS.md`), and one
spec-review path that can actually read a spec file.

After this chunk, `epics/` and `.project/ideas/` do not exist, `.project/templates/` holds exactly
one file, and every step of the chunk lifecycle is executable end to end without an epic directory.

**One seam stays open on purpose, and the goal is worded to admit it** (spec review, P2): the
operator-facing `docs/admin/agent-guide.md` still describes both frozen trees as live surfaces
(`:66-68`, `:106`, `:108`). It belongs to the separate `docs/` sweep already queued in NEXT. So this
chunk stands up the replacement surface and freezes the old one — it does not finish teaching the
docs about it.

## Audit of the inherited claim

The README's NOW entry is a claim like any other. Three parts of it did not survive the repo:

1. **`epics/` is at the REPO ROOT, not `.project/epics/`.** Five directories (`E-174`, `E-263`,
   `E-271`, `E-274`, `E-275`), 26 tracked files. Verified: `ls .project/epics` → no such directory;
   `find . -maxdepth 3 -name epics` → `./epics`.
2. **The residual "`.project/codex-spec-review.md` still … points at three rules Step 1 deleted"
   is STALE.** `grep -n 'workflow-discipline\|agent-routing\|dispatch-pattern'` on that file
   returns nothing. Only the first half holds: it is epic/story-shaped throughout, and Step 2's
   "scrubbed its role names" missed `PM` at lines 92 and 94. This spec carries the true half only.
3. **Archiving the epics is BLOCKED today.** See the next section — it is the load-bearing finding
   of this audit and it changes the scope of the chunk.

Two things in scope that the README does not name, included because leaving them is drift of the
exact class this migration exists to remove:

- `.claude/rules/canonical-seams.md:7` also carries `epics/**` in its `paths:` frontmatter. The
  README names only `documentation.md` and `ideas-workflow.md`.
- `docs/admin/operations.md:1042-1046` is a live troubleshooting section for
  `[archive-refs: BLOCKED]`, and dies with the gate.

## The blocked gate (why gate retirement is load-bearing, not tidying)

`.githooks/pre-commit:8-89` fires `scripts/check_archive_refs.sh <ID>` whenever a staged
`epics/E-NNN-*` deletion pairs with a staged `.project/archive/E-NNN-*` addition for the same ID.
There is no override; the hook says so, and `--no-verify` is the only escape, which also disables
the PII scan.

That script greps the **working tree**, excluding only `.git` (`check_archive_refs.sh:97-98`). It
therefore reads `.codex-home/`, which is gitignored (`.gitignore:32`) and holds the Codex session
transcripts written on every `codex exec` run — transcripts that quote old `epics/E-NNN-` paths.

Measured 2026-08-08, per epic ID, files containing `epics/<ID>-`:

| ID | in `.codex-home/` | tracked, outside `.project/archive/` and `epics/` |
|----|---|---|
| E-174 | 3 | 0 |
| E-263 | 1 | 0 |
| E-271 | 1 | 0 |
| E-274 | 1 | 4 |
| E-275 | 1 | 2 |

So the gate returns BLOCKED for all five, and four of those five block on nothing but ignored
session logs. Because lifecycle step 2 runs `codex exec` on every chunk, those logs regenerate
permanently: the gate cannot be satisfied again in this repo.

**Operator ruling (2026-08-08): retire the gate with the freeze.** After the freeze, `epics/` does
not exist and no epic can ever be archived again, so the gate guards a directory nothing can
enter. Step 2 had already parked its deletion as "later cleanup" (decision 3); this is that
cleanup.

The consequence must be stated plainly rather than glossed: the hook that runs at commit time is
the one on disk, so deleting the stanza and moving the epics in one commit means **the archive move
itself is ungated**. Verification step 2 substitutes a manual sweep with a positive control. That
is a deliberate, one-time, operator-ruled substitution, not an oversight.

## Operator rulings folded in (2026-08-08)

1. **Archive-refs gate**: retire it with the freeze; repoint by hand this once.
2. **codex-spec-review**: rewrite all three artifacts (script, skill, rubric).
3. **`specs/done/`**: a spec that reads COMPLETE moves there; everything still open stays live.
4. **Ideas**: freeze `.project/ideas/` alongside `epics/`.
5. **The ideas CONCEPT survives, the apparatus does not**: `.project/specs/IDEAS.md`, one line per
   idea, no template, no numbering, no statuses, started EMPTY.
6. **The CLAUDE.md cap is a TRIPWIRE, not a wall**: never raise it unilaterally, never compress
   load-bearing content to meet it — surface the trade. Promoted to a NEW principle I (§7).
7. **Retire the `RULED` status**: keep the vocabulary at four; re-status the three specs that use
   it to `PARKED + why` (§10). Post-review ruling.

## Files

### Moves (freeze)

- `epics/E-174-key-extractor-chunk-search/` → `.project/archive/E-174-key-extractor-chunk-search/`
- `epics/E-263-deep-scout/` → `.project/archive/E-263-deep-scout/`
- `epics/E-271-workflow-process-redesign/` → `.project/archive/E-271-workflow-process-redesign/`
- `epics/E-274-age-group-level-signal/` → `.project/archive/E-274-age-group-level-signal/`
- `epics/E-275-classifier-hardening/` → `.project/archive/E-275-classifier-hardening/`
  (top level of `.project/archive/`, matching the 271 entries already there; E-263 is PARKED by
  operator ruling and the freeze goes over it)
- `.project/ideas/` → `.project/archive/ideas/` — **235 files TOTAL**: 234 `IDEA-*.md` plus the
  README index. (An earlier draft said "235 plus its README"; off by one, caught twice.)
- **Seven** COMPLETE specs → `.project/specs/done/`: `2026-08-02-boxscore-envelope-identity.md`,
  `2026-08-04-rung-c-auto-accept-criteria-drift.md`, `2026-08-04-search-entity-class-filter.md`,
  `2026-08-05-rung-c-search-resolve-recoverable.md`,
  `2026-08-06-claude-md-rewrite-and-line-of-march.md`, `2026-08-06-retire-the-choreography.md`,
  **and this spec itself** — step 7 flips its Status to COMPLETE before staging, so its own rule
  applies to it (see §6a).

### Deletes

- `scripts/check_archive_refs.sh`
- `tests/test_archive_refs_gate.py`
- `.claude/rules/ideas-workflow.md`
- `.project/templates/epic-template.md`, `story-template.md`, `research-spike-template.md`,
  `idea-template.md`

### Creates

- `.project/specs/IDEAS.md` — empty of entries
- `.project/templates/spec-template.md` — ≤30 lines

### Edits

| File | Change |
|---|---|
| `.githooks/pre-commit` | remove the archive-reference stanza, lines 8-89, incl. the `ARCHIVE_REFS` assignment at 25 |
| `docs/admin/operations.md` | remove the `[archive-refs: BLOCKED]` troubleshooting section — **lines 1042-1053**, heading through the "no override flag" paragraph, stopping before `## Monitoring` at 1055 (an earlier draft said 1042-1046 and would have left half the section stranded); add a Source entry for this spec in the footer, leaving E-279's entry as the historical record of what it added |
| `scripts/codex-spec-review.sh` | take a spec FILE path; add a `RESULT_FILE` receipt |
| `.claude/skills/codex-spec-review/SKILL.md` | resolve a spec file on both paths; align the read-receipt gate; drop epic edge cases |
| `.project/codex-spec-review.md` | rewrite the rubric for a one-page spec |
| `.claude/skills/workflow-help/SKILL.md` | re-list spec review; delete the "deliberately absent" paragraph |
| `.claude/rules/documentation.md` | drop `epics/**` from `paths:` |
| `.claude/rules/canonical-seams.md` | drop `epics/**` from `paths:` |
| `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md:16` | repoint `epics/E-274-…` to its archived path |
| `.claude/agent-memory/baseball-coach/e274-age-group-level-signal-consultation.md:8` | repoint `.project/ideas/IDEA-171-…` to its archived path (found by spec review, missed by the first sweep) |
| `CLAUDE.md` | five edits, incl. NEW principle I — see the byte budget below |
| `.project/specs/README.md` | step 9 update: NOW cleared, Step 4 promoted, `specs/done/` rule recorded (with `--follow`), residuals refreshed |
| `.project/specs/2026-08-04-docs-api-redacted-prefix-corpus.md` | status line `RULED` → `PARKED + why` (§10) |
| `.project/specs/2026-08-04-org-team-discovery-and-roster-ingest.md` | status line `RULED` → `PARKED + why` (§10) |
| `.project/specs/2026-08-05-rung-c-season-year-filter.md` | status line `RULED` → `PARKED + why` (§10) |

## The work

### 1. Freeze the epics

`git mv` the five directories. Exactly **one** live pointer needs repointing:
`.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md:16`, which is a
forward-looking instruction ("E-275 planning should cite those"), not a record.

The other five tracked files spelling `epics/E-274-` / `epics/E-275-` stay as written:
`.project/research/2026-07-25-session-handoff.md` (2 hits), `.project/research/E-275-planning-record.md`,
`.project/research/E-275-spec-audit-iteration-1.md`, and two idea files being frozen anyway. This
follows the Step 2 precedent — historical records keep their references; only pointers get
repointed.

### 2. Retire the archive-refs gate

Delete the script, its test, the pre-commit stanza, and the operations-doc troubleshooting section.

**Do NOT touch** the neighbouring safety machinery:

- the frozen-archive invariant (`.githooks/pre-commit:91-159`),
- the doc-PII byte-gate (`:200-`),
- `src/safety/pii_patterns.py` `SKIP_PATHS`.

The `epics/` and `.project/ideas/` entries in `SKIP_PATHS`, and the `epics` entry in the hook's
`GATE_TREES` loop, go inert but stay harmless. Removing them would churn a security control and
six test assertions (`tests/test_pii_scanner.py:536,539,550,582,586`,
`tests/test_doc_pii_hook.py`) for zero safety gain.

Verified safe, and worth recording because it looked like a second blocker: the archive commit
stages `epics/` paths as **deletions**, and `STAGED_ARR` is built with `--diff-filter=ACMR`
(`.githooks/pre-commit:181`). Deletions never enter it, so `epics` is never appended to
`GATE_TREES`, and the "`epics/` is staged but absent from the index snapshot" branch at
`:242-246` cannot fire.

### 3. Freeze the ideas apparatus

`git mv .project/ideas .project/archive/ideas`. Delete `.claude/rules/ideas-workflow.md` outright —
its whole subject is idea-to-epic promotion (comparison table, promotion criteria, 90-day cadence),
and the promotion target no longer exists.

Pointer cost is low but NOT zero, and an earlier draft of this spec understated it (spec review,
P2). Live rules that cite ideas (`pii-safety.md` → IDEA-102, IDEA-112; `canonical-seams.md`;
`data-model.md`) cite them **by ID only, never by path**, so a move strands nothing there. The
path-shaped live references are three, not two:

- `.claude/rules/ideas-workflow.md` — deleted here.
- `.claude/agent-memory/baseball-coach/e274-age-group-level-signal-consultation.md:8` — spells
  `.project/ideas/IDEA-171-…`. Live memory for a surviving agent, so **repoint it**, alongside the
  `e275-…` repoint in §1.
- `docs/admin/agent-guide.md:66,108` (and `:67,68,106` for `/epics/`) — a 124-line file about
  deleted agents, owned by the separate `docs/` sweep. **Out of scope, and that is a real seam**:
  until that sweep runs, one operator-facing doc still points at both frozen trees. The Goal
  section is worded to admit this rather than claim the replacement surface is fully stood up.

**PII coverage after the move — corrected.** An earlier draft claimed "archived ideas stay
PII-skipped: `.project/archive/` is already in `SKIP_PATHS`." That conflated the two instruments
and was **false** (spec review, P1). `SKIP_PATHS` governs only the PATTERN scanner
(`src/safety/pii_patterns.py`). The doc-PII **byte-gate** is a separate instrument, and
`scripts/check_doc_pii.sh` excludes exactly ONE subtree — `.project/archive/agent-memory/`
(`:169-171`) — not `.project/archive/` broadly. `tests/test_doc_pii_hook.py` codifies both legs:
`.project/ideas/…` is gated today (`:148`), and ordinary `.project/archive/…` content stays gated
(`:210`, the narrowness control). So the truth is: **ideas are byte-gated before the move and
byte-gated after it. Coverage is unchanged, not removed.**

### 4. The concept survives — `.project/specs/IDEAS.md`

Create it **empty**: a heading and one line saying what it is and how it is worked. One line per
idea thereafter. No template, no numbering, no statuses, no index. Curated at the per-3-chunk
audit; an entry becomes a spec only when the operator decides to work it. The frozen tree is
history — salvage on demand, never bulk-migrated.

**The PII gain is real but NARROW, and must be stated narrowly** — an earlier draft overclaimed it
(spec review, P1). Both trees are, and were, covered by the doc-PII byte-gate. What IDEAS.md adds
is the second instrument: `.project/specs/` is **not** in `SKIP_PATHS`, so the pattern scanner runs
on it, which the ideas tree never had. Per `.claude/rules/pii-safety.md:54`, that buys
**credential / email / phone** coverage and **nothing against names** — and names are the class
that actually bit (the IDEA-096 capture, a real minor's name, remediated in E-254 Phase-4b).

So: a genuine improvement, in a class orthogonal to the one failure on record. Write it that way in
the file, and do not let it read as "ideas are now safe."

Two CLAUDE.md amendments come with it:

- **Principle B** — discovered work exits as a spec stub only when it is BROKEN or OWED; a "might
  want someday" exits as one line in IDEAS.md.
- **Principle F** — the audit's housekeeping sweep covers IDEAS.md as well as the spec files.

The three-way split must be stated so it cannot blur: **broken or owed → a spec stub; someday →
IDEAS.md; product direction → `docs/vision-signals.md`.** That third channel is unchanged by this
chunk, and `.claude/rules/vision-signals.md` is not edited.

### 5. Templates

Delete all four. `research-spike-template.md` is epic-shaped like the other two (`E-NNN-R-SS`,
links to `../E-NNN-slug/epic.md`); `idea-template.md` has no apparatus left to template.

Add `.project/templates/spec-template.md`, **≤30 lines**, whose FIRST line is the no-real-names
instruction pointing at the placeholder taxonomy in `.claude/rules/api-docs.md`. Sections mirror
lifecycle step 1 exactly: Status/Date header, goal, files, out-of-scope, verification commands,
progress log. Status values are step 9's: `COMPLETE (this commit)`, `PARKED + why`, `STUB`,
`OPEN + what decision is owed`.

Known and accepted: `.project/templates/` is in `SKIP_PATHS`, so the template file itself is not
PII-scanned. It carries no data, and its instruction is aimed at the specs written FROM it, which
are scanned.

### 6. `specs/done/`

Create the directory and record the rule in `.project/specs/README.md`: at handoff, a spec whose
Status you just flipped to COMPLETE moves to `.project/specs/done/` in the same commit. Everything
still open stays in the live directory — that is exactly what principle F's audit has to see.

Spec review corrected three things here.

**(a) This spec moves too (P1).** Step 7 flips Status to COMPLETE before staging, so by its own
rule this spec lands in `done/` in the same commit — **seven files move, not six**. An earlier
draft moved six and then wrote verification counts that assumed otherwise. Verification steps 3, 4
and 6 are corrected accordingly, and step 6 dogfoods the review script against a spec that STAYS
live, not this one.

**(b) `RULED` is a fifth status the vocabulary does not admit (P2).** An earlier draft listed it
among the statuses that stay live, which would have frozen the contradiction. **Ruled by the
operator: retire it, keep four, re-status the three specs — see §10.**

**(c) Plain `git log` does NOT follow the rename (P2).** An earlier draft claimed it did, so step
9's "no hash needed, `git log` on the spec supplies it" would have quietly broken for every moved
spec. Verified by direct construction in a scratch repo: after a `git mv`, `git log -- <newpath>`
shows only the move commit; `git log --follow -- <newpath>` shows the full history. The
`.project/specs/README.md` entry for `done/` **must spell `--follow`**, and CLAUDE.md step 9's
clause must not promise more than plain `git log` delivers. This is the difference between a
convention and a convention that works.

### 7. CLAUDE.md byte budget — the tightest constraint in this chunk

**Measured 2026-08-08: 10,955 bytes against the 11,264-byte cap. 309 bytes of headroom.** The
README's standing residual says 10,585; that number is stale — step 2's own rewrite consumed the
difference.

Five edits are owed:

| Edit | Direction |
|---|---|
| step 2: delete "The legacy codex-spec-review skill needs an epic dir; don't use it." | ≈ −68 |
| step 9: add the `specs/done/` clause | ≈ +40 |
| principle B: replace the stub sentence with the stub-vs-IDEAS split | ≈ +60 |
| principle F: extend housekeeping to IDEAS.md | ≈ +30 |
| **principle I (NEW): caps are tripwires** | ≈ +175 |

Net ≈ **+235 bytes** against 309 of headroom, landing near **11,190 of 11,264 — roughly 70 bytes
to spare.** These are estimates, easily ±50 in aggregate; EXECUTE measures rather than trusts them.
`wc -c CLAUDE.md ≤ 11264` is an acceptance criterion, not a courtesy check.

Principle I is an **operator-directed promotion**, recorded because the provenance matters: principle
E's "promote a lesson to a rule only after it bites twice, at the audit, never mid-flight" binds the
SESSION, not the operator. No session inferred this rule into existence.

**Principle I is also the edit most likely to breach the cap it describes**, which is the correct
kind of problem to have and is flagged here deliberately rather than discovered mid-edit. Draft, to
be written to the byte:

> **I.** A cap is a TRIPWIRE, not a wall: when one binds against load-bearing content, stop and
> bring the operator the trade. Never compress meaning to fit; never raise a cap yourself.

If the measured total overruns, **EXECUTE does not compress its way back under** — it stops and
surfaces the trade per that very principle. Applying the rule to its own landing is the point, not
an irony to be engineered around.

**The cap is a TRIPWIRE, not a wall (operator ruling, 2026-08-08).** Never raise it unilaterally —
it exists to stop the drift back toward a 20KB always-on file, and raising it silently is the
failure it was built to prevent. But never cut bone to meet it either. If landing this chunk would
force deleting or compressing a **load-bearing** sentence anywhere in CLAUDE.md, **STOP and bring
the operator the specific trade** — which sentence, what it protects, what the alternative costs.
The operator raises the cap deliberately or cuts something themselves. **Bytes never outrank
meaning.** Tightening genuinely loose wording is fine and needs no ruling; trading away a rule that
earns its place is not a session's call.

### 8. Rewrite the codex-spec-review triad

**`scripts/codex-spec-review.sh`** — argument becomes a spec FILE path; the `epic.md` requirement
and the directory resolution go. Adopt the receipt shape `scripts/codex-review.sh` already uses:
tee the Codex output to a deterministic `RESULT_FILE` and print `RESULT_FILE=<path>`, its `wc -l`,
and its `tail -n 1`. That receipt is the whole reason to keep a script rather than a bare `codex
exec`: it is what stops a session triaging off a truncated Bash preview — the failure that once
mischaracterized four valid findings as "2 LOW already-adjudicated" off a ~2KB preview of a ~373KB
result. Today's spec-review script has no tee at all, so it is the weaker of the two twins. The
clean-result sentence becomes spec-shaped ("No findings. This spec is ready to execute."), and
`RUNTIME CONTEXT NOTE FROM PM` loses the role name.

**`.claude/skills/codex-spec-review/SKILL.md`** — prerequisites and both execution paths resolve a
spec file; the epic-not-found / no-`.md`-files / epic-is-archived edge cases go; the read-receipt
gate is re-pointed at the script's `RESULT_FILE` instead of instructing a manual re-run with a
redirect (the manual redirect is the documented fabrication hole — 44 of 48 invocations skipped
it). Triggers drop `E-NNN`. Keeps `disable-model-invocation: true`.

**`.project/codex-spec-review.md`** — rewrite the rubric for a one-page spec.

- **Drop** the categories that exist only for multi-story epics: §2 cross-story dependency
  sequencing, §3 file-conflict and parallel execution, §4 story sizing and vertical slicing, §8
  per-story Definition of Done, and the three epic-level categories §10 internal consistency, §11
  propagation completeness, §12 AC surface area. Drop the Facts Table preamble with them — it is
  built to catch drift ACROSS story files.
- **Keep and re-aim**: §1 (verification commands concrete and observable), §5 (scope correctness,
  including the two destructive seams by name), §6 + §9 merged into one claims-versus-repo-reality
  category, §7 narrowed to the two surviving domain agents.
- **Keep substantially as written**: §9b, safety absolutes without an attempted counterexample.
  It is the one category with a documented kill record, and its examples stay because they are
  evidence, not decoration.
- **Add**: does the spec name its out-of-scope; does it carry a progress log; does it name a person.
- Reporting cites the spec's heading rather than a story ID and AC label. The re-review protocol
  loses `PM` (lines 92, 94).

**`.claude/skills/workflow-help/SKILL.md`** — re-list spec review in the cheat sheet and delete the
"`codex-spec-review` is deliberately absent … Add it back when Step 3 rewrites its input
resolution" paragraph (`:74-76`). This chunk is what closes it.

### 9. Rule trims

- `.claude/rules/documentation.md` — drop `epics/**` from `paths:`. Nothing else changes; line 43's
  "(or epic ID, for older entries)" is a correct historical note and stays.
- `.claude/rules/canonical-seams.md` — drop `epics/**` from `paths:`.
- `.claude/rules/ideas-workflow.md` — deleted in §3.

### 10. Retire the `RULED` status — RULED: retire it (operator, 2026-08-08)

Spec review found the vocabulary and the practice disagreeing. CLAUDE.md step 9 and
`.project/specs/README.md:7-8` enumerate FOUR statuses — COMPLETE, PARKED, STUB, OPEN — but three
live specs read `RULED`, all written 2026-08-08 when the parked decisions were settled. Writing the
`specs/done/` rule would have frozen the contradiction.

**Operator ruling: keep the vocabulary at four; re-status the three specs.** So CLAUDE.md and the
README need NO change here — a real byte saving against §7's budget, which had provisionally
costed the alternative.

All three are the same shape — ruled, queued, not started — and the live directory already holds
the precedent for it: `2026-08-04-identifier-validity-audit.md` reads "PARKED — funded by the
operator, not started". All three take **PARKED**, and each `why` must carry the ruling forward
verbatim in substance. **Preserving the ruling wording is the whole risk of this option; a status
line rewritten into vagueness loses a decision the operator made.** Re-read each body afterward and
confirm the ruling is still recoverable from the file alone.

| Spec | New status line (`PARKED + why`) |
|---|---|
| `2026-08-04-docs-api-redacted-prefix-corpus.md` | PARKED — rule RELAXED, scrub CANCELLED: real team/org/game ID prefixes are acceptable in `-REDACTED` placeholders, PERSON-scoped ids stay synthetic-only. The `api-docs.md` rule edit rides the PII-docs chunk; the measurement below stays as the record. |
| `2026-08-04-org-team-discovery-and-roster-ingest.md` | PARKED — bulk org discovery DECLINED (vision non-goal); the narrow opponent roster-recovery MEASUREMENT is funded and queued in README NEXT, not started. Design nothing unless the reach number is material. |
| `2026-08-05-rung-c-season-year-filter.md` | PARKED — BUILD ruled, queued in README NEXT as its own small chunk after Step 3, not started. Semantics settled: never cross-YEAR; same-year cross-season is fine; absent `season.year` REFUSES auto-accept (fail-closed); compare against `teams.season_year`. |

Recorded for the Step 4 rule pass, not acted on here: `PARKED` now carries two meanings — "set
aside indefinitely" and "ruled and queued". The README's NEXT section is what distinguishes them.
If that proves confusing in practice, Step 4 is where it gets looked at.

## Out of scope

- The `docs/` sweep for the retired workflow — a separate NEXT item (~110 references across 18
  files), which owns `docs/admin/agent-guide.md` and its ideas-tree references.
- The `api-docs.md` redacted-prefix rule relaxation — rides the PII-docs chunk by prior ruling.
- `src/safety/pii_patterns.py`, the frozen-archive invariant, the doc-PII byte-gate, and the
  `epics` entry in the hook's `GATE_TREES` loop. All deliberately inert, not edited.
- Bulk-migrating the 235 frozen ideas into IDEAS.md. It starts empty by ruling; salvage on demand.
- `.claude/rules/vision-signals.md` and `docs/vision-signals.md` — the third channel is unchanged.
- The `codex-review` skill vs. first-party `codex review` comparison — owed since Step 2, still
  carried forward rather than silently dropped.
- Any `src/`, `migrations/`, or product behavior change.

## Verification

Run in order. **Redirect pytest to a file and capture `$?` separately — never trust a piped exit
code.**

1. `ls epics .project/ideas` → both absent. `ls .project/archive | grep -c '^E-'` includes the five
   moved IDs; `ls .project/archive/ideas | wc -l` → **235** (234 ideas + README).
2. **Tracked-surface archive sweep, with a positive control.** For each of E-174, E-263, E-271,
   E-274, E-275: `git grep -nIF "epics/<ID>-" -- . ':!.project/archive'` returns nothing.
   **Prove the instrument can fail first**: plant one such string in a tracked file, confirm the
   sweep reports it, remove it, re-run clean. A sweep that has not been shown failing proves
   nothing (principle G).

   **State its scope honestly (spec review, P2).** This is NOT a like-for-like replacement of the
   retired gate. That gate read the WORKING TREE (`check_archive_refs.sh:38,97`), ignored files
   included; this reads TRACKED content only. The positive control proves tracked-file grep works —
   it says nothing about the ignored-worktree class. That narrowing is **deliberate and is the
   point**: reading ignored `.codex-home/` transcripts is precisely the defect that made the gate
   unusable, and an untracked session log is not a surviving reference. Call this a narrower
   tracked-surface sweep that is correct where the old gate was wrong — never "the substitute."
3. `wc -l .project/templates/spec-template.md` ≤ 30, and its first line carries the no-real-names
   instruction. `.project/specs/IDEAS.md` exists with no entries. `ls .project/templates` → exactly
   one file.
4. `ls .project/specs/*.md | wc -l` → **10** — 8 live specs + README + IDEAS.md;
   `ls .project/specs/done/*.md | wc -l` → **7**. (Arithmetic, stated so it can be checked: 14
   pre-existing specs + this one = 15; 15 − 7 moved = 8 live.) An earlier draft said 8 live and 6
   moved, having forgotten to count this spec on either side of the subtraction.
5. `bash -n .githooks/pre-commit` parses clean. A scratch commit touching only `.project/` prints
   `[pii-hook] PII scan passed.` — and its ABSENCE is the alarm, not its presence.
6. `./scripts/codex-spec-review.sh .project/specs/<a-spec-that-stays-live>.md` runs, prints a
   `RESULT_FILE=` line with `wc -l` and `tail -n 1`, and Codex reads the spec file. **Do not target
   this spec** — it moves to `done/` in this same commit, so its live path will not exist.
   `2026-08-05-rung-c-season-year-filter.md` is a good target.
7. No spec's STATUS LINE still reads `RULED`: `head -5` each of the three named specs and confirm
   the status line says `PARKED`. (A bare `grep RULED .project/specs/*.md` is the wrong instrument
   — this spec's own §10 discusses the status by name and will always match.) Then **re-read all
   three re-statused bodies** and confirm each ruling is still recoverable from the file alone —
   the status rewrite is where a decision gets lost, and no grep can see that.
8. `wc -c CLAUDE.md` → report the number; must be ≤ 11264.
9. **Full suite** — the chunk touches `scripts/` and `tests/`, so green is mandatory:
   `python -m pytest tests/ > /tmp/…/pytest.txt 2>&1; echo $?` then read the file for the RC and
   the pass/fail line. `test_archive_refs_gate.py` is gone; nothing else regressed.
10. `python3 src/safety/pii_scanner.py --staged`, comparing scanned-count to staged-count.
   `SKIP_PATHS` blinds it to whole trees — `.claude/`, `.project/archive/`, `.project/templates/`
   all appear in this diff. Give every skipped staged file a manual pass with a positive control,
   and note that a silent RC=0 under `.claude/` is vacuous, not clean.

## Progress log

- **2026-08-08** — Spec written. Audit findings recorded above: `epics/` is at the repo root; the
  README's "three deleted rules" residual is stale; the archive-refs gate is BLOCKED for all five
  IDs by gitignored `.codex-home/` session logs and cannot be satisfied again in this repo;
  `canonical-seams.md` and `docs/admin/operations.md` are in scope and were not named by the
  README; CLAUDE.md headroom is 309 bytes, not the 603 the stale README figure implies. Five
  operator rulings folded in.
- **2026-08-08** — Operator ruling: the CLAUDE.md cap is a TRIPWIRE, not a wall. Never raise it
  unilaterally, never compress load-bearing content to meet it; surface the trade instead. Folded
  into §7 and promoted, at operator instruction, to a NEW principle I (see §7 for the provenance
  note — principle E's promote-at-the-audit rule binds the session, not the operator).
- **2026-08-08** — **Codex spec review: COMPLETE.** Headless `codex exec`, receipt: 4,124 lines,
  last line "Several other cited facts did check out: `epics/` is at repo root, the archive-gate
  `.codex-home` hit counts match today, and `CLAUDE.md` is currently 10,955 bytes." Six findings,
  all read to completion and independently re-verified against the repo before disposition. **All
  six ACCEPTED — none dismissed.**

  | # | Finding | Disposition |
  |---|---|---|
  | P1-1 | §6 inconsistent about whether THIS spec moves to `done/`; verification counts and the step-6 target both wrong | **FIXED** — seven files move, not six; steps 4 and 6 corrected; step 6 retargeted to a spec that stays live |
  | P1-2 | §3/§4 falsified safety absolute: "archived ideas stay PII-skipped" conflated the pattern scanner with the byte-gate; the IDEAS.md gain was overstated | **FIXED** — coverage is UNCHANGED by the move (byte-gate covers both); the real gain is pattern-scanner coverage of credential/email/phone only, explicitly *not* names, the class that actually bit |
  | P2-1 | §3 understated live path references; missed `e274-…-consultation.md:8` and the `agent-guide.md` seam | **FIXED** — third repoint added to Files; Goal softened to admit the docs seam rather than claim a finished surface |
  | P2-2 | Verification step 2 is not a like-for-like substitute for the retired gate (tracked-only vs. working-tree) | **FIXED** — reframed as a narrower tracked-surface sweep that is correct where the old gate was wrong; scope stated, not implied |
  | P2-3 | `RULED` is a fifth status the vocabulary does not admit; and plain `git log` does NOT follow the rename | **FIXED + ESCALATED** — `--follow` verified by construction and now required in the README wording; the `RULED` vocabulary is an Open decision for the operator |
  | P3 | Stale counts: ideas 235-not-236, operations.md section runs to 1053-not-1046 | **FIXED** — both corrected (both had also been caught in-session before the review landed) |

  Self-caught in the same pass, before the review returned: the ideas off-by-one, the
  operations.md range, and the live-spec count. Recorded because the overlap is the useful signal —
  the review's unique contribution was the two P1s and the `git log --follow` falsification, none
  of which a self-review had surfaced.
- **2026-08-08** — Operator ruling on the one escalated finding: **retire `RULED`**, keep the
  vocabulary at four, re-status the three specs to `PARKED + why` (§10). CLAUDE.md and the README
  keep their four-status text unchanged, which returns the bytes §7 had provisionally costed for
  the alternative. Spec is complete and ready for commit approval.
