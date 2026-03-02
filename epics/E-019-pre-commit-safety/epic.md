<!-- synthetic-test-data -->
# E-019: Pre-Commit Safety Gates

## Status
`COMPLETED`

## Overview
Prevent accidental commits of PII, credentials, and sensitive raw data files by installing a two-layer pre-commit defense (Git hook + Claude Code PreToolUse hook) backed by a stdlib-only Python scanner. This is the minimum safety infrastructure required before the project starts committing real code that interacts with GameChanger API data.

## Background & Context
GameChanger API responses contain real PII: player names, parent contact info, coach phone numbers and emails. Additionally, the project uses short-lived API tokens, session cookies, and other credentials that must never enter Git history. During iterative API exploration, agents routinely save raw JSON responses to disk. Without guardrails, one accidental `git add .` writes sensitive data into permanent Git history, requiring a destructive rewrite to remove.

This epic promotes IDEA-004 (demoted from E-006, ABANDONED 2026-03-01). The architect's original design at `/.project/research/E-006-precommit-design.md` is thorough and sound. This epic preserves the core two-layer architecture while consolidating the original 6 stories into 4 pragmatic stories -- collapsing the standalone PII taxonomy doc into scanner inline documentation, and merging scanner + tests into a single story.

**Expert consultation**: claude-architect delivered the full design in `/.project/research/E-006-precommit-design.md` during E-006. That design remains current and is the implementation spec for this epic. No additional consultation required -- the design was reviewed for the pragmatic consolidation and nothing was dropped that provides a real safety property.

## Goals
- An `/ephemeral/` directory exists, is gitignored, and gives agents a safe place to dump raw API responses
- A Git pre-commit hook blocks commits containing PII or credential patterns, naming the file, line, and pattern
- A Claude Code PreToolUse hook provides earlier interception when agents (the primary committers) attempt to commit sensitive data
- Both hooks call the same stdlib-only Python scanner -- detection logic written and tested once
- A developer guide tells any agent or human how to work safely with sensitive data
- Credential patterns (API tokens, Bearer headers, session cookies) are scanned alongside PII patterns

## Non-Goals
- This epic does NOT encrypt or anonymize PII in the database
- This epic does NOT audit existing repository history for past leaks (the project is new)
- This epic does NOT restrict what data can be stored in `/ephemeral/` -- the directory is safe-by-default (gitignored)
- This epic does NOT add CI/CD enforcement (the scanner supports it; that is a future addition)
- This epic does NOT attempt full-name detection via regex (unreliable; names are covered by the `/ephemeral/` convention)
- This epic does NOT create a standalone `docs/pii-taxonomy.md` -- the taxonomy is embedded in the scanner patterns module and the developer guide

## Success Criteria
1. Running `git commit` on a staged file containing a real email address, phone number, or credential pattern is blocked before the commit is created, with the blocking message naming the file, line number, and pattern
2. Running `git commit` on a staged Python source file with no sensitive patterns passes without interference
3. Running `git commit` on a staged file annotated with `synthetic-test-data` in its first 5 lines passes even if it contains sensitive patterns
4. The `/ephemeral/` directory exists with a README, is gitignored, and data files in it do not appear in `git status`
5. `pytest tests/test_pii_scanner.py` exits 0 with all tests green, using only synthetic test data
6. The developer guide at `docs/safe-data-handling.md` answers: "Where do I put this JSON file?", "Can I commit this test fixture?", and "What do I do when the hook fires?"

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-019-01 | Ephemeral data directory and gitignore rules | DONE | None | general-dev-01 |
| E-019-02 | Pre-commit hook scaffold (Git + Claude Code) | DONE | None | general-dev-02 |
| E-019-03 | PII and credential scanner with tests | DONE | E-019-02 | general-dev-03 |
| E-019-04 | Developer guide for safe data handling | DONE | E-019-03 | general-dev-04 |

## Technical Notes

### Design Document
The full design lives at `/.project/research/E-006-precommit-design.md`. That document is the implementation spec. If anything in the stories conflicts with the design doc, the design doc wins (except where this epic explicitly overrides it, noted below).

### Overrides from E-006 Design
1. **No standalone `docs/pii-taxonomy.md`**: The original design called for a separate taxonomy document (E-006-02). This epic collapses that into inline documentation in `src/safety/pii_patterns.py` (Python comments explaining each pattern category) and the developer guide. The taxonomy content is preserved; the standalone file is not needed for MVP.
2. **Scanner + tests in one story**: E-006-04 (scanner) and E-006-05 (tests) are merged into E-019-03. The scanner is small enough to implement and test in a single session.
3. **Credential patterns added**: The original design covered PII only. This epic adds credential patterns (Bearer tokens, API keys, session cookies, common secrets formats) to `pii_patterns.py`. The scanner module name stays `pii_scanner.py` for continuity with the design doc.
4. **Simplified ephemeral structure**: No pre-created per-epic subdirectories. Just `/ephemeral/` with a `scratch/` dir and a README. Agents create epic-specific subdirs as needed.

### Chosen Mechanism: Two-Layer Defense
Unchanged from the design doc. Both layers are essential:

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
- Blocks the tool call via JSON denial output if sensitive data is detected
- No installation step required -- fires automatically from project settings

Both hooks call the same scanner. If the scanner does not exist yet (E-019-02 runs before E-019-03), both hooks pass silently.

### The Scanner: `src/safety/pii_scanner.py`
Interface contract (unchanged from design doc):
```
USAGE:
  python3 src/safety/pii_scanner.py --staged       # scan git staged files
  python3 src/safety/pii_scanner.py --stdin         # read file paths from stdin (one per line)
  python3 src/safety/pii_scanner.py file1 file2     # scan specific files

EXIT CODES:
  0  -- no PII/credentials detected (or all files skipped)
  1  -- sensitive data detected in one or more files

OUTPUT on violation (to stderr):
  [PII BLOCKED] path/to/file.json:42: matched 'email' pattern
  [PII BLOCKED] path/to/file.json:87: matched 'bearer_token' pattern
  3 violation(s) found in 2 file(s).
```

### Pattern Storage: Python Module
Patterns are stored in `src/safety/pii_patterns.py` as Python constants -- NOT YAML. This keeps the scanner stdlib-only. Initial pattern categories:

**PII patterns:**
- `email`: Email addresses
- `us_phone`: US phone numbers in common formats

**Credential patterns:**
- `bearer_token`: Bearer authorization headers
- `api_key_assignment`: Common API key assignment patterns (e.g., `api_key = "sk-..."`)
- `session_cookie`: Session cookie values in common formats
- `env_secret`: Patterns matching `.env`-style secrets (e.g., `SECRET_KEY=...` with a long value)

The implementing agent should read `/.project/research/E-006-precommit-design.md` for exact regex guidance on PII patterns, then extend with credential patterns using the same structure.

### Synthetic Data Convention
The string `synthetic-test-data` appearing anywhere in the first 5 lines of a file exempts it from scanning. Case-sensitive. This is the canonical convention.

### Bypass Policy
- Git hook bypass: `git commit --no-verify` (standard Git, cannot be disabled)
- Claude Code hook bypass: Cannot be bypassed by an agent. Only a human can disable it via `.claude/settings.json`.
- The developer guide must document both and warn about misuse.

### Scoped Rule
`.claude/rules/pii-safety.md`: advisory guidance scoped to `src/safety/**`, `.githooks/**`, and `.claude/hooks/pii-check.sh`. Warns against weakening patterns or adding blanket exclusions.

### File Ownership by Story (for parallel execution safety)
| Story | Files Owned |
|-------|-------------|
| E-019-01 | `/ephemeral/README.md`, `/ephemeral/scratch/.gitkeep`, `.gitignore` (root -- ephemeral section only) |
| E-019-02 | `.githooks/pre-commit`, `.claude/hooks/pii-check.sh`, `scripts/install-hooks.sh`, `.claude/settings.json` (hooks block), `.claude/rules/pii-safety.md`, `.claude/hooks/README.md` (update) |
| E-019-03 | `src/safety/__init__.py`, `src/safety/pii_scanner.py`, `src/safety/pii_patterns.py`, `tests/test_pii_scanner.py` |
| E-019-04 | `docs/safe-data-handling.md`, `CLAUDE.md` (Commands section update) |

E-019-01 and E-019-02 share no files and can execute in parallel. E-019-03 requires E-019-02 (calling conventions). E-019-04 requires E-019-03 (real scanner output to document).

## Open Questions
None. All design decisions were resolved during E-006's architect consultation. The pragmatic consolidation introduces no new open questions.

## History
- 2026-03-02: Created by promoting IDEA-004. Consolidated from E-006 (ABANDONED 2026-03-01) -- 6 stories reduced to 4. Added credential scanning scope. Status set to READY.
