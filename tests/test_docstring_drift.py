"""Guard against stale credential key references in docstrings and comments.

After the migration to profile-scoped credential keys (_WEB / _MOBILE suffixes),
this test scans source files to ensure no flat (unsuffixed) credential key names
remain in docstrings or comments.  This catches docstring/code drift when the
code has been updated but explanatory text still references the old naming.

Flat key names to guard against (any without an immediately following _WEB or
_MOBILE suffix):
  - GAMECHANGER_AUTH_TOKEN
  - GAMECHANGER_DEVICE_ID
  - GAMECHANGER_APP_NAME

Scanning is restricted to docstring lines (string literals at statement position)
and comment lines (lines whose first non-whitespace character is ``#``).
Pure code that uses the base names to construct profile-scoped keys at runtime
(e.g. tuple literals in _PROFILE_SCOPED_KEYS, f-string templates) is intentionally
not flagged.
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

_SCAN_DIRS: list[Path] = [
    _PROJECT_ROOT / "src",
    _PROJECT_ROOT / "scripts",
]

# Flat credential key names that must always carry a _WEB or _MOBILE suffix
# when referenced in documentation or comments.
_FLAT_KEYS: list[str] = [
    "GAMECHANGER_AUTH_TOKEN",
    "GAMECHANGER_DEVICE_ID",
    "GAMECHANGER_APP_NAME",
]

# Regex: matches any flat key NOT immediately followed by _WEB or _MOBILE.
_FLAT_KEY_RE: re.Pattern[str] = re.compile(
    r"(?<![A-Z_])("
    + "|".join(re.escape(k) for k in _FLAT_KEYS)
    + r")(?!_(?:WEB|MOBILE))"
)


# ---------------------------------------------------------------------------
# AST-based docstring line extractor
# ---------------------------------------------------------------------------


def _docstring_lines(source: str, filepath: Path) -> list[tuple[int, str]]:
    """Return (lineno, text) pairs for every source line inside a docstring.

    A docstring is a bare string-literal expression (``Expr(Constant(str))``)
    at module, class, or function body level.  Multi-line docstrings contribute
    one pair per physical source line.

    Args:
        source: Full text of the Python source file.
        filepath: Used for error messages only.

    Returns:
        List of ``(1-based line number, raw line text)`` tuples.
    """
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    source_lines = source.splitlines()
    result: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        start = (node.lineno or 1) - 1
        end = (node.end_lineno or node.lineno) - 1
        for i in range(start, end + 1):
            if i < len(source_lines):
                result.append((i + 1, source_lines[i]))
    return result


def _comment_lines(source: str) -> list[tuple[int, str]]:
    """Return (lineno, text) pairs for every pure comment line (``# ...``).

    Inline comments (e.g. ``x = 1  # note``) are NOT returned -- only lines
    whose first non-whitespace character is ``#``.

    Args:
        source: Full text of the Python source file.

    Returns:
        List of ``(1-based line number, raw line text)`` tuples.
    """
    result: list[tuple[int, str]] = []
    for i, line in enumerate(source.splitlines()):
        if line.lstrip().startswith("#"):
            result.append((i + 1, line))
    return result


# ---------------------------------------------------------------------------
# File scanner
# ---------------------------------------------------------------------------


def _scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Return violations in docstrings/comments of one ``.py`` file.

    Args:
        filepath: Path to the file to scan.

    Returns:
        List of ``(lineno, matched_key, full_line)`` tuples.  Empty when clean.
    """
    source = filepath.read_text(encoding="utf-8")
    violations: list[tuple[int, str, str]] = []
    candidates = _docstring_lines(source, filepath) + _comment_lines(source)
    for lineno, line in candidates:
        for m in _FLAT_KEY_RE.finditer(line):
            violations.append((lineno, m.group(1), line.rstrip()))
    return violations


def _collect_python_files() -> list[Path]:
    """Return all ``.py`` files under the configured scan directories."""
    files: list[Path] = []
    for scan_dir in _SCAN_DIRS:
        if scan_dir.exists():
            files.extend(sorted(scan_dir.rglob("*.py")))
    return files


# ---------------------------------------------------------------------------
# Primary regression test
# ---------------------------------------------------------------------------


def test_no_flat_credential_keys_in_source() -> None:
    """Docstrings and comments must not reference flat (unsuffixed) credential keys."""
    all_violations: list[str] = []
    for py_file in _collect_python_files():
        for lineno, key, line in _scan_file(py_file):
            rel = py_file.relative_to(_PROJECT_ROOT)
            all_violations.append(f"  {rel}:{lineno}  [{key}]  {line}")

    if all_violations:
        detail = "\n".join(all_violations)
        pytest.fail(
            f"Found {len(all_violations)} stale flat credential key reference(s) in "
            f"docstrings/comments (use _WEB or _MOBILE suffix):\n{detail}"
        )


# ---------------------------------------------------------------------------
# Unit tests for scanner internals
# ---------------------------------------------------------------------------


class TestFlatKeyRegex:
    """Regex correctly distinguishes flat keys from profile-scoped keys."""

    def test_flat_auth_token_matched(self) -> None:
        assert _FLAT_KEY_RE.search("# see GAMECHANGER_AUTH_TOKEN for details")

    def test_flat_device_id_matched(self) -> None:
        assert _FLAT_KEY_RE.search("# set GAMECHANGER_DEVICE_ID")

    def test_flat_app_name_matched(self) -> None:
        assert _FLAT_KEY_RE.search("# set GAMECHANGER_APP_NAME")

    def test_web_suffix_not_matched(self) -> None:
        assert not _FLAT_KEY_RE.search("# use GAMECHANGER_AUTH_TOKEN_WEB")

    def test_mobile_suffix_not_matched(self) -> None:
        assert not _FLAT_KEY_RE.search("# use GAMECHANGER_AUTH_TOKEN_MOBILE")

    def test_device_id_web_not_matched(self) -> None:
        assert not _FLAT_KEY_RE.search("# GAMECHANGER_DEVICE_ID_WEB is the key")

    def test_device_id_mobile_not_matched(self) -> None:
        assert not _FLAT_KEY_RE.search("# GAMECHANGER_DEVICE_ID_MOBILE")

    def test_app_name_web_not_matched(self) -> None:
        assert not _FLAT_KEY_RE.search("# GAMECHANGER_APP_NAME_WEB")

    def test_app_name_mobile_not_matched(self) -> None:
        assert not _FLAT_KEY_RE.search("# GAMECHANGER_APP_NAME_MOBILE")


class TestCommentLines:
    def test_pure_comment_returned(self) -> None:
        source = "x = 1\n# this is a comment\ny = 2\n"
        lines = _comment_lines(source)
        assert any("this is a comment" in line for _, line in lines)

    def test_non_comment_not_returned(self) -> None:
        source = 'x = "not a comment"\n'
        assert _comment_lines(source) == []

    def test_inline_comment_not_returned(self) -> None:
        # Inline: first non-whitespace is NOT '#'
        source = "x = 1  # inline note\n"
        assert _comment_lines(source) == []

    def test_indented_comment_returned(self) -> None:
        source = "if True:\n    # nested comment\n    pass\n"
        lines = _comment_lines(source)
        assert any("nested comment" in line for _, line in lines)


class TestDocstringLines:
    def test_module_docstring_returned(self) -> None:
        source = '"""Module docstring."""\nx = 1\n'
        lines = _docstring_lines(source, Path("<test>"))
        assert any("Module docstring" in line for _, line in lines)

    def test_function_docstring_returned(self) -> None:
        source = textwrap.dedent(
            '''\
            def foo():
                """Function docstring."""
                pass
            '''
        )
        lines = _docstring_lines(source, Path("<test>"))
        assert any("Function docstring" in line for _, line in lines)

    def test_assignment_string_not_returned(self) -> None:
        # Assignment string is not an Expr -- must not be returned
        source = 'x = "not a docstring"\n'
        assert _docstring_lines(source, Path("<test>")) == []

    def test_multiline_docstring_all_lines_returned(self) -> None:
        source = textwrap.dedent(
            '''\
            """
            Line one.
            Line two.
            """
            '''
        )
        lines = _docstring_lines(source, Path("<test>"))
        texts = [line for _, line in lines]
        assert any("Line one" in t for t in texts)
        assert any("Line two" in t for t in texts)


class TestScanFile:
    def test_flat_key_in_comment_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("# set GAMECHANGER_AUTH_TOKEN before running\nx = 1\n")
        violations = _scan_file(f)
        assert len(violations) == 1
        assert violations[0][1] == "GAMECHANGER_AUTH_TOKEN"

    def test_flat_key_in_docstring_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text('"""Use GAMECHANGER_DEVICE_ID to authenticate."""\nx = 1\n')
        violations = _scan_file(f)
        assert len(violations) == 1
        assert violations[0][1] == "GAMECHANGER_DEVICE_ID"

    def test_scoped_key_in_comment_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("# set GAMECHANGER_AUTH_TOKEN_WEB\nx = 1\n")
        assert _scan_file(f) == []

    def test_flat_key_in_tuple_literal_not_flagged(self, tmp_path: Path) -> None:
        """Flat key base names in code (data, not docs) are not flagged."""
        f = tmp_path / "example.py"
        f.write_text(
            '_PROFILE_SCOPED_KEYS: tuple[str, ...] = (\n'
            '    "GAMECHANGER_AUTH_TOKEN",\n'
            '    "GAMECHANGER_DEVICE_ID",\n'
            '    "GAMECHANGER_APP_NAME",\n'
            ')\n'
        )
        assert _scan_file(f) == []

    def test_flat_key_in_fstring_code_not_flagged(self, tmp_path: Path) -> None:
        """F-string template building a scoped key is not flagged."""
        f = tmp_path / "example.py"
        f.write_text('token = env[f"GAMECHANGER_AUTH_TOKEN{suffix}"]\n')
        assert _scan_file(f) == []

    def test_flat_key_in_print_statement_not_flagged(self, tmp_path: Path) -> None:
        """A flat key in a print() call (code, not doc) is not flagged."""
        f = tmp_path / "example.py"
        f.write_text('print("Ensure GAMECHANGER_AUTH_TOKEN is set")\n')
        assert _scan_file(f) == []

    def test_multiple_violations_all_returned(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text(
            "# See GAMECHANGER_AUTH_TOKEN and GAMECHANGER_DEVICE_ID for setup\nx = 1\n"
        )
        violations = _scan_file(f)
        assert len(violations) == 2

    def test_flat_key_both_in_comment_and_docstring_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text(
            '"""Module: uses GAMECHANGER_APP_NAME env var."""\n'
            "# Also check GAMECHANGER_AUTH_TOKEN\n"
            "x = 1\n"
        )
        violations = _scan_file(f)
        keys_found = {v[1] for v in violations}
        assert "GAMECHANGER_APP_NAME" in keys_found
        assert "GAMECHANGER_AUTH_TOKEN" in keys_found
