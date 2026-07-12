# E-256-09: CI workflow (the static gate)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, a single `.github/workflows/ci.yml` runs the static half of the project's gates on push: pytest, a case-insensitive PII sweep, a lockfile-drift check, and `docker build`. The workflow explicitly documents what it **cannot** absorb — the credentialed populated-DB smoke — so that boundary is not silently reopened.

## Context
No CI exists; the full-suite gate and PII scan are process/per-machine only. The suite is ~79s (SE's upgraded-stack run was `3849 passed`), has zero secrets, and is fully mockable. The explicit boundary matters: `AGENTIC-FLOW-REVIEW.md` proposes "wire `smoke_test.py` into CI or delete it" — a **false binary** (Technical Notes §5). `smoke_test.py` needs a live app + credentials so it cannot run in CI, and it is prescribed in a runbook so it must not be deleted; it STAYS as a manual operator step. The CI workflow must record that verdict. Also: the doc-PII byte-gate (story 14) is a local-commit-hook gate, not a CI gate — CI would always be in EXAMPLE MODE (denylist gitignored), so CI runs the **pattern scanner only** (Technical Notes §7).

## Acceptance Criteria
- [ ] **AC-1**: Given a push, when the workflow runs, then it executes, as separate steps that each fail the build on failure: (a) `pytest`, (b) the case-insensitive PII **pattern scanner** invoked with an **explicit file enumeration** so it actually scans (a bare `python -m src.safety.pii_scanner` with no args prints help and exits 0 — a no-op, `pii_scanner.py:404-406`; use a checked-out-tree enumeration such as `git ls-files -z | xargs -0 python -m src.safety.pii_scanner` or the `--stdin` file-list form, NOT `--staged`, which is the pre-commit mode with no staged set on a CI checkout), (c) a lockfile-drift check (recompile and diff, or `pip-compile --dry-run` equivalent), and (d) `docker build`.
- [ ] **AC-2**: Given the PII step, when the workflow runs, then it invokes the **pattern scanner only** and does **not** invoke `scripts/check_doc_pii.sh` — with a comment in the workflow stating why (the byte-gate needs the gitignored denylist absent on runners, so it would always exit 3/EXAMPLE MODE; it is a local pre-commit gate).
- [ ] **AC-3**: Given `scripts/smoke_test.py`, when this story is complete, then the workflow records the **keep-not-delete, not-in-CI** verdict and its reason (live app + credentials required; runbook-prescribed) **as a comment in `ci.yml`** (SE-owned; NOT a `docs/admin/` note — per Q1 routing, this story does not edit docs/admin), so the false binary is not reopened.
- [ ] **AC-4**: Given the lockfile-drift check, when the committed `requirements.txt` is out of sync with `requirements.in`, then the workflow fails; when they are in sync (as story 07 leaves them), it passes.
- [ ] **AC-5**: Given `docker build` in CI, when it runs, then it succeeds against a fresh checkout (relies on story 06's `.dockerignore` + removed `data/seeds/` COPY).

## Technical Approach
One workflow file. Depends on story 06 (clean `docker build`), story 07 (drift-free lockfiles), story 08 (ruff clean — optionally add a ruff step), and story 14 (so the byte-gate-vs-CI boundary is settled before AC-2 is written). Keep the workflow minimal and mockable — no credentials, no live services. Do not attempt to run `bb report` or `smoke_test.py` in CI.

## Dependencies
- **Blocked by**: E-256-06 (`docker build`), E-256-07 (lockfiles), E-256-08 (ruff), E-256-14 (byte-gate/CI boundary)
- **Blocks**: None

## Files to Create or Modify
- `.github/workflows/ci.yml` (create) — the `smoke_test.py` keep-not-delete verdict lives as a comment here (NOT a `docs/admin/` note, per Q1 routing)

## Agent Hint
software-engineer

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (the workflow itself is the deliverable; verify it runs locally via `act` or by inspection)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
CI cannot absorb the credentialed populated-DB smoke — that stays with the code-reviewer at closure (Step 1d, story 11) and the operator post-deploy. State this in the workflow so the split is legible.
