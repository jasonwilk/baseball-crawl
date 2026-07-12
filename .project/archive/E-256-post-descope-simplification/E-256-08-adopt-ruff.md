# E-256-08: Adopt ruff (F-class)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

> **Status-hygiene note (PM, 2026-07-10):** this file was never flipped to `IN_PROGRESS` during dispatch — PM was never asked, and did not notice. The work is complete and both gates cleared; the intermediate state was simply never recorded. Recording the lapse rather than backdating it. Same class as the epic's standing lesson: *an artifact that was never updated is indistinguishable from one that was checked and found correct.*

## Description
After this story is complete, ruff is configured for the F-class (pyflakes) lint rules scoped to `src/` and `scripts/`, the 17 real F-class violations in `src/` are fixed, and the 6 false positives are resolved cleanly (via a `TYPE_CHECKING` block) rather than suppressed.

## Context
No lint tooling exists today. Technical Notes §12 has the counts: 17 F-class in `src/` (8 F401 unused-import, 5 F541 f-string-without-placeholders, 4 F841 unused-variable), 22 including `scripts/`. Repo-wide 96, of which 6 are false positives — F821 undefined-name in `tests/test_cli_creds.py`, all string return annotations paired with function-local imports, never evaluated at runtime; the clean fix is a `TYPE_CHECKING` block. **mypy is explicitly out of scope.** Two of the F841s are at `backfill.py:184-185`, which story 02 deletes — so they must already be gone when this story runs (hence the dependency).

## Acceptance Criteria
- [ ] **AC-1**: Given `pyproject.toml`, when this story is complete, then `[tool.ruff.lint]` selects `["F"]` only, scoped to `src/` and `scripts/`, with no mypy configuration added.
- [ ] **AC-2**: Given `ruff check src/ scripts/`, when this story is complete, then it reports **zero** violations.
- [ ] **AC-3** (PM-amended pre-dispatch, 2026-07-10 — **scope contradiction resolved, disposition (2)**): Given the F821 false positives in `tests/test_cli_creds.py` (e.g. `:199`, `) -> "ProfileCheckResult":` — a string return annotation paired with a function-local import, never evaluated at runtime), when this story is complete, then they are resolved via a `TYPE_CHECKING` block (**not** a `# noqa`).
  **`tests/` is outside AC-1's configured scope and outside AC-2's checked paths**, so AC-2's command cannot observe this fix. That is by design, not an oversight. AC-3 is therefore verified by an **explicitly out-of-scope command, named here so nobody has to invent one**: `ruff check tests/test_cli_creds.py --select F821` reports zero. **Do not widen AC-1's scope to make AC-3 gradeable** — §12 chose `src/` + `scripts/` deliberately, and `tests/` carries the bulk of the ~74 other repo-wide violations.
  The fix is real work: string annotations that resolve only via a function-local import are fragile, and the count is **not** to be trusted (see AC-6 — re-derive it; "6" was measured six stories ago).
- [ ] **AC-4** (PM-amended 2026-07-10 — **SE escalated; this is not lint**): Given `src/api/routes/auth.py:640-650`, when this story is complete, then the **whole nine-line block** is deleted — the comment at `:640`, the `existing_creds` declaration at `:641`, and the `try/except` that populates it — **and NOT before [`IDEA-121`](../../.project/ideas/IDEA-121-webauthn-exclude-credentials.md) exists**, which it now does. The deletion's commit trail MUST cite `IDEA-121`.
  ~~"…resolved by dropping the unused binding while preserving any side effect of the right-hand call."~~ — struck.

  **Disposition (b), and the ordering is the safeguard.** The RHS is pure (SE verified: a read-only `SELECT` comprehension), so the original instruction was technically satisfiable. It was also **wrong**, because the code says what it is for: `:640` reads *"Fetch existing credentials to exclude from registration options,"* and `generate_registration_options()` at `:652-662` **never receives them**. `grep -rn 'exclude_credentials' src/ tests/` → zero repo-wide; the library parameter exists. **A passkey registration meant to exclude already-registered credentials does not, and this block was the only in-code evidence of that intent.** Deleting it satisfies AC-2 and erases the bug report.

  **Not disposition (a).** Implementing `exclude_credentials` is a behavior change to the auth path, needing its own test and a client-side decision about the rejected-ceremony message. Under a lint story that is precisely the scope creep this story guards against.

  **Severity, stated honestly:** minor, security-adjacent, **not a vulnerability.** No authentication bypass; every credential still belongs to the correct user. A user can silently re-register an authenticator they already have, minting a duplicate row. IDEA-121 preserves the deleted code verbatim.

  **§12's protection was too narrow.** It shielded `starter_prediction.py` **by name** and left `auth.py` exposed to the identical hazard. **A guardrail written around one instance does not generalize to its class** — the class being *"a lint violation whose fix erases a design record."* That belongs in the closure item, not in a per-file exception list.
- [ ] **AC-5**: Given the full suite, when this story is complete, then it is green.
- [ ] **AC-6** (PM, pre-dispatch — **the baseline may not come from the certifying invocation**): Given that this story's gate is grep-shaped (`ruff check` reports zero), when the pre-existing violation set is enumerated, then it is derived from the **index blob** (`git show :<file> | ruff check --stdin-filename <file> -`, or an equivalent read of the staged tree), **never from the same invocation that later certifies the fix**. *A green `ruff check` on the working tree cannot distinguish "the violations are gone" from "ruff never saw them"* (CR). The enumeration comes from the index; the certification from the working tree.
  **Every count in Technical Notes §12 is a planning-time observation, not a current fact.** "17 F-class in `src/`", "4 F841", "6 F821", "22 including `scripts/`" were all measured before stories 01–05 deleted the disk flow, `bridge.py`, and `backfill.py`, and split `generator.py` into `lifecycle.py`. **Re-derive every number; report the derivation command.** A number carried forward from a tree that no longer exists is the epic's signature defect.
- [ ] **AC-7** (PM, pre-dispatch — *root-anchored-on-purpose, for lint scope*): Given that `tests/` is excluded from ruff's configured scope **deliberately**, when `pyproject.toml`'s ruff config is written, then it carries a comment saying so, with the approximate count of violations that widening would import. A reader cannot otherwise distinguish *intended* scope from *overlooked* scope — the identical ambiguity story 06's `.dockerignore` ANCHORING preamble exists to remove. Without it, the next person to widen the scope discovers the cost as a red build.

  **AMENDED 2026-07-10, after CR held a MUST FIX over PM's PASS.** The count MUST be **re-derived against the post-fix tree**, MUST NOT enumerate a violation class with **zero members**, and the comment MUST record both the derivation command and the fact that the obvious spot-check (`ruff check tests/`) reports **vacuously zero**, because `include` filters directory walks.

  **Why:** the first version asserted `~74 (48 F401, 16 F841, 6 F821, 2 F811, 2 F541)`. The six F821 were the ones **AC-3 resolved in the same commit**. `48+16+2+2 = 68`. The comment enumerated a class with **zero members** and quoted a widening cost that widening would not incur — **and the mechanic it documents is the one that hides its own error**, since anyone spot-checking the number the obvious way gets a vacuous green. Same shape as story 06's `.dockerignore` rationale falsified by AC-5 in the commit that introduced it.

  **PM verified that the comment STATED a measurement; PM did not verify the MEASUREMENT.** That is the closed loop one level up — I graded the artifact against the AC and never ran the AC's own arithmetic. CR's reason for overriding stands as precedent: *"I would otherwise apply a weaker standard than the one I asked PM to enforce against SE's `.dockerignore` header. The impact is smaller; the standard is not."* **A reviewer may hold a MUST against the AC-verifier's PASS, on a standard the AC-verifier established.** Recorded deliberately, because the alternative is a verifier who cannot be checked.

## PM RESOLUTION — the `starter_prediction.py` handoff (2026-07-10)
**Story 05 settled this. It is NOT ambiguous, and it does NOT come back to SE's judgment.** §12 required story 08 not to silently delete `latest_game_date` until story 05 had interpreted it. Story 05 did, with a citation: `83b5458 feat(E-214)` replaced `latest_game_date` with `reference_date` at every rest-calculation site, changed the parameter type, and **left the producing assignment behind**. `reference_date` **is** the correct anchor, pinned by `TestReferenceDateAnchorsReasoning` (asserts "9 days rest"; the old anchor yields 3).

PM re-verified in the current tree. Delete **all three** lines together:
- `starter_prediction.py:1125` — the comment `# ── Latest game date for rest calculations ──` (**false** since E-214; every rest calculation anchors on the caller-supplied `reference_date`).
- `:1126` — `all_dates = sorted(set(r["game_date"] for r in pitching_history))`
- `:1127` — `latest_game_date = all_dates[-1] if all_dates else ""`

**The part ruff cannot supply:** `:1126`'s `all_dates` is consumed **only** by `:1127`. Remove `:1127` alone and ruff sees `all_dates` as *used* on the pass that flags `latest_game_date`, then flags `all_dates` on the *next* pass. One-at-a-time. Delete both, plus the comment — *"an AC citing a line number specifies a cursor, not a lesion"* (CR).

**Do not touch `:869`.** There is a *second*, unrelated `all_dates` in this module (`:869`, inside a different function) which **is** used at `:873` and `:882`. A blind `all_dates` deletion breaks live code. This is exactly why the handoff was routed rather than left to a lint pass.

## Technical Approach
Fix violations rather than blanket-ignore. For AC-4, check whether the `existing_creds` assignment's RHS has a side effect before removing — if it does, keep the call and drop the binding; if pure, remove the statement. The two `backfill.py` F841s are not this story's concern (story 02 deleted the file). Adopt ruff as a dev dependency via the `*.in` workflow if it is not already present.

## Dependencies
- **Blocked by**: E-256-01, E-256-02, E-256-03, E-256-04, E-256-05, E-256-07 — ruff must lint the **final** `src/`/`scripts/` tree, so it runs after every story that mutates those trees (01 deletes the disk flow, 02 deletes backfill, 03 the dead-code sweep, 04 restructures generator.py + creates `lifecycle.py`, 05 the rest-day edit, 07 the dep bump that also touches `requirements-dev`). Otherwise a later story adds an unused import after the baseline is set and CI (story 09) catches it instead.
- **Blocks**: E-256-09 (CI may run ruff as part of the static gate — coordinate with story 09)

## Files to Create or Modify
- `pyproject.toml` (`[tool.ruff.lint]`)
- The ~17 `src/` files carrying F-class violations (unused imports, empty f-strings, unused vars)
- `tests/test_cli_creds.py` (`TYPE_CHECKING` block)
- `src/api/routes/auth.py` (line ~648)
- `requirements-dev.in`/`.txt` if ruff is added as a dev dep

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-09**: a clean `ruff check` the CI static gate can optionally run.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
mypy is deliberately deferred (epic Non-Goals). ruff F-class only for this pass.
