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

## Scanner capabilities (E-254-06 hardening)

- Credential patterns (`bearer_token`, `api_key_assignment`) compile with `re.IGNORECASE`, so the project's own UPPERCASE env-var format (`GC_ACCESS_TOKEN=…`, `GC_CLIENT_TOKEN=…`, `GC_REFRESH_TOKEN=…`, `GC_DEVICE_ID=…`) is caught. Email/phone stay case-neutral. The `api_key_assignment` key alternation is broadened to the project token-key names (client/refresh_token, device_id) — TARGETED, not a blanket `\w+`; the value side still requires `[=:]` + a 16+ non-space value, so prose like "rotate the api_key" does not false-match. `SYNTHETIC_MARKER` and the `pii-ok` marker stay case-sensitive by design (a typo'd `PII-OK` must not suppress a real finding).
- `--staged` mode scans the STAGED BLOB (`git show :<path>`), not the working-tree bytes, so a token staged then cleaned from the working tree is still caught. Both the working-tree (`scan_file`) and staged (`_scan_staged_one`) paths route through the shared `_scan_text` helper (identical marker/`pii-ok`/email-allowlist/pattern logic). The staged path deliberately OMITS the `Path.exists()` scannability gate — a staged-add-then-`rm` leaves the blob in the index while the working-tree copy is gone; reusing the exists() gate there would skip that genuine leak vector.
- An UNREADABLE staged blob FAILS CLOSED: non-zero exit + an operator-visible stdout refusal (`[pii-scan] REFUSING to certify clean: unreadable staged blob …`). The scanner NEVER certifies clean on content it could not read. Do NOT regress this to warn-and-skip — that was the Phase-4b fail-open.
- The `# pii-ok` inline marker (case-sensitive substring; `<!-- pii-ok -->` in HTML/XML) suppresses benign credential-SHAPED lines (var-to-var, dict-key, fn-call assignments) in the real credential modules (`src/gamechanger/token_manager.py`, `credential_parser.py`, `src/cli/creds.py`) — lines that trip the broadened key-name alternation but carry no literal credential VALUE. Use it only for genuine non-value lines, never to silence a real secret.

**Reviewer gotcha**: an editable install can shadow worktree patterns — when running the scanner against WORKTREE code, force the worktree module (e.g. run from the worktree root with `PYTHONPATH` set to it) so you exercise the worktree's `pii_patterns.py`, not an installed copy.

## Doc-PII byte-gate (`scripts/check_doc_pii.sh`)

`scripts/check_doc_pii.sh <docs-dir>` is a committed, PII-FREE operational harness (E-254-07) that greps a docs tree against a denylist of literal real identifiers (names, UUIDs, public_ids) — the identifier class the pattern scanner above cannot detect — and fails (exit `1`, `file:line`) if any are present. It is a config/config.example split: the REAL denylist lives ONLY in the uncommitted, gitignored `secrets/pii-denylist.txt` (supplied via `PII_DENYLIST_FILE`); the committed halves are the harness + the fake-sentinel `scripts/pii-denylist.example.txt` (`ZZ__EXAMPLE_*` / prefix `zzzzzzzz`). Denylist line format `<type> <pattern>` with `type ∈ {plain, regex, prefix}` (`prefix` catches full UUIDs + bare prose prefixes while allowing the approved `<p>-REDACTED` placeholder). Exit codes: `0`=REAL + 0 matches (PASS), `1`=identifier present (FAIL), `2`=self-test/malformed (INVALID), `3`=real denylist absent → EXAMPLE MODE (INCONCLUSIVE — MUST NOT be recorded as a pass). The machinery-based self-test is data-independent, so a gutted harness exits `2`, never `0`. Run: `PII_DENYLIST_FILE=secrets/pii-denylist.txt scripts/check_doc_pii.sh docs/api`.

## Coverage footgun — planning/idea/epic artifacts are UNGATED (IDEA-102)

The two enforcement mechanisms leave a gap: the pre-commit `pii_scanner` has `epics/` + `.project/` in `SKIP_PATHS` and cannot regex-detect NAMES (only credentials/email/phone), and the doc-PII byte-gate is scoped to `docs/api/` only. So real identifiers — especially MINOR names — in idea/epic/planning artifacts rest solely on author discipline. This is not hypothetical: a real minor's name once landed in an idea file (the IDEA-096 capture, caught by Codex, remediated in E-254 Phase-4b). **When authoring `.project/**` or `epics/**`, never paste real names or identifiers — use the placeholder taxonomy in `.claude/rules/api-docs.md`.** The systematic fix (extending gate coverage to planning artifacts) is tracked in IDEA-102.
