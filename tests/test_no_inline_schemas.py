"""CI guardrail: forbid inline CREATE TABLE in tests/ (E-221-03).

Fails if any `tests/test_*.py` contains literal `CREATE TABLE` without a
`# noqa: fixture-schema` pragma. Legitimate exceptions (migration-runner
tests, backup round-trips, fail-closed-missing-table tests) must add the
pragma and a docstring rationale. See E-221 for context.
"""

from __future__ import annotations

from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_PRAGMA = "# noqa: fixture-schema"
_FORBIDDEN = "CREATE TABLE"
# Files whose own content exercises the guardrail (self-reference is fine).
_SELF_EXEMPT = {"test_no_inline_schemas.py"}


def test_no_inline_create_table_in_tests() -> None:
    """Fail if any tests/test_*.py contains CREATE TABLE without the pragma."""
    violations: list[str] = []
    for path in sorted(_TESTS_DIR.rglob("test_*.py")):
        if path.name in _SELF_EXEMPT:
            continue
        text = path.read_text(encoding="utf-8")
        if _FORBIDDEN not in text:
            continue
        if _PRAGMA in text:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _FORBIDDEN in line:
                violations.append(f"{path.relative_to(_TESTS_DIR.parent)}:{lineno}")
                break

    assert not violations, (
        "Inline CREATE TABLE found in test file(s). "
        "Use `load_real_schema(conn)` from `tests/conftest.py` instead. "
        "See E-221 for context. If this file legitimately needs inline "
        "schema (e.g., it tests the migration runner or backup mechanism), "
        "add `# noqa: fixture-schema` to the module docstring with a "
        "rationale.\n\nViolations:\n  " + "\n  ".join(violations)
    )
