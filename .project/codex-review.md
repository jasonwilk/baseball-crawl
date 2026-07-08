# Code-Review Rubric for baseball-crawl

## Setup

Before reviewing, read these files:
1. `CLAUDE.md` -- project conventions, code style, security rules, and architecture
2. If the change is tied to a story, read the story file and its parent epic's Technical Notes

## Review Priorities (in order)

> The detailed **Bug Pattern Checklist** and **Security checklist** are appended to the review prompt as separate sections, single-sourced live from `.claude/agents/code-reviewer.md` (the authoritative rubric) at prompt-assembly time -- so they never drift from CR's rubric. Apply them in addition to the priorities below; do not re-summarize them here.

1. **Bugs and regressions** -- logic errors, off-by-ones, wrong defaults, silent failures (plus the appended Bug Pattern Checklist)
2. **Missing tests** -- data parsing, transformation, and loader logic must have tests; flag any untested code
3. **Security** -- apply the appended Security checklist in full (single-sourced from `code-reviewer.md`); do not treat this line as an abbreviated substitute for it
4. **Schema drift** -- database writes that do not match current migration state; loader fields that do not exist in the schema
5. **Planning/implementation mismatch** -- code that does not satisfy the story's acceptance criteria, or contradicts the epic's Technical Notes
6. **Style and convention violations** -- missing type hints, `print()` instead of `logging`, raw `httpx.Client()` instead of `create_session()`, `os.path` instead of `pathlib`

## Reporting

- Cite file and line number for every finding
- Group findings by priority level
- If the review is clean, state explicitly: "No findings."
- Do not report nitpicks or stylistic opinions unless they violate a rule in CLAUDE.md
