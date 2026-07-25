# API Scout -- Agent Memory

## Credential Lifecycle

**Three-token architecture confirmed 2026-03-07. Programmatic refresh CONFIRMED WORKING.**

**gc-signature CRACKED 2026-03-07.** Algorithm: `{nonce}.{hmac}` where nonce=Base64(32 random bytes) and hmac=HMAC-SHA256(clientKey, timestamp|nonce_bytes|sorted_body_values[|prevSig_bytes]). Full details: `data/raw/gc-signature-algorithm.md`, `docs/api/auth.md`.

**Three token types:**
- **CLIENT token** (exp-iat = 600s = 10 min): `type:"client"`, `sid`, `cid`, `iat`, `exp`. Anonymous session token.
- **ACCESS token** (~61 min web / ~12 hours mobile): `type:"user"`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp`. Sent as gc-token in all standard API calls.
- **REFRESH token** (14 days, self-renewing): `id` (uuid:uuid), `cid`, `uid`, `email`, `iat`, `exp`. No `type` field, different `kid`. Sent as gc-token in POST /auth refresh calls.

**.env variables:** `GAMECHANGER_REFRESH_TOKEN_WEB`, `GAMECHANGER_CLIENT_ID_WEB`, `GAMECHANGER_CLIENT_KEY_WEB` (SECRET), `GAMECHANGER_DEVICE_ID`, `GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`.

**Mobile profile:** Mobile client IDs are version-specific and rotate with app updates. `0f18f027-...` = Odyssey/2026.8.0 (iOS 26.3.0), `23e37466-2878-43f4-a9f8-5f1751b7efcf` = Odyssey/2026.9.0 (iOS 26.3.1, current as of 2026-03-12). Web client ID: `07cb985d-...`. Mobile client key UNKNOWN (iOS binary). Programmatic mobile refresh NOT POSSIBLE.

**Token validity check**: `GET /me/user` returns 200 OK (valid) or 401 (expired).

**REFRESH TOKEN STATUS**: Last known expired 2026-03-09. Session 2026-03-11_032625 captured new web session data -- credentials must have been refreshed between 2026-03-09 and 2026-03-11.

Credentials are NEVER logged, committed, or displayed. Redact to `{AUTH_TOKEN}` in all docs.

## API Spec Location

Single source of truth: `docs/api/` -- index at `docs/api/README.md`, per-endpoint files in `docs/api/endpoints/` (120 files (119 endpoints + 1 web-routes reference) as of 2026-07-08, E-255-04).

## Exploration Status

As of 2026-03-12. See `docs/api/README.md` for full endpoint index.

## Topic File Index

- [exploration-findings.md](exploration-findings.md) -- Detailed session findings: 2026-03-09 (opponent import flow, game creation, mobile search, progenitor_team_id full access confirmed), 2026-03-11 (E-094 constraints confirmed, gc-user-action values, athlete profile hierarchy, 10 new endpoints), 2026-03-12 (follow-gating confirmed, unfollow 2-step sequence, notification settings, iOS app version). Also: iOS app identity, opponent ID hierarchy (root vs progenitor vs public_id), HTTP 500/404/403 patterns.
- [operational-notes.md](operational-notes.md) -- High-priority unexplored areas (POST /search schema, LSB HS credentials, import-summary), boxscore critical facts (game_stream.id, asymmetric keys, groups), JWT decode tips (exp-iat thresholds), security rules and PII hotspots.
- [mobile-auth-notes.md](mobile-auth-notes.md) -- Mobile authentication specifics and credential capture workflow.
- [client-id-rotation.md](client-id-rotation.md) -- GC client IDs rotate on web redeployments and iOS app updates; never assume permanence
- [search-endpoint-notes.md](search-endpoint-notes.md) -- POST /search folds diacritics server-side; narrow-regex recommendation; 2026-04-16 punct-failure claim didn't fully reproduce 2026-04-17
- [public-games-opponent-identity.md](public-games-opponent-identity.md) -- /public/.../games opponent_team is NAME-only (no public_id/root/progenitor); now returns upcoming games too; refutes scheduler auto-resolve assumption (2026-06-12); + `completed` is TERMINAL, no zero-completed shape, DB-as-prior-snapshot method (longitudinal 2026-07-20)
- [boxscore-empty-shape.md](boxscore-empty-shape.md) -- scored-but-empty boxscore = sub-case A (team-key envelope present, per-player stats empty) → loader errors=0/completed; sub-case B (no keys) is a different failure event (E-236 SQ2)
- [roster-vs-boxscore-identity.md](roster-vs-boxscore-identity.md) -- roster(14)<boxscore(25) explained by /players status="removed"; person_id==id never unifies same-human duplicate UUIDs; /teams/public/.../players auth REQUIRED (verified 2026-06-21)
- [plays-pitch-type-templates.md](plays-pitch-type-templates.md) -- plays at_plate_details emit "Ball 1 (Fastball)"-style pitch-type-tagged templates when scorekeeper charts pitch type; exact-match parser drops them → pitch_count/FPS collapse to 0 (verified 2026-06-28). Also: structured pitch fields + velocity + createdAt live in game-streams/events, not plays
- [boxscore-stats-and-outcome-vocab.md](boxscore-stats-and-outcome-vocab.md) -- boxscore BF/#P/TS/WP live in pitching group's `extra` array (opponents too, not just members); 21-string plays outcome vocab; boxscore BF == completed-PA count exactly (reconcile sizing, 2026-06-29)
- [docs-api-pii-corpus.md](docs-api-pii-corpus.md) -- docs/api embeds real UUIDs + team/venue/person names corpus-wide; denylist can't certify "clean," only a systematic sweep can; auth.md/headers.md client IDs are app constants, NOT PII (2026-07-06, E-254-07)
- [public-team-profile-season-shape.md](public-team-profile-season-shape.md) -- SETTLED: team_season.season = bare string, year FLAT at team_season.year, record singular keys; team_season.season.year is a fabrication. Doc AND testing.md already corrected -- no open action, stop re-probing (2026-07-25)
- [era-basis-and-backsolve-method.md](era-basis-and-backsolve-method.md) -- GC ERA/K/G basis = settings.scorekeeping.bats.innings_per_game (int 6/7, per-team-season, opponent-capable via gc_uuid, NOT on public profile, fallback 7) + the reusable back-solve method for reverse-engineering how GC computes any rate stat (motivated E-264, 2026-07-14)
- [public-team-age-group-level-field.md](public-team-age-group-level-field.md) -- age_group is a polymorphic 3-family LEVEL field (school/travel/rec) w/ high_varsity|high_junior_varsity|high_freshman, ON the public profile at zero cost, 100% populated (91 teams), CONFIRMED on non-managed opponents 25/25; live caveats: operator-entered + enum NOT provably exhaustive; 42% of opponents unreachable upstream. DOC CORRECTIONS LANDED -- read docs/api, don't re-derive. **Joint distribution vs NAME measured n=73: name carries the level 73/73 (signals ANTI-correlated), "Reserve tagged high_varsity" is CONSTRUCTED (0 of 17; all map DOWN), operational disagreement 3/73 w/ age_group right every time** (2026-07-25, E-274)
- [public-team-accept-header-inert.md](public-team-accept-header-inert.md) -- NEGATIVE obs: vendor Accept changes NOTHING on /public/teams/{public_id} (identical bytes, Vary omits Accept) -- don't re-probe; + the reusable bare-vs-bare CONTROL for A/B diffs against signed-URL endpoints (2026-07-25)
- [measurement-discipline.md](measurement-discipline.md) -- VALIDATED 2026-07-25: (1) refuse to answer from adjacent data you already hold — a same-named field on a different endpoint produces an UNDETECTABLE wrong answer; (2) scope a CAUTION as tightly as a number, since a caution propagates where a number gets audited
- [search-opponent-import-regression.md](search-opponent-import-regression.md) -- GET /search/opponent-import 400s on its own documented example; doc+README now downgraded CONFIRMED->OBSERVED w/ Regression section. Open action: capture browser curl for the real Accept version. Its inferred age_group/competition_level rows are likely WRONG (2026-07-25)
