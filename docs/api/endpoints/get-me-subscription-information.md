---
method: GET
path: /me/subscription-information
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
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
tags: [me, subscription]
caveats: []
related_schemas: []
see_also:
  - path: /subscription/details
    reason: More detailed subscription information (plan code, billing info, dates, members)
  - path: /me/user
    reason: Also includes has_subscription, access_level, subscription_source fields
---

# GET /me/subscription-information

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns subscription summary for the authenticated user. Higher-level view than `GET /subscription/details`.

```
GET https://api.team-manager.gc.com/me/subscription-information
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `best_subscription` | object | The user's best (highest tier) active subscription |
| `best_subscription.type` | string | Subscription type. Observed: `"team_manager"` |
| `best_subscription.provider_type` | string | Billing provider. Observed: `"recurly"` |
| `best_subscription.is_gc_classic` | boolean | Whether this is a legacy GC Classic subscription |
| `best_subscription.is_trial` | boolean | Whether this is a free trial |
| `best_subscription.end_date` | string (ISO 8601) | Subscription expiration date |
| `best_subscription.access_level` | string | Access tier. Observed: `"premium"` |
| `best_subscription.billing_cycle` | string | Billing frequency. Observed: `"year"` |
| `best_subscription.amount_in_cents` | integer | Amount charged per cycle in cents (9999 = $99.99) |
| `best_subscription.provider_details` | object | Provider-specific renewal/cancellation state |
| `best_subscription.provider_details.will_renew` | boolean | Whether the subscription auto-renews |
| `best_subscription.provider_details.was_terminated_by_provider` | boolean | |
| `best_subscription.provider_details.was_terminated_by_staff` | boolean | |
| `highest_access_level` | string | The overall highest access level across all subscriptions |
| `is_free_trial_eligible` | boolean | Whether the user can start a free trial |

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
