# IDEA-194: Execute `POST /auth` Curls in `bb creds import`

## Status
`CANDIDATE`

## Summary
Make `bb creds import` handle a `POST /auth` curl copied from browser dev tools by actually **executing** the request and reading the tokens out of the response body, rather than only parsing request headers. This is the full design from E-175, preserved at that epic's abandonment on 2026-07-26 because the design is sound -- what failed was the cost/benefit, not the plan.

## Why It Matters
The natural operator instinct is "copy the auth request, paste it, import it," and that is precisely the shape that does not work. Three independent defects combine (all three verified still present in current code on 2026-07-26):

1. **Client tokens are discarded.** `_resolve_web_token_key` (`src/gamechanger/credential_parser.py:282`) returns `None` for any token whose type is non-null and not `"user"`, so the client token a password/user-auth/client-auth curl carries is silently dropped and validation fails.
2. **The tokens are in the response, not the request.** `import_creds` (`src/cli/creds.py:171`) calls `parse_credentials` and stops -- it never issues the request, so a `POST /auth` response body is unreachable. (Exception: a refresh-type curl already carries the refresh token in its `gc-token` header and parses fine -- but the operator has no way to know which type they copied.)
3. **The warning misdirects.** Covered separately in [[IDEA-193]], which is the cheap independent half and should not wait on this.

## Rough Timing
**Explicit promotion trigger: the operator hits this and all three workarounds fail.** That is the bar, and it is deliberately high -- this fixes a fallback path, and `bb creds setup web` (the documented primary, which does the full login programmatically) plus two other working import shapes stand between an operator and this pain. Do not promote on the defect being real; it is real and has been for months without anyone being blocked.

## Dependencies & Blockers
- [ ] None technical. Every symbol the design references still exists and is unchanged in shape.

## Open Questions
- Is the fallback path worth machinery at all, or should `bb creds import` simply **detect** a `POST /auth` curl and print "paste the JSON response body instead"? That is a fraction of the work and closes most of the operator confusion. This is the question to answer before promoting -- the full execution design may be over-built for the need.

## Notes
Source: E-175, abandoned 2026-07-26. Full spec preserved at `/.project/archive/E-175-creds-import-post-auth/`, including the two-layer architecture (parser stays pure and raises a carrier exception; the CLI layer owns HTTP execution), the five body types, the error-handling matrix, and the credential-merge rules. Read it there rather than re-deriving.

**Three constraints from that spec that must survive any future attempt**, because each is a real hazard rather than a design preference:

- **Never execute a `{"type":"logout"}` curl.** Running it invalidates the refresh token server-side and destroys the operator's GameChanger session. Detect the body type *before* making any HTTP call and refuse.
- **Do not route the execution through `create_session()`** (`src/http/session.py`). It injects project default headers, and the captured `gc-signature` was computed over the original request's parameters -- substituting headers can invalidate it. This is a one-shot curl replay, a named exception to normal HTTP discipline: use a plain client with no default headers, pass the captured headers verbatim, and send the body as raw content rather than re-serialized JSON.
- **The body may contain a password.** `{"type":"password","password":"..."}` is one of the five shapes. It may be used as request content and nothing else -- never logged, never written to `.env`, never printed.

**Correction to the record, carried forward deliberately.** E-175 was demoted READY→DRAFT on 2026-07-08 partly on the stated ground that "the auth/credential code has since changed materially (notably E-254's auth hardening -- magic-link GET/POST split, passkey/login changes)." **That reason is wrong.** E-254 hardened *app-internal* authentication in `src/api/` -- magic links, passkeys, production detection -- which is a different subsystem from GameChanger credential import in `src/gamechanger/credential_parser.py`. It does not touch this surface, and all three defects above survived it untouched. The demotion **verdict** was right (the epic was stale on age and on value); only its cited reason was false. Recorded here so the next triage does not inherit it -- a verdict's stated reason rots independently of the verdict, and a correct conclusion protects its false premise from review.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
