# Code-Review Rubric for baseball-crawl

## Setup

Before reviewing, read these files:
1. `CLAUDE.md` -- project conventions, code style, security rules, and architecture
2. If the change is tied to a story, read the story file and its parent epic's Technical Notes

## Review Priorities (in order)

1. **Bugs and regressions** -- logic errors, off-by-ones, wrong defaults, silent failures
2. **Missing tests** -- data parsing, transformation, and loader logic must have tests; flag any untested code
3. **Credential and security risks** -- credentials or tokens in code, logs, comments, or test fixtures; SQL injection; insecure defaults
4. **Schema drift** -- database writes that do not match current migration state; loader fields that do not exist in the schema
5. **Planning/implementation mismatch** -- code that does not satisfy the story's acceptance criteria, or contradicts the epic's Technical Notes
6. **Style and convention violations** -- missing type hints, `print()` instead of `logging`, raw `httpx.Client()` instead of `create_session()`, `os.path` instead of `pathlib`

7. **Extended bug pattern checks** (abbreviated from `.claude/agents/code-reviewer.md` Bug Pattern Checklist -- that file is the authoritative source; update these summaries when the CR checklist changes):
   - Caller audit: grep for callers of any changed function; verify callers remain correct; check semantic siblings (parallel functions implementing the same concern) and stale prose references (docstrings, comments, `docs/` mentioning renamed/removed identifiers)
   - API field contract: cross-reference API field paths against `docs/api/endpoints/`; verify correct endpoint variant (authenticated vs public) and required headers
   - Function contract preservation: verify docstring/type-hint promises still hold after rewrites; flag silent divergence between docs and implementation
   - Deploy-time safety: verify new column references exist in `migrations/*.sql`; check migration numbering is sequential; verify NULL handling for new columns on existing tables
   - Remediation regression guard: apply full checklist to Round 2 fix code -- remediation is new code that can introduce the same bug classes
   - Test-validates-spec: verify test mocks match the authoritative spec (`docs/api/endpoints/`, `migrations/*.sql`, docstrings), not the implementation under test
   - Status lifecycle (extended): verify in-memory flags/booleans are set only after the gated operation succeeds, not before the attempt

## Reporting

- Cite file and line number for every finding
- Group findings by priority level
- If the review is clean, state explicitly: "No findings."
- Do not report nitpicks or stylistic opinions unless they violate a rule in CLAUDE.md
