---
method: GET
path: /subscription/recurly/plans
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 6 plans observed. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "6 plans"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [subscription, user]
caveats: []
related_schemas: []
see_also:
  - path: /subscription/details
    reason: User's current subscription status and plan
---

# GET /subscription/recurly/plans

**Status:** CONFIRMED LIVE -- 200 OK. 6 plans observed. Last verified: 2026-03-07.

Returns all available subscription plans offered by GameChanger via Recurly.

```
GET https://api.team-manager.gc.com/subscription/recurly/plans
```

## Response

Bare JSON array of plan objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Plan UUID |
| `name` | string | Plan display name |
| `code` | string | Plan code (e.g., `"premium_year"`, `"plus_month"`) |
| `tier` | string | Tier name: `"plus"` or `"premium"` |
| `level` | integer | Tier level (1=plus, 3=premium solo, 7=premium shared) |
| `maximum_allowed_members` | integer | Max users on shared plan |
| `provider` | string | `"recurly"` |
| `billing.interval` | integer | Billing interval count |
| `billing.interval_unit` | string | `"months"` |
| `billing.price_in_cents` | integer | Price per cycle in cents |
| `billing.currency` | string | `"USD"` |
| `free_trial.length_in_days` | integer | Free trial length |
| `free_trial.is_user_eligible` | boolean | Whether this user can start a trial for this plan |

### Observed Plans (2026-03-07)

| Plan Code | Name | Price | Cycle | Max Users |
|-----------|------|-------|-------|-----------|
| `premium_year_shared` | Premium Yearly Shared | $179.99 | year | 4 |
| `premium_month_shared` | Premium Monthly Shared | $24.99 | month | 4 |
| `plus_month` | Plus Monthly | $9.99 | month | 1 |
| `plus_year` | Plus Yearly | $39.99 | year | 1 |
| `premium_year` | Premium Yearly | $99.99 | year | 1 |
| `premium_month` | Premium Monthly | $14.99 | month | 1 |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
