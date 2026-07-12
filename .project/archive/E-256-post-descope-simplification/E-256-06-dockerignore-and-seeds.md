# E-256-06: Add .dockerignore; delete the orphaned data/seeds surface

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## ⚠️ PM PRE-DISPATCH REVIEW (2026-07-09)
PM ran the two checks the AC-3b precedent now requires: **(1) does the deliverable produce a reviewable diff, and (2) can the implementer and reviewer actually satisfy each AC?**

**(1) PASSES.** Unlike story 03's ghost directories, every deliverable here is tracked: `.dockerignore` is a new file, `Dockerfile:38,41` and `.gitignore:40-41` are tracked lines. PM confirmed all three citations are current (`Dockerfile:38` = `RUN mkdir -p ./data/seeds && chown -R appuser:appuser ./data`; `:41` = `COPY data/seeds/ ./data/seeds/`; `.gitignore:40-41` = the `!data/seeds/` negations). **The untracked `data/seeds/seed_dev.sql` is correctly NOT a deliverable** — the Technical Approach already says "left alone or noted," which is exactly the AC-3b disposition, arrived at independently. `data/` does not exist in the worktree at all.

**(2) FAILS on two ACs, and they must be rewritten before they are graded.**
- **AC-1's second clause** ("*and a `docker build` succeeds without them present in context*") and **AC-4** in full ("*Given a fresh `git clone`, when `docker compose build` is run…*") **cannot be executed by SE or verified by CR.** `.claude/rules/worktree-isolation.md` forbids `docker compose` in the epic worktree, and there is no Docker there. An implementer reporting AC-4 green would be reporting a check it did not run; a reviewer confirming it would be certifying the same. **This is the closed-loop defect's sibling: an AC whose verification is unavailable to everyone who must grade it.**
- **Rewrite, effective now:**
  - **AC-1** (SE-satisfiable): a `.dockerignore` exists at the repo root excluding at least `.env*`, `data/`, `.git/`, `__pycache__/`, `*.pyc`. Verified by reading the file — a static, reviewable artifact.
  - **AC-4** (NOT SE's, NOT CR's): the fresh-clone `docker compose build` is an **operator/closure verification**, discharged either by story 09's CI `docker build` stage (the durable mechanism, which is why 09 is blockedBy 06) or by the operator at closure. SE MUST NOT report it; CR MUST NOT certify it. **PM records it as a closure obligation.**

**One surface the story does not name.** `.gitignore:38` carries the comment *"but commit seed SQL files (data/seeds/ is source-controlled)"* — a **false statement** (§9's forensics: the file was never tracked) sitting directly above the negations AC-3 deletes. Deleting `:40-41` and leaving `:38` would strand a comment asserting the opposite of the new state. **AC-3 extends to `:38`.** Found by reading the lines around the cited ones, not by grepping the cited ones — the same move that surfaced story 05's fourth consumer.

## Description
After this story is complete, the repo has a `.dockerignore` that keeps `.env`, the live DB, and `.git` out of the Docker build context, and the orphaned `data/seeds/` deploy surface — which makes a fresh clone's documented deploy dead on arrival — is fully removed rather than resurrected.

## Context
Two independent fixes are bundled here because both concern the Docker build context and a fresh clone. No `.dockerignore` today means `.env`, the live DB, and `.git` all ship to the daemon as build context — one careless `COPY . .` from baking secrets into layers. Separately, `data/seeds/` is not in git despite `.gitignore` claiming it is, and `Dockerfile:41`'s `COPY data/seeds/` breaks any fresh clone. Git forensics settle the direction (Technical Notes §9): `seed_dev.sql` was **never tracked**, so committing it would resurrect ~21 KB of demo data E-228 deliberately removed and contradict the `bb db reset` empty-DB invariant. Fix = delete the orphaned surface, not commit the file.

## Acceptance Criteria
> **AMENDED IN PLACE 2026-07-09 (PM, pre-dispatch).** The original text of AC-1 and AC-4 is preserved below as struck-through, because it is the record of what was specified. **The amended text is authoritative.** Rationale in the PM Pre-Dispatch Review block above.

- [x] **AC-1** (amended THREE times — see below): Given the repo root, when this story is complete, then a `.dockerignore` exists whose patterns exclude from the build context:
  - **at any depth** — environment files (`.env` and variants) and Python bytecode/build artifacts (`__pycache__/`, `*.pyc`, `*.pyo`, `*.egg-info/`);
  - **at the context root, deliberately** — the live data tree (`data/`) and the VCS directory (`.git/`), per AC-5.3.

  Verified by reading the file. Literal spellings are illustrative, **not** the criterion.
  - ~~**Amendment 3** (round 3): "…exclude from the build context, **at any depth**: environment files, the live data tree, the VCS directory, and Python bytecode."~~ — **struck: it contradicted AC-5.3**, which mandates `data/` and `.git/` be root-anchored *on purpose*. Read literally, AC-1 then FAILED on two of its four items against an artifact that is correct. **"At any depth" was the right fix for the wrong scope**: it cures the string-vs-effect defect for env files and bytecode, and over-corrects `data/`/`.git/` from *a string nobody meant* into **an effect nobody wants**. CR's repair, adopted verbatim. **This is the THIRD generation of the same object inside one story** — `.gitignore:38` (a comment asserting the opposite of the truth), amendment 2 (a criterion checkable and false), amendment 3 (a criterion whose literal reading contradicts a sibling AC). *The story keeps regenerating the defect it exists to delete, one layer up each time.*
  - ~~**Amendment 1** (pre-dispatch): "…and a `docker build` succeeds without them present in context."~~ — struck: not executable in the epic worktree (no Docker); reassigned to AC-4.
  - ~~**Amendment 2** (round 2): "…excludes at least `.env*`, `data/`, `.git/`, `__pycache__/`, and `*.pyc`."~~ — **struck: AC-1 and AC-5 were in literal contradiction.** AC-5 mandates deleting the exact strings this clause mandated keeping (`__pycache__/` → `**/__pycache__/`; `*.pyc` → `**/*.pyc`). CR graded PASS on effect, FAIL on letter, and it was right on both. **This was CR's own diagnosis materialized as a spec defect**: *"excluding at least `__pycache__/`" specifies a string, not an effect.* The original phrasing was the main session's and CR's, carried through PM's amendment unexamined; it survived six stories only because nothing changed the spelling. **It is `.gitignore:38` at the spec layer — an acceptance criterion a reader can check against the file and find false — written into the very story that exists to delete such an object.** Restated above in terms of effect.
- [x] **AC-2**: Given the Dockerfile, when this story is complete, then the `COPY data/seeds/` at `Dockerfile:41` is deleted; the `chown` at `Dockerfile:38` keeps its non-`/seeds` components (the `/seeds` component is dropped); and the runtime bind-mount comment noting the shadow is preserved or corrected. **Extended (PM):** the `# Copy seed data …` comment immediately above the deleted `COPY` goes with it.
- [x] **AC-3**: Given `.gitignore`, when this story is complete, then the dead `!data/seeds/` negations (lines ~40-41) are deleted. **Extended (PM):** so is the false comment at `:38` (*"but commit seed SQL files (data/seeds/ is source-controlled)"* — never true; §9), and `:37`'s sentence is repaired where `:38` was its continuation.
- [~] **AC-4 — REASSIGNED, NOT UNMET.** ~~"Given a fresh `git clone`, when `docker compose build` is run, then it succeeds with no missing-`data/seeds/` failure."~~ **This AC is not gradeable by the implementer or the code-reviewer**: `.claude/rules/worktree-isolation.md` forbids `docker compose` in the epic worktree and no Docker exists there. **SE MUST NOT report it; CR MUST NOT certify it.** It is discharged either by story 09's CI `docker build` stage (the durable mechanism — this is *why* 09 is blockedBy 06) or by the operator at closure. **Carried on both the PM and main-session closure lists.** An unchecked box here means *reassigned*, not *unfinished*.
- [ ] **AC-5** (PM, from CR's SHOULD FIX — *fix the promise AND the patterns*): Given that Docker anchors an unprefixed pattern at the context root, when this story is complete, then **`.dockerignore` no longer promises more than it delivers**:
  1. The artifact patterns become recursive: `**/__pycache__/`, `**/*.pyc`, `**/*.pyo`, `**/*.egg-info/`. Today `__pycache__/` matches only a *top-level* directory, so `src/gamechanger/loaders/__pycache__/` still enters the context via `COPY src/ ./src/` — including, per story 03, `.pyc` for source that no longer exists. Its section header ("regenerated inside the image") is false for the nested case.
  2. **`.env*` becomes `**/.env*`.** Root-anchored is a latent hole: a `.env` created anywhere under `src/` would ride `COPY src/` into a layer. Zero cost, and CLAUDE.md's Security Rules make this the one pattern that must never be narrower than the COPY it guards.
  3. The **deliberately root-anchored** patterns (`data/`, `secrets/`, `proxy/`, `ephemeral/`, `.git/`) get a one-line comment saying so. There is exactly one `data/` and anchoring is the intent — but a reader cannot distinguish *intended* anchoring from *overlooked* anchoring, which is precisely how this defect arrived.

  **Why this is a MUST once written down.** The file's own preamble reads *"what it keeps out can be read off the patterns directly."* That is the sentence a future reader will trust, and it is currently false. **This story exists in part to delete a `.gitignore` comment that asserted the opposite of the truth** (`:38`). Shipping a `.dockerignore` whose preamble makes a promise its patterns don't keep is the same defect, introduced in the same commit that removes the old one. CR's diagnosis is the general form: **`"excluding at least __pycache__/"` specifies a string, not an effect** — an AC anyone can grade that doesn't mean what it says. The exact inverse of AC-4's ungradeable criterion, and the same decoupling of satisfaction from the property wanted.
- [ ] **AC-6** (PM, from CR's disproof of "not feasible"): Given that a **build-breakage** test is feasible and non-circular even without a daemon, when this story is complete, then `tests/` contains a test asserting **no `.dockerignore` pattern excludes any `COPY` target**, where:
  - The target list is **parsed from the `Dockerfile`** at test time — a source `.dockerignore` did not produce. **Do not hardcode the four targets**; a hand-written list makes the enumeration and the guard share an author, which is the closed loop this epic keeps producing.
  - ~~The matcher may be Python's `fnmatch`, and the test's docstring MUST record why that is sound: **`fnmatch`'s `*` crosses `/` while Docker's does not, so `fnmatch` is strictly more permissive; a "no match" under `fnmatch` therefore implies "no match" under Docker.** The check is conservative in the safe direction… Without that note a future reader will "fix" the matcher and invert the guarantee.~~
  - **AMENDED (round 2) — the rationale above is FALSE for the `**/` patterns AC-5 introduces in the same commit, and PM mandated it verbatim.** `fnmatch` has **no `**` concept**: it collapses `**` to a single `*`, which already crosses `/`, so `fnmatch.translate("**/x")` yields a regex **requiring** a literal slash, while Docker's `**/` spans **zero** segments. On `**/` patterns `fnmatch` therefore **under**-matches, and *"no match under `fnmatch`" does NOT imply "no match under Docker."* A `**/`-prefixed pattern naming a COPY target (`**/src/`) is invisible to the guard: the build breaks and the test stays green. Not a live bug — the shipped file has zero collisions — but **a guard that will not fire when it matters.**

    **The corrected mandate.** The matcher may be `fnmatch`, but it MUST expand `**/` to also match zero segments, and the docstring MUST record **both axes**:
    1. **Patterns without `**`**: `fnmatch`'s `*` crosses `/` and Docker's does not, so `fnmatch` **over**-matches. A no-match implies a no-match. Conservative in the safe direction.
    2. **Patterns with `**/`**: `fnmatch` **under**-matches (zero-segment case), so the helper MUST special-case it. Only after that expansion does "no match ⇒ no match" hold.

    Pin `('**/src/', 'src/', True)` as a test case. **Delete the "do not fix the matcher" instruction**: for `**/`, a matcher *more* faithful to Docker matches *more* and **closes** the hole. That sentence told the next reader to leave the defect in place — *a false comment sitting above true code, the same defect class as `.gitignore:38`, introduced in the commit that deletes it.* AC-6's own words were "*without that note a future reader will 'fix' the matcher and invert the guarantee*"; **the note inverted the guarantee itself.**

    `fnmatch` still may never be asked to *certify* an exclusion — the one thing it cannot do (`fnmatch("data/app.db", "data/")` is `False` though Docker excludes it). Neither check asks it to.
  - Falsifying input, to be demonstrated: adding `src/` to `.dockerignore` makes the test fail.
  - **This is the only executable guard this file will ever have without a Docker daemon.** A *security* test (does the built context omit `.env`?) remains infeasible here — that half of SE's "not feasible" stands.

## PM Circuit-Breaker Accounting (2026-07-09)
**This is ROUND 1 against the amended six-AC story.** SE's prior pass satisfied all four ACs it was given; both gates passed it; CR then retracted its approval on its own initiative because the spec had grown underneath it. AC-5 and AC-6 originate from CR's review and PM's rulings — **not from an SE failure.**

**The general rule PM is setting, so this is not an ad-hoc reset:** the 2-round circuit breaker counts **failures against a given acceptance criterion**, not rounds against a story. It exists to catch an implementer that cannot converge on a fixed target. When PM widens scope mid-story the target changed, and the counter for the *new* ACs starts at zero.

Four guards keep that from being gameable:
1. **Per-AC counting.** If SE fails the *same* AC twice, that is two strikes regardless of what else was added. AC-1/2/3 are closed and cannot be re-opened to launder a strike.
2. **Origin test.** A reset applies only when the new ACs originate **outside the implementer's control** (a reviewer's finding, a PM ruling). An AC added because SE's own work revealed the spec was wrong does *not* reset — that is convergence, and it is counted.
3. **Declared at the moment of widening, never retroactively.** PM records the reset when the AC is added. A reset claimed *after* a failure is not a reset.
4. **The story-level ceiling survives.** Regardless of per-AC counters, a story exceeding three total rounds is surfaced to the user. The breaker guards against non-convergence; the ceiling guards against churn.

AC-6's test is a novel artifact nobody has written before. A defect in it on the next pass is a **normal round-1 finding**, not a second strike.

## PM AC-Verification Round 3 (2026-07-09)
**AC-1 (effect-stated) PASS. AC-5 PASS. AC-6 PASS.** AC-2/AC-3 undisturbed; AC-4 correctly not evaluated.

- **AC-1 PASS on the amended effect.** Read `.dockerignore`: env files excluded at any depth (`**/.env*`, root form kept belt-and-braces); `data/` root-anchored, which is correct — there is exactly one; `.git/`; bytecode/build artifacts recursive (`**/__pycache__/`, `**/*.pyc`, `**/*.pyo`, `**/*.egg-info/`). The restated AC is gradeable against the file rather than against a snapshot of the file's former spelling.
- **AC-5 PASS, beyond the ask.** ANCHORING preamble present and correct; `**/.DS_Store` caught unprompted; the credentials group carries the "must never be narrower than the COPY it guards" rationale; data/VCS/runtime groups carry `ROOT-ANCHORED ON PURPOSE`.
- **AC-6 PASS.** `tests/test_docker_build_context.py`: COPY targets **parsed** from the Dockerfile; **both non-vacuity guards** present (non-empty AND exactly four AND `src/` present; plus a pattern-list guard); `_excludes` performs the zero-segment expansion; the docstring records **both axes** with `fnmatch.translate` evidence inline; `('**/src/','src/',True)` and four siblings pinned; and `test_bare_fnmatch_would_miss_the_zero_segment_case` pins the defect so the expansion cannot be deleted as dead code. The "do not fix the matcher" instruction is correctly **narrowed to Axis 1**, where it is true, and paired with its opposite for Axis 2.

**ACCEPTED RESIDUE — graded SHOULD, explicitly NOT a MUST, explicitly NOT ceiling-triggering.** Two groups retain the intended-vs-overlooked ambiguity AC-5 clause 3 exists to remove:
1. `.dockerignore:41-60` — header reads *"Python build/run artifacts. RECURSIVE"*, but its last four members (`.venv/`, `.uv-cache/`, `.pytest_cache/`, `.ruff_cache/`) are **root-anchored**. A reader takes the header as covering them.
2. `:77-81` (compose/Docker group) carries **no anchoring note** at all.

Neither names a COPY target, neither is a security pattern, neither changes any effect AC-1 requires. **PM rules this does not reopen the story.** If CR sends a round for another reason, fold in two comment lines; otherwise carry as a closure note. At pass 3 of 3 the cost of another round exceeds the cost of two imprecise comments — and saying so explicitly is better than pretending not to have seen them.

**FOURTH TAXONOMY ENTRY (SE), and it is the one that would have caught this epic's own failure.** PM's three describe a **green** result carrying no information (closed loop / empty enumeration / ungradeable criterion). SE's describes a **red** result carrying no information:

> *"A guard is not verified by its falsifying input passing — it is verified by running that input against the guard **without** the fix. Input A alone would have shown me a red test; only the pre-fix control shows me the test was blind before."*

SE reverted `_excludes` to the broken matcher in a shadow copy and confirmed `test_no_ignore_pattern_excludes_a_copy_target` **stayed green** with `**/src/` present. The defect executed rather than being argued. **A falsification cannot distinguish "the fix works" from "this input was always red."** Generalizes past tests: the main session's staging check, CR's diffstat, story 02's grep — each a control never run against a known-bad input. **A control you have never seen fail is a control you have never seen.**

**THE RELAY-INTEGRITY GAP.** SE: *"A relayed reason is not a checked reason, and a docstring is a load-bearing claim about code, not commentary on it."* PM wrote the AC, CR authored the argument, the main session carried it, SE carved it into a docstring — four agents, one unfalsified claim, surfaced only because CR re-derived it against a file AC-5 had changed. `dispatch-pattern.md`'s relay rule forbids relaying content one has not **read**; reading was never the failing step. It is silent on relaying an **argument** one has not **checked**. PM's *"an amendment is a re-authoring"* is the same rule from the spec side. **Both reduce to: the last person to sign it owns it.**

## Technical Approach
Delete, do not commit — see Technical Notes §9 for the forensics. This is a **single-owner SE story** (repo-root build/ignore files only). Per CA's Q1 routing rule, the `docs/admin/architecture.md:67` seeds-line correction (a `docs/admin/` edit, docs-writer's domain) is **factored OUT of this story into story 10** (the docs-writer docs/admin story) — it is NOT an AC here. The stale on-disk `seed_dev.sql` (untracked) can be left alone or noted; it is invisible to git and harmless once the COPY is gone.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-09 (CI runs `docker build`, which needs `.dockerignore` and a clean fresh-clone build)

## Files to Create or Modify
- `.dockerignore` (create)
- `Dockerfile` (lines ~38, ~41)
- `.gitignore` (lines ~40-41)
- (NOT `docs/admin/architecture.md` — the seeds-line correction is story 10's, per Q1 routing.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-09**: a clean fresh-clone `docker build` that the CI workflow's `docker build` stage depends on.

## Definition of Done
- [ ] All acceptance criteria pass
- [x] Tests written and passing — **"where feasible" EVALUATED, and the answer is two-part** (CR, refining SE): a **security** assertion (does the built context omit `.env`?) is **infeasible** without a Docker daemon, and any pytest-level assertion about `.dockerignore`'s *contents* would be a set-membership test whose set is the file itself — the closed loop. But a **build-breakage** assertion is **feasible and non-circular**: it draws its target list from the `Dockerfile`, a source `.dockerignore` did not produce, and has a real falsifying input. **AC-6 is that test.** Recorded here so the archive shows this line evaluated rather than forgotten.
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Committing the seed file would contradict the documented `bb db reset` empty-DB invariant (`.claude/rules/data-model.md`). Deletion is the settled direction.
