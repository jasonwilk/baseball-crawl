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


def has_synthetic_marker(lines: list[str]) -> bool:
    """Check if the first 5 lines of a file contain the synthetic data marker."""
    for line in lines[:5]:
        if SYNTHETIC_MARKER in line:
            return True
    return False


def scan_file(file_path: str) -> list[Violation]:
    """Scan a single file for PII and credential patterns.

    Args:
        file_path: Path to the file to scan (relative or absolute).

    Returns:
        List of Violation tuples for any matches found. Empty list if the file
        is clean, skipped, or cannot be read.
    """
    if should_skip_path(file_path):
        logger.debug("Skipping (skip path): %s", file_path)
        return []

    if not is_scannable(file_path):
        logger.debug("Skipping (non-scannable extension): %s", file_path)
        return []

    path = Path(file_path)
    if not path.exists():
        logger.debug("Skipping (does not exist): %s", file_path)
        return []

    try:
        text = path.read_text(errors="replace")
    except OSError as e:
        logger.warning("Could not read %s: %s", file_path, e)
        return []

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


def _count_scannable(file_paths: list[str]) -> int:
    """Count files that will actually be scanned (not skipped).

    A file is scannable if it is not in a skip path, has a scannable
    extension, and exists on disk.
    """
    count = 0
    for file_path in file_paths:
        fp = file_path.strip()
        if should_skip_path(fp):
            continue
        if not is_scannable(fp):
            continue
        if not Path(fp).exists():
            continue
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

    violations = scan_files(file_paths)

    if violations:
        report_violations(violations)
        return 1

    # Print success confirmation if any files were actually scanned
    scanned = _count_scannable(file_paths)
    if scanned > 0:
        print(
            f"[pii-scan] Scanned {scanned} file(s), 0 violations.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
