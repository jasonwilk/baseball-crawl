---
method: PATCH
path: /me/user
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: observed
    notes: 1 hit, status 200. Discovered 2026-03-05.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [me, write]
caveats:
  - >
    WRITE OPERATION: Updates the authenticated user's own profile. Not relevant to
    read-only data ingestion.
  - >
    PII: Request body and response contain user profile data (name, preferences, etc.).
    Never log or store request/response bodies for this endpoint.
  - >
    REQUEST BODY UNKNOWN: Content-Type not captured in proxy log. Likely
    application/json with partial user profile fields.
related_schemas: []
see_also:
  - path: /me/user
    reason: Read user profile (GET -- authenticated, confirmed)
---

# PATCH /me/user

**Status:** OBSERVED (proxy log, 1 hit, status 200). Write operation -- not relevant to data ingestion.

Updates the authenticated user's own profile information (name, preferences, or other mutable fields).

```
PATCH https://api.team-manager.gc.com/me/user
```

## Request

Request body schema not captured. Likely a partial JSON object with user profile fields to update.

## Response

Schema not captured. Status 200 observed. Likely returns the updated user profile object.

**Discovered:** 2026-03-05.
