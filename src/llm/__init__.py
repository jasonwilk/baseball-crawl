"""LLM integration package.

Provides a reusable OpenRouter HTTP client and helpers for checking
LLM availability.
"""

from __future__ import annotations

from src.llm.openrouter import LLMError, is_llm_available, query_openrouter

__all__ = ["LLMError", "is_llm_available", "query_openrouter"]
