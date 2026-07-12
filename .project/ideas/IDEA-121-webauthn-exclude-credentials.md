# IDEA-121: Passkey registration does not exclude already-registered credentials

**Status**: CANDIDATE
**Created**: 2026-07-10
**Source**: E-256-08. SE refused to delete the dead block that was the only in-code evidence of this gap, and escalated. **This idea exists so the deletion can proceed without erasing the bug report.**

## The Gap

`POST /auth/passkey/register/begin` (`src/api/routes/auth.py`) fetches the user's existing passkey credential IDs, then **never passes them to `generate_registration_options()`**. The `exclude_credentials` parameter is not supplied.

Verified, not assumed:
- `grep -rn 'exclude_credentials' src/ tests/` → **zero matches, repo-wide.**
- `inspect.signature(webauthn.generate_registration_options)` → **the parameter exists.** The library supports it.
- The code says what it was for. `auth.py:640` reads: `# Fetch existing credentials to exclude from registration options.`

The block as it stands (pre-deletion, preserved here verbatim because the code is about to be removed):

```python
# Fetch existing credentials to exclude from registration options.
existing_creds: list[bytes] = []
try:
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            "SELECT credential_id FROM passkey_credentials WHERE user_id = ?",
            (user_id,),
        )
        existing_creds = [row[0] for row in cursor.fetchall()]
except sqlite3.Error:
    logger.exception("DB error fetching existing passkey credentials for user %d", user_id)

registration_options = generate_registration_options(
    rp_id=rp_id,
    rp_name="Baseball Stats",
    user_name=email,
    user_id=str(user_id).encode(),
    user_display_name=email,
    authenticator_selection=AuthenticatorSelectionCriteria(...),
)   # <-- no exclude_credentials
```

## Effect, stated honestly

A user can silently re-register an authenticator they have already registered, producing duplicate `passkey_credentials` rows for one physical key. **This is not an authentication bypass and not a vulnerability** — every credential still belongs to the correct user, and login is unaffected. It is a hygiene and UX defect: the WebAuthn spec provides `excludeCredentials` precisely so the browser refuses the ceremony instead of minting a duplicate.

Severity: **minor, security-adjacent.** Worth fixing; not worth a hotfix.

## The Fix

```python
exclude_credentials=[PublicKeyCredentialDescriptor(id=c) for c in existing_creds]
```

Plus the import, plus a test asserting the descriptors reach the options object, plus a decision about what the client does when the browser rejects the ceremony (today it would surface as a generic registration failure).

**Why it was not done in E-256-08:** that story adopts ruff F-class linting. Implementing a WebAuthn behavior change under a lint story is exactly the scope creep the story guards against. The dead block was deleted there; **this idea is its replacement, filed BEFORE the deletion landed** so the intent survives outside the code.

## Trigger to Promote

Any of:
1. A user or operator reports duplicate passkeys for one authenticator.
2. Any epic touching `src/api/routes/auth.py`'s registration path — fold it in there.
3. A passkey-UX pass (the client-side rejection message needs designing regardless).

## Non-Goals

- Deleting duplicate `passkey_credentials` rows that may already exist. Separate question; measure first.
- Treating this as a vulnerability. It is not one.

## Related

- E-256-08 AC-4 (the F841 that surfaced it).
- [[IDEA-112]] — the other security-adjacent residue from this cycle.
