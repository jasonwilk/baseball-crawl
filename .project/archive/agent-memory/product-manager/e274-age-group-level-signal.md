---
name: e274-age-group-level-signal
description: E-274 (read GC's age_group school family as a level signal in detect_league_level) — scope, open gates, measured value, closure obligations, and two refuted over-generalisations. Read before planning or dispatching E-274.
metadata:
  type: project
---

# E-274 — `age_group` School Family as a Structured Level Signal

Status **DRAFT** as of 2026-07-25. Promoted from IDEA-171. Full spec: `/workspaces/baseball-crawl/epics/E-274-*/`.

## Scope

Read GameChanger's `age_group` school family as a structured level signal in `detect_league_level`. **ONE production file**; no schema, no migration, no crawl — the report generator already fetches and passes the value, and SE verified all 7 school values are inert today.

3 stories: **01** SE core, **02** SE (BLOCKED on prevalence; may be ABANDONED), **04** CA pitch-rules ladder.

**Story 03 was REMOVED** — its premise was falsified (no level label reaches the coach at *all* today) and re-filed as IDEA-177. ⚠️ **Its tombstone file needs `git rm` before the planning commit.**

## Open gates

- **OQ-1 and OQ-2** remain open — baseball-coach re-ruling the Reserve veto, whose direction was refuted 0/17.
- **OQ-5 CLOSED**: season present 73/73, all `"spring"` — the premise inverted, so IDEA-168 does **not** sequence first.
- **OQ-6 RETRACTED as INVALID**: it claimed "no HS-opponent report has ever been generated"; the operator corrected that dozens have — they are just expired/purged out of the DB. (Durable: **ask the operator about history; the DB is current state, not a record.**)

**The operator holds a build/shrink/shelve call given the 4% measured value. Not dispatching at all is a legitimate outcome.**

## Measured value — both populations

| Population | Teams changed | Rate |
|---|---|---|
| spring | 3 of 73 | 4.1% |
| summer | 4 of 134 | 3.0% |

**0 of 207 changes move toward LESS rest.** Rates agree; **the MECHANISM is the finding**, not the rate. api-scout's read is **BUILD**, with an honest ceiling: single digits per schedule, concentrated in currently-suppressed cards.

The decisive case: **3 summer school programs play under a SPONSOR name** — no school name, no tier word — where `age_group` is the *only* level signal. All are currently `unknown` → card SUPPRESSED, and they are **unreachable by any name-parsing improvement**. What the data refutes is shelving this *as redundant with the name*.

## Two refuted over-generalisations, both drawn from the same 73

Both were recorded as durable cautions and both are **wrong as properties of the field**:

1. ~~"0 of 73 have no level word; the signals are anti-correlated"~~ — **refuted** by the sponsor-name cases above.
2. ~~"`season` is constant within the school family (all spring), so it cannot disambiguate school tiers"~~ — **refuted**: summer has 13 school-family teams, so **`season` and `age_group` are INDEPENDENT axes**.

Note the shape: one narrow population, two confident generalisations, both false. This does **not** contradict E-272's season-is-discriminating finding, which came from a mixed-family summer/legion population.

## Closure obligations — these survive even if the epic is ABANDONED

In the epic's "Closure Obligations" section. **File them as ideas at closure:**

1. **Verdict-reason rot** — a consultation/assessment verdict's stated REASON can rot independently of the verdict, so a "is there a verdict per domain/trigger?" check passes cleanly while the reason underneath is false. Generalizes to the 8-trigger closure assessment and the ratchet exception.
2. **Consultation PHRASING drives derivation-vs-compression** — "what does X say" and "confirm X" produce different work from the same expert.
3. **Removing a story mid-planning orphans references in ≥4 sections.**

## Settled — do not relitigate

- **Widen the existing recognized-`age_group` step**; do NOT add a rung.
- **Allowlist, NOT a closed enum** — exhaustiveness could not be certified.
- `middle_*` / `elementary` / `college` **TERMINALLY SUPPRESS**.
- Narrow **Reserve-only veto** on the tie-break.

## Live-run context

The escalation run produced 9/9 reports succeeded, zero orphan deletions, and the 3 Reserve teams were the **first real exercise of E-272's NRBL path**.
