---
method: GET
path: /me/user
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Used as token health check (200 = valid, 401 = expired).
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.user+json; version=0.3.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/me-user-sample.json
raw_sample_size: "PII-redacted user profile, ~1 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [user, auth]
related_schemas: []
see_also:
  - path: /me/teams
    reason: First call after authentication to discover team UUIDs
  - path: /me/subscription-information
    reason: Detailed subscription info including provider_details and access levels
---

# GET /me/user

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-04.

Returns the authenticated user's profile and subscription information. The primary use case is a **token health check**: a 200 response confirms the `gc-token` is valid; a 401 response means the token has expired and must be rotated.

```
GET https://api.team-manager.gc.com/me/user
```

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.user+json; version=0.3.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

No `gc-user-action` observed for this endpoint.

## Response

Single JSON object with 12 top-level fields. Response contains PII (email, name). Never log or store unredacted.

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | User UUID. Same as the `uid` field in the decoded JWT payload. |
| `email` | string | User email address. **PII -- redact in stored files.** |
| `first_name` | string | First name. **PII.** |
| `last_name` | string | Last name. **PII.** |
| `registration_date` | string (ISO 8601) | Account creation date. |
| `status` | string | Account status. Observed: `"active"`. |
| `is_bats_account_linked` | boolean | Whether the BATS (Baseball Analytics Tracking System) account is linked. |
| `is_bats_team_imported` | boolean | Whether teams have been imported from BATS. |
| `has_subscription` | boolean | Whether the user has an active subscription. |
| `access_level` | string | User's access level (e.g., `"premium"`, `"free"`). |
| `subscription_source` | string or null | Source of subscription (e.g., `"apple"`, `"stripe"`, or null). |
| `subscription_information` | object | Detailed subscription data. |

### subscription_information Object

| Field | Type | Description |
|-------|------|-------------|
| `best_subscription` | object or null | Details about the user's active/best subscription. |
| `best_subscription.type` | string | Subscription plan type. |
| `best_subscription.provider` | string | Billing provider (e.g., `"apple"`, `"stripe"`). |
| `best_subscription.billing_cycle` | string | Billing period (e.g., `"monthly"`, `"annual"`). |
| `best_subscription.amount_in_cents` | int | Price in cents. |
| `best_subscription.end_date` | string (ISO 8601) | When the subscription expires. |
| `best_subscription.provider_details` | object | Provider-specific billing details. |
| `highest_access_level` | string | Highest access level across all subscriptions. |

## Token Health Check Pattern

```python
def check_token_health(session) -> bool:
    """Returns True if the token is valid, False if expired."""
    response = session.get(
        "https://api.team-manager.gc.com/me/user",
        headers={"Accept": "application/vnd.gc.com.user+json; version=0.3.0"}
    )
    return response.status_code == 200
```

Run this before starting any long ingestion run. Token lifetime is 14 days (see `auth.md`).

The `id` field in the response matches the `uid` field in the decoded JWT payload, confirming the token belongs to the expected account.

## Known Limitations

- All fields are PII (email, first_name, last_name). Redact in all stored files and logs.
- `subscription_information.best_subscription` may be null for free accounts.
- `subscription_source` can be null.
- Token lifetime is 14 days -- call this endpoint before long runs to confirm the token is still valid.

**Discovered:** 2026-03-04. **Last confirmed:** 2026-03-04.
