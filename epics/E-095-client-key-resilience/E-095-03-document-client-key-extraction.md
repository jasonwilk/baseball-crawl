# E-095-03: Document Client Key Extraction Process

## Epic
[E-095: Client Key Credential Resilience](epic.md)

## Status
`TODO`

## Description
After this story is complete, `docs/api/auth.md` will contain a "Client Key Extraction" section documenting both the automated (`bb creds extract-key`) and manual (browser DevTools) processes for obtaining a fresh client key from the GameChanger web JavaScript bundle. The section will include the exact JS variable name (`EDEN_AUTH_CLIENT_KEY`), the composite format, staleness symptoms, and verification steps. The operator will be able to recover from a stale client key by following documented procedures instead of reverse-engineering the extraction process from scratch.

## Context
The client key was originally extracted manually from the GC JS bundle (referenced in `data/raw/gc-signature-algorithm.md`), but the extraction steps were never written up as an operator-facing procedure. When GC rotated the key, the operator had to rediscover the process -- spending significant time chasing misleading "credentials expired" errors before realizing the client key was the problem.

The key is embedded in the bundle as `EDEN_AUTH_CLIENT_KEY` in the format `clientId:clientKey`. It is an app-wide secret (same for all users), embedded in a publicly accessible JavaScript bundle. It only changes when GC redeploys their web bundle.

## Acceptance Criteria
- [ ] **AC-1**: `docs/api/auth.md` has a new "Client Key Extraction" section (as a top-level section, after "Required Credentials" and before "Token Health Check") with two subsections: "Automated Extraction" and "Manual Extraction (Browser DevTools)."
- [ ] **AC-2**: The "Automated Extraction" subsection documents `bb creds extract-key` (dry-run by default, `--apply` to write), including example output showing the diff format.
- [ ] **AC-3**: The "Manual Extraction" subsection has numbered steps: (1) open `https://web.gc.com` in Chrome, (2) open DevTools Sources tab, (3) search the JS bundle for `EDEN_AUTH_CLIENT_KEY`, (4) the value is a composite `clientId:clientKey` string -- copy it, (5) split on the first `:` to get the UUID (client_id) and the base64 string (client_key), (6) update `.env` with `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB`.
- [ ] **AC-4**: The section includes a "How to Know the Key Is Stale" subsection explaining: (a) the symptom -- all auth fails, `bb creds refresh` says "Credentials expired" or "Signature rejected", `bb creds check` shows `[XX]` on Client Key section, (b) the cause -- GC redeployed their JS bundle with a new `EDEN_AUTH_CLIENT_KEY`, (c) the misleading diagnostic path -- refresh token looks valid, presence check passes, but every POST /auth call fails with HTTP 401.
- [ ] **AC-5**: The section includes a note that the client key is app-wide (same for all users), not per-user. Also notes it only changes when GC redeploys the web bundle (potentially months between rotations, but unpredictable). Also notes that `GAMECHANGER_CLIENT_ID_WEB` may change at the same time (it is part of the same composite value).
- [ ] **AC-6**: The section includes a verification step: after updating `.env`, run `bb creds check --profile web` and confirm the Client Key section shows `[OK]`, then run `bb creds refresh --profile web` to confirm the token refresh succeeds.
- [ ] **AC-7**: No credential values (actual client keys, client IDs, bundle hashes) appear in the documentation. Only placeholder examples and the variable name `EDEN_AUTH_CLIENT_KEY`.
- [ ] **AC-8**: The existing "Client Key" subsection under "gc-signature Signing Algorithm" cross-references the new extraction section for the step-by-step procedure.
- [ ] **AC-9**: The JS bundle URL pattern (`https://web.gc.com/static/js/index.{hash}.js`) is documented, noting that the hash changes with each deployment.
- [ ] **AC-10**: The section notes that the client-auth step (step 2) requires no `previousSignature` -- it is always the first call in any login sequence. This is helpful context for operators reading about the signing algorithm.
- [ ] **AC-11**: The automated extraction subsection notes that the HTML page must be fetched fresh each time -- never cache the bundle URL between runs, since the hash changes on every GC deployment.

## Technical Approach
This is a documentation-only story. The new content goes into `docs/api/auth.md`, which already has sections on the client key's role in signing. The new section documents the *extraction and recovery procedures* rather than the algorithm. This story depends on E-095-04 so that the `bb creds extract-key` command exists and can be accurately documented.

Reference files:
- `docs/api/auth.md` -- existing auth documentation, target for new section
- `data/raw/gc-signature-algorithm.md` -- technical details about the key's location in the JS bundle

## Dependencies
- **Blocked by**: E-095-02 (docs reference `bb creds check` Client Key Validation section output), E-095-04 (needs the automated extraction command to exist before documenting it)
- **Blocks**: None

## Files to Create or Modify
- `docs/api/auth.md` -- new "Client Key Extraction" section with automated and manual subsections, cross-reference from existing "Client Key" subsection

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
