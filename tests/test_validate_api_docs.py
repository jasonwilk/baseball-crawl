"""Tests for scripts/validate_api_docs.py validation logic.

Uses synthetic inline YAML content to test each validation rule independently.
No real endpoint files are read by these tests -- they test the functions directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import the functions under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_api_docs import (
    Finding,
    _normalize_status,
    parse_frontmatter,
    parse_inventory,
    validate_file,
    validate_inventory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_endpoint_file(tmp_path: Path, filename: str, frontmatter: str, body: str = "") -> Path:
    """Write a synthetic endpoint file and return its path."""
    content = f"---\n{frontmatter.strip()}\n---\n\n{body}"
    filepath = tmp_path / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


MINIMAL_VALID_FM = """\
method: GET
path: /test/endpoint
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Tested.
  mobile:
    status: unverified
    notes: Not tested.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-01-01"
last_confirmed: "2026-01-01"
tags: [team, player]
caveats: []
related_schemas: []
see_also: []
"""


# ---------------------------------------------------------------------------
# parse_frontmatter tests
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_parses_valid_frontmatter(self):
        content = "---\nmethod: GET\npath: /foo\n---\n\n# Body"
        result = parse_frontmatter(content)
        assert result == {"method": "GET", "path": "/foo"}

    def test_returns_none_when_no_frontmatter(self):
        content = "# No frontmatter here\n"
        result = parse_frontmatter(content)
        assert result is None

    def test_returns_none_on_unclosed_frontmatter(self):
        content = "---\nmethod: GET\n"
        result = parse_frontmatter(content)
        assert result is None

    def test_handles_empty_frontmatter(self):
        content = "---\n---\n\n# Body"
        result = parse_frontmatter(content)
        assert result == {} or result is None  # yaml.safe_load of empty string returns None

    def test_returns_none_on_invalid_yaml(self):
        content = "---\nkey: value: broken\n---\n"
        result = parse_frontmatter(content)
        # Depending on pyyaml behavior, may return None or partial
        # Main contract: does not raise
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# _normalize_status tests
# ---------------------------------------------------------------------------

class TestNormalizeStatus:
    def test_plain_status_unchanged(self):
        assert _normalize_status("CONFIRMED") == "CONFIRMED"

    def test_strips_parenthetical_annotation(self):
        assert _normalize_status("CONFIRMED (empty)") == "CONFIRMED"

    def test_strips_csv_annotation(self):
        assert _normalize_status("CONFIRMED (CSV)") == "CONFIRMED"

    def test_strips_partial_annotation(self):
        assert _normalize_status("OBSERVED (HTTP 404)") == "OBSERVED"

    def test_strips_upgrade_annotation(self):
        assert _normalize_status("CONFIRMED (PARTIAL->CONFIRMED)") == "CONFIRMED"

    def test_partial_status(self):
        assert _normalize_status("PARTIAL") == "PARTIAL"


# ---------------------------------------------------------------------------
# validate_file -- required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_valid_file_has_no_errors(self, tmp_path):
        filepath = make_endpoint_file(tmp_path, "get-test.md", MINIMAL_VALID_FM)
        findings = validate_file(filepath)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert errors == []

    def test_missing_method_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("method: GET\n", "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("method" in m for m in error_msgs)

    def test_missing_path_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("path: /test/endpoint\n", "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("path" in m for m in error_msgs)

    def test_missing_status_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("status: CONFIRMED\n", "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("status" in m for m in error_msgs)

    def test_missing_auth_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("auth: required\n", "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("auth" in m for m in error_msgs)

    def test_missing_tags_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("tags: [team, player]\n", "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("tags" in m for m in error_msgs)

    def test_missing_discovered_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace('discovered: "2026-01-01"\n', "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("discovered" in m for m in error_msgs)

    def test_missing_response_shape_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("response_shape: object\n", "")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("response_shape" in m for m in error_msgs)


# ---------------------------------------------------------------------------
# validate_file -- allowed values
# ---------------------------------------------------------------------------

class TestAllowedValues:
    def test_invalid_status_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("status: CONFIRMED", "status: UNKNOWN_VALUE")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("Invalid status" in m for m in error_msgs)

    def test_all_valid_statuses_accepted(self, tmp_path):
        for s in ["CONFIRMED", "OBSERVED", "PARTIAL", "UNTESTED", "DEPRECATED"]:
            fm = MINIMAL_VALID_FM.replace("status: CONFIRMED", f"status: {s}")
            filepath = make_endpoint_file(tmp_path, f"get-{s.lower()}.md", fm)
            findings = validate_file(filepath)
            status_errors = [f for f in findings if f.severity == "ERROR" and "Invalid status" in f.message]
            assert status_errors == [], f"Status '{s}' should be valid but got errors: {status_errors}"

    def test_invalid_auth_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("auth: required", "auth: token")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("Invalid auth" in m for m in error_msgs)

    def test_auth_none_accepted(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("auth: required", "auth: none")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        auth_errors = [f for f in findings if f.severity == "ERROR" and "Invalid auth" in f.message]
        assert auth_errors == []

    def test_invalid_response_shape_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("response_shape: object", "response_shape: json")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("response_shape" in m for m in error_msgs)

    def test_response_shape_string_accepted(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("response_shape: object", "response_shape: string")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        shape_errors = [f for f in findings if f.severity == "ERROR" and "response_shape" in f.message]
        assert shape_errors == []

    def test_invalid_profile_status_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace(
            "    status: confirmed\n    notes: Tested.",
            "    status: unknown_profile_status\n    notes: Tested."
        )
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("profiles.web.status" in m for m in error_msgs)


# ---------------------------------------------------------------------------
# validate_file -- tag vocabulary
# ---------------------------------------------------------------------------

class TestTagVocabulary:
    def test_unknown_tag_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("tags: [team, player]", "tags: [team, completely_unknown_tag_xyz]")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        error_msgs = [f.message for f in findings if f.severity == "ERROR"]
        assert any("completely_unknown_tag_xyz" in m for m in error_msgs)

    def test_known_tags_accepted(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("tags: [team, player]", "tags: [team, player, stats, games]")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        tag_errors = [f for f in findings if f.severity == "ERROR" and "tag" in f.message.lower()]
        assert tag_errors == []

    def test_tag_count_too_low_produces_warn(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("tags: [team, player]", "tags: [team]")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        warns = [f for f in findings if f.severity == "WARN" and "Tag count" in f.message]
        assert len(warns) == 1

    def test_tag_count_too_high_produces_warn(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace(
            "tags: [team, player]",
            "tags: [team, player, stats, games, events, video]"
        )
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        warns = [f for f in findings if f.severity == "WARN" and "Tag count" in f.message]
        assert len(warns) == 1

    def test_tag_count_in_range_no_warn(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("tags: [team, player]", "tags: [team, player, stats]")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        warns = [f for f in findings if f.severity == "WARN" and "Tag count" in f.message]
        assert warns == []

    def test_tags_not_list_produces_error(self, tmp_path):
        fm = MINIMAL_VALID_FM.replace("tags: [team, player]", "tags: team")
        filepath = make_endpoint_file(tmp_path, "get-test.md", fm)
        findings = validate_file(filepath)
        errors = [f for f in findings if f.severity == "ERROR" and "tags" in f.message.lower()]
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# validate_file -- unparseable frontmatter
# ---------------------------------------------------------------------------

class TestFrontmatterParsing:
    def test_bad_yaml_produces_error(self, tmp_path):
        content = "---\nkey: value: broken: yaml\n---\n\n# Body"
        filepath = tmp_path / "bad.md"
        filepath.write_text(content)
        findings = validate_file(filepath)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) >= 1
        assert any("frontmatter" in f.message.lower() for f in errors)


# ---------------------------------------------------------------------------
# validate_file -- web-routes special case
# ---------------------------------------------------------------------------

class TestWebRoutesSpecialCase:
    def test_web_routes_file_skips_field_validation(self, tmp_path):
        """web-routes-not-api.md should return no findings regardless of content."""
        content = "---\nstatus: NOT_API\ndiscovered: '2026-01-01'\ntags: [web-routes]\n---\n"
        filepath = tmp_path / "web-routes-not-api.md"
        filepath.write_text(content)
        findings = validate_file(filepath)
        assert findings == []


# ---------------------------------------------------------------------------
# Integration: validate actual endpoint files pass
# ---------------------------------------------------------------------------

class TestActualEndpointFiles:
    """Integration tests that validate the real endpoint files in docs/api/endpoints/."""

    def test_all_endpoint_files_have_no_errors(self):
        """Run the validator against the actual endpoint directory and assert zero errors."""
        endpoints_dir = Path("docs/api/endpoints")
        if not endpoints_dir.exists():
            pytest.skip("docs/api/endpoints not found -- run from project root")

        from validate_api_docs import validate_directory
        results = validate_directory(endpoints_dir)
        all_errors = [
            f"{filename}: {finding.message}"
            for filename, findings in results.items()
            for finding in findings
            if finding.severity == "ERROR"
        ]
        assert all_errors == [], f"Validation errors found:\n" + "\n".join(all_errors)

    def test_index_consistency(self):
        """All endpoint files should be in the index and vice versa."""
        endpoints_dir = Path("docs/api/endpoints")
        readme_path = Path("docs/api/README.md")
        if not endpoints_dir.exists() or not readme_path.exists():
            pytest.skip("docs/api directory not found -- run from project root")

        from validate_api_docs import validate_index_consistency
        findings = validate_index_consistency(endpoints_dir, readme_path)
        errors = [f.message for f in findings if f.severity == "ERROR"]
        assert errors == [], f"Index consistency errors:\n" + "\n".join(errors)


# ---------------------------------------------------------------------------
# parse_inventory -- Section 7 table parsing
# ---------------------------------------------------------------------------

SAMPLE_SPEC_CONTENT = """\
## 7. Complete Endpoint Inventory

### Tier 1

| # | Method | Path | Status | Filename | Schema |
|---|--------|------|--------|----------|--------|
| 1 | GET | `/me/teams` | CONFIRMED | `get-me-teams.md` | inline |
| 2 | POST | `/auth` | PARTIAL | `post-auth.md` | inline |

### Tier 2

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 3 | GET | `/teams/{team_id}/schedule` | CONFIRMED (empty) | `get-teams-team_id-schedule.md` |
| 4 | GET | `/teams/{team_id}/players` | OBSERVED (HTTP 404) | `get-teams-team_id-players.md` |
"""

SPEC_WITH_ANNOTATION = """\
## 7. Complete Endpoint Inventory

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 1 | GET | `/me/user` | CONFIRMED (PARTIAL->CONFIRMED) | `get-me-user.md` |
| 2 | GET | `/teams/{team_id}` | CONFIRMED (CSV) | `get-teams-team_id.md` |
"""


class TestParseInventory:
    def test_parses_basic_rows(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SAMPLE_SPEC_CONTENT, encoding="utf-8")
        entries = parse_inventory(spec_file)
        # Filter out the auto-appended web-routes entry
        real_entries = [e for e in entries if e["filename"] != "web-routes-not-api.md"]
        assert len(real_entries) == 4

    def test_parses_method_and_path(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SAMPLE_SPEC_CONTENT, encoding="utf-8")
        entries = parse_inventory(spec_file)
        real_entries = [e for e in entries if e["filename"] != "web-routes-not-api.md"]
        first = real_entries[0]
        assert first["method"] == "GET"
        assert first["path"] == "/me/teams"
        assert first["status"] == "CONFIRMED"
        assert first["filename"] == "get-me-teams.md"

    def test_strips_parenthetical_annotations_from_status(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SAMPLE_SPEC_CONTENT, encoding="utf-8")
        entries = parse_inventory(spec_file)
        real_entries = [e for e in entries if e["filename"] != "web-routes-not-api.md"]
        # Entry 3: "CONFIRMED (empty)" -> "CONFIRMED"
        assert real_entries[2]["status"] == "CONFIRMED"
        # Entry 4: "OBSERVED (HTTP 404)" -> "OBSERVED"
        assert real_entries[3]["status"] == "OBSERVED"

    def test_strips_upgrade_annotation(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SPEC_WITH_ANNOTATION, encoding="utf-8")
        entries = parse_inventory(spec_file)
        real_entries = [e for e in entries if e["filename"] != "web-routes-not-api.md"]
        assert real_entries[0]["status"] == "CONFIRMED"
        assert real_entries[1]["status"] == "CONFIRMED"

    def test_always_appends_web_routes_entry(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SAMPLE_SPEC_CONTENT, encoding="utf-8")
        entries = parse_inventory(spec_file)
        web_routes = [e for e in entries if e["filename"] == "web-routes-not-api.md"]
        assert len(web_routes) == 1
        assert web_routes[0]["status"] == "NOT_API"

    def test_empty_spec_returns_only_web_routes_entry(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# No inventory tables here\n", encoding="utf-8")
        entries = parse_inventory(spec_file)
        assert len(entries) == 1
        assert entries[0]["filename"] == "web-routes-not-api.md"

    def test_handles_post_method(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SAMPLE_SPEC_CONTENT, encoding="utf-8")
        entries = parse_inventory(spec_file)
        real_entries = [e for e in entries if e["filename"] != "web-routes-not-api.md"]
        post_entry = real_entries[1]
        assert post_entry["method"] == "POST"
        assert post_entry["path"] == "/auth"
        assert post_entry["status"] == "PARTIAL"


# ---------------------------------------------------------------------------
# validate_inventory -- cross-checking spec inventory against disk files
# ---------------------------------------------------------------------------

MINIMAL_ENDPOINT_FM = """\
method: GET
path: /me/teams
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
  mobile:
    status: unverified
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-01-01"
last_confirmed: "2026-01-01"
tags: [team, user]
"""

SINGLE_ENTRY_SPEC = """\
## 7. Inventory

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 1 | GET | `/me/teams` | CONFIRMED | `get-me-teams.md` |
"""


class TestValidateInventory:
    def test_matching_file_produces_no_errors(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SINGLE_ENTRY_SPEC, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        (endpoints_dir / "get-me-teams.md").write_text(
            f"---\n{MINIMAL_ENDPOINT_FM.strip()}\n---\n\n# Body",
            encoding="utf-8",
        )
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert errors == []

    def test_missing_inventory_file_produces_error(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SINGLE_ENTRY_SPEC, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        # get-me-teams.md does NOT exist
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert any("missing" in f.message.lower() for f in errors)
        assert any(f.filename == "get-me-teams.md" for f in errors)

    def test_method_mismatch_produces_error(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SINGLE_ENTRY_SPEC, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        wrong_fm = MINIMAL_ENDPOINT_FM.replace("method: GET", "method: POST")
        (endpoints_dir / "get-me-teams.md").write_text(
            f"---\n{wrong_fm.strip()}\n---\n\n# Body", encoding="utf-8"
        )
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert any("Method mismatch" in f.message for f in errors)

    def test_path_mismatch_produces_error(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SINGLE_ENTRY_SPEC, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        wrong_fm = MINIMAL_ENDPOINT_FM.replace("path: /me/teams", "path: /me/wrong")
        (endpoints_dir / "get-me-teams.md").write_text(
            f"---\n{wrong_fm.strip()}\n---\n\n# Body", encoding="utf-8"
        )
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert any("Path mismatch" in f.message for f in errors)

    def test_status_mismatch_produces_error(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SINGLE_ENTRY_SPEC, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        wrong_fm = MINIMAL_ENDPOINT_FM.replace("status: CONFIRMED", "status: OBSERVED")
        (endpoints_dir / "get-me-teams.md").write_text(
            f"---\n{wrong_fm.strip()}\n---\n\n# Body", encoding="utf-8"
        )
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert any("Status mismatch" in f.message for f in errors)

    def test_status_with_annotation_normalized_for_comparison(self, tmp_path):
        """Inventory entry 'CONFIRMED (empty)' should match file status 'CONFIRMED'."""
        annotated_spec = """\
## 7. Inventory

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 1 | GET | `/me/teams` | CONFIRMED (empty) | `get-me-teams.md` |
"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(annotated_spec, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        (endpoints_dir / "get-me-teams.md").write_text(
            f"---\n{MINIMAL_ENDPOINT_FM.strip()}\n---\n\n# Body", encoding="utf-8"
        )
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert errors == []

    def test_unparseable_frontmatter_produces_error(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SINGLE_ENTRY_SPEC, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        (endpoints_dir / "get-me-teams.md").write_text(
            "---\nkey: value: broken: yaml\n---\n\n# Body", encoding="utf-8"
        )
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "---\nstatus: NOT_API\n---\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert any("frontmatter" in f.message.lower() for f in errors)

    def test_web_routes_checked_existence_only(self, tmp_path):
        """web-routes-not-api.md in spec passes without frontmatter checks."""
        spec_with_web_routes = """\
## 7. Inventory

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 1 | GET | `/me/teams` | CONFIRMED | `get-me-teams.md` |
"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(spec_with_web_routes, encoding="utf-8")
        endpoints_dir = tmp_path / "endpoints"
        endpoints_dir.mkdir()
        (endpoints_dir / "get-me-teams.md").write_text(
            f"---\n{MINIMAL_ENDPOINT_FM.strip()}\n---\n\n# Body", encoding="utf-8"
        )
        # web-routes file exists with minimal non-standard content
        (endpoints_dir / "web-routes-not-api.md").write_text(
            "# Not an API endpoint\n", encoding="utf-8"
        )
        findings = validate_inventory(spec_file, endpoints_dir)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert errors == []
