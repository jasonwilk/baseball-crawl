---
method: GET
path: /places/{place_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. Full schema observed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.place_details+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "1 record"
discovered: "2026-03-11"
last_confirmed: null
tags: [schedule, games]
caveats:
  - >
    GOOGLE PLACES ID: The place_id path parameter is a Google Places API ID
    (e.g., ChIJQ2fqS8z3k4cRUG4qNPnoWI0). These IDs appear in event location
    data from /teams/{team_id}/schedule and /me/schedule.
see_also:
  - path: /me/schedule
    reason: Events in schedule responses may reference place_ids for venue details
  - path: /teams/{team_id}/schedule
    reason: Team schedule -- events may contain place_id references
---

# GET /places/{place_id}

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns detailed location information for a specific place, identified by a Google Places API ID. Used to resolve venue details (address, coordinates, location name) for game and practice events.

```
GET https://api.team-manager.gc.com/places/{place_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `place_id` | string | Google Places API place ID (e.g., `ChIJQ2fqS8z3k4cRUG4qNPnoWI0`) |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.place_details+json; version=0.0.0
```

## Response

**HTTP 200.** Single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Google Places place ID (same as path param) |
| `lat_long` | object | Geographic coordinates |
| `lat_long.lat` | number | Latitude (decimal degrees) |
| `lat_long.long` | number | Longitude (decimal degrees) |
| `address` | string | Full formatted address string |
| `address_object` | object | Structured address components |
| `address_object.street_number` | string | Street number |
| `address_object.street_name` | string | Street name |
| `address_object.city` | string | City |
| `address_object.state` | string | State abbreviation |
| `address_object.country` | string | Country name |
| `address_object.postal_code` | string | ZIP/postal code |
| `location_name` | string | Venue name (e.g., school or park name) |
| `types` | array of string | Google Places types. Observed: `["establishment", "point_of_interest", "school", "secondary_school"]`. |

## Example Response

```json
{
  "id": "ChIJQ2fqS8z3k4cRUG4qNPnoWI0",
  "lat_long": {
    "lat": 41.000000,
    "long": -96.000000
  },
  "address": "12345 Example Rd, Anytown, XX 00000, USA",
  "address_object": {
    "street_number": "12345",
    "street_name": "Example Rd",
    "city": "Anytown",
    "state": "XX",
    "country": "United States",
    "postal_code": "00000"
  },
  "location_name": "Anytown Field",
  "types": ["establishment", "point_of_interest", "school", "secondary_school"]
}
```

**Coaching relevance: LOW.** Venue lookup for display purposes. Not needed for stats ingestion. Useful if building a schedule view with venue maps.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
