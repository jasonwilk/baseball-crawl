<!-- synthetic-test-data -->
# E-006 Pre-Commit Safety System Design

## Executive Summary

### The Problem

GameChanger API responses contain real PII: player names, parent emails, coach phone numbers. During development, agents and developers routinely save raw JSON to disk for inspection. One accidental `git add .` followed by a commit writes that data into permanent Git history. Removing it requires a destructive history rewrite.

### The Solution

A two-layer defense:

1. **Git pre-commit hook** (primary enforcement): A Python script invoked by Git's native `pre-commit` hook that scans staged files for PII patterns. If any match, the commit is blocked with a clear error message naming the file, line, and pattern. This runs automatically on every `git commit` -- no developer action required after initial setup.

2. **Claude Code PreToolUse hook** (agent-layer defense): A lightweight shell script that fires before Claude Code executes any `Bash` tool call containing `git commit`. It runs the same scanner against staged files, blocking the tool call before Git even starts. This catches PII when Claude is the one committing.

Neither layer requires the developer to remember to run anything. Both are automatic. Both call the same scanner.

### Why Two Layers

| Scenario | Git hook catches it | Claude Code hook catches it |
|----------|--------------------|-----------------------------|
| Developer runs `git commit` in their terminal | Yes | No (not in Claude Code) |
| Claude Code agent runs `git commit` via Bash tool | Yes | Yes (earlier, with better feedback) |
| Developer uses a Git GUI that honors hooks | Yes | No |
| Developer uses `git commit --no-verify` | No | N/A |
| Claude Code runs `git add` then `git commit` | Yes | Yes |

The Claude Code hook adds defense-in-depth for the most common scenario in this project (agents doing the committing), while the Git hook covers all other paths.

---

## Proposed Mechanism

### Architecture Overview

```
Developer or Agent runs "git commit"
        |
        v
  [Git pre-commit hook]  <-- .githooks/pre-commit (shell script)
        |
        v
  [PII Scanner]           <-- src/safety/pii_scanner.py (Python)
        |
        +---> EXIT 0: commit proceeds
        +---> EXIT 1: commit blocked, violations printed to stderr
```

```
Claude Code agent attempts Bash("git commit ...")
        |
        v
  [PreToolUse hook]       <-- .claude/hooks/pii-check.sh (shell script)
        |
        v
  [PII Scanner]           <-- src/safety/pii_scanner.py (same scanner)
        |
        +---> EXIT 0: tool call proceeds (Git hook will also run)
        +---> EXIT 2: tool call blocked, feedback sent to Claude
```

### Component Inventory

| Component | Path | Type | Purpose |
|-----------|------|------|---------|
| Git pre-commit hook | `.githooks/pre-commit` | Shell script (committed) | Entry point for Git's hook system |
| Claude Code hook | `.claude/hooks/pii-check.sh` | Shell script (committed) | Entry point for Claude Code's PreToolUse system |
| PII scanner | `src/safety/pii_scanner.py` | Python script | Core scanning logic -- shared by both hooks |
| Pattern config | `src/safety/pii_patterns.yaml` | YAML file | Regex patterns and rules, derived from PII taxonomy |
| Hook setup script | `scripts/install-hooks.sh` | Shell script (committed) | One-command setup for new clones |

### Why This Mechanism (and Not Others)

**Rejected: `pre-commit` Python framework** (`.pre-commit-config.yaml`, `pip install pre-commit`)
- Adds a significant dependency (`pre-commit` pulls in `virtualenv`, `cfgv`, `identify`, `nodeenv`, `pyyaml`)
- Designed for multi-hook orchestration across many tools -- overkill when we have exactly one custom hook
- Adds a layer of indirection between the hook and the scanner
- Requires `pre-commit install` and `pre-commit run` commands that are unfamiliar to some developers
- Our project is early stage with no `pyproject.toml` or `requirements.txt` yet -- adding `pre-commit` as the first dependency is backwards

**Rejected: Raw `.git/hooks/pre-commit`** (not committed to repo)
- Not version-controlled; each developer must manually copy or symlink the hook
- Easy to forget on a fresh clone
- No way to update the hook across all developer machines

**Chosen: `.githooks/` directory with `core.hooksPath`**
- The hook script is committed to the repo, version-controlled, and visible in code review
- One-time setup: `git config core.hooksPath .githooks` (automated by `scripts/install-hooks.sh`)
- No external dependencies beyond Python (which the project already requires)
- Direct and transparent -- developers can read the hook and understand exactly what it does
- The scanner is a plain Python script, testable independently of Git

**Chosen additionally: Claude Code PreToolUse hook**
- Deterministic enforcement at the agent layer (CLAUDE.md rules are advisory; hooks are guaranteed)
- Catches PII before Git even starts, providing faster feedback to the agent
- Configured in `.claude/settings.json`, committed to the repo, automatic for all Claude Code users
- No installation step -- it fires automatically when Claude Code loads the project settings

---

## Claude Code Integration

### PreToolUse Hook Configuration

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pii-check.sh",
            "timeout": 10,
            "statusMessage": "Checking staged files for PII..."
          }
        ]
      }
    ]
  }
}
```

### Hook Script: `.claude/hooks/pii-check.sh`

The script receives JSON on stdin from Claude Code. It must:

1. Parse the `tool_input.command` field to determine if this is a `git commit` command
2. If not a git commit, exit 0 immediately (do not interfere with other Bash commands)
3. If it is a git commit, run the PII scanner against staged files
4. If the scanner finds PII, output a JSON denial decision and exit

**Pseudocode:**

```bash
#!/bin/bash
# .claude/hooks/pii-check.sh
# Claude Code PreToolUse hook: blocks git commit if staged files contain PII

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only intercept git commit commands
if ! echo "$COMMAND" | grep -qE '^git\s+commit'; then
  exit 0
fi

# Run PII scanner against staged files
SCANNER="$CLAUDE_PROJECT_DIR/src/safety/pii_scanner.py"

if [ ! -f "$SCANNER" ]; then
  # Scanner not yet installed (E-006-04 pending); allow commit
  exit 0
fi

# Run scanner; capture output
SCAN_OUTPUT=$(python3 "$SCANNER" --staged 2>&1)
SCAN_EXIT=$?

if [ $SCAN_EXIT -ne 0 ]; then
  # PII detected -- block the tool call
  jq -n --arg reason "$SCAN_OUTPUT" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("PII detected in staged files. Move sensitive files to /ephemeral/ or remove PII before committing.\n\n" + $reason)
    }
  }'
  exit 0
fi

# No PII found -- allow the commit
exit 0
```

**Key design decisions in this script:**

- It exits 0 even when blocking. The denial is communicated via JSON output (`permissionDecision: "deny"`), not via exit code 2. This follows the Claude Code hooks reference pattern for PreToolUse decisions.
- If the scanner does not exist yet (E-006-03 runs before E-006-04), the hook passes silently. This allows the scaffold to be installed without breaking commits.
- The script only intercepts `git commit` commands. All other Bash tool calls pass through with zero overhead (a single `grep` check).

### What This Does NOT Do

- It does not create an agent. PII scanning is a deterministic check, not a reasoning task. An agent would be slower, more expensive, and less reliable than a regex scan.
- It does not create a skill. Skills are for reusable instructions that Claude applies during work. PII scanning is a gate, not a workflow.
- It does not add a rule to CLAUDE.md. Rules are advisory. The existing Security Rules section in CLAUDE.md already instructs agents to avoid PII in commits. The hook is the enforcement layer that backs up those advisory rules with a deterministic check.

### CLAUDE.md Integration

No changes to CLAUDE.md are needed for the hook mechanism itself. The existing Security Rules section already covers the policy. However, E-006-06 (developer guide) should add a brief note to CLAUDE.md's Commands section once the installation command exists:

```markdown
## Commands
- `./scripts/install-hooks.sh` -- one-time setup for PII pre-commit hook (run after cloning)
```

### Rule Addition

A scoped rule should be added at `.claude/rules/pii-safety.md` to reinforce the hook with advisory guidance:

```yaml
---
paths:
  - "src/safety/**"
  - ".githooks/**"
  - ".claude/hooks/pii-check.sh"
---

# PII Safety System Rules

- The PII scanner at src/safety/pii_scanner.py is a security control. Changes require careful review.
- Never weaken regex patterns without explicit approval.
- Never add blanket exclusions to the scanner's skip list.
- Test changes against the test suite in tests/test_pii_scanner.py before committing.
- The scanner must remain fast (under 1 second for 20 files). Do not add heavy dependencies.
```

---

## Implementation Contract

This section tells the engineer implementing E-006-03 through E-006-05 exactly what to build, in what order, and where each piece lives.

### E-006-03: Pre-Commit Hook Scaffold

**What to build:**

1. **`.githooks/pre-commit`** -- A shell script that Git calls on every commit. It:
   - Gets the list of staged files from `git diff --cached --name-only --diff-filter=ACM`
   - Passes them to `src/safety/pii_scanner.py`
   - If the scanner exits non-zero, prints the scanner's output and exits 1 (blocking the commit)
   - If the scanner exits zero, exits 0 (allowing the commit)
   - If the scanner does not exist yet, prints a warning and exits 0 (stub behavior)

   ```bash
   #!/bin/bash
   # .githooks/pre-commit
   # PII safety pre-commit hook -- blocks commits containing PII patterns
   # See docs/safe-data-handling.md for details

   SCANNER="$(git rev-parse --show-toplevel)/src/safety/pii_scanner.py"

   if [ ! -f "$SCANNER" ]; then
     echo "[pii-hook] Scanner not installed yet. Skipping PII check."
     exit 0
   fi

   # Get staged files (Added, Copied, Modified only -- not Deleted)
   STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

   if [ -z "$STAGED_FILES" ]; then
     exit 0
   fi

   # Run scanner
   echo "$STAGED_FILES" | python3 "$SCANNER" --stdin
   EXIT_CODE=$?

   if [ $EXIT_CODE -ne 0 ]; then
     echo ""
     echo "[pii-hook] Commit blocked. Fix the violations above, then try again."
     echo "[pii-hook] If this is a false positive, see docs/safe-data-handling.md"
     exit 1
   fi

   exit 0
   ```

2. **`.claude/hooks/pii-check.sh`** -- The Claude Code PreToolUse hook script (see pseudocode above). Must be executable (`chmod +x`).

3. **`scripts/install-hooks.sh`** -- A one-command setup script:

   ```bash
   #!/bin/bash
   # scripts/install-hooks.sh
   # Run this once after cloning the repository.

   set -e

   REPO_ROOT="$(git rev-parse --show-toplevel)"

   echo "Configuring Git to use .githooks/ directory..."
   git config core.hooksPath "$REPO_ROOT/.githooks"

   echo "Verifying hook is executable..."
   chmod +x "$REPO_ROOT/.githooks/pre-commit"

   echo "Done. PII pre-commit hook is active."
   echo "Test it with: git commit --allow-empty -m 'test hook'"
   ```

4. **Update `.claude/settings.json`** -- Add the `hooks` block for the PreToolUse hook (see Configuration section above). Merge it with the existing settings; do not overwrite `agent`, `env`, or `statusLine`.

5. **Verify the scaffold works:**
   - Run `./scripts/install-hooks.sh`
   - Run `git commit --allow-empty -m "test: verify hook fires"` -- should see the "Scanner not installed" warning and succeed
   - Confirm Claude Code loads the PreToolUse hook (check `/hooks` menu)

**Files to create:**
- `.githooks/pre-commit` (new, executable)
- `.claude/hooks/pii-check.sh` (new, executable)
- `scripts/install-hooks.sh` (new, executable)

**Files to modify:**
- `.claude/settings.json` (add hooks block)

### E-006-04: PII Scanner Implementation

**What to build:**

1. **`src/safety/pii_scanner.py`** -- The core scanner. Interface contract:

   ```
   USAGE:
     python3 src/safety/pii_scanner.py --staged          # scan git staged files
     python3 src/safety/pii_scanner.py --stdin            # read file paths from stdin (one per line)
     python3 src/safety/pii_scanner.py file1 file2 ...    # scan specific files

   EXIT CODES:
     0  -- no PII detected (or all files skipped)
     1  -- PII detected in one or more files

   OUTPUT (on PII detection, to stderr):
     [PII BLOCKED] path/to/file.json:42: matched 'email' pattern
     [PII BLOCKED] path/to/file.json:87: matched 'us_phone' pattern
     [PII BLOCKED] path/to/other.csv:3: matched 'email' pattern

     3 violation(s) found in 2 file(s).

   OUTPUT (on clean scan, to stderr, only in verbose mode):
     Scanned 5 file(s). No PII detected.
   ```

2. **`src/safety/pii_patterns.yaml`** -- Pattern definitions. Structure:

   ```yaml
   # PII detection patterns for baseball-crawl
   # Derived from docs/pii-taxonomy.md
   # Each pattern: name, regex, description, and optional file_types restriction

   patterns:
     - name: email
       regex: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
       description: Email addresses
       # Matches: coach@school.org, parent.name@gmail.com
       # Does not match: user@localhost (no TLD)

     - name: us_phone
       regex: '(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
       description: US phone numbers in common formats
       # Matches: (555) 867-5309, 555-867-5309, 555.867.5309, 5558675309
       # Note: may match some non-phone 10-digit numbers -- acceptable false positive rate

     # Additional patterns added as PII taxonomy (E-006-02) specifies them

   # Synthetic data annotation that exempts a file from scanning
   synthetic_marker: "synthetic-test-data"
   # If this string appears anywhere in the first 5 lines of a file, the file is skipped.

   # File extensions to scan (allowlist). Files not on this list are skipped.
   scannable_extensions:
     - .py
     - .json
     - .yaml
     - .yml
     - .md
     - .txt
     - .csv
     - .toml
     - .cfg
     - .ini
     - .html
     - .xml

   # Paths to always skip (relative to repo root), in addition to non-scannable extensions
   skip_paths:
     - ".git/"
     - ".claude/"
     - "node_modules/"
     - "__pycache__/"
   ```

3. **`src/safety/__init__.py`** -- Empty file to make it a Python package.

4. **Replace the stub in `.githooks/pre-commit`** -- The scanner now exists, so the "scanner not installed" warning path should no longer trigger. No code change needed if the scaffold was built correctly (it checks for file existence).

**Scanner design requirements:**

- Standard library only. No pip dependencies. The scanner uses `re`, `yaml` (PyYAML), `pathlib`, `sys`, `argparse`, and `logging`. If PyYAML is not available, fall back to a hardcoded pattern dict with a logged warning. This keeps the hook zero-dependency for fresh clones.
- Actually, revise: use only stdlib. Replace YAML config with a Python dict in a separate module (`src/safety/pii_patterns.py`) to avoid even the PyYAML dependency. Simpler, faster import, and no parsing step. The YAML format shown above is the logical structure; implement it as:

   ```python
   # src/safety/pii_patterns.py
   """PII detection patterns for baseball-crawl. Derived from docs/pii-taxonomy.md."""

   PATTERNS = [
       {
           "name": "email",
           "regex": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
           "description": "Email addresses",
       },
       {
           "name": "us_phone",
           "regex": r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
           "description": "US phone numbers in common formats",
       },
   ]

   SYNTHETIC_MARKER = "synthetic-test-data"

   SCANNABLE_EXTENSIONS = {
       ".py", ".json", ".yaml", ".yml", ".md", ".txt",
       ".csv", ".toml", ".cfg", ".ini", ".html", ".xml",
   }

   SKIP_PATHS = {".git/", ".claude/", "node_modules/", "__pycache__/"}
   ```

- Read files with `errors='replace'` to handle encoding issues gracefully.
- Log to stderr, not stdout. The Git hook captures stderr for display; stdout is used for Git's internal protocol.
- Check the synthetic marker in the first 5 lines of each file. If found, skip the file entirely.
- Report ALL violations, not just the first. Collect them, then print and exit.
- Target: under 500ms for a 20-file changeset.

**Files to create:**
- `src/safety/__init__.py`
- `src/safety/pii_scanner.py`
- `src/safety/pii_patterns.py`

**Files to modify:**
- None (the hook scaffold already calls the scanner at the right path)

### E-006-05: Pre-Commit Hook Tests

**What to build:**

- `tests/test_pii_scanner.py` -- pytest tests that import and exercise `src.safety.pii_scanner` directly
- Test fixtures created via `tmp_path`, not committed fixture files (simpler, no risk of fixture drift)
- Every test file/string that contains PII-like patterns must also contain the word `synthetic-test-data` in a comment in the test source, and use obviously fake data (`test@example.com`, `(555) 867-5309`, `Jane Fakename`)

**Test matrix (minimum):**

| Test case | Input | Expected |
|-----------|-------|----------|
| Email detected | File containing `coach@school.org` | Block, report file:line + pattern name |
| Phone detected | File containing `(555) 867-5309` | Block, report file:line + pattern name |
| Clean Python file | File with only code, no PII patterns | Pass |
| Synthetic annotation | File with PII patterns + `synthetic-test-data` in first 5 lines | Pass (skipped) |
| Binary extension skipped | File path ending in `.png` | Pass (skipped, no read attempt) |
| Empty file | Zero-byte file | Pass |
| Multiple violations | File with email AND phone on different lines | Block, report BOTH violations |
| Multiple files, mixed | Two files: one clean, one with PII | Block, report only the dirty file |
| Encoding error | File with invalid UTF-8 bytes | Pass (read with errors='replace', no crash) |
| Skip path | File under `.git/` or `.claude/` | Pass (skipped) |

---

## Bypass / Override Policy

### When Bypassing Is Legitimate

There are exactly two legitimate reasons to bypass the PII hook:

1. **Known false positive on a specific commit**: The scanner matched a pattern that is not actually PII (e.g., a regex string in source code that contains `@` symbols resembling an email). The developer has verified the match is not real PII.

2. **Emergency hotfix**: A production-blocking fix must be committed immediately and the scanner is blocking on a false positive that cannot be quickly resolved.

### How to Bypass

**Git hook bypass:**

```bash
git commit --no-verify -m "fix: emergency hotfix for X"
```

The `--no-verify` flag skips all Git hooks, including the PII scanner. This is a standard Git feature and cannot be disabled.

**Claude Code hook bypass:**

The Claude Code PreToolUse hook cannot be bypassed by the agent. It can only be disabled by:
- Removing the hook from `.claude/settings.json` (requires human action)
- Setting `"disableAllHooks": true` in settings (requires human action)

This is intentional. Agents should never bypass PII checks. If an agent encounters a false positive, it should report the issue and let a human decide.

### Bypass Audit Trail

There is no automatic logging of `--no-verify` usage. Git does not provide a hook that fires when hooks are skipped. However:

- The developer guide (E-006-06) must prominently warn that `--no-verify` skips ALL hooks, not just the PII scanner
- The developer guide must state that `--no-verify` should be followed by a manual review of the committed files
- Consider a future IDEA: a CI/CD job that runs the PII scanner on every push, catching anything that slipped through via `--no-verify`

### What Is NOT a Legitimate Bypass

- "The hook is slow" -- fix the hook, do not bypass it
- "I'm committing test data" -- use the synthetic data annotation instead
- "I'm sure this file is clean" -- let the scanner confirm it

---

## CI/CD Considerations

### Current Scope (This Epic)

This epic focuses on local enforcement. CI/CD integration is a future concern.

### Future Integration (Captured as Idea, Not Built Now)

When CI/CD is added (GitHub Actions), the same scanner should run as a check on every push:

```yaml
# .github/workflows/pii-check.yml (FUTURE -- not part of E-006)
name: PII Check
on: [push, pull_request]
jobs:
  pii-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Scan for PII
        run: |
          git diff --name-only HEAD~1 HEAD | python3 src/safety/pii_scanner.py --stdin
```

This catches anything that slipped through via `--no-verify` or a misconfigured local environment. The scanner is designed to work in both contexts (local and CI) because it accepts file paths on stdin and has zero external dependencies.

### Local Dev vs CI Differences

| Aspect | Local dev | CI |
|--------|-----------|-----|
| Trigger | `git commit` (automatic) | `push` / `pull_request` event |
| Files scanned | Staged files only | Diff between commits |
| Bypass possible | Yes (`--no-verify`) | No (CI always runs) |
| Scanner location | `src/safety/pii_scanner.py` (same) | `src/safety/pii_scanner.py` (same) |
| Dependencies | Python 3 (already required) | Python 3 (setup in workflow) |

---

## Testing Strategy

### Unit Tests (E-006-05)

Test the scanner function directly with synthetic data. Import `pii_scanner` and call its scanning functions with temporary files. Do not test via `git commit` in the test suite -- that couples tests to Git state and is fragile.

### Integration Verification (Manual, Part of E-006-03 Definition of Done)

After installing the scaffold:

1. Create a file with a fake email address: `echo "contact: test@example.com" > /tmp/pii-test.txt`
2. Stage it: `git add /tmp/pii-test.txt` (or a file in the repo)
3. Attempt to commit: `git commit -m "test"`
4. Verify: commit is blocked, error message names the file and pattern
5. Remove the file: `git reset HEAD /tmp/pii-test.txt`
6. Commit a clean Python file: verify it passes without interference

### Claude Code Hook Verification (Manual, Part of E-006-03 Definition of Done)

1. In a Claude Code session, ask the agent to commit a staged file containing PII
2. Verify: the PreToolUse hook fires and blocks the Bash tool call
3. Verify: Claude receives feedback explaining why and suggesting a fix

### Regression Testing

The scanner test suite (`tests/test_pii_scanner.py`) should be included in any future CI pipeline and run on every PR. It has no external dependencies and no network calls.

---

## Summary of Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hook framework | None -- native Git `core.hooksPath` | Simplest option; no dependencies; project is early stage |
| Hook location | `.githooks/pre-commit` (committed) | Version-controlled, visible in code review |
| Installation | `scripts/install-hooks.sh` (one command) | Minimal friction for new clones |
| Scanner language | Python (stdlib only) | Project's primary language; no pip install needed |
| Pattern storage | Python module (`pii_patterns.py`) | Zero dependencies; faster than YAML parsing |
| Claude Code integration | PreToolUse hook on Bash matcher | Deterministic enforcement at agent layer |
| Agent/skill/rule | None created for scanning | Scanning is deterministic, not a reasoning task |
| Scoped rule added | `.claude/rules/pii-safety.md` | Advisory protection for the safety code itself |
| Bypass mechanism | `git commit --no-verify` (standard Git) | Cannot be disabled; documented with warnings |
| CI integration | Future (not this epic) | Scanner designed to support it; captured as idea |
| Synthetic data convention | `synthetic-test-data` marker in first 5 lines | Simple, scannable, hard to add accidentally |

---

## Appendix: File Map

After E-006-03 through E-006-05 are complete, these files will exist:

```
baseball-crawl/
  .githooks/
    pre-commit                    # Git hook entry point (E-006-03)
  .claude/
    hooks/
      pii-check.sh               # Claude Code PreToolUse hook (E-006-03)
      statusline.sh              # (already exists)
      README.md                  # (already exists -- update to document pii-check.sh)
    rules/
      pii-safety.md              # Scoped rule for safety code (E-006-03)
    settings.json                # Updated with hooks block (E-006-03)
  scripts/
    install-hooks.sh             # One-command hook installation (E-006-03)
  src/
    safety/
      __init__.py                # Package marker (E-006-04)
      pii_scanner.py             # Core scanning logic (E-006-04)
      pii_patterns.py            # Pattern definitions (E-006-04)
  tests/
    test_pii_scanner.py          # Scanner test suite (E-006-05)
  docs/
    pii-taxonomy.md              # PII category definitions (E-006-02)
    safe-data-handling.md        # Developer guide (E-006-06)
```

---

## Revision History

- 2026-02-28: Initial design. Author: claude-architect.
