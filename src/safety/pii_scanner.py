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
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from src.safety.pii_patterns import (
    COMPILED_PATTERNS,
    PLACEHOLDER_EMAILS,
    PII_OK_MARKER,
    RFC2606_DOMAINS,
    SCANNABLE_BASENAMES,
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
    """Check if a file has a scannable extension, dotfile name, or basename.

    Three cases, tried in this order:

    1. A DOTFILE (``.env``, ``.env.example``, ``.eslintrc.json``) -- matched on
       the whole name, then on its leading dotted component, then falling
       through to the ordinary suffix test.
    2. A real extension, tested against ``SCANNABLE_EXTENSIONS``.
    3. An EXTENSIONLESS name (``Dockerfile``, ``pre-commit``), tested against
       ``SCANNABLE_BASENAMES``.

    Cases 1 and 3 both used to be holes and both are widenings, never
    narrowings. See ``SCANNABLE_BASENAMES`` for the extensionless allowlist's
    known limitation and why a shebang test cannot replace it.

    ⚠ **Still NOT covered, recorded so the boundary reads as a decision rather
    than a claim of completeness**: non-dotfile templates whose final suffix is
    unlisted (``docker-compose.override.yml.example``), and file types absent
    from ``SCANNABLE_EXTENSIONS`` entirely (``migrations/*.sql``,
    ``requirements.in``, ``*.conf``). Widening the scan surface to those is a
    policy call, not a bug fix.
    """
    p = Path(file_path)
    name = p.name
    lowered = name.lower()
    # Dotfiles FIRST, because Path.suffix lies about them. The old order tested
    # the suffix first, so this branch was reachable only when the suffix was
    # EMPTY -- and `Path(".env.example").suffix` is ".example", not "". The
    # comment here used to say it handled ".env, .env.local, etc."; it handled
    # neither `.env.local` NOR the TRACKED `.env.example` / `proxy/.env.example`,
    # which are the likeliest files in the repo to receive a real token by
    # copy-paste from a working env file.
    if lowered.startswith("."):
        # The whole name may BE the extension (".env")...
        if lowered in SCANNABLE_EXTENSIONS:
            return True
        # ...or it may be a variant/template of one (".env.example",
        # ".env.local"), in which case the LEADING dotted component decides.
        if "." + lowered.lstrip(".").split(".")[0] in SCANNABLE_EXTENSIONS:
            return True
        # Deliberate fall-through, NOT an else: a dotfile with an ordinary
        # scannable suffix (".eslintrc.json") must stay scannable. Returning
        # here would NARROW a security control, which this fix must never do.
    suffix = p.suffix.lower()
    if suffix:
        return suffix in SCANNABLE_EXTENSIONS
    return lowered in SCANNABLE_BASENAMES


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
        logger.warning(
            "Could not read staged blob for %s: %s", _display_path(file_path), e
        )
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

    Paths are used EXACTLY as given -- never trimmed. A leading or trailing
    space is a legal filename character, and stripping one silently rewrites the
    path: where the trimmed form collides with another staged path (a clean
    ``x.md`` beside a credential-bearing ``" x.md"``), ``git show :<path>`` reads
    the WRONG blob and the scanner certifies clean over content it never saw --
    the precise failure ``get_staged_files``'s ``-z`` exists to prevent. The
    ``--stdin`` caller strips its own line delimiters before calling in.
    """
    all_violations: list[Violation] = []
    unreadable: list[str] = []
    for file_path in file_paths:
        violations, is_unreadable = _scan_staged_one(file_path)
        all_violations.extend(violations)
        if is_unreadable:
            unreadable.append(file_path)
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

    Paths are used EXACTLY as given -- see :func:`scan_staged` for why trimming
    is unsafe. The ``--stdin`` caller strips its own line delimiters.

    Returns:
        Aggregated list of all violations found across all files.
    """
    all_violations: list[Violation] = []
    for file_path in file_paths:
        all_violations.extend(scan_file(file_path))
    return all_violations


def get_staged_files() -> list[str]:
    """Get the list of staged files from git.

    Enumerates the SAME staged set as ``.githooks/pre-commit`` (see its lines
    83-95). Both halves of the flag set are load-bearing, and both are here
    because the enumerations drifted apart once already:

    - ``R`` is included because ``--diff-filter=ACM`` alone drops a staged
      rename, and git scores a move-AND-edit as ``R<score>``. When the rename is
      the only staged change the returned list is EMPTY, so a rename carrying a
      planted credential reached no gate at all. ``--name-only`` reports a
      rename's DESTINATION path, which is the path to scan. ``D`` stays excluded
      -- a deleted path has no blob to read.
    - ``-z`` is the only safe enumeration: without it git C-quotes any path
      containing a non-ASCII byte, a double-quote, or a backslash, and such a
      path names no readable file, so ``git show :<path>`` cannot resolve it and
      the content goes unscanned. ``core.quotePath=false`` covers only the
      non-ASCII case.

    This is the SECOND time an ``ACMR`` fix has had to be applied to a sibling
    enumeration -- the hook's own was 2026-07-28, recorded as a finding in
    ``.project/research/2026-08-08-migration-audit-3.md:41``. Keep the reason
    beside the flags; a bare flag with no rationale is what let them drift.

    The output is read as BYTES and decoded with :func:`os.fsdecode`, NOT with
    ``text=True``. A filename is a byte string on POSIX and need not be valid
    UTF-8; ``text=True`` would raise ``UnicodeDecodeError`` -- which is not in
    the caught tuple below -- so one undecodable path would abort the scan of the
    WHOLE staged set. ``os.fsdecode`` round-trips such bytes through surrogate
    escapes, and ``subprocess`` re-encodes them with ``os.fsencode``, so
    ``git show :<path>`` still resolves the blob and the content is actually
    scanned. (``text=True`` would also silently translate a ``\\r`` inside a
    path, breaking the byte-exactness promised below.)

    Returns:
        List of staged file paths (Added, Copied, Modified, Renamed -- not
        Deleted), exactly as git reports them (never C-quoted, never trimmed).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
            capture_output=True,
            check=True,
        )
        return [os.fsdecode(f) for f in result.stdout.split(b"\0") if f]
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Could not get staged files: %s", e)
        return []


def _display_path(file_path: str) -> str:
    """Render a path safely for stdout/stderr.

    A path decoded by :func:`os.fsdecode` can carry surrogate escapes for bytes
    that are not valid UTF-8, and printing one raises ``UnicodeEncodeError``.
    That would turn a REPORTED violation into a crash -- failing closed, but
    losing the operator-visible reason. Undecodable bytes render as ``\\x``
    escapes instead.
    """
    return os.fsencode(file_path).decode("utf-8", "backslashreplace")


def report_violations(violations: list[Violation]) -> None:
    """Print violation report to stderr.

    Args:
        violations: List of violations to report.
    """
    for v in violations:
        print(
            f"[PII BLOCKED] {_display_path(v.file_path)}:{v.line_number}: "
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
        # Not trimmed -- this count is reconciled against the staged-path count
        # at lifecycle step 6, so it must agree with what scan_staged actually
        # read, path for path.
        if _scannability_skip_reason(file_path, check_exists=check_exists) is None:
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
        help="Scan git staged files (Added, Copied, Modified, Renamed)",
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
                "[pii-scan] REFUSING to certify clean: unreadable staged blob "
                f"{_display_path(path)}"
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
