<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# PII scanner hardening — `--staged` enumeration bypasses + the inert `epics/` entries

**Date**: 2026-08-10 · **Status**: `READY`
**Source**: `.project/specs/README.md` STANDING RESIDUALS — the `pii_scanner.py --staged` rename blindness
(found 2026-08-08, Step 3) and the inert `epics/` entries in the two security controls, which that residual
explicitly routes through this chunk.

## Goal

`src/safety/pii_scanner.py --staged` enumerates the same staged set the pre-commit hook does, closing two
documented bypasses in one function: a rename (including a move-AND-edit) is scanned, and a path git C-quotes
is scanned. Each fix lands behind a RED test proven failing first. Riding with it, the two `epics/` entries
that can no longer match come out of `SKIP_PATHS` and `GATE_TREES` together with every restatement of them,
leaving the doc/code agreement correct in its new state.

## Why this matters (verified, not inherited)

`--staged` is not a convenience path. Two things run it:

- `CLAUDE.md` step 6 tells **every session** to run `python3 src/safety/pii_scanner.py --staged` by hand.
- `.claude/hooks/pii-check.sh:35` runs it as a **PreToolUse gate on every agent `git commit`**.

`get_staged_files()` (`src/safety/pii_scanner.py:353`) enumerates with `git diff --cached --name-only
--diff-filter=ACM` and splits the result on newlines. `.githooks/pre-commit:98` enumerates the same set with
`--diff-filter=ACMR` **and** `-z`, and lines 83-95 of that file document why each is load-bearing. The hook is
unaffected by both bugs, so *committed* content is still gated — the gap is in the by-hand command and the
agent hook.

Measured on the Step 3 commit and recorded in the line of march: `ACM` enumerated **17** paths where `ACMR`
enumerated **284** — 267 renames invisible, including a move-AND-edit git scored `R099`.

### Audit of the inherited claims — done in the spec session, do not re-inherit

**Line-number drift.** `README.md:148` cites `src/safety/pii_scanner.py:320`. On disk the `--diff-filter=ACM`
is at **line 353**. Content confirmed, citation stale — the file grew when the extensionless-scannability fix
landed 2026-08-09. `README.md:78`'s `.githooks/pre-commit:125` for `GATE_TREES` is accurate.

**The doc/code coupling claim.** `README.md:81-83` says the `epics/` entries "must move WITH
`.claude/rules/pii-safety.md:50,52,54`, which restates `SKIP_PATHS` accurately as the code stands today.
Editing either side alone breaks a doc/code agreement that is currently correct." Read against disk, **the
three cited lines are not equivalent and the claim is over-broad**:

- **`:54` — CONFIRMED, this is the real coupling.** "the pre-commit `pii_scanner` has `epics/` and the four
  legacy `.project/` subdirs (`archive/`, `ideas/`, `research/`, `templates/`) in `SKIP_PATHS`" is a direct,
  currently-true restatement of `src/safety/pii_patterns.py:188`. Removing the code entry without this line
  falsifies the doc. The same line also instructs "When authoring `.project/**` or `epics/**`, never paste
  real names" — an authoring rule for a tree that cannot be authored.
- **`:52` — WEAKER than claimed.** It is a section heading ("Coverage footgun — planning/idea/epic artifacts
  are UNGATED"). Removing a `SKIP_PATHS` entry makes "epic" vestigial; it does not falsify a heading. Edit for
  coherence, not correctness.
- **`:50` — the claim is FALSE here; LEAVE THE LINE.** Its two `epics/` mentions are (a) historical
  provenance — the archive-reference gate "was removed with the `epics/` freeze on 2026-08-08" — and (b) an
  illustrative nested-lookalike path (`epics/E-999/.project/archive/agent-memory/…`) demonstrating that the
  exclusion prefix is anchored at position 1. Neither restates `SKIP_PATHS` or `GATE_TREES`; neither becomes
  false. Illustration (b) is mirrored verbatim at `scripts/check_doc_pii.sh:57`, a file this chunk does not
  touch, so editing one side would *create* a divergence. And `README.md:168-171`'s own criterion-vs-evidence
  rule says historical records stay as written. **Editing `:50` would be the defect, not the fix.**

**Three restatement sites the residual did not name**, found by sweeping by FILE then reading
(`.claude/rules/tool-discipline.md`). Each is a `SKIP_PATHS`/`GATE_TREES` restatement that goes false:
`.githooks/pre-commit:118`, `.github/workflows/ci.yml:84`, and the test assertions in step 4 below.

**`epics/` is genuinely inert.** `git ls-files epics` returns zero paths and `ls -d epics` reports no such
directory. Nothing can be staged under a tree that does not exist, so neither entry can match.

## Files

- `src/safety/pii_scanner.py` — edit: `get_staged_files()` enumeration (two fixes + the comment that explains
  them).
- `src/safety/pii_patterns.py` — edit: drop the `epics/` entry from `SKIP_PATHS`, and the sentence of its
  comment block that justifies it.
- `.githooks/pre-commit` — edit: drop `epics` from the `GATE_TREES` loop (`:125`); correct the comment at
  `:118`.
- `.github/workflows/ci.yml` — edit: correct the `SKIP_PATHS` restatement in the PII-sweep comment (`:84`).
- `.claude/rules/pii-safety.md` — edit: `:54` (the `SKIP_PATHS` restatement + the authoring instruction),
  `:52` (heading), and the "Scanner capabilities" section (`:19` area) to record the hardened enumeration.
  **`:50` is NOT edited.**
- `tests/test_pii_scanner.py` — edit: two new RED tests; retire the five `epics/` skip-path assertions;
  correct two stale `--diff-filter=ACM` docstrings.
- `tests/test_doc_pii_hook.py` — edit: retarget every `epics/` staging fixture to a live `.project/` path.
- `.project/specs/README.md` — edit at step 9: strike both residuals, add the stubs below.
- `.project/specs/2026-08-10-pii-scanner-hardening.md` — this file: Status flipped at step 7 so it rides the
  commit, then `git mv`-ed into `.project/specs/done/` in that same commit at step 9.

## The work

### 1. RED tests first (both must be proven failing before any `src/` edit)

The template already exists: `tests/test_doc_pii_hook.py:517`
`test_rename_with_edit_introducing_credential_blocks`. **Two things carry over, both load-bearing:**

- **Build the credential at runtime by concatenation** — the existing test uses
  `credential = "GC_REFRESH_TOKEN=" + "z" * 40`. A credential-shaped *literal* in the test source trips the
  scanner on this very file at commit time, and `.project/specs/` is itself scanned, which is why this spec
  states the fixture the same way. Never reach for a suppressor here (remedy #1: change the data).
- **Assert the precondition that git actually scored the change `R`** —
  `git diff --cached --name-status` must start with `R`. Without it, a change scoring below the rename
  threshold stages as an `A`, which `ACM` already catches, and the test passes **vacuously** without
  exercising the enumeration it exists to pin.

Both new tests are unit-level against `get_staged_files()`, following `TestStagedBlob*`
(`tests/test_pii_scanner.py:1054-1123`): `_init_git_repo(tmp_path)` + `monkeypatch.chdir(repo)`, then assert
on the returned list and on `scan_staged_files(staged)`.

- **Test A — rename-plus-edit carrying a planted token.** Seed and commit a file; `git mv` it; append the
  runtime-built credential to the destination; stage. Assert the `R` precondition, then assert the
  destination path is in `get_staged_files()` and that `scan_staged_files` reports one
  `api_key_assignment` violation on it. **Pre-fix this FAILS**: `ACM` drops the `R`, the returned list is
  empty, and no violation is produced.
- **Test B — hostile filename.** Parametrized over `rép.md`, `a"b.md`, `a\b.md` (the three classes
  `tests/test_doc_pii_hook.py:486-487` already pins for the hook). Stage a new file at that path holding the
  runtime-built credential; assert the path is returned exactly and the violation is reported. **Pre-fix this
  FAILS**: `--name-only` without `-z` C-quotes the path, so the returned string names no readable file and
  `git show :<quoted>` cannot resolve it.

The three hostile-filename classes are the ones `tests/test_doc_pii_hook.py:486-487` already parametrizes for
the hook (`test_hostile_filename_still_blocks`) — reuse that list rather than inventing one.

Record each test's pre-fix outcome **individually** — never an aggregate count
(`.claude/rules/testing.md`, mutation protocol).

### 2. The two enumeration fixes

In `get_staged_files()` (`src/safety/pii_scanner.py:353`):

- `--diff-filter=ACM` → `--diff-filter=ACMR`. `--name-only` reports a rename's **destination** path, which is
  the path to scan. `D` stays excluded.
- Add `-z` and split the output on `\0` instead of `str.splitlines()`, dropping the trailing empty field.
  Keep the existing `.strip()`-free contract at the call sites (`scan_staged` already strips per path).

Update the function's docstring — it currently says "(Added, Copied, Modified only)" — and the `--staged`
argparse help string at `:411`, which says the same. Add a comment carrying the *reason* for each flag, in
the shape `.githooks/pre-commit:83-95` uses; a bare flag with no rationale is what let the two enumerations
drift apart in the first place. Note in it that this is the **second** time an `ACMR` fix has had to be
applied to a sibling enumeration (the hook's was 2026-07-28) — recorded as a finding in
`.project/research/2026-08-08-migration-audit-3.md:41`.

### 3. The `epics/` removals, all sides together

- `src/safety/pii_patterns.py:188` — remove `"epics/"` from `SKIP_PATHS`. The TN-2 comment block above it
  justifies the *legacy `.project/` subdirs* as well, so trim only what named `epics/`; the measured 43-match
  noise rationale still covers the surviving entries and must stay.
- `.githooks/pre-commit:125` — `for tree in epics .project` → `for tree in .project`. The loop, the
  `GATED -ne ${#GATE_TREES[@]}` counter, and the literal-prefix `case` all keep working unchanged with one
  tree.
- `.githooks/pre-commit:118` — "The pattern scanner skips epics/ and .project/" → `.project/` only. (This
  comment is *also* wrong in a second way that predates this chunk: the scanner skips four legacy `.project/`
  subdirs, not `.project/`. Correct it while here.)
- `.github/workflows/ci.yml:84` — "SKIP_PATHS (epics/, the four legacy .project/ subdirs, lockfiles, ...)"
  → drop `epics/`.
- `.claude/rules/pii-safety.md:54` — drop `epics/` from the `SKIP_PATHS` restatement and from the authoring
  instruction. `:52` — drop "epic" from the heading. **Do not touch `:50`.**

**`.project/ideas/` stays.** The sweep found it is also inert (no such directory; ideas now live at
`.project/specs/IDEAS.md`, history at `.project/archive/ideas/`). Operator ruling 2026-08-10: the asymmetry is
real — `epics/` can never return, `.project/ideas/` plausibly could, and the re-measured noise rationale still
covers it. Carried as a stub, not removed.

### 4. Test fallout — MUST-FIX in this commit

Per `.claude/rules/testing.md` ("when you change a production contract, stale tests are MUST-FIX"), not a
follow-up.

- `tests/test_pii_scanner.py:533-612` — five assertions that `should_skip_path("epics/…") is True`
  (`test_epics_path_skipped`, `test_epics_nested_path_skipped`, `test_epics_file_skipped`,
  `test_scan_file_skips_epics_path`, and the `TestEpicsPathExclusionIntegration` class name/docstrings). These
  go RED on the removal. Retire the `epics/`-specific ones rather than inverting them to
  `is False` — an assertion that a nonexistent tree is *not* skipped pins nothing. Keep and rename the class
  so the surviving legacy-`.project/` coverage is not lost.
- `tests/test_doc_pii_hook.py` — roughly ten sites stage `epics/E-999-demo/epic.md` as the `GATE_TREES`
  fixture, including the class at `:146` asserting "both planning trees are gated". Every one must retarget to
  a live `.project/` path. **Retarget to `.project/research/` or `.project/archive/`** — both exist on disk.
  **Not `.project/ideas/`** (inert; would pin a phantom path). **Not `.project/archive/agent-memory/`** — the
  frozen-archive invariant at `.githooks/pre-commit:36` would block the fixture before the byte-gate ran.
  Re-word the `:146` docstring: it is now one gated tree, not two.

  ⚠ **A rejected reason, corrected — do not re-derive it.** The spec-review draft rejected `.project/specs/`
  on the grounds that the pattern scanner, which does not skip that tree, would fire on the fixture first and
  make the test pass vacuously. **That claim is FALSE and was refuted by reproduction** (codex spec review,
  2026-08-10): the fixture identifier is `FAKE_TOKEN` at `tests/test_doc_pii_hook.py:24`, a fabricated
  sentinel matching none of the scanner's four regex classes. Staging it under `.project/specs/` scans clean
  (`Scanned 1 file(s), 0 violations.`) and the doc-PII byte-gate — the intended instrument — is what blocks.
  `.project/specs/` is therefore *admissible*; `.project/research/` remains merely **preferred**, because it
  is in `SKIP_PATHS` and so keeps exactly one gate in play on the path under test, which matters for the
  hostile-filename fixtures (`a"b.md`, `a\b.md`) where you want to know unambiguously which gate blocked.
  Preference, not prohibition.
- `tests/test_pii_scanner.py:1089,1112` — docstrings naming `--diff-filter=ACM`. The `:1112` staged-deletion
  test **still passes** (`D` is excluded by `ACMR` too); this is a stale-comment fix, not a behavior change.
  Say so in the progress log so a reviewer does not read it as an untested behavior change.

### 5. Record the hardened behavior

`.claude/rules/pii-safety.md`, "Scanner capabilities" section: `:19` describes `--staged` blob reading without
saying anything about how the staged set is *enumerated*. Add the enumeration contract (`ACMR` + `-z`) and why
each half is load-bearing, so the next drift between this function and the hook is visible in the rule.

## Step 5 — review experiment (operator protocol, verbatim)

This chunk carries a measurement. Run it as written; the criterion is pre-registered on purpose.

> Review experiment, protocol matters: freeze the staged diff, then run ALL arms against that same frozen
> state BEFORE fixing anything — collect findings, then fix once. (Chunk 10 fixed between passes, which
> muddied the overlap measurement.) Arms: (a) bare headless `claude -p "/code-review"` — diff-only context;
> (b) enriched headless — same, but the prompt instructs it to read the spec and the line of march first;
> (c) operator-typed `/code-review`; (d) operator-typed `/security-review`; (e) the codex layers as usual.
> Then classify every finding: which arms caught it, and is it in-diff or an interaction with unchanged code.
> Verdict in the progress log.
>
> Decision criterion, stated before the data: if enriched-headless catches everything the typed review catches
> on this chunk, step 5 automates for ordinary code chunks and typed reviews get reserved for
> destructive/security surfaces. If the interaction-class gap persists even with the spec fed in, typed stays
> for all `src/` chunks and we stop wondering.

Arms (c) and (d) are **operator-typed and are two separate messages** — a session cannot invoke either, and
one line runs only the first. Stop and ask. Feeds Audit 4.

## Out of scope

- **`.project/ideas/` in `SKIP_PATHS`** — inert, deliberately left (operator ruling above). Stub at step 9.
- **`.dockerignore:71` and `AGENTS.md:8`** still name `epics/`. Neither restates these two constants, so
  neither goes false here. `AGENTS.md:8` is retired-workflow residue belonging to that sweep's lineage.
- **`scripts/check_doc_pii.sh:57,166`** mention `epics` illustratively (a nested-lookalike path; "pointing the
  gate at `epics` yields no exclusion"). Both stay true. Editing them would diverge from
  `pii-safety.md:50`, which mirrors `:57`.
- **`.claude/rules/pii-safety.md:50`** — audited, claim refuted, left as written. See above.
- **Widening the scan surface** — `migrations/*.sql`, `requirements.in`, `*.conf`, non-dotfile templates like
  `docker-compose.override.yml.example`. A standing residual and a policy call, not a bug fix.
- **IDEA-112** (suppressor narrowing) and **IDEA-102** (gating planning artifacts against NAMES). The
  `epics/` removal does not touch the name-detection gap, which is what actually bit.
- ⚠ **CI's whole-tree PII scan is RED on `main` right now — surfaced by this chunk's `/code-review`,
  2026-08-10, and NOT introduced by it.** The 2026-08-09 dotfile/extensionless widening made `.env.example`
  scannable, and it carries three `email` matches. Reproduced with CI's exact command:
  `git ls-files -z | xargs -0 python3 -m src.safety.pii_scanner` → **RC=123**, three `[PII BLOCKED]` lines on
  `.env.example` (`:182` our own `noreply@` service address; `:279`/`:283` two `USER:PASS@host` proxy-URL
  FORMAT comments, where the email regex matches the `PASSWORD@host` fragment). Under `pipefail`,
  `.github/workflows/ci.yml:95` fails on the next push. **This collides with a standing operator ruling.**
  `.project/specs/README.md:104-108` records "Operator ruled: LEAVE, no suppressor" for these exact three
  matches — read and confirmed to hold no credential and no person's address — but states the consequence as
  only "staging `.env.example` will trip the hook." The CI half was not named, so the ruling was made against
  half the consequence. **Owed: an operator decision, not a session fix**, and it is not this chunk's to make
  — it touches neither `get_staged_files()` nor the `epics/` entries. Remedy #1 (reword the placeholder data:
  `USER:PASS@host`, an RFC 2606 or `PLACEHOLDER_EMAILS` address) remains the right instrument if the ruling
  moves; a suppressor inside a credential template is still the wrong one.
- **`tests/fixtures/*.sql` are outside the scan surface, and the standing residual does not name them.**
  `README.md:113-117` records `migrations/*.sql` as a known policy call; the same `SCANNABLE_EXTENSIONS` gap
  leaves `tests/fixtures/seed.sql`, `parity_consistent.sql`, and `recon_scoreboard_seed.sql` unscanned. Seed
  fixtures are the higher-risk half — a plausible landing spot for a real player name or email, the same class
  that once put a real minor's name in a planning file. Widen the residual's wording when it is next touched.
- **The stale `codex-spec-review` rubric.** `.project/codex-spec-review.md:48` still enumerates FOUR spec
  statuses and calls a fifth a finding, but `READY` was added 2026-08-09 by operator ruling and is documented
  in `CLAUDE.md` step 9 and `.project/specs/README.md:8-12`. The rubric was not updated with it, so it flags
  every `READY` spec — as it flagged this one. The **rubric** is stale, not this spec's Status; correcting it
  is a one-line docs edit that does not belong inside a security-control chunk. Stub at step 9.

## Verification

Redirect pytest to a file and capture `$?` separately — never trust a piped exit code
(`.claude/rules/tool-discipline.md`).

1. **Positive control, before any `src/` edit.** With `get_staged_files()` unmodified:
   `python -m pytest tests/test_pii_scanner.py -k "rename_with_edit or hostile" > /tmp/red.txt 2>&1;
   echo "RC=$?" >> /tmp/red.txt` — read the file. Expected: **both new tests FAIL**, reported per-test, with
   the failure being an empty/mis-quoted enumeration rather than an error in the fixture. A test that fails
   for a fixture reason proves nothing.
2. **Targeted green, after.** `python -m pytest tests/test_pii_scanner.py tests/test_doc_pii_hook.py >
   /tmp/targeted.txt 2>&1; echo "RC=$?" >> /tmp/targeted.txt` — expected `RC=0`, and the retargeted
   `test_doc_pii_hook.py` fixtures still block on a planted denylist identifier (that suite's own positive
   control — a retarget that silently stopped gating is the failure mode to rule out).
3. **Full suite.** This touches `src/` and `tests/`, so: `python -m pytest tests/ > /tmp/full.txt 2>&1;
   echo "RC=$?" >> /tmp/full.txt` — expected `RC=0`. Read the file for the RC and the pass/fail line.
4. **Enumeration differential, on a STAGED state you construct.** The earlier draft of this step asked for a
   historical-commit diff (`<ref>^ <ref>`) and was **not runnable** — `get_staged_files()` reads the current
   INDEX only and cannot be pointed at an arbitrary commit, and the carried 17-vs-284 figure was a
   staged-state measurement, not a reproducible commit object (codex spec review, 2026-08-10). Construct the
   state instead, in a scratch repo: seed and commit a file, `git mv` it, edit the destination, `git add -A`.
   Then, against that one index, compare all three:
   `git diff --cached --name-only --diff-filter=ACM | wc -l`,
   `git diff --cached --name-only --diff-filter=ACMR | wc -l`, and `len(get_staged_files())`.
   Expected: `ACM` = 0, `ACMR` = 1, and `get_staged_files()` = 1 returning the **destination** path — the
   post-fix function agrees with `ACMR`, not with `ACM`. Do not carry the 17-vs-284 numbers forward as a
   verification target; they are the historical motivation, not a reproducible expectation.
5. **The hook still passes.** `bash .githooks/pre-commit` behavior is covered by suite 2, but confirm at
   commit time that `[pii-hook] PII scan passed.` prints. **Its ABSENCE is the alarm** — if missing, stop and
   investigate.
6. **Step 6 scan, reconciling THREE counts.** `python3 src/safety/pii_scanner.py --staged` on its own prints
   only `[pii-scan] Scanned N file(s), 0 violations.` — a COUNT, never the path list
   (`src/safety/pii_scanner.py:474`), so it cannot by itself show which paths were enumerated (codex spec
   review, 2026-08-10). Run it **with the companion** `git diff --cached --name-only` and reconcile three
   numbers: staged paths, scanned count, and the `done/` move. Step 9 moves this spec into
   `.project/specs/done/`, which is a **rename** — historically invisible to this exact command, and the
   reason the scanner-rename-gap has bitten every closing chunk. After this fix the destination path must
   appear in the staged enumeration; if it does not, that is a finding, not a convenience.
   `SKIP_PATHS` still blinds the scanner to `.claude/` entirely, so give every staged `.claude/` file (this
   chunk edits `.claude/rules/pii-safety.md`) a manual pass with a positive control — a silent RC=0 there is
   vacuous, not clean.

## Progress log

- **2026-08-10** — Spec written (lifecycle steps 1-2). Plan-mode audit resolved both inherited claims against
  the repo: the `pii_scanner.py:320` citation had drifted to `:353`, and the "`pii-safety.md:50,52,54` all
  restate `SKIP_PATHS`" claim is over-broad — `:54` confirmed, `:52` cosmetic, `:50` refuted and left alone.
  The sweep also found three restatement sites the residual did not name (`pre-commit:118`, `ci.yml:84`, and
  the two test files) plus a third inert entry (`.project/ideas/`). Operator rulings: fold the `-z` fix in
  (two bypasses, one function, one security review, both RED tests required); leave `.project/ideas/` and
  record the stub; embed the step-5 review experiment verbatim with its criterion pre-registered.
- **2026-08-10** — `./scripts/codex-spec-review.sh` run; `RESULT_FILE` read in full (5 findings: 3×P2, 2×P3).
  **Four folded in.** (1) P2 — verification step 4 was not runnable: it asked `get_staged_files()` to read a
  historical commit, which it cannot; rewritten as a constructed staged state comparing `ACM` / `ACMR` /
  `get_staged_files()` against one index, and the 17-vs-284 figures demoted from expectation to motivation.
  (2) P2 — verification step 6 named a command that prints a COUNT, not paths; a `git diff --cached
  --name-only` companion added. (3) P2 — **my stated reason for rejecting `.project/specs/` as a test
  retarget was false**, and codex refuted it by reproduction: the fixture sentinel matches no scanner regex,
  so the tree scans clean and the byte-gate blocks as intended. Claim corrected in place with the refutation
  recorded; `.project/research/` demoted from prohibition to preference, with the real reason (one gate in
  play on the hostile-filename paths). (4) P3 — this spec file added to the Files list for the step-7 status
  flip and the step-9 `done/` move. **One NOT taken:** P3 on `Status: READY` — the rubric
  (`.project/codex-spec-review.md:48`) lists four statuses and predates `READY`'s addition on 2026-08-09;
  codex flagged the conflict itself. The rubric is stale, not the Status. Recorded as a stub instead.
- **2026-08-10** — Operator-typed `/code-review` run on the branch range (it swept `origin/main...HEAD`, 9
  commits, wider than this chunk's spec-only staged diff; full suite re-run green, 4471 passed). Four
  findings. **Two were mine and are fixed**: two line citations in this spec had drifted —
  `.githooks/pre-commit:119`→**118** and `tests/test_doc_pii_hook.py:490`→**486-487** — both verified against
  the repo before correcting, and a follow-up grep found **three more occurrences** of the stale numbers that
  a single edit would have missed. That this spec's own audit section treats citation precision as
  load-bearing, and then carried three stale citations, is itself the lesson: line-anchored references rot,
  and grep-after-edit is the only thing that catches the copies. **Two were outside this chunk and are
  stubs** (see Out of scope): the live CI break on `.env.example`, and `tests/fixtures/*.sql` sitting outside
  the scan surface. A third finding (a wasted `POST /search` round-trip in `opponent_ladder._resolve_via_search`
  when the member season year is NULL) belongs to the rung-(c) chunk, not this one — `IDEAS.md` material.
