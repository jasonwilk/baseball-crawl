"""Tests for the pure JSON-extraction helper in ``src/llm/json_extract.py``.

Covers the five must-parse real-world LLM response shapes (TN-1), the
string-aware brace-in-narrative case (F-F), the smart-quote case, and the
clean-fail cases (prose-only, empty, ``None``, truncated, mid-object).  No
HTTP -- the helper is a pure function.
"""

from __future__ import annotations

import pytest

from src.llm.json_extract import extract_json_object
from src.llm.openrouter import LLMError

_EXPECTED = {"narrative": "LSB rolls", "bullpen_sequence": ["A", "B"]}

_BARE = '{"narrative": "LSB rolls", "bullpen_sequence": ["A", "B"]}'

# Must-parse shapes: (label, raw content, expected dict).
_MUST_PARSE = [
    pytest.param("bare", _BARE, _EXPECTED, id="bare"),
    pytest.param(
        "json_fenced",
        f"```json\n{_BARE}\n```",
        _EXPECTED,
        id="json_fenced",
    ),
    pytest.param(
        "fence_no_tag",
        f"```\n{_BARE}\n```",
        _EXPECTED,
        id="fence_without_tag",
    ),
    pytest.param(
        "leading_prose",
        f"Here is the analysis:\n{_BARE}",
        _EXPECTED,
        id="leading_prose",
    ),
    pytest.param(
        "trailing_prose",
        f"{_BARE}\nThat is my assessment.",
        _EXPECTED,
        id="trailing_prose",
    ),
    pytest.param(
        "brace_in_narrative",
        '{"narrative": "rally scored {3} in the 5th", '
        '"bullpen_sequence": ["A"]}',
        {"narrative": "rally scored {3} in the 5th", "bullpen_sequence": ["A"]},
        id="brace_in_narrative",
    ),
    pytest.param(
        "leading_prose_with_braces",
        "Use {narrative,bullpen_sequence}:\n" + _BARE,
        _EXPECTED,
        id="leading_prose_with_braces",
    ),
]


@pytest.mark.parametrize("label, content, expected", _MUST_PARSE)
def test_extract_json_object_recovers_must_parse_shapes(label, content, expected):
    assert extract_json_object(content) == expected


def test_extract_json_object_fenced_with_prose_around_fence():
    """Fence embedded in prose still extracts (combined real-world shape)."""
    content = f"Sure! Here you go:\n```json\n{_BARE}\n```\nLet me know."
    assert extract_json_object(content) == _EXPECTED


# Clean-fail cases: each must raise LLMError, never an unhandled error.
_CLEAN_FAIL = [
    pytest.param("This is just prose with no JSON at all.", id="prose_only"),
    pytest.param("", id="empty_string"),
    pytest.param("   \n\t  ", id="whitespace_only"),
    pytest.param(None, id="none"),
    pytest.param('{"narrative": "incomplete', id="truncated"),
    pytest.param('{"a": {"b": 1}', id="mid_object_unbalanced"),
    pytest.param("[1, 2, 3]", id="json_array_not_object"),
]


@pytest.mark.parametrize("content", _CLEAN_FAIL)
def test_extract_json_object_raises_llmerror_on_unrecoverable(content):
    with pytest.raises(LLMError):
        extract_json_object(content)


def test_extract_json_object_none_does_not_raise_typeerror():
    """``None`` is caught and re-raised as ``LLMError`` (AC-3)."""
    with pytest.raises(LLMError):
        extract_json_object(None)  # type: ignore[arg-type]


def test_extract_json_object_smart_quotes_clean_fail():
    """Smart-quote-delimited JSON has a defined outcome: clean-fail, no crash."""
    smart = "{“narrative”: “LSB rolls”}"
    with pytest.raises(LLMError):
        extract_json_object(smart)


def test_extract_json_object_does_not_validate_domain_fields():
    """Extraction returns any JSON object; domain validation is out of scope."""
    content = '{"unexpected": "shape", "no_narrative": true}'
    assert extract_json_object(content) == {
        "unexpected": "shape",
        "no_narrative": True,
    }
