#!/usr/bin/env python3
"""Validate YAML frontmatter schema compliance and index consistency for docs/api/endpoints/.

Usage:
    python scripts/validate_api_docs.py

Exit code 0 on success (no ERRORs), exit code 1 if any ERROR-level findings exist.
WARNings do not affect exit code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENDPOINTS_DIR = Path("docs/api/endpoints")
README_PATH = Path("docs/api/README.md")
FORMAT_SPEC_PATH = Path(".project/research/E-062-format-spec.md")

# The web-routes file is a special reference file -- not a standard endpoint file.
WEB_ROUTES_FILE = "web-routes-not-api.md"

REQUIRED_FIELDS = [
    "method",
    "path",
    "status",
    "auth",
    "profiles",
    "response_shape",
    "discovered",
    "tags",
]

ALLOWED_STATUS = {"CONFIRMED", "OBSERVED", "PARTIAL", "UNTESTED", "DEPRECATED"}
ALLOWED_AUTH = {"required", "none"}
ALLOWED_PROFILE_STATUS = {"confirmed", "unverified", "not_applicable", "observed", "partial"}
ALLOWED_RESPONSE_SHAPE = {"array", "object", "string"}

TAG_VOCABULARY = {
    "schedule",
    "games",
    "team",
    "player",
    "stats",
    "season",
    "organization",
    "opponent",
    "video",
    "lineup",
    "public",
    "auth",
    "subscription",
    "user",
    "sync",
    "coaching",
    "spray-chart",
    "events",
    "bridge",
    "bulk",
    "calendar",
    "me",
    "media",
    "permissions",
    "search",
    "web-routes",
    "write",
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

Severity = str  # "ERROR" | "WARN"


class Finding:
    """A single validation finding."""

    def __init__(self, filename: str, severity: Severity, message: str) -> None:
        self.filename = filename
        self.severity = severity
        self.message = message

    def __str__(self) -> str:
        return f"  [{self.severity}] {self.message}"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict[str, Any] | None:
    """Parse YAML frontmatter from a markdown file.

    Returns the parsed dict, or None if no frontmatter block is found.
    """
    if not content.startswith("---"):
        return None
    # Find the closing ---
    end = content.find("\n---", 3)
    if end == -1:
        return None
    yaml_block = content[3:end].strip()
    try:
        return yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return None


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------

def validate_file(filepath: Path) -> list[Finding]:
    """Validate a single endpoint file.

    Returns a list of Finding objects (may be empty if valid).
    """
    filename = filepath.name
    findings: list[Finding] = []

    content = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)

    if fm is None:
        findings.append(Finding(filename, "ERROR", "Could not parse YAML frontmatter"))
        return findings

    # Special case: web-routes-not-api.md -- existence check only, skip field validation
    if filename == WEB_ROUTES_FILE:
        return findings

    # AC-2: Required fields
    for field in REQUIRED_FIELDS:
        if field not in fm:
            findings.append(Finding(filename, "ERROR", f"Missing required field: {field}"))

    # AC-3: Allowed values for enumerated fields
    status = fm.get("status")
    if status is not None and status not in ALLOWED_STATUS:
        findings.append(Finding(
            filename, "ERROR",
            f"Invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUS)}"
        ))

    auth = fm.get("auth")
    if auth is not None and auth not in ALLOWED_AUTH:
        findings.append(Finding(
            filename, "ERROR",
            f"Invalid auth '{auth}'. Allowed: {sorted(ALLOWED_AUTH)}"
        ))

    response_shape = fm.get("response_shape")
    if response_shape is not None and response_shape not in ALLOWED_RESPONSE_SHAPE:
        findings.append(Finding(
            filename, "ERROR",
            f"Invalid response_shape '{response_shape}'. Allowed: {sorted(ALLOWED_RESPONSE_SHAPE)}"
        ))

    profiles = fm.get("profiles")
    if profiles is not None and isinstance(profiles, dict):
        for profile_name, profile_data in profiles.items():
            if not isinstance(profile_data, dict):
                continue
            pstatus = profile_data.get("status")
            if pstatus is not None and pstatus not in ALLOWED_PROFILE_STATUS:
                findings.append(Finding(
                    filename, "ERROR",
                    f"Invalid profiles.{profile_name}.status '{pstatus}'. "
                    f"Allowed: {sorted(ALLOWED_PROFILE_STATUS)}"
                ))

    # AC-4: Tag vocabulary compliance
    tags = fm.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            findings.append(Finding(filename, "ERROR", "Field 'tags' must be a list"))
        else:
            for tag in tags:
                if tag not in TAG_VOCABULARY:
                    findings.append(Finding(
                        filename, "ERROR",
                        f"Unknown tag '{tag}'. Not in controlled vocabulary."
                    ))

            # AC-5: Tag count (WARN only)
            tag_count = len(tags)
            if tag_count < 2 or tag_count > 5:
                findings.append(Finding(
                    filename, "WARN",
                    f"Tag count {tag_count} is outside recommended range of 2-5"
                ))

    return findings


# ---------------------------------------------------------------------------
# Directory-wide validation
# ---------------------------------------------------------------------------

def validate_directory(endpoints_dir: Path = ENDPOINTS_DIR) -> dict[str, list[Finding]]:
    """Validate all endpoint files in the directory.

    Returns a dict mapping filename -> list of findings.
    """
    results: dict[str, list[Finding]] = {}
    for filepath in sorted(endpoints_dir.glob("*.md")):
        findings = validate_file(filepath)
        results[filepath.name] = findings
    return results


# ---------------------------------------------------------------------------
# Index consistency validation
# ---------------------------------------------------------------------------

def extract_index_links(readme_path: Path = README_PATH) -> set[str]:
    """Extract all endpoint file links from the README index.

    Returns a set of filenames (basenames) referenced in the index.
    """
    content = readme_path.read_text(encoding="utf-8")
    # Match markdown links pointing into endpoints/ directory
    # Pattern: [anything](endpoints/filename.md)
    pattern = re.compile(r"\(endpoints/([^)]+\.md)\)")
    return {m.group(1) for m in pattern.finditer(content)}


def validate_index_consistency(
    endpoints_dir: Path = ENDPOINTS_DIR,
    readme_path: Path = README_PATH,
) -> list[Finding]:
    """Check for orphan files and missing files between disk and index.

    AC-6: Orphan files (on disk but not in index) -> ERROR
    AC-7: Missing files (in index but not on disk) -> ERROR
    """
    findings: list[Finding] = []

    disk_files = {f.name for f in endpoints_dir.glob("*.md")}
    index_files = extract_index_links(readme_path)

    orphans = disk_files - index_files
    for filename in sorted(orphans):
        findings.append(Finding(filename, "ERROR", f"File exists on disk but is not listed in README index"))

    missing = index_files - disk_files
    for filename in sorted(missing):
        findings.append(Finding(filename, "ERROR", f"File listed in README index but does not exist on disk"))

    return findings


# ---------------------------------------------------------------------------
# Format spec inventory parsing
# ---------------------------------------------------------------------------

def _normalize_status(raw: str) -> str:
    """Normalize an inventory status value by stripping parenthetical annotations.

    Examples:
        'CONFIRMED (empty)' -> 'CONFIRMED'
        'OBSERVED (HTTP 404)' -> 'OBSERVED'
        'CONFIRMED (PARTIAL->CONFIRMED)' -> 'CONFIRMED'
        'CONFIRMED (CSV)' -> 'CONFIRMED'
        'PARTIAL' -> 'PARTIAL'
    """
    return raw.split("(")[0].strip()


def parse_inventory(spec_path: Path = FORMAT_SPEC_PATH) -> list[dict[str, str]]:
    """Parse the endpoint inventory tables from Section 7 of the format spec.

    Returns a list of dicts with keys: method, path, status, filename.
    The web-routes reference file entry is included with method='' and path=''.
    """
    content = spec_path.read_text(encoding="utf-8")

    entries: list[dict[str, str]] = []

    # Match table rows that have a numeric # column (inventory rows)
    # Format: | 1 | GET | `/path` | STATUS | `filename.md` | ... |
    # Also handles Tier 3 tables which omit the Schema column
    row_pattern = re.compile(
        r"^\|\s*\d+\s*\|"          # | # |
        r"\s*(\w+)\s*\|"           # | Method |
        r"\s*`([^`]+)`\s*\|"       # | `/path` |
        r"\s*([^|]+?)\s*\|"        # | Status (may have annotations) |
        r"\s*`([^`]+)`\s*\|",      # | `filename.md` |
        re.MULTILINE,
    )
    for m in row_pattern.finditer(content):
        method = m.group(1).strip()
        path = m.group(2).strip()
        raw_status = m.group(3).strip()
        filename = m.group(4).strip()
        entries.append({
            "method": method,
            "path": path,
            "status": _normalize_status(raw_status),
            "filename": filename,
        })

    # Add the web-routes reference file (special entry, no standard row format)
    entries.append({
        "method": "",
        "path": "",
        "status": "NOT_API",
        "filename": WEB_ROUTES_FILE,
    })

    return entries


def validate_inventory(
    spec_path: Path = FORMAT_SPEC_PATH,
    endpoints_dir: Path = ENDPOINTS_DIR,
) -> list[Finding]:
    """AC-8: Verify each inventory entry exists on disk with matching frontmatter.

    For each entry in the format spec inventory:
    - Verify the expected filename exists on disk -> ERROR if missing
    - Verify the file's frontmatter method, path, status match inventory -> ERROR on mismatch
    The web-routes-not-api.md file is checked for existence only (no frontmatter match).
    """
    findings: list[Finding] = []
    entries = parse_inventory(spec_path)

    for entry in entries:
        filename = entry["filename"]
        filepath = endpoints_dir / filename

        if not filepath.exists():
            findings.append(Finding(
                filename, "ERROR",
                f"Inventory expects file to exist on disk but it is missing"
            ))
            continue

        # web-routes is existence-check only
        if filename == WEB_ROUTES_FILE:
            continue

        content = filepath.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        if fm is None:
            findings.append(Finding(
                filename, "ERROR",
                "Inventory file exists but frontmatter could not be parsed"
            ))
            continue

        # Check method
        file_method = str(fm.get("method", "")).upper()
        inv_method = entry["method"].upper()
        if file_method != inv_method:
            findings.append(Finding(
                filename, "ERROR",
                f"Method mismatch: inventory expects '{inv_method}', file has '{file_method}'"
            ))

        # Check path
        file_path = str(fm.get("path", ""))
        inv_path = entry["path"]
        if file_path != inv_path:
            findings.append(Finding(
                filename, "ERROR",
                f"Path mismatch: inventory expects '{inv_path}', file has '{file_path}'"
            ))

        # Check status (normalize both to base keyword)
        file_status = _normalize_status(str(fm.get("status", "")))
        inv_status = entry["status"]
        if file_status != inv_status:
            findings.append(Finding(
                filename, "ERROR",
                f"Status mismatch: inventory expects '{inv_status}', file has '{file_status}'"
            ))

    return findings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Run all validations and print grouped output. Returns exit code."""
    # Validate all individual files
    file_results = validate_directory()

    # Validate index consistency (orphans + missing)
    index_findings = validate_index_consistency()

    # Validate against format spec inventory
    inventory_findings = validate_inventory()

    # Group index and inventory findings under a synthetic key
    all_results: dict[str, list[Finding]] = dict(file_results)
    if index_findings:
        all_results["[index-consistency]"] = index_findings
    if inventory_findings:
        # Merge inventory findings by filename into existing entries
        for f in inventory_findings:
            key = f.filename if f.filename else "[inventory]"
            if key not in all_results:
                all_results[key] = []
            all_results[key].append(f)

    # Count totals
    error_count = 0
    warn_count = 0
    valid_count = 0

    output_lines: list[str] = []

    for filename in sorted(all_results.keys()):
        findings = all_results[filename]
        if not findings:
            valid_count += 1
            continue

        file_errors = sum(1 for f in findings if f.severity == "ERROR")
        file_warns = sum(1 for f in findings if f.severity == "WARN")
        error_count += file_errors
        warn_count += file_warns

        if file_errors > 0 or file_warns > 0:
            output_lines.append(f"\n{filename}:")
            for finding in findings:
                output_lines.append(str(finding))

    # Print findings
    if output_lines:
        for line in output_lines:
            print(line)

    # Summary line
    total_files = len(file_results)
    valid_count = total_files - sum(
        1 for findings in file_results.values() if any(f.severity in ("ERROR", "WARN") for f in findings)
    )
    print(
        f"\nSummary: {error_count} error(s), {warn_count} warning(s), "
        f"{valid_count}/{total_files} files valid"
    )

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
