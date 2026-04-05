"""Tests for the OpenRouter HTTP client in src/llm/openrouter.py."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from src.llm.openrouter import LLMError, is_llm_available, query_openrouter


# ── is_llm_available ────────────────────────────────────────────────────


class TestIsLlmAvailable:

    def test_available_when_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
        assert is_llm_available() is True

    def test_unavailable_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert is_llm_available() is False

    def test_unavailable_when_key_empty(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        assert is_llm_available() is False


# ── query_openrouter ────────────────────────────────────────────────────


_MESSAGES = [{"role": "user", "content": "Hello"}]

_VALID_RESPONSE = {
    "choices": [{"message": {"content": "response text"}}],
}


class TestQueryOpenrouterHeaders:
    """Verify correct request headers and body shape."""

    def test_sends_auth_header(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        captured_request = {}

        def mock_post(self, url, **kwargs):
            captured_request["url"] = str(url)
            captured_request["headers"] = kwargs.get("headers", {})
            captured_request["json"] = kwargs.get("json", {})
            return httpx.Response(200, json=_VALID_RESPONSE)

        with patch.object(httpx.Client, "post", mock_post):
            query_openrouter(_MESSAGES)

        assert captured_request["headers"]["Authorization"].startswith("Bearer ")
        assert captured_request["headers"]["Content-Type"] == "application/json"

    def test_sends_correct_body(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        captured = {}

        def mock_post(self, url, **kwargs):
            captured["json"] = kwargs.get("json", {})
            return httpx.Response(200, json=_VALID_RESPONSE)

        with patch.object(httpx.Client, "post", mock_post):
            query_openrouter(_MESSAGES, model="test/model", max_tokens=256, temperature=0.5)

        body = captured["json"]
        assert body["model"] == "test/model"
        assert body["messages"] == _MESSAGES
        assert body["max_tokens"] == 256
        assert body["temperature"] == 0.5

    def test_default_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
        monkeypatch.setenv("OPENROUTER_MODEL", "custom/model")

        captured = {}

        def mock_post(self, url, **kwargs):
            captured["json"] = kwargs.get("json", {})
            return httpx.Response(200, json=_VALID_RESPONSE)

        with patch.object(httpx.Client, "post", mock_post):
            query_openrouter(_MESSAGES)

        assert captured["json"]["model"] == "custom/model"

    def test_default_model_fallback(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        captured = {}

        def mock_post(self, url, **kwargs):
            captured["json"] = kwargs.get("json", {})
            return httpx.Response(200, json=_VALID_RESPONSE)

        with patch.object(httpx.Client, "post", mock_post):
            query_openrouter(_MESSAGES)

        assert captured["json"]["model"] == "anthropic/claude-haiku-4-5-20251001"

    def test_posts_to_correct_url(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")

        captured = {}

        def mock_post(self, url, **kwargs):
            captured["url"] = str(url)
            return httpx.Response(200, json=_VALID_RESPONSE)

        with patch.object(httpx.Client, "post", mock_post):
            query_openrouter(_MESSAGES)

        assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"


class TestQueryOpenrouterErrors:
    """Verify error handling for various failure modes."""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(LLMError, match="OPENROUTER_API_KEY is not set"):
            query_openrouter(_MESSAGES)

    def test_401_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "bad-key")

        def mock_post(self, url, **kwargs):
            return httpx.Response(401, text="Unauthorized")

        with patch.object(httpx.Client, "post", mock_post):
            with pytest.raises(LLMError, match="authentication failed.*401"):
                query_openrouter(_MESSAGES)

    def test_429_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        def mock_post(self, url, **kwargs):
            return httpx.Response(429, text="Rate limited")

        with patch.object(httpx.Client, "post", mock_post):
            with pytest.raises(LLMError, match="rate limit.*429"):
                query_openrouter(_MESSAGES)

    def test_500_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        def mock_post(self, url, **kwargs):
            return httpx.Response(500, text="Internal server error")

        with patch.object(httpx.Client, "post", mock_post):
            with pytest.raises(LLMError, match="HTTP 500"):
                query_openrouter(_MESSAGES)

    def test_timeout_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        def mock_post(self, url, **kwargs):
            raise httpx.ReadTimeout("Connection timed out")

        with patch.object(httpx.Client, "post", mock_post):
            with pytest.raises(LLMError, match="timed out"):
                query_openrouter(_MESSAGES)

    def test_connection_error_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        def mock_post(self, url, **kwargs):
            raise httpx.ConnectError("Connection refused")

        with patch.object(httpx.Client, "post", mock_post):
            with pytest.raises(LLMError, match="request failed"):
                query_openrouter(_MESSAGES)

    def test_invalid_json_response_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        def mock_post(self, url, **kwargs):
            return httpx.Response(200, text="not json at all")

        with patch.object(httpx.Client, "post", mock_post):
            with pytest.raises(LLMError, match="invalid JSON"):
                query_openrouter(_MESSAGES)


class TestQueryOpenrouterSuccess:
    """Verify successful response handling."""

    def test_returns_parsed_json(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        def mock_post(self, url, **kwargs):
            return httpx.Response(200, json=_VALID_RESPONSE)

        with patch.object(httpx.Client, "post", mock_post):
            result = query_openrouter(_MESSAGES)

        assert result == _VALID_RESPONSE
