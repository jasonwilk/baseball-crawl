# IDEA-060: Comprehensive Flow Testing and Validation

## Status
`CANDIDATE`

## Summary
Systematic end-to-end testing of every user flow in the system. Partially completed during E-187 evaluation (6 of 14 flows tested). Remaining flows need live testing with real data to verify correctness and discover gaps before coaching staff begins using the system.

## Why It Matters
Every flow tested so far has revealed at least one gap. The report flow found the spray endpoint asymmetry (E-186), stale files, team identity mismatches, and threshold issues (E-187). The opponent flow found missing spray crawl in the web pipeline, missing auto-scout after resolution (IDEA-059). Untested flows likely have undiscovered gaps.

## Flows Tested (2026-03-29)

| # | Flow | Method | Gaps Found |
|---|------|--------|-----------|
| 1 | Report generation (CLI) | `bb report generate` x6 teams | Stale spray files, matplotlib missing, gc_uuid mismatch (North Star), threshold suppression |
| 2 | Report generation (admin UI) | Admin generate button x2 | Same as CLI |
| 3 | Add tracked team (admin UI) | Added Reserve + Bennington | Clean |
| 4 | Sync tracked team (admin Sync) | Synced Reserve + Bennington | No spray crawl (IDEA-059 Gap 1) |
| 5 | Member sync (pipeline trigger) | `run_member_sync` for Freshman Grizzlies | Auto-resolved opponents never scouted (IDEA-059 Gap 1b) |

## Flows Not Yet Tested

| # | Flow | What to Test | Risk |
|---|------|-------------|------|
| 6 | Admin opponent resolve | `/admin/opponents/{link_id}/resolve` -- GC search to connect unresolved opponents. We have 18 unresolved. | Does auto-scout trigger? Does it find the right team? |
| 7 | `bb data scout` CLI | Full CLI scouting path (has spray crawl + gc_uuid resolution unlike web) | Verify CLI path still works after E-186 fallback removal |
| 8 | `bb data resolve-opponents` CLI | CLI opponent resolution | Does it resolve correctly? Does it use public_id filtering? |
| 9 | Dashboard opponent list | `/dashboard/opponents` -- data states (stats/syncing/scoresheet), sorting | Does it render? Are data states correct? |
| 10 | Dashboard opponent detail | Stats, record, spray charts for a specific opponent | Stats correct? Spray missing (known)? Layout issues? |
| 11 | Dashboard player profile | Individual player view with spray chart | Does spray chart render? |
| 12 | `bb data sync` (YAML config) | Full member sync via YAML teams config | Different path than web trigger -- same results? |
| 13 | Re-sync a team | Sync same team twice | Idempotency -- no duplicate data? |
| 14 | Report for team that's also opponent | Generate report for a team already in team_opponents | Does data cross-pollinate? Team identity issues? |

## Rough Timing
After E-187, E-178, and E-180 are complete. Before coaching staff begins using the dashboard for real game prep.

## Dependencies & Blockers
- [ ] E-187 (threshold calibration) -- changes display behavior
- [ ] IDEA-059 (opponent flow gaps) -- fixes known gaps before testing catches them again
- [ ] IDEA-058 (pyproject deps) -- matplotlib needed for CLI spray chart rendering

## Open Questions
- Should this be a testing/QA epic with stories per flow, or an informal walkthrough session?
- Should we automate any of these as integration tests, or are they manual validation only?

## Notes
- Every tested flow found gaps. Expect the untested flows to find more.
- The 18 unresolved opponents from the Freshman Grizzlies sync are ideal test data for flows 6 and 8.
- Dashboard views (flows 9-11) need the app running with a valid session -- can test via the admin UI.

---
Created: 2026-03-29
Last reviewed: 2026-03-29
Review by: 2026-06-27
