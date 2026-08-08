---
name: dead-symbol-deletion
description: Before deleting a lint-flagged unused binding/import, check for evidence outside the code that the symbol was an unfinished intent — two real cases, one procedure
metadata:
  type: feedback
---

An unused binding looks identical to an unfinished intent. Two E-256-08 cases, same lint codes
(F841/F401), opposite dispositions — and the code at the line could not tell them apart:

- **`src/api/routes/auth.py:640`** — fetched passkey credential IDs under the comment *"Fetch
  existing credentials to exclude from registration options,"* never passed them to
  `generate_registration_options()`. `grep -rn 'exclude_credentials' src/ tests/` → **zero
  repo-wide**; `inspect.signature(webauthn.generate_registration_options)` → **the parameter
  exists**. A real unimplemented gap. Escalated → IDEA-117 filed → then deleted.
- **`src/gamechanger/client.py:46`** — imported `AuthSigningError`, never caught it, two called
  functions raise it, `git log -S'except AuthSigningError' -- <file>` → **empty for the file's whole
  history**. Same markers. But `tests/test_client.py:1133` and `:1275` assert the exception **must
  propagate** ("not swallowed by `except: pass`"). A vestige. Deleted.

**Procedure.** For each lint-flagged dead symbol, look for evidence *outside* the code — tests, the
introducing commit, a library signature:
- **Contradiction** (a test asserts the opposite behavior) → vestige, delete.
- **Corroboration, no implementation** (comment/annotation/library capability supports the intent,
  nothing contradicts it) → unfinished intent. File the idea BEFORE deleting.
- **No outside evidence** → unknown, not safe. Escalate.

Cite the evidence in the report, not the judgment: a reviewer who never saw the code can check "this
test contradicts it"; nobody can check "I looked and it seemed fine."

**Two mechanics, both hit for real:**
- **Delete by literal multi-line block, never by symbol name.** `starter_prediction.py` had two
  unrelated `all_dates` — dead at `:1126`, **live at `:869`** in another function. `cli/creds.py:37`
  imports `AuthSigningError` and **catches it at `:374`**, while `client.py:46`'s copy was dead. A
  symbol-scoped edit breaks live code at both sites.
- **A dead pair needs both lines.** `all_dates` was consumed only by `latest_game_date`; delete the
  consumer alone and the linter sees the producer as *used*, flagging it on the next pass. Delete the
  whole block, stale comment included.
