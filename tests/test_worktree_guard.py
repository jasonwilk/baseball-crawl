"""
Tests for the PreToolUse write-safety guard (`.claude/hooks/worktree-guard.sh`).

The guard makes two denials: a path containing a `..` segment, and a path
outside the repository other than the session scratchpad and `~/.claude/`.
Everything else passes. It never denies via exit code -- a denial is JSON on
stdout with exit 0, so a test that only checks the return code proves nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK = PROJECT_ROOT / ".claude" / "hooks" / "worktree-guard.sh"

# Resolved at import: the fail-open test hands the child an emptied PATH, and a
# bare "bash" would then fail to launch at all -- a green that says nothing.
BASH = shutil.which("bash") or "/bin/bash"

REPO = "/workspaces/baseball-crawl"


def _run(
    file_path: str,
    *,
    path_override: str | None = None,
    home: str | None = None,
    project_dir: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the guard with a PreToolUse payload on stdin.

    `CLAUDE_PROJECT_DIR` is popped unless a test sets it explicitly, so the
    suite exercises the hardcoded default rather than whatever the harness
    happens to export.
    """
    env = os.environ.copy()
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    if path_override is not None:
        env["PATH"] = path_override
    if home is not None:
        env["HOME"] = home
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path}})
    return subprocess.run(
        [BASH, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _decision(result: subprocess.CompletedProcess[str]) -> str | None:
    """The guard's permissionDecision, or None when it allowed silently."""
    assert result.returncode == 0, f"guard must always exit 0, got {result.returncode}"
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def _reason(result: subprocess.CompletedProcess[str]) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


class TestPathTraversal:
    """`..` is denied wherever it appears, including under the repo root."""

    def test_parent_dir_segment_denied(self) -> None:
        result = _run(f"{REPO}/docs/../src/foo.py")
        assert _decision(result) == "deny"
        assert ".." in _reason(result)

    def test_parent_dir_segment_denied_outside_repo(self) -> None:
        assert _decision(_run("/tmp/claude-1000/../../etc/passwd")) == "deny"

    def test_dots_inside_a_filename_are_not_a_segment(self) -> None:
        assert _decision(_run(f"{REPO}/docs/foo..bar.md")) is None

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp//claude-1000/notes.md",
            "//workspaces/baseball-crawl/src/foo.py",
            f"{REPO}//src/foo.py",
        ],
    )
    def test_double_slash_is_normalised_before_the_prefix_match(self, path: str) -> None:
        """`tr -s '/'` must run before the allow-roots match.

        The first two cases are the ones that discriminate: without the `tr`
        they miss their allow-root pattern and are denied. The third does NOT
        discriminate -- `/workspaces/baseball-crawl/*` glob-matches the extra
        slash because `*` absorbs it -- and is kept only so the repo-root case
        is covered alongside its neighbours. Verified by executing the hook
        with the `tr` line stripped.
        """
        assert _decision(_run(path)) is None


class TestScope:
    """In-repo writes pass; outside-repo writes are denied but for two roots."""

    @pytest.mark.parametrize(
        "rel",
        ["src/foo.py", "tests/test_foo.py", "migrations/001.sql", "CLAUDE.md"],
    )
    def test_in_repo_paths_allowed(self, rel: str) -> None:
        assert _decision(_run(f"{REPO}/{rel}")) is None

    def test_scratchpad_allowed(self) -> None:
        assert _decision(_run("/tmp/claude-1000/session/notes.md")) is None

    def test_claude_home_allowed(self, tmp_path: Path) -> None:
        home = str(tmp_path)
        result = _run(f"{home}/.claude/projects/p/memory/lesson.md", home=home)
        assert _decision(result) is None

    def test_arbitrary_outside_path_denied(self) -> None:
        result = _run("/etc/cron.d/backdoor")
        assert _decision(result) == "deny"
        assert "outside the repository" in _reason(result)

    def test_home_outside_dot_claude_denied(self, tmp_path: Path) -> None:
        home = str(tmp_path)
        assert _decision(_run(f"{home}/.bashrc", home=home)) == "deny"

    def test_repo_root_follows_claude_project_dir(self, tmp_path: Path) -> None:
        """A checkout elsewhere is allowed when CLAUDE_PROJECT_DIR names it."""
        other = str(tmp_path / "checkout")
        assert _decision(_run(f"{other}/src/foo.py", project_dir=other)) is None
        # ...and the default root is no longer allowed under that setting.
        assert _decision(_run(f"{REPO}/src/foo.py", project_dir=other)) == "deny"

    def test_trailing_slash_on_project_dir_is_tolerated(self, tmp_path: Path) -> None:
        other = str(tmp_path / "checkout")
        assert _decision(_run(f"{other}/src/foo.py", project_dir=f"{other}/")) is None

    def test_unset_project_dir_does_not_fail_open(self) -> None:
        """With the var unset the literal default applies, not `/*`."""
        assert _decision(_run("/etc/passwd")) == "deny"

    def test_root_project_dir_does_not_fail_open(self) -> None:
        """`CLAUDE_PROJECT_DIR=/` strips to empty; the arm must not become `/*`."""
        result = _run("/etc/passwd", project_dir="/")
        assert _decision(result) == "deny"
        assert "not a usable repository root" in _reason(result)

    def test_non_canonical_project_dir_still_allows_in_repo_writes(self) -> None:
        """REPO gets the same slash-squeeze as FILE_PATH, or every write denies."""
        assert _decision(_run(f"{REPO}/src/foo.py", project_dir="/workspaces//baseball-crawl")) is None

    def test_relative_path_denied(self) -> None:
        # The Write/Edit tools require absolute paths; a relative one reaching
        # the guard is unexpected, so it fails closed rather than passing.
        assert _decision(_run("src/foo.py")) == "deny"

    def test_worktree_path_denied(self) -> None:
        # Behaviour change from the dispatch-era guard, pinned deliberately:
        # /tmp/.worktrees/ used to pass unconditionally and is now outside-repo.
        assert _decision(_run("/tmp/.worktrees/baseball-crawl-E-999/src/foo.py")) == "deny"


class TestFailOpen:
    """The guard must not wedge the session when it cannot decide."""

    def test_missing_jq_allows(self, tmp_path: Path) -> None:
        empty_bin = tmp_path / "bin"
        empty_bin.mkdir()
        result = _run(f"{REPO}/src/foo.py", path_override=str(empty_bin))
        assert _decision(result) is None

    def test_no_file_path_allows(self) -> None:
        assert _decision(_run("")) is None
