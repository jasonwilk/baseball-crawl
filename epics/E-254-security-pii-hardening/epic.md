# E-254: Security & PII Hardening — DRAFT STUB (audit CE-4)

## Status
`DRAFT`
<!-- Capture stub from the 2026-07-03 platform audit (PLATFORM-AUDIT.md, repo root, UNCOMMITTED).
     Carries the audit's CE-4 scope, absorbed findings, size, owners, sequence. NOT refined: no stories/ACs.
     Refine to READY before dispatch. Do NOT dispatch a DRAFT. -->

## Overview
Make the designated safety controls actually enforce what the project believes they do, and close the auth/serving hardening gaps. The PII scanner — the sole enforcement behind "credentials MUST NEVER appear in commit history" — is case-sensitive and misses the project's own UPPERCASE credential format end-to-end; several auth and report-serving paths leak live credentials or fail open.

## Audit Provenance
- **CE #**: CE-4 · **Size**: M · **Owners**: software-engineer, api-scout · **Sequence**: position 6 — the scanner fix (F-H3 core) is a quick win that can be pulled forward; the rest is a coherent hardening pass.
- **§4 scope row (verbatim)**: "PII scanner case + staged-blob fixes (F-H3), magic-link log/GET-verify fixes, endpoint-doc PII scrub (15 files), APP_ENV fail-safe, rowcount gate, cache-control, timing, options rate-limit, admin sweep test."
- **Absorbs**: F-H3 (HIGH) + 4 medium + 7 low.

## Absorbed Findings (one-liners copied from the audit)
- **F-H3 (HIGH)** — PII scanner credential patterns are case-sensitive; the project's own UPPERCASE env-var credential format passes clean end-to-end (`pii_patterns.py:67`). Pasted `GC_ACCESS_TOKEN=eyJ…` commits with "[pii-scan] … 0 violations". Fix: compile with `re.IGNORECASE`; add project-specific token key names; regression tests with uppercase forms.
- **`pii_scanner --staged` scans working-tree content, not the staged blobs that commit; staged-but-deleted files silently skipped** (`pii_scanner.py:141`). Fix: read `git show :<path>`.
- **Magic-link URLs (live 15-min admin credentials) written to logs when Mailgun unconfigured, no production guard, fake success page** (`email.py:52`). Fix: gate the stdout fallback on `APP_ENV != 'production'`; error without the body.
- **Magic-link verification consumes the token and issues a 7-day session on a bare GET** (`auth.py:324`) — mail-provider link scanners burn the token (lockout) and can receive a live session; raw token lands in access logs. Fix: no-side-effect GET interstitial + CSRF-protected POST consume.
- **15 endpoint docs commit a real, identifiable 14U youth team** (full UUID, `public_id`, name/city, exact 61-29-2 record) — the api-docs rule was literally written from this data and the docs were never scrubbed. Fix: sweep all 15 files to the placeholder taxonomy (git history retains old values; this stops propagation). *(api-scout)*
- **Cookie Secure flags + dev-bypass guard all fail open on missing/mistyped `APP_ENV`** (`auth.py:93`, LOW).
- **Passkey registration consume ignores the DELETE rowcount, violating the single-use invariant** (`auth.py:595`, LOW).
- **Report HTML served `Cache-Control: public, max-age=3600`, undermining revocation by up to an hour** (`reports.py:85`, LOW).
- **Login timing reveals whether an email is registered, defeating the route's stated enumeration protection** (`auth.py:317`, LOW).
- **Unauthenticated passkey-options endpoint allows unbounded challenge-row writes** (`auth.py:685`, LOW).
- **Admin denial is per-route opt-in with no sweep test; all POST mutation routes lack non-admin 403 coverage** (`reports_admin.py:664`, LOW).

## Non-Goals (boundary vs. adjacent epics)
- The 15-endpoint-doc PII scrub is shared with CE-5's api-doc truth sweep — the scrub itself is scoped HERE (security); CE-5 handles the doc-ACCURACY corrections to the same files. Coordinate so one pass covers both (or sequence CE-4's scrub first).
- Known-vulnerable dependency PINS (jinja2/starlette CVEs) → CE-6 foundations (dep refresh), not here — though the reachable starlette multipart DoS is security-relevant; note the linkage at refinement.

## Refinement Notes (for the future planning session)
- Never accept infra/network controls (Cloudflare) as a substitute for app-layer fixes (`.claude/agent-memory/product-manager/feedback_csrf_cloudflare.md`) — the magic-link GET-verify fix must be app-layer.
- api-scout owns the 15-file endpoint-doc PII scrub; software-engineer owns the scanner + auth + serving fixes.

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-4). Not refined; not dispatchable until taken to READY.
