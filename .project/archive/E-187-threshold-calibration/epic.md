# E-187: Threshold Calibration for Youth/HS Seasons

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Replace stat suppression with contextual display in scouting reports, fix two E-186 post-review findings (search pagination, integration test gaps), and codify the display philosophy in the context layer. The core principle: **never suppress stats, always contextualize**. Every number displays at full weight with a PA/IP badge showing data depth. Heat-map color richness scales with data depth via graduated intensity tiers. Thresholds are calibrated for 25-game youth/HS seasons.

## Background & Context
After E-186 delivered standalone scouting reports with spray charts, evaluation of 6 reports revealed two problems:

1. **Heat maps nearly blank for early-season teams.** Millard South (5 games, 18 batters) showed almost no heat-map coloring because only 2 batters exceeded the 20 PA threshold. York Varsity (5 games, 15 batters) had the same issue -- 3 qualified at 20 PA vs 10 at 5 PA.

2. **Suppression removes useful information.** Lincoln Southwest Freshman's C Johnson had a 189.0 ERA on 0.1 IP -- mathematically correct and coaching-relevant ("this kid got shelled, pounce if he comes in"). The current renderer dims this to gray and adds an asterisk, making it easy to miss. The user's guidance: "I'd rather see it. We just have to display it in a way that gives it context."

The user's design philosophy: **The system presents data; the coach is the analyst.** Show every number at full visual weight. Give context (PA/IP count) so the coach knows the depth. Don't dim, hide, or suppress based on sample size. Heat-map coloring is a visual signal layer whose richness scales with data depth (graduated intensity per TN-2a) -- it's about progressively adding signal as confidence grows, not hiding data.

Separately, E-186 Codex post-dispatch review identified: (1) `_resolve_gc_uuid` doesn't paginate POST /search, and (2) no integration test covers the resolution wiring.

**Expert consultations** (during planning session 2026-03-29):
- **baseball-coach**: Consulted on threshold appropriateness for HS/youth seasons. Confirmed 25-35 game range, "show with caveats" vs "hide entirely" framing.
- **claude-architect**: Consulted on context-layer placement. Recommended scoped rule for display surfaces, coach agent def update, CLAUDE.md fix. Codified "don't steer when you can define" principle during planning.
- **ux-designer**: Consulted on small-sample visual treatment. Produced detailed design spec: PA/IP badges, suppression removal, graduated heat intensity tiers, season progression. Design incorporated into E-187-02 ACs and TN-2/TN-2a.
- **software-engineer**: Consulted on renderer code structure, existing `_pa` computation, test inventory.

## Goals
- Replace dimming/asterisk/footnote suppression with PA/IP badges on every player
- Lower qualification thresholds to 5 PA (batting) and 6 IP (pitching) for youth/HS seasons
- Add graduated heat intensity (color richness scales with data depth -- light greens early season, full gradient by mid-season)
- Fix the search pagination bug in `_resolve_gc_uuid`
- Add missing integration and pagination tests
- Codify "never suppress, always contextualize" and season-length calibration in the context layer

## Non-Goals
- Adding display changes to the dashboard opponent detail pages (future work -- see IDEA-059)
- Making thresholds user-configurable at runtime
- Changing the heat-map algorithm itself (percentile-based ranking still works fine)
- Rate stat suppression at any sample size (explicitly rejected -- show every number)

## Success Criteria
1. A scouting report for an opponent with 5 games shows all stats at full visual weight with PA/IP badges -- no dimming, no asterisks, no footnotes
2. Heat-map color richness scales with data depth -- subtle greens with 2-3 qualified players, full gradient at 8+
3. `_resolve_gc_uuid` paginates through POST /search results up to 5 pages
4. Integration tests cover the gc_uuid resolution → persist → spray-crawler wiring
5. A context-layer rule codifies both the display philosophy and season-length calibration

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-187-01 | Fix search pagination and add integration tests | DONE | None | - |
| E-187-02 | Replace stat suppression with contextual display | DONE | None | - |
| E-187-03 | Codify display philosophy and season-length calibration in context layer | DONE | None | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### TN-1: Revised Threshold Values

All thresholds live in `src/reports/renderer.py` as module-level constants. The revised values:

| Constant | Current | Revised | Rationale |
|----------|---------|---------|-----------|
| `_MIN_PA_BATTING` | 20 | 5 | ~2 games of PA for a starter (3 PA/game). Shows heat after 2nd game. |
| `_MIN_IP_OUTS_PITCHING` | 45 (15 IP) | 18 (6 IP) | ~2 starts for a HS pitcher (3 IP/start). Shows heat after 2nd outing. |
| `_MIN_BIP_SPRAY` | 3 | 3 | Already appropriate. 3 BIP is the user's stated minimum. |
| `_MIN_BIP_TEAM_SPRAY` | 20 | 20 | Already appropriate. Unchanged. |
| `_KEY_PITCHER_MIN_OUTS` | 45 (15 IP) | 18 (6 IP) | Matches pitching small-sample threshold. |
| `_KEY_BATTER_MIN_PA` | 20 | 5 | Matches batting small-sample threshold. |

The key-player callout thresholds should match the small-sample thresholds. The heat-map algorithm (percentile ranking within qualified players) works correctly regardless of threshold level because it's relative, not absolute.

The code uses strict less-than comparison (`pa < _MIN_PA_BATTING`). A player with exactly 5 PA or 18 ip_outs is considered qualified (not small-sample).

### TN-2: Suppression Removal and Badge Addition

The template (`src/api/templates/reports/scouting_report.html`) currently has these suppression artifacts to REMOVE:
- CSS rule: `tr.small-sample td { color: #9ca3af; }` (dims text to gray)
- HTML: `class="small-sample"` conditional on `<tr>` elements
- HTML: ` *` asterisk appended to player names when `_small_sample`
- HTML: footnote divs ("* Small sample size (fewer than N PA/IP)")

REPLACE with PA/IP badges on every player row:
- `.depth-badge` CSS class: `{ display: inline-block; font-size: 7pt; font-weight: 600; color: #6b7280; background: #f3f4f6; border-radius: 3px; padding: 0 3px; margin-left: 3px; }`
- Batting: `<span class="depth-badge">{{ player._pa }} PA</span>` in the player name cell
- Pitching: `<span class="depth-badge">{{ pitcher.ip_outs | ip_display }} IP</span>` in the player name cell
- Badge shows for ALL players (neutral metadata, not a warning marker)

### TN-2a: Graduated Heat Intensity

Heat-map richness scales with data depth. The percentile algorithm is unchanged. The graduated behavior clamps the maximum heat level based on team depth: `min(computed_level, max_level_for_depth)`. Players below the per-player threshold always get `heat-0`.

**Batting tiers** (UXD design -- optimized for short seasons, starts early, gets rich fast):

| Qualified Batters (5+ PA) | Max Heat Level | Season Phase |
|--------------------------|----------------|--------------|
| 0-2 | 0 (no heat) | Game 1, nobody qualifies yet |
| 3-4 | 1 (lightest green) | Game 2, starters start qualifying |
| 5-6 | 2 | Games 3-4, most starters appearing |
| 7-8 | 3 | Games 4-6, confident ranking |
| 9+ | 4 (full gradient) | Games 5+, full lineup qualifying |

**Pitching tiers** (compressed -- pitching staffs are smaller):

| Qualified Pitchers (6+ IP) | Max Heat Level | Season Phase |
|---------------------------|----------------|--------------|
| 0-1 | 0 (no heat) | Games 1-2, at most the ace qualifies |
| 2 | 1 (lightest green) | Games 3-4, two arms with enough work |
| 3 | 2 | Games 5-7, three rotation arms |
| 4-5 | 3 | Games 8-12, most of the staff |
| 6+ | 4 (full gradient) | Games 15+, full staff exposure |

Design rationale: short seasons need to start showing signal early. The report feels alive from game 2. Each tier step represents ~2 games of additional data, so the coach sees visual progression after every couple of games. By game 5-6 for batting (9 qualifying batters = full lineup), the report is at full richness.

Implementation: iterate the tier table top-down, return first match where `qualified_count >= threshold`. Default is 0.

```python
_BATTING_HEAT_TIERS = [(9, 4), (7, 3), (5, 2), (3, 1)]   # 0-2: max=0
_PITCHING_HEAT_TIERS = [(6, 4), (4, 3), (3, 2), (2, 1)]   # 0-1: max=0
```

### TN-3: Search Pagination Protocol

`_resolve_gc_uuid` in `src/reports/generator.py` must paginate POST /search:
- Start at page 0. If the page returns exactly 25 hits and no match found, increment page and retry.
- Cap at 5 pages (125 results). If no match after 5 pages, return None.
- Return immediately when a matching `public_id` is found.
- The `start_at_page` parameter already exists in the API call -- just needs a loop.
- Per `.claude/rules/gc-uuid-bridge.md:45`: "Paginate if needed."

### TN-4: Integration Test Coverage

Two test gaps to fill in `tests/test_report_generator.py`:
1. **Resolution wiring test**: Seed a team with `gc_uuid=NULL`, mock POST /search to return a match, verify: (a) gc_uuid is stored in the teams table, (b) the resolved gc_uuid is passed to `_crawl_and_load_spray`.
2. **Pagination test**: Mock page 0 with 25 non-matching hits, page 1 with a matching hit. Verify `_resolve_gc_uuid` returns the correct gc_uuid and called POST /search twice.

### TN-5: Context Layer Files

The context-layer story creates:
- New rule: `.claude/rules/display-philosophy.md` -- scoped to display surfaces (`src/reports/**`, `src/api/templates/**`, `src/charts/**`, `src/api/routes/dashboard.py`). Combines "never suppress, always contextualize" + season-length calibration in one file.
- Update: `.claude/agents/baseball-coach.md` -- add season-length context, update threshold references (20 PA → 5 PA, 15 IP → 6 IP), add "never suppress" principle
- Update: CLAUDE.md Data Model section -- fix stale "10 BIP minimum" reference to reflect actual thresholds (3 BIP per player, 20 BIP team)

### TN-6: Test Updates

At minimum 12 tests in `tests/test_report_renderer.py` require updates. The implementing agent must grep for `_MIN_PA_BATTING`, `_MIN_IP_OUTS_PITCHING`, `< 45`, `< 20`, `fewer than 15`, and `fewer than 20` to find all occurrences. Categories of affected tests:

- **Batting threshold tests**: Tests that use PA values between 5 and 19 as "small sample" data (e.g., PA=12, PA=14, PA=19). These are no longer below threshold. Adjust test data to use PA < 5. **Watch for `test_small_sample_all_zero` (line 626)**: uses PA=5 via `ab=5` arithmetic -- won't be caught by grepping for `< 20` or the constant name. PA=5 is now ON the boundary (qualified), so the test must change to PA=4.
- **Pitching threshold tests**: Tests that use `ip_outs` values between 18 and 44 as "small sample" or "not qualified" data (e.g., `ip_outs=30`). These are no longer below threshold. Adjust test data to use `ip_outs < 18`.
- **Inline `_small_sample` assignments**: 8 pitching heat/key-player tests (lines 697-801) manually set `_small_sample` with `< 45` instead of using the constant. Update to `< 18` for consistency.
- **Footnote text assertions**: Tests checking for "fewer than 15 IP" or "fewer than 20 PA" text. These footnotes are REMOVED entirely (not updated) per the display philosophy. Tests asserting their presence should be removed or inverted (assert NOT present).
- **Dimming/asterisk assertions**: Tests checking for `class="small-sample"` or asterisk in player names. These should be removed or inverted.
- **New tests needed**: PA/IP badge rendering, graduated heat intensity tiers, no-dimming verification.

## Open Questions
- None -- all workstreams are well-scoped.

## History
- 2026-03-29: Created. Combines E-186 post-review fixes, threshold calibration, and context-layer codification.
- 2026-03-29: Internal review (11 findings: 4 accepted, 7 dismissed).
- 2026-03-29: Codex review round 1 (9 findings: 5 accepted, 4 dismissed).
- 2026-03-29: Scope expanded after report evaluation: E-187-02 grew from "lower thresholds" to "replace suppression with contextual display" (PA/IP badges, graduated heat). E-187-03 expanded to codify "never suppress, always contextualize." Reverted to DRAFT for re-review.
- 2026-03-29: Codex review round 2 (5 findings: all accepted -- stale gate references, history/status mismatch, propagation cleanup, docs contradiction).
- 2026-03-29: Final holistic review (CR + PM + CA + SE + UXD). CR: 3 low findings (all fixed). PM: verified all ACs achievable, TNs sufficient. CA: confirmed context-layer design sound. SE: confirmed implementation feasible, flagged PA=5 boundary test grep-miss risk (added to TN-6). UXD: 2 minor findings (badge mobile sizing, print border -- deferred to implementation). Set to READY.
- 2026-03-29: Set to ACTIVE, dispatch started.
- 2026-03-29: All stories DONE. CR integration review: APPROVED (0 findings). Codex code review: 4 findings (2 valid and fixed, 2 dismissed). Epic COMPLETED.

### Documentation Assessment
- `docs/coaching/understanding-stats.md` has stale "20 PA / 15 IP" thresholds at lines 179, 188. Routed to docs-writer for update.

### Context-Layer Assessment
- New convention/pattern: **YES** -- display-philosophy.md rule (codified in E-187-03)
- Architectural decision: **YES** -- graduated heat intensity tiers (codified in E-187-03)
- Footgun/failure mode: **No**
- Agent behavior change: **YES** -- baseball-coach agent updated (done in E-187-03)
- Domain knowledge: **YES** -- season-length calibration (codified in E-187-03)
- New CLI command/workflow: **No**

All "yes" items codified during the epic itself (E-187-03). No additional context-layer work needed.

### Review Scorecard (Dispatch)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-187-01 | 1 | 1 | 0 |
| Per-story CR -- E-187-02 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 4 | 2 | 2 |
| **Total** | **5** | **3** | **2** |

### Review Scorecard (Planning)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 5 | 1 | 4 |
| Internal iteration 1 -- Holistic team (PM) | 6 | 3 | 3 |
| Codex review round 1 | 9 | 5 | 4 |
| Codex review round 2 | 5 | 5 | 0 |
| Final holistic review (CR+PM+CA+SE+UXD) | 3 | 3 | 0 |
| **Total** | **28** | **17** | **11** |
| **Total** | **11** | **4** | **7** |
