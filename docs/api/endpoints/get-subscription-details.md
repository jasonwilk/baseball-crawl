---
method: GET
path: /subscription/details
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Previously observed in proxy -- status upgraded. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [subscription, user]
caveats: []
related_schemas: []
see_also:
  - path: /me/subscription-information
    reason: Higher-level subscription summary (less detail but simpler structure)
---

# GET /subscription/details

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns detailed subscription information for the authenticated user.

```
GET https://api.team-manager.gc.com/subscription/details
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `highest_tier` | string | User's highest subscription tier. Observed: `"premium"` |
| `is_free_trial_eligible` | boolean | Whether the user can start a free trial |
| `subscriptions` | array | Array of active subscription objects |
| `subscriptions[].id` | UUID | Subscription UUID |
| `subscriptions[].plan` | object | Plan details |
| `subscriptions[].plan.provider` | string | Billing provider (`"recurly"`) |
| `subscriptions[].plan.code` | string | Plan code (e.g., `"premium_year"`) |
| `subscriptions[].plan.level` | integer | Tier level number (3 for premium) |
| `subscriptions[].plan.tier` | string | Tier name (`"premium"`) |
| `subscriptions[].plan.max_allowed_members` | integer | Max users on this subscription |
| `subscriptions[].status.is_billing` | boolean | Whether billing is active |
| `subscriptions[].status.is_in_free_trial` | boolean | |
| `subscriptions[].status.is_canceled` | boolean | |
| `subscriptions[].status.is_paused` | boolean | |
| `subscriptions[].status.is_expired` | boolean | |
| `subscriptions[].status.is_unpaid` | boolean | |
| `subscriptions[].billing_info.amount_in_cents` | integer | Amount in cents |
| `subscriptions[].billing_info.currency` | string | Currency code (`"USD"`) |
| `subscriptions[].billing_info.cycle` | string | `"yearly"` or `"monthly"` |
| `subscriptions[].dates.start` | string (ISO 8601) | Subscription start date |
| `subscriptions[].dates.end` | string (ISO 8601) | Subscription end/renewal date |
| `subscriptions[].is_owner` | boolean | Whether this user owns the subscription |
| `subscriptions[].is_gc_classic` | boolean | Legacy subscription flag |
| `subscriptions[].members` | array | Shared subscription members |

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
