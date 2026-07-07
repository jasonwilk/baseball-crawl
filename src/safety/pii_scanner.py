"""
synthetic-test-data
PII and credential scanner for baseball-crawl pre-commit hooks.

Scans files for sensitive data patterns (emails, phone numbers, Bearer tokens,
API keys) and blocks commits when violations are found. Called by both the Git
pre-commit hook and the Claude Code PreToolUse hook.

Usage:
    python3 src/safety/pii_scanner.py --staged       # scan git staged files
    python3 src/safety/pii_scanner.py --stdin         # read file paths from stdin
    python3 src/safety/pii_scanner.py file1 file2     # scan specific files

Exit codes:
    0  -- no PII/credentials detected (or all files skipped)
    1  -- sensitive data detected in one or more files
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from src.safety.pii_patterns import (
    COMPILED_PATTERNS,
    PLACEHOLDER_EMAILS,
    PII_OK_MARKER,
    RFC2606_DOMAINS,
    SCANNABLE_EXTENSIONS,
    SKIP_PATHS,
    SYNTHETIC_MARKER,
)

logger = logging.getLogger(__name__)


class Violation(NamedTuple):
    """A single PII/credential violation found in a file."""
    file_path: str
    line_number: int
    pattern_name: str


def is_rfc2606_email(email: str) -> bool:
    """Return True if the email's domain is an RFC 2606 reserved domain.

    Uses suffix matching: a domain is allowed if it equals a reserved entry
    or ends with "." + a reserved entry. TLD entries like ".test" match any
    domain ending in that TLD.
    """
    at_pos = email.rfind("@")
    if at_pos < 0:
        return False
    domain = email[at_pos + 1:].lower()
    for entry in RFC2606_DOMAINS:
        entry_norm = entry.lstrip(".")
        if domain == entry_norm or domain.endswith("." + entry_norm):
            return True
    return False


def is_placeholder_email(email: str) -> bool:
    """Return True if the email is a known placeholder address.

    Performs case-insensitive exact matching against PLACEHOLDER_EMAILS.
    """
    return email.lower() in PLACEHOLDER_EMAILS


def should_skip_path(file_path: str) -> bool:
    """Check if a file path should be skipped based on SKIP_PATHS prefixes."""
    for prefix in SKIP_PATHS:
        if file_path.startswith(prefix):
            return True
    return False


def is_scannable(file_path: str) -> bool:
    """Check if a file has a scannable extension.

    Handles dotfiles like .env where Path.suffix returns empty string
    but the filename itself is a scannable "extension".
    """
    p = Path(file_path)
    suffix = p.suffix.lower()
    if suffix:
        return suffix in SCANNABLE_EXTENSIONS
    # Handle dotfiles: .env, .env.local, etc.
    name = p.name
    if name.startswith("."):
        # Treat the whole name as the extension (e.g., ".env")
        return name.lower() in SCANNABLE_EXTENSIONS
    return False


def _scannability_skip_reason(file_path: str, check_exists: bool = True) -> str | None:
    """Return why a file is skipped by the scannability gate, or None if scannable.

    The single source of the scannability decision shared by ``scan_file`` and
    ``_count_scannable`` so the two can never diverge. A file is scannable when
    it is not in a skip path, has a scannable extension, and (by default) exists
    on disk.

    ``check_exists=False`` OMITS the working-tree existence check and is used by
    the ``--staged`` path only: a token can be staged as an ADD and then the
    working-tree copy deleted (``rm``), leaving the blob in the index (listed
    Added) while ``Path.exists()`` is False. The staged content is read from the
    blob via ``git show :<path>`` regardless of working-tree existence, so
    reusing the exists() gate there would SKIP that genuine leak vector (F-H3 /
    TN-5 exists()-gate footgun). Callers MUST NOT flip this default for the
    working-tree (``scan_file``) path.
    """
    if should_skip_path(file_path):
        return "skip path"
    if not is_scannable(file_path):
        return "non-scannable extension"
    if check_exists and not Path(file_path).exists():
        return "does not exist"
    return None


def has_synthetic_marker(lines: list[str]) -> bool:
    """Check if the first 5 lines of a file contain the synthetic data marker."""
    for line in lines[:5]:
        if SYNTHETIC_MARKER in line:
            return True
    return False


def _scan_text(file_path: str, text: str) -> list[Violation]:
    """Scan already-read text for PII and credential patterns.

    The shared post-read scanning body consumed by BOTH the working-tree path
    (``scan_file``) and the staged-blob path (``scan_staged_file``), so the two
    apply identical synthetic-marker, ``pii-ok`` suppression, email-allowlist,
    and pattern logic. ``file_path`` is used only for the reported violation
    location and log messages -- the bytes come from ``text``.
    """
    lines = text.splitlines()

    if has_synthetic_marker(lines):
        logger.debug("Skipping (synthetic marker): %s", file_path)
        return []

    violations: list[Violation] = []
    for line_number, line in enumerate(lines, start=1):
        if PII_OK_MARKER in line:
            logger.debug("Skipping suppressed line %s:%d", file_path, line_number)
            continue
        for compiled in COMPILED_PATTERNS:
            for match in compiled["pattern"].finditer(line):
                if compiled["name"] == "email":
                    email = match.group(0)
                    if is_rfc2606_email(email):
                        logger.debug(
                            "Skipping RFC 2606 email match on %s:%d",
                            file_path,
                            line_number,
                        )
                        continue
                    if is_placeholder_email(email):
                        logger.debug(
                            "Skipping placeholder email match on %s:%d",
                            file_path,
                            line_number,
                        )
                        continue
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_number=line_number,
                        pattern_name=compiled["name"],
                    )
                )

    return violations


def scan_file(file_path: str) -> list[Violation]:
    """Scan a single working-tree file for PII and credential patterns.

    Args:
        file_path: Path to the file to scan (relative or absolute).

    Returns:
        List of Violation tuples for any matches found. Empty list if the file
        is clean, skipped, or cannot be read.
    """
    skip_reason = _scannability_skip_reason(file_path)
    if skip_reason is not None:
        logger.debug("Skipping (%s): %s", skip_reason, file_path)
        return []

    path = Path(file_path)
    try:
        text = path.read_text(errors="replace")
    except OSError as e:
        logger.warning("Could not read %s: %s", file_path, e)
        return []

    return _scan_text(file_path, text)


def _read_staged_blob(file_path: str) -> str | None:
    """Return the STAGED blob content for ``file_path`` via ``git show :<path>``.

    Reads the index blob, NOT the working tree -- so a token staged and then
    removed from the working tree is still seen (F-H3 staged-blob gap). Returns
    None (and logs a warning) when the blob cannot be read (no such staged path,
    git absent). An unreadable blob is a FAIL-CLOSED signal, not a skip: the
    caller (:func:`scan_staged` -> ``main``) turns any None into a non-zero exit
    plus an operator-visible refusal, because a credential scanner must never
    certify a blob it could not read as clean. Other paths' real findings are
    still reported alongside the refusal.
    """
    try:
        result = subprocess.run(
            ["git", "show", f":{file_path}"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Could not read staged blob for %s: %s", file_path, e)
        return None


def _scan_staged_one(file_path: str) -> tuple[list[Violation], bool]:
    """Scan one STAGED file's index blob.

    Returns ``(violations, unreadable)`` where ``unreadable`` is True when the
    staged blob could NOT be read (``git show :<path>`` failed). A gate-skipped
    path returns ``([], False)``.

    Applies the skip-path and extension gates but NOT the working-tree
    ``Path.exists()`` gate (TN-5 footgun): the staged content is read from the
    index blob via ``git show :<path>`` regardless of whether the working-tree
    copy still exists, so a staged-add-then-``rm`` token is still caught.
    """
    skip_reason = _scannability_skip_reason(file_path, check_exists=False)
    if skip_reason is not None:
        logger.debug("Skipping staged (%s): %s", skip_reason, file_path)
        return [], False

    text = _read_staged_blob(file_path)
    if text is None:
        # Fail-closed signal (a credential scanner must never certify a blob it
        # could not read as clean). The warning is already logged by
        # _read_staged_blob; the caller turns this into a non-zero exit.
        return [], True

    return _scan_text(file_path, text), False


def scan_staged(file_paths: list[str]) -> tuple[list[Violation], list[str]]:
    """Scan STAGED index blobs, returning ``(violations, unreadable_paths)``.

    ``unreadable_paths`` is the list of staged paths whose blob could not be
    read; ``main`` fails CLOSED (non-zero exit + operator-visible refusal) on
    any such path, so the scanner never reports "clean" on content it did not
    actually scan. Real findings on other paths are still returned.
    """
    all_violations: list[Violation] = []
    unreadable: list[str] = []
    for file_path in file_paths:
        fp = file_path.strip()
        violations, is_unreadable = _scan_staged_one(fp)
        all_violations.extend(violations)
        if is_unreadable:
            unreadable.append(fp)
    return all_violations, unreadable


def scan_staged_file(file_path: str) -> list[Violation]:
    """Scan a single STAGED file's index blob; return only its violations.

    Thin wrapper over :func:`_scan_staged_one` for callers that only need the
    findings (the unreadable-blob fail-closed handling lives in ``main`` via
    :func:`scan_staged`).
    """
    violations, _unreadable = _scan_staged_one(file_path)
    return violations


def scan_staged_files(file_paths: list[str]) -> list[Violation]:
    """Scan multiple STAGED files' index blobs; return only their violations."""
    violations, _unreadable = scan_staged(file_paths)
    return violations


def scan_files(file_paths: list[str]) -> list[Violation]:
    """Scan multiple files for PII and credential patterns.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        Aggregated list of all violations found across all files.
    """
    all_violations: list[Violation] = []
    for file_path in file_paths:
        all_violations.extend(scan_file(file_path.strip()))
    return all_violations


def get_staged_files() -> list[str]:
    """Get the list of staged files from git.

    Returns:
        List of staged file paths (Added, Copied, Modified only).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Could not get staged files: %s", e)
        return []


def report_violations(violations: list[Violation]) -> None:
    """Print violation report to stderr.

    Args:
        violations: List of violations to report.
    """
    for v in violations:
        print(
            f"[PII BLOCKED] {v.file_path}:{v.line_number}: "
            f"matched '{v.pattern_name}' pattern",
            file=sys.stderr,
        )

    files_affected = len(set(v.file_path for v in violations))
    print(
        f"\n{len(violations)} violation(s) found in {files_affected} file(s).",
        file=sys.stderr,
    )


def _count_scannable(file_paths: list[str], check_exists: bool = True) -> int:
    """Count files that will actually be scanned (not skipped).

    A file is scannable if it is not in a skip path and has a scannable
    extension (and, by default, exists on disk). ``check_exists=False`` mirrors
    the ``--staged`` gate so a staged-add-then-``rm`` file still counts.
    """
    count = 0
    for file_path in file_paths:
        fp = file_path.strip()
        if _scannability_skip_reason(fp, check_exists=check_exists) is None:
            count += 1
    return count


def main() -> int:
    """Main entry point for the PII scanner CLI.

    Returns:
        Exit code: 0 for clean, 1 for violations found.
    """
    parser = argparse.ArgumentParser(
        description="Scan files for PII and credential patterns."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan git staged files (Added, Copied, Modified)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read file paths from stdin, one per line",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific files to scan",
    )

    args = parser.parse_args()

    # Determine which files to scan
    if args.staged:
        file_paths = get_staged_files()
    elif args.stdin:
        file_paths = [
            line.strip()
            for line in sys.stdin.readlines()
            if line.strip()
        ]
    elif args.files:
        file_paths = args.files
    else:
        parser.print_help(sys.stderr)
        return 0

    if not file_paths:
        return 0

    # In --staged mode, scan the STAGED index blobs (git show :<path>), not the
    # working-tree bytes -- a token staged then cleaned from the working tree
    # must still be caught (F-H3 staged-blob gap).
    unreadable: list[str] = []
    if args.staged:
        violations, unreadable = scan_staged(file_paths)
    else:
        violations = scan_files(file_paths)

    exit_code = 0

    if violations:
        report_violations(violations)
        exit_code = 1

    if unreadable:
        # Fail-CLOSED: a credential scanner must NEVER certify a staged blob it
        # could not read as clean. Operator-visible on STDOUT (not just the
        # stderr warning) plus a non-zero exit, so a pre-commit run blocks rather
        # than passing green on unscanned content. Any real findings above are
        # still reported -- the unreadable handling does not mask them.
        for path in unreadable:
            print(
                f"[pii-scan] REFUSING to certify clean: unreadable staged blob {path}"
            )
        exit_code = 1

    if exit_code:
        return exit_code

    # Print success confirmation if any files were actually scanned. In --staged
    # mode the existence gate is omitted (a staged-add-then-rm file still counts).
    scanned = _count_scannable(file_paths, check_exists=not args.staged)
    if scanned > 0:
        print(
            f"[pii-scan] Scanned {scanned} file(s), 0 violations.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
