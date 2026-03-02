# synthetic-test-data
# This file contains fake PII patterns for testing the scanner.
# All data is obviously synthetic -- no real PII appears anywhere.
"""
Tests for src/safety/pii_scanner.py

All test data uses obviously fake values:
- test@example.com, coach@school.org (fake emails)
- (555) 867-5309 (fake phone)
- Bearer eyFAKETOKEN123 (fake token)
- api_key = "sk-fakekeyfakekeyfakekey" (fake key)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.safety.pii_scanner import (
    Violation,
    has_synthetic_marker,
    is_scannable,
    scan_file,
    scan_files,
    should_skip_path,
)


# ---------------------------------------------------------------------------
# Helper to write a temp file and return its path as a string
# ---------------------------------------------------------------------------

def _write_file(tmp_path: Path, name: str, content: str) -> str:
    """Write content to a temp file and return its string path."""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return str(p)


# ---------------------------------------------------------------------------
# Unit tests: should_skip_path
# ---------------------------------------------------------------------------

class TestShouldSkipPath:
    def test_skip_git_dir(self) -> None:
        assert should_skip_path(".git/config") is True

    def test_skip_claude_dir(self) -> None:
        assert should_skip_path(".claude/settings.json") is True

    def test_skip_node_modules(self) -> None:
        assert should_skip_path("node_modules/package/index.js") is True

    def test_skip_pycache(self) -> None:
        assert should_skip_path("__pycache__/module.cpython-311.pyc") is True

    def test_normal_path_not_skipped(self) -> None:
        assert should_skip_path("src/safety/pii_scanner.py") is False


# ---------------------------------------------------------------------------
# Unit tests: is_scannable
# ---------------------------------------------------------------------------

class TestIsScannable:
    def test_python_scannable(self) -> None:
        assert is_scannable("src/main.py") is True

    def test_json_scannable(self) -> None:
        assert is_scannable("data/response.json") is True

    def test_env_scannable(self) -> None:
        assert is_scannable(".env") is True

    def test_shell_scannable(self) -> None:
        assert is_scannable("scripts/run.sh") is True

    def test_png_not_scannable(self) -> None:
        assert is_scannable("image.png") is False

    def test_pyc_not_scannable(self) -> None:
        assert is_scannable("module.pyc") is False

    def test_db_not_scannable(self) -> None:
        assert is_scannable("app.db") is False

    def test_sqlite_not_scannable(self) -> None:
        assert is_scannable("data.sqlite") is False


# ---------------------------------------------------------------------------
# Unit tests: has_synthetic_marker
# ---------------------------------------------------------------------------

class TestHasSyntheticMarker:
    def test_marker_in_first_line(self) -> None:
        assert has_synthetic_marker(["# synthetic-test-data", "other"]) is True

    def test_marker_in_fifth_line(self) -> None:
        lines = ["a", "b", "c", "d", "# synthetic-test-data", "f"]
        assert has_synthetic_marker(lines) is True

    def test_marker_in_sixth_line_not_found(self) -> None:
        lines = ["a", "b", "c", "d", "e", "# synthetic-test-data"]
        assert has_synthetic_marker(lines) is False

    def test_no_marker(self) -> None:
        assert has_synthetic_marker(["line 1", "line 2"]) is False

    def test_empty_lines(self) -> None:
        assert has_synthetic_marker([]) is False


# ---------------------------------------------------------------------------
# Integration tests: scan_file
# ---------------------------------------------------------------------------

class TestScanFileEmailDetection:
    """AC-1: Email addresses are detected and reported."""

    def test_email_detected(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "contact.json",
            '{"email": "coach@school.org"}\n',
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"
        assert violations[0].line_number == 1

    def test_email_with_plus(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "data.json",
            '{"email": "test+tag@example.com"}\n',
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"


class TestScanFilePhoneDetection:
    """AC-2: US phone numbers are detected and reported."""

    def test_phone_parentheses(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "contact.txt",
            "Phone: (555) 867-5309\n",
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "us_phone"

    def test_phone_dashes(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "contact.txt",
            "Phone: 555-867-5309\n",
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "us_phone"

    def test_phone_dots(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "contact.txt",
            "Phone: 555.867.5309\n",
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "us_phone"

    def test_phone_with_country_code(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "contact.txt",
            "Phone: +1-555-867-5309\n",
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "us_phone"


class TestScanFileBearerTokenDetection:
    """AC-3: Bearer tokens are detected and reported."""

    def test_bearer_token(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "auth.json",
            '{"Authorization": "Bearer eyFAKETOKEN123"}\n',
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "bearer_token"

    def test_bearer_lowercase(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "auth.txt",
            "bearer eyFAKETOKEN456abc\n",
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "bearer_token"


class TestScanFileApiKeyDetection:
    """AC-4: API key assignments are detected and reported."""

    def test_api_key_equals(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "config.py",
            'api_key = "sk-fakekeyfakekeyfakekey"\n',
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"

    def test_secret_key_colon(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "config.yaml",
            "secret_key: xKfake_secret_value_here_long_enough\n",
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"

    def test_access_token(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "config.json",
            '{"access_token": "ghp_xFakeTokenValueHereLong"}\n',
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"


class TestScanFileCleanFile:
    """AC-5: Clean files pass without violations."""

    def test_clean_python(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "clean.py",
            'def hello() -> str:\n    """Say hello."""\n    return "hello world"\n',
        )
        violations = scan_file(path)
        assert violations == []

    def test_clean_json(self, tmp_path: Path) -> None:
        path = _write_file(
            tmp_path,
            "clean.json",
            '{"name": "team", "wins": 15, "losses": 8}\n',
        )
        violations = scan_file(path)
        assert violations == []


class TestScanFileSyntheticAnnotation:
    """AC-6: Files with synthetic-test-data marker are skipped."""

    def test_synthetic_marker_skips_file(self, tmp_path: Path) -> None:
        content = (
            "# synthetic-test-data\n"
            "# This file is for testing only.\n"
            "coach@school.org\n"
            "(555) 867-5309\n"
            "Bearer eyFAKETOKEN789\n"
        )
        path = _write_file(tmp_path, "fixtures.txt", content)
        violations = scan_file(path)
        assert violations == []

    def test_synthetic_marker_in_line_5(self, tmp_path: Path) -> None:
        content = (
            "line 1\n"
            "line 2\n"
            "line 3\n"
            "line 4\n"
            "# synthetic-test-data\n"
            "coach@school.org\n"
        )
        path = _write_file(tmp_path, "fixtures2.txt", content)
        violations = scan_file(path)
        assert violations == []


class TestScanFileBinaryExtensionSkip:
    """AC-7: Binary extension files are skipped without reading."""

    def test_png_skipped(self, tmp_path: Path) -> None:
        path = _write_file(tmp_path, "image.png", "coach@school.org")
        violations = scan_file(path)
        assert violations == []

    def test_pyc_skipped(self, tmp_path: Path) -> None:
        path = _write_file(tmp_path, "module.pyc", "coach@school.org")
        violations = scan_file(path)
        assert violations == []

    def test_db_skipped(self, tmp_path: Path) -> None:
        path = _write_file(tmp_path, "app.db", "coach@school.org")
        violations = scan_file(path)
        assert violations == []

    def test_sqlite_skipped(self, tmp_path: Path) -> None:
        path = _write_file(tmp_path, "data.sqlite", "coach@school.org")
        violations = scan_file(path)
        assert violations == []


class TestScanFileMultipleViolations:
    """AC-8: Multiple violations in one file are all reported."""

    def test_email_and_phone_on_different_lines(self, tmp_path: Path) -> None:
        content = (
            "Contact info:\n"
            "Email: test@example.com\n"
            "Phone: (555) 867-5309\n"
        )
        path = _write_file(tmp_path, "contact.txt", content)
        violations = scan_file(path)
        assert len(violations) == 2
        pattern_names = {v.pattern_name for v in violations}
        assert "email" in pattern_names
        assert "us_phone" in pattern_names


class TestScanFileEmptyFile:
    """AC-9 (partial): Empty files do not crash."""

    def test_empty_file(self, tmp_path: Path) -> None:
        path = _write_file(tmp_path, "empty.txt", "")
        violations = scan_file(path)
        assert violations == []


class TestScanFileEncodingError:
    """AC-9 (partial): Encoding errors are handled gracefully."""

    def test_invalid_utf8(self, tmp_path: Path) -> None:
        path = tmp_path / "bad_encoding.txt"
        path.write_bytes(b"Normal text\n\xff\xfe Bad bytes\nMore text\n")
        violations = scan_file(str(path))
        # Should not crash. May or may not find violations depending on
        # how replacement characters look, but must not raise.
        assert isinstance(violations, list)


class TestScanFileSkipPath:
    """AC-12 (partial): Files under skip paths are skipped."""

    def test_git_path_skipped(self, tmp_path: Path) -> None:
        violations = scan_file(".git/config")
        assert violations == []

    def test_claude_path_skipped(self, tmp_path: Path) -> None:
        violations = scan_file(".claude/settings.json")
        assert violations == []


# ---------------------------------------------------------------------------
# Integration tests: scan_files (multiple files)
# ---------------------------------------------------------------------------

class TestScanFilesMultiple:
    """AC-8 extended: Mixed clean and dirty files."""

    def test_mixed_clean_and_dirty(self, tmp_path: Path) -> None:
        clean_path = _write_file(
            tmp_path,
            "clean.py",
            'x = 42\n',
        )
        dirty_path = _write_file(
            tmp_path,
            "dirty.json",
            '{"email": "test@example.com"}\n',
        )
        violations = scan_files([clean_path, dirty_path])
        assert len(violations) == 1
        assert violations[0].file_path == dirty_path
        assert violations[0].pattern_name == "email"

    def test_all_clean(self, tmp_path: Path) -> None:
        p1 = _write_file(tmp_path, "a.py", "x = 1\n")
        p2 = _write_file(tmp_path, "b.py", "y = 2\n")
        violations = scan_files([p1, p2])
        assert violations == []

    def test_multiple_dirty_files(self, tmp_path: Path) -> None:
        p1 = _write_file(tmp_path, "a.json", '{"email": "test@example.com"}\n')
        p2 = _write_file(tmp_path, "b.txt", "Phone: (555) 867-5309\n")
        violations = scan_files([p1, p2])
        assert len(violations) == 2

    def test_nonexistent_file_skipped(self, tmp_path: Path) -> None:
        violations = scan_files([str(tmp_path / "nonexistent.json")])
        assert violations == []


# ---------------------------------------------------------------------------
# Integration tests: report formatting
# ---------------------------------------------------------------------------

class TestReportViolations:
    """Verify report output format matches the design spec."""

    def test_report_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from src.safety.pii_scanner import report_violations

        violations = [
            Violation(file_path="path/to/file.json", line_number=42, pattern_name="email"),
            Violation(file_path="path/to/file.json", line_number=87, pattern_name="bearer_token"),
        ]
        report_violations(violations)
        captured = capsys.readouterr()
        assert "[PII BLOCKED] path/to/file.json:42: matched 'email' pattern" in captured.err
        assert "[PII BLOCKED] path/to/file.json:87: matched 'bearer_token' pattern" in captured.err
        assert "2 violation(s) found in 1 file(s)." in captured.err
