---
paths:
  - "**/*.py"
---

# Python Style Rules

- Use type hints for all function parameters and return types
- Use `from __future__ import annotations` at the top of each module for modern type syntax
- Prefer `pathlib.Path` over `os.path` for all file operations
- Use f-strings for string formatting
- Use `logging` module, never `print()` for operational output
- Use dataclasses or Pydantic models for structured data, not plain dicts
- Use context managers (`with`) for file and network resources
- Follow PEP 8 naming: snake_case for functions/variables, PascalCase for classes
- Keep functions under 50 lines; extract helpers for complex logic
- Use explicit exception types, never bare `except:`
