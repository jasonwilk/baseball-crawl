"""
Integration tests for the PostToolUse edit-verification hook
(`.claude/hooks/edit-verify.sh`).

The hook re-reads the target of an Edit/Write and confirms the written content
landed. It distinguishes transient flakiness (empty/unreadable re-read -> retry
once, then warn, never hard-fail) from a genuinely-absent edit (file readable
but content missing -> top-level {"decision":"block"} signal). These tests feed
crafted PostToolUse stdin JSON to the hook via subprocess and assert its
stdout/stderr/exit behavior for the present / absent / transient-empty cases
(E-231-02 AC-3 through AC-5), plus the Write path and the empty-new_string
no-op case.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK = PROJECT_ROOT / ".claude" / "hooks" / "edit-verify.sh"


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    """Invoke the hook with a PostToolUse JSON payload on stdin."""
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def _edit_payload(file_path: Path, new_string: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(file_path), "new_string": new_string},
    }


def _write_payload(file_path: Path, content: str) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": str(file_path), "content": content},
    }


@pytest.mark.integration
class TestEditLanded:
    """AC-5: an Edit/Write that did land passes silently (no false alarm)."""

    def test_present_single_line(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("line one\nhello world\nline three\n")
        result = _run_hook(_edit_payload(f, "hello world"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "block" not in result.stdout

    def test_present_multiline(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("header\nalpha\nbeta\ngamma\nfooter\n")
        result = _run_hook(_edit_payload(f, "alpha\nbeta\ngamma"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_write_present(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        body = "full written body\nsecond line\n"
        f.write_text(body)
        result = _run_hook(_write_payload(f, body))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestWriteEquality:
    """Write uses whole-file equality, not substring (P1 remediation).

    For a Write the written content IS the whole file, so a substring test is
    too weak: a failed Write that left stale surrounding bytes would pass
    silently. Write must require whole-file equality.
    """

    @pytest.mark.integration
    def test_write_with_stale_surrounding_bytes_blocks(self, tmp_path: Path) -> None:
        # Write "body\n" but the file still holds prefix/suffix around it — a
        # substring test would pass; equality must block.
        f = tmp_path / "f.txt"
        f.write_text("prefix\nbody\nsuffix\n")
        result = _run_hook(_write_payload(f, "body\n"))
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"

    @pytest.mark.integration
    def test_clean_write_passes_under_equality(self, tmp_path: Path) -> None:
        # A correct Write yields FILE_CONTENT == VALUE after $() strip.
        f = tmp_path / "f.txt"
        body = "exact body\nonly\n"
        f.write_text(body)
        result = _run_hook(_write_payload(f, body))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


@pytest.mark.integration
class TestEditAbsent:
    """AC-4: a confirmed real-absent edit emits a top-level block decision."""

    def test_absent_blocks_and_names_file(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("line one\nDIFFERENT content\nline three\n")
        result = _run_hook(_edit_payload(f, "hello world"))
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"
        assert str(f) in decision["reason"]
        assert "did not land" in decision["reason"]

    def test_partial_multiline_landing_blocks(self, tmp_path: Path) -> None:
        # 'gamma' never landed -> the full multiline new_string is absent.
        f = tmp_path / "f.txt"
        f.write_text("header\nalpha\nbeta\nfooter\n")
        result = _run_hook(_edit_payload(f, "alpha\nbeta\ngamma"))
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"


@pytest.mark.integration
class TestTransientEmpty:
    """AC-3: empty/unreadable re-read -> retry then warn, never hard-fail/block."""

    def test_empty_file_warns_no_block(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("")  # empty: should-exist-but-empty transient case
        result = _run_hook(_edit_payload(f, "hello world"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""  # no block on stdout
        assert "uncertain" in result.stderr

    def test_missing_file_warns_no_block(self, tmp_path: Path) -> None:
        f = tmp_path / "does-not-exist.txt"
        result = _run_hook(_edit_payload(f, "hello world"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "uncertain" in result.stderr

    def test_dark_content_read_does_not_block(self, tmp_path: Path) -> None:
        # Regression for the unified-read fix: a file of only newlines passes a
        # `test -s` non-empty check but yields EMPTY captured content (command
        # substitution strips trailing newlines). A stat-gate-only design would
        # fall through to a false "did not land" block; the unified content read
        # must treat the empty content as transient -> warn, never block.
        f = tmp_path / "f.txt"
        f.write_text("\n\n\n")
        result = _run_hook(_edit_payload(f, "hello world"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""  # no block on a dark/empty content read
        assert "uncertain" in result.stderr


@pytest.mark.integration
class TestNoOp:
    """An empty new_string (e.g. a deletion Edit) has nothing to verify."""

    def test_empty_new_string_passes_silently(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("whatever\n")
        result = _run_hook(_edit_payload(f, ""))
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert result.stderr.strip() == ""
