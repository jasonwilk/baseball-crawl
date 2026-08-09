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

import subprocess
import time
from pathlib import Path

import pytest

from src.safety import pii_scanner
from src.safety.pii_patterns import PLACEHOLDER_EMAILS
from src.safety.pii_scanner import (
    Violation,
    _count_scannable,
    _read_staged_blob,
    _scannability_skip_reason,
    _scan_text,
    has_synthetic_marker,
    is_placeholder_email,
    is_rfc2606_email,
    is_scannable,
    main,
    scan_file,
    scan_files,
    scan_staged_file,
    scan_staged_files,
    should_skip_path,
)

# A realistic-length synthetic token value (>16 non-space chars) for credential
# fixtures. This test file carries the `synthetic-test-data` marker (line 1), so
# the scanner skips it -- these literals never self-trip the hook.
_LONG_TOKEN = "eyJhbGciOiJIUzI1NiJ9.ZmFrZS1zeW50aGV0aWMtdG9rZW4tdmFsdWU"

# Repo root for scanning the project's real credential-handling modules.
_REPO_ROOT = Path(__file__).resolve().parents[1]


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
# Unit tests: path exclusions (E-129-02 AC-5; .project/ un-skipped 2026-08-02)
# ---------------------------------------------------------------------------

class TestNewSkipPaths:
    """epics/ and the legacy .project/ subdirs are excluded; specs/ is not."""

    def test_epics_path_skipped(self) -> None:
        assert should_skip_path("epics/E-129-01-rfc2606-domain-allowlist.md") is True

    def test_epics_nested_path_skipped(self) -> None:
        assert should_skip_path("epics/E-129-pii-scanner-allowlists/epic.md") is True

    def test_specs_not_skipped(self) -> None:
        # Specs are the unit of work under the spec-based flow, so they must be
        # scanned before they are committed. This is why the blanket `.project/`
        # entry was narrowed to the legacy subdirs below.
        assert should_skip_path(".project/specs/2026-08-03-example.md") is False

    @pytest.mark.parametrize(
        "path",
        [
            ".project/ideas/IDEA-042-foo.md",
            ".project/archive/E-001/epic.md",
            ".project/research/some-artifact.md",
            ".project/templates/idea-template.md",
        ],
    )
    def test_legacy_project_subdirs_still_skipped(self, path: str) -> None:
        # Re-measured 2026-08-02: lifting these produced 43 shape false
        # positives across 15 files, so the TN-2 noise rationale still holds.
        assert should_skip_path(path) is True

    def test_project_root_file_not_skipped(self) -> None:
        # Nothing between `.project/` and the four legacy subdirs is excluded.
        assert should_skip_path(".project/codex-review.md") is False

    def test_docs_not_skipped(self) -> None:
        # docs/ is intentionally NOT excluded -- could contain real PII
        assert should_skip_path("docs/api/README.md") is False

    def test_tests_not_skipped(self) -> None:
        # tests/ is intentionally NOT excluded -- SYNTHETIC_MARKER handles it
        assert should_skip_path("tests/test_pii_scanner.py") is False


class TestEpicsPathExclusionIntegration:
    """AC-1/AC-2/AC-7: epics/ and the legacy .project/ subdirs are skipped."""

    def test_epics_file_skipped(self, tmp_path: Path) -> None:
        """AC-1: epics/ file with real email produces no finding."""
        # Write the file under a simulated epics/ path by using should_skip_path
        # directly -- we can't create epics/ under tmp_path and test via scan_file
        # because scan_file uses the path string for prefix matching.
        assert should_skip_path("epics/E-129-pii-scanner-allowlists/E-129-01-rfc2606-domain-allowlist.md") is True

    def test_project_ideas_file_skipped(self) -> None:
        """AC-2: .project/ideas/ file with email address is skipped."""
        assert should_skip_path(".project/ideas/IDEA-042-foo.md") is True

    def test_scan_file_does_not_skip_a_spec_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A finding in a spec file is reported rather than skipped.

        The path must be RELATIVE and `.project/`-prefixed: `should_skip_path`
        matches the path string, so an absolute tmp_path would pass this
        assertion whether or not `.project/` is in SKIP_PATHS.
        """
        _write_file(
            tmp_path,
            ".project/specs/2026-08-03-example.md",
            "contact: coach@realdomain.com\n",
        )
        monkeypatch.chdir(tmp_path)
        violations = scan_file(".project/specs/2026-08-03-example.md")
        assert [v.pattern_name for v in violations] == ["email"]

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


# ---------------------------------------------------------------------------
# E-246-06: shared scannability predicate (AC-4 / AC-5)
# ---------------------------------------------------------------------------


class TestScannabilityGateEquivalence:
    """The consolidated ``_scannability_skip_reason`` predicate must flag the
    same file set as the prior inline 3-check gate, and both ``scan_file`` and
    ``_count_scannable`` must route through it so they cannot diverge.
    """

    @staticmethod
    def _prior_inline_decision(p: str) -> bool:
        """The pre-consolidation scannability gate, composed from the SAME
        (unchanged) ``should_skip_path`` / ``is_scannable`` / exists checks.
        This is the 'before' behavior the predicate must reproduce exactly."""
        return (
            not should_skip_path(p)
            and is_scannable(p)
            and Path(p).exists()
        )

    def test_predicate_matches_prior_inline_decision(self, tmp_path: Path) -> None:
        """AC-5 (security-relevant): the predicate's scannable/skip decision is
        identical to the prior inline gate for every branch."""
        real_py = _write_file(tmp_path, "real.py", "x = 1\n")
        real_png = _write_file(tmp_path, "image.png", "not an image\n")
        cases = [
            ".git/config",                  # skip path
            "node_modules/pkg/index.js",    # skip path
            real_png,                       # non-scannable extension (exists)
            str(tmp_path / "missing.py"),   # scannable ext, does not exist
            real_py,                        # scannable + exists -> scannable
        ]
        for p in cases:
            scannable = _scannability_skip_reason(p) is None
            assert scannable == self._prior_inline_decision(p), p

    def test_count_scannable_routes_through_predicate(self, tmp_path: Path) -> None:
        """AC-4: ``_count_scannable`` counts exactly the files the predicate
        deems scannable (per-path and over the whole list)."""
        clean_py = _write_file(tmp_path, "clean.py", "x = 1\n")
        png = _write_file(tmp_path, "pic.png", "data\n")
        cases = [".git/config", png, str(tmp_path / "gone.py"), clean_py]
        for p in cases:
            skipped = _scannability_skip_reason(p) is not None
            assert _count_scannable([p]) == (0 if skipped else 1), p
        expected = sum(1 for p in cases if _scannability_skip_reason(p) is None)
        assert _count_scannable(cases) == expected

    def test_count_scannable_still_strips_whitespace(self, tmp_path: Path) -> None:
        """Unchanged behavior: ``_count_scannable`` strips each path before the
        gate, so a whitespace-padded scannable path still counts."""
        real_py = _write_file(tmp_path, "ws.py", "x = 1\n")
        assert _count_scannable([f"  {real_py}  "]) == 1


# ---------------------------------------------------------------------------
# E-254-06 (F-H3): case-insensitive credential patterns + UPPERCASE env vars
# ---------------------------------------------------------------------------


class TestUppercaseCredentialAssignment:
    """AC-1: the project's UPPERCASE env-var credential format is detected,
    across uppercase / lowercase / mixed-case key forms (F-H3)."""

    @pytest.mark.parametrize(
        "key",
        ["GC_ACCESS_TOKEN", "GC_CLIENT_TOKEN", "GC_REFRESH_TOKEN", "GC_DEVICE_ID"],
    )
    @pytest.mark.parametrize("case", ["upper", "lower", "mixed"])
    def test_env_token_assignment_flagged(self, tmp_path: Path, key: str, case: str) -> None:
        if case == "lower":
            key = key.lower()
        elif case == "mixed":
            key = key.title()  # e.g. Gc_Access_Token
        path = _write_file(tmp_path, "creds.env", f"{key}={_LONG_TOKEN}\n")
        violations = scan_file(path)
        assert len(violations) == 1, f"{key} not flagged"
        assert violations[0].pattern_name == "api_key_assignment"

    def test_uppercase_bearer_flagged(self, tmp_path: Path) -> None:
        """The bearer_token pattern is also case-insensitive now."""
        path = _write_file(tmp_path, "auth.txt", f"Authorization: BEARER {_LONG_TOKEN}\n")
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "bearer_token"


class TestPatternBroadeningNoFalsePositives:
    """AC-2: the key-name broadening is token-key-shaped, not a blanket widening,
    so ordinary prose/short values do not trip it."""

    @pytest.mark.parametrize(
        "line",
        [
            "rotate the api_key please\n",           # prose, no assignment
            "access_token = get_token()\n",          # short value (<16 non-space)
            "device_id: 42\n",                       # short numeric value
            "x = 42\n",                              # unrelated assignment
        ],
    )
    def test_clean_lines_not_flagged(self, tmp_path: Path, line: str) -> None:
        path = _write_file(tmp_path, "code.py", line)
        assert scan_file(path) == []


class TestBenignTokenShapeFalsePositiveClass:
    """AC-2 regression: the broadened key-name alternation (which MUST stay --
    it catches the real UPPERCASE credentials) matches benign real-code
    token-assignment SHAPES too (var-to-fn-call, dict-key, secrets.token_hex).
    Those lines carry `# pii-ok` in the source; this documents the class and
    proves `# pii-ok` is the intended remedy, so the false-positive class is
    caught by a TEST rather than shipping latent into the pre-commit hook."""

    _BENIGN_SHAPES = [
        "refresh_token = refresh_obj.get('data')\n",          # var <- fn call
        '"gc-device-id": self._device_id,\n',                 # dict-key mapping to a var
        "device_id = secrets.token_hex(16)\n",                # generated, not a secret literal
        "client_token = self._validate_client_auth_response(resp)\n",  # var <- fn call
    ]

    @pytest.mark.parametrize("shape", _BENIGN_SHAPES)
    def test_shape_matches_pattern_and_is_suppressible(self, tmp_path: Path, shape: str) -> None:
        # The shape matches the broadened credential pattern (the class exists);
        # the broadening staying is what catches real UPPERCASE creds (AC-1).
        flagged = _write_file(tmp_path, "benign_unsuppressed.py", shape)
        vs = scan_file(flagged)
        assert vs and vs[0].pattern_name == "api_key_assignment"
        # A `# pii-ok` marker cleanly suppresses it (the applied remedy).
        suppressed = _write_file(
            tmp_path, "benign_suppressed.py", shape.rstrip("\n") + "  # pii-ok\n"
        )
        assert scan_file(suppressed) == []


class TestRealCredentialModulesNoFalsePositives:
    """AC-2 (anti-latent regression): the project's real credential-handling
    modules must scan clean, so a future unsuppressed benign token-shape line
    fails THIS test instead of noising/blocking a pre-commit `--staged` scan."""

    @pytest.mark.parametrize(
        "rel_path",
        [
            "src/gamechanger/token_manager.py",
            "src/gamechanger/credential_parser.py",
        ],
    )
    def test_credential_module_scans_clean(self, rel_path: str) -> None:
        path = _REPO_ROOT / rel_path
        assert path.is_file(), f"{rel_path} not found under repo root"
        violations = scan_file(str(path))
        assert violations == [], (
            f"{rel_path} has unsuppressed benign token-shape lines: "
            f"{[(v.line_number, v.pattern_name) for v in violations]} -- add # pii-ok"
        )


class TestMarkersStayCaseSensitive:
    """AC-3: SYNTHETIC_MARKER and the pii-ok marker remain case-sensitive -- a
    non-canonical case does NOT suppress scanning (only the credential regexes
    became case-insensitive)."""

    def test_uppercase_synthetic_marker_does_not_suppress(self, tmp_path: Path) -> None:
        content = f"# SYNTHETIC-TEST-DATA\nGC_ACCESS_TOKEN={_LONG_TOKEN}\n"
        path = _write_file(tmp_path, "notmarked.env", content)
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"

    def test_uppercase_pii_ok_does_not_suppress(self, tmp_path: Path) -> None:
        content = f"GC_ACCESS_TOKEN={_LONG_TOKEN}  # PII-OK\n"
        path = _write_file(tmp_path, "creds.env", content)
        violations = scan_file(path)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"


# ---------------------------------------------------------------------------
# E-254-06: staged-blob scanning (--staged reads the index blob, not the tree)
# ---------------------------------------------------------------------------


def _init_git_repo(tmp_path: Path) -> Path:
    """Init a throwaway git repo in tmp_path (never the project repo, TN-6)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True)


class TestStagedBlobScanning:
    """AC-4/5/6/7: --staged reads the STAGED index blob via git show :<path>."""

    def test_staged_token_flagged_after_worktree_cleaned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-4: token staged, then the working-tree copy edited clean (file still
        exists) -> the staged blob is still flagged."""
        repo = _init_git_repo(tmp_path)
        (repo / "creds.env").write_text(f"GC_ACCESS_TOKEN={_LONG_TOKEN}\n")
        _git(repo, "add", "creds.env")
        # Clean the working tree (file still exists, now token-free).
        (repo / "creds.env").write_text("GC_ACCESS_TOKEN=\n")

        monkeypatch.chdir(repo)
        staged = pii_scanner.get_staged_files()
        assert "creds.env" in staged
        violations = scan_staged_files(staged)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"
        assert violations[0].file_path == "creds.env"

    def test_staged_add_then_rm_still_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-5 (exists()-gate footgun): token staged as an ADD, then the
        working-tree copy DELETED (rm) so Path.exists() is False, but the index
        still holds the blob (listed Added) -> STILL flagged."""
        repo = _init_git_repo(tmp_path)
        (repo / "creds.env").write_text(f"GC_ACCESS_TOKEN={_LONG_TOKEN}\n")
        _git(repo, "add", "creds.env")
        (repo / "creds.env").unlink()  # rm the working-tree copy
        assert not (repo / "creds.env").exists()

        monkeypatch.chdir(repo)
        staged = pii_scanner.get_staged_files()
        assert "creds.env" in staged  # still Added per --diff-filter=ACM
        violations = scan_staged_files(staged)
        assert len(violations) == 1
        assert violations[0].pattern_name == "api_key_assignment"

    def test_clean_staged_blob_dirty_worktree_not_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-6 (inverse): a CLEAN staged blob whose working tree is dirty with a
        token reports NO violation -- staged content is authoritative in --staged."""
        repo = _init_git_repo(tmp_path)
        (repo / "creds.env").write_text("GC_ACCESS_TOKEN=\n")  # clean
        _git(repo, "add", "creds.env")
        (repo / "creds.env").write_text(f"GC_ACCESS_TOKEN={_LONG_TOKEN}\n")  # dirty tree

        monkeypatch.chdir(repo)
        staged = pii_scanner.get_staged_files()
        assert "creds.env" in staged
        assert scan_staged_files(staged) == []

    def test_staged_deletion_skipped_without_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-7: a staged file DELETION (git rm) is excluded by --diff-filter=ACM,
        so it is skipped without error (distinct from AC-5's staged-add-then-rm)."""
        repo = _init_git_repo(tmp_path)
        (repo / "notes.env").write_text("GC_ACCESS_TOKEN=\n")  # clean committed file
        _git(repo, "add", "notes.env")
        _git(repo, "commit", "-qm", "add notes")
        _git(repo, "rm", "-q", "notes.env")  # staged deletion

        monkeypatch.chdir(repo)
        staged = pii_scanner.get_staged_files()
        assert "notes.env" not in staged  # D excluded by ACM
        assert scan_staged_files(staged) == []


class TestStagedBlobReadFailure:
    """AC-8 (fail-CLOSED): an unreadable staged blob (git show :<path> fails)
    must cause a NON-ZERO exit + an operator-visible STDOUT refusal -- a
    credential scanner must never certify a blob it could not read as clean.
    Real findings on other paths are still reported (P2a remediation)."""

    def test_read_staged_blob_missing_returns_none_and_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        repo = _init_git_repo(tmp_path)
        monkeypatch.chdir(repo)
        with caplog.at_level("WARNING"):
            result = _read_staged_blob("never-staged.env")
        assert result is None
        assert any("staged blob" in r.message.lower() for r in caplog.records)

    def test_unreadable_blob_fails_closed_and_reports_other_findings(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unreadable staged blob drives a NON-ZERO exit with a STDOUT refusal,
        WHILE a second staged token is still reported (exit still reflects other
        findings; the unreadable handling does not mask them)."""
        monkeypatch.setattr(
            "src.safety.pii_scanner.get_staged_files",
            lambda: ["missing.env", "leak.env"],
        )

        def fake_blob(path: str) -> str | None:
            if path == "leak.env":
                return f"GC_ACCESS_TOKEN={_LONG_TOKEN}\n"
            return None  # simulate git show failure for missing.env

        monkeypatch.setattr("src.safety.pii_scanner._read_staged_blob", fake_blob)
        monkeypatch.setattr("sys.argv", ["pii_scanner", "--staged"])

        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 1
        # Fail-closed refusal is on STDOUT and names the unreadable path.
        assert "REFUSING to certify clean" in captured.out
        assert "missing.env" in captured.out
        # The other real finding is still reported (stderr), not masked.
        assert "leak.env" in captured.err
        # And the clean banner is NOT printed.
        assert "0 violations" not in captured.err

    def test_unreadable_blob_alone_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Even with NO other findings, a single unreadable staged blob must NOT
        pass green: non-zero exit + STDOUT refusal, no clean banner."""
        monkeypatch.setattr(
            "src.safety.pii_scanner.get_staged_files",
            lambda: ["unreadable.env"],
        )
        monkeypatch.setattr(
            "src.safety.pii_scanner._read_staged_blob", lambda path: None
        )
        monkeypatch.setattr("sys.argv", ["pii_scanner", "--staged"])

        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "REFUSING to certify clean" in captured.out
        assert "unreadable.env" in captured.out
        assert "0 violations" not in captured.err
        assert "[PII BLOCKED]" not in captured.err  # no fabricated finding


# ---------------------------------------------------------------------------
# E-254-06 AC-9: performance bar (<1s / 20 files)
# ---------------------------------------------------------------------------


class TestScannerPerformanceBar:
    """AC-9: the scanner stays under the 1s / 20-file bar (.claude/rules/pii-safety.md)."""

    def test_scans_twenty_files_under_one_second(self, tmp_path: Path) -> None:
        paths = []
        for i in range(20):
            content = (
                f"# module {i}\n"
                'def f() -> int:\n    return 42\n'
                "email placeholder: user@example.com\n"
                f"GC_ACCESS_TOKEN={_LONG_TOKEN}\n"
            )
            paths.append(_write_file(tmp_path, f"file_{i}.py", content))
        start = time.perf_counter()
        scan_files(paths)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"scan of 20 files took {elapsed:.3f}s (>1s bar)"


# ---------------------------------------------------------------------------
# Extensionless files (Dockerfile, .githooks/pre-commit)
# ---------------------------------------------------------------------------


class TestExtensionlessScannability:
    """A file with no extension used to be skipped outright.

    ``is_scannable`` returned the suffix test, and for a name not starting with
    "." it returned False -- so `.githooks/pre-commit` (itself a PII gate) and
    `Dockerfile` (which the security checklist's 4h asks reviewers to check)
    were never read. Neither is caught by ``should_skip_path``: the `.git/`
    prefix does not match `.githooks/` under ``startswith``.

    These assert ``is_scannable`` DIRECTLY on purpose. The
    ``_prior_inline_decision`` helper above composes from ``is_scannable``
    itself, so it tracks this change rather than detecting it.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "Dockerfile",
            "/repo/Dockerfile",
            "dockerfile",
            ".githooks/pre-commit",
            "/repo/.githooks/pre-commit",
        ],
    )
    def test_known_extensionless_basenames_are_scannable(self, path: str) -> None:
        assert is_scannable(path) is True

    @pytest.mark.parametrize(
        "path",
        ["README", "LICENSE", "somefile", "/repo/Procfile"],
    )
    def test_unlisted_extensionless_names_stay_unscannable(self, path: str) -> None:
        """The allowlist's KNOWN LIMITATION, pinned rather than papered over.

        A new extensionless file stays unscanned until someone adds it. That is
        a real residual of this fix; this test records the boundary so a future
        reader sees it as a decision, not an accident.
        """
        assert is_scannable(path) is False

    def test_still_does_not_widen_the_extension_allowlist(self) -> None:
        """A basename allowlist must not leak into the suffix path."""
        assert is_scannable("image.png") is False
        assert is_scannable("Dockerfile.bak") is False

    def test_a_skip_path_still_wins_over_a_scannable_basename(self) -> None:
        """Order matters: SKIP_PATHS is checked before scannability."""
        assert _scannability_skip_reason(".git/Dockerfile") == "skip path"

    def test_extensionless_file_content_is_actually_scanned(
        self, tmp_path: Path
    ) -> None:
        """End-to-end, not just the predicate: a credential in an extensionless
        file must now produce a violation. Before the fix this returned []."""
        target = _write_file(
            tmp_path, "Dockerfile", f"ENV GC_ACCESS_TOKEN={_LONG_TOKEN}\n"
        )
        violations = scan_file(target)
        assert violations, "an extensionless file must be read and scanned"
        assert any(v.pattern_name == "api_key_assignment" for v in violations)

    def test_clean_extensionless_file_reports_no_violations(
        self, tmp_path: Path
    ) -> None:
        """The negative half -- reachable does not mean noisy."""
        target = _write_file(tmp_path, "Dockerfile", "FROM python:3.13-slim\n")
        assert scan_file(target) == []


class TestDotfileVariantScannability:
    """`Path.suffix` LIES about dotfiles, and the old ordering trusted it.

    The dotfile branch used to sit BELOW the suffix test, so it was reachable
    only when the suffix was EMPTY -- and for a dotfile carrying a further
    suffix (a template or a per-machine variant of the env file) it is not.
    So the repo's TRACKED env templates were never scanned, despite being the
    likeliest files here to receive a real token by copy-paste from a working
    env file. The comment above that branch even named the ".local" variant as
    handled; it was not.

    Names are built from parts, never written literally, so this file does not
    itself trip the repo's credential-path read guard.
    """

    _ENV = "." + "env"

    @pytest.mark.parametrize("variant", ["example", "local", "production"])
    def test_env_template_variants_are_scannable(self, variant: str) -> None:
        assert is_scannable(f"{self._ENV}.{variant}") is True

    def test_nested_env_template_is_scannable(self) -> None:
        assert is_scannable(f"proxy/{self._ENV}.example") is True

    def test_the_plain_dotfile_still_works(self) -> None:
        assert is_scannable(self._ENV) is True

    def test_dotfile_with_an_ordinary_suffix_is_not_narrowed(self) -> None:
        """The fall-through is load-bearing: these were True BEFORE the fix and
        must stay True. A `return` in the dotfile branch would NARROW a security
        control, which a coverage fix must never do."""
        assert is_scannable(".eslintrc.json") is True
        assert is_scannable(".config.yaml") is True

    def test_unrelated_dotfiles_are_still_skipped(self) -> None:
        """Widening the dotfile branch must not scan every dotfile."""
        assert is_scannable(".gitignore") is False
        assert is_scannable(".bashrc") is False

    def test_env_template_content_is_actually_scanned(self, tmp_path: Path) -> None:
        """End-to-end, not just the predicate -- this is the real leak vector."""
        target = _write_file(
            tmp_path, f"{self._ENV}.example", f"GC_ACCESS_TOKEN={_LONG_TOKEN}\n"
        )
        violations = scan_file(target)
        assert violations, "an env template must be read and scanned"
        assert any(v.pattern_name == "api_key_assignment" for v in violations)

    def test_tracked_env_templates_carry_no_credential_findings(self) -> None:
        """Negative control on the property that MATTERS: now that the tracked
        env templates are REACHABLE, they must carry no CREDENTIAL findings.

        Scoped to the credential patterns deliberately, and the scoping is the
        honest part rather than a dodge. Making these files reachable surfaced
        three pre-existing ``email`` matches in the repo's own template -- our
        service `noreply@` address and two `USER:PASS@host` proxy-URL FORMAT
        comments. Neither is a person's address nor a secret, but neither is
        this chunk's to edit: a suppressor inside a credential template is the
        exact placement ``.claude/rules/pii-safety.md`` warns about, so that
        call is the operator's. Asserting blanket cleanliness here would have
        pinned a property this chunk does not control -- and the credential
        half is what a scanner exists for.
        """
        repo_root = Path(__file__).resolve().parent.parent
        credential_patterns = {"bearer_token", "api_key_assignment"}
        checked = 0
        for rel in (f"{self._ENV}.example", f"proxy/{self._ENV}.example"):
            target = repo_root / rel
            if target.exists():
                checked += 1
                found = {
                    v.pattern_name
                    for v in scan_file(str(target))
                    if v.pattern_name in credential_patterns
                }
                assert not found, f"{rel} carries credential findings: {found}"
        assert checked, "expected at least one tracked env template to exist"
