# E-234-05: (Stretch) E2E fixture-driven report generation from recorded payloads

## Epic
[E-234: Report Regression Guards](epic.md)

## Status
`TODO`

## Description
After this story is complete, the suite contains one end-to-end report-generation test that mocks only the HTTP transport (feeding recorded GameChanger payloads per-URL) and drives `generate_report()` through its full crawl→load→query→render path. This is the only guard that catches GC payload-shape drift; existing tests mock the crawler/loader and cannot.

## Context
Existing report tests stub the crawler and loader, so they validate orchestration but not the real payload-parsing path. A transport-only mock that replays recorded payloads exercises the parsers against realistic GC shapes. SE judged this feasible (recorded payloads exist in `data/raw/` and `tests/fixtures/game-plays-fresh.json`) but a genuine story, not a freebie — the crawler issues sequenced calls (schedule → per-game boxscore → roster → spray → plays) so the fixture must supply a coherent URL-keyed set. See Technical Notes §TN-5. **This is a clearly-cuttable stretch story.**

## Acceptance Criteria
- [ ] **AC-1**: A test mocks only the HTTP transport (e.g., respx-style, keyed per-URL) with recorded payloads for ONE game-set / ONE team and drives `generate_report()` end to end, asserting a NAMED stat set — team W-L record, ≥1 batting season line, ≥1 pitching season line, and ≥1 plays-derived stat (e.g. FPS%) if present in the chosen game-set — against expected values **hand-computed from the recorded payloads at fixture-curation time** and committed alongside the fixture (the implementer does NOT invent the oracle), per Technical Notes §TN-5. The test reads payloads ONLY from `tests/fixtures/e2e/`, never from `data/raw/` (gitignored, absent in worktrees/CI).
- [ ] **AC-2**: The committed fixture is curated for PII and credentials — any auth headers/tokens stripped per the security rule — before commit, per Technical Notes §TN-5.
- [ ] **AC-3**: The test makes no real network call and requires no credentials.
- [ ] **AC-4**: No `src/` behavior change — additive test and fixture only.

## Technical Approach
Mock at the `create_session`/httpx transport layer and return recorded JSON per endpoint URL. Scope to a single coherent game-set for a single team — prove the transport-mocked path works, expand later. Source payloads from `data/raw/` or `tests/fixtures/`, sanitized. See Technical Notes §TN-5.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_report_e2e.py` (new)
- `tests/fixtures/e2e/` (new — sanitized recorded payloads)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
**Cuttable**: if fixture curation balloons beyond a single session, convert this story to an idea (`IDEA-NNN`) rather than padding the epic — per planning honesty and the lead's direction. The PM may cut this at READY time if the user wants Epic A kept to a half-day.
