# E-095-04: Automated Client Key Extraction Command

## Epic
[E-095: Client Key Credential Resilience](epic.md)

## Status
`TODO`

## Description
After this story is complete, running `bb creds extract-key` will automatically fetch the current GameChanger client key from the publicly accessible GC JavaScript bundle, compare it against the current `.env` value, and update `.env` if the key has changed. This makes GC key rotation a non-event -- the operator runs one command instead of manually navigating DevTools, finding the bundle, and grepping for the key.

## Context
The client key (`EDEN_AUTH_CLIENT_KEY`) is embedded in the GC web JavaScript bundle at `https://web.gc.com/static/js/index.{hash}.js`. The bundle is publicly accessible (no auth needed). The key is a composite value in the format `clientId:clientKey`, where the client key is a 44-character base64 string (HMAC-SHA256 secret). The JS bundle URL changes with each deployment (the hash in the filename changes), but the HTML page at `https://web.gc.com` always links to the current bundle via a `<script>` tag.

The extraction process (confirmed working manually):
1. Fetch `https://web.gc.com` to get the HTML page
2. Find the `<script>` tag with `src` matching `static/js/index.*.js`
3. Fetch that JS bundle
4. Regex for `EDEN_AUTH_CLIENT_KEY:"([^"]+)"` to extract the composite value
5. Split on `:` (first occurrence) -- left side is `client_id` (UUID), right side is `client_key` (base64)

## Acceptance Criteria
- [ ] **AC-1**: A new `extract-key` command exists in the `bb creds` command group. Running `bb creds extract-key` fetches the GC homepage HTML, finds the JS bundle URL, downloads the bundle, and extracts the `EDEN_AUTH_CLIENT_KEY` value.
- [ ] **AC-2**: Dry-run by default: the command prints what it found and what would change in `.env`, but does NOT write to `.env` unless `--apply` is passed. This follows the same pattern as `bb proxy refresh-headers`.
- [ ] **AC-3**: When `--apply` is passed and the key has changed, the command updates `GAMECHANGER_CLIENT_KEY_WEB` and `GAMECHANGER_CLIENT_ID_WEB` in `.env` using `atomic_merge_env_file()` from `src/gamechanger/credential_parser.py`.
- [ ] **AC-4**: The command output shows a clear diff: "Client ID: {current} -> {new}" and "Client Key: [changed]" (never showing the actual key values, only whether they changed). When the client ID is unchanged, show "Client ID: [unchanged]" (do not omit the line -- the operator should see it was checked). If the key is unchanged, output "Client key is current (no update needed)."
- [ ] **AC-4a**: In dry-run mode (default), the output opens with a banner: "Dry run -- pass --apply to write to .env" (or similar) so the operator knows no changes were written.
- [ ] **AC-4b**: After `--apply` writes successfully, the command prints a confirmation message (e.g., "Updated GAMECHANGER_CLIENT_KEY_WEB and GAMECHANGER_CLIENT_ID_WEB in .env") followed by a next-step prompt: "Next: run `bb creds check --profile web` to verify, then `bb creds refresh --profile web` to test token refresh." This closes the recovery loop.
- [ ] **AC-5**: When the HTML page cannot be fetched (network error, non-200 status), the command prints a clear error including the target URL and exits with code 1.
- [ ] **AC-6**: When the JS bundle URL cannot be found in the HTML (page structure changed), the command prints a clear error explaining what it looked for and exits with code 1.
- [ ] **AC-7**: When `EDEN_AUTH_CLIENT_KEY` cannot be found in the JS bundle (variable name changed), the command prints a clear error and exits with code 1.
- [ ] **AC-8**: The extraction logic (fetching HTML, finding bundle URL, downloading bundle, extracting key) lives in a reusable module under `src/gamechanger/` (not inline in the CLI command), so it can be called from other code paths in the future.
- [ ] **AC-9**: The HTTP requests use `httpx.Client` with `trust_env=False` (no proxy -- this is a public web request, not a GC API call). Standard browser-like headers from `src/http/headers.py` are used.
- [ ] **AC-10**: The command respects the composite format: the regex captures `EDEN_AUTH_CLIENT_KEY:"<uuid>:<base64-key>"` and splits on the first `:` only (the base64 key may contain `=` padding but not `:`).
- [ ] **AC-10a**: If multiple `<script>` tags match the `static/js/index.*.js` pattern, the command uses the first match and logs a warning. This handles potential edge cases in the HTML structure without failing.
- [ ] **AC-11**: Tests cover: successful extraction (mock HTML with script tag, mock bundle with EDEN_AUTH_CLIENT_KEY), key unchanged scenario, key changed scenario with --apply, HTML fetch failure, bundle URL not found, EDEN_AUTH_CLIENT_KEY not found in bundle, multiple matching script tags (use first, log warning). All tests mock HTTP -- no real network calls.
- [ ] **AC-12**: The command never prints, logs, or stores the actual client key value in any output. It shows the client ID (a UUID, not sensitive) and indicates whether the key changed, but the key itself is treated as a secret.

## Technical Approach
The extraction logic belongs in a new module under `src/gamechanger/` (e.g., `key_extractor.py` or similar). The CLI command in `src/cli/creds.py` is a thin wrapper that calls the extractor, compares results against current `.env` values, and optionally writes updates. The HTML parsing can use simple regex or string matching -- the `<script>` tag pattern is stable and a full HTML parser is unnecessary.

The `atomic_merge_env_file()` helper from `src/gamechanger/credential_parser.py` handles the `.env` write-back, consistent with how `TokenManager` persists rotated refresh tokens.

Reference files:
- `src/gamechanger/credential_parser.py` -- `atomic_merge_env_file()` for .env write-back
- `src/http/headers.py` -- `BROWSER_HEADERS` for the HTTP request
- `src/cli/creds.py` -- existing command patterns (app Typer group)

## Dependencies
- **Blocked by**: None
- **Blocks**: E-095-03 (docs story references this command)

## Handoff Context
- **Produces for E-095-03**: The command name (`bb creds extract-key`), the `--apply` flag semantics, and the output format. E-095-03 documents both the manual and automated extraction processes.

## Files to Create or Modify
- `src/gamechanger/key_extractor.py` (new) -- extraction logic: fetch HTML, find bundle URL, download bundle, extract EDEN_AUTH_CLIENT_KEY, parse composite value
- `src/cli/creds.py` -- new `extract_key` command
- `tests/test_key_extractor.py` (new) -- tests for the extraction module
- `tests/test_cli_creds.py` (or equivalent) -- tests for the CLI command integration

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
