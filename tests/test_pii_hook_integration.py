# synthetic-test-data
# This file contains fake PII patterns for testing the pre-commit hook.
# All data is obviously synthetic -- no real PII appears anywhere.
"""
Integration tests for the git pre-commit hook chain.

These tests create temporary git repos, configure the PII pre-commit hook,
and verify end-to-end behavior: blocked commits, clean commits, success
messages, and synthetic-marker bypass.

Fake PII values used in tests:
- test@example.com (fake email)
- (555) 867-5309 (fake phone)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# Absolute path to the project root (where .githooks/ lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _init_repo(tmp_path: Path) -> Path:
    """Initialize a temp git repo wired to the project's pre-commit hook.

    Creates a git repo in tmp_path, configures core.hooksPath to point at
    the project's .githooks/ directory, sets git user config, and symlinks
    src/safety/ so the hook can find the scanner.

    Returns:
        The tmp_path (for convenience).
    """
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        env=env,
    )

    # Configure git user (required for commits)
    for key, value in [
        ("user.email", "test@localhost"),
        ("user.name", "Test User"),
        ("core.hooksPath", str(PROJECT_ROOT / ".githooks")),
    ]:
        subprocess.run(
            ["git", "config", key, value],
            cwd=tmp_path,
            capture_output=True,
            check=True,
            env=env,
        )

    # Symlink src/safety/ into the temp repo so the hook can resolve the scanner
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "safety").symlink_to(PROJECT_ROOT / "src" / "safety")

    return tmp_path


def _git_commit(repo_path: Path, message: str = "test commit") -> subprocess.CompletedProcess[str]:
    """Run git commit in the given repo and return the result."""
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    return subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        env=env,
    )


def _stage_file(repo_path: Path, name: str, content: str) -> Path:
    """Write a file in the repo, stage it, and return its path."""
    file_path = repo_path / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(
        ["git", "add", name],
        cwd=repo_path,
        capture_output=True,
        check=True,
        env=env,
    )
    return file_path


@pytest.mark.integration
class TestHookBlocksPII:
    """AC-1, AC-3: Hook blocks commits containing PII patterns."""

    def test_email_blocks_commit(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_file(repo, "contact.json", '{"email": "test@example.com"}\n')
        result = _git_commit(repo)
        assert result.returncode != 0

    def test_blocked_output_contains_pii_blocked_and_pattern(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_file(repo, "contact.json", '{"email": "test@example.com"}\n')
        result = _git_commit(repo)
        combined = result.stdout + result.stderr
        assert "[PII BLOCKED]" in combined
        assert "email" in combined


@pytest.mark.integration
class TestHookAllowsClean:
    """AC-2, AC-4: Hook allows clean commits and prints success messages."""

    def test_clean_commit_succeeds(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_file(repo, "clean.py", "x = 42\n")
        result = _git_commit(repo)
        assert result.returncode == 0

    def test_clean_commit_output_contains_success_messages(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_file(repo, "clean.py", "x = 42\n")
        result = _git_commit(repo)
        combined = result.stdout + result.stderr
        assert "[pii-scan] Scanned" in combined
        assert "[pii-hook] PII scan passed." in combined


@pytest.mark.integration
class TestHookSyntheticMarkerBypass:
    """AC-5: Files with synthetic-test-data marker pass even with PII."""

    def test_synthetic_marker_allows_pii(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        content = (
            "# synthetic-test-data\n"
            "# This is test data.\n"
            "coach@school.org\n"
            "(555) 867-5309\n"
        )
        _stage_file(repo, "fixtures.txt", content)
        result = _git_commit(repo)
        assert result.returncode == 0
