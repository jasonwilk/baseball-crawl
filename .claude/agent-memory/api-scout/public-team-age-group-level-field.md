---
name: public-team-age-group-level-field
description: age_group on GET /public/teams/{public_id} is a polymorphic three-family LEVEL field (school/travel/recreational) carrying high_varsity/high_junior_varsity/high_freshman — available for teams we do NOT manage, at zero extra request cost
metadata:
  type: reference
---

# `age_group` is a LEVEL field, not an age bracket (verified live 2026-07-25)

`GET /public/teams/{public_id}` returns a top-level `age_group` string. **The name is
misleading.** It is not merely an age bracket — it is a **polymorphic level field** whose
value is drawn from one of three disjoint vocabularies, and for school teams it carries an
explicit varsity / JV / freshman token.

## The three families

| family | `competition_level` (auth-only) | `age_group` values |
|---|---|---|
| **school** | `school` | `elementary`, `middle_12U`, `middle_13O`, `high_freshman`, `high_junior_varsity`, `high_varsity`, `college` |
| **travel** | `club_travel` | `NNU` brackets — observed live: `8U 9U 10U 11U 12U 13U 14U 15U 18U` |
| **recreational** | `recreational` | free-text ranges rendering as `"Between 13 - 18"` |

Union is roughly 22 values, which is the likely referent of the operator's phrase
"levels of > 15" (i.e. the picker has >15 options — NOT a numeric level above 15;
the numeric reading was refuted by the sample). That phrasing was never confirmed.

## Provenance — GameChanger's own client code, NOT inference

The school family is **exhaustively enumerated** in GC's public web bundle
(`https://web.gc.com/static/js/index.*.js`, fetched unauthenticated). The display mapper:

```js
if (e.competition_level === Ja.SCHOOL) switch (e.age_group) {
  case "elementary":       return "Elementary School";
  case "high_varsity":
  case "high_junior_varsity":
  case "high_freshman":    return "High School";
  case "middle_12U":
  case "middle_13O":       return "Middle School";
  case "college":          return "College";
}
```

and the team-creation picker gives the labels:

```js
const dl = { [xt.HIGH_FRESHMAN]:"Freshman", [xt.HIGH_JUNIOR_VARSITY]:"Junior Varsity", [xt.HIGH_VARSITY]:"Varsity" };
```

**The bundle is the authoritative source for this enum.** Re-fetch it (hashed filename
changes per deploy — find it via `src=` in the team page HTML) rather than guessing values.
The bracket/range families' string literals are NOT in that bundle (generated dynamically);
those were observed empirically off live responses.

## Where it lives — zero extra cost

- **`GET /public/teams/{public_id}`** — top level, **no auth**. This is the response the
  report generator already fetches and parses. Available for teams we do **not** manage:
  an 18-team sweep of `membership_type='tracked'` opponents returned a populated
  `age_group` on **all 18**.
- `GET /teams/{gc_uuid}` (auth) — same field, plus `competition_level`.
- **`competition_level` is authenticated-ONLY — not on the public profile.** Mostly does
  not matter: `age_group` is self-disambiguating by shape (`high_*`/`middle_*` ⇒ school,
  `NNU` ⇒ travel, `Between N - M` ⇒ recreational).
- **NOT available from `POST /search`** — hits carry no `age_group`/`competition_level`
  at all (see [[search-endpoint-notes]]). The public profile is the only cheap source.

## It discriminates — verified live

`GET /me/teams`, own program, spring 2026, `competition_level: "school"`:
`high_varsity` ×1, `high_junior_varsity` ×1, `high_freshman` ×2. That is exactly the
varsity/JV/freshman split that `detect_league_level`
(`src/reports/starter_prediction.py`) otherwise guesses from team-name keywords.

**Parser gap worth knowing:** that function's `age_group` branch tests only `\d+U\b` and
`\b\d+\s*-\s*\d+\b`. Every `high_*` value matches **neither**, so school teams fall through
to name-keyword matching while the field naming their level sits unread in the same response.

## CAVEAT A — operator-entered, not authoritative about the league

`age_group` is whatever the opposing coach **selected** when creating the team in
GameChanger. It is authoritative about that selection, **not** about the team's actual
league classification. It can be wrong, stale, or left at a default. Treat it as a strong
signal, never as ground truth.

## CAVEAT B — varsity/JV never yet seen on an OPPONENT's public profile

`high_varsity` and `high_junior_varsity` were observed **only on our own teams**, via the
authenticated `/me/teams`. The 18-team opponent sweep against the public profile found
**only** `high_freshman`. So the claim "the public profile exposes the varsity/JV token for
teams we don't manage" is **extrapolated, not observed**.

**Close this before any code depends on the field.** It is one cheap unauthenticated call
against a known opposing varsity team's `public_id`.

## Additional limit — GameChanger has no "reserve" level

The HS enum is three values. LSB's four classifications (freshman / reserve / JV / varsity)
do **not** map 1:1 — note the two `high_freshman` teams above, almost certainly Freshman +
Reserve collapsed. Harmless for pitch-rest rules (both sit in `nsaa_subvarsity`), but real.

## Doc corrections owed

`docs/api/endpoints/get-public-teams-public_id.md`, `get-teams-team_id.md`, and
`get-me-teams.md` all describe `age_group` as a free-text age bracket. That is wrong **in
kind**, not just incomplete. Deferred as post-dispatch follow-up (E-272 dispatch had
`docs/api/**` hook-blocked). Related: [[public-team-profile-season-shape]],
[[public-team-accept-header-inert]].
