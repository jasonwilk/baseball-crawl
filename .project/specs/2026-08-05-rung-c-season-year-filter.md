# Rung (c): should auto-accept require a season-year match?

**Date:** 2026-08-05 · **Status:** **PARKED — BUILD ruled by the operator 2026-08-08**, queued in
README NEXT as its own small chunk after Step 3, not started. Operator semantics: a team
from one YEAR must never auto-match a team from another year; cross-season within the same year
(spring 2026 vs summer 2026) is legitimate; absent `season.year` REFUSES auto-accept
(fail-closed). Compare against the member team's `teams.season_year`. Split out of
`2026-08-04-rung-c-auto-accept-criteria-drift.md` on the operator's call
("track separately; keep that chunk focused").
**Source:** codex spec review of `2026-08-05-rung-c-search-resolve-recoverable.md`, which
refuted the premise this had been shelved on. Measurements below were taken directly.

## The question

`docs/api/flows/opponent-resolution.md` documented, and the code never implemented, a
season-year condition on rung (c) auto-accept:

> **Season year match**: `result.season.year` matches the member team's `season_year`

Rung (c) currently auto-accepts on **exactly one team hit and nothing else** — no name
corroboration, no season corroboration. The single-team count is the entire gate.

## ⚰ Why the old reason for shelving this is RETIRED

The predecessor spec said a season filter *"assumes `result.season.year` is populated and
comparable, which is unverified on this path"*, and a later draft hardened that into
"never observed here — no proxy capture, no fixture, no reader in `src/`."

**Measured against the repo, that is false.** From
`proxy/data/sessions/2026-03-11_032625/endpoint-log.jsonl`, the only real captured
`POST /search` bodies in the repo (2 responses, 15 hits):

- **15/15 hits carry `result.season.year`**, populated — values `2026` and `2025`.
- `tests/fixtures/e2e/search_response.json` and `tests/fixtures/e2e_degraded/search_response.json`
  carry it too.
- Only the narrow claim survives: **nothing in `src/` reads it.** That is a fact about our
  code, not about the data's availability.

**And the filter would have discriminated something real:** one captured query returned a
`{"name": "summer", "year": 2025}` hit in the same result set as `spring 2026` hits. A
season gate is not hypothetical noise-reduction on this data.

⚠ **Sample bound, stated so this is not over-read:** 15 hits from one query family (a single
youth-travel club, 2026-03-11). Enough to refute "never observed"; **not** a census, and not
evidence about how often a stale-season hit is the *only* hit — which is the case that
actually matters, and which nothing here measures.

## What is genuinely open

1. **Plumbing.** `_resolve_via_search(client, opponent_name)`
   (`src/gamechanger/opponent_ladder.py`) does not receive the member team's `season_year`.
   Adding the filter is a signature change plus a caller change in
   `src/reports/morning_run.py::_process_opponent`.
2. **No season column on `opponent_links`.** Nothing durable records which season a mapping
   was made for. Whether that matters depends on (3).
3. **Semantics — the real decision.** Which season must match?
   - The member team's `teams.season_year`? Live DB spans two: **2025 (55 teams), 2026 (432)**.
   - The scheduled game's date-derived year?
   - What about a legitimately cross-season opponent — a fall-ball team playing a spring
     program? A strict equality gate would send those to the operator queue.
4. **Direction of the trade.** This TIGHTENS auto-accept: fewer wrong auto-resolves, more
   opponents punted to the operator queue. That is the opposite trade from the
   entity-class filter (which widened it), and the operator absorbs the difference.

## What changed underneath this while it sat

`2026-08-05-rung-c-search-resolve-recoverable.md` made a `search` resolution **correctable**
via `bb report map-opponent`. That **lowers the urgency** of this filter without removing its
value: a wrong auto-resolve is no longer unrecoverable, but it still has to be *noticed*
first, and an unnoticed one still feeds reports. Prevention and recovery are complements.

## Out of scope

- Do not implement from this stub alone — it is a decision, not a plan.
- Do not re-probe `POST /search` to re-establish that `season.year` exists. It is measured
  above; the bar is the semantics decision, not more data.

## Verification (when this is built)

- `python -m pytest tests/ > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then read the
  file. **Never pipe pytest.**
- `tests/test_opponent_ladder.py` — a stale-season hit is dropped; a matching-season hit is
  accepted; a hit with `season` **absent** must not be silently treated as matching
  (fail-closed, per `.claude/rules/python-style.md`: a missing safety signal defaults to
  REFUSE).
- Fixtures must carry the real shape: `season` is an **object** `{name, year}` on this
  endpoint — NOT the public team profile's flat `team_season` shape. `docs/api/endpoints/post-search.md`
  flags that trap explicitly; do not carry a parser between the two.

## Progress log

- **2026-08-05** — Stubbed. No code, no doc edit. Split from the drift spec after a codex
  spec review refuted the "data unavailable" premise; measurements re-taken directly against
  the capture and fixtures rather than inherited from the review.
