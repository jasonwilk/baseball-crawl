<!-- synthetic-test-data -->
# E-022: Safety Scan Hardening

## Status
`COMPLETED`

## Overview
Harden the pre-commit PII safety infrastructure (delivered in E-019) so that safety scans produce visible confirmation, agents structurally verify scans ran, the hook intercept pattern covers edge cases, and the scanner has integration tests proving the full hook chain works. The goal is to move from "assumed safe" to "verified safe" on every commit.

## Background & Context
E-019 delivered a two-layer pre-commit defense: a Git pre-commit hook and a Claude Code PreToolUse hook, both backed by a stdlib-only Python scanner at `src/safety/pii_scanner.py`. The infrastructure is configured and functional.

However, a recent commit (E-021 archive) exposed a confidence gap: the safety scan presumably ran but produced zero visible confirmation. No agent verified the scan executed. No output confirmed it. The scanner exits 0 silently on clean files, and neither hook prints anything on success. If the scanner had a bug, or if `--no-verify` was used, or if a hook did not fire for any reason, there would be no evidence of the gap.

The core problem is **silent success**. The hooks were designed to be loud on failure and invisible on success. That is the wrong default for a safety control -- safety controls should produce an audit trail on every invocation, not just on violations.

**Expert consultation**: claude-architect domain (hooks system, agent behavior). Key findings from reviewing the hooks knowledge base:
- PreToolUse hooks support `hookSpecificOutput` JSON with `permissionDecision` but the simplest confirmation path is through the scanner itself (both hooks call the same scanner).
- The PreToolUse `statusMessage` ("Checking staged files for PII...") provides spinner text but no completion confirmation.
- PostToolUse hooks exist and fire after tool success -- could be used for post-commit verification, but adds complexity beyond what is needed. Not recommended for MVP.
- Subagents spawned via Agent Teams inherit `.claude/settings.json` hooks (same project context). No gap there.
- Git worktrees inherit `core.hooksPath` from the main worktree config. No gap there.
- The `^git\s+commit` grep pattern in pii-check.sh misses git commit commands embedded in multi-command chains (e.g., `git add . && git commit -m "msg"`). This is a real gap.
- No native PreCommit/PostCommit hook event exists in Claude Code (feature request #4834 closed as "not planned").

## Goals
- The PII scanner prints a visible confirmation line on clean scans, so both hooks produce evidence the scan ran
- The git pre-commit hook produces visible output on every commit (success or failure)
- The Claude Code PreToolUse hook intercepts git commit commands reliably, including when chained with other commands
- CLAUDE.md git conventions remind agents to verify PII scan confirmation in commit output
- Integration tests prove the full git hook chain fires and blocks real violations
- The scanner's pattern detection is validated with targeted edge-case tests beyond the existing unit tests

## Non-Goals
- This epic does NOT add new PII detection patterns (that is a separate concern)
- This epic does NOT add CI/CD enforcement of the scanner
- This epic does NOT add PostToolUse hooks for post-commit verification (unnecessary complexity)
- This epic does NOT change the scanner's blocking behavior -- only its success output
- This epic does NOT add logging/persistence of scan results (audit log is a future concern)
- This epic does NOT address `--no-verify` bypass -- that is a legitimate escape hatch documented in `docs/safe-data-handling.md`

## Success Criteria
1. After a clean `git commit`, the terminal shows output like `[pii-scan] Scanned N files, 0 violations` -- visible evidence the scan ran
2. After a clean `git commit` through Claude Code, the agent sees confirmation that the PII scan completed successfully
3. The PreToolUse hook intercepts `git commit` commands whether they appear alone, in `&&` chains, or in `;` chains
4. CLAUDE.md Git Conventions section includes a reminder to verify PII scan confirmation
5. `pytest tests/test_pii_hook_integration.py` exits 0, proving the git pre-commit hook fires and blocks a staged file with PII
6. `pytest tests/test_pii_scanner.py` continues to pass with expanded edge-case coverage

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-022-01 | Add success confirmation to PII scanner | DONE | None | claude-architect |
| E-022-02 | Harden PreToolUse hook intercept pattern | DONE | None | claude-architect |
| E-022-03 | Add git commit workflow reminder to CLAUDE.md | DONE | None | claude-architect |
| E-022-04 | Integration tests for git pre-commit hook chain | DONE | E-022-01 | claude-architect |

## Technical Notes

### Scanner Success Output (E-022-01)
The scanner at `src/safety/pii_scanner.py` currently exits 0 with no output on clean scans. The change is to add a summary line to stderr on success:

```
[pii-scan] Scanned 5 files, 0 violations.
```

This line goes to stderr (like violation output) so it appears in terminal output for both hooks. The exit code remains 0. The format mirrors the existing violation summary (`N violation(s) found in N file(s)`).

The git pre-commit hook at `.githooks/pre-commit` should also print a confirmation banner:

```
[pii-hook] PII scan passed.
```

The PreToolUse hook at `.claude/hooks/pii-check.sh` does not need to change for success output -- the scanner's stderr output will be visible to the agent via the underlying git commit command's output (the git pre-commit hook's output is shown to the caller).

### PreToolUse Hook Intercept Pattern (E-022-02)
The current pattern in `.claude/hooks/pii-check.sh` is:

```bash
if ! echo "$COMMAND" | grep -qE '^git\s+commit'; then
```

This misses git commit when chained:
- `git add . && git commit -m "msg"` -- the full command is one string, git commit is not at the start
- `cd /path && git commit -m "msg"` -- same issue
- `git commit -m "msg"; git push` -- git commit IS at the start but this works

The fix: change from `^git\s+commit` (anchored to start) to an unanchored pattern that matches `git commit` anywhere in the command string, with appropriate word boundaries:

```bash
if ! echo "$COMMAND" | grep -qE '(^|[;&|]\s*)git\s+commit'; then
```

This matches git commit at the start of the command OR preceded by `;`, `&`, or `|` (the shell chaining operators). This covers `&&`, `||`, `;`, and `|` chains.

### CLAUDE.md Git Conventions (E-022-03)
Add one bullet to the existing Git Conventions section in CLAUDE.md:

```
- After committing, verify the `[pii-scan]` confirmation appears in the output. If it does not, the safety scan may not have run -- investigate before proceeding.
```

This is a lightweight advisory -- not a rule file, not a hook, not a blocker. It creates structural awareness in agents that read CLAUDE.md.

### Integration Test Strategy (E-022-04)
The existing `tests/test_pii_scanner.py` tests scanner functions directly (import and call). It does NOT test whether the git hook fires. An integration test should:

1. Create a temporary git repo with `git init`
2. Configure `core.hooksPath` to point to the project's `.githooks/` directory
3. Ensure the scanner is available (symlink or copy)
4. Stage a file with PII, attempt `git commit`, verify it is blocked
5. Stage a clean file, attempt `git commit`, verify it succeeds and the `[pii-scan]` confirmation appears in output

This test lives at `tests/test_pii_hook_integration.py` (separate from the scanner unit tests). It requires `git` to be available but no other external dependencies. Mark with `@pytest.mark.integration` so it can be skipped in fast test runs.

The test does NOT test the Claude Code PreToolUse hook (that requires a running Claude Code session and cannot be automated in pytest). It tests the git hook chain only.

### File Ownership by Story (for parallel execution safety)
| Story | Files Owned |
|-------|-------------|
| E-022-01 | `src/safety/pii_scanner.py`, `.githooks/pre-commit`, `tests/test_pii_scanner.py` |
| E-022-02 | `.claude/hooks/pii-check.sh` |
| E-022-03 | `CLAUDE.md` |
| E-022-04 | `tests/test_pii_hook_integration.py` (new file) |

E-022-01, E-022-02, and E-022-03 share no files and can execute in parallel. E-022-04 depends on E-022-01 (needs the success confirmation output to verify in the integration test).

## Open Questions
None. All design decisions are resolved based on the existing E-019 infrastructure and Claude Code hooks knowledge.

## History
- 2026-03-02: Created. Follows up on E-019 (Pre-Commit Safety Gates, COMPLETED). Expert consultation: claude-architect domain (hooks system review). Status set to READY.
