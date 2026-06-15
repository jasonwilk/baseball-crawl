# Degraded-opponent acceptance E2E fixture (E-236-08)

**Purpose.** The strong acceptance test for Epic E-236's unifying invariant: when an
opponent's data is degraded, BOTH integrity surfaces (the operator run record AND the
coach footer) tell the truth, and neither false-alarms on the clean parts. Drives the
real `generate_report()` against a transport-only respx mock — see
`tests/test_report_e2e_degraded.py`.

**Sibling, not a fork.** This set lives beside the golden oracle (`tests/fixtures/e2e/`)
and does NOT modify it (AC-1). It reuses the same anonymized team identity (`ExampleTm001`)
but a different, deliberately-degraded game set.

## Scenario — a MIX so a real report still renders (N>0) while degraded

| Game | id (…NNN) | Boxscore | Contributes to N? |
|------|-----------|----------|-------------------|
| 1 | …002 | `boxscore_charted.json` (full, real stats) | **yes** |
| 2 | …004 | `boxscore_empty.json` (sub-case A, empty) | no |
| 3 | …006 | `boxscore_empty.json` (sub-case A, empty) | no |

So **M = 3 completed games, N = 1 with data → 0 < N < M.** A full report (with a footer
trust-block) renders because N>0; a pure N==0 scenario would produce the no_games page
(story 05), which is out of scope here.

Three degradations combined:

- **plays-failing** — every `/plays` fetch returns HTTP 500 (registered by the test, no
  fixture). → `plays_status="failed"`, K (`plays_games_covered`) == 0, `plays_errors` == M.
- **spray-less** — every `/player-stats` returns `spray_null.json` (`spray_chart_data: null`).
  A null chart is a fetch SUCCESS, not an error (TN-1/TN-7), so → `spray_status="completed"`,
  `spray_games_with_data` == 0 (NOT partial/failed — the false-alarm guard).
- **scored-but-empty** — games 2 & 3 use the api-scout-confirmed **sub-case A** boxscore
  (own = slug/no-dashes key + opp = UUID/with-dashes key; both `groups` present per category
  with EMPTY `stats` arrays). The loader writes a games row + final score, zero stat rows,
  `LoadResult.errors=0` → `load_status="completed"`, `crawl_status="completed"`. This is the
  SAME shape story 09's sub-case-A unit test uses (DE CAUTION 2).

## Expected truth on both surfaces (asserted in ONE test so they cannot drift)

**Run record (`report_generation_runs`):** crawl_status=completed, load_status=completed,
plays_status=failed, spray_status=completed, overall_status=completed; M=3, N=1, K=0,
spray_games_with_data=0; derived operator-degraded = true (completed overall + plays failed).

**Coach footer (rendered HTML):** coverage severity reflects N-of-M; "No pitch-detail data"
(K==0); spray "unavailable"; and the coach degraded-confidence line does NOT fire (clean,
anchored identity — no false alarm). The charted game's stats render correctly (negative path).
