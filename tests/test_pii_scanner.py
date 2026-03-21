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

from src.safety.pii_patterns import PLACEHOLDER_EMAILS
from src.safety.pii_scanner import (
    Violation,
    _count_scannable,
    has_synthetic_marker,
    is_placeholder_email,
    is_rfc2606_email,
    is_scannable,
    main,
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
            '{"email": "test+tag@realdomain.com"}\n',
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
            "Email: test@realdomain.com\n"
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
# Unit tests: is_rfc2606_email (E-129-01)
# ---------------------------------------------------------------------------

class TestIsRfc2606Email:
    """AC-7: Unit tests for the RFC 2606 domain allowlist helper."""

    # Second-level reserved domains
    def test_example_com(self) -> None:
        assert is_rfc2606_email("user@example.com") is True

    def test_example_org(self) -> None:
        assert is_rfc2606_email("user@example.org") is True

    def test_example_net(self) -> None:
        assert is_rfc2606_email("user@example.net") is True

    def test_subdomain_of_example_com(self) -> None:
        assert is_rfc2606_email("test@subdomain.example.com") is True

    def test_subdomain_of_example_org(self) -> None:
        assert is_rfc2606_email("test@subdomain.example.org") is True

    # TLD-based entries
    def test_dot_test_tld(self) -> None:
        assert is_rfc2606_email("admin@foo.test") is True

    def test_dot_example_tld(self) -> None:
        assert is_rfc2606_email("admin@bar.example") is True

    def test_dot_invalid_tld(self) -> None:
        assert is_rfc2606_email("admin@host.invalid") is True

    def test_dot_localhost_tld(self) -> None:
        assert is_rfc2606_email("admin@foo.localhost") is True

    def test_multi_level_dot_test(self) -> None:
        assert is_rfc2606_email("x@bar.baz.test") is True

    # localhost bare hostname
    def test_localhost_bare(self) -> None:
        # admin@localhost doesn't match the email regex (no dot in domain),
        # but the helper should still return True for correctness.
        assert is_rfc2606_email("admin@localhost") is True

    # Real domains must NOT be allowed
    def test_real_domain_not_allowed(self) -> None:
        assert is_rfc2606_email("jason@realdomain.com") is False

    def test_school_domain_not_allowed(self) -> None:
        assert is_rfc2606_email("coach@school.org") is False

    def test_gmail_not_allowed(self) -> None:
        assert is_rfc2606_email("user@gmail.com") is False

    def test_domain_ending_in_example_com_substring_not_allowed(self) -> None:
        # "notexample.com" should NOT match because it doesn't equal example.com
        # or end with ".example.com"
        assert is_rfc2606_email("user@notexample.com") is False

    # Case insensitivity
    def test_uppercase_domain(self) -> None:
        assert is_rfc2606_email("user@EXAMPLE.COM") is True


# ---------------------------------------------------------------------------
# Integration tests: scan_file with RFC 2606 allowlist (E-129-01 ACs)
# ---------------------------------------------------------------------------

class TestRfc2606DomainAllowlist:
    """AC-1 through AC-6: Email allowlist filtering integration tests."""

    def test_ac1_example_com_not_reported(self, tmp_path: Path) -> None:
        """AC-1: user@example.com produces no email finding."""
        path = _write_file(tmp_path, "doc.md", "Contact: user@example.com\n")
        violations = scan_file(path)
        assert violations == []

    def test_ac2_subdomain_example_org_not_reported(self, tmp_path: Path) -> None:
        """AC-2: test@subdomain.example.org produces no email finding."""
        path = _write_file(tmp_path, "doc.md", "Email: test@subdomain.example.org\n")
        violations = scan_file(path)
        assert violations == []

    def test_ac3_dot_test_tld_not_reported(self, tmp_path: Path) -> None:
        """AC-3: admin@foo.test produces no email finding."""
        path = _write_file(tmp_path, "doc.md", "Server: admin@foo.test\n")
        violations = scan_file(path)
        assert violations == []

    def test_ac5_real_domain_still_reported(self, tmp_path: Path) -> None:
        """AC-5: jason@realdomain.com IS reported as a violation."""
        path = _write_file(tmp_path, "contact.json", '{"email": "jason@realdomain.com"}\n')
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"

    def test_example_net_not_reported(self, tmp_path: Path) -> None:
        """example.net is reserved -- no finding."""
        path = _write_file(tmp_path, "doc.txt", "user@example.net\n")
        violations = scan_file(path)
        assert violations == []

    def test_dot_invalid_tld_not_reported(self, tmp_path: Path) -> None:
        """host.invalid is a reserved TLD -- no finding."""
        path = _write_file(tmp_path, "doc.txt", "admin@host.invalid\n")
        violations = scan_file(path)
        assert violations == []

    def test_phone_unaffected_by_allowlist(self, tmp_path: Path) -> None:
        """Other patterns (phone) are unaffected by the email allowlist."""
        path = _write_file(tmp_path, "contact.txt", "Phone: (555) 867-5309\n")
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "us_phone"

    def test_rfc2606_email_mixed_with_real_email(self, tmp_path: Path) -> None:
        """A file with both a reserved and a real email on separate lines: only real is flagged."""
        content = "Doc: user@example.com\nCoach: coach@school.org\n"
        path = _write_file(tmp_path, "mixed.txt", content)
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"
        assert violations[0].line_number == 2

    def test_rfc2606_and_real_email_on_same_line(self, tmp_path: Path) -> None:
        """Regression: RFC 2606 email first on a line must not suppress real email on the same line."""
        content = "Doc: user@example.com Coach: coach@school.org\n"
        path = _write_file(tmp_path, "mixed.txt", content)
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"
        assert violations[0].line_number == 1


# ---------------------------------------------------------------------------
# Unit tests: path exclusions for epics/ and .project/ (E-129-02 AC-5)
# ---------------------------------------------------------------------------

class TestNewSkipPaths:
    """AC-5/AC-7: epics/ and .project/ are excluded by SKIP_PATHS."""

    def test_epics_path_skipped(self) -> None:
        assert should_skip_path("epics/E-129-01-rfc2606-domain-allowlist.md") is True

    def test_epics_nested_path_skipped(self) -> None:
        assert should_skip_path("epics/E-129-pii-scanner-allowlists/epic.md") is True

    def test_project_path_skipped(self) -> None:
        assert should_skip_path(".project/ideas/IDEA-042-foo.md") is True

    def test_project_archive_skipped(self) -> None:
        assert should_skip_path(".project/archive/E-001/epic.md") is True

    def test_docs_not_skipped(self) -> None:
        # docs/ is intentionally NOT excluded -- could contain real PII
        assert should_skip_path("docs/api/README.md") is False

    def test_tests_not_skipped(self) -> None:
        # tests/ is intentionally NOT excluded -- SYNTHETIC_MARKER handles it
        assert should_skip_path("tests/test_pii_scanner.py") is False


class TestEpicsPathExclusionIntegration:
    """AC-1/AC-2/AC-7: Files under epics/ and .project/ are skipped during scan."""

    def test_epics_file_skipped(self, tmp_path: Path) -> None:
        """AC-1: epics/ file with real email produces no finding."""
        # Write the file under a simulated epics/ path by using should_skip_path
        # directly -- we can't create epics/ under tmp_path and test via scan_file
        # because scan_file uses the path string for prefix matching.
        assert should_skip_path("epics/E-129-pii-scanner-allowlists/E-129-01-rfc2606-domain-allowlist.md") is True

    def test_project_ideas_file_skipped(self) -> None:
        """AC-2: .project/ideas/ file with email address is skipped."""
        assert should_skip_path(".project/ideas/IDEA-042-foo.md") is True

    def test_scan_file_skips_epics_path(self, tmp_path: Path) -> None:
        """scan_file returns empty when the path string starts with epics/."""
        # Create a real file but pass it with an epics/ prefix path
        real_file = tmp_path / "story.md"
        real_file.write_text("coach@realdomain.com\n")
        # Simulate what the scanner sees: the path as reported by git
        violations = scan_file("epics/fake-story.md")
        assert violations == []


# ---------------------------------------------------------------------------
# Unit tests: inline suppression (E-129-02 AC-3/AC-4/AC-6/AC-8)
# ---------------------------------------------------------------------------

class TestInlineSuppression:
    """AC-3/AC-4/AC-6/AC-7/AC-8: pii-ok marker suppresses findings on a line."""

    def test_suppressed_line_not_reported(self, tmp_path: Path) -> None:
        """AC-3: Line with # pii-ok is not reported."""
        path = _write_file(
            tmp_path,
            "config.py",
            'email = "jason@realdomain.com"  # pii-ok\n',
        )
        violations = scan_file(path)
        assert violations == []

    def test_unsuppressed_line_is_reported(self, tmp_path: Path) -> None:
        """AC-4: Line without # pii-ok IS reported."""
        path = _write_file(
            tmp_path,
            "config.py",
            'email = "jason@realdomain.com"\n',
        )
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"

    def test_html_suppression_form(self, tmp_path: Path) -> None:
        """AC-8: <!-- pii-ok --> also suppresses (contains 'pii-ok' substring)."""
        path = _write_file(
            tmp_path,
            "page.html",
            '<p>Contact: coach@realdomain.com <!-- pii-ok --></p>\n',
        )
        violations = scan_file(path)
        assert violations == []

    def test_suppressed_bearer_token(self, tmp_path: Path) -> None:
        """Suppression works for non-email patterns too."""
        path = _write_file(
            tmp_path,
            "docs.md",
            'Authorization: Bearer eyEXAMPLETOKEN123abc  # pii-ok\n',
        )
        violations = scan_file(path)
        assert violations == []

    def test_suppression_only_on_marked_line(self, tmp_path: Path) -> None:
        """Suppression is per-line: other lines still flagged."""
        content = (
            'email = "jason@realdomain.com"  # pii-ok\n'
            'other = "coach@school.org"\n'
        )
        path = _write_file(tmp_path, "config.py", content)
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].line_number == 2

    def test_suppression_marker_alone_no_crash(self, tmp_path: Path) -> None:
        """A line containing only the marker does not crash."""
        path = _write_file(tmp_path, "notes.txt", "# pii-ok\n")
        violations = scan_file(path)
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
            '{"email": "test@realdomain.com"}\n',
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
        p1 = _write_file(tmp_path, "a.json", '{"email": "test@realdomain.com"}\n')
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


# ---------------------------------------------------------------------------
# Tests: success confirmation output (E-022-01)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Integration tests: placeholder email allowlist (E-144-01)
# ---------------------------------------------------------------------------

class TestPlaceholderEmailAllowlist:
    """AC-1 through AC-5: Placeholder email allowlist filtering tests."""

    # (a) Each seeded email produces no violations via scan_file
    @pytest.mark.parametrize("email", [
        "your@email.com",
        "user@email.com",
        "user@domain.com",
        "admin@domain.com",
        "admin@yourcompany.com",
        "info@yourcompany.com",
        "user@yourdomain.com",
        "admin@yourdomain.com",
    ])
    def test_seeded_email_not_reported(self, tmp_path: Path, email: str) -> None:
        """Each seed placeholder email produces no violation."""
        path = _write_file(tmp_path, "doc.md", f"Contact: {email}\n")
        violations = scan_file(path)
        assert violations == [], f"Expected no violation for {email}"

    # (b) A similar-but-not-listed email still gets flagged
    def test_similar_email_still_flagged(self, tmp_path: Path) -> None:
        """me@domain.com is not in the allowlist and must still be reported."""
        path = _write_file(tmp_path, "doc.md", "Contact: me@domain.com\n")
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "email"

    # (c) Case-insensitive matching
    def test_uppercase_placeholder_not_reported(self, tmp_path: Path) -> None:
        """Uppercase variant of a seeded email is also skipped."""
        path = _write_file(tmp_path, "doc.md", "Contact: USER@DOMAIN.COM\n")
        violations = scan_file(path)
        assert violations == []

    def test_mixed_case_placeholder_not_reported(self, tmp_path: Path) -> None:
        """Mixed-case variant of a seeded email is also skipped."""
        path = _write_file(tmp_path, "doc.md", "Contact: Admin@YourCompany.com\n")
        violations = scan_file(path)
        assert violations == []

    # Unit tests for is_placeholder_email directly
    def test_is_placeholder_email_match(self) -> None:
        assert is_placeholder_email("user@domain.com") is True

    def test_is_placeholder_email_case_insensitive(self) -> None:
        assert is_placeholder_email("USER@DOMAIN.COM") is True

    def test_is_placeholder_email_not_in_list(self) -> None:
        assert is_placeholder_email("me@domain.com") is False

    def test_is_placeholder_email_real_domain(self) -> None:
        assert is_placeholder_email("jason@realdomain.com") is False

    def test_placeholder_emails_allowlist_exact_contents(self) -> None:
        """Guard: PLACEHOLDER_EMAILS must equal the exact TN-1 seed set -- no more, no less."""
        expected: frozenset[str] = frozenset({
            "your@email.com",
            "user@email.com",
            "user@domain.com",
            "admin@domain.com",
            "admin@yourcompany.com",
            "info@yourcompany.com",
            "user@yourdomain.com",
            "admin@yourdomain.com",
        })
        assert PLACEHOLDER_EMAILS == expected


class TestSuccessConfirmation:
    """E-022-01: Scanner prints confirmation on clean scans."""

    def test_confirmation_on_clean_scan(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """AC-1/AC-6: Confirmation line printed for clean scans."""
        p1 = _write_file(tmp_path, "a.py", "x = 1\n")
        p2 = _write_file(tmp_path, "b.py", "y = 2\n")
        monkeypatch.setattr("sys.argv", ["pii_scanner", p1, p2])
        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[pii-scan] Scanned 2 file(s), 0 violations." in captured.err

    def test_no_confirmation_on_empty_file_list(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """AC-2: No confirmation when no files to scan."""
        monkeypatch.setattr("sys.argv", ["pii_scanner", "--staged"])
        monkeypatch.setattr(
            "src.safety.pii_scanner.get_staged_files", lambda: []
        )
        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "[pii-scan]" not in captured.err

    def test_no_confirmation_on_violations(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """AC-3: No confirmation when violations are found."""
        dirty = _write_file(tmp_path, "dirty.json", '{"email": "test@realdomain.com"}\n')
        monkeypatch.setattr("sys.argv", ["pii_scanner", dirty])
        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[PII BLOCKED]" in captured.err
        assert "[pii-scan] Scanned" not in captured.err
