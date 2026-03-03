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

## Reporting

- Cite file and line number for every finding
- Group findings by priority level
- If the review is clean, state explicitly: "No findings."
- Do not report nitpicks or stylistic opinions unless they violate a rule in CLAUDE.md
