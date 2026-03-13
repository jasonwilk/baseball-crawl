# E-104-01: Confirm Athlete-Profile Endpoints and Test Opponent Access

## Epic
[E-104: Athlete Profile Endpoint Probe -- Opponent Player Access](epic.md)

## Status
`TODO`

## Description
After this story is complete, all four athlete-profile endpoints will be independently confirmed (or documented as inaccessible) via live curl, and we will know whether they work for opponent players. The api-scout will first confirm the endpoints work for a known own-team player (control), then test with an opponent player_id from a boxscore (experiment).

## Context
The four athlete-profile endpoints are currently status: OBSERVED from a 2026-03-11 web proxy session. They have never been independently curled. The critical unknown is whether these endpoints are restricted to players with a family/guardian relationship to the authenticated user, or whether they work for any player in GameChanger (including opponents from boxscores).

## Acceptance Criteria
- [ ] **AC-1**: All four athlete-profile endpoints (`/athlete-profile/{id}`, `/athlete-profile/{id}/players`, `/athlete-profile/{id}/career-stats-association`, `/athlete-profile/{id}/career-stats`) are independently curled with a known own-team `athlete_profile_id`. Each endpoint's doc file is updated: `status` to CONFIRMED, `last_confirmed` to today's date, `profiles.web.status` to `confirmed`.
- [ ] **AC-2**: `GET /players/{player_id}` is independently curled with a known own-team player_id. The doc file is updated: `status` to CONFIRMED, `last_confirmed` to today's date. The `person_id` field value is recorded and its relationship to `athlete_profile_id` is documented.
- [ ] **AC-3**: An opponent `player_id` is obtained from boxscore data (either from the database or a live boxscore API call). `GET /players/{opponent_player_id}` is curled. The response (success or error) is documented.
- [ ] **AC-4**: If AC-3 succeeds and yields a `person_id` (or `athlete_profile_id`), all four athlete-profile endpoints are curled with that ID. Results documented: HTTP status code, whether data is returned, any differences from own-team responses.
- [ ] **AC-5**: If any endpoint returns an error for opponent players, the exact HTTP status code and response body are documented in the endpoint doc's caveats section.
- [ ] **AC-6**: A probe summary file is created at `/.project/research/E-104-athlete-profile-probe.md` documenting: (a) which endpoints work for opponents, (b) the lookup path from `player_id` to `athlete_profile_id`, (c) any access restrictions discovered, (d) recommendations for the data pipeline.

## Technical Approach
The api-scout should use the web profile credentials from `.env`. The test strategy is documented in the epic's Technical Notes: own-team first (control), then opponent (experiment). The four endpoint doc files and the `/players/{player_id}` doc file are listed in the epic's Technical Notes with full paths. The api-scout should also check whether the `/teams/{team_id}/players` roster response includes an `athlete_profile_id` field -- this would be an alternative discovery path.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-104-02

## Files to Create or Modify
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id.md` (update status, last_confirmed)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-players.md` (update status, last_confirmed)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats-association.md` (update status, last_confirmed)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats.md` (update status, last_confirmed)
- `docs/api/endpoints/get-players-player_id.md` (update status, last_confirmed, person_id documentation)
- `/.project/research/E-104-athlete-profile-probe.md` (new -- probe summary)

## Agent Hint
api-scout

## Handoff Context
- **Produces for E-104-02**: The probe summary at `/.project/research/E-104-athlete-profile-probe.md` contains the confirmed lookup path (or lack thereof) from `player_id` to `athlete_profile_id`. E-104-02 needs this to know what documentation updates are required.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Endpoint doc files updated with live verification results
- [ ] Probe summary created with clear answers to the three key questions
- [ ] No credentials, tokens, or PII in any committed files

## Notes
- The gc-signature header in curls expires quickly -- execute promptly after constructing.
- If `person_id` is NOT the `athlete_profile_id`, the api-scout should explore whether the `/me/associated-players` endpoint or roster responses contain an `athlete_profile_id` field that could serve as the bridge.
- The `GET /athlete-profile/{id}` base endpoint (profile metadata) is listed in the existing docs but was not mentioned in the user's task description -- include it in testing since a doc already exists.
