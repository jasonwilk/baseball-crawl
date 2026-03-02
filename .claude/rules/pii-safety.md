---
paths:
  - "src/safety/**"
  - ".githooks/**"
  - ".claude/hooks/pii-check.sh"
---

# PII Safety System Rules

- The PII scanner at src/safety/pii_scanner.py is a security control. Changes require careful review.
- Never weaken regex patterns without explicit approval.
- Never add blanket exclusions to the scanner's skip list.
- Test changes against the test suite in tests/test_pii_scanner.py before committing.
- The scanner must remain fast (under 1 second for 20 files). Do not add heavy dependencies.
