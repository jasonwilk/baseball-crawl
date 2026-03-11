---
method: GET
path: /ics-calendar-documents/user/{user_id}.ics
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. Returns iCal VCALENDAR format.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "text/calendar"
gc_user_action: null
query_params: []
pagination: false
response_shape: string
response_sample: null
raw_sample_size: null
discovered: "2026-03-11"
last_confirmed: null
tags: [calendar, schedule, me]
caveats:
  - >
    NON-JSON RESPONSE: This endpoint returns iCalendar (RFC 5545) format text, not JSON.
    The Accept header is text/calendar. Do not attempt to parse as JSON.
  - >
    URL SUFFIX: The path includes a literal .ics file extension as part of the URL
    (e.g., /ics-calendar-documents/user/{uuid}.ics). This is unusual compared to
    other GC API paths but is the documented pattern.
see_also:
  - path: /me/schedule
    reason: Same schedule data in JSON format -- prefer for programmatic access
  - path: /me/external-calendar-sync-url/team/{team_id}
    reason: Team-scoped iCal subscription URL (different path pattern)
---

# GET /ics-calendar-documents/user/{user_id}.ics

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns the user's full schedule as an iCalendar (RFC 5545) document. The response body is a standard VCALENDAR format with VEVENT entries for each scheduled event across all teams.

This endpoint is used by the web app to enable "Export to Calendar" functionality (Google Calendar, Apple Calendar, Outlook, etc.).

```
GET https://api.team-manager.gc.com/ics-calendar-documents/user/{user_id}.ics
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | UUID | The user UUID (obtained from GET /me/user `id` field) |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: text/calendar
```

## Response

**HTTP 200.** iCalendar text (RFC 5545). Content-Type: `text/calendar`.

Key iCal fields observed per VEVENT:

| iCal Field | Description |
|------------|-------------|
| `UID` | GC event UUID |
| `DTSTART` | Event start time (UTC) |
| `DTEND` | Event end time (UTC) |
| `SUMMARY` | Event title (e.g., team name + event type) |
| `LOCATION` | Address of venue |
| `GEO` | Latitude/longitude coordinates |
| `DESCRIPTION` | Event notes/description |
| `STATUS` | Event status. Observed: `CONFIRMED`. |
| `CLASS` | Visibility. Observed: `PUBLIC`. |
| `DTSTAMP` | Document generation timestamp |
| `CREATED` | Event creation timestamp |
| `LAST-MODIFIED` | Last modification timestamp |
| `X-WR-CALNAME` | Calendar name (team name) |
| `X-PUBLISHED-TTL` | Cache freshness hint. Observed: `PT18000S` (5 hours). |

## Example Response (truncated)

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//com.gc/NONSGML GameChanger - Back End//EN
X-WR-CALNAME:Example Team 9U
X-PUBLISHED-TTL:PT18000S
BEGIN:VEVENT
UID:00000000-REDACTED
DTSTAMP:20260311T035206Z
CREATED:20251012T133918Z
LAST-MODIFIED:20251116T170649Z
DTSTART:20251214T193000Z
CLASS:PUBLIC
SUMMARY:Example Team 9U Practice
GEO:40.000000;-96.000000
LOCATION:Anytown Field
DESCRIPTION:Optional practice\n1:30-3
STATUS:CONFIRMED
DTEND:20251214T203000Z
END:VEVENT
END:VCALENDAR
```

**Coaching relevance: NONE.** Calendar export for end-user convenience. For programmatic schedule access, use `GET /me/schedule` (JSON format).

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
