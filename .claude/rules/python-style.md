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
- **No `sys.path` manipulation in `src/` modules**: Never use `sys.path.insert()` or `sys.path.append()` in modules under `src/`. Path manipulation belongs only in standalone scripts (`scripts/`) that need to bootstrap `src.*` imports when run directly. `src/` modules are always importable via the editable install.
- **Repo-root resolution convention**: Use `Path(__file__).resolve().parents[N]` to derive repo-root-relative paths from `src/` modules. Count directory levels from the module to the repo root (e.g., `parents[2]` for `src/db/reset.py`, `parents[3]` for `src/gamechanger/crawlers/roster.py`). See existing usage throughout `src/` for reference.
