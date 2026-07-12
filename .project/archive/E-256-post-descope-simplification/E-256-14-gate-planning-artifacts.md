# E-256-14: Gate planning artifacts with the doc-PII byte-gate

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, the pre-commit hook runs `scripts/check_doc_pii.sh` (the literal-identifier denylist byte-gate) against staged `epics/` and `.project/` trees, closing the committed-artifact PII gap for the identifier class the pattern scanner structurally cannot detect (names, UUIDs, public_ids). This is the promotion of **IDEA-102**.

## Context
This is flow-review item 12b, and it **promotes IDEA-102** (`.project/ideas/IDEA-102-committed-artifact-pii-gap.md`, whose "cheapest lever" open question is exactly this). The two PII gates catch **disjoint classes** (Technical Notes §6): the pattern scanner matches shapes (hence the `epics/`/`.project/` noise that put them in `SKIP_PATHS`), the byte-gate matches literal known identifiers (never noise in a committed file). So the byte-gate adds coverage over the planning trees **without a single false positive** — and `SKIP_PATHS` stays unchanged. Two design rulings are settled: exit-code disposition (Technical Notes §7) and the index-vs-working-tree hazard requiring a `git checkout-index` wrapper (Technical Notes §8).

## Acceptance Criteria
- [ ] **AC-1**: Given the pre-commit hook, when a commit stages files under `epics/` or `.project/`, then the hook runs `scripts/check_doc_pii.sh` against those staged trees via a `git checkout-index --prefix="$tmp/" -a` snapshot into a `mktemp -d` (so the gate judges the INDEX, not the working tree — Technical Notes §8), invoking the script once per tree and aggregating exit codes.
- [ ] **AC-2**: Given the exit-code disposition (Technical Notes §7), when the hook runs the byte-gate, then: exit 0 passes and emits `[doc-pii: REAL, 0 matches]`; exit 1 (denylisted identifier present) **BLOCKS**; exit 2 (self-test/malformed) **BLOCKS** (fail closed); exit 3 (denylist absent → EXAMPLE MODE) **announces loudly (`[doc-pii: INCONCLUSIVE — example mode]`) and does NOT block**.
- [ ] **AC-3**: Given `scripts/check_doc_pii.sh`, when this story is complete, then it is **NOT modified** — no `--staged` mode, no multi-tree argument; its single-directory contract, self-test, and four exit codes all survive (the wrapper lives in the hook, per Technical Notes §8).
- [ ] **AC-4**: Given `src/safety/pii_patterns.py`, when this story is complete, then it is **NOT modified** — `SKIP_PATHS` still contains `epics/` and `.project/` (Technical Notes §6); a `git diff` shows zero changes to that file.
- [ ] **AC-5**: Given a fresh clone with the denylist absent (the default, since `secrets/pii-denylist.txt` is gitignored), when a commit stages a planning artifact, then the hook does not block it (exit 3 announced) — the fresh clone remains committable.
- [ ] **AC-6** (PM-amended pre-dispatch, 2026-07-10): Given a staged planning artifact containing a denylisted identifier and a present denylist, when the commit is attempted, then the hook blocks it (exit 1).

  **⚠️ MANDATORY — do NOT satisfy this AC with a real identifier.** Read literally, AC-6 asks you to write a **real denylisted identifier** (a real name, UUID, or `public_id`) into a test fixture in order to prove the gate keeps real identifiers out. **That commits the exact PII the gate exists to prevent, in the test for the gate.** It is a closed loop of the most literal kind, and it would be caught only by the gate it is testing — after the commit.

  **Use the mechanism the repo already ships:** set `PII_DENYLIST_FILE` to a temporary denylist containing a **fabricated** identifier, or use the committed fake-sentinel `scripts/pii-denylist.example.txt`. The staged artifact under test carries the **same fabricated** identifier. Never `secrets/pii-denylist.txt`; never a real identifier — not in a fixture, not in a heredoc, not in an assertion message, not in a test name.

  **AC-5 has the mirror-image hazard and is safe by construction**: it asserts the *absence* of a denylist (exit 3), so it needs no identifier at all. If satisfying AC-5 requires you to write one, you have misread it.

## Technical Approach
CA designs the hook wrapper (per `feedback_domain_expert_designs`). The `git checkout-index` snapshot is the load-bearing design element — a working-tree grep in a commit hook is a false-pass hazard worse than the exit-3 inconclusive (Technical Notes §8). The hook lives in `.githooks/pre-commit` (where `.githooks/pre-commit:21` already runs the pattern scanner via `--stdin`). Cleanup the `mktemp -d` (`rm -rf`) unconditionally.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-09 (the CI story's AC-2 states the byte-gate is a local-hook gate NOT run in CI — that boundary must be settled here first)

## Files to Create or Modify
- `.githooks/pre-commit` (add the byte-gate wrapper)
- A test under `tests/` exercising the hook's exit-code disposition — **add one if the disposition is isolable** (a hook shelling `git checkout-index` + `check_doc_pii.sh` is subprocess-testable per `.claude/rules/testing.md`, so the exit-3-does-not-block / exit-1-blocks behavior should not ship untested)
- **NOT** `scripts/check_doc_pii.sh` (AC-3), **NOT** `src/safety/pii_patterns.py` (AC-4)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-256-09**: the settled "byte-gate is a local pre-commit gate, not a CI gate" boundary that the CI story's AC-2 records.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `check_doc_pii.sh` and `pii_patterns.py` unmodified (AC-3, AC-4)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
On completion, IDEA-102's status flips to PROMOTED with a link to E-256 (PM handles the idea-file + README update at plan time).
