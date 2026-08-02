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

## Suppression mechanisms and choice hierarchy

Two suppressors let an author silence a match. **Both sit OUTSIDE the `COMPILED_PATTERNS` loop in `_scan_text` (`src/safety/pii_scanner.py`), so — despite the "benign credential-SHAPED lines" framing above — each suppresses ALL patterns, credential patterns included** (`bearer_token`, `api_key_assignment`, `email`, `us_phone`), not just the shape heuristics:

- **Per-line `# pii-ok`** (`PII_OK_MARKER`, `pii_scanner.py:151-153`): the `if PII_OK_MARKER in line: continue` runs *before* the per-line pattern loop, so it drops the ENTIRE line from scanning. Case-sensitive substring; `<!-- pii-ok -->` in HTML/XML.
- **File-level `synthetic-test-data`** (`SYNTHETIC_MARKER`, `pii_scanner.py:145-148` via `has_synthetic_marker`, which reads the first 5 lines): a hit returns `[]` for the WHOLE file *before* the per-line loop begins, so every line and every pattern in the file is unscanned.

This whole-pattern scope is **by design and load-bearing**: a synthetic end-to-end auth fixture legitimately contains `Authorization: Bearer test-token-…`, which matches `bearer_token`; the file marker is what lets that fixture exist without a false block. But the corollary is sharp — **a real credential value behind either marker is silently unscanned, and that is a MUST FIX, not a sanctioned suppression.** The markers suppress *matches*; they do not certify *safety*.

**Choice hierarchy — which instrument to reach for (most-preferred first):**

1. **Change the data** so no pattern matches (a fake value that is not credential-shaped, an RFC 2606 email, a placeholder). Always preferred: it leaves NO standing suppression, so nothing can later hide a real value behind it. For a credential-parser fixture in particular, changing the fake value is the correct fix — do not reach for a marker.
2. **Line-scoped `# pii-ok`** on the single offending line, only when the line carries no literal credential VALUE (a var-to-var, dict-key, or fn-call assignment that trips the broadened key-name alternation but holds no secret).
3. **File-level `synthetic-test-data`** ONLY for an end-to-end synthetic fixture, and **NEVER on a file that handles, parses, or could receive real credentials** (a credential-parser test is the worst possible place for it — it is the file most likely to receive a real token when a dev pastes a curl to reproduce).

**Why not a blanket `tests/**` shape-exemption?** Rejected on two independent grounds. (1) *Evidence*: the shape heuristics fire zero times across `tests/**`, so the exemption buys nothing — and `email` / `bearer_token` / `api_key_assignment` MUST keep running there (`code-reviewer.md` §4g Credential Hygiene names "test fixtures using real credentials" a MUST FIX), so any carve-out would have to be per-pattern, strictly worse than a marker. (2) *Visibility to review*: a marker is a **literal token in the diff** the reviewer sees and scrutinizes (§4g) — an explicit, reviewable authorial act; a path exemption is **invisible in the diff** and silently leaves every future fixture under `tests/` unscanned for credentials forever, with no recorded author intent.

**The marker-visibility argument is why a marker beats a path exemption — it is NOT a structural closure.** It does not close the staged-blob hole where a `GC_REFRESH_TOKEN=<real> # pii-ok` line is staged, scanned clean, and never reviewed (an ad-hoc operator commit, an unread file, or a marker added in one epic with a real token added to that file epics later). Treating review visibility as a closure would be the same category error as accepting Cloudflare as CSRF mitigation. That residual is a real, tracked hole — **IDEA-112** (a measurement-first suppressor-narrowing idea), out of scope here.

## Doc-PII byte-gate (`scripts/check_doc_pii.sh`)

`scripts/check_doc_pii.sh <docs-dir>` is a committed, PII-FREE operational harness (E-254-07) that greps a docs tree against a denylist of literal real identifiers (names, UUIDs, public_ids) — the identifier class the pattern scanner above cannot detect — and fails (exit `1`, `file:line`) if any are present. It is a config/config.example split: the REAL denylist lives ONLY in the uncommitted, gitignored `secrets/pii-denylist.txt` (supplied via `PII_DENYLIST_FILE`); the committed halves are the harness + the fake-sentinel `scripts/pii-denylist.example.txt` (`ZZ__EXAMPLE_*` / prefix `zzzzzzzz`). Denylist line format `<type> <pattern>` with `type ∈ {plain, regex, prefix}` (`prefix` catches full UUIDs + bare prose prefixes while allowing the approved `<p>-REDACTED` placeholder). Exit codes: `0`=REAL + 0 matches (PASS), `1`=identifier present (FAIL), `2`=self-test/malformed (INVALID), `3`=real denylist absent → EXAMPLE MODE (INCONCLUSIVE — MUST NOT be recorded as a pass). The machinery-based self-test is data-independent, so a gutted harness exits `2`, never `0`. Run: `PII_DENYLIST_FILE=secrets/pii-denylist.txt scripts/check_doc_pii.sh docs/api`.

## Coverage footgun — planning/idea/epic artifacts are UNGATED (IDEA-102)

The two enforcement mechanisms leave a gap: the pre-commit `pii_scanner` has `epics/` and the four legacy `.project/` subdirs (`archive/`, `ideas/`, `research/`, `templates/`) in `SKIP_PATHS` and — the load-bearing half — cannot regex-detect NAMES at all (only credentials/email/phone), and the doc-PII byte-gate is scoped to `docs/api/` only. (On 2026-08-02 the blanket `.project/` entry was narrowed to those four subdirs so `.project/specs/` is scanned. **The TN-2 noise premise was re-measured and HOLDS** — lifting the skip surfaced 43 matches across 15 files, all shape false-positives — which is why the legacy subdirs keep their exclusion. Scanning specs buys credential/email/phone coverage there and **nothing against names**, so the gap below is unchanged for the class that actually bit.) So real identifiers — especially MINOR names — in idea/epic/planning artifacts rest solely on author discipline. This is not hypothetical: a real minor's name once landed in an idea file (the IDEA-096 capture, caught by Codex, remediated in E-254 Phase-4b). **When authoring `.project/**` or `epics/**`, never paste real names or identifiers — use the placeholder taxonomy in `.claude/rules/api-docs.md`.** The systematic fix (extending gate coverage to planning artifacts) is tracked in IDEA-102.
