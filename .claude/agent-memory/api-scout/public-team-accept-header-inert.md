---
name: public-team-accept-header-inert
description: NEGATIVE observation — the vendor Accept is INERT on GET /public/teams/{public_id} for CORRECT-vs-ABSENT only; a WRONG vendor type still 415s there (2026-07-26). Includes the reusable bare-vs-bare control for A/B diffing endpoints with signed URLs
metadata:
  type: reference
---

# The vendor `Accept` is INERT on `GET /public/teams/{public_id}` (verified 2026-07-25)

**Do not re-probe this.** This is the negative observation the endpoint doc lacked, which is
what forced the probe in the first place.

Sending `Accept: application/vnd.gc.com.public_team_profile+json; version=0.1.0` +
`gc-app-name: web` (what `src/gamechanger/team_resolver.py` pins) versus sending neither
(what `create_session()` produces) makes **no difference to the response**:

- Zero paths present in one variant only; zero type mismatches.
- **Identical `content-length`** byte counts across three paired teams.
- Every consumed field identical: `name`, `ngb`, `age_group`, `team_season.{year,season}`.
- Response `content-type` is `application/json; charset=utf-8` under **both** — the server
  does **not** echo the vendor media type.
- **`Vary: Origin,Accept-Encoding` — notably NOT `Accept`.** Independent server-side
  corroboration that `Accept` does not select the representation.

Conclusion: this endpoint does not content-negotiate **across the pair that was tested**. The
`version=0.1.0` pin is inert in both directions for that pair — adopting it cannot regress us,
and omitting it costs nothing.

## ⚠️ BOUND ON THE ABOVE (2026-07-26) — "inert" ≠ "any Accept is safe"

The 2026-07-25 experiment compared the **correct** vendor type against a **bare** request. It
never sent a **wrong** one. On 2026-07-26 a wrong resource type
(`public_game:list+json`) sent to this same endpoint returned a hard **HTTP 415**.

| `Accept` sent | Result |
|---|---|
| correct vendor type | 200, byte-identical to bare |
| absent / browser-generic | 200, byte-identical to vendor |
| **wrong vendor resource type** | **415, no body** |

So the original sentence "**ignores `Accept` entirely**" was WRONG — struck above. GC validates
the resource type *before* it negotiates, which is why `Vary` omitting `Accept` is still
accurate and not in tension: `Vary` describes which headers pick among representations the
server WILL serve, not which requests it REFUSES.

The general rule (verified on two public endpoints, see [[accept-header-strictness]]): **a
wrong vendor type 415s; a generic or absent one is served.** The "do not re-probe" instruction
stands for the correct-vs-absent pair only.

**Method lesson worth more than the fact:** a negative result carries an implicit scope, and
the closing generalization is where it gets lost. "Inert" was measured over a 2-cell space and
written as though it covered the whole space. When recording a negative observation, state the
cells actually tested.

## Correction to a common misstatement

`create_session()` does **not** send httpx's bare `*/*`. The web profile applies
`BROWSER_HEADERS`, which sets `Accept: application/json, text/plain, */*`
(`src/http/headers.py`). Captured off the wire. So the divergence between the project's two
callers is "browser-generic vs. GC-vendor-specific," **not** "no header vs. header."

## Reusable method — the bare-vs-bare CONTROL

Generalizes to **any** A/B response comparison against an endpoint that returns signed URLs.

The paired A/B initially showed bodies comparing **unequal**, which looks like a real finding.
It was not. The fix is to run a **control**: two requests with **identical** headers,
back-to-back, diffed the same way.

```
CONTROL   bare#1 vs bare#2 : 1 differing leaf — avatar_url diverges at char 271 of 662
TREATMENT bare vs vendor   : 1 differing leaf — avatar_url diverges at char 271 of 662
bare vs vendor, avatar_url excluded: 0 differing leaves
```

The control produced the **same** single difference as the treatment, attributing it to
per-request CloudFront **re-signing** of `avatar_url` rather than to the header under test.
Without the control, "bodies differ" would have been reported as a header effect.

Two habits this encodes:
1. **Diff structurally (paths + types), then by value** — an eyeball comparison of two ~1 KB
   JSON bodies will miss things and invent others.
2. **Never attribute a difference to your treatment until a same-headers control has ruled
   out request-to-request churn.** Signed URLs, `etag`, and timestamps all churn.

This turned a plausible P1 review finding into a settled non-issue on evidence rather than
argument.

**Now recorded in the endpoint doc (2026-07-25)** — `get-public-teams-public_id.md` carries
this negative observation in its Headers section, including the `Vary` corroboration and an
explicit "do not re-probe." It also contrasts it with the `GET /me/teams` **false-403** trap
(a stale `Accept` version there returns 403 despite valid credentials, per
`.claude/rules/auth-module.md`) so the two are not conflated. The doc was corrected on
2026-07-26 to carry the 415 bound above; it no longer says `Accept` is wholly inert here.

Related: [[accept-header-strictness]], [[public-team-age-group-level-field]],
[[public-team-profile-season-shape]].
