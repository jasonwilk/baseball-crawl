# E-036: Fix Codex Code-Review Wrapper

## Status
`COMPLETED`

## Overview
The `scripts/codex-review.sh` wrapper created in E-034 does not work. The `codex review` CLI (v0.107.0+) does not allow combining the `[PROMPT]` argument with `--uncommitted`, `--base`, or `--commit` flags. All three review modes fail on invocation. This epic fixes the wrapper so code review actually works with our project-specific rubric.

## Background & Context
E-034 created a two-lane Codex review system: code review (`codex review` + wrapper) and spec review (`codex exec` + wrapper). The spec-review lane works correctly -- `codex exec --ephemeral -` accepts piped input without conflict. The code-review lane is broken because the script passes the rubric via stdin as a PROMPT argument (`- <"${RUBRIC_FILE}"`), which is incompatible with every review flag.

The script's header comment (lines 4-9) falsely claims CLI compatibility was verified. In practice:
- `codex review --uncommitted - <rubric` -> error: `--uncommitted` cannot be used with `[PROMPT]`
- `codex review --base <branch> - <rubric` -> error: `--base` cannot be used with `[PROMPT]`
- `codex review --commit <sha> - <rubric` -> error: `--commit` cannot be used with `[PROMPT]`

Running `codex review --uncommitted` WITHOUT a prompt works fine (generic review, no project rubric).

The core problem is twofold:
1. The PROMPT argument is incompatible with review flags (must be removed)
2. Without the PROMPT argument, there is no known mechanism to inject our project-specific rubric into `codex review`

A research spike is needed to determine whether Codex offers any alternative mechanism (config file, instructions file, environment variable, etc.) for injecting custom review instructions, or whether we need a fundamentally different approach (e.g., using `codex exec` with manually-provided diffs).

**Expert consultation:** No expert consultation required -- this is a bug fix to tooling scripts. The domain is shell scripting and Codex CLI behavior, not coaching data, API design, agent architecture, or database schema.

## Goals
- All three `codex-review.sh` modes (`uncommitted`, `base`, `commit`) execute without error
- Our project-specific rubric (`.project/codex-review.md`) is delivered to Codex during code review
- Script header comments accurately reflect verified CLI behavior

## Non-Goals
- Changing the rubric content (`.project/codex-review.md` content is fine)
- Changing the spec-review system (`codex-spec-review.sh` works correctly)
- Adding new review modes or features
- Changing model selection behavior

## Success Criteria
1. `scripts/codex-review.sh uncommitted` completes without CLI argument errors and uses the project rubric
2. `scripts/codex-review.sh base main` completes without CLI argument errors and uses the project rubric
3. `scripts/codex-review.sh commit <sha>` completes without CLI argument errors and uses the project rubric
4. No false claims about CLI compatibility in script comments
5. CLAUDE.md Commands section is accurate (updated if the interface changes)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-036-R-01 | Research: how to pass custom rubric to codex review | DONE | None | general-dev |
| E-036-01 | Fix codex-review.sh to work with project rubric | DONE | E-036-R-01 | general-dev |
| E-036-02 | Update CLAUDE.md Commands section if interface changed | DONE | E-036-01 | claude-architect |

## Technical Notes

### Problem Analysis
The `codex review` subcommand treats `[PROMPT]` as a mutually exclusive alternative to the `--uncommitted`, `--base`, and `--commit` flags. You can provide a PROMPT (for a free-form review request) OR a flag (for a scoped diff review), but not both. The E-034 implementation assumed they could be combined; they cannot.

### Research Spike Scope (E-036-R-01)
The spike must answer: **How do we get our rubric into a `codex review` invocation that uses `--uncommitted`, `--base`, or `--commit`?**

Investigate in this order:
1. `codex review --help` -- any flags for instructions, config, or system prompt?
2. `codex --help` -- any global config mechanism (e.g., `--config`, `--instructions`)?
3. Codex config files -- does Codex read a project-level config file (e.g., `codex.json`, `.codex/`, `codex.toml`)?
4. Environment variables -- does Codex respect any env var for custom instructions?
5. Codex documentation/changelog -- any recently added mechanism?
6. Alternative approach: if no injection mechanism exists, evaluate using `codex exec` with manually-assembled diff + rubric as prompt (similar to how spec-review works). Assess whether this produces equivalent review quality.

The spike produces a findings document with a recommended approach for E-036-01.

### Fix Story Scope (E-036-01)
Implement whatever approach the research spike recommends. At minimum:
- Remove the broken `- <"${RUBRIC_FILE}"` PROMPT argument from all three modes
- Apply the recommended rubric delivery mechanism
- Fix the header comment to accurately describe verified CLI behavior
- Verify all three modes execute without error

### CLAUDE.md Update Scope (E-036-02)
If E-036-01 changes the script's user-facing interface (e.g., new flags, different invocation syntax), update the Commands section in CLAUDE.md. If the interface is unchanged (same modes, same syntax), this story is a no-op and can be marked DONE immediately. The story also verifies that the existing Commands entry is still accurate.

### File Ownership
- `scripts/codex-review.sh` -- modified by E-036-01 only
- `.project/codex-review.md` -- NOT modified (rubric content is fine)
- `CLAUDE.md` -- modified by E-036-02 only (if needed)
- Research findings -- written by E-036-R-01 in `epics/E-036-codex-review-fix/E-036-R-01-findings.md`

No file conflicts between stories. E-036-R-01 and E-036-01 are sequential (dependency). E-036-01 and E-036-02 are sequential (dependency). No parallel execution.

## Open Questions
- None. The research spike is designed to resolve the open technical question.

## History
- 2026-03-03: Created. Two failures identified in codex-review.sh: (1) PROMPT argument incompatible with review flags, (2) no known mechanism to inject project rubric. Research spike to find the rubric delivery mechanism, then fix story, then optional CLAUDE.md update.
- 2026-03-03: Dispatch started. E-036-R-01 dispatched first (no blockers).
- 2026-03-03: COMPLETED. All 3 stories verified DONE. Key finding: `codex review` has no mechanism for custom instructions alongside diff-scope flags. Solution: replaced `codex review` with `codex exec --ephemeral -` using assembled rubric + diff prompts (same pattern as spec-review wrapper). User-facing interface unchanged (same modes, same syntax). CLAUDE.md Commands entry verified accurate, no update needed. No documentation impact.
