# IDEA-193: The `bb creds import` Access-Token Warning Sends Operators in a Circle

## Status
`CANDIDATE`

## Summary
When an operator pastes a curl carrying an **access** token instead of a refresh token, `bb creds import` warns them to go copy a `POST /auth` curl instead -- but importing a `POST /auth` curl does not work either, so the advice routes them into a dead end and back to the same warning. The message needs to name the three paths that actually work. This is a handful of lines in one function, independent of everything else in the abandoned E-175.

## Why It Matters
This is live today and it actively misdirects. The warning is the only guidance an operator gets at the moment their import silently drops the token they pasted, and it points at the one workflow that is guaranteed to fail. Someone following it faithfully will loop until they give up or read the source.

**Exact text, `src/gamechanger/credential_parser.py::_resolve_web_token_key` (verified present 2026-07-26; the E-175 spec cited it at "line ~270", it is now at lines 290-297 -- cite the symbol, not the line):**

> "gc-token header contains an access token (type='user'), not a refresh token. Access tokens expire in ~60 minutes and cannot be used for programmatic refresh. **To capture a refresh token, copy a curl command from a POST /auth request in browser dev tools (Network tab -> filter by 'auth' -> right-click -> Copy as cURL).** Skipping -- %s will NOT be updated."

The bolded advice is the defect. `import_creds` (`src/cli/creds.py:171`) calls `parse_credentials` and nothing else -- it never executes the curl, so the tokens in a `POST /auth` **response** are unreachable, and a `POST /auth` request carrying a client token is discarded by this same function a few lines below. Both halves of the suggested workflow fail.

**The fix** -- replace with guidance naming the paths that do work (E-175 TN-8's wording, still accurate):

> "To import a refresh token: paste the JSON response body from POST /auth, or copy a curl from a GET request that carries a refresh token in the gc-token header. (Or run `bb creds setup web`, which does the whole login programmatically.)"

Note this is E-175's TN-8 wording with its forward-looking clause removed. The original said "copy a POST /auth curl from browser dev tools (tokens will be extracted automatically)" because it was written assuming the rest of E-175 would ship. It did not, so that clause must **not** be carried over -- it would restate the same false promise the current message makes.

## Rough Timing
Not worth its own epic. The natural carrier is the next epic that touches `src/gamechanger/credential_parser.py` for any reason -- fold it in as a small additional scope item rather than planning around it. If no such epic appears and an operator hits the loop again, promote it then.

## Dependencies & Blockers
- [ ] None. The fix is self-contained in one function and changes no behavior -- only the message text.

## Open Questions
- Should the second warning branch in the same function (unexpected non-null token type, lines 299-307) get the same treatment? It is less misleading -- it says only "Skipping" without giving bad advice -- but it gives no recovery path at all. Probably yes, same edit.

## Notes
Source: extracted from E-175 (Fix `bb creds import` for POST /auth Curl Commands) at abandonment, 2026-07-26. E-175 was abandoned because its main body -- executing captured `POST /auth` curls, five body types, a logout-rejection guard, a full HTTP error matrix -- is a lot of machinery for a **fallback** credential path that has three working alternatives. The warning-message fix is the one piece whose value does not depend on any of that, so it was pulled out rather than archived with the epic. See [[IDEA-194]] for the execution design itself.

The three working import paths, for whoever writes the replacement text: paste the raw JSON response body from `POST /auth` (the `gc_auth` shape is already handled by `_parse_json_credentials()`); copy a curl from a **GET** request whose `gc-token` header carries a refresh token; or use `bb creds setup web`, the documented primary path, which performs the full login programmatically.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
