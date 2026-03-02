# E-006: Hard Data Boundaries and PII Protection

## Status
`ABANDONED`

## Overview
This epic ensures that personally identifiable information (PII) -- names, contact details, and other sensitive player and coach data -- can never be committed to the Git repository or pushed to GitHub, even accidentally. It establishes safe ephemeral storage for development data, a two-layer pre-commit scanning defense, and clear documentation so every agent and developer knows exactly where the boundary is.

## Background & Context
GameChanger API responses contain real PII: player names, parent contact information, coach phone numbers and emails. This data must live in Cloudflare D1 in production and in ephemeral local directories during development -- but it must never appear in a Git commit.

The risk is real: during iterative API exploration, it is natural to save raw JSON responses to disk for inspection. Without explicit guardrails, one of those files could be committed. A committed PII file becomes part of the permanent Git history and would need a destructive rewrite to remove.

Claude-architect has delivered a design document at `/.project/research/E-006-precommit-design.md` specifying the chosen mechanism: a two-layer defense using a native Git pre-commit hook (`.githooks/pre-commit`) and a Claude Code PreToolUse hook (`.claude/hooks/pii-check.sh`), backed by a stdlib-only Python scanner at `src/safety/pii_scanner.py`. All stories are now unblocked.

## Goals
- A `/ephemeral/` directory tree exists, is gitignored globally, and is organized by epic ID so developers know exactly where to put exploration data
- A written PII taxonomy defines what counts as PII in the baseball-crawl context and how to identify it in API responses
- A Git pre-commit hook actively blocks commits containing PII patterns (primary enforcement: fires for all developers and Git clients)
- A Claude Code PreToolUse hook provides agent-layer defense (fires before Git even starts when Claude is doing the committing)
- Both hooks call the same Python scanner, so the detection logic is written and tested once
- Tests prove the scanner detects PII and respects the synthetic data annotation
- A developer guide tells any agent or human exactly how to work safely with sensitive data

## Non-Goals
- This epic does NOT encrypt or anonymize PII in the production database -- that is a future concern
- This epic does NOT audit the existing repository history for past PII leaks (the project is new; no concern yet)
- This epic does NOT implement PII handling in the Cloudflare D1 layer -- that belongs to E-003 or a future data-governance epic
- This epic does NOT restrict what data can be stored in `/ephemeral/` -- the point is that the directory is safe-by-default (gitignored), not that its contents are scanned
- This epic does NOT add CI/CD enforcement -- that is captured as a future idea; the scanner is designed to support it when needed

## Success Criteria
1. Running `git commit` on a staged file containing a real email address or phone number is blocked before the commit is created, and the blocking message names the file, the line number, and the pattern that matched
2. Running `git commit` on a staged Python source file that contains no PII passes without interference
3. Running `git commit` on a staged file annotated with `synthetic-test-data` in its first 5 lines passes without interference even if it contains PII-like patterns
4. The `/ephemeral/` directory structure exists with a README and all data-file contents are confirmed absent from git tracking
5. The PII taxonomy document exists at `docs/pii-taxonomy.md` and covers at least: names, emails, phone numbers, addresses, and GameChanger-specific identifiers
6. `pytest tests/test_pii_scanner.py` exits 0 with all tests green, with no real PII in any fixture
7. The developer guide exists at `docs/safe-data-handling.md` and answers: "Where do I put this JSON file?", "Can I commit this test fixture?", and "What do I do when the hook fires?"

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-006-01 | Ephemeral data directory structure and gitignore rules | TODO | None | - |
| E-006-02 | PII taxonomy for baseball-crawl | TODO | None | - |
| E-006-03 | Pre-commit hook scaffold | TODO | None | - |
| E-006-04 | PII scanner implementation | TODO | E-006-02, E-006-03 | - |
| E-006-05 | Pre-commit hook tests | TODO | E-006-04 | - |
| E-006-06 | Developer guide for safe data handling | TODO | E-006-02, E-006-04 | - |

## Technical Notes

### Chosen Mechanism: Two-Layer Defense
The architect's design at `/.project/research/E-006-precommit-design.md` specifies:

**Layer 1 -- Git pre-commit hook** (primary enforcement):
- Entry point: `.githooks/pre-commit` (committed shell script)
- Activated via: `git config core.hooksPath .githooks` (automated by `scripts/install-hooks.sh`)
- Fires on every `git commit` regardless of who or what is committing
- Calls `src/safety/pii_scanner.py --stdin`, passing staged file paths on stdin
- If scanner exits non-zero: prints output and exits 1 (blocking the commit)

**Layer 2 -- Claude Code PreToolUse hook** (agent-layer defense):
- Entry point: `.claude/hooks/pii-check.sh` (committed shell script)
- Configured in `.claude/settings.json` under `hooks.PreToolUse` with matcher `Bash`
- Fires before any Claude Code `Bash` tool call; checks if it is a `git commit` command
- If it is a git commit: runs `src/safety/pii_scanner.py --staged`
- Blocks the tool call via JSON denial output if PII is detected
- No installation step required -- fires automatically from project settings

Both hooks call the same scanner. If the scanner does not exist yet (E-006-03 runs before E-006-04), both hooks pass silently.

### The Scanner: `src/safety/pii_scanner.py`
Interface contract (implementing agent must read the full design doc for details):
```
USAGE:
  python3 src/safety/pii_scanner.py --staged       # scan git staged files
  python3 src/safety/pii_scanner.py --stdin         # read file paths from stdin (one per line)
  python3 src/safety/pii_scanner.py file1 file2     # scan specific files

EXIT CODES:
  0  -- no PII detected (or all files skipped)
  1  -- PII detected in one or more files

OUTPUT on violation (to stderr):
  [PII BLOCKED] path/to/file.json:42: matched 'email' pattern
  3 violation(s) found in 2 file(s).
```

### Pattern Storage: Python Module, Not YAML
Patterns are stored in `src/safety/pii_patterns.py` as a Python dict -- NOT a YAML file. This keeps the scanner stdlib-only (no PyYAML dependency). The YAML-style format appears in the design doc as documentation only; the implementation uses the Python module.

### Synthetic Data Convention (Decided -- No Longer Open)
The synthetic data marker is the string `synthetic-test-data` appearing anywhere in the **first 5 lines** of a file. If this marker is present, the scanner skips the file entirely. This is the canonical convention; E-006-02 documents it and E-006-04 implements it.

### Bypass Policy (Decided -- No Longer Open)
The only legitimate bypass is `git commit --no-verify` (standard Git). This skips all Git hooks. It cannot be logged or audited automatically. The developer guide must warn that this bypasses ALL hooks, not just PII scanning, and should be followed by manual review. The Claude Code hook cannot be bypassed by an agent -- only a human can disable it by modifying `.claude/settings.json`.

### Scoped Rule
A scoped rule at `.claude/rules/pii-safety.md` protects the safety code itself: advisory guidance against weakening patterns or adding blanket exclusions, scoped to `src/safety/**`, `.githooks/**`, and `.claude/hooks/pii-check.sh`.

### What Is and Is Not PII in This Project
This is elaborated in E-006-02 and `docs/pii-taxonomy.md`, but the key principle is: **any data that identifies a real person is PII**. In the baseball context this includes:
- Full names (player, coach, parent)
- Contact information (email, phone, address)
- GameChanger user IDs (which resolve to real identities)
- Photos and profile images

Synthetic test data (invented names, fake phone numbers) is NOT PII and may be committed as test fixtures, provided it is clearly labeled with the `synthetic-test-data` marker.

### Ephemeral Directory Convention
```
/ephemeral/
  README.md                 # explains the directory, warns against committing
  E-001/                    # exploration data for epic E-001
  E-005/                    # exploration data for epic E-005
  E-006/                    # exploration data for epic E-006
  scratch/                  # unepic-ed one-off files
```

All of `/ephemeral/` is added to `.gitignore` with exceptions to allow `.gitkeep` and `README.md` to be tracked.

### File Ownership by Story (for parallel execution safety)
| Story | Files Owned |
|-------|-------------|
| E-006-01 | `/ephemeral/README.md`, `/ephemeral/` dir tree, `/ephemeral/.gitignore`, `.gitignore` (root) |
| E-006-02 | `docs/pii-taxonomy.md` |
| E-006-03 | `.githooks/pre-commit`, `.claude/hooks/pii-check.sh`, `scripts/install-hooks.sh`, `.claude/settings.json`, `.claude/rules/pii-safety.md`, `.claude/hooks/README.md` (update) |
| E-006-04 | `src/safety/__init__.py`, `src/safety/pii_scanner.py`, `src/safety/pii_patterns.py` |
| E-006-05 | `tests/test_pii_scanner.py` |
| E-006-06 | `docs/safe-data-handling.md`, `CLAUDE.md` (add install command to Commands section) |

E-006-01, E-006-02, and E-006-03 share no files and can execute in parallel. E-006-04 requires E-006-02 (for patterns) and E-006-03 (for calling convention). E-006-05 and E-006-06 require E-006-04.

## Open Questions
1. **Full name detection**: Simple regex is unreliable for detecting names. The E-006-02 taxonomy should specify whether name detection is attempted (with known false-positive risk) or left to human judgment. The scanner's initial pattern set includes email and phone only; names can be added if the taxonomy justifies a viable pattern.
2. **CI enforcement**: Should the same scanner run in CI (GitHub Actions) to catch anything that slips through `--no-verify`? This is a non-goal for this epic but worth capturing for the IDEA backlog. The scanner is designed to support it (stdin mode, no external dependencies).

## History
- 2026-02-28: Created. Status set to ACTIVE. E-006-03 started BLOCKED pending claude-architect design.
- 2026-02-28: Architect delivered design doc at `/.project/research/E-006-precommit-design.md`. E-006-03 unblocked. Open Questions 1 (bypass) and 4 (synthetic convention) resolved. Epic technical notes updated to reflect chosen mechanism. All stories updated.
- 2026-03-01: ABANDONED during triage. PII protection is still needed but not at the right priority level for current project phase. Demoted to IDEA-004 for future promotion when data pipeline (E-002) is producing real data that needs protection.
