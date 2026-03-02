---
paths:
  - "tests/**"
  - "**/*test*.py"
---

# Testing Rules

- Use pytest as the test runner
- IMPORTANT: Never make real HTTP requests in tests -- use mocks or fixtures
- Use pytest fixtures for test data setup
- Test data parsing and transformation logic thoroughly
- Use parametrize for testing multiple input variations
- Name test files as `test_<module>.py`
- Name test functions as `test_<behavior_being_tested>`
- Prefer specific assertions (`assert result == expected`) over generic (`assert result`)
- Include edge cases: empty data, malformed input, missing fields
